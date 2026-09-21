"""Parse captured Python as data. No imported source is executed."""

import ast
import hashlib
from collections import Counter

from nova_core.contracts import ContractError, digest
from . import seed_ucr

MAX_BYTES = 262144
MAX_NODES = 256


def validate_graph(graph):
    safe = seed_ucr._validate_code_flow(graph)
    if len(safe["nodes"]) > MAX_NODES:
        raise ContractError("graph exceeds the 256-function experiment budget")
    return safe


def parse_source(text, module):
    if not isinstance(text, str) or len(text.encode()) > MAX_BYTES:
        raise ContractError("source exceeds byte budget")
    if not isinstance(module, str) or not module or len(module) > 100:
        raise ContractError("invalid module label")
    try:
        tree = ast.parse(text)
    except (SyntaxError, RecursionError) as exc:
        raise ContractError("source is not parseable Python") from exc
    definitions = []

    def collect(body, scope=(), class_scope=None):
        for node in body:
            if isinstance(node, ast.ClassDef):
                collect(node.body, scope + (node.name,), scope + (node.name,))
            elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                name = scope + (node.name,)
                definitions.append((name, scope, class_scope, node))
                collect(node.body, name, class_scope)
            # Conditional module/class definitions remain visible as static possibilities.
            elif isinstance(node, (ast.If, ast.Try, ast.With)):
                collect(node.body, scope, class_scope)
                collect(getattr(node, "orelse", []), scope, class_scope)
                collect(getattr(node, "finalbody", []), scope, class_scope)
                for handler in getattr(node, "handlers", []):
                    collect(handler.body, scope, class_scope)

    collect(tree.body)
    # Duplicate definitions are ambiguous (overloads/rebinding); never resolve to an arbitrary one.
    counts = Counter(name for name, _, _, _ in definitions)
    known = {name: module + ":" + ".".join(name) for name, _, _, _ in definitions if counts[name] == 1}
    nodes = [{"id": identity, "module": module, "kind": "function"} for identity in known.values()]
    edges, unresolved = set(), 0
    for name, scope, cls, fn in definitions:
        if name not in known:
            continue
        locals_written = {n.id for stmt in fn.body for n in ast.walk(stmt)
                          if isinstance(n, ast.Name) and isinstance(n.ctx, ast.Store)}
        locals_written.update(a.arg for a in fn.args.posonlyargs + fn.args.args + fn.args.kwonlyargs)
        if fn.args.vararg:
            locals_written.add(fn.args.vararg.arg)
        if fn.args.kwarg:
            locals_written.add(fn.args.kwarg.arg)

        class Calls(ast.NodeVisitor):
            def visit_FunctionDef(self, node):
                pass

            visit_AsyncFunctionDef = visit_FunctionDef
            visit_ClassDef = visit_FunctionDef
            visit_Lambda = visit_FunctionDef

            def visit_Call(self, node):
                nonlocal unresolved
                target = None
                callee = node.func
                if isinstance(callee, ast.Name) and callee.id not in locals_written:
                    # Resolve lexical functions, not arbitrary same-name methods in a class.
                    prefixes = [name, scope] if cls is None else [name]
                    prefixes += [()]
                    for prefix in prefixes:
                        if prefix + (callee.id,) in known:
                            target = known[prefix + (callee.id,)]
                            break
                elif (isinstance(callee, ast.Attribute) and isinstance(callee.value, ast.Name)
                      and callee.value.id in ("self", "cls") and cls):
                    target = known.get(cls + (callee.attr,))
                if target is None:
                    unresolved += 1
                else:
                    edges.add((known[name], target, "static_call"))
                self.generic_visit(node)

        visitor = Calls()
        for stmt in fn.body:
            visitor.visit(stmt)
    graph = validate_graph({"nodes": nodes, "edges": [dict(src=a, dst=b, kind=k) for a, b, k in edges]})
    return {"graph": graph, "unresolved_calls": unresolved,
            "ambiguous_definitions": sum(v for v in counts.values() if v > 1),
            "source_sha256": hashlib.sha256(text.encode()).hexdigest(),
            "semantics": "conservative syntactic call candidates; not observed execution or causality"}


def graph_views(graph, count=12):
    """Deterministic induced subgraphs, retaining exact observed node/edge values."""
    graph = validate_graph(graph)
    nodes = graph["nodes"]
    result, seen = [], set()
    for i in range(96):
        if i == 0:
            chosen = nodes
        else:
            ranked = sorted(nodes, key=lambda n: digest([i, n["id"]]))
            size = max(2, len(nodes) * (3 + i % 7) // 10)
            chosen = ranked[:size]
        identities = {n["id"] for n in chosen}
        view = validate_graph({"nodes": chosen, "edges": [e for e in graph["edges"]
                              if e["src"] in identities and e["dst"] in identities]})
        token = digest(view)
        if token not in seen:
            seen.add(token)
            result.append(view)
        if len(result) == count:
            break
    return result

"""Typed relational program synthesis; no registry of target algorithms.

Generic relation composition and bounded fixed-point iteration can construct
new programs. Search is finite and budgeted; this is not unrestricted rewriting.
"""

import ast
from itertools import product

from nova_core.contracts import ContractError, digest, encode

MAX_CANDIDATES = 2048


def tree_size(tree):
    return 1 + sum(tree_size(x) for x in tree[1:] if isinstance(x, list))


def validate(tree, genes, depth=0, in_fix=False, trail=()):
    if type(tree) is not list or not tree or depth > 10 or type(tree[0]) is not str:
        raise ContractError("invalid program tree")
    op = tree[0]
    if op == "const" and len(tree) == 2 and type(tree[1]) is int and abs(tree[1]) <= 1000000:
        return "number"
    if op == "call" and len(tree) == 2 and type(tree[1]) is str:
        if tree[1] not in genes or tree[1] in trail or len(trail) >= 16:
            raise ContractError("missing or cyclic inherited program")
        return validate(genes[tree[1]]["tree"], genes, 0, False, trail + (tree[1],))
    if op in ("edges", "state") and len(tree) == 1:
        if op == "state" and not in_fix:
            raise ContractError("iteration state outside fixed point")
        return "relation"
    if op == "nodes" and len(tree) == 1:
        return "number"
    if op in ("union", "difference", "compose") and len(tree) == 3:
        if all(validate(t, genes, depth + 1, in_fix, trail) == "relation" for t in tree[1:]):
            return "relation"
    if op == "fix" and len(tree) == 3 and not in_fix:
        if (validate(tree[1], genes, depth + 1, False, trail) == "relation" and
                validate(tree[2], genes, depth + 1, True, trail) == "relation"):
            return "relation"
    if op in ("count", "max_out") and len(tree) == 2:
        if validate(tree[1], genes, depth + 1, in_fix, trail) == "relation":
            return "number"
    if op in ("add", "sub", "max") and len(tree) == 3:
        if all(validate(t, genes, depth + 1, in_fix, trail) == "number" for t in tree[1:]):
            return "number"
    raise ContractError("unsupported program or type mismatch")


def execute(tree, graph, genes, state=None):
    op = tree[0]
    if op == "edges":
        return {(e["src"], e["dst"]) for e in graph["edges"]}
    if op == "state":
        return state
    if op == "nodes":
        return len(graph["nodes"])
    if op == "const":
        return tree[1]
    if op == "call":
        return execute(genes[tree[1]]["tree"], graph, genes)
    if op == "fix":
        current = execute(tree[1], graph, genes)
        for _ in range(len(graph["nodes"]) + 1):
            nxt = execute(tree[2], graph, genes, current)
            if nxt == current:
                return current
            current = nxt
        raise ContractError("fixed point did not converge within graph bound")
    a = execute(tree[1], graph, genes, state)
    if op == "count":
        return sum(x != y for x, y in a)
    if op == "max_out":
        counts = {}
        for x, y in a:
            if x != y:
                counts[x] = counts.get(x, 0) + 1
        return max(counts.values(), default=0)
    b = execute(tree[2], graph, genes, state)
    if op == "union":
        return a | b
    if op == "difference":
        return a - b
    if op == "compose":
        grouped = {}
        for x, y in b:
            grouped.setdefault(x, set()).add(y)
        return {(x, z) for x, y in a for z in grouped.get(y, ())}
    if op == "add":
        return a + b
    if op == "sub":
        return a - b
    if op == "max":
        return max(a, b)
    raise ContractError("unknown operation")


def compile_source(tree):
    """Emit self-contained Python, not an alias to a prewritten target family."""
    lines = ["def solve(graph, genes):", "    edges = {(e['src'], e['dst']) for e in graph['edges']}"]
    serial = [0]

    def emit(node, indent="    ", current=None):
        op = node[0]
        if op == "edges":
            return "edges"
        if op == "state":
            return current
        if op == "nodes":
            return "len(graph['nodes'])"
        if op == "const":
            return repr(node[1])
        if op == "call":
            return "genes[" + repr(node[1]) + "](graph, genes)"
        serial[0] += 1
        name = "v" + str(serial[0])
        if op == "fix":
            seed = emit(node[1], indent, current)
            lines.append(indent + name + " = " + seed)
            lines.append(indent + "for _ in range(len(graph['nodes']) + 1):")
            nxt = emit(node[2], indent + "    ", name)
            lines.extend([indent + "    if " + nxt + " == " + name + ":",
                          indent + "        break", indent + "    " + name + " = " + nxt,
                          indent + "else:", indent + "    raise ValueError('fixed point budget')"])
            return name
        a = emit(node[1], indent, current)
        if op == "count":
            expr = "sum(x != y for x, y in " + a + ")"
        elif op == "max_out":
            expr = "max((sum(x == n['id'] and x != y for x, y in " + a + ") for n in graph['nodes']), default=0)"
        else:
            b = emit(node[2], indent, current)
            if op == "compose":
                lines.extend([indent + name + "_index = {}", indent + "for x, y in " + b + ":",
                              indent + "    " + name + "_index.setdefault(x, set()).add(y)"])
                expr = "{(x, z) for x, y in " + a + " for z in " + name + "_index.get(y, ())}"
            elif op == "max":
                expr = "max(" + a + ", " + b + ")"
            else:
                symbol = {"union": "|", "difference": "-", "add": "+", "sub": "-"}[op]
                expr = "(" + a + " " + symbol + " " + b + ")"
        lines.append(indent + name + " = " + expr)
        return name

    output = emit(tree)
    lines.append("    return " + output)
    source = "\n".join(lines) + "\n"
    ast.parse(source)
    return source


def make_program(tree, genes):
    if validate(tree, genes) != "number":
        raise ContractError("a public graph program must return a number")
    body = {"schema": "nova.next.program.v1", "tree": tree, "source": compile_source(tree)}
    return {**body, "id": digest(body)}


def candidates(genes):
    edge, state = ["edges"], ["state"]
    relations = [edge]
    # Enumerate generic recurrence bodies. No target law or oracle enters here.
    for op, left, right in product(("union", "compose", "difference"), (edge, state), (edge, state)):
        body = [op, left, right]
        relations.append(["fix", edge, body])
    for left, right in product((edge, state), (edge, state)):
        relations.append(["fix", edge, ["union", state, ["compose", left, right]]])
    scalar = [["const", 0], ["nodes"]] + [["call", key] for key in sorted(genes)]
    scalar += [[op, relation] for relation in relations for op in ("count", "max_out")]
    scalar.sort(key=lambda t: (tree_size(t), encode(t)))
    # First test inherited compositions: acquiring a mechanism enlarges future search atoms.
    reusable = [["call", key] for key in sorted(genes)]
    combinations = [[op, a, b] for a, b in product(reusable, scalar) for op in ("sub", "add", "max")]
    combinations += [[op, a, b] for a, b in product(scalar, scalar) for op in ("sub", "add")]
    seen = set()
    for tree in scalar + combinations:
        token = digest(tree)
        if token in seen:
            continue
        seen.add(token)
        yield tree
        if len(seen) >= MAX_CANDIDATES:
            break


def synthesize(rows, genes):
    attempts = 0
    for tree in candidates(genes):
        attempts += 1
        try:
            if all(execute(tree, r["graph"], genes) == r["expected"] for r in rows):
                return {"program": make_program(tree, genes), "attempts": attempts}
        except (ContractError, TypeError, ValueError):
            continue
    return {"program": None, "attempts": attempts}


def dependencies(tree):
    if tree[0] == "call":
        return {tree[1]}
    return set().union(*(dependencies(x) for x in tree[1:] if isinstance(x, list))) if len(tree) > 1 else set()

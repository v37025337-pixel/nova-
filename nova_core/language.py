"""A finite expression language and exact Python AST compiler; no user exec."""

import ast
from functools import lru_cache

from .contracts import ContractError, decode, digest, encode, equal, normalized
from . import extensions

LANGUAGE = "nova.expression.v1"
UNARY = ("strip", "lower", "upper", "length", "parse_json", "json", "sum", "sort", "keys")
BINARY = ("add", "sub", "mul", "equal", "less", "get")


def primitive(op, *args):
    a = args[0]
    b = args[1] if len(args) > 1 else None
    numeric = lambda x: type(x) in (int, float)
    if op in ("strip", "lower", "upper") and type(a) is str:
        out = getattr(a, op)()
    elif op == "length" and type(a) in (str, list, dict):
        out = len(a)
    elif op == "parse_json" and type(a) is str:
        out = decode(a)
    elif op == "json":
        out = encode(a)
    elif op == "sum" and type(a) is list and all(numeric(x) for x in a):
        out = sum(a)
    elif op == "sort" and type(a) is list and (all(numeric(x) for x in a) or all(type(x) is str for x in a)):
        out = sorted(a)
    elif op == "keys" and type(a) is dict:
        out = sorted(a)
    elif op in ("add", "sub", "mul", "less") and numeric(a) and numeric(b):
        out = {"add": lambda: a + b, "sub": lambda: a - b,
               "mul": lambda: a * b, "less": lambda: a < b}[op]()
    elif op == "equal":
        out = equal(a, b)
    elif op == "get" and type(a) is dict and type(b) is str:
        out = a[b]
    else:
        raise ContractError("operation/input type mismatch: " + op)
    return normalized(out)


def validate(node, memory, depth=0, budget=None):
    budget = [96] if budget is None else budget
    budget[0] -= 1
    if depth > 8 or budget[0] < 0 or type(node) is not list or not node:
        raise ContractError("invalid or oversized expression")
    tag = node[0]
    if tag == "input" and len(node) == 2 and type(node[1]) is str and len(node[1]) <= 128:
        return
    if tag == "const" and len(node) == 2 and type(node[1]) in (str, int, float, bool, type(None)):
        normalized(node[1])
        return
    if tag == "ref" and len(node) == 2 and type(node[1]) is str and node[1] in memory:
        return
    if (tag == "apply" and len(node) == 3 and type(node[1]) is str and node[1] in memory and
            memory[node[1]].get("language") == extensions.LANGUAGE):
        extensions.check(memory[node[1]])
        validate(node[2], memory, depth + 1, budget)
        return
    if tag == "call" and len(node) >= 2 and type(node[1]) is str:
        arity = 1 if node[1] in UNARY else 2 if node[1] in BINARY else -1
        if len(node) == arity + 2:
            for child in node[2:]:
                validate(child, memory, depth + 1, budget)
            return
    if tag == "object" and len(node) == 2 and type(node[1]) is dict and len(node[1]) <= 8:
        for key, child in node[1].items():
            if type(key) is not str or len(key) > 128:
                raise ContractError("invalid expression field")
            validate(child, memory, depth + 1, budget)
        return
    raise ContractError("unknown expression or unavailable parent")


def dependencies(node):
    if node[0] == "ref":
        return {node[1]}
    if node[0] == "apply":
        return {node[1]} | dependencies(node[2])
    children = node[2:] if node[0] == "call" else node[1].values() if node[0] == "object" else []
    return set().union(*(dependencies(child) for child in children))


def _ast(node):
    tag = node[0]
    if tag == "input":
        return ast.Subscript(ast.Name("inputs", ast.Load()), ast.Constant(node[1]), ast.Load())
    if tag == "const":
        return ast.Constant(node[1])
    if tag == "ref":
        return ast.Call(ast.Name("recall", ast.Load()), [ast.Constant(node[1]), ast.Name("inputs", ast.Load())], [])
    if tag == "apply":
        return ast.Call(ast.Name("recall", ast.Load()), [ast.Constant(node[1]), _ast(node[2])], [])
    if tag == "call":
        return ast.Call(ast.Name("primitive", ast.Load()), [ast.Constant(node[1])] + [_ast(x) for x in node[2:]], [])
    return ast.Dict([ast.Constant(k) for k in sorted(node[1])], [_ast(node[1][k]) for k in sorted(node[1])])


def source(node):
    tree = ast.Module(body=[ast.FunctionDef(name="solve", args=ast.arguments(
        posonlyargs=[], args=[ast.arg(arg="inputs"), ast.arg(arg="recall")],
        kwonlyargs=[], kw_defaults=[], defaults=[]), body=[ast.Return(_ast(node))],
        decorator_list=[])], type_ignores=[])
    return ast.unparse(ast.fix_missing_locations(tree)) + "\n"


def candidate(node, memory):
    validate(node, memory)
    body = {"language": LANGUAGE, "ir": node, "source": source(node),
            "parents": sorted(dependencies(node))}
    return {**body, "id": digest(body)}


def check(program, memory):
    if program.get("language") == extensions.LANGUAGE:
        extensions.check(program)
        return
    if candidate(program["ir"], memory) != program:
        raise ContractError("program/source identity mismatch")


@lru_cache(maxsize=512)
def _compiled(generated_source):
    namespace = {"__builtins__": {}, "primitive": primitive}
    # Only source regenerated from validated IR reaches this function.
    exec(compile(generated_source, "<nova-generated>", "exec"), namespace)
    return namespace["solve"]


def execute(program, inputs, memory):
    inputs = normalized(inputs)
    budget = [4096]
    active = set()

    def run(p, data):
        budget[0] -= 1
        if budget[0] < 0 or len(active) >= 24 or p["id"] in active:
            raise ContractError("program dependency budget or cycle")
        check(p, memory)
        active.add(p["id"])
        try:
            if p.get("language") == extensions.LANGUAGE:
                return extensions.execute(p, data)
            return normalized(_compiled(p["source"])(data, recall))
        finally:
            active.remove(p["id"])

    def recall(pid, data):
        return run(memory[pid], data)

    return run(program, inputs)


def interpret(node, inputs, memory):
    tag = node[0]
    if tag == "input":
        return inputs[node[1]]
    if tag == "const":
        return node[1]
    if tag == "ref":
        return execute(memory[node[1]], inputs, memory)
    if tag == "apply":
        return execute(memory[node[1]], interpret(node[2], inputs, memory), memory)
    if tag == "call":
        return primitive(node[1], *(interpret(x, inputs, memory) for x in node[2:]))
    return {k: interpret(v, inputs, memory) for k, v in node[1].items()}

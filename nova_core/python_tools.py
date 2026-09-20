"""Pure stdlib tool composition; the maintainer supplies tools, never a solution.

No dynamic imports or arbitrary Python plugins. Generated source is regenerated
from bounded IR before compilation, and executes under the existing seccomp
worker. Library algorithms retain their library attribution.
"""

from functools import cmp_to_key, lru_cache
import operator

from .contracts import ContractError, digest, encode, normalized

LANGUAGE = "nova.python-composition.v1"
FUNCTIONS = {"builtins.int": int, "builtins.float": float, "builtins.len": len,
             "builtins.abs": abs, "builtins.sum": sum, "builtins.sorted": sorted,
             "str.strip": str.strip, "str.lower": str.lower, "str.upper": str.upper,
             "str.split": str.split, "operator.lt": operator.lt,
             "operator.eq": operator.eq, "operator.add": operator.add,
             "operator.sub": operator.sub}
BINARY = {"str.split", "operator.lt", "operator.eq", "operator.add", "operator.sub"}
ERRORS = (ContractError, TypeError, ValueError, KeyError, OverflowError)


def catalogue():
    tools = []
    for name in sorted(FUNCTIONS):
        module = name.split(".")[0]
        page = {"builtins": "functions", "str": "stdtypes", "operator": "operator"}[module]
        tools.append({"name": name, "arity": 2 if name in BINARY else 1,
                      "implementation": "Python standard library",
                      "documentation": "https://docs.python.org/3/library/" + page + ".html"})
    body = {"language": LANGUAGE, "tools": tools,
            "combinators": ["map_unary_tool", "stable_sort_by_inherited_relation"],
            "boundary": "bounded JSON values; no imports, files, sockets or callbacks from inputs"}
    return {**body, "id": digest(body)}


def invoke(name, *args):
    if name not in FUNCTIONS or len(args) != (2 if name in BINARY else 1):
        raise ContractError("unknown Python tool or arity")
    args = normalized(list(args))
    return normalized(FUNCTIONS[name](*args))


def lift(name, values):
    if name in BINARY or name not in FUNCTIONS or type(values) is not list:
        raise ContractError("map requires a unary tool and a bounded list")
    return normalized([invoke(name, item) for item in values])


def order(pid, values, recall):
    if type(values) is not list or len(values) > 128 or recall is None:
        raise ContractError("ordering requires a bounded list and inherited relation")
    def compare(left, right):
        forward = recall(pid, {"left": left, "right": right})
        backward = recall(pid, {"left": right, "right": left})
        if type(forward) is not bool or type(backward) is not bool or forward and backward:
            raise ContractError("inherited comparator is not an asymmetric boolean relation")
        return -1 if forward else 1 if backward else 0
    return normalized(sorted(values, key=cmp_to_key(compare)))


def gene(ir, parameters, provenance):
    normalized(ir)
    if (type(parameters) is not list or not 1 <= len(parameters) <= 8 or
            any(type(p) is not str or not p or len(p) > 128 for p in parameters) or
            len(set(parameters)) != len(parameters) or
            type(provenance) is not str or len(provenance) != 64):
        raise ContractError("invalid composition signature or provenance")
    parents, used, budget = set(), set(), [128]
    def source(node, depth=0):
        budget[0] -= 1
        if depth > 8 or budget[0] < 0 or type(node) is not list or len(node) < 2:
            raise ContractError("composition IR budget or shape")
        tag = node[0]
        if tag == "input" and len(node) == 2 and node[1] in parameters:
            return "inputs[" + repr(node[1]) + "]"
        if tag == "const" and len(node) == 2 and type(node[1]) in (str, int, float, bool, type(None)):
            return repr(node[1])
        if tag == "call" and node[1] in FUNCTIONS and len(node) == (4 if node[1] in BINARY else 3):
            used.add(node[1])
            return "invoke(" + repr(node[1]) + ", " + ", ".join(source(n, depth+1) for n in node[2:]) + ")"
        if tag == "map" and len(node) == 3 and node[1] in FUNCTIONS and node[1] not in BINARY:
            used.add(node[1])
            return "lift(" + repr(node[1]) + ", " + source(node[2], depth+1) + ")"
        if tag == "order" and len(node) == 3 and type(node[1]) is str and len(node[1]) == 64:
            parents.add(node[1])
            used.update(["builtins.sorted", "functools.cmp_to_key"])
            return "order(" + repr(node[1]) + ", " + source(node[2], depth+1) + ", recall)"
        raise ContractError("unsupported composition IR")
    generated = "def solve(inputs, recall):\n    return " + source(ir) + "\n"
    body = {"language": LANGUAGE, "ir": ir, "source": generated,
            "definition": {"parameters": parameters}, "provenance": provenance,
            "catalogue": catalogue()["id"], "tools": sorted(used), "parents": sorted(parents),
            "author": "kernel_training_only_library_composition"}
    return {**body, "id": digest(body)}


def check(program):
    if gene(program["ir"], program["definition"]["parameters"], program["provenance"]) != program:
        raise ContractError("Python composition source, tools or provenance mismatch")


@lru_cache(maxsize=256)
def compiled(source):
    namespace = {"__builtins__": {}, "invoke": invoke, "lift": lift, "order": order}
    exec(compile(source, "<nova-python-composition>", "exec"), namespace)
    return namespace["solve"]


def execute(program, inputs, recall=None):
    check(program)
    if type(inputs) is not dict or set(inputs) != set(program["definition"]["parameters"]):
        raise ContractError("Python composition requires exact named inputs")
    return normalized(compiled(program["source"])(normalized(inputs), recall))


def synthesize(training, provenance):
    """Enumerate transformations and binary operations using training data only.

    Delimiters come from input characters. No task name, version-order template,
    holdout, package-specific parser or external oracle is available here.
    """
    parameters = sorted(training[0]["input"])
    target = encode([r["output"] for r in training])
    pool, seen, attempts = [], set(), 0
    def add(ir, values, depth):
        nonlocal attempts
        attempts += 1
        key = encode(values)
        if key in seen:
            return None
        seen.add(key)
        pool.append((ir, values, depth))
        return gene(ir, parameters, provenance) if key == target else None
    for field in parameters:
        result = add(["input", field], [r["input"][field] for r in training], 0)
        if result:
            return {"gene": result, "attempts": attempts}
    separators = sorted({c for row in training for x in row["input"].values()
                         if type(x) is str for c in x if not c.isalnum()})[:16]
    unary = [n for n in sorted(FUNCTIONS) if n not in BINARY]
    for depth in range(3):
        features = list(pool)[:96]
        # Relation/composition is searched at each increasing transformation depth.
        for name in sorted(BINARY - {"str.split"}):
            for a, av, _ in features:
                for b, bv, _ in features:
                    attempts += 1
                    if attempts > 12000:
                        return {"gene": None, "attempts": attempts-1}
                    try:
                        values = [invoke(name, x, y) for x, y in zip(av, bv)]
                    except ERRORS:
                        continue
                    if encode(values) == target:
                        return {"gene": gene(["call", name, a, b], parameters, provenance), "attempts": attempts}
        if depth == 2:
            break
        for ir, values, level in features:
            if level != depth:
                continue
            for name in unary:
                for mapped in (False, True):
                    try:
                        computed = [(lift if mapped else invoke)(name, v) for v in values]
                        result = add(["map" if mapped else "call", name, ir], computed, depth+1)
                    except ERRORS:
                        continue
                    if result:
                        return {"gene": result, "attempts": attempts}
            for sep in separators:
                try:
                    computed = [invoke("str.split", v, sep) for v in values]
                    result = add(["call", "str.split", ir, ["const", sep]], computed, depth+1)
                except ERRORS:
                    continue
                if result:
                    return {"gene": result, "attempts": attempts}
    return {"gene": None, "attempts": attempts}

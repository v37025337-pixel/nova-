"""Specification-derived, bounded word-expression genes. No hash implementation.

The maintainer supplies a compiler and elementary word semantics; the journal
records the external specification and the kernel's generated body separately.
This dialect deliberately does not pretend to understand arbitrary prose/loops.
"""

import ast
import re
from functools import lru_cache
from itertools import islice, product

from .contracts import ContractError, digest, normalized
from . import sequence, python_tools

LANGUAGE = "nova.word-expression.v1"
OPS = {ast.BitXor: "xor", ast.BitAnd: "and", ast.BitOr: "or",
       ast.Add: "add", ast.Sub: "sub", ast.Mult: "mul",
       ast.LShift: "shl", ast.RShift: "shr"}
CALLS = {"ROTR": "rotr", "ROTL": "rotl", "SHR": "shr"}


def is_extension(program):
    return program.get("language") in (LANGUAGE, sequence.LANGUAGE, python_tools.LANGUAGE)


def specification(raw):
    fields = {"id", "source", "title", "width", "text", "provenance"}
    if type(raw) is not dict or set(raw) != fields:
        raise ContractError("specification fields mismatch")
    normalized(raw)
    if (any(type(raw[k]) is not str or not raw[k] for k in fields - {"width"}) or
            not re.fullmatch(r"[A-Za-z0-9_.-]{1,80}", raw["id"]) or
            type(raw["width"]) is not int or not 1 <= raw["width"] <= 32):
        raise ContractError("invalid specification identity or word width")
    return dict(raw)


def parse_expression(expression, parameters, width):
    if type(expression) is not str or len(expression) > 2048:
        raise ContractError("expression too large")
    try:
        parsed = ast.parse(expression.strip(), mode="eval")
    except (SyntaxError, RecursionError) as exc:
        raise ContractError("unsupported mathematical expression") from exc
    budget = [128]

    def visit(node, depth=0):
        budget[0] -= 1
        if budget[0] < 0 or depth > 12:
            raise ContractError("word expression budget")
        if isinstance(node, ast.Name) and node.id in parameters:
            return ["arg", node.id]
        if isinstance(node, ast.Constant) and type(node.value) is int and 0 <= node.value < 2 ** width:
            return ["literal", node.value]
        if isinstance(node, ast.UnaryOp) and isinstance(node.op, ast.Invert):
            return ["not", visit(node.operand, depth + 1)]
        if isinstance(node, ast.BinOp) and type(node.op) in OPS:
            op = OPS[type(node.op)]
            left, right = visit(node.left, depth + 1), visit(node.right, depth + 1)
            if op in ("shl", "shr") and (right[0] != "literal" or right[1] >= width):
                raise ContractError("shift must have a bounded literal count")
            return [op, left, right]
        if (isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and
                node.func.id in CALLS and len(node.args) == 2 and not node.keywords):
            value, count = (visit(x, depth + 1) for x in node.args)
            if count[0] != "literal" or count[1] >= width:
                raise ContractError("rotation must have a bounded literal count")
            return [CALLS[node.func.id], value, count]
        raise ContractError("unsupported syntax in word specification")

    return visit(parsed.body)


def word(op, width, *values):
    mask = (1 << width) - 1
    a = values[0]
    b = values[1] if len(values) > 1 else None
    if op == "not":
        out = ~a
    elif op == "xor":
        out = a ^ b
    elif op == "and":
        out = a & b
    elif op == "or":
        out = a | b
    elif op == "add":
        out = a + b
    elif op == "sub":
        out = a - b
    elif op == "mul":
        out = a * b
    elif op == "shl":
        out = a << b
    elif op == "shr":
        out = a >> b
    elif op == "rotr":
        out = (a >> b) | (a << (width - b))
    elif op == "rotl":
        out = (a << b) | (a >> (width - b))
    else:
        raise ContractError("unknown word operation")
    return out & mask


def generated_source(ir, width):
    def emit(node):
        if node[0] == "arg":
            return ast.Subscript(ast.Name("inputs", ast.Load()), ast.Constant(node[1]), ast.Load())
        if node[0] == "literal":
            return ast.Constant(node[1])
        return ast.Call(ast.Name("word", ast.Load()),
                        [ast.Constant(node[0]), ast.Constant(width)] + [emit(x) for x in node[1:]], [])
    function = ast.FunctionDef(name="solve", args=ast.arguments(
        posonlyargs=[], args=[ast.arg(arg="inputs")], kwonlyargs=[], kw_defaults=[], defaults=[]),
        body=[ast.Return(emit(ir))], decorator_list=[])
    return ast.unparse(ast.fix_missing_locations(ast.Module(body=[function], type_ignores=[]))) + "\n"


def gene(definition, spec_digest):
    if type(definition) is not dict or set(definition) != {"name", "parameters", "width", "expression"}:
        raise ContractError("primitive definition mismatch")
    name, params, width = (definition[k] for k in ("name", "parameters", "width"))
    if (type(name) is not str or not re.fullmatch(r"[A-Za-z][A-Za-z0-9_]{0,63}", name) or
            type(params) is not list or not 1 <= len(params) <= 3 or len(set(params)) != len(params) or
            any(type(p) is not str or not re.fullmatch(r"[a-z][a-z0-9_]{0,15}", p) for p in params) or
            type(width) is not int or not 1 <= width <= 32 or
            type(spec_digest) is not str or not re.fullmatch(r"[0-9a-f]{64}", spec_digest)):
        raise ContractError("primitive parameters or provenance mismatch")
    ir = parse_expression(definition["expression"], params, width)
    body = {"language": LANGUAGE, "definition": definition, "specification": spec_digest,
            "ir": ir, "source": generated_source(ir, width), "parents": []}
    return {**body, "id": digest(body)}


def check(g):
    if g.get("language") == python_tools.LANGUAGE:
        python_tools.check(g)
        return
    if g.get("language") == sequence.LANGUAGE:
        sequence.check(g)
        return
    if gene(g["definition"], g["specification"]) != g:
        raise ContractError("primitive body/source/provenance mismatch")


@lru_cache(maxsize=256)
def compiled(source):
    namespace = {"__builtins__": {}, "word": word}
    exec(compile(source, "<nova-word-gene>", "exec"), namespace)
    return namespace["solve"]


def execute(g, inputs, recall=None):
    if g.get("language") == python_tools.LANGUAGE:
        return python_tools.execute(g, inputs, recall)
    if g.get("language") == sequence.LANGUAGE:
        return sequence.execute(g, inputs)
    check(g)
    params, width = g["definition"]["parameters"], g["definition"]["width"]
    if (type(inputs) is not dict or set(inputs) != set(params) or
            any(type(v) is not int or not 0 <= v < 2 ** width for v in inputs.values())):
        raise ContractError("primitive requires exact unsigned word arguments")
    return compiled(g["source"])(inputs)


def learn(raw):
    """Extract equations from a document, not implementations or oracle answers.

    Recognizes plain f(x,y)=... notation and mathematical PDF glyphs. Formula
    constants come from the document. Names do not select algorithm templates.
    Unsupported control flow is reported, never silently considered compiled.
    """
    spec = specification(raw)
    text = spec["text"].translate(str.maketrans({"": "&", "∧": "&", "": "|", "∨": "|",
                                              "": "^", "⊕": "^", "": "~", "¬": "~"}))
    # Typeset indexed functions are names, not executable dispatch shortcuts.
    text = re.sub(r"[Σ]\s*\{(\d+)\}\s*(\d+)\s*", r"Sigma_\1_\2", text)
    text = re.sub(r"[σ]\s*(\d+)\{(\d+)\}\s*", r"sigma_\2_\1", text)
    text = re.sub(r"\b(ROTR|ROTL|SHR)\s*(\d+)\s*\(([^()]*)\)", r"\1(\3,\2)", text)
    definitions, rejected = [], []
    for line in text.splitlines():
        match = re.fullmatch(r"\s*([A-Za-z][A-Za-z0-9_]*)\s*\(([^()]*)\)\s*=\s*(.+?)\s*", line)
        if not match:
            continue
        name, args, expression = match.groups()
        expression = re.sub(r"\s+\(\d+\.\d+\)\s*$", "", expression)
        definition = {"name": name, "parameters": [x.strip() for x in args.split(",")],
                      "width": spec["width"], "expression": expression}
        try:
            definitions.append(gene(definition, digest(spec)))
        except (ContractError, TypeError, ValueError) as exc:
            rejected.append({"name": name, "reason": str(exc)})
        if len(definitions) + len(rejected) >= 32:
            break
    unsupported = []
    if re.search(r"\bFor\s+\w+\s*=|\bfor\s+\w+\s+in\b", text):
        unsupported.append("indexed_recurrence_and_iteration")
    if re.search(r"\bpad(?:ded|ding)?\b|\bmessage block\b", text, re.I):
        unsupported.append("byte_encoding_padding_and_blocks")
    return {"specification": digest(spec), "genes": definitions, "rejected": rejected,
            "unsupported": unsupported, "author": "kernel_equation_compiler",
            "knowledge_author": spec["provenance"]}


def applications(g, training, memory):
    """Enumerate bounded argument bindings, using training inputs only."""
    from .language import interpret
    if g.get("language") == python_tools.LANGUAGE:
        params = g["definition"]["parameters"]
        if all(set(row["input"]) == set(params) for row in training):
            yield ["apply", g["id"], ["object", {k: ["input", k] for k in params}]]
        return
    width = g["definition"]["width"]
    nodes = [["input", k] for k in sorted(training[0]["input"])]
    nodes += [["ref", pid] for pid, p in memory.items() if not is_extension(p)]
    eligible = []
    for node in nodes[:64]:
        try:
            values = [interpret(node, row["input"], memory) for row in training]
            valid = (all(type(v) is str and len(v.encode("utf-8")) <= sequence.MAX_BYTES for v in values)
                     if g["language"] == sequence.LANGUAGE else
                     all(type(v) is int and 0 <= v < 2 ** width for v in values))
            if valid:
                eligible.append(node)
        except (ContractError, KeyError, TypeError, ValueError, OverflowError, RecursionError):
            continue
    params = g["definition"]["parameters"]
    for args in islice(product(eligible, repeat=len(params)), 256):
        yield ["apply", g["id"], ["object", dict(zip(params, args))]]

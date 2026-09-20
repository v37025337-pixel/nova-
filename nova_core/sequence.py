"""Bounded byte/array/loop genes and an exact AST compiler.

Only elementary operations live here. Constants, functions, assignments, loop
bounds and their order belong to the generated IR, never to a hash template.
"""

import ast
import re
from functools import lru_cache

from .contracts import ContractError, digest, encode, normalized

LANGUAGE = "nova.sequence.v1"
MAX_BYTES = 1024
MAX_ARRAY = 2048
MAX_ITERATIONS = 20000
WORD_OPS = {"add", "sub", "mul", "xor", "and", "or", "not", "shl", "shr", "rotl", "rotr"}
HELPERS = {"utf8": 1, "pad": 6, "chunks": 2, "words": 3, "size": 1, "copy": 1,
           "zeros": 1, "hex": 3, "at": 2}


def name(value):
    if type(value) is not str or not re.fullmatch(r"[A-Za-z][A-Za-z0-9_]{0,47}", value):
        raise ContractError("invalid sequence variable")
    return value


def validate(ir, width):
    from .extensions import gene as word_gene
    if (type(ir) is not dict or set(ir) != {"functions", "body", "result"} or
            type(width) is not int or width not in (8, 16, 32) or
            type(ir["functions"]) is not dict or len(ir["functions"]) > 16):
        raise ContractError("invalid sequence schema or word width")
    for key, definition in ir["functions"].items():
        name(key)
        if definition["name"] != key or definition["width"] != width:
            raise ContractError("sequence function signature mismatch")
        word_gene(definition, "0" * 64)
    budget = [2000]

    def expr(node, known, depth=0):
        budget[0] -= 1
        if budget[0] < 0 or depth > 16 or type(node) is not list or not node:
            raise ContractError("sequence expression budget")
        op = node[0]
        if op == "literal" and len(node) == 2:
            v = node[1]
            if type(v) is int and 0 <= v <= 2 ** 32:
                return
            if type(v) is str and v in ("big", "little"):
                return
            if type(v) is list and len(v) <= 128 and all(type(x) is int and 0 <= x < 2 ** width for x in v):
                return
        if op == "input" and node == ["input", "message"]:
            return
        if op == "var" and len(node) == 2 and name(node[1]) in known:
            return
        if op == "array" and len(node) <= 129:
            for sub in node[1:]:
                expr(sub, known, depth + 1)
            return
        if op == "word" and len(node) >= 3 and node[1] in WORD_OPS:
            arity = 1 if node[1] == "not" else 2
            if len(node) != arity + 2:
                raise ContractError("word arity")
            if node[1] in ("shl", "shr", "rotl", "rotr") and (
                    node[-1][0] != "literal" or type(node[-1][1]) is not int or node[-1][1] >= width):
                raise ContractError("unbounded sequence shift")
            for sub in node[2:]:
                expr(sub, known, depth + 1)
            return
        if op == "call" and len(node) >= 2 and node[1] in ir["functions"]:
            if len(node) != 2 + len(ir["functions"][node[1]]["parameters"]):
                raise ContractError("function arity")
            for sub in node[2:]:
                expr(sub, known, depth + 1)
            return
        if op in HELPERS and len(node) == HELPERS[op] + 1:
            for sub in node[1:]:
                expr(sub, known, depth + 1)
            return
        raise ContractError("unknown expression or use before definition")

    def statements(body, known, depth=0):
        if type(body) is not list or len(body) > 128 or depth > 3:
            raise ContractError("sequence statement budget")
        for row in body:
            budget[0] -= 1
            if budget[0] < 0 or type(row) is not list or not row:
                raise ContractError("sequence body budget")
            if row[0] == "set" and len(row) == 3:
                expr(row[2], known)
                known.add(name(row[1]))
            elif row[0] == "put" and len(row) == 4 and name(row[1]) in known:
                expr(row[2], known)
                expr(row[3], known)
            elif row[0] == "for" and len(row) == 5:
                expr(row[2], known)
                expr(row[3], known)
                statements(row[4], known | {name(row[1])}, depth + 1)
            else:
                raise ContractError("unknown sequence statement")
    known = set()
    statements(ir["body"], known)
    expr(ir["result"], known)


def source(ir, width):
    from .extensions import parse_expression
    def call(key, args):
        return ast.Call(ast.Name(key, ast.Load()), args, [])
    def var(key, ctx=None):
        return ast.Name("v_" + key, ctx or ast.Load())
    def word_expr(node):
        if node[0] == "arg":
            return var(node[1])
        if node[0] == "literal":
            return ast.Constant(node[1])
        return call("word", [ast.Constant(node[0]), ast.Constant(width)] + [word_expr(n) for n in node[1:]])
    def expr(node):
        op = node[0]
        if op == "literal":
            return ast.List([ast.Constant(x) for x in node[1]], ast.Load()) if type(node[1]) is list else ast.Constant(node[1])
        if op == "var":
            return var(node[1])
        if op == "array":
            return ast.List([expr(n) for n in node[1:]], ast.Load())
        if op == "input":
            return ast.Subscript(ast.Name("inputs", ast.Load()), ast.Constant(node[1]), ast.Load())
        if op == "word":
            return call("word", [ast.Constant(node[1]), ast.Constant(width)] + [expr(n) for n in node[2:]])
        if op == "call":
            return call("fn_" + node[1], [expr(n) for n in node[2:]])
        return call("s_" + op, [expr(n) for n in node[1:]])
    def statements(rows):
        result = []
        for row in rows:
            if row[0] == "set":
                result.append(ast.Assign([var(row[1], ast.Store())], expr(row[2])))
            elif row[0] == "put":
                result.append(ast.Expr(call("s_put", [var(row[1]), expr(row[2]), expr(row[3])])))
            else:
                iterator = call("s_range", [expr(row[2]), expr(row[3]), ast.Name("budget", ast.Load())])
                result.append(ast.For(var(row[1], ast.Store()), iterator, statements(row[4]) or [ast.Pass()], []))
        return result
    def function(key, params, body):
        return ast.FunctionDef(key, ast.arguments(posonlyargs=[], args=[ast.arg(arg=p) for p in params],
                               kwonlyargs=[], kw_defaults=[], defaults=[]), body, [])
    functions = []
    for key, definition in sorted(ir["functions"].items()):
        term = parse_expression(definition["expression"], definition["parameters"], width)
        functions.append(function("fn_" + key, ["v_" + p for p in definition["parameters"]], [ast.Return(word_expr(term))]))
    body = [ast.Assign([ast.Name("budget", ast.Store())], ast.List([ast.Constant(MAX_ITERATIONS)], ast.Load()))]
    body += statements(ir["body"]) + [ast.Return(expr(ir["result"]))]
    functions.append(function("solve", ["inputs"], body))
    return ast.unparse(ast.fix_missing_locations(ast.Module(functions, type_ignores=[]))) + "\n"


def gene(ir, width, specifications, derivation):
    validate(ir, width)
    if (type(specifications) is not list or not 1 <= len(specifications) <= 8 or
            any(type(x) is not str or not re.fullmatch(r"[a-f0-9]{64}", x) for x in specifications) or
            type(derivation) is not dict or len(encode(derivation)) > 16000):
        raise ContractError("invalid sequence provenance")
    body = {"language": LANGUAGE, "definition": {"parameters": ["message"], "width": width,
            "input_type": "utf8_text", "max_bytes": MAX_BYTES}, "ir": ir,
            "source": source(ir, width), "specifications": specifications,
            "derivation": derivation, "parents": []}
    return {**body, "id": digest(body)}


def check(g):
    if gene(g["ir"], g["definition"]["width"], g["specifications"], g["derivation"]) != g:
        raise ContractError("sequence IR/source/provenance mismatch")


def _integer(n, maximum=MAX_ARRAY):
    if type(n) is not int or not 0 <= n <= maximum:
        raise ContractError("sequence integer bounds")
    return n


def _array(a):
    if type(a) not in (list, bytes) or len(a) > MAX_ARRAY:
        raise ContractError("sequence array bounds")
    return a


def s_utf8(value):
    if type(value) is not str:
        raise ContractError("sequence requires UTF-8 text")
    data = value.encode("utf-8")
    if len(data) > MAX_BYTES:
        raise ContractError("sequence input byte budget")
    return data


def s_pad(data, bit, target, modulus, length_bits, order):
    if (type(data) is not bytes or len(data) > MAX_BYTES or type(bit) is not int or bit not in (0, 1) or
            any(type(n) is not int or not 8 <= n <= 4096 or n % 8 for n in (target, modulus, length_bits)) or
            target + length_bits != modulus or order not in ("big", "little") or len(data) * 8 >= 2 ** length_bits):
        raise ContractError("unsupported padding congruence")
    zeros = (target // 8 - (len(data) + 1)) % (modulus // 8)
    return data + bytes([bit << 7]) + bytes(zeros) + (len(data) * 8).to_bytes(length_bits // 8, order)


def s_chunks(a, n):
    _array(a)
    _integer(n)
    if not n or len(a) % n:
        raise ContractError("unaligned blocks")
    return [a[i:i+n] for i in range(0, len(a), n)]


def s_words(data, width, order):
    if type(data) is not bytes or width not in (8, 16, 32) or order not in ("big", "little"):
        raise ContractError("invalid word decoding")
    return [int.from_bytes(chunk, order) for chunk in s_chunks(data, width // 8)]


def s_at(a, i):
    _array(a)
    _integer(i)
    if i >= len(a):
        raise ContractError("array index out of range")
    return a[i]


def s_put(a, i, value):
    if type(a) is not list or type(value) is not int or not 0 <= value < 2 ** 32:
        raise ContractError("invalid array assignment")
    s_at(a, i)
    a[i] = value


def s_range(start, stop, budget):
    _integer(start)
    _integer(stop)
    for i in range(start, stop + 1):
        budget[0] -= 1
        if budget[0] < 0:
            raise ContractError("sequence iteration budget")
        yield i


def s_hex(a, width, order):
    _array(a)
    if width not in (8, 16, 32) or order not in ("big", "little") or len(a) > 128:
        raise ContractError("invalid word serialization")
    return b"".join(_integer(n, 2 ** width - 1).to_bytes(width // 8, order) for n in a).hex()


@lru_cache(maxsize=32)
def _compiled(source_text):
    from .extensions import word
    namespace = {"__builtins__": {}, "word": word, "s_utf8": s_utf8, "s_pad": s_pad,
                 "s_chunks": s_chunks, "s_words": s_words, "s_at": s_at, "s_put": s_put,
                 "s_range": s_range, "s_hex": s_hex, "s_size": lambda a: len(_array(a)),
                 "s_copy": lambda a: list(_array(a)), "s_zeros": lambda n: [0] * _integer(n)}
    exec(compile(source_text, "<nova-sequence-gene>", "exec"), namespace)
    return namespace["solve"]


def execute(g, inputs):
    check(g)
    if type(inputs) is not dict or set(inputs) != {"message"}:
        raise ContractError("sequence requires exactly message")
    s_utf8(inputs["message"])
    return normalized(_compiled(g["source"])(inputs))

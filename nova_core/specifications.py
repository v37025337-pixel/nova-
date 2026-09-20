"""Compiler for a documented, typeset block-recurrence notation.

This is a maintainer-written reader, not general natural-language reasoning.
It extracts all arithmetic, constants, temporal references and iteration bounds
from journalled documents. It contains no algorithm-name dispatch, digest
implementation, compression formula, initial vector or round constant table.
"""

import ast
import re

from .contracts import ContractError, digest
from .extensions import OPS, learn as learn_words
from .sequence import gene


def notation(text):
    text = text.translate(str.maketrans({"": "&", "∧": "&", "": "|", "∨": "|", "": "^", "⊕": "^",
                                       "": "~", "¬": "~", "": "+", "": "-", "": "=", "": "<=", "": "≡"}))
    text = re.sub(r"[Σ]\s*\{(\d+)\}\s*(\d+)\s*", r"Sigma_\1_\2", text)
    text = re.sub(r"[Σ]\s*(\d+)\s*\{(\d+)\}\s*", r"Sigma_\2_\1", text)
    text = re.sub(r"[σ]\s*(\d+)\s*\{(\d+)\}\s*", r"sigma_\2_\1", text)
    return text


def required(pattern, text, label, flags=0):
    result = re.search(pattern, text, flags)
    if result is None:
        raise ContractError("SPECIFICATION_MISSING:" + label)
    return result


def term(text, arrays, functions, iteration):
    text = re.sub(r"\{\d+\}", "", text.strip())
    names = "|".join(re.escape(a) for a in sorted(arrays))
    text = re.sub(r"\b(" + names + r")\s*(\d+|[a-z])\s*\(\s*" + re.escape(iteration) + r"\s*-\s*1\s*\)",
                  r"previous_\1[\2]", text)
    text = re.sub(r"\b(" + names + r")\s*(\d+|[a-z])\s*\(\s*" + re.escape(iteration) + r"\s*\)",
                  r"\1[\2]", text)
    text = re.sub(r"\b(" + names + r")\s*([a-z])\s*(?:-\s*(\d+))?(?![a-zA-Z0-9_\[(])",
                  lambda m: m[1] + "[" + m[2] + ("-" + m[3] if m[3] else "") + "]", text)
    try:
        parsed = ast.parse(text, mode="eval").body
    except (SyntaxError, RecursionError) as exc:
        raise ContractError("SPECIFICATION_EXPRESSION_UNSUPPORTED:" + text) from exc

    def visit(node, depth=0):
        if depth > 12:
            raise ContractError("specification expression depth")
        if isinstance(node, ast.Constant) and type(node.value) is int and 0 <= node.value < 2 ** 32:
            return ["literal", node.value]
        if isinstance(node, ast.Name):
            return ["var", node.id]
        if isinstance(node, ast.Subscript) and isinstance(node.value, ast.Name) and (
                node.value.id in arrays or node.value.id in {"previous_" + a for a in arrays}):
            return ["at", ["var", node.value.id], visit(node.slice, depth + 1)]
        if isinstance(node, ast.BinOp) and type(node.op) in OPS:
            return ["word", OPS[type(node.op)], visit(node.left, depth + 1), visit(node.right, depth + 1)]
        if isinstance(node, ast.UnaryOp) and isinstance(node.op, ast.Invert):
            return ["word", "not", visit(node.operand, depth + 1)]
        if (isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id in functions and
                not node.keywords and len(node.args) == len(functions[node.func.id]["parameters"])):
            return ["call", node.func.id] + [visit(a, depth + 1) for a in node.args]
        raise ContractError("SPECIFICATION_EXPRESSION_UNSUPPORTED:" + text)
    return visit(parsed)


def assignments(text, arrays, functions, iteration):
    result = []
    for line in text.splitlines():
        if "=" not in line:
            continue
        if line.count("=") != 1:
            raise ContractError("ambiguous assignment")
        left, right = line.split("=")
        lhs = term(left, arrays, functions, iteration)
        rhs = term(right, arrays, functions, iteration)
        if lhs[0] == "var":
            result.append(["set", lhs[1], rhs])
        elif lhs[0] == "at" and lhs[1][0] == "var" and not lhs[1][1].startswith("previous_"):
            result.append(["put", lhs[1][1], lhs[2], rhs])
        else:
            raise ContractError("unsupported assignment target")
    if not result:
        raise ContractError("no executable assignments in numbered step")
    return result


def compile_documents(documents):
    """No training or held-out rows enter this compiler."""
    if not documents or len({d["width"] for d in documents}) != 1:
        raise ContractError("missing or inconsistent word width")
    width = documents[0]["width"]
    parts = [(d, notation(d["text"])) for d in documents]
    joined = "\n".join(text for _, text in parts)
    orders = set(re.findall(r"[“\"](big|little)-endian[”\"] convention", joined))
    if len(orders) != 1:
        raise ContractError("SPECIFICATION_MISSING:unambiguous_byte_order")
    order = next(iter(orders))
    required(r"Text inputs use UTF-8", joined, "text_encoding_interface")
    required(r"lowercase hexadecimal", joined, "output_encoding_interface")
    pad = required(r"Append the bit [“\"]([01])[”\"].*?≡\s*(\d+)\s*mod\s*(\d+)\s*\..*?Then append the (\d+)-bit block",
                   joined, "padding_congruence", re.S)
    bit, target, modulus, length_bits = map(int, pad.groups())
    if width not in (8, 16, 32) or modulus % width or target + length_bits != modulus:
        raise ContractError("unsupported padding or block alignment")
    algorithms = [(d, t) for d, t in parts if re.search(r"For\s+[a-z]\s*=\s*1\s+to\s+[A-Z]\s*:", t)]
    if len(algorithms) != 1:
        raise ContractError("SPECIFICATION_MISSING:single_block_algorithm")
    algorithm, text = algorithms[0]
    outer = required(r"For\s+([a-z])\s*=\s*1\s+to\s+([A-Z])\s*:", text, "outer_iteration")
    iteration, block_count = outer.groups()
    input_array = required(r"message,\s*([A-Z]),", text, "message_symbol")[1]
    functions = {}
    for d in documents:
        for g in learn_words(d)["genes"]:
            definition = g["definition"]
            if definition["name"] in functions:
                raise ContractError("ambiguous function definitions")
            functions[definition["name"]] = definition
    initial, tables = {}, {}
    for _, block in parts:
        for match in re.finditer(r"^\s*([A-Z])\s*(\d+)\(\s*0\s*\)\s*=\s*([0-9a-fA-F]+)\s*$", block, re.M):
            key, index, value = match.groups()
            bucket = initial.setdefault(key, {})
            if int(index) in bucket or len(value) != width // 4:
                raise ContractError("invalid initial array")
            bucket[int(index)] = int(value, 16)
        marker = re.search(r"constant words are.*?to right\)", block, re.S)
        if marker:
            symbols = re.findall(r"\b([A-Z])\s*0", block[:marker.start()])
            if not symbols:
                raise ContractError("SPECIFICATION_MISSING:constant_array_symbol")
            key = symbols[-1]
            values = []
            for line in block[marker.end():].splitlines():
                items = line.split()
                if items and all(re.fullmatch(r"[0-9a-fA-F]{" + str(width // 4) + "}", x) for x in items):
                    values.extend(int(x, 16) for x in items)
                elif values:
                    break
            if not values or key in tables:
                raise ContractError("missing or ambiguous constant table")
            tables[key] = values
    if not initial or set(initial) & set(tables):
        raise ContractError("SPECIFICATION_MISSING:initial_state")
    for key, entries in initial.items():
        if sorted(entries) != list(range(len(entries))) or len(entries) > 128:
            raise ContractError("initial state has holes")
    start, end = text.index("{", outer.end()), text.rindex("}")
    block_body = text[start+1:end]
    steps = list(re.finditer(r"^\s*(\d+)\.\s+([^\n]+)", block_body, re.M))
    if not steps or [int(s[1]) for s in steps] != list(range(1, len(steps) + 1)):
        raise ContractError("missing or unordered algorithm steps")
    arrays = set(initial) | set(tables) | {input_array}
    schedule = required(r"Prepare the message schedule,\s*\{([A-Z])([a-z])\}", block_body, "schedule_symbol")
    arrays.add(schedule[1])
    lit = lambda value: ["literal", value]
    var = lambda value: ["var", value]
    body = [["set", "novaBytes", ["utf8", ["input", "message"]]],
            ["set", "novaBlocks", ["chunks", ["pad", var("novaBytes"), lit(bit), lit(target), lit(modulus), lit(length_bits), lit(order)], lit(modulus // 8)]]]
    for key, values in sorted(tables.items()):
        body.append(["set", key, lit(values)])
    for key, entries in sorted(initial.items()):
        body.append(["set", key, lit([entries[i] for i in range(len(entries))])])
    block_ir = [["set", "previous_" + key, ["copy", var(key)]] for key in sorted(initial)]
    block_ir.append(["set", input_array, ["words", ["at", var("novaBlocks"), ["word", "sub", var(iteration), lit(1)]], lit(width), lit(order)]])
    trace = []
    for index, step in enumerate(steps):
        content = block_body[step.end():steps[index+1].start() if index+1 < len(steps) else len(block_body)]
        heading = step[2].strip()
        if heading.startswith("Prepare the message schedule"):
            cases = []
            # The case's expression and both bounds are read from each table row.
            pattern = r"^\s*(.+?)\s+(\d+)\s*<=\s*" + re.escape(schedule[2]) + r"\s*<=\s*(\d+)\s*$"
            for match in re.finditer(pattern, content, re.M):
                expression, lower, upper = match.groups()
                cases.append((int(lower), int(upper), term(expression, arrays, functions, iteration)))
            if not cases or cases[0][0] != 0 or any(a > b or b >= 128 for a, b, _ in cases):
                raise ContractError("invalid recurrence cases")
            if any(prev[1] + 1 != nxt[0] for prev, nxt in zip(cases, cases[1:])):
                raise ContractError("recurrence cases overlap or leave gaps")
            block_ir.append(["set", schedule[1], ["zeros", lit(cases[-1][1] + 1)]])
            for lower, upper, expression in cases:
                block_ir.append(["for", schedule[2], lit(lower), lit(upper),
                                 [["put", schedule[1], var(schedule[2]), expression]]])
            trace.append({"step": int(step[1]), "kind": "piecewise_recurrence", "ranges": [[a, b] for a, b, _ in cases]})
        elif heading.startswith("Initialize") or heading.startswith("Compute"):
            parsed = assignments(content, arrays, functions, iteration)
            block_ir.extend(parsed)
            trace.append({"step": int(step[1]), "kind": "ordered_assignments", "count": len(parsed)})
        else:
            loop = re.fullmatch(r"For\s+([a-z])\s*=\s*(\d+)\s+to\s+(\d+)\s*:", heading)
            if not loop or not 0 <= int(loop[2]) <= int(loop[3]) < 128:
                raise ContractError("unsupported numbered step:" + heading)
            parsed = assignments(content, arrays, functions, iteration)
            block_ir.append(["for", loop[1], lit(int(loop[2])), lit(int(loop[3])), parsed])
            trace.append({"step": int(step[1]), "kind": "bounded_iteration", "range": [int(loop[2]), int(loop[3])], "assignments": len(parsed)})
    body.append(["for", iteration, lit(1), ["size", var("novaBlocks")], block_ir])
    outputs = re.findall(r"\b([A-Z])\s*(\d+)\(\s*" + re.escape(block_count) + r"\s*\)", text[end+1:])
    if not outputs or any(key not in initial or int(idx) >= len(initial[key]) for key, idx in outputs):
        raise ContractError("SPECIFICATION_MISSING:ordered_output_words")
    result = ["hex", ["array"] + [["at", var(key), lit(int(idx))] for key, idx in outputs], lit(width), lit(order)]
    ir = {"functions": functions, "body": body, "result": result}
    provenance = {"reader": "typeset_block_recurrence_v1", "algorithm_document": digest(algorithm),
                  "steps": trace, "padding": {"bit": bit, "target": target, "modulus": modulus, "length_bits": length_bits},
                  "constant_counts": {key: len(values) for key, values in tables.items()},
                  "initial_counts": {key: len(entries) for key, entries in initial.items()},
                  "output_indices": [[key, int(idx)] for key, idx in outputs],
                  "encoding": "UTF-8", "byte_order": order,
                  "scope": "specified_algorithm_compilation_not_algorithm_invention"}
    return gene(ir, width, sorted(digest(d) for d in documents), provenance)


def learn(knowledge):
    documents = [knowledge[key] for key in sorted(knowledge)]
    try:
        g = compile_documents(documents)
        return {"compiler": "typeset_block_recurrence_v1", "genes": [g], "missing": [], "author": "kernel_document_compiler"}
    except (ContractError, ValueError, TypeError, KeyError, IndexError, RecursionError) as exc:
        return {"compiler": "typeset_block_recurrence_v1", "genes": [], "missing": [str(exc)], "author": "kernel_document_compiler"}

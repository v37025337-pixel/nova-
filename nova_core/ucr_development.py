"""Training-only UCR proposals translated into Nova's existing expression DSL.

The maintainer supplies this adapter and the finite primitive registry. UCR
chooses compositions; it cannot execute input source, rewrite the runtime or
admit a skill. Its internal split is search data, never fresh gate evidence.
"""

import hashlib
from functools import partial
from pathlib import Path

from nova_tools.universal_code_reader import UniversalCodeReader

from .contracts import ContractError, digest
from .evaluation import score
from .language import BINARY, UNARY, candidate, primitive
from .synthesis import synthesize as native_synthesize

CONFIG = {"max_depth": 3, "generated_per_round": 2048, "candidates_per_round": 12,
          "training_rows": 8, "input_fields": 1, "native_fallback": True}
CONSTANTS = (-1, 0, 1, 2, "", None, True, False)


def manifest():
    root = Path(__file__).resolve().parents[1]
    paths = ("nova_tools/__init__.py", "nova_tools/universal_code_reader.py")
    return {"mechanism": "ucr_training_only_native_expression_proposals_v1",
            "author": "maintainer", "reader_version": UniversalCodeReader.VERSION,
            "config": dict(CONFIG),
            "sources": {p: hashlib.sha256((root / p).read_bytes()).hexdigest() for p in paths}}


def translate(tree, field, depth=0, budget=None):
    """Translate only the exact registered grammar; never parse generated text."""
    budget = [96] if budget is None else budget
    budget[0] -= 1
    if type(tree) is not tuple or not tree or depth > CONFIG["max_depth"] or budget[0] < 0:
        raise ContractError("invalid UCR expression tree")
    if tree[0] == "arg" and len(tree) == 2 and type(tree[1]) is int and tree[1] == 0:
        return ["input", field]
    if len(tree) != 3 or tree[0] != "op" or type(tree[1]) is not str or type(tree[2]) is not tuple:
        raise ContractError("unsupported UCR expression")
    label, children = tree[1], tree[2]
    constants = {f"nova.constant.{i}": value for i, value in enumerate(CONSTANTS)}
    if label in constants and len(children) == 1:
        # Validate even the ignored child; unknown operations cannot hide here.
        translate(children[0], field, depth + 1, budget)
        return ["const", constants[label]]
    op = label.removeprefix("nova.")
    arity = 1 if op in UNARY else 2 if op in BINARY else -1
    if label != "nova." + op or len(children) != arity:
        raise ContractError("unregistered UCR primitive or arity")
    return ["call", op, *[translate(child, field, depth + 1, budget) for child in children]]


def _constant(value, _argument):
    return value


def _reader():
    reader = UniversalCodeReader()
    # The external builtins have different semantics (including equality).
    # Use Nova's exact implementations, then independently score translated IR.
    reader.semantic_primitives.clear()
    for op in UNARY + BINARY:
        reader.register_semantic_primitive("nova." + op, partial(primitive, op),
            arity=1 if op in UNARY else 2,
            category="arithmetic" if op in ("add", "sub", "mul") else "custom",
            commutative=op in ("add", "mul", "equal"),
            provenance={"origin": "nova_native_expression_primitive", "operation": op})
    for index, value in enumerate(CONSTANTS):
        reader.register_semantic_primitive(f"nova.constant.{index}", partial(_constant, value),
            arity=1, category="construction", provenance={"origin": "native_search_constant"})
    return reader


def synthesize(training, memory, policy=None):
    """Accept only training data. A fresh reader prevents ambient learned state."""
    receipt = {"mechanism": "ucr_training_only_native_expression_proposals_v1",
               "reader_version": UniversalCodeReader.VERSION, "training_sha256": digest(training),
               "training_rows": len(training), "fresh_cases_seen": 0,
               "internal_split": "training_partition_used_for_ranking_not_independent_validation",
               "rounds": [], "status": "NO_EXACT_TRAINING_FIT"}
    valid = (2 <= len(training) <= CONFIG["training_rows"] and
             all(type(r["input"]) is dict and len(r["input"]) == 1 for r in training) and
             all(set(r["input"]) == set(training[0]["input"]) for r in training))
    generated = 0
    if valid:
        field = next(iter(training[0]["input"]))
        traces = [{"code": "r = F(arg0)", "inputs": {"arg0": r["input"][field]}, "output": r["output"]}
                  for r in training]
        reader = _reader()
        for depth in range(1, CONFIG["max_depth"] + 1):
            model = reader.infer_compositional_reasoning(traces, max_depth=depth,
                max_generated=CONFIG["generated_per_round"], max_candidates=CONFIG["candidates_per_round"])
            symbol = model.symbols.get("F")
            count = symbol.diagnostics["generated_expression_count"] if symbol else 0
            generated += count
            row = {"depth": depth, "generated": count, "translated": 0, "exact_training_fits": 0}
            receipt["rounds"].append(row)
            for hypothesis in symbol.candidates if symbol else []:
                try:
                    proposed = candidate(translate(hypothesis.tree, field), memory)
                except ContractError:
                    continue
                row["translated"] += 1
                if score(proposed, training, memory)["passed"] != len(training):
                    continue
                row["exact_training_fits"] += 1
                receipt.update(status="TRAINING_FIT", selected_expression=hypothesis.expression,
                               selected_program=proposed["id"])
                return {"program": proposed, "attempts": generated, "native_attempts": 0,
                        "selection": "training_only", "ucr": receipt}
    else:
        receipt["status"] = "UNSUPPORTED_INPUT_SHAPE"
    fallback = native_synthesize(training, memory, policy)
    return {**fallback, "attempts": generated + fallback["attempts"],
            "native_attempts": fallback["attempts"], "ucr": receipt}

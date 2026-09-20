"""Training-only, bounded enumerative synthesis with verified program reuse."""

from .contracts import ContractError, encode, equal
from .language import BINARY, UNARY, candidate, interpret

MAX_ATTEMPTS = 12000
MAX_DEPTH = 3
ERRORS = (ContractError, KeyError, TypeError, ValueError, OverflowError, RecursionError)


def synthesize(training, memory):
    """No holdout argument exists. The first exact training fit is frozen."""
    pool, seen = [], set()
    attempts = 0
    desired = [row["output"] for row in training]

    def add(node, depth):
        nonlocal attempts
        if attempts >= MAX_ATTEMPTS:
            return None
        attempts += 1
        try:
            values = [interpret(node, row["input"], memory) for row in training]
            signature = encode(values)
            if signature in seen:
                return None
            seen.add(signature)
            item = (node, depth, values)
            pool.append(item)
            return item
        except ERRORS:
            return None

    def matches(values, targets):
        return all(equal(a, b) for a, b in zip(values, targets))

    def assemble(targets, depth=0):
        for node, _, values in pool:
            if matches(values, targets):
                return node
        if depth < 3 and all(type(x) is dict and set(x) == set(targets[0]) for x in targets) and len(targets[0]) <= 8:
            fields = {k: assemble([x[k] for x in targets], depth + 1) for k in sorted(targets[0])}
            if all(v is not None for v in fields.values()):
                return ["object", fields]
        return None

    def result():
        node = assemble(desired)
        if node is not None:
            try:
                return {"program": candidate(node, memory), "attempts": attempts,
                        "selection": "training_only"}
            except ERRORS:
                pass
        return None

    for key in sorted(training[0]["input"]):
        add(["input", key], 0)
    for pid in memory:
        add(["ref", pid], 0)
    constants = [-1, 0, 1, 2, "", None, True, False]
    for row in training:
        for val in row["input"].values():
            if type(val) is dict:
                constants.extend(sorted(val))
    if all(equal(x, desired[0]) for x in desired) and type(desired[0]) in (str, int, float, bool, type(None)):
        constants.append(desired[0])
    for val in constants[:64]:
        add(["const", val], 0)
    found = result()
    if found:
        return found
    for depth in range(1, MAX_DEPTH + 1):
        previous = list(pool)
        frontier = [item for item in previous if item[1] == depth - 1][:96]
        for node, _, _ in frontier:
            for op in UNARY:
                add(["call", op, node], depth)
        found = result()
        if found:
            return found
        for left, ld, _ in previous[:64]:
            for right, rd, _ in previous[:64]:
                if max(ld, rd) != depth - 1:
                    continue
                for op in BINARY:
                    add(["call", op, left, right], depth)
                if attempts >= MAX_ATTEMPTS:
                    break
            if attempts >= MAX_ATTEMPTS:
                break
        found = result()
        if found:
            return found
        if attempts >= MAX_ATTEMPTS:
            break
    return {"program": None, "attempts": attempts, "selection": "training_only"}

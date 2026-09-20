"""Training-only, bounded enumerative synthesis with verified program reuse."""

from .contracts import ContractError, digest, encode, equal
from .language import BINARY, UNARY, candidate, interpret, primitive
from .extensions import applications, is_extension

MAX_ATTEMPTS = 12000
MAX_DEPTH = 3
ERRORS = (ContractError, KeyError, TypeError, ValueError, OverflowError, RecursionError)


def check_policy(policy):
    fields = {"schema", "parent", "depth", "attempts", "unary", "binary", "typed", "early_stop", "unary_first", "queue", "id"}
    if type(policy) is not dict or set(policy) != fields:
        raise ContractError("invalid engine policy fields")
    if (policy["schema"] != "nova.engine-policy.v1" or
            policy["parent"] is not None and (type(policy["parent"]) is not str or len(policy["parent"]) != 64) or
            type(policy["depth"]) is not int or not 1 <= policy["depth"] <= 4 or
            type(policy["attempts"]) is not int or policy["attempts"] != MAX_ATTEMPTS or
            type(policy["unary"]) is not list or sorted(policy["unary"]) != sorted(UNARY) or
            type(policy["binary"]) is not list or sorted(policy["binary"]) != sorted(BINARY) or
            any(type(policy[key]) is not bool for key in ("typed", "early_stop", "unary_first")) or
            policy["queue"] != "deficit_then_previous_cost" or
            digest({k: v for k, v in policy.items() if k != "id"}) != policy["id"]):
        raise ContractError("engine policy identity or bounds mismatch")


def accepts(op, *values):
    """Necessary type conditions only; actual execution still verifies the value."""
    a = values[0]
    if op in ("strip", "lower", "upper", "parse_json"):
        return type(a) is str
    if op == "length":
        return type(a) in (str, list, dict)
    if op in ("sum", "sort"):
        return type(a) is list
    if op == "keys":
        return type(a) is dict
    if op in ("add", "sub", "mul", "less"):
        return all(type(v) in (int, float) for v in values)
    if op == "get":
        return type(a) is dict and type(values[1]) is str
    return True


def synthesize(training, memory, policy=None):
    """No holdout argument exists. The first exact training fit is frozen."""
    pool, seen = [], set()
    if policy is not None:
        check_policy(policy)
    attempts, considered, pruned = 0, 0, 0
    solution = None
    visited = set()
    unary = policy["unary"] if policy else UNARY
    binary = policy["binary"] if policy else BINARY
    max_depth = policy["depth"] if policy else MAX_DEPTH
    desired = [row["output"] for row in training]

    def add(node, depth, operands=None):
        nonlocal attempts, considered, pruned, solution
        if attempts >= MAX_ATTEMPTS or solution is not None:
            return None
        if policy:
            token = encode(node)
            if token in visited:
                return None
            visited.add(token)
        considered += 1
        if policy and policy["typed"] and operands is not None:
            if not all(accepts(node[1], *values) for values in zip(*operands)):
                pruned += 1
                return None
        attempts += 1
        try:
            # All language primitives are pure. Operand values have already
            # been interpreted on these exact training rows. Reusing them
            # preserves search order, receipts and results while avoiding
            # repeated execution of expensive inherited genes (e.g. hashing).
            values = ([primitive(node[1], *args) for args in zip(*operands)]
                      if operands is not None else
                      [interpret(node, row["input"], memory) for row in training])
            signature = encode(values)
            if signature in seen:
                return None
            seen.add(signature)
            item = (node, depth, values)
            pool.append(item)
            if policy and policy["early_stop"]:
                proposed = node if matches(values, desired) else assemble(desired) if type(desired[0]) is dict else None
                if proposed is not None:
                    try:
                        solution = candidate(proposed, memory)
                    except ERRORS:
                        pass
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
        if solution is not None:
            return receipt(solution)
        node = assemble(desired)
        if node is not None:
            try:
                return receipt(candidate(node, memory))
            except ERRORS:
                pass
        return None

    def receipt(program):
        body = {"program": program, "attempts": attempts, "selection": "training_only"}
        if policy:
            body.update(engine=policy["id"], considered=considered, type_pruned=pruned)
        return body

    for key in sorted(training[0]["input"]):
        add(["input", key], 0)
    for pid, p in memory.items():
        if not is_extension(p):
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
    for p in memory.values():
        if is_extension(p):
            for node in applications(p, training, memory):
                add(node, 1)
    found = result()
    if found:
        return found
    if policy and policy["unary_first"]:
        for depth in range(1, max_depth + 1):
            for node, _, values in [item for item in pool if item[1] == depth - 1][:96]:
                for op in unary:
                    add(["call", op, node], depth, [values])
            found = result()
            if found:
                return found
    for depth in range(1, max_depth + 1):
        previous = [item for item in pool if item[1] < depth]
        frontier = [item for item in previous if item[1] == depth - 1][:96]
        for node, _, values in frontier:
            for op in unary:
                add(["call", op, node], depth, [values])
        found = result()
        if found:
            return found
        for left, ld, lv in previous[:64]:
            for right, rd, rv in previous[:64]:
                if max(ld, rd) != depth - 1:
                    continue
                for op in binary:
                    add(["call", op, left, right], depth, [lv, rv])
                if attempts >= MAX_ATTEMPTS or solution is not None:
                    break
            if attempts >= MAX_ATTEMPTS or solution is not None:
                break
        found = result()
        if found:
            return found
        if attempts >= MAX_ATTEMPTS:
            break
    return receipt(None)

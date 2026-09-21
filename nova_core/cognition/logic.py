"""Bounded Horn inference with explicit negation, provenance and four verdicts.

Conflicting evidence is retained. A contradiction does not imply arbitrary facts.
No reasoning claim here implies subjective awareness or universal theorem proving.
"""

from itertools import product
import re

from nova_core.contracts import ContractError, digest


def atom(raw, variables=False):
    if type(raw) is not list or not 1 <= len(raw) <= 5:
        raise ContractError("atom requires predicate and up to four arguments")
    for token in raw:
        if type(token) is not str or not re.fullmatch(r"[!?A-Za-z0-9_.:/-]{1,100}", token):
            raise ContractError("invalid logic token")
        if token.startswith("?") and not variables:
            raise ContractError("facts must be ground")
    if raw[0].startswith("?") or raw[0] == "!":
        raise ContractError("predicate must be fixed")
    return tuple(raw)


def opposite(value):
    return ((value[0][1:] if value[0].startswith("!") else "!" + value[0]), *value[1:])


def match(pattern, fact, bindings):
    if len(pattern) != len(fact) or pattern[0] != fact[0]:
        return None
    result = dict(bindings)
    for variable, value in zip(pattern[1:], fact[1:]):
        if variable.startswith("?"):
            if variable in result and result[variable] != value:
                return None
            result[variable] = value
        elif variable != value:
            return None
    return result


def reason(facts, rules, query):
    query = atom(query)
    if type(facts) is not list or len(facts) > 128 or type(rules) is not list or len(rules) > 32:
        raise ContractError("reasoning input budget")
    proofs = {}
    for i, raw in enumerate(facts):
        value = atom(raw)
        proofs.setdefault(value, {"kind": "observation", "index": i, "id": digest(list(value))})
    normalized, ids = [], set()
    for rule in rules:
        if (type(rule) is not dict or set(rule) != {"id", "if", "then"} or type(rule["id"]) is not str
                or not rule["id"] or len(rule["id"]) > 80 or rule["id"] in ids
                or type(rule["if"]) is not list or not 1 <= len(rule["if"]) <= 4):
            raise ContractError("invalid or duplicate inference rule")
        premises = [atom(v, True) for v in rule["if"]]
        conclusion = atom(rule["then"], True)
        known = {x for p in premises for x in p if x.startswith("?")}
        if any(x.startswith("?") and x not in known for x in conclusion):
            raise ContractError("conclusion contains unbound variable")
        ids.add(rule["id"])
        normalized.append((rule["id"], premises, conclusion))
    attempts, exhausted = 0, False
    for _ in range(128):
        changed = False
        for identity, premises, conclusion in normalized:
            joins = [({}, [])]
            for pattern in premises:
                following = []
                for (bindings, support), fact in product(joins, list(proofs)):
                    attempts += 1
                    if attempts > 50_000:
                        exhausted = True
                        break
                    found = match(pattern, fact, bindings)
                    if found is not None:
                        following.append((found, support + [proofs[fact]["id"]]))
                joins = following
                if exhausted:
                    break
            for bindings, support in joins:
                if exhausted:
                    break
                value = tuple(bindings.get(x, x) for x in conclusion)
                if value not in proofs:
                    if len(proofs) >= 256:
                        exhausted = True
                        break
                    proofs[value] = {"kind": "inference", "rule": identity, "premises": support,
                                     "id": digest(list(value))}
                    changed = True
            if exhausted:
                break
        if not changed or exhausted:
            break
    positive, negative = query in proofs, opposite(query) in proofs
    verdict = "BOTH" if positive and negative else "TRUE" if positive else "FALSE" if negative else "UNKNOWN"
    return {"verdict": verdict, "query": list(query), "complete": not exhausted,
            "budget_exhausted": exhausted, "matching_steps": attempts,
            "support": proofs.get(query), "counter_support": proofs.get(opposite(query)),
            "proofs": [{"atom": list(k), **v} for k, v in sorted(proofs.items())],
            "semantics": "four-valued bounded Horn inference with explicit negation"}

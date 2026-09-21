"""Typed action planning and evidence-conditioned cost; no embedded workflow path."""

import heapq

from nova_core.contracts import ContractError, digest


def action_cost(action, experience):
    history = experience.get(action["id"], {"success": 0, "failure": 0})
    # Laplace-smoothed reliability, with a bounded penalty for observed failure.
    numerator = history["success"] + history["failure"] + 2
    denominator = history["success"] + 1
    return action.get("cost", 1) * numerator / denominator


def plan(catalog, available, goal, experience=None, disabled=()):
    if type(goal) is not str or len(goal) > 160 or len(available) > 64:
        raise ContractError("invalid planning goal or input budget")
    experience = experience or {}
    actions = [a for a in catalog.values() if a["id"] not in disabled]
    relevant = {goal}
    for _ in range(len(actions) + 1):
        previous = set(relevant)
        for action in actions:
            if action["output"] in relevant:
                relevant.update(action["inputs"].values())
        if previous == relevant:
            break
    actions = [a for a in actions if a["output"] in relevant]
    initial = frozenset(available)
    frontier, best, serial = [(0.0, 0, initial, [])], {initial: 0.0}, 0
    expanded = 0
    while frontier and expanded < 2048:
        cost, _, known, path = heapq.heappop(frontier)
        if cost != best[known]:
            continue
        expanded += 1
        if goal in known:
            body = {"status": "PLANNED", "goal": goal, "actions": path,
                    "cost": cost, "expanded": expanded, "initial_types": sorted(initial)}
            return {**body, "id": digest(body)}
        if len(path) >= 12:
            continue
        for action in sorted(actions, key=lambda a: a["id"]):
            if action["output"] in known or not set(action["inputs"].values()) <= known:
                continue
            reached = known | {action["output"]}
            following_cost = cost + action_cost(action, experience)
            if following_cost >= best.get(reached, float("inf")):
                continue
            best[reached] = following_cost
            serial += 1
            heapq.heappush(frontier, (following_cost, serial, reached, path + [action["id"]]))
    return {"status": "UNREACHABLE", "goal": goal, "expanded": expanded,
            "reason": "PLANNING_BUDGET" if frontier else "MISSING_CAPABILITY_OR_INPUT"}

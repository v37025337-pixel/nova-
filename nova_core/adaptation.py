"""Pure engine-policy genetics and evidence, reduced by the one kernel loop."""

from collections import Counter

from .contracts import ContractError, dataset_id, digest, task_spec
from .evaluation import score
from .genetics import genome
from .language import BINARY, UNARY, execute
from .synthesis import ERRORS, MAX_ATTEMPTS, MAX_DEPTH, synthesize
from .extensions import LANGUAGE as WORD_LANGUAGE


def trial_spec(raw):
    if type(raw) is not dict or set(raw) != {"id", "tasks"}:
        raise ContractError("engine trial requires exactly id and tasks")
    if type(raw["tasks"]) is not list or not 1 <= len(raw["tasks"]) <= 8:
        raise ContractError("engine trial requires 1..8 validation tasks")
    tasks = [task_spec(t) for t in raw["tasks"]]
    task_spec({**tasks[0], "id": raw["id"]})
    if len({t["id"] for t in tasks}) != len(tasks):
        raise ContractError("duplicate engine validation task")
    inputs = [digest(row["input"]) for t in tasks for split in ("train", "holdout") for row in t[split]]
    if len(inputs) != len(set(inputs)):
        raise ContractError("engine validation tasks must have distinct inputs")
    return {"id": raw["id"], "tasks": tasks}


def trial_dataset(trial):
    return "engine:" + digest(sorted(dataset_id(task) for task in trial["tasks"]))


def input_tokens(tasks):
    return {digest(row["input"]) for task in tasks for split in ("train", "holdout") for row in task[split]}


def derive_policy(programs, previous=None):
    """Native mutation rule. No validation task or holdout is an argument."""
    counts = Counter()

    def walk(node):
        if node[0] == "call":
            counts[node[1]] += 1
            for child in node[2:]:
                walk(child)
        elif node[0] == "object":
            for child in node[1].values():
                walk(child)
        elif node[0] == "apply":
            walk(node[2])

    for program in programs.values():
        if program.get("language") != WORD_LANGUAGE:
            walk(program["ir"])
    rank = lambda operations: sorted(operations, key=lambda op: (-counts[op], operations.index(op)))
    body = {"schema": "nova.engine-policy.v1", "parent": previous["id"] if previous else None,
            "depth": min(4, (previous["depth"] if previous else MAX_DEPTH) + 1), "attempts": MAX_ATTEMPTS,
            "unary": rank(UNARY), "binary": rank(BINARY), "typed": True, "early_stop": True,
            "unary_first": sum(counts[op] for op in UNARY) >= sum(counts[op] for op in BINARY),
            "queue": "deficit_then_previous_cost"}
    return {**body, "id": digest(body)}, dict(sorted(counts.items()))


def compatible(memory, rows):
    usable = {}
    for pid, program in memory.items():
        if program.get("language") == WORD_LANGUAGE:
            usable[pid] = program
            continue
        try:
            for row in rows:
                execute(program, row["input"], memory)
            usable[pid] = program
        except ERRORS:
            continue
    return usable


def successful(result, rows, memory):
    if result["program"] is None:
        return False
    observed = score(result["program"], rows, memory)
    return observed["passed"] == observed["total"]


def engine_proposal(state, selection, memory):
    parent = state["genomes"][state["current"]]
    active = state["generations"][state["current"]]
    trial = state["engine_trials"][selection["task"]]
    candidate, counts = derive_policy(memory, parent.get("engine"))
    # Reconstruct pre-admission memory: benchmarking a task with its own answer
    # already in recall would give misleading search-cost evidence.
    rows = []
    for tid, pid in sorted(active.items()):
        task = state["tasks"][tid]
        admitted_at = next(h["event"] for h in state["experience"][tid]
                           if h["status"] == "ADMITTED" and h["program"] == pid)
        earlier = {p: gene for p, gene in memory.items() if state["gene_events"][p] < admitted_at and p != pid}
        earlier = compatible(earlier, task["train"])
        before = synthesize(task["train"], earlier, parent.get("engine"))
        after = synthesize(task["train"], earlier, candidate)
        rows.append({"task": tid, "memory": sorted(earlier),
                     "parent_attempts": before["attempts"], "candidate_attempts": after["attempts"],
                     "parent_solved": successful(before, task["train"], earlier),
                     "candidate_solved": successful(after, task["train"], earlier)})
    training = {"tasks": rows, "parent_attempts": sum(r["parent_attempts"] for r in rows),
                "candidate_attempts": sum(r["candidate_attempts"] for r in rows)}
    improved = bool(rows) and all(r["candidate_solved"] for r in rows) and training["candidate_attempts"] < training["parent_attempts"]
    # One frozen policy sees the reserved validation suite. Failed evaluation
    # consumes the suite too; there is no holdout-guided candidate retry.
    validation = []
    if improved:
        for task in trial["tasks"]:
            inherited = compatible(memory, task["train"])
            result = synthesize(task["train"], inherited, candidate)
            program = result.pop("program")
            validation.append({"task": task["id"], "program": program, "synthesis": result,
                               "train": score(program, task["train"], inherited) if program else None,
                               "holdout": score(program, task["holdout"], inherited) if program else None})
    regression = {tid: score(memory[pid], state["tasks"][tid]["train"] + state["tasks"][tid]["holdout"], memory)
                  for tid, pid in sorted(active.items())}
    reason = "VERIFIED_ENGINE_IMPROVEMENT"
    if not improved:
        reason = "NO_ENGINE_TRAINING_IMPROVEMENT"
    elif any(v["program"] is None or any(v[split]["passed"] != v[split]["total"] for split in ("train", "holdout")) for v in validation):
        reason = "ENGINE_VALIDATION_FAILED"
    elif any(r["passed"] != r["total"] for r in regression.values()):
        reason = "REGRESSION_FAILED"
    report = {"training": training, "validation": validation, "regression": regression,
              "frozen_candidate": candidate["id"], "reason": reason}
    child = genome(active, parent["id"], candidate, parent.get("capabilities"))
    mutation = {"kind": "EVOLVE_ENGINE_POLICY", "parent_genome": parent["id"], "child_genome": child,
                "inherited_genes": parent["genes"], "added_genes": [],
                "engine_parent": candidate["parent"], "engine_child": candidate["id"]}
    causes = {"task_event": state["task_events"][selection["task"]], "previous_attempt": None,
              "gene_events": {pid: state["gene_events"][pid] for pid in memory}}
    shared = digest({"task": trial, "genome": parent["id"], "parent_event": state["last_event"]})
    workspace = {"context": shared,
                 "CODE": {"engine_candidate": candidate["id"], "author": "kernel_bounded_policy_mutation"},
                 "LOGIC": {"evidence": digest(report), "verdict": reason},
                 "THINKING": {"goal": selection["task"], "causes": causes, "policy": selection["policy"]},
                 "INTELLIGENCE": {"operator_counts": counts, "selection_data": "active_gene_IR_only"}}
    admitted = reason == "VERIFIED_ENGINE_IMPROVEMENT"
    return {"kind": "step", "domain": "ENGINE", "status": "ADMITTED" if admitted else "WITHHOLD",
            "reason": reason, "selection": selection, "program": None, "engine_candidate": candidate,
            "workspace": workspace, "mutation": mutation, "event": state["last_event"] + 1,
            "synthesis": {"attempts": training["candidate_attempts"], "selection": "experience_only"},
            "gate": report, "parent_generation": state["current"],
            "generation": state["admissions"] + 1 if admitted else state["current"], "dataset": trial_dataset(trial)}

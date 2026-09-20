"""Frozen candidate evaluation: held-out improvement, regression and ablation."""

from .contracts import equal
from .language import candidate, execute
from .synthesis import ERRORS


def score(program, rows, memory):
    outcomes = []
    for row in rows:
        try:
            output = execute(program, row["input"], memory)
            outcomes.append({"ok": equal(output, row["output"]), "output": output})
        except ERRORS as exc:
            outcomes.append({"ok": False, "error": type(exc).__name__})
    return {"passed": sum(x["ok"] for x in outcomes), "total": len(rows), "outcomes": outcomes}


def baseline(task):
    return candidate(["input", sorted(task["train"][0]["input"])[0]], {})


def gate(program, task, memory, active, tasks):
    extended = {**memory, program["id"]: program}
    training = score(program, task["train"], extended)
    heldout = score(program, task["holdout"], extended)
    before = score(baseline(task), task["holdout"], {})
    regressions = {tid: score(memory[pid], tasks[tid]["train"] + tasks[tid]["holdout"], extended)
                   for tid, pid in sorted(active.items())}
    ablation = []
    for pid in program["parents"]:
        reduced = {k: v for k, v in memory.items() if k != pid}
        observed = score(program, task["holdout"], reduced)
        ablation.append({"parent": pid, "passed_without_parent": observed["passed"],
                         "failed_without_parent": observed["passed"] < heldout["passed"]})
    reason = "VERIFIED_IMPROVEMENT"
    if training["passed"] != training["total"]:
        reason = "TRAINING_FAILED"
    elif heldout["passed"] != heldout["total"]:
        reason = "HOLDOUT_FAILED"
    elif heldout["passed"] <= before["passed"]:
        reason = "NO_HOLDOUT_IMPROVEMENT"
    elif any(r["passed"] != r["total"] for r in regressions.values()):
        reason = "REGRESSION_FAILED"
    return {"train": training, "holdout": heldout, "baseline_holdout": before,
            "regression": regressions, "ablation": ablation, "reason": reason}

"""The single NOVA control loop and deterministic event reducer."""

import hashlib
import sys
from pathlib import Path

from .contracts import ContractError, IntegrityError, dataset_id, digest, encode, task_spec
from .evaluation import baseline, gate, score
from .genetics import genome, vary
from .language import execute
from .memory import Journal
from .synthesis import ERRORS, MAX_ATTEMPTS, MAX_DEPTH, synthesize

SCHEMA = "nova.kernel.v1"


def runtime_manifest():
    return {"schema": SCHEMA, "python": list(sys.version_info[:2]), "sources": {p.name: hashlib.sha256(p.read_bytes()).hexdigest()
            for p in sorted(Path(__file__).parent.glob("*.py"))},
            "search": {"attempts": MAX_ATTEMPTS, "depth": MAX_DEPTH},
            "runtime": "single_state_single_queue_single_journal",
            "faculties": {"CODE": "native_expression_synthesis_and_ast_execution",
                          "LOGIC": "contracts_deficits_and_admission_evidence",
                          "THINKING": "causal_goal_selection_and_continuation",
                          "INTELLIGENCE": "experience_conditioned_verified_gene_selection"},
            "program_author": "kernel_training_only", "engine_author": "maintainer"}


def initial_state():
    return {"tasks": {}, "generations": {0: {}}, "parents": {0: None},
            "genomes": {0: genome({})}, "task_events": {}, "gene_events": {},
            "experience": {}, "last_event": 1,
            "programs": {}, "current": 0, "attempted": set(),
            "consumed": set(), "admissions": 0, "attempts": 0}


def context(state):
    active = state["generations"][state["current"]]
    memory = {pid: state["programs"][pid] for pid in dict.fromkeys(active.values())}
    return active, memory, digest(sorted(memory))


def intelligence(state, tid, memory):
    """Select executable inherited genes using this task's training inputs only."""
    task = state["tasks"][tid]
    usable = {}
    for pid, program in memory.items():
        try:
            for row in task["train"]:
                execute(program, row["input"], memory)
            usable[pid] = program
        except ERRORS:
            continue
    history = state["experience"].get(tid, [])
    return {"strategy": "verified_gene_composition" if usable else "native_primitive_search",
            "usable_genes": list(usable), "memory_context": digest(sorted(usable)),
            "previous_attempt": history[-1]["event"] if history else None,
            "previous_failures": sum(h["status"] == "WITHHOLD" for h in history)}


def task_queue(state):
    active, memory, _ = context(state)
    rows = []
    for tid, task in state["tasks"].items():
        plan = intelligence(state, tid, memory)
        if tid in active:
            status = "ADMITTED"
        elif dataset_id(task) in state["consumed"]:
            status = "EVALUATION_CONSUMED"
        elif (tid, plan["memory_context"]) in state["attempted"]:
            status = "WAITING_FOR_NEW_MEMORY"
        elif plan["previous_attempt"] is not None:
            status = "RETRY_READY"
        else:
            status = "PENDING"
        rows.append({"task": tid, "status": status, "submitted_event": state["task_events"][tid],
                     "plan": plan})
    return rows


def choose(state):
    options = []
    for item in task_queue(state):
        if item["status"] not in ("PENDING", "RETRY_READY"):
            continue
        tid = item["task"]
        task = state["tasks"][tid]
        result = score(baseline(task), task["train"], {})
        failure = 1 - result["passed"] / result["total"]
        options.append((-failure, tid, result, item["plan"]))
    if not options:
        return None
    _, tid, observed, plan = min(options, key=lambda x: (x[0], x[1]))
    return {"task": tid, "memory_context": plan["memory_context"], "plan": plan, "baseline_train": observed,
            "policy": "largest_training_deficit_then_task_id"}


def propose(state):
    selection = choose(state)
    if selection is None:
        return {"status": "IDLE", "reason": "NO_ELIGIBLE_DEFICIT"}
    active, memory, _ = context(state)
    task = state["tasks"][selection["task"]]
    plan = selection["plan"]
    search_memory = {pid: memory[pid] for pid in plan["usable_genes"]}
    result = synthesize(task["train"], search_memory)
    program = result["program"]
    mutation = vary(state["genomes"][state["current"]], task["id"], program, memory) if program else None
    report = gate(program, task, memory, active, state["tasks"]) if program else None
    if report:
        report["genetics"] = {"passed": True, "parent_genome": mutation["parent_genome"],
                              "candidate_genome": mutation["child_genome"]["id"]}
    reason = report["reason"] if report else "SEARCH_EXHAUSTED"
    admitted = reason == "VERIFIED_IMPROVEMENT"
    causes = {"task_event": state["task_events"][task["id"]],
              "previous_attempt": plan["previous_attempt"],
              "gene_events": {pid: state["gene_events"][pid] for pid in plan["usable_genes"]}}
    shared_context = digest({"task": task, "genome": state["genomes"][state["current"]]["id"],
                             "memory": selection["memory_context"], "parent_event": state["last_event"]})
    workspace = {"context": shared_context,
                 "THINKING": {"goal": task["id"], "causes": causes, "policy": selection["policy"]},
                 "INTELLIGENCE": plan,
                 "CODE": {"program": program["id"] if program else None,
                          "attempts": result["attempts"], "selection": result["selection"]},
                 "LOGIC": {"baseline_train": digest(selection["baseline_train"]),
                           "evidence": digest(report), "verdict": reason}}
    return {"kind": "step", "status": "ADMITTED" if admitted else "WITHHOLD",
            "reason": reason, "selection": selection, "program": program,
            "workspace": workspace, "mutation": mutation, "event": state["last_event"] + 1,
            "synthesis": {k: v for k, v in result.items() if k != "program"}, "gate": report,
            "parent_generation": state["current"],
            "generation": state["admissions"] + 1 if admitted else state["current"],
            "dataset": dataset_id(task)}


def apply_step(state, body):
    tid = body["selection"]["task"]
    state["attempted"].add((tid, body["selection"]["memory_context"]))
    state["attempts"] += 1
    state["experience"].setdefault(tid, []).append({
        "event": body["event"], "context": body["workspace"]["context"],
        "causes": body["workspace"]["THINKING"]["causes"],
        "memory_context": body["selection"]["memory_context"],
        "status": body["status"], "reason": body["reason"],
        "program": body["program"]["id"] if body["program"] else None,
        "search_attempts": body["synthesis"]["attempts"]})
    if body["program"] is not None:
        state["consumed"].add(body["dataset"])
    if body["status"] == "ADMITTED":
        program = body["program"]
        state["programs"][program["id"]] = program
        state["gene_events"].setdefault(program["id"], body["event"])
        state["genomes"][body["generation"]] = body["mutation"]["child_genome"]
        state["generations"][body["generation"]] = {
            **state["generations"][state["current"]], tid: program["id"]}
        state["parents"][body["generation"]] = state["current"]
        state["current"] = body["generation"]
        state["admissions"] += 1


def validate_rollback(state, target):
    if type(target) is not int:
        raise ContractError("generation must be an integer")
    parent = state["parents"][state["current"]]
    while parent is not None:
        if parent == target:
            return
        parent = state["parents"][parent]
    raise ContractError("rollback target must be a strict active ancestor")


class Kernel:
    def __init__(self, path, create=False):
        self.journal = Journal(path, create=create)
        self.manifest = runtime_manifest()
        try:
            events, head = self.journal.read()
            if not events:
                if not create:
                    raise IntegrityError("missing genesis")
                self.journal.append({"kind": "genesis", "manifest": self.manifest}, head)
            self._load()
        except Exception:
            self.close()
            raise

    def _load(self):
        events, head = self.journal.read()
        if not events or encode(events[0]) != encode({"kind": "genesis", "manifest": self.manifest}):
            raise IntegrityError("genesis/runtime mismatch; use the original engine for this state")
        state = initial_state()
        try:
            for seq, body in enumerate(events[1:], 2):
                if body.get("kind") == "tasks" and set(body) == {"kind", "tasks"}:
                    if type(body["tasks"]) is not list or not body["tasks"]:
                        raise ContractError("empty task event")
                    for raw in body["tasks"]:
                        task = task_spec(raw)
                        if encode(task) != encode(raw) or task["id"] in state["tasks"]:
                            raise ContractError("duplicate or noncanonical task event")
                        state["tasks"][task["id"]] = task
                        state["task_events"][task["id"]] = seq
                elif body.get("kind") == "step":
                    # Recompute the actual selector, synthesis, outputs and verdict.
                    if encode(propose(state)) != encode(body):
                        raise IntegrityError("step replay/evidence mismatch")
                    apply_step(state, body)
                elif body.get("kind") == "rollback" and set(body) == {"kind", "target", "from"}:
                    if type(body["from"]) is not int or body["from"] != state["current"]:
                        raise ContractError("rollback parent mismatch")
                    validate_rollback(state, body["target"])
                    state["current"] = body["target"]
                else:
                    raise ContractError("unknown event schema")
                state["last_event"] = seq
        except (ValueError, KeyError, TypeError, RecursionError) as exc:
            raise IntegrityError("semantic replay failed: " + str(exc)) from exc
        return state, head, len(events)

    def register(self, specs):
        if type(specs) is not list or not 1 <= len(specs) <= 64:
            raise ContractError("register 1..64 tasks per batch")
        tasks = [task_spec(s) for s in specs]
        state, head, _ = self._load()
        known = dict(state["tasks"])
        new = []
        for task in tasks:
            if task["id"] in known:
                if known[task["id"]] != task:
                    raise ContractError("task id is immutable: " + task["id"])
            else:
                known[task["id"]] = task
                new.append(task)
        if new:
            self.journal.append({"kind": "tasks", "tasks": new}, head)
        return {"registered": [task["id"] for task in new]}

    def step(self):
        state, head, _ = self._load()
        body = propose(state)
        if body["status"] != "IDLE":
            self.journal.append(body, head)
        return body

    def develop(self, steps=3):
        if type(steps) is not int or not 1 <= steps <= 100:
            raise ContractError("development steps must be an integer in 1..100")
        results = []
        for _ in range(steps):
            body = self.step()
            results.append(body)
            if body["status"] == "IDLE":
                break
        return {"steps": results, "state": self.status()}

    def queue(self):
        state, _, _ = self._load()
        return task_queue(state)

    def causal_memory(self):
        state, _, _ = self._load()
        return {"schema": "nova.causal-memory.v1", "experiences": state["experience"],
                "task_events": state["task_events"], "gene_events": state["gene_events"]}

    def genome(self):
        state, _, _ = self._load()
        return state["genomes"][state["current"]]

    def predict(self, task_id, inputs):
        state, _, _ = self._load()
        active, memory, _ = context(state)
        if task_id not in active:
            raise ContractError("task has no active verified program: " + task_id)
        task = state["tasks"][task_id]
        if type(inputs) is not dict or set(inputs) != set(task["train"][0]["input"]):
            raise ContractError("query input fields do not match the task")
        return execute(memory[active[task_id]], inputs, memory)

    def rollback(self, generation):
        state, head, _ = self._load()
        validate_rollback(state, generation)
        self.journal.append({"kind": "rollback", "from": state["current"], "target": generation}, head)
        return self.status()

    def status(self):
        state, head, count = self._load()
        active, memory, _ = context(state)
        next_choice = choose(state)
        return {"schema": SCHEMA, "head": head, "events": count,
                "runtime_digest": digest(self.manifest), "active_generation": state["current"],
                "admissions_total": state["admissions"], "attempts_total": state["attempts"],
                "tasks_total": len(state["tasks"]), "active_tasks": dict(active),
                "programs_active": len(memory), "next_task": next_choice["task"] if next_choice else None,
                "genome": state["genomes"][state["current"]]["id"],
                "queue": {row["task"]: row["status"] for row in task_queue(state)},
                "self_model": {"successful_admissions": state["admissions"],
                               "withheld_attempts": state["attempts"] - state["admissions"],
                               "search_attempts_total": sum(h["search_attempts"] for history in state["experience"].values() for h in history)},
                "claim": "bounded_program_learning"}

    def audit(self, expected_head=None):
        result = self.status()
        if expected_head is not None and expected_head != result["head"]:
            raise IntegrityError("external journal head mismatch")
        return {"status": "PASS", "verification": "full_deterministic_semantic_replay", **result}

    def backup(self, destination):
        self.audit()
        self.journal.backup(destination)
        with Kernel(destination) as restored:
            return restored.audit()

    def close(self):
        self.journal.close()

    def __enter__(self):
        return self

    def __exit__(self, *_):
        self.close()

"""The single NOVA control loop and deterministic event reducer."""

import hashlib
import sys
from copy import deepcopy
from pathlib import Path

from .adaptation import engine_proposal, input_tokens, trial_dataset, trial_spec
from . import capability, autonomy, observations, ucr_development
from .compatibility import recognized_legacy
from .contracts import ContractError, IntegrityError, dataset_id, digest, encode, task_spec
from .evaluation import baseline, gate, score
from .genetics import genome, vary
from .language import execute
from .extensions import is_extension
from .memory import Journal, ZERO
from .synthesis import ERRORS, MAX_ATTEMPTS, MAX_DEPTH, synthesize

SCHEMA = "nova.kernel.v8"


def runtime_manifest():
    return {"schema": SCHEMA, "python": list(sys.version_info[:2]), "sources": {p.name: hashlib.sha256(p.read_bytes()).hexdigest()
            for p in sorted(Path(__file__).parent.glob("*.py"))},
            "search": {"attempts": MAX_ATTEMPTS, "depth": MAX_DEPTH},
            "runtime": "single_state_single_queue_single_journal",
            "faculties": {"CODE": "native_expression_synthesis_and_ast_execution",
                          "LOGIC": "contracts_deficits_and_admission_evidence",
                          "THINKING": "causal_goal_selection_and_continuation",
                          "INTELLIGENCE": "experience_conditioned_verified_gene_selection"},
            "program_author": "kernel_training_only", "engine_author": "maintainer",
            "engine_policy_author": "kernel_bounded_experience_conditioned_mutation",
            "capability_author": "kernel_specification_conditioned_document_compiler",
            "capability_dialect": "bounded_word_equations_and_typeset_block_recurrences",
            "autonomy": "bounded_failure_conditioned_relational_subgoals_with_external_io",
            "python_tools": "pure_stdlib_composition_and_inherited_relation_transfer",
            "observations": {"mechanism": "measured_scalar_field_prediction_errors_v1", "author": "maintainer",
                             "config": observations.CONFIG},
            "ucr_development": ucr_development.manifest()}


def initial_state():
    return {"tasks": {}, "generations": {0: {}}, "parents": {0: None},
            "genomes": {0: genome({})}, "task_events": {}, "gene_events": {},
            "experience": {}, "last_event": 1,
            "programs": {}, "current": 0, "attempted": set(),
            "consumed": set(), "admissions": 0, "attempts": 0, "engine_trials": {},
            "knowledge": {}, "capability_attempted": set(), "capability_pending": {},
            "capability_experience": {}, "capability_evaluated_inputs": set(),
            "autonomy": autonomy.initial(), "observations": [], "observation_hashes": set(), "observation_inputs": set()}


def context(state):
    active = state["generations"][state["current"]]
    ids = list(dict.fromkeys(active.values())) + state["genomes"][state["current"]].get("capabilities", [])
    memory = {pid: state["programs"][pid] for pid in ids}
    return active, memory, digest(sorted(memory))


def intelligence(state, tid, memory):
    """Select executable inherited genes using this task's training inputs only."""
    task = state["tasks"][tid]
    usable = {}
    for pid, program in memory.items():
        if is_extension(program):
            usable[pid] = program
            continue
        try:
            for row in task["train"]:
                execute(program, row["input"], memory)
            usable[pid] = program
        except ERRORS:
            continue
    history = state["experience"].get(tid, [])
    plan = {"strategy": "verified_gene_composition" if usable else "native_primitive_search",
            "usable_genes": list(usable), "memory_context": digest(sorted(usable)),
            "previous_attempt": history[-1]["event"] if history else None,
            "previous_failures": sum(h["status"] == "WITHHOLD" for h in history)}
    policy = state["genomes"][state["current"]].get("engine")
    if policy:
        plan.update(engine=policy["id"], memory_context=digest([plan["memory_context"], policy["id"]]),
                    previous_cost=history[-1]["search_attempts"] if history else 0)
    return plan


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
    policy = state["genomes"][state["current"]].get("engine")
    for tid, trial in state["engine_trials"].items():
        history = state["experience"].get(tid, [])
        status = "EVALUATION_CONSUMED" if trial_dataset(trial) in state["consumed"] else "PENDING"
        if policy and any(h.get("engine") == policy["id"] and h["status"] == "ADMITTED" for h in history):
            status = "ADMITTED"
        rows.append({"task": tid, "kind": "ENGINE", "status": status,
                     "submitted_event": state["task_events"][tid],
                     "plan": {"memory_context": digest([sorted(memory), policy]), "previous_attempt": None}})
    return rows + capability.queue(state, rows)


def choose(state):
    options = []
    extensions = []
    for item in task_queue(state):
        if item["status"] not in ("PENDING", "RETRY_READY"):
            continue
        tid = item["task"]
        if item.get("kind") == "CAPABILITY":
            extensions.append(item)
            continue
        if item.get("kind") == "ENGINE":
            return {"task": tid, "kind": "ENGINE", "memory_context": item["plan"]["memory_context"],
                    "plan": item["plan"], "policy": "registered_engine_trial_before_programs"}
        task = state["tasks"][tid]
        result = score(baseline(task), task["train"], {})
        failure = 1 - result["passed"] / result["total"]
        options.append((-failure, tid, result, item["plan"]))
    if not options:
        if not extensions:
            return None
        item = min(extensions, key=lambda row: (row["submitted_event"], row["target"]))
        return {"task": item["task"], "target": item["target"], "kind": "CAPABILITY",
                "plan": item["plan"], "policy": "oldest_remembered_exhausted_deficit_then_task_id"}
    _, tid, observed, plan = min(options, key=lambda x: (x[0], x[3].get("previous_cost", 0), x[1]))
    return {"task": tid, "memory_context": plan["memory_context"], "plan": plan, "baseline_train": observed,
            "policy": "largest_training_deficit_then_previous_cost_then_task_id" if "engine" in plan else "largest_training_deficit_then_task_id"}


def propose(state):
    if autonomy.enabled(state) and state["autonomy"]["enabled"]:
        _, memory, _ = context(state)
        return autonomy.propose(state, memory)
    selection = choose(state)
    if selection is None:
        waiting = [r for r in task_queue(state) if r["status"] == "WAITING_FOR_FRESH_HOLDOUT"]
        if waiting:
            return {"status": "WAITING", "reason": "FRESH_HOLDOUT_REQUIRED", "task": waiting[0]["target"]}
        return {"status": "IDLE", "reason": "NO_ELIGIBLE_DEFICIT"}
    active, memory, _ = context(state)
    if selection.get("kind") == "CAPABILITY":
        return capability.freeze(state, selection, memory)
    if selection.get("kind") == "ENGINE":
        return engine_proposal(state, selection, memory)
    task = state["tasks"][selection["task"]]
    plan = selection["plan"]
    search_memory = {pid: memory[pid] for pid in plan["usable_genes"]}
    result = synthesize(task["train"], search_memory, state["genomes"][state["current"]].get("engine"))
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
    if body.get("domain") == "ENGINE":
        state["experience"][tid][-1]["engine"] = body["engine_candidate"]["id"]
    if body["program"] is not None or body.get("domain") == "ENGINE":
        state["consumed"].add(body["dataset"])
    if body["status"] == "ADMITTED":
        program = body["program"]
        if program is not None:
            state["programs"][program["id"]] = program
            state["gene_events"].setdefault(program["id"], body["event"])
        state["genomes"][body["generation"]] = body["mutation"]["child_genome"]
        state["generations"][body["generation"]] = {
            **state["generations"][state["current"]], **({tid: program["id"]} if program else {})}
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


def validate_trial(state, trial):
    if "@engine:" + trial["id"] in state["engine_trials"] or len(state["engine_trials"]) >= 16:
        raise ContractError("duplicate engine trial or trial limit reached")
    existing = list(state["tasks"].values()) + [t for prior in state["engine_trials"].values() for t in prior["tasks"]]
    if input_tokens(trial["tasks"]) & input_tokens(existing):
        raise ContractError("engine validation inputs already used or reserved")


def upgrade_proposal(state, target, previous_head):
    source = state["runtime_manifest"]
    if (not recognized_legacy(source) or target["schema"] not in ("nova.kernel.v2", "nova.kernel.v3", "nova.kernel.v4", "nova.kernel.v5", "nova.kernel.v6", "nova.kernel.v7", "nova.kernel.v8") or
            source["schema"] >= target["schema"] or
            target["schema"] != SCHEMA and not recognized_legacy(target)):
        raise ContractError("unsupported runtime transition")
    active, memory, _ = context(state)
    regression = {tid: score(memory[pid], state["tasks"][tid]["train"] + state["tasks"][tid]["holdout"], memory)
                  for tid, pid in sorted(active.items())}
    if any(r["passed"] != r["total"] for r in regression.values()):
        raise IntegrityError("runtime transition regresses inherited programs")
    return {"kind": "runtime_upgrade", "from": digest(state["runtime_manifest"]), "to": target,
            "previous_head": previous_head, "generation": state["current"],
            "genome": state["genomes"][state["current"]]["id"], "regression": regression,
            "author": "maintainer", "verification": "full_legacy_replay_and_inherited_program_regression"}


class Kernel:
    def __init__(self, path, create=False):
        self.journal = Journal(path, create=create)
        self.manifest = runtime_manifest()
        self._cache = None
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

    def _load(self, force=False):
        events, head = self.journal.read()
        origin = events[0].get("manifest") if events else None
        if (not events or set(events[0]) != {"kind", "manifest"} or events[0]["kind"] != "genesis" or
                encode(origin) != encode(self.manifest) and not recognized_legacy(origin)):
            raise IntegrityError("genesis/runtime mismatch; use the original engine for this state")
        state = initial_state()
        state["runtime_manifest"] = origin
        start = 1
        prefix = digest([1, ZERO, events[0]])
        # Hashes/canonical JSON are checked on every read. Only an identical,
        # already semantically verified prefix can reuse this in-process cache.
        if not force and self._cache and len(events) >= self._cache[0]:
            count, cached_head, cached_state = self._cache
            prefix_check = ZERO
            for seq, body in enumerate(events[:count], 1):
                prefix_check = digest([seq, prefix_check, body])
            if prefix_check == cached_head:
                state, start, prefix = deepcopy(cached_state), count, cached_head
        try:
            for seq, body in enumerate(events[start:], start + 1):
                if body.get("kind") == "tasks" and set(body) == {"kind", "tasks"}:
                    if type(body["tasks"]) is not list or not body["tasks"]:
                        raise ContractError("empty task event")
                    for raw in body["tasks"]:
                        task = task_spec(raw)
                        if encode(task) != encode(raw) or task["id"] in state["tasks"]:
                            raise ContractError("duplicate or noncanonical task event")
                        reserved = [t for trial in state["engine_trials"].values() for t in trial["tasks"]]
                        if input_tokens([task]) & input_tokens(reserved):
                            raise ContractError("program task overlaps reserved engine validation")
                        state["tasks"][task["id"]] = task
                        state["task_events"][task["id"]] = seq
                elif body.get("kind") == "step":
                    # Recompute the actual selector, synthesis, outputs and verdict.
                    if encode(propose(state)) != encode(body):
                        raise IntegrityError("step replay/evidence mismatch")
                    apply_step(state, body)
                elif body.get("kind") == "engine_trial" and set(body) == {"kind", "trial"}:
                    if state["runtime_manifest"]["schema"] not in ("nova.kernel.v2", "nova.kernel.v3", "nova.kernel.v4", "nova.kernel.v5", "nova.kernel.v6", "nova.kernel.v7", "nova.kernel.v8"):
                        raise ContractError("engine policy requires runtime upgrade")
                    trial = trial_spec(body["trial"])
                    if encode(trial) != encode(body["trial"]):
                        raise ContractError("noncanonical engine trial")
                    validate_trial(state, trial)
                    tid = "@engine:" + trial["id"]
                    state["engine_trials"][tid] = trial
                    state["task_events"][tid] = seq
                elif body.get("kind") == "runtime_upgrade":
                    target = body["to"]
                    if not recognized_legacy(target) and encode(target) != encode(self.manifest):
                        raise IntegrityError("unknown runtime transition target")
                    if encode(body) != encode(upgrade_proposal(state, target, prefix)):
                        raise IntegrityError("runtime upgrade evidence mismatch")
                    state["runtime_manifest"] = target
                elif body.get("kind") == "knowledge" and set(body) == {"kind", "specification"}:
                    self._require_capability_runtime(state)
                    spec = capability.validate_knowledge(state, body["specification"])
                    state["knowledge"][spec["id"]] = spec
                elif body.get("kind") == "observation":
                    expected, extracted = observations.ingest(state, body["document"])
                    if encode(body) != encode(expected):
                        raise IntegrityError("observation parse/provenance replay mismatch")
                    observations.apply(state, body, extracted)
                elif body.get("kind") == "capability_freeze":
                    self._require_capability_runtime(state)
                    if encode(propose(state)) != encode(body):
                        raise IntegrityError("native capability freeze replay mismatch")
                    capability.apply_freeze(state, body)
                elif body.get("kind") == "capability_evaluation":
                    self._require_capability_runtime(state)
                    frozen = state["capability_pending"][body["target"]]
                    _, memory, _ = context(state)
                    if encode(capability.evaluate_frozen(state, frozen, body["rows"], memory)) != encode(body):
                        raise IntegrityError("capability evaluation replay mismatch")
                    capability.apply_evaluation(state, body)
                elif body.get("kind") == "autonomy_start":
                    if (not autonomy.enabled(state) or state["autonomy"]["enabled"] or
                            body != {"kind": "autonomy_start", "config": autonomy.CONFIG}):
                        raise ContractError("invalid autonomy start or runtime")
                    autonomy.apply(state, body)
                elif body.get("kind") == "autonomy_step":
                    if not autonomy.enabled(state) or encode(propose(state)) != encode(body):
                        raise IntegrityError("autonomous decision replay mismatch")
                    autonomy.apply(state, body)
                elif body.get("kind") == "autonomy_response":
                    if not autonomy.enabled(state) or encode(autonomy.validate_response(state, body["response"])) != encode(body):
                        raise IntegrityError("autonomous source response mismatch")
                    autonomy.apply(state, body)
                elif body.get("kind") == "autonomy_evaluation":
                    _, memory, _ = context(state)
                    if not autonomy.enabled(state) or encode(autonomy.assess(state, body["freeze"], body["rows"], memory)) != encode(body):
                        raise IntegrityError("autonomous evaluation replay mismatch")
                    autonomy.apply(state, body)
                elif body.get("kind") == "rollback" and set(body) == {"kind", "target", "from"}:
                    if type(body["from"]) is not int or body["from"] != state["current"]:
                        raise ContractError("rollback parent mismatch")
                    validate_rollback(state, body["target"])
                    state["current"] = body["target"]
                else:
                    raise ContractError("unknown event schema")
                state["last_event"] = seq
                prefix = digest([seq, prefix, body])
        except (ValueError, KeyError, TypeError, RecursionError) as exc:
            raise IntegrityError("semantic replay failed: " + str(exc)) from exc
        self._cache = (len(events), head, deepcopy(state))
        return state, head, len(events)

    def _require_current(self, state):
        if encode(state["runtime_manifest"]) != encode(self.manifest):
            raise ContractError("legacy state is read-only; run upgrade before new mutations")

    def _require_capability_runtime(self, state):
        if not capability.enabled(state):
            raise ContractError("capability event before runtime support")

    def upgrade(self):
        state, head, _ = self._load(force=True)
        if encode(state["runtime_manifest"]) == encode(self.manifest):
            return {"status": "CURRENT", "head": head}
        body = upgrade_proposal(state, self.manifest, head)
        self.journal.append(body, head)
        return {"status": "UPGRADED", "transition": body, "state": self.status()}

    def register_engine_trial(self, raw):
        trial = trial_spec(raw)
        state, head, _ = self._load()
        self._require_current(state)
        tid = "@engine:" + trial["id"]
        if tid in state["engine_trials"] and encode(state["engine_trials"][tid]) == encode(trial):
            return {"registered": []}
        validate_trial(state, trial)
        self.journal.append({"kind": "engine_trial", "trial": trial}, head)
        return {"registered": [tid]}

    def start_autonomy(self):
        state, head, _ = self._load()
        self._require_current(state)
        if not autonomy.enabled(state):
            raise ContractError("autonomy requires runtime v5")
        if state["autonomy"]["enabled"]:
            return {"status": "CURRENT"}
        body = {"kind": "autonomy_start", "config": autonomy.CONFIG}
        self.journal.append(body, head)
        return {"status": "STARTED", "config": autonomy.CONFIG}

    def autonomy_response(self, response):
        state, head, _ = self._load()
        self._require_current(state)
        body = autonomy.validate_response(state, response)
        self.journal.append(body, head)
        return {"status": "RECORDED", "event": body["event"]}

    def autonomy_assess(self, freeze_id, rows):
        state, head, _ = self._load()
        self._require_current(state)
        _, memory, _ = context(state)
        body = autonomy.assess(state, freeze_id, rows, memory)
        self.journal.append(body, head)
        return body

    def study(self, raw):
        state, head, _ = self._load()
        self._require_current(state)
        spec = capability.validate_knowledge(state, raw)
        self.journal.append({"kind": "knowledge", "specification": spec}, head)
        return {"registered": spec["id"], "digest": digest(spec)}

    def observe(self, raw):
        state, head, _ = self._load()
        self._require_current(state)
        if not observations.enabled(state):
            raise ContractError("structured observations require runtime v7")
        extracted = observations.extract(raw)
        if raw["sha256"] in state["observation_hashes"]:
            return {"status": "DUPLICATE", "sha256": raw["sha256"]}
        body = {"kind": "observation", "document": deepcopy(raw), "receipt": extracted["receipt"]}
        self.journal.append(body, head)
        return {"status": "RECORDED", **extracted["receipt"]}

    def assess(self, freeze_id, rows):
        state, head, _ = self._load()
        self._require_current(state)
        frozen = next((f for f in state["capability_pending"].values() if f["freeze"] == freeze_id), None)
        if frozen is None:
            raise ContractError("unknown or already consumed frozen candidate")
        _, memory, _ = context(state)
        body = capability.evaluate_frozen(state, frozen, rows, memory)
        self.journal.append(body, head)
        return body

    def register(self, specs):
        if type(specs) is not list or not 1 <= len(specs) <= 64:
            raise ContractError("register 1..64 tasks per batch")
        tasks = [task_spec(s) for s in specs]
        state, head, _ = self._load()
        self._require_current(state)
        known = dict(state["tasks"])
        new = []
        for task in tasks:
            if task["id"] in known:
                if known[task["id"]] != task:
                    raise ContractError("task id is immutable: " + task["id"])
            else:
                reserved = [t for trial in state["engine_trials"].values() for t in trial["tasks"]]
                if input_tokens([task]) & input_tokens(reserved):
                    raise ContractError("program task overlaps reserved engine validation")
                known[task["id"]] = task
                new.append(task)
        if new:
            self.journal.append({"kind": "tasks", "tasks": new}, head)
        return {"registered": [task["id"] for task in new]}

    def step(self):
        state, head, _ = self._load()
        self._require_current(state)
        body = propose(state)
        if body["status"] not in ("IDLE", "WAITING"):
            self.journal.append(body, head)
        return body

    def develop(self, steps=3):
        if type(steps) is not int or not 1 <= steps <= 100:
            raise ContractError("development steps must be an integer in 1..100")
        results = []
        for _ in range(steps):
            body = self.step()
            results.append(body)
            if body["status"] in ("IDLE", "WAITING"):
                break
        return {"steps": results, "state": self.status()}

    def queue(self):
        state, _, _ = self._load()
        return task_queue(state)

    def causal_memory(self):
        state, _, _ = self._load()
        return {"schema": "nova.causal-memory.v1", "experiences": state["experience"],
                "task_events": state["task_events"], "gene_events": state["gene_events"],
                "capability_experiences": state["capability_experience"],
                "knowledge": {key: digest(spec) for key, spec in state["knowledge"].items()}}

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
        self._require_current(state)
        validate_rollback(state, generation)
        self.journal.append({"kind": "rollback", "from": state["current"], "target": generation}, head)
        return self.status()

    def status(self):
        state, head, count = self._load()
        active, memory, _ = context(state)
        next_choice = choose(state)
        return {"schema": SCHEMA, "head": head, "events": count,
                "runtime_digest": digest(self.manifest), "active_generation": state["current"],
                "active_runtime_digest": digest(state["runtime_manifest"]),
                "upgrade_required": encode(state["runtime_manifest"]) != encode(self.manifest),
                "engine_policy": state["genomes"][state["current"]].get("engine"),
                "admissions_total": state["admissions"], "attempts_total": state["attempts"],
                "tasks_total": len(state["tasks"]), "active_tasks": dict(active),
                "programs_active": len(memory), "next_task": next_choice["task"] if next_choice else None,
                "genome": state["genomes"][state["current"]]["id"],
                "queue": {row["task"]: row["status"] for row in task_queue(state)},
                "self_model": {"successful_admissions": state["admissions"],
                               "withheld_attempts": state["attempts"] - state["admissions"],
                               "search_attempts_total": sum(h["search_attempts"] for history in state["experience"].values() for h in history)},
                "capabilities_active": state["genomes"][state["current"]].get("capabilities", []),
                "claim": "bounded_program_policy_and_specification_conditioned_grammar_learning",
                **({"autonomy": autonomy.status(state)} if autonomy.enabled(state) else {}),
                **({"observations": {"documents_seen": len(state["observation_hashes"]),
                    "window_documents": len(state["observations"]),
                    "window_records": sum(len(d["records"]) for d in state["observations"])}}
                   if observations.enabled(state) else {})}

    def audit(self, expected_head=None):
        self._load(force=True)
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

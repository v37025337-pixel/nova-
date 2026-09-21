"""Native capability goals and gates, with all state reduced by Kernel.

This module has no database or loop. Freeze gets training/specifications only;
fresh evaluation is a later event and can neither alter nor reselect a body.
"""

from .contracts import ContractError, dataset_id, digest, encode, task_spec
from .evaluation import score
from .extensions import applications, execute as execute_word, learn, specification
from .genetics import genome
from .isolation import evaluate
from .language import candidate
from .synthesis import MAX_ATTEMPTS
from . import sequence, specifications


def enabled(state):
    return state["runtime_manifest"]["schema"] in ("nova.kernel.v3", "nova.kernel.v4", "nova.kernel.v5", "nova.kernel.v6", "nova.kernel.v7")


def queue(state, rows):
    if not enabled(state):
        return []
    result = []
    for row in rows:
        if row.get("kind") == "ENGINE" or row["status"] != "WAITING_FOR_NEW_MEMORY":
            continue
        tid = row["task"]
        history = state["experience"].get(tid, [])
        if not history or history[-1]["reason"] != "SEARCH_EXHAUSTED":
            continue
        token = digest([tid, state["genomes"][state["current"]]["id"], state["knowledge"]])
        if state["runtime_manifest"]["schema"] in ("nova.kernel.v4", "nova.kernel.v5", "nova.kernel.v6", "nova.kernel.v7"):
            token = digest([token, "typeset_block_recurrence_v1"])
        pending = state["capability_pending"].get(tid)
        status = "PENDING"
        if pending and pending["parent_generation"] == state["current"]:
            status = "WAITING_FOR_FRESH_HOLDOUT"
        elif token in state["capability_attempted"]:
            status = "WAITING_FOR_NEW_KNOWLEDGE"
        result.append({"task": "@capability:" + tid, "kind": "CAPABILITY", "target": tid,
                       "status": status, "submitted_event": history[-1]["event"],
                       "plan": {"memory_context": token, "previous_attempt": history[-1]["event"]}})
    return result


def diagnosis(training, history, knowledge):
    documents = [learn(knowledge[key]) for key in sorted(knowledge)]
    missing = set()

    def visit(node):
        if node[0] not in ("arg", "literal"):
            if node[0] in ("xor", "and", "or", "not", "shr", "shl", "rotl", "rotr"):
                missing.add(node[0])
            for sub in node[1:]:
                visit(sub)

    for doc in documents:
        for g in doc["genes"]:
            visit(g["ir"])
    exhausted_budget = history[-1]["search_attempts"] >= MAX_ATTEMPTS
    explanation = {"observed": "SEARCH_EXHAUSTED", "source_events": [h["event"] for h in history],
                   "search": "ATTEMPT_BUDGET_REACHED" if exhausted_budget else "BOUNDED_FRONTIER_EXHAUSTED",
                   "proof_of_global_impossibility": False,
                   "knowledge": "AVAILABLE" if knowledge else "MISSING_ALGORITHM_SPECIFICATION",
                   "unavailable_native_word_operations": sorted(missing),
                   "hypothesis": "REPRESENTATION_GAP" if missing else "BUDGET_OR_REPRESENTATION_OR_KNOWLEDGE_GAP",
                   "training_output_types": sorted({type(row["output"]).__name__ for row in training}),
                   "unsupported_specification_constructs": sorted({x for doc in documents for x in doc["unsupported"]})}
    return explanation, documents


def freeze(state, selection, memory):
    tid = selection["target"]
    training = state["tasks"][tid]["train"]
    parent = state["genomes"][state["current"]]
    diagnosed, documents = diagnosis(training, state["experience"][tid], state["knowledge"])
    algorithm = None
    if state["runtime_manifest"]["schema"] in ("nova.kernel.v4", "nova.kernel.v5", "nova.kernel.v6", "nova.kernel.v7"):
        algorithm = specifications.learn(state["knowledge"])
        diagnosed["algorithm_compiler"] = {k: v for k, v in algorithm.items() if k != "genes"}
        if algorithm["genes"]:
            diagnosed["resolved_by_sequence_compiler"] = diagnosed["unsupported_specification_constructs"]
            diagnosed["unsupported_specification_constructs"] = []
    # The compiler API and argument binder have no held-out data parameter.
    generated = [g for doc in documents for g in doc["genes"]]
    if algorithm:
        generated += algorithm["genes"]
    genes = generated[:64]
    program = chosen = None
    tested = 0
    for g in genes:
        extended = {**memory, g["id"]: g}
        for ir in applications(g, training, memory):
            tested += 1
            proposed = candidate(ir, extended)
            observed = score(proposed, training, extended)
            if observed["passed"] == observed["total"]:
                chosen, program = g, proposed
                break
        if program:
            break
    # Actually compile/run even partial generated formulas, with synthetic words.
    # This is a smoke check, explicitly not an independent algorithm holdout.
    jobs = []
    for g in genes:
        inputs = {p: "" if g["language"] == sequence.LANGUAGE else 0 for p in g["definition"]["parameters"]}
        jobs.append({"program": g, "rows": [{"input": inputs, "output": execute_word(g, inputs)}]})
    sandbox = evaluate(jobs, {}) if jobs else None
    reason = "CANDIDATE_FROZEN" if program else "NO_TRAINING_FIT"
    if not state["knowledge"]:
        reason = "KNOWLEDGE_MISSING"
    elif not program and diagnosed["unsupported_specification_constructs"]:
        reason = "SPECIFICATION_LANGUAGE_INCOMPLETE"
    child = None
    if program:
        child = genome({**parent["bindings"], tid: program["id"]}, parent["id"], parent.get("engine"),
                       parent.get("capabilities", []) + [chosen["id"]])
    goal = {"task": tid, "action": "EXTEND_GRAMMAR_TO_RESOLVE_REMEMBERED_DEFICIT",
            "origin": "kernel_causal_memory", "cause": selection["plan"]["previous_attempt"],
            "required_result": "new_primitive_and_training_fit_before_fresh_evaluation"}
    next_requirement = ("fresh_independent_holdout" if program else
                        "algorithm_specification" if not state["knowledge"] else
                        "specification_compiler_for:" + ",".join(diagnosed["unsupported_specification_constructs"])
                        if diagnosed["unsupported_specification_constructs"] else "new_specification_or_search_representation")
    report = {"diagnosis": diagnosed, "learning": documents, "sandbox_smoke": sandbox,
              "candidate_budget": 64, "candidates_deferred_by_budget": max(0, len(generated) - 64),
              "argument_bindings_tested": tested, "hidden_cases_seen": 0, "next_requirement": next_requirement}
    if algorithm:
        report["algorithm_learning"] = algorithm
    body = {"kind": "capability_freeze", "domain": "CAPABILITY", "selection": selection,
            "status": "FROZEN" if program else "WITHHOLD", "reason": reason,
            "event": state["last_event"] + 1, "parent_generation": state["current"],
            "parent_genome": parent["id"], "program": program, "primitive": chosen,
            "child_genome": child, "report": report,
            "workspace": {"context": digest([parent["id"], selection, state["knowledge"]]),
                          "THINKING": goal, "INTELLIGENCE": diagnosed,
                          "CODE": {"author": "kernel_equation_compiler", "generated": [g["id"] for g in genes],
                                   "selected": chosen["id"] if chosen else None},
                          "LOGIC": {"verdict": reason, "fresh_evaluation_required": True}}}
    if chosen and chosen["language"] == sequence.LANGUAGE:
        body["workspace"]["CODE"]["author"] = "kernel_document_compiler"
    return {**body, "freeze": digest(body)}


def apply_freeze(state, body):
    tid = body["selection"]["target"]
    state["capability_attempted"].add(body["selection"]["plan"]["memory_context"])
    state["capability_experience"].setdefault(tid, []).append(body)
    if body["status"] == "FROZEN":
        state["capability_pending"][tid] = body


def validate_fresh(state, frozen, rows):
    tid = frozen["selection"]["target"]
    if state["capability_pending"].get(tid) != frozen or frozen["parent_generation"] != state["current"]:
        raise ContractError("candidate is stale or already evaluated")
    canonical = task_spec({**state["tasks"][tid], "holdout": rows})["holdout"]
    if encode(canonical) != encode(rows):
        raise ContractError("fresh evaluation must use canonical JSON values")
    known = {digest(row["input"]) for task in state["tasks"].values()
             for split in ("train", "holdout") for row in task[split]}
    known |= {digest(row["input"]) for trial in state["engine_trials"].values()
              for task in trial["tasks"] for split in ("train", "holdout") for row in task[split]}
    known |= state["capability_evaluated_inputs"]
    if any(digest(row["input"]) in known for row in rows):
        raise ContractError("fresh holdout overlaps previous training, evaluation or reserved inputs")


def evaluate_frozen(state, frozen, rows, memory):
    validate_fresh(state, frozen, rows)
    tid = frozen["selection"]["target"]
    program, g = frozen["program"], frozen["primitive"]
    extended = {**memory, g["id"]: g, program["id"]: program}
    task = state["tasks"][tid]
    main = evaluate([{"program": program, "rows": task["train"]},
                     {"program": program, "rows": task["holdout"]},
                     {"program": program, "rows": rows}], extended)
    train, heldout, fresh = main["results"]
    regression = {}
    for old_tid, pid in sorted(state["generations"][state["current"]].items()):
        old = state["tasks"][old_tid]
        result = evaluate([{"program": memory[pid], "rows": old["train"] + old["holdout"]}], extended)
        regression[old_tid] = result["results"][0]
    ablated = evaluate([{"program": program, "rows": rows}], memory)["results"][0]
    # Compare every executable inherited program on the same fresh inputs.
    before = [score(p, rows, memory)["passed"] for p in memory.values()]
    best_before = max(before, default=0)
    reason = "VERIFIED_CAPABILITY_IMPROVEMENT"
    if any(r["passed"] != r["total"] for r in (train, heldout, fresh)):
        reason = "CAPABILITY_VALIDATION_FAILED"
    elif any(r["passed"] != r["total"] for r in regression.values()):
        reason = "REGRESSION_FAILED"
    elif ablated["passed"] >= fresh["passed"] or best_before >= fresh["passed"]:
        reason = "NO_CAUSAL_IMPROVEMENT"
    report = {"isolation": main["isolation"], "train": train, "original_holdout": heldout,
              "fresh_holdout": fresh, "regression": regression,
              "ablation": {"removed_primitive": g["id"], "without_primitive": ablated,
                           "best_inherited_passed": best_before,
                           "old_grammar_failure_event": frozen["selection"]["plan"]["previous_attempt"],
                           "claim": "improvement_over_recorded_bounded_search_and_active_genes"}}
    return {"kind": "capability_evaluation", "domain": "CAPABILITY", "freeze": frozen["freeze"],
            "event": state["last_event"] + 1, "target": tid, "rows": rows,
            "status": "ADMITTED" if reason == "VERIFIED_CAPABILITY_IMPROVEMENT" else "WITHHOLD",
            "reason": reason, "report": report, "parent_generation": state["current"],
            "generation": state["admissions"] + 1 if reason == "VERIFIED_CAPABILITY_IMPROVEMENT" else state["current"]}


def apply_evaluation(state, body):
    tid = body["target"]
    frozen = state["capability_pending"].pop(tid)
    state["capability_evaluated_inputs"].update(digest(r["input"]) for r in body["rows"])
    state["consumed"].add(dataset_id(state["tasks"][tid]))
    state["capability_experience"][tid].append(body)
    state["attempts"] += 1
    if body["status"] == "ADMITTED":
        generation = body["generation"]
        for p in (frozen["primitive"], frozen["program"]):
            state["programs"][p["id"]] = p
            state["gene_events"][p["id"]] = body["event"]
        state["parents"][generation] = state["current"]
        state["genomes"][generation] = frozen["child_genome"]
        state["generations"][generation] = dict(frozen["child_genome"]["bindings"])
        state["current"] = generation
        state["admissions"] += 1
        state["experience"].setdefault(tid, []).append({
            "event": body["event"], "program": frozen["program"]["id"], "status": "ADMITTED",
            "reason": body["reason"], "search_attempts": frozen["report"]["argument_bindings_tested"],
            "context": frozen["workspace"]["context"], "causes": frozen["workspace"]["THINKING"],
            "memory_context": frozen["selection"]["plan"]["memory_context"]})


def validate_knowledge(state, raw):
    spec = specification(raw)
    if spec["id"] in state["knowledge"] or len(state["knowledge"]) >= 8:
        raise ContractError("duplicate knowledge identity or knowledge budget")
    return spec

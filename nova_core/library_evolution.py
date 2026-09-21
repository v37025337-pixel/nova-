"""v6 library-assisted recovery and transfer of a verified ordering relation.

This is a bounded maintainer-written extension of goal discovery, not a general
intelligence claim. Historical v5 decisions retain their original semantics.
"""

from copy import deepcopy

from . import python_tools
from .contracts import ContractError, digest, encode, normalized
from .isolation import evaluate
from .language import candidate


def enabled(state):
    return state["runtime_manifest"]["schema"] in ("nova.kernel.v6", "nova.kernel.v7", "nova.kernel.v8")


def retryable(record, state):
    # A failed fresh evaluation is final. New tools can reopen only a search
    # which never produced a candidate or consumed external evaluation inputs.
    outcome = record["outcome"]
    return (enabled(state) and outcome.get("reason") == "KNOWLEDGE_NOT_EXECUTABLE_IN_CURRENT_GRAMMAR"
            and outcome.get("report", {}).get("fresh_cases_seen") == 0
            and record["goal"]["runtime_digest"] != digest(state["runtime_manifest"]))


def transfer_goal(state, memory):
    completed = state["autonomy"]["completed"]
    attempted = {r["goal"]["deficit_id"] for r in completed}
    for record in completed:
        prior, outcome = record["goal"], record["outcome"]
        if (outcome["status"] != "ADMITTED" or prior.get("transfer_from") or
                prior["contract"]["law"] != "lexicographic_integer_components"):
            continue
        pid = outcome["program"]["id"]
        if pid not in memory or not outcome.get("primitive"):
            continue
        root = state["tasks"][prior["root_task"]]
        deficit = digest([prior["deficit_id"], pid, "unresolved_permutation_transfer"])
        if deficit in attempted:
            continue
        fields = [k for k in sorted(root["train"][0]["input"]) if all(
            type(r["input"][k]) is list and type(r["output"]) is list and
            sorted(map(encode, r["input"][k])) == sorted(map(encode, r["output"]))
            for r in root["train"] + root["holdout"])]
        if not fields or len(root["train"]) > 32 or len(root["holdout"]) > 8:
            continue
        body = {"deficit_id": deficit, "origin": "native_transfer_to_unresolved_parent_failure",
                "root_task": prior["root_task"], "root_task_origin": prior["root_task_origin"],
                "cause_event": outcome["event"], "root_dataset": digest(root),
                "observed_failure": "PARENT_PERMUTATION_STILL_UNRESOLVED",
                "transfer_from": prior["id"], "required_capability": pid,
                "contract": {"law": "stable_permutation_by_inherited_relation",
                    "relation_law": prior["contract"]["law"], "input_fields": [fields[0]],
                    "output": "permutation", "fresh_min": 16, "success_threshold": 1,
                    "regression_threshold": 1, "ablation_required": True,
                    "properties": ["permutation", "stable", "declared_order_law", "inherited_relation_dependency"]},
                "search_terms": ["stable", "sort", "comparison", "relation"],
                "utility": "apply the admitted relation to the original unresolved permutation deficit",
                "parent_generation": state["current"], "parent_genome": state["genomes"][state["current"]]["id"],
                "runtime_digest": digest(state["runtime_manifest"]),
                "evidence_sources": [root["source"], "journal:event:" + str(outcome["event"])],
                "training": root["train"], "original_holdout": root["holdout"],
                "claim_boundary": "bounded transfer to an operator-originated parent task; library sorting algorithm"}
        body["id"] = "auto-" + digest(body)[:24]
        return body
    return None


def propose(state, memory):
    from .autonomy import event, request
    a, goal = state["autonomy"], state["autonomy"]["current"]
    if not goal or goal["contract"]["law"] in ("numeric_less", "observed_field_reconstruction"):
        return None
    if a["phase"] == "GOAL_FROZEN":
        return event(state, "ROUTE_SELECTED", status="PLANNED", reason="NATIVE_PYTHON_TOOL_COMPOSITION",
            goal=goal["id"], change_type="LIBRARY_ASSISTED_PROGRAM_GENE",
            alternatives={"PROGRAM_GENE": "existing expression tools lack sequence representation conversion",
                          "ENGINE_POLICY": "search reordering cannot expose unavailable Python functions",
                          "LIBRARY_COMPOSITION": "request pure function catalogue, then search combinations using training only"},
            proof_of_impossibility=False, algorithm_invention_claim=False)
    if a["phase"] == "ROUTE_SELECTED":
        req = request(state, "PYTHON_CATALOGUE", purpose=goal["utility"],
                      supported_language=python_tools.LANGUAGE)
        return event(state, "REQUESTED", status="REQUESTED", reason="NATIVE_TOOL_DISCOVERY", request=req)
    if a["phase"] == "PYTHON_CATALOGUE_RECEIVED":
        receipt = a["responses"][-1]["response"]
        frozen = {"goal": digest(goal), "parent_genome": goal["parent_genome"],
                  "runtime": goal["runtime_digest"], "tool_receipt": digest(receipt),
                  "contract": goal["contract"]}
        return event(state, "SEARCH_FROZEN", status="SEARCH_FROZEN", reason="TOOLS_INPUTS_AND_CRITERIA_FROZEN",
                     goal=goal["id"], frozen=frozen, freeze=digest(frozen))
    if a["phase"] == "SEARCH_FROZEN":
        receipt = a["responses"][-1]["response"]
        if goal.get("transfer_from"):
            primitive = python_tools.gene(["order", goal["required_capability"],
                ["input", goal["contract"]["input_fields"][0]]],
                sorted(goal["training"][0]["input"]), digest(receipt))
            search = {"gene": primitive, "attempts": 1}
        else:
            search = python_tools.synthesize(goal["training"], digest(receipt))
            primitive = search["gene"]
        if primitive is None:
            return event(state, "WITHHOLD", status="WITHHOLD", reason="PYTHON_COMPOSITION_SEARCH_EXHAUSTED",
                goal=goal["id"], report={"native_search_attempts": search["attempts"], "fresh_cases_seen": 0})
        extended = {**memory, primitive["id"]: primitive}
        program = candidate(["apply", primitive["id"], ["object", {
            k: ["input", k] for k in primitive["definition"]["parameters"]}]], extended)
        isolated = evaluate([{"program": program, "rows": goal["training"]}], extended)
        if isolated["results"][0]["passed"] != len(goal["training"]):
            return event(state, "WITHHOLD", status="WITHHOLD", reason="PYTHON_COMPOSITION_TRAIN_FAILED",
                         goal=goal["id"], report={"isolated_train": isolated, "fresh_cases_seen": 0})
        body = event(state, "CANDIDATE_FROZEN", status="FROZEN", reason="AWAITING_FRESH_INDEPENDENT_EVALUATION",
            goal=goal["id"], parent_genome=goal["parent_genome"], program=program, primitive=primitive,
            report={"search_attempts": search["attempts"], "isolated_train": isolated, "fresh_cases_seen": 0,
                    "tools_used": primitive["tools"], "catalogue_receipt": digest(receipt),
                    "algorithm_invention_claim": False, "author": primitive["author"]})
        return {**body, "freeze": digest(body)}
    return None


def validate_response(state, raw):
    a = state["autonomy"]
    normalized(raw)
    if (a["phase"] != "REQUESTED" or not a["request"] or
            a["request"]["kind"] != "PYTHON_CATALOGUE" or
            set(raw) != {"kind", "request", "catalogue", "environment"} or
            raw["kind"] != "PYTHON_CATALOGUE" or raw["request"] != a["request"]["id"] or
            raw["catalogue"] != python_tools.catalogue()):
        raise ContractError("Python tool response does not match the native request and runtime")
    if (type(raw["environment"]) is not dict or
            raw["environment"].get("python") != state["runtime_manifest"]["python"]):
        raise ContractError("Python environment version does not match the runtime")
    return {"kind": "autonomy_response", "event": state["last_event"]+1, "response": deepcopy(raw)}


def dependency_closure(program, memory):
    found, todo = set(), list(program["parents"])
    while todo:
        pid = todo.pop()
        if pid not in found:
            found.add(pid)
            if pid in memory:
                todo.extend(memory[pid]["parents"])
    return sorted(found)

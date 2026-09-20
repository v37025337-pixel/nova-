"""Bounded endogenous subgoals and external knowledge requests in Kernel's journal.

This is a maintainer-written problem constructor, not unrestricted invention.
It derives ordering subgoals from actual failed permutation tasks. Source and
candidate selection are native; an external broker only fulfils recorded I/O.
"""

from copy import deepcopy
import hashlib
import re
from urllib.parse import urlsplit

from .contracts import ContractError, dataset_id, digest, encode, normalized, task_spec
from .evaluation import score
from .extensions import applications, learn
from .genetics import vary
from .isolation import evaluate
from .language import candidate
from .synthesis import synthesize
from . import library_evolution

ALLOWED_HOSTS = ("peps.python.org", "docs.python.org", "packaging.python.org",
                 "www.rfc-editor.org", "csrc.nist.gov", "nvlpubs.nist.gov")
CONFIG = {"required_generations": 3, "fresh_min": 16, "fresh_max": 24,
          "success_threshold": 1, "max_documents": 3,
          "problem_constructor": "failed_permutation_to_pair_relation_v1"}


def initial():
    return {"enabled": False, "completed": [], "current": None, "request": None,
            "responses": [], "phase": "OFF", "consumed_inputs": [], "candidate": None}


def enabled(state):
    return state["runtime_manifest"]["schema"] in ("nova.kernel.v5", "nova.kernel.v6")


def source_url(value):
    if type(value) is not str or len(value) > 1024:
        raise ContractError("invalid knowledge URL")
    parsed = urlsplit(value)
    if (parsed.scheme != "https" or parsed.hostname not in ALLOWED_HOSTS or
            parsed.username is not None or parsed.password is not None or
            parsed.port not in (None, 443) or parsed.fragment):
        raise ContractError("knowledge URL must use an allowed public HTTPS source")
    return value


def relation_goal(state, memory):
    """No task IDs, package names, generation numbers or future labels are inputs."""
    previous = {x["goal"]["deficit_id"] for x in state["autonomy"]["completed"]
                if not library_evolution.retryable(x, state)}
    options = []
    for tid, history in sorted(state["experience"].items()):
        if tid not in state["tasks"] or tid in state["generations"][state["current"]]:
            continue
        if not history or history[-1]["reason"] != "HOLDOUT_FAILED":
            continue
        task = state["tasks"][tid]
        examples = []
        for row in task["holdout"]:
            ordered = row["output"]
            if type(ordered) is not list or len(ordered) < 3:
                continue
            for field, values in row["input"].items():
                if (type(values) is not list or sorted(map(encode, values)) != sorted(map(encode, ordered)) or
                        len(set(map(encode, ordered))) != len(ordered)):
                    continue
                for i, left in enumerate(ordered):
                    for right in ordered[i+1:]:
                        examples.extend([{"input": {"left": left, "right": right}, "output": True},
                                         {"input": {"left": right, "right": left}, "output": False}])
        unique = {digest(r["input"]): r for r in examples}
        rows = [unique[k] for k in sorted(unique)]
        if len(rows) < 24:
            continue
        values = [x for row in rows for x in row["input"].values()]
        if all(type(x) in (int, float) for x in values):
            law, terms = "numeric_less", ["numeric", "comparison", "ordering", "specification"]
        elif all(type(x) is str and re.fullmatch(r"[0-9]+(?:\.[0-9]+)+", x) for x in values):
            law, terms = "lexicographic_integer_components", ["version", "numeric", "ordering", "specification"]
        else:
            continue
        def hypothesis(row):
            left, right = row["input"]["left"], row["input"]["right"]
            if law == "lexicographic_integer_components":
                left = tuple(int(x) for x in left.split("."))
                right = tuple(int(x) for x in right.split("."))
            return left < right
        if any(hypothesis(row) != row["output"] for row in rows):
            continue
        # The ontology has two named properties; it is not a general NL reader.
        # The relation is hypothesised from failed examples, and the external
        # evaluator must check the declared law on fresh inputs after freeze.
        deficit_id = digest([tid, history[-1]["event"], law])
        if deficit_id in previous:
            continue
        training, holdout = rows[:16], rows[16:24]
        old_best = max((score(p, training, memory)["passed"] for p in memory.values()), default=0)
        if old_best == len(training):
            continue
        contract = {"law": law, "input_fields": ["left", "right"], "output": "boolean",
                    "properties": ["irreflexive", "asymmetric", "transitive", "declared_order_law"],
                    "fresh_min": CONFIG["fresh_min"], "success_threshold": 1,
                    "regression_threshold": 1, "ablation_required": True}
        body = {"deficit_id": deficit_id, "origin": "native_analysis_of_failed_permutations",
                "root_task": tid, "root_task_origin": "operator", "cause_event": history[-1]["event"],
                "root_dataset": digest(task), "observed_failure": history[-1]["reason"],
                "observed_pair_count": len(rows), "best_inherited_train": old_best,
                "contract": contract, "search_terms": terms,
                "utility": "supply a reusable ordering relation missing from the failed permutation skill",
                "parent_generation": state["current"], "parent_genome": state["genomes"][state["current"]]["id"],
                "runtime_digest": digest(state["runtime_manifest"]),
                "evidence_sources": [task["source"]], "training": training, "original_holdout": holdout,
                "claim_boundary": "endogenous subgoal of an operator-originated failure; bounded property ontology"}
        body["id"] = "auto-" + digest(body)[:24]
        options.append(body)
    return min(options, key=lambda g: (g["cause_event"], g["id"])) if options else None


def event(state, phase, **fields):
    return {"kind": "autonomy_step", "phase": phase, "event": state["last_event"] + 1, **fields}


def request(state, kind, **fields):
    body = {"kind": kind, "goal": state["autonomy"]["current"]["id"], **fields}
    return {**body, "id": digest(body)}


def rank_sources(goal, results):
    terms = set(goal["search_terms"])
    ranked = []
    for row in results:
        tokens = set(re.findall(r"[a-z]+", (row["title"] + " " + row["snippet"] + " " + row["url"]).lower()))
        ranked.append({**row, "relevance": len(terms & tokens)})
    return sorted(ranked, key=lambda r: (-r["relevance"], r["url"]))


def propose(state, memory):
    a = state["autonomy"]
    if not a["enabled"]:
        return None
    if a["current"] is None:
        goal = library_evolution.transfer_goal(state, memory) if library_evolution.enabled(state) else None
        goal = goal or relation_goal(state, memory)
        if goal is None:
            return {"status": "IDLE", "reason": "NO_SUPPORTED_ENDOGENOUS_DEFICIT"}
        return event(state, "GOAL_FROZEN", status="GOAL_FROZEN", reason="NEW_RELATIONAL_SUBGOAL",
                     goal=goal, freeze=digest(goal))
    goal = a["current"]
    if library_evolution.enabled(state) and goal["runtime_digest"] != digest(state["runtime_manifest"]):
        return event(state, "WITHHOLD", status="WITHHOLD", reason="AUTONOMOUS_RUNTIME_STALE", goal=goal["id"])
    if goal["parent_genome"] != state["genomes"][state["current"]]["id"]:
        return event(state, "WITHHOLD", status="WITHHOLD", reason="AUTONOMOUS_GOAL_STALE", goal=goal["id"])
    if library_evolution.enabled(state):
        proposal = library_evolution.propose(state, memory)
        if proposal is not None:
            return proposal
    if a["phase"] == "GOAL_FROZEN":
        # Representation-based routing precedes code generation. It is an
        # explicit hypothesis, not a proof that the old search is impossible.
        choice = "PROGRAM_GENE" if goal["contract"]["law"] == "numeric_less" else "ALGORITHM_MECHANISM"
        return event(state, "ROUTE_SELECTED", status="PLANNED", reason="NATIVE_REPRESENTATION_DIAGNOSIS",
                     goal=goal["id"], change_type=choice,
                     alternatives={"PROGRAM_GENE": "numeric comparison exists" if choice == "PROGRAM_GENE" else "no scalar string-to-components operation",
                                   "ENGINE_POLICY": "ordering more existing operators does not add string decomposition",
                                   "GRAMMAR_EXTENSION": "formal specification needed before generating a primitive",
                                   "ALGORITHM_MECHANISM": "component decomposition and ordered comparison required"},
                     proof_of_impossibility=False)
    if a["phase"] == "ROUTE_SELECTED":
        req = request(state, "SEARCH", query=" ".join(goal["search_terms"]), allowed_hosts=list(ALLOWED_HOSTS))
        return event(state, "REQUESTED", status="REQUESTED", reason="KNOWLEDGE_SEARCH", request=req)
    if a["phase"] == "SEARCH_RECEIVED":
        ranking = rank_sources(goal, a["responses"][-1]["response"]["results"])
        if not ranking:
            return event(state, "WITHHOLD", status="WITHHOLD", reason="NO_ELIGIBLE_KNOWLEDGE_SOURCE", goal=goal["id"])
        req = request(state, "READ", url=ranking[0]["url"], title=ranking[0]["title"], terms=goal["search_terms"])
        return event(state, "REQUESTED", status="REQUESTED", reason="NATIVE_SOURCE_SELECTION", request=req, ranking=ranking)
    if a["phase"] == "DOCUMENT_RECEIVED":
        docs = [x["response"] for x in a["responses"] if x["response"]["kind"] == "DOCUMENT"]
        search_results = next(x["response"]["results"] for x in a["responses"] if x["response"]["kind"] == "SEARCH_RESULTS")
        ranking = rank_sources(goal, search_results)
        remaining = [r for r in ranking if r["url"] not in {d["url"] for d in docs}]
        if remaining and len(docs) < CONFIG["max_documents"]:
            selected = remaining[0]
            req = request(state, "READ", url=selected["url"], title=selected["title"], terms=goal["search_terms"])
            return event(state, "REQUESTED", status="REQUESTED", reason="NATIVE_SOURCE_SELECTION", request=req, ranking=ranking)
        freeze = {"goal": digest(goal), "parent_genome": goal["parent_genome"],
                  "runtime": goal["runtime_digest"], "source_documents": [digest(d) for d in docs],
                  "contract": goal["contract"]}
        return event(state, "SEARCH_FROZEN", status="SEARCH_FROZEN", reason="INPUTS_AND_CRITERIA_FROZEN",
                     goal=goal["id"], frozen=freeze, freeze=digest(freeze))
    if a["phase"] == "SEARCH_FROZEN":
        return build(state, memory)
    if a["phase"] == "REQUESTED":
        return {"status": "WAITING", "reason": "EXTERNAL_IO_REQUIRED", "request": a["request"]}
    if a["phase"] == "CANDIDATE_FROZEN":
        return {"status": "WAITING", "reason": "FRESH_HOLDOUT_REQUIRED", "freeze": a["candidate"]["freeze"]}
    raise ContractError("unknown autonomy phase")


def build(state, memory):
    a, goal = state["autonomy"], state["autonomy"]["current"]
    training = goal["training"]
    # No fresh holdout or original holdout enters either synthesis API.
    search = synthesize(training, memory, state["genomes"][state["current"]].get("engine"))
    program, primitive = search["program"], None
    compiler_receipts = []
    if program is None:
        for response in a["responses"]:
            doc = response["response"]
            if doc["kind"] != "DOCUMENT":
                continue
            spec = {"id": "auto-doc-" + doc["sha256"][:24], "source": doc["url"], "title": doc["title"],
                    "width": 32, "text": doc["text"], "provenance": "external-source-sha256:" + doc["source_sha256"]}
            learned = learn(spec)
            compiler_receipts.append({"document": digest(doc), "generated_genes": len(learned["genes"]),
                                      "unsupported": learned["unsupported"]})
            for gene in learned["genes"]:
                extended = {**memory, gene["id"]: gene}
                for ir in applications(gene, training, memory):
                    proposed = candidate(ir, extended)
                    if score(proposed, training, extended)["passed"] == len(training):
                        program, primitive = proposed, gene
                        break
                if program:
                    break
            if program:
                break
    if program is None:
        return event(state, "WITHHOLD", status="WITHHOLD", reason="KNOWLEDGE_NOT_EXECUTABLE_IN_CURRENT_GRAMMAR",
                     goal=goal["id"], report={"native_search_attempts": search["attempts"],
                     "document_compilation": compiler_receipts, "fresh_cases_seen": 0,
                     "next_requirement": "general string/sequence relation compiler; no ready library substitution"})
    extended = {**memory, **({primitive["id"]: primitive} if primitive else {})}
    isolated = evaluate([{"program": program, "rows": training}], extended)
    body = event(state, "CANDIDATE_FROZEN", status="FROZEN", reason="AWAITING_FRESH_INDEPENDENT_EVALUATION",
                 goal=goal["id"], parent_genome=goal["parent_genome"], program=program, primitive=primitive,
                 report={"search_attempts": search["attempts"], "document_compilation": compiler_receipts,
                         "isolated_train": isolated, "fresh_cases_seen": 0})
    return {**body, "freeze": digest(body)}


def validate_response(state, raw):
    a = state["autonomy"]
    if library_evolution.enabled(state) and (a.get("request") or {}).get("kind") == "PYTHON_CATALOGUE":
        return library_evolution.validate_response(state, raw)
    if a["phase"] != "REQUESTED" or not a["request"]:
        raise ContractError("there is no pending autonomous I/O request")
    normalized(raw)
    req = a["request"]
    if raw.get("request") != req["id"]:
        raise ContractError("response belongs to another request")
    if req["kind"] == "SEARCH":
        if set(raw) != {"kind", "request", "results"} or raw["kind"] != "SEARCH_RESULTS":
            raise ContractError("invalid search response")
        if type(raw["results"]) is not list or not 1 <= len(raw["results"]) <= 12:
            raise ContractError("search results must contain 1..12 sources")
        seen = set()
        for item in raw["results"]:
            if set(item) != {"url", "title", "snippet"}:
                raise ContractError("invalid search result fields")
            source_url(item["url"])
            if item["url"] in seen or any(type(item[k]) is not str for k in ("title", "snippet")):
                raise ContractError("duplicate or invalid search result")
            seen.add(item["url"])
    else:
        if set(raw) != {"kind", "request", "url", "title", "text", "sha256", "source_sha256", "obtained_at"} or raw["kind"] != "DOCUMENT":
            raise ContractError("invalid document response")
        if raw["url"] != req["url"] or raw["title"] != req["title"]:
            raise ContractError("source changed after native selection")
        if (type(raw["text"]) is not str or not raw["text"] or
                hashlib.sha256(raw["text"].encode()).hexdigest() != raw["sha256"] or
                not re.fullmatch(r"[a-f0-9]{64}", raw["source_sha256"])):
            raise ContractError("document hash or text mismatch")
    return {"kind": "autonomy_response", "event": state["last_event"] + 1, "response": deepcopy(raw)}


def assess(state, frozen_id, rows, memory):
    a, goal = state["autonomy"], state["autonomy"]["current"]
    frozen = a["candidate"]
    if a["phase"] != "CANDIDATE_FROZEN" or frozen is None or frozen["freeze"] != frozen_id:
        raise ContractError("unknown or consumed autonomous candidate")
    if goal["parent_genome"] != state["genomes"][state["current"]]["id"]:
        raise ContractError("autonomous candidate belongs to another genome")
    if library_evolution.enabled(state) and goal["runtime_digest"] != digest(state["runtime_manifest"]):
        raise ContractError("autonomous candidate belongs to another runtime")
    if type(rows) is not list or not CONFIG["fresh_min"] <= len(rows) <= CONFIG["fresh_max"]:
        raise ContractError("autonomous assessment needs 16..24 fresh examples")
    tid = goal["id"]
    task = task_spec({"id": tid, "source": "kernel:autonomy:" + digest(goal),
                      "train": goal["training"], "holdout": rows})
    if encode(rows) != encode(task["holdout"]):
        raise ContractError("fresh evaluation must use canonical JSON values")
    seen = {digest(r["input"]) for old in state["tasks"].values() for split in ("train", "holdout") for r in old[split]}
    seen |= {digest(r["input"]) for r in goal["training"] + goal["original_holdout"]}
    seen |= set(a["consumed_inputs"])
    if any(digest(r["input"]) in seen for r in rows):
        raise ContractError("fresh autonomous evaluation overlaps known inputs")
    program, primitive = frozen["program"], frozen["primitive"]
    extended = {**memory, **({primitive["id"]: primitive} if primitive else {}), program["id"]: program}
    result = evaluate([{"program": program, "rows": rows}, {"program": program, "rows": goal["original_holdout"]}], extended)
    regression = {}
    for old_tid, pid in sorted(state["generations"][state["current"]].items()):
        old = state["tasks"][old_tid]
        regression[old_tid] = evaluate([{"program": memory[pid], "rows": old["train"] + old["holdout"]}], extended)["results"][0]
    parent_best = max((score(p, rows, memory)["passed"] for p in memory.values()), default=0)
    dependencies = (library_evolution.dependency_closure(program, extended)
                    if library_evolution.enabled(state) else program["parents"])
    ablation = {pid: evaluate([{"program": program, "rows": rows}], {k: v for k, v in extended.items() if k != pid})["results"][0]
                for pid in dependencies}
    reason = "VERIFIED_AUTONOMOUS_SUBGOAL"
    if any(r["passed"] != r["total"] for r in result["results"]):
        reason = "AUTONOMOUS_HOLDOUT_FAILED"
    elif any(r["passed"] != r["total"] for r in regression.values()):
        reason = "REGRESSION_FAILED"
    elif parent_best == len(rows):
        reason = "NO_NEW_ABILITY_OVER_INHERITED_GENES"
    # An extension must be ablated by its actual dependency; expression genes
    # instead compare old active programs and ablate every inherited dependency.
    elif primitive and ablation.get(primitive["id"], {}).get("passed", len(rows)) == len(rows):
        reason = "NO_CAUSAL_CAPABILITY_IMPROVEMENT"
    elif goal.get("required_capability") and ablation.get(goal["required_capability"], {}).get("passed", len(rows)) == len(rows):
        reason = "NO_CAUSAL_TRANSFER"
    mutation = vary(state["genomes"][state["current"]], tid, program, memory) if primitive is None else None
    if primitive is not None:
        from .genetics import genome
        parent = state["genomes"][state["current"]]
        mutation = {"child_genome": genome({**parent["bindings"], tid: program["id"]}, parent["id"], parent.get("engine"), parent.get("capabilities", []) + [primitive["id"]])}
    task["holdout"] = goal["original_holdout"] + rows
    return {"kind": "autonomy_evaluation", "event": state["last_event"] + 1,
            "freeze": frozen_id, "rows": rows, "task": task, "program": program, "primitive": primitive,
            "mutation": mutation, "status": "ADMITTED" if reason == "VERIFIED_AUTONOMOUS_SUBGOAL" else "WITHHOLD",
            "reason": reason, "generation": state["admissions"] + 1 if reason == "VERIFIED_AUTONOMOUS_SUBGOAL" else state["current"],
            "report": {"isolation": result["isolation"], "fresh": result["results"][0], "original_holdout": result["results"][1],
                       "regression": regression, "ablation": ablation, "best_inherited_passed": parent_best}}


def apply(state, body):
    a = state["autonomy"]
    kind = body["kind"]
    if kind == "autonomy_start":
        a["enabled"], a["phase"] = True, "DISCOVER"
        return
    if kind == "autonomy_response":
        a["responses"].append(body)
        a["phase"] = "SEARCH_RECEIVED" if body["response"]["kind"] == "SEARCH_RESULTS" else "DOCUMENT_RECEIVED"
        if body["response"]["kind"] == "PYTHON_CATALOGUE":
            a["phase"] = "PYTHON_CATALOGUE_RECEIVED"
        a["request"] = None
        return
    if kind == "autonomy_evaluation":
        a["consumed_inputs"].extend(digest(r["input"]) for r in body["rows"])
        state["attempts"] += 1
        if body["status"] == "ADMITTED":
            tid, generation = body["task"]["id"], body["generation"]
            state["tasks"][tid] = body["task"]
            state["consumed"].add(dataset_id(body["task"]))
            state["task_events"][tid] = a["goal_event"]
            for program in (body["program"], body["primitive"]):
                if program:
                    state["programs"][program["id"]] = program
                    state["gene_events"].setdefault(program["id"], body["event"])
            state["parents"][generation] = state["current"]
            state["genomes"][generation] = body["mutation"]["child_genome"]
            state["generations"][generation] = {**state["generations"][state["current"]], tid: body["program"]["id"]}
            state["current"] = generation
            state["admissions"] += 1
            state["experience"][tid] = [{"event": body["event"], "context": digest(a["current"]),
                "causes": {"task_event": a["goal_event"]}, "memory_context": a["current"]["parent_genome"],
                "status": "ADMITTED", "reason": body["reason"], "program": body["program"]["id"],
                "search_attempts": a["candidate"]["report"]["search_attempts"]}]
        finish(state, body)
        return
    a["phase"] = body["phase"]
    if body["phase"] == "GOAL_FROZEN":
        a.update(current=body["goal"], goal_event=body["event"], responses=[], request=None, candidate=None)
    elif body["phase"] == "REQUESTED":
        a["request"] = body["request"]
    elif body["phase"] == "CANDIDATE_FROZEN":
        a["candidate"] = body
    elif body["phase"] == "WITHHOLD":
        finish(state, body)


def finish(state, body):
    a = state["autonomy"]
    a["completed"].append({"goal": a["current"], "outcome": body})
    a.update(current=None, candidate=None, request=None, phase="DISCOVER")


def status(state):
    a = state["autonomy"]
    admitted = [x for x in a["completed"] if x["outcome"]["status"] == "ADMITTED"]
    return {"enabled": a["enabled"], "phase": a["phase"], "request": a["request"],
            "current_goal": a["current"], "completed": len(a["completed"]),
            "admissions": len(admitted), "required_generations": CONFIG["required_generations"],
            "claim": ("bounded_library_assisted_subgoal_and_transfer" if library_evolution.enabled(state)
                      else "bounded_endogenous_relational_subgoal_loop"),
            "autonomous_capability_evolution_proven": False}

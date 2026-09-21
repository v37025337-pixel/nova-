"""Bounded self-supervised field prediction from complete JSON/CSV observations.

The parser, field-pair ontology, baseline family and selection rule are written
by the maintainer. Actual values, prediction errors, the chosen field pair and
the synthesized program come from runtime observations. A prediction error is
not proof that its target is predictable, causal, or scientifically meaningful.
"""

import csv
import hashlib
import io
from collections import Counter, defaultdict
from copy import deepcopy
from itertools import zip_longest
from urllib.parse import urlsplit

from .contracts import ContractError, decode, digest, encode, normalized
from .evaluation import score
from .isolation import evaluate
from .language import candidate
from .synthesis import synthesize

LAW = "observed_field_reconstruction"
CONFIG = {"document_bytes": 262144, "window_documents": 32, "records_per_document": 128,
          "fields_per_record": 16, "tree_nodes": 8192, "pairs_per_decision": 64,
          "training_rows": 8, "diagnostic_rows": 8, "minimum_errors": 3,
          "minimum_error_sources": 2}


def enabled(state):
    return state["runtime_manifest"]["schema"] in ("nova.kernel.v7", "nova.kernel.v8")


def extract(raw):
    if type(raw) is not dict or set(raw) != {"source", "media_type", "text", "sha256", "obtained_at"}:
        raise ContractError("observation requires source, media_type, text, sha256, obtained_at")
    if any(type(raw[k]) is not str for k in raw):
        raise ContractError("observation fields must be strings")
    source = urlsplit(raw["source"])
    if (len(raw["source"]) > 1024 or source.scheme != "https" or not source.hostname or
            source.username is not None or source.password is not None or
            source.port not in (None, 443) or source.fragment):
        raise ContractError("observation provenance must use a credential-free HTTPS URL")
    data = raw["text"].encode("utf-8")
    if (not data or len(data) > CONFIG["document_bytes"] or
            hashlib.sha256(data).hexdigest() != raw["sha256"] or
            not 1 <= len(raw["obtained_at"]) <= 128):
        raise ContractError("observation content, hash or timestamp is invalid")
    media = raw["media_type"].split(";", 1)[0].strip().lower()
    if media == "application/json" or media.endswith("+json"):
        try:
            root = decode(raw["text"])
        except (ValueError, RecursionError) as exc:
            raise ContractError("observation is not complete valid JSON") from exc
    elif media == "text/csv":
        try:
            reader = csv.DictReader(io.StringIO(raw["text"]), strict=True)
            if not reader.fieldnames or len(set(reader.fieldnames)) != len(reader.fieldnames):
                raise ContractError("CSV needs unique nonempty headers")
            root = []
            for row in reader:
                if None in row or any(v is None for v in row.values()):
                    raise ContractError("CSV row width differs from its header")
                root.append(row)
                if len(root) > CONFIG["records_per_document"]:
                    break
        except csv.Error as exc:
            raise ContractError("invalid CSV observation") from exc
    else:
        raise ContractError("observation parser supports complete JSON and CSV only")
    records, nodes, limited = [], 0, False

    def visit(value, path, location, depth=0):
        nonlocal nodes, limited
        nodes += 1
        if nodes > CONFIG["tree_nodes"] or depth > 16 or len(records) >= CONFIG["records_per_document"]:
            limited = True
            return
        if type(value) is dict:
            fields = {}
            for key in sorted(value):
                item = value[key]
                if len(key) > 128 or type(item) not in (str, int, float, bool):
                    continue
                if type(item) is str and len(item) > 1024:
                    continue
                try:
                    fields[key] = normalized(item)
                except ContractError:
                    continue
            if len(fields) > CONFIG["fields_per_record"]:
                limited = True
                fields = dict(list(fields.items())[:CONFIG["fields_per_record"]])
            if len(fields) >= 2:
                records.append({"path": path, "location": location, "values": fields})
            def segment(key):
                return key.replace("~", "~0").replace("/", "~1").replace("*", "~2")
            children = ((value[k], path + "/" + segment(k), location + "/" + segment(k)) for k in sorted(value))
        elif type(value) is list:
            children = ((v, path + "/*", location + "/" + str(i)) for i, v in enumerate(value))
        else:
            return
        for child, child_path, child_location in children:
            if nodes >= CONFIG["tree_nodes"] or len(records) >= CONFIG["records_per_document"]:
                limited = True
                break
            if type(child) in (dict, list):
                visit(child, child_path, child_location, depth + 1)

    visit(root, "", "")
    return {"records": records, "receipt": {"records": len(records), "limited": limited,
            "parser": "complete_json_csv_scalar_records_v1", "sha256": raw["sha256"]}}


def ingest(state, raw):
    if not enabled(state):
        raise ContractError("structured observations require runtime v7")
    extracted = extract(raw)
    if raw["sha256"] in state["observation_hashes"]:
        raise ContractError("observation payload was already recorded")
    return {"kind": "observation", "document": deepcopy(raw), "receipt": extracted["receipt"]}, extracted


def apply(state, body, extracted):
    raw = body["document"]
    state["observation_hashes"].add(raw["sha256"])
    for record in extracted["records"]:
        state["observation_inputs"].update(digest({k: v}) for k, v in record["values"].items())
    state["observations"].append({"source": raw["source"], "sha256": raw["sha256"],
        "event": state["last_event"] + 1, "records": extracted["records"]})
    state["observations"] = state["observations"][-CONFIG["window_documents"]:]


def groups(state):
    pairs = defaultdict(lambda: defaultdict(list))
    for doc in state["observations"]:
        host = urlsplit(doc["source"]).hostname
        for record in doc["records"]:
            fields = record["values"]
            for inp in sorted(fields):
                for target in sorted(fields):
                    if inp == target:
                        continue
                    key = (host, record["path"], inp, target, type(fields[inp]).__name__, type(fields[target]).__name__)
                    pairs[key][doc["source"]].append({
                        "row": {"input": {inp: fields[inp]}, "output": fields[target]},
                        "source": doc["source"], "event": doc["event"],
                        "sha256": doc["sha256"], "location": record["location"]})
    eligible = []
    for key, sources in sorted(pairs.items()):
        if len(sources) < CONFIG["minimum_error_sources"]:
            continue
        # Interleave sources before splitting: neither split is a single URL.
        entries, seen, conflicting = [], {}, False
        for batch in zip_longest(*(sources[s] for s in sorted(sources))):
            for item in batch:
                if item is None:
                    continue
                token = digest(item["row"]["input"])
                output = encode(item["row"]["output"])
                if token in seen:
                    if seen[token] != output:
                        conflicting = True
                    continue
                seen[token] = output
                entries.append(item)
        if (conflicting or len(entries) < CONFIG["training_rows"] + CONFIG["diagnostic_rows"] or
                len({encode(x["row"]["output"]) for x in entries}) < 2):
            continue
        eligible.append((key, entries))
    return eligible


def discover(state, memory):
    if not enabled(state):
        return None
    attempted = {r["goal"]["deficit_id"] for r in state["autonomy"]["completed"]}
    eligible, options = groups(state), []
    for key, entries in eligible[:CONFIG["pairs_per_decision"]]:
        training = [e["row"] for e in entries[:CONFIG["training_rows"]]]
        diagnostic = entries[CONFIG["training_rows"]:CONFIG["training_rows"] + CONFIG["diagnostic_rows"]]
        rows = [e["row"] for e in diagnostic]
        counts = Counter(encode(r["output"]) for r in training)
        modal = decode(min(counts, key=lambda v: (-counts[v], v)))
        predictors = [candidate(["input", key[2]], {}), candidate(["const", modal], {}), *memory.values()]
        # Predictor is selected using training only, before examining errors.
        predictor = min(predictors, key=lambda p: (-score(p, training, memory)["passed"], p["id"]))
        result = score(predictor, rows, memory)
        errors = [{**e, "prediction": outcome} for e, outcome in zip(diagnostic, result["outcomes"]) if not outcome["ok"]]
        error_sources = sorted({e["source"] for e in errors})
        if len(errors) < CONFIG["minimum_errors"] or len(error_sources) < CONFIG["minimum_error_sources"]:
            continue
        deficit = digest([LAW, key, [e["row"] for e in entries]])
        if deficit in attempted:
            continue
        contract = {"host": key[0], "record_path": key[1], "input_field": key[2], "target_field": key[3],
                    "input_type": key[4], "target_type": key[5]}
        body = {"deficit_id": deficit, "origin": "native_observation_prediction_error",
                "root_task": None, "root_task_origin": "unlabelled_observation",
                "cause_event": min(e["event"] for e in errors), "root_dataset": digest(entries),
                "observed_failure": "REPEATED_FIELD_PREDICTION_ERROR", "predictability_proven": False,
                "contract": {"law": LAW, "input_fields": [key[2]], "output": key[5],
                    "fresh_min": 16, "success_threshold": 1, "regression_threshold": 1,
                    "ablation_required": True, "properties": ["exact_agreement_with_unseen_observed_field"]},
                "observation_contract": contract, "baseline_program": predictor,
                "prediction_evidence": {"failed": len(errors), "total": len(rows), "errors": errors,
                    "predictor_selected_on": "training_only", "baseline_training": score(predictor, training, memory),
                    "diagnostic_is_fresh_evaluation": False},
                "selection": {"eligible_pairs": len(eligible), "evaluated_pairs": min(len(eligible), CONFIG["pairs_per_decision"]),
                    "rule": "most_diagnostic_errors_then_oldest_event_then_goal_identity"},
                "utility": "test whether an observed field can be reconstructed from another field with a reusable program",
                "parent_generation": state["current"], "parent_genome": state["genomes"][state["current"]]["id"],
                "runtime_digest": digest(state["runtime_manifest"]), "evidence_sources": error_sources,
                "training": training, "original_holdout": rows,
                "claim_boundary": "maintainer-defined field-pair ontology; selected by measured errors; no causality or predictability proof"}
        body["id"] = "auto-" + digest(body)[:24]
        options.append(body)
    return min(options, key=lambda g: (-g["prediction_evidence"]["failed"], g["cause_event"], g["id"])) if options else None


def propose(state, memory):
    from .autonomy import event
    a, goal = state["autonomy"], state["autonomy"]["current"]
    if not enabled(state) or not goal or goal["contract"]["law"] != LAW:
        return None
    if a["phase"] == "GOAL_FROZEN":
        frozen = {"goal": digest(goal), "training": digest(goal["training"]),
                  "runtime": goal["runtime_digest"], "parent_genome": goal["parent_genome"]}
        return event(state, "SEARCH_FROZEN", status="SEARCH_FROZEN", reason="OBSERVATION_INPUTS_AND_CRITERIA_FROZEN",
                     goal=goal["id"], frozen=frozen, freeze=digest(frozen))
    if a["phase"] != "SEARCH_FROZEN":
        return None
    searcher = synthesize
    if state["runtime_manifest"]["schema"] == "nova.kernel.v8":
        from .ucr_development import synthesize as searcher
    search = searcher(goal["training"], memory, state["genomes"][state["current"]].get("engine"))
    details = {"ucr": search["ucr"], "native_search_attempts": search["native_attempts"]} if "ucr" in search else {}
    program = search["program"]
    if program is None:
        return event(state, "WITHHOLD", status="WITHHOLD", reason="OBSERVATION_SEARCH_EXHAUSTED",
                     goal=goal["id"], report={"native_search_attempts": search["attempts"], "fresh_cases_seen": 0,
                     "predictability_proven": False, **details})
    isolated = evaluate([{"program": program, "rows": goal["training"]}], memory)
    if isolated["results"][0]["passed"] != len(goal["training"]):
        return event(state, "WITHHOLD", status="WITHHOLD", reason="OBSERVATION_TRAIN_FAILED", goal=goal["id"])
    body = event(state, "CANDIDATE_FROZEN", status="FROZEN", reason="AWAITING_FRESH_INDEPENDENT_EVALUATION",
                 goal=goal["id"], parent_genome=goal["parent_genome"], program=program, primitive=None,
                 report={"search_attempts": search["attempts"], "isolated_train": isolated,
                         "fresh_cases_seen": 0, "author": "kernel_training_only", **details})
    return {**body, "freeze": digest(body)}

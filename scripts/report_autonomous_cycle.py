"""Report the pre-registered gates without treating missing evidence as PASS.

This is an evidence reporter, not a general theorem prover for autonomy. In
particular the bounded, operator-rooted goal constructor cannot pass gate 1.
"""

import argparse
import gzip
import hashlib
import json
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from nova_core.contracts import digest, encode
from nova_core.kernel import runtime_manifest
from run_development_chain import write_json


def report(output):
    protocol = json.loads((output / "protocol.json").read_text())
    summary = json.loads((output / "run-summary.json").read_text())
    exported = json.loads((output / "journal.json").read_text())
    parent = json.loads((ROOT / protocol["parent_journal"]).read_text())
    events = exported["events"][len(parent["events"]):]
    replay = json.loads((output / "cold-replay.json").read_text())
    goals = [e for e in events if e.get("phase") == "GOAL_FROZEN"]
    freezes = [e for e in events if e.get("phase") == "SEARCH_FROZEN"]
    routes = [e for e in events if e.get("phase") == "ROUTE_SELECTED"]
    candidates = [e for e in events if e.get("phase") == "CANDIDATE_FROZEN"]
    evaluations = [e for e in events if e["kind"] == "autonomy_evaluation"]
    admissions = [e for e in evaluations if e["status"] == "ADMITTED"]
    documents = [e["response"] for e in events if e["kind"] == "autonomy_response" and e["response"]["kind"] == "DOCUMENT"]
    requests = [e["request"] for e in events if e.get("phase") == "REQUESTED"]
    unchanged = digest(runtime_manifest()) == protocol["runtime_sha256"]
    for relative in protocol["frozen_files"] + [str((output / "protocol.json").relative_to(ROOT))]:
        unchanged &= subprocess.check_output(["git", "show", summary["protocol_commit"] + ":" + relative], cwd=ROOT) == (ROOT / relative).read_bytes()
    sources = []
    for path in sorted((output / "sources").glob("document-*.json")):
        if path.name.endswith(".receipt.json"):
            continue
        doc = json.loads(path.read_text())
        raw = gzip.decompress(path.with_suffix(".html.gz").read_bytes())
        sources.append({"url": doc["url"], "source_sha256": doc["source_sha256"],
                        "raw_hash_valid": hashlib.sha256(raw).hexdigest() == doc["source_sha256"],
                        "text_hash_valid": hashlib.sha256(doc["text"].encode()).hexdigest() == doc["sha256"],
                        "journal_matches": doc in documents})
    prefix_ok = encode(exported["events"][:len(parent["events"])]) == encode(parent["events"])
    cold_ok = replay.get("status") == "PASS" and replay.get("head") == exported["head"]
    goals_ok = bool(goals) and all(g["freeze"] == digest(g["goal"]) and
        g["goal"]["contract"]["success_threshold"] == 1 and g["goal"]["utility"] for g in goals)
    freezes_ok = bool(freezes) and all(f["freeze"] == digest(f["frozen"]) and
        any(g["goal"]["id"] == f["goal"] and g["event"] < f["event"] for g in goals) for f in freezes)
    freezes_ok &= all(any(f["goal"] == c["goal"] and f["event"] < c["event"] for f in freezes) for c in candidates)
    regression_ok = summary["regression"]["passed"] == summary["regression"]["total"] == 114 and summary["regression"]["skills"] == 19
    source_ok = bool(sources) and len(sources) == len(documents) and all(all(s[k] for k in ("raw_hash_valid", "text_hash_valid", "journal_matches")) for s in sources)
    def gate(number, status, evidence):
        return {"id": number, "status": status, "requirement": protocol["gates"][number-1]["requirement"], "evidence": evidence}
    gates = [
        gate(1, "PARTIAL" if goals else "FAIL", "Native relation subgoal derived from an operator-originated failed permutation; maintainer-written two-law ontology. No wholly new externally discovered problem family."),
        gate(2, "PASS" if goals_ok else "FAIL", {"goal_ids": [g["goal"]["id"] for g in goals], "artifact": "frozen-goal.json"}),
        gate(3, "PASS" if goals_ok and freezes_ok and unchanged else "FAIL", {"runtime_and_frozen_files_unchanged": unchanged, "artifact": "search-freeze.json"}),
        gate(4, "PARTIAL" if routes else "FAIL", {"selected": [r["change_type"] for r in routes], "limit": "Representation-based routing between two implemented paths, not a general search over all change classes."}),
        gate(5, "PASS" if source_ok and requests else "FAIL", {"native_queries": [r["query"] for r in requests if r["kind"] == "SEARCH"], "sources": sources, "limit": "Allowed domains and I/O broker supplied by maintainer; literal documents selected by native ranking."}),
        gate(6, "PARTIAL" if candidates else "FAIL", {"frozen_candidates": len(candidates), "outcomes": [x["outcome"]["reason"] for x in summary["completed"]]}),
        gate(7, "NOT_RUN" if not evaluations else ("PASS" if all(e["report"]["fresh"]["passed"] == e["report"]["fresh"]["total"] for e in evaluations) else "FAIL"), {"fresh_evaluations": len(evaluations), "fresh_cases": sum(e["report"]["fresh"]["total"] for e in evaluations)}),
        gate(8, "PASS" if regression_ok and prefix_ok else "FAIL", summary["regression"]),
        gate(9, "NOT_RUN" if not evaluations else "PARTIAL", "No new accepted mechanism was available for a causal removal experiment." if not admissions else "Inspect exact new-capability ablation evidence before claiming PASS."),
        gate(10, "PARTIAL" if cold_ok else "FAIL", {"separate_process_cold_replay": cold_ok, "new_admissions": len(admissions), "new_generation_rollback": "NOT_RUN"}),
        gate(11, "NOT_RUN", "No admitted autonomous generation followed by native discovery and execution of a transfer task."),
        gate(12, "FAIL", {"accepted_autonomous_generations": len(admissions), "required": protocol["required_generations"], "causal_three_generation_chain": False})]
    if not prefix_ok or not unchanged or not source_ok or not cold_ok:
        raise AssertionError("experiment evidence integrity failed")
    result = {"schema": "nova.strict-autonomy-review.v1", "status": "WITHHOLD", "gates": gates,
        "claim": "bounded endogenous subgoal discovery and native knowledge requests observed; autonomous capability evolution not established",
        "unit_tests_are_not_autonomy_evidence": True}
    write_json(output / "gate-review.json", result)
    summary.update(status="WITHHOLD", cold_replay={"status": "PASS" if cold_ok else "FAIL", "head": replay["head"]},
        strict_gate_review="gate-review.json", strict_autonomy_proven=False, new_candidates=len(candidates), fresh_cases=sum(e["report"]["fresh"]["total"] for e in evaluations),
        source_requests=len(documents), source_hashes_verified=source_ok)
    write_json(output / "run-summary.json", summary)
    print(json.dumps({"status": result["status"], "admissions": len(admissions), "regression": summary["regression"], "cold_replay": cold_ok, "gates": [{"id": g["id"], "status": g["status"]} for g in gates]}))


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("output", type=Path)
    report(parser.parse_args().output.resolve())

"""Probe the unchanged kernel with its pinned, task-free static graph checkpoint.

This broker records native decisions; it does not invent a goal, relabel one
source as several, supply a program, or treat previously seen rows as fresh.
"""

import argparse
from collections import Counter
from datetime import datetime, timezone
import gzip
import hashlib
from pathlib import Path
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from nova_core.contracts import ContractError, decode, digest, encode
from nova_core.kernel import Kernel, context, runtime_manifest
from nova_core.memory import Journal, ZERO
from nova_core.observations import CONFIG, groups
from scripts.run_development_chain import write_json
from scripts.run_unlabelled_stream import full_regression


def now():
    return datetime.now(timezone.utc).isoformat()


def emit(**fields):
    print(encode(fields), flush=True)


def pinned_parent():
    manifest = decode((ROOT / "canonical/static-codeflow.json").read_text())
    for name, expected in manifest["file_sha256"].items():
        if hashlib.sha256((ROOT / name).read_bytes()).hexdigest() != expected:
            raise ContractError("pinned graph import changed: " + name)
    checkpoint = manifest["checkpoint"]
    parent = decode(gzip.decompress((ROOT / checkpoint["journal"]).read_bytes()).decode())
    if (parent["head"] != checkpoint["head"] or
            len(parent["events"]) != checkpoint["events"]):
        raise ContractError("graph checkpoint anchor mismatch")
    head, prefix_length = ZERO, None
    for index, body in enumerate(parent["events"], 1):
        head = digest([index, head, body])
        if head == checkpoint["parent_head"]:
            prefix_length = index
    if head != parent["head"] or prefix_length is None:
        raise ContractError("invalid graph checkpoint history")
    delta = parent["events"][prefix_length:]
    if not delta or any(e["kind"] != "observation" for e in delta):
        raise ContractError("graph import contains non-observation events")
    return manifest, parent, {e["document"]["sha256"] for e in delta}


def run(output, max_steps=8):
    if not 1 <= max_steps <= 16:
        raise ContractError("probe accepts 1..16 native steps")
    manifest, parent, graph_hashes = pinned_parent()
    output.mkdir(parents=True, exist_ok=False)
    source_commit = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip()
    frozen_runtime = runtime_manifest()
    protocol = {
        "schema": "nova.codeflow-goal-probe.v1", "frozen_at": now(),
        "source_commit": source_commit,
        "runner_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        "runtime_sha256": digest(frozen_runtime), "parent_head": parent["head"],
        "checkpoint_manifest_sha256": digest(manifest), "max_native_steps": max_steps,
        "inputs": "the already imported exact graph observations plus inherited G22 memory",
        "operator_task": None, "operator_solution": None,
        "admission_requirements": [
            "native goal with evidence from supplied graphs", "kernel-produced frozen candidate",
            "16..24 genuinely unseen independently labelled examples after candidate freeze",
            "full inherited regression", "causal improvement over inherited programs",
            "native admission event", "cold replay and restart"],
        "stop_on": ["IDLE", "WAITING", "WITHHOLD", "FROZEN", "REQUESTED"],
        "graph_provenance": "one supplied file; upstream source and dynamic execution unverified",
        "diagnostics": "read-only observation subsets, never journal events or new evidence",
    }
    write_json(output / "protocol.json", protocol)
    state_path = output / "state.sqlite"
    journal = Journal(state_path, create=True)
    try:
        head = ZERO
        for body in parent["events"]:
            head = journal.append(body, head)
        if head != parent["head"]:
            raise ContractError("reconstructed journal changed")
    finally:
        journal.close()
    emit(stage="full_semantic_replay", events=len(parent["events"]), head=head)
    started = time.monotonic()
    with Kernel(state_path) as kernel:
        replay_seconds = time.monotonic() - started
        before = kernel.status()
        if (before["head"] != parent["head"] or before["upgrade_required"] or
                before["genome"] != manifest["checkpoint"]["genome"] or
                before["active_generation"] != manifest["checkpoint"]["active_generation"] or
                not before["autonomy"]["enabled"] or before["autonomy"]["current_goal"]):
            raise ContractError("probe requires the exact idle, current graph checkpoint")
        state, _, _ = kernel._load()
        graph_docs = [d for d in state["observations"] if d["sha256"] in graph_hashes]
        if {d["sha256"] for d in graph_docs} != graph_hashes:
            raise ContractError("graph observations are no longer fully in the active window")
        graph_sources = {d["source"] for d in graph_docs}
        pair_counts = {}
        for label, docs in (
            ("all_observations", state["observations"]),
            ("graph_observations_only", graph_docs),
            ("without_graph_observations", [d for d in state["observations"] if d["sha256"] not in graph_hashes]),
        ):
            eligible = groups({**state, "observations": docs})
            pair_counts[label] = [{"key": list(k), "rows": len(rows),
                                  "source_count": len({r["source"] for r in rows})}
                                 for k, rows in eligible]
        diagnostic = {
            "graph_documents": len(graph_docs), "graph_source_identities": len(graph_sources),
            "graph_records_by_path": dict(Counter(r["path"] for d in graph_docs for r in d["records"])),
            "minimum_error_sources": CONFIG["minimum_error_sources"],
            "eligible_pairs": pair_counts,
            "meaning": "eligibility diagnostics; not a mechanism ablation or evidence of improvement",
        }
        write_json(output / "diagnostics.json", diagnostic)
        write_json(output / "before.json", before)
        write_json(output / "replay.json", {"status": "PASS", "head": before["head"],
                   "events": before["events"], "seconds": replay_seconds,
                   "verification": "Kernel constructor full deterministic semantic replay"})
        emit(stage="parent_verified", generation=before["active_generation"],
             graph_eligible_pairs=len(pair_counts["graph_observations_only"]))
        actions = []
        for _ in range(max_steps):
            action = kernel.step()
            actions.append(action)
            write_json(output / "actions.json", actions)
            emit(stage="native_step", status=action["status"], reason=action["reason"])
            if action["status"] in protocol["stop_on"]:
                break
        regression = full_regression(kernel)
        write_json(output / "regression.json", regression)
        after = kernel.status()
        events, head = kernel.journal.read()
        if events[:len(parent["events"])] != parent["events"]:
            raise ContractError("probe changed the inherited journal")
        delta = events[len(parent["events"]):]
        if any(e["kind"] in ("tasks", "knowledge", "runtime_upgrade", "engine_trial", "observation") for e in delta):
            raise ContractError("probe injected an external task, solution or observation")
        if runtime_manifest() != frozen_runtime:
            raise ContractError("runtime changed after protocol freeze")
        goal = next((a["goal"] for a in actions if a.get("phase") == "GOAL_FROZEN"), None)
        candidate = next((a for a in actions if a.get("phase") == "CANDIDATE_FROZEN"), None)
        attributable = bool(goal and graph_sources.intersection(goal.get("evidence_sources", [])))
        status = "AWAITING_FRESH_BLIND" if candidate else "WITHHOLD"
        if regression["passed"] != regression["total"]:
            status = "FAIL_REGRESSION"
        summary = {
            "schema": "nova.codeflow-goal-probe-result.v1", "status": status,
            "completed_at": now(), "protocol_sha256": digest(protocol),
            "parent_head": parent["head"], "head": head,
            "active_generation": after["active_generation"], "new_admissions": after["admissions_total"] - before["admissions_total"],
            "new_journal_events": len(delta), "operator_tasks": 0, "operator_programs": 0,
            "native_goal_found": goal is not None, "goal_uses_graph_source": attributable,
            "candidate_frozen": candidate is not None,
            "last_native_status": actions[-1]["status"], "last_native_reason": actions[-1]["reason"],
            "fresh_blind": "NOT_RUN", "fresh_rows": 0, "mechanism_ablation": "NOT_RUN",
            "admission": "NOT_REACHED", "g23": "NOT_REACHED",
            "regression": {k: regression[k] for k in ("passed", "total", "skills")},
            "graph_eligible_pairs": len(pair_counts["graph_observations_only"]),
            "graph_source_identities": len(graph_sources), "required_error_sources": CONFIG["minimum_error_sources"],
            "runtime_unchanged": True, "parent_prefix_unchanged": True,
            "claim": "task-free native goal probe, not proof of new capability or autonomous graph reasoning",
        }
        write_json(output / "after.json", after)
        write_json(output / "summary.json", summary)
        if delta:
            exported = {"schema": "nova.journal.export.v1", "events": events, "head": head}
            (output / "journal.json.gz").write_bytes(gzip.compress(encode(exported).encode(), mtime=0))
        emit(stage="result", **summary)
    # WITHHOLD is an observed experimental outcome, not a process failure.
    return 1 if summary["status"] == "FAIL_REGRESSION" else 0


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--max-steps", type=int, default=8)
    args = parser.parse_args()
    raise SystemExit(run(args.output.resolve(), args.max_steps))

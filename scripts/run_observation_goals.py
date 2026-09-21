"""Frozen full-document observation experiment; the broker supplies no tasks."""

import argparse
from concurrent.futures import ThreadPoolExecutor
import json
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from nova_core.contracts import ContractError, digest, encode
from nova_core.kernel import Kernel, runtime_manifest
from nova_core.memory import Journal
from run_development_chain import restore, write_json
from run_unlabelled_stream import fetch, full_regression, now


def emit(**fields):
    print(json.dumps(fields, ensure_ascii=False), flush=True)


def run(output, state_path, freeze_commit, parent_state=None):
    protocol = json.loads((output / "protocol.json").read_text())
    sources = json.loads((output / "sources.json").read_text())
    for name in protocol["frozen_files"]:
        if subprocess.check_output(["git", "show", freeze_commit + ":" + name], cwd=ROOT) != (ROOT / name).read_bytes():
            raise ContractError("frozen file changed: " + name)
    if digest(runtime_manifest()) != protocol["runtime_sha256"]:
        raise ContractError("runtime changed after freeze")
    if state_path.exists() or (output / "receipts.json").exists():
        raise ContractError("state or experiment already exists; never silently repeat a run")
    parent = json.loads((ROOT / protocol["parent_journal"]).read_text())
    if parent["head"] != protocol["parent_head"]:
        raise ContractError("parent journal changed")
    write_json(output / "code-freeze.json", {"commit": freeze_commit, "recorded_at": now(),
               "runtime_sha256": digest(runtime_manifest()), "protocol_sha256": digest(protocol)})
    if parent_state:
        journal = Journal(parent_state)
        try:
            events, head = journal.read()
            if head != parent["head"] or encode(events) != encode(parent["events"]):
                raise ContractError("parent SQLite state does not match published history")
            journal.backup(state_path)
        finally:
            journal.close()
    else:
        restore(parent, state_path)
    # Publish the experiment's fixed provenance before issuing network requests.
    (output / "sources").mkdir(exist_ok=True)
    with ThreadPoolExecutor(max_workers=3) as executor:
        responses = list(executor.map(lambda item: fetch(item, output, protocol["transport"]), sources))
    receipts = [{k: v for k, v in response.items() if k != "text"} for response in responses]
    write_json(output / "receipts.json", receipts)
    with Kernel(state_path) as kernel:
        emit(stage="parent_verified", generation=kernel.status()["active_generation"])
        upgrade = kernel.upgrade()
        write_json(output / "upgrade.json", upgrade)
        baseline = kernel.step()
        write_json(output / "baseline.json", baseline)
        ingestion = []
        for response in responses:
            if response["status"] != "FETCHED":
                ingestion.append({"id": response["id"], "status": "TRANSPORT_FAILED"})
                continue
            # Exact decoded response, no fields, goals, excerpts or answers chosen by the broker.
            raw = {"source": response["url"], "media_type": response["content_type"],
                   "text": response["text"], "sha256": response["sha256"], "obtained_at": response["completed_at"]}
            try:
                result = kernel.observe(raw)
            except ContractError as exc:
                result = {"status": "REJECTED", "reason": str(exc)}
            ingestion.append({"id": response["id"], **result})
            emit(stage="ingress", **ingestion[-1])
        write_json(output / "ingestion.json", ingestion)
        actions = []
        for _ in range(protocol["max_steps"]):
            action = kernel.step()
            actions.append(action)
            write_json(output / "actions.json", actions)
            emit(stage="native_step", status=action["status"], reason=action["reason"])
            if action["status"] in ("IDLE", "WAITING", "WITHHOLD", "FROZEN"):
                break
        regression = full_regression(kernel)
        write_json(output / "regression.json", regression)
        events, head = kernel.journal.read()
        if encode(events[:len(parent["events"])]) != encode(parent["events"]):
            raise ContractError("the parent history was modified")
        export = {"schema": "nova.journal.export.v1", "head": head, "events": events}
        write_json(output / "journal.json", export)
        status = kernel.status()
        write_json(output / "status.json", status)
        goal = next((a["goal"] for a in actions if a.get("phase") == "GOAL_FROZEN"), None)
        summary = {"completed_at": now(), "parent_head": parent["head"], "head": head,
            "runtime_version": "0.7.0", "active_generation": status["active_generation"],
            "goal_found": goal is not None, "goal_id": goal["id"] if goal else None,
            "observation_contract": goal["observation_contract"] if goal else None,
            "last_outcome": actions[-1]["status"], "last_reason": actions[-1]["reason"],
            "operator_task_events": sum(e["kind"] == "tasks" for e in events[len(parent["events"]):]),
            "operator_answer_labels": 0, "fresh_evaluation_performed": False,
            "capability_improvement_proven": False, "unrestricted_autonomy_proven": False,
            "regression": {k: regression[k] for k in ("passed", "total", "skills")},
            "observations": status["observations"],
            "boundary": "maintainer-added observation/goal ontology; native goal selection and synthesis; retrieval may repeat historical source records"}
        write_json(output / "run-summary.json", summary)
        emit(stage="result", **summary)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--experiment", type=Path, required=True)
    parser.add_argument("--state", type=Path, required=True)
    parser.add_argument("--freeze-commit", required=True)
    parser.add_argument("--parent-state", type=Path)
    args = parser.parse_args()
    run(args.experiment.resolve(), args.state.resolve(), args.freeze_commit, args.parent_state)

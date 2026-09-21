"""Continue the real G22 journal with active UCR proposals, without new tasks.

No fresh examples are supplied by this protocol. A discovered candidate stays
frozen awaiting external evaluation; exhausted searches remain in the journal.
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

from nova_core.contracts import digest
from nova_core.evaluation import score
from nova_core.kernel import Kernel, context, runtime_manifest
from nova_core.synthesis import synthesize
from scripts.run_development_chain import restore


def write(path, value):
    path.write_text(json.dumps(value, ensure_ascii=True, allow_nan=False, sort_keys=True, indent=2) + "\n")


def run(parent_path, output):
    output.mkdir(parents=True, exist_ok=False)
    raw = parent_path.read_bytes()
    parent = json.loads(gzip.decompress(raw) if parent_path.suffix == ".gz" else raw)
    state_path = output / "state.sqlite"
    print(json.dumps({"phase": "restore_and_verify_parent", "events": len(parent["events"])}), flush=True)
    restore(parent, state_path)
    manifest = runtime_manifest()
    protocol = {"schema": "nova.ucr-development-protocol.v1", "author": "maintainer",
                "parent_path": str(parent_path.relative_to(ROOT)),
                "parent_file_sha256": hashlib.sha256(raw).hexdigest(), "parent_head": parent["head"],
                "runtime_manifest": manifest, "runtime_sha256": digest(manifest),
                "max_steps": 3, "new_observations": 0, "new_registered_tasks": 0, "fresh_rows": 0,
                "control": "native_search_on_the_same_frozen_training_and_parent_memory",
                "stop": "first completed or frozen search; never supply invented fresh evaluations"}
    write(output / "protocol.json", protocol)
    print(json.dumps({"phase": "open_verified_parent_and_upgrade"}), flush=True)
    with Kernel(state_path) as kernel:
        before = kernel.status()
        upgrade = kernel.upgrade()
        print(json.dumps({"phase": "runtime_upgrade", "status": upgrade["status"]}), flush=True)
        actions = []
        selected = None
        for _ in range(protocol["max_steps"]):
            action = kernel.step()
            actions.append(action)
            if action.get("phase") == "GOAL_FROZEN":
                selected = action["goal"]
            print(json.dumps({"status": action["status"], "reason": action.get("reason"),
                              "ucr": action.get("report", {}).get("ucr", {}).get("status")}), flush=True)
            if action["status"] in ("IDLE", "WAITING", "FROZEN", "WITHHOLD"):
                break
        snapshot, _, _ = kernel._load()
        active, memory, _ = context(snapshot)
        control = (synthesize(selected["training"], memory, snapshot["genomes"][snapshot["current"]].get("engine"))
                   if selected else {"status": "NO_GOAL"})
        regression = {tid: score(memory[pid], snapshot["tasks"][tid]["train"] + snapshot["tasks"][tid]["holdout"], memory)
                      for tid, pid in sorted(active.items())}
        after = kernel.status()
        events, head = kernel.journal.read()
        if events[:len(parent["events"])] != parent["events"]:
            raise ValueError("parent history changed")
        (output / "journal.json.gz").write_bytes(gzip.compress(json.dumps(
            {"schema": "nova.journal.export.v1", "head": head, "events": events}, ensure_ascii=True).encode(), mtime=0))
        write(output / "upgrade.json", upgrade)
        write(output / "actions.json", actions)
        write(output / "native-control.json", control)
        write(output / "regression.json", regression)

    print(json.dumps({"phase": "separate_process_replay", "events": len(events)}), flush=True)
    process = subprocess.run([sys.executable, "-m", "nova_core", "--state", str(state_path.resolve()),
                              "verify", "--expected-head", head], cwd=ROOT, capture_output=True, text=True, timeout=180)
    (output / "restart-stdout.json").write_text(process.stdout)
    (output / "restart-stderr.txt").write_text(process.stderr)
    replay = json.loads(process.stdout) if process.returncode == 0 else {}
    reports = [a["report"]["ucr"] for a in actions if "ucr" in a.get("report", {})]
    delta = events[len(parent["events"]):]
    passed, total = sum(r["passed"] for r in regression.values()), sum(r["total"] for r in regression.values())
    summary = {"schema": "nova.ucr-development-run.v1", "before": before, "after": after,
               "protocol_sha256": digest(protocol), "parent_prefix_unchanged": True,
               "ucr_used_by_kernel": bool(reports), "ucr_reports": reports,
               "native_control_found_program": control.get("program") is not None,
               "native_control_attempts": control.get("attempts"),
               "new_task_events": sum(e["kind"] == "tasks" for e in delta),
               "new_admissions": after["admissions_total"] - before["admissions_total"],
               "regression": {"passed": passed, "total": total, "skills": len(regression)},
               "cold_replay": {"status": replay.get("status", "ERROR"), "exit_code": process.returncode,
                               "events": len(events), "head": head},
               "status": "PASS_ACTIVE_INTEGRATION" if reports and passed == total and process.returncode == 0 else "FAIL",
               "limitations": ["this protocol supplies no new independent evaluation data",
                   "UCR proposes compositions of maintainer-defined Nova primitives",
                   "goal selection retains v7's bounded field-pair ranking",
                   "a passing integration does not prove a new capability or autonomous source rewriting"]}
    write(output / "summary.json", summary)
    print(json.dumps({k: summary[k] for k in ("status", "ucr_used_by_kernel", "new_admissions", "regression", "cold_replay")}), flush=True)
    return 0 if summary["status"] == "PASS_ACTIVE_INTEGRATION" else 1


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--parent", type=Path, default=ROOT / "experience/ucr-v16-integration/journal.json.gz")
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    return run(args.parent.resolve(), args.output.resolve())


if __name__ == "__main__":
    raise SystemExit(main())

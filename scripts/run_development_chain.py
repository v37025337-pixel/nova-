"""Run a pre-registered corpus on the unchanged NOVA runtime and retain evidence."""

import argparse
import json
import subprocess
import sys
import tempfile
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from nova_core.contracts import ContractError, decode, digest, encode, equal
from nova_core.kernel import Kernel, context, runtime_manifest
from nova_core.language import execute
from nova_core.memory import Journal, ZERO
from nova_core.synthesis import ERRORS


def write_json(path, value):
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2) + "\n", encoding="utf-8")
    temporary.replace(path)


def restore(parent, destination):
    """Validate a complete exported history before publishing a new SQLite state."""
    if destination.exists():
        raise ContractError("restore destination already exists")
    if set(parent) != {"schema", "head", "events"} or parent["schema"] != "nova.journal.export.v1":
        raise ContractError("unsupported journal export")
    destination.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(dir=destination.parent, prefix="nova-restore-") as temporary:
        staged = Path(temporary) / "state.sqlite"
        journal = Journal(staged, create=True)
        try:
            head = ZERO
            for event in parent["events"]:
                head = journal.append(event, head)
            if head != parent["head"]:
                raise ContractError("export does not match its anchored head")
        finally:
            journal.close()
        with Kernel(staged) as verified:
            verified.audit(expected_head=parent["head"])
            verified.journal.backup(destination)


def run(directory, state_path, protocol_commit, output_directory=None):
    output_directory = output_directory or directory
    output_directory.mkdir(parents=True, exist_ok=True)
    summary_path = output_directory / "run-summary.json"
    if summary_path.exists():
        raise ContractError("run summary already exists; use --output with a new directory")
    protocol = decode((directory / "protocol.json").read_text())
    corpus = decode((directory / "corpus.json").read_text())
    queries = decode((directory / "queries.json").read_text())
    parent = decode((ROOT / protocol["parent_journal"]).read_text())
    if digest(corpus) != protocol["corpus_sha256"] or digest(queries) != protocol["queries_sha256"]:
        raise ContractError("frozen corpus/query digest mismatch")
    sources = {"nova_core/" + k: v for k, v in runtime_manifest()["sources"].items()}
    if digest(sources) != protocol["runtime_manifest_sha256"]:
        raise ContractError("runtime changed after protocol registration")
    if parent["head"] != protocol["parent_head"]:
        raise ContractError("parent checkpoint changed")
    # Verify pre-registration against the actual committed Git objects.
    for filename in ("protocol.json", "corpus.json", "queries.json", "sources.json"):
        relative = str((directory / filename).relative_to(ROOT))
        frozen = subprocess.check_output(["git", "show", protocol_commit + ":" + relative], cwd=ROOT)
        if frozen != (directory / filename).read_bytes():
            raise ContractError("input differs from the pre-registered commit: " + filename)
    if not state_path.exists():
        restore(parent, state_path)
    started = time.perf_counter()
    timings = []
    query_results = []
    parent_count = len(parent["events"])
    positive = protocol["positive_task_ids"]
    with Kernel(state_path) as kernel:
        events, _ = kernel.journal.read()
        if encode(events[:parent_count]) != encode(parent["events"]):
            raise ContractError("state is not a continuation of the pinned parent")
        kernel.register(corpus)
        events, _ = kernel.journal.read()
        steps = [e for e in events[parent_count:] if e["kind"] == "step"]
        if any(e["selection"]["task"] not in positive + [protocol["negative_control"]] for e in steps):
            raise ContractError("state contains unrelated development attempts")
        for _ in range(protocol["max_steps"] - len(steps)):
            before = time.perf_counter()
            record = kernel.step()
            timings.append({"task": record.get("selection", {}).get("task"),
                            "seconds": time.perf_counter() - before})
            print(json.dumps({"task": record.get("selection", {}).get("task"),
                              "status": record["status"], "reason": record["reason"],
                              "generation": record.get("generation"),
                              "search_attempts": record.get("synthesis", {}).get("attempts")}), flush=True)
            if record["status"] == "IDLE":
                break
            steps.append(record)
            write_json(output_directory / "steps.json", steps)
            if record["status"] == "ADMITTED":
                (output_directory / "genes").mkdir(exist_ok=True)
                (output_directory / "genes" / ("g" + str(record["generation"]) + ".py")).write_text(
                    record["program"]["source"], encoding="utf-8")
        # One verified snapshot for all query executions; queries never enter synthesis.
        snapshot, final_head, _ = kernel._load()
        active, memory, _ = context(snapshot)
        for query in queries:
            row = {"task": query["task"], "source": query["source"], "input": query["input"],
                   "expected": query["expected"]}
            try:
                if query["task"] not in active:
                    raise ContractError("task has no admitted program")
                output = execute(memory[active[query["task"]]], query["input"], memory)
                row.update(output=output, passed=equal(output, query["expected"]))
            except ERRORS as exc:
                row.update(passed=False, error=type(exc).__name__)
            query_results.append(row)
        events, observed_head = kernel.journal.read()
        if observed_head != final_head:
            raise ContractError("state changed during query verification")
        exported = {"schema": "nova.journal.export.v1", "head": final_head, "events": events}
        write_json(output_directory / "journal.json", exported)
        write_json(output_directory / "query-results.json", query_results)
        write_json(output_directory / "genome.json", snapshot["genomes"][snapshot["current"]])
        write_json(output_directory / "causal-memory.json", {"schema": "nova.causal-memory.v1",
                   "experiences": snapshot["experience"], "task_events": snapshot["task_events"],
                   "gene_events": snapshot["gene_events"]})
        backup = state_path.with_name(state_path.stem + "-backup.sqlite")
        if backup.exists():
            raise ContractError("backup already exists; do not overwrite it")
        kernel.journal.backup(backup)
    # Restart and semantic replay of an online backup in a separate Python process.
    print(json.dumps({"phase": "separate_process_restart_and_replay"}), flush=True)
    replay_started = time.perf_counter()
    command = [sys.executable, "-m", "nova_core", "--state", str(backup), "verify", "--expected-head", final_head]
    replay = subprocess.run(command, cwd=ROOT, text=True, capture_output=True, timeout=180)
    (output_directory / "restart-stdout.json").write_text(replay.stdout)
    (output_directory / "restart-stderr.txt").write_text(replay.stderr)
    restarted = decode(replay.stdout) if replay.returncode == 0 else None
    admitted = [s for s in steps if s["status"] == "ADMITTED"]
    lineage = [{"from": a["generation"], "to": b["generation"],
                "previous_program_used": a["program"]["id"] in b["program"]["parents"],
                "genome_parent_matches": b["mutation"]["parent_genome"] == a["mutation"]["child_genome"]["id"]}
               for a, b in zip(admitted, admitted[1:])]
    negative = [s for s in steps if s["selection"]["task"] == protocol["negative_control"]]
    target_met = (len(admitted) == len(positive)
                  and [s["selection"]["task"] for s in admitted] == positive
                  and all(r["previous_program_used"] and r["genome_parent_matches"] for r in lineage)
                  and all(q["passed"] for q in query_results)
                  and bool(negative) and negative[0]["status"] == "WITHHOLD"
                  and replay.returncode == 0 and restarted["head"] == final_head)
    summary = {"schema": "nova.development-run.v1", "status": "PASS" if target_met else "WITHHOLD",
               "protocol_commit": protocol_commit, "protocol_sha256": digest(protocol),
               "engine_commit": protocol["engine_commit"], "runtime_changed": False,
               "parent_generation": protocol["parent_generation"],
               "active_generation": snapshot["current"], "new_admissions": len(admitted),
               "new_attempts": len(steps), "lineage": lineage,
               "stages": [{"task": s["selection"]["task"], "status": s["status"], "reason": s["reason"],
                           "generation": s["generation"], "program": s["program"]["id"] if s["program"] else None,
                           "parents": s["program"]["parents"] if s["program"] else [],
                           "holdout": {"passed": s["gate"]["holdout"]["passed"], "total": s["gate"]["holdout"]["total"]} if s["gate"] else None,
                           "search_attempts": s["synthesis"]["attempts"]} for s in steps],
               "new_queries": {"passed": sum(r["passed"] for r in query_results), "total": len(query_results),
                               "source_repositories": len(set(r["source"] for r in query_results))},
               "journal_head": final_head, "events": len(events),
               "restart_and_backup_replay": {"returncode": replay.returncode,
                    "status": restarted["status"] if restarted else "ERROR",
                    "seconds": time.perf_counter() - replay_started},
               "timings": timings, "total_seconds": time.perf_counter() - started,
               "limitations": protocol["claims"] + ["task goals and reference outputs are maintainer-authored",
                    "native programs are selected by the unchanged runtime without LLM candidate generation",
                    "this run does not implement host-engine self-rewrite or prove consciousness"]}
    write_json(summary_path, summary)
    print(json.dumps({"status": summary["status"], "active_generation": summary["active_generation"],
                      "admissions": len(admitted), "queries": summary["new_queries"],
                      "restart": summary["restart_and_backup_replay"], "seconds": summary["total_seconds"]}), flush=True)
    return summary


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--experiment", type=Path, default=ROOT / "experience/development-chain-v1")
    parser.add_argument("--state", type=Path, default=ROOT / "state/development-chain-v1.sqlite")
    parser.add_argument("--protocol-commit")
    parser.add_argument("--output", type=Path, help="new directory for a repeat run's results")
    parser.add_argument("--restore", type=Path, help="restore an anchored journal instead of running a new experiment")
    args = parser.parse_args()
    if args.restore:
        checkpoint = decode(args.restore.read_text())
        restore(checkpoint, args.state.resolve())
        print(json.dumps({"status": "RESTORED", "head": checkpoint["head"]}))
    else:
        if not args.protocol_commit:
            parser.error("--protocol-commit is required when running an experiment")
        run(args.experiment.resolve(), args.state.resolve(), args.protocol_commit,
            args.output.resolve() if args.output else None)

"""Execute one frozen, bounded engine evolution and its subsequent learning chain."""

import argparse
import json
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from nova_core.adaptation import compatible, input_tokens
from nova_core.contracts import ContractError, decode, digest, encode, equal
from nova_core.kernel import Kernel, context, runtime_manifest
from nova_core.language import execute
from nova_core.synthesis import ERRORS, synthesize
from scripts.run_development_chain import restore, write_json


def query_rows(kernel, queries):
    state, _, _ = kernel._load()
    active, memory, _ = context(state)
    results = []
    for query in queries:
        try:
            output = execute(memory[active[query["task"]]], query["input"], memory)
            results.append({**query, "output": output, "passed": equal(output, query["expected"])})
        except ERRORS as exc:
            results.append({**query, "passed": False, "error": type(exc).__name__})
    return results


def run(directory, state_path, protocol_commit, output):
    if state_path.exists() or (output / "run-summary.json").exists():
        raise ContractError("use a new state path and output directory for a new run")
    protocol = decode((directory / "protocol.json").read_text())
    trial = decode((directory / "trial.json").read_text())
    corpus = decode((directory / "corpus.json").read_text())
    queries = decode((directory / "queries.json").read_text())
    for name, value in (("trial", trial), ("corpus", corpus), ("queries", queries)):
        if digest(value) != protocol[name + "_sha256"]:
            raise ContractError("frozen input changed: " + name)
    if list(sys.version_info[:2]) != protocol["python"] or digest(runtime_manifest()["sources"]) != protocol["runtime_sources_sha256"]:
        raise ContractError("runtime or Python differs from the frozen protocol")
    for name in ("protocol.json", "trial.json", "corpus.json", "queries.json"):
        relative = str((directory / name).relative_to(ROOT))
        frozen = subprocess.check_output(["git", "show", protocol_commit + ":" + relative], cwd=ROOT)
        if frozen != (directory / name).read_bytes():
            raise ContractError("input differs from pre-registration: " + name)
    parent = decode((ROOT / protocol["parent_journal"]).read_text())
    if parent["head"] != protocol["parent_head"]:
        raise ContractError("parent checkpoint changed")
    used = input_tokens(trial["tasks"] + corpus)
    if any(digest(q["input"]) in used for q in queries):
        raise ContractError("post-training query overlaps training or validation")
    output.mkdir(parents=True, exist_ok=True)
    restore(parent, state_path)
    started = time.perf_counter()
    steps, timings = [], []
    old_queries = decode((ROOT / "experience/development-chain-v1/queries.json").read_text())
    with Kernel(state_path) as kernel:
        state, _, _ = kernel._load()
        if state["current"] != protocol["parent_generation"]:
            raise ContractError("unexpected parent generation")
        _, memory, _ = context(state)
        probe = synthesize(corpus[0]["train"], compatible(memory, corpus[0]["train"]))
        write_json(output / "parent-search-probe.json", {"task": corpus[0]["id"], "data": "training_only", **probe})
        write_json(output / "upgrade.json", kernel.upgrade())
        kernel.register_engine_trial(trial)
        kernel.register(corpus)
        for _ in range(protocol["max_steps"]):
            before = time.perf_counter()
            step = kernel.step()
            timings.append({"task": step.get("selection", {}).get("task"), "seconds": time.perf_counter() - before})
            print(json.dumps({"task": step.get("selection", {}).get("task"), "status": step["status"],
                              "reason": step["reason"], "generation": step.get("generation"),
                              "attempts": step.get("synthesis", {}).get("attempts")}), flush=True)
            if step["status"] == "IDLE":
                break
            steps.append(step)
            write_json(output / "steps.json", steps)
            if step.get("domain") == "ENGINE" and step["status"] != "ADMITTED":
                break
        new_results = query_rows(kernel, queries)
        old_results = query_rows(kernel, old_queries)
        write_json(output / "query-results.json", {"new": new_results, "inherited": old_results})
        audit = kernel.audit()
        write_json(output / "audit.json", audit)
        events, head = kernel.journal.read()
        if encode(events[:len(parent["events"])]) != encode(parent["events"]):
            raise ContractError("original history prefix was not preserved")
        write_json(output / "journal.json", {"schema": "nova.journal.export.v1", "head": head, "events": events})
        write_json(output / "genome.json", kernel.genome())
        write_json(output / "causal-memory.json", kernel.causal_memory())
        genes = output / "genes"
        genes.mkdir(exist_ok=True)
        for step in steps:
            if step["status"] == "ADMITTED" and step["program"] is not None:
                (genes / ("g" + str(step["generation"]) + ".py")).write_text(step["program"]["source"], encoding="utf-8")
            if step.get("domain") == "ENGINE":
                write_json(output / "engine-policy.json", step["engine_candidate"])
        backup = state_path.with_name(state_path.stem + "-backup.sqlite")
        rollback_path = state_path.with_name(state_path.stem + "-rollback.sqlite")
        kernel.journal.backup(backup)
        kernel.journal.backup(rollback_path)
    restart_started = time.perf_counter()
    restart = subprocess.run([sys.executable, "-m", "nova_core", "--state", str(backup), "verify", "--expected-head", head],
                             cwd=ROOT, capture_output=True, text=True, timeout=180)
    (output / "restart-stdout.json").write_text(restart.stdout, encoding="utf-8")
    (output / "restart-stderr.txt").write_text(restart.stderr, encoding="utf-8")
    restart_seconds = time.perf_counter() - restart_started
    with Kernel(rollback_path) as reverted:
        reverted.rollback(protocol["parent_generation"])
        rollback_audit = reverted.audit()
        rollback_queries = query_rows(reverted, old_queries)
        rollback_events, rollback_head = reverted.journal.read()
        write_json(output / "rollback-receipt.json", {"audit": rollback_audit, "queries": rollback_queries,
                                                       "event": rollback_events[-1], "head": rollback_head})
    engine = next((s for s in steps if s.get("domain") == "ENGINE"), None)
    programs = [s for s in steps if s.get("domain") != "ENGINE" and s["status"] == "ADMITTED"]
    links = [{"parent": first["generation"], "child": second["generation"],
              "used_previous_program": first["program"]["id"] in second["program"]["parents"]}
             for first, second in zip(programs, programs[1:])]
    control = next((s for s in steps if s["selection"]["task"] == protocol["negative_task"]), None)
    checks = {"engine_admitted": engine is not None and engine["status"] == "ADMITTED",
              "old_search_cannot_solve_first_new_task": probe["program"] is None,
              "ordered_program_admissions": [s["selection"]["task"] for s in programs] == protocol["positive_tasks"],
              "previous_program_reuse": len(links) == 2 and all(link["used_previous_program"] for link in links),
              "fresh_queries": all(q["passed"] for q in new_results),
              "inherited_queries": all(q["passed"] for q in old_results),
              "unsupported_hash_withheld": control is not None and control["reason"] == "SEARCH_EXHAUSTED" and control["program"] is None,
              "cold_restart": restart.returncode == 0 and decode(restart.stdout)["head"] == head,
              "rollback": rollback_audit["active_generation"] == protocol["parent_generation"] and rollback_audit["engine_policy"] is None and all(q["passed"] for q in rollback_queries),
              "final_generation": audit["active_generation"] == protocol["expected_final_generation"]}
    summary = {"status": "PASS" if all(checks.values()) else "WITHHOLD", "checks": checks,
               "protocol_commit": protocol_commit, "parent_head": parent["head"], "head": head,
               "generation": audit["active_generation"], "events": audit["events"], "links": links,
               "new_queries": {"passed": sum(q["passed"] for q in new_results), "total": len(new_results)},
               "inherited_queries": {"passed": sum(q["passed"] for q in old_results), "total": len(old_results)},
               "engine_training": engine["gate"]["training"] if engine else None,
               "timings": timings, "cold_restart_seconds": restart_seconds,
               "cycle_seconds": time.perf_counter() - started, "claim_boundary": protocol["claim_boundary"]}
    write_json(output / "run-summary.json", summary)
    print(json.dumps({"status": summary["status"], "checks": checks, "generation": summary["generation"], "head": head}), flush=True)
    return 0 if summary["status"] == "PASS" else 2


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--state", type=Path, required=True)
    parser.add_argument("--protocol-commit", required=True)
    parser.add_argument("--experiment", type=Path, default=ROOT / "experience/engine-cycle-v2")
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    try:
        return run(args.experiment.resolve(), args.state.resolve(), args.protocol_commit,
                   (args.output or args.experiment).resolve())
    except (ContractError, OSError, subprocess.SubprocessError) as exc:
        print(json.dumps({"status": "ERROR", "error": str(exc)}), file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())

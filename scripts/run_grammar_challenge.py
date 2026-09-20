"""Probe the native entry into grammar evolution on a pinned, unchanged kernel.

This is an observer of the first necessary gate, not a replacement primitive
generator or a complete sandbox/admission implementation. An idle/program/policy
result cannot earn grammar-evolution PASS. Later gates require a separate real
implementation and remain NOT_REACHED here; no synthetic receipts fill them in.
"""

import argparse
import copy
import json
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from nova_core.contracts import ContractError, IntegrityError, decode, digest, encode
from nova_core.evaluation import score
from nova_core.kernel import Kernel, context, runtime_manifest
from nova_core.language import BINARY, LANGUAGE, UNARY, candidate
from nova_core.memory import Journal
from nova_core.synthesis import check_policy
from scripts.run_development_chain import restore, write_json

GATES = (
    "native_deficit_selection", "native_missing_primitive_diagnosis",
    "native_primitive_implementation", "candidate_compile", "candidate_sandbox",
    "fresh_hidden_holdout", "candidate_full_regression", "causal_ablation",
    "genome_admission", "post_admission_restart", "post_admission_replay",
    "native_next_goal_selection")


def classify_result(step):
    if step.get("status") == "IDLE":
        return "IDLE"
    if step.get("domain") == "ENGINE":
        return "ENGINE_POLICY"
    if (step.get("program") or {}).get("language") == LANGUAGE:
        return "FIXED_GRAMMAR_PROGRAM"
    if step.get("status") == "WITHHOLD" and step.get("program") is None:
        return "NO_PROGRAM"
    return "UNRECOGNIZED_RESULT"


def grammar_boundary_probes(policy=None):
    """External negative contract tests; no proposal is registered or executed."""
    from nova_core.adaptation import derive_policy
    baseline = copy.deepcopy(policy) if policy else derive_policy({})[0]
    expanded = copy.deepcopy(baseline)
    expanded["unary"].append("probe_new_primitive")
    expanded["id"] = digest({k: v for k, v in expanded.items() if k != "id"})
    results = {"author": "external_verifier", "unary": list(UNARY), "binary": list(BINARY)}
    operations = {
        "new_expression_operation": lambda: candidate(["call", "probe_new_primitive", ["input", "x"]], {}),
        "expanded_policy_operator_set": lambda: check_policy(expanded)}
    for name, operation in operations.items():
        try:
            operation()
            results[name] = {"rejected": False}
        except ContractError as exc:
            results[name] = {"rejected": True, "error": type(exc).__name__, "message": str(exc)}
    return results


def observe(kernel, expected_head):
    before = kernel.status()
    if before["head"] != expected_head:
        raise IntegrityError("challenge parent head mismatch")
    queue = kernel.queue()
    memory = kernel.causal_memory()
    unresolved = {}
    for item in queue:
        history = memory["experiences"].get(item["task"], [])
        if item["status"] != "ADMITTED" and history and history[-1]["reason"] == "SEARCH_EXHAUSTED":
            unresolved[item["task"]] = {"queue_status": item["status"], "history": history}
    # No task id, source, implementation, forced retry, policy or answer is
    # supplied to the kernel. Selection must originate in its actual controller.
    native = kernel.develop(1)
    step = native["steps"][0]
    selected = step.get("selection", {}).get("task")
    selected_deficit = selected in unresolved
    first_unmet = GATES[1] if selected_deficit else GATES[0]
    gates = [{"gate": name, "status": "PASS" if name == GATES[0] and selected_deficit else
              "BLOCKED" if name == first_unmet else "NOT_REACHED"} for name in GATES]
    after = kernel.status()
    state, _, _ = kernel._load()
    active, executable, _ = context(state)
    regression = {tid: score(executable[pid], state["tasks"][tid]["train"] + state["tasks"][tid]["holdout"], executable)
                  for tid, pid in sorted(active.items())}
    return {"schema": "nova.grammar-entry-observation.v1", "evolution_verdict": "WITHHOLD",
            "scope": "native_entry_probe_on_unchanged_runtime", "complete_capability_pipeline_implemented": False,
            "first_unmet_gate": first_unmet, "gates": gates, "before": before, "after": after,
            "queue_before": queue, "unresolved_deficits_observed_externally": unresolved,
            "native_result": native, "native_result_type": classify_result(step), "native_selected_task": selected,
            "native_diagnosis": None, "native_primitive_candidates": [],
            "candidate_compile_invocations": 0, "candidate_sandbox_invocations": 0,
            "hidden_holdout": {"status": "NOT_CREATED_NO_ELIGIBLE_CANDIDATE", "evaluated_cases": 0},
            "external_contract_probes": grammar_boundary_probes(before["engine_policy"]),
            "baseline_regression": regression,
            "baseline_preserved": before["head"] == after["head"] and before["genome"] == after["genome"],
            "external_intervention": {"new_tasks_registered": 0, "retries_forced": 0,
                                      "source_candidates_supplied": 0, "runtime_files_modified": 0}}


def run(protocol_path, state_path, output, protocol_commit):
    if state_path.exists() or output.exists():
        raise ContractError("challenge state and output must be new paths")
    protocol = decode(protocol_path.read_text(encoding="utf-8"))
    for relative in (str(protocol_path.relative_to(ROOT)), "scripts/run_grammar_challenge.py"):
        frozen = subprocess.check_output(["git", "show", protocol_commit + ":" + relative], cwd=ROOT)
        if frozen != (ROOT / relative).read_bytes():
            raise ContractError("changed since pre-registration: " + relative)
    if list(sys.version_info[:2]) != protocol["python"] or digest(runtime_manifest()["sources"]) != protocol["runtime_sources_sha256"]:
        raise ContractError("runtime or Python changed since pre-registration")
    if list(GATES) != protocol["required_gates"]:
        raise ContractError("gate sequence differs from pre-registration")
    parent = decode((ROOT / protocol["parent_journal"]).read_text(encoding="utf-8"))
    if parent["head"] != protocol["parent_head"]:
        raise IntegrityError("parent export anchor changed")
    started = time.perf_counter()
    restore(parent, state_path)
    output.mkdir(parents=True)
    process = subprocess.run([sys.executable, str(Path(__file__).resolve()), "observe",
                              "--state", str(state_path), "--expected-head", parent["head"]],
                             cwd=ROOT, capture_output=True, text=True, timeout=180)
    (output / "observer-stdout.json").write_text(process.stdout, encoding="utf-8")
    (output / "observer-stderr.txt").write_text(process.stderr, encoding="utf-8")
    if process.returncode != 0:
        raise ContractError("native entry observation failed; see observer stderr")
    observation = decode(process.stdout)
    journal = Journal(state_path)
    try:
        events, head = journal.read()
    finally:
        journal.close()
    unchanged = encode(events) == encode(parent["events"]) and head == parent["head"]
    if not unchanged or not observation["baseline_preserved"]:
        raise IntegrityError("unexpected state mutation; requires inspection, never automatic G13 admission")
    baseline = observation["baseline_regression"]
    summary = {"schema": "nova.grammar-challenge-result.v1", "execution_status": "COMPLETED",
               "evolution_verdict": observation["evolution_verdict"], "first_unmet_gate": observation["first_unmet_gate"],
               "protocol_commit": protocol_commit, "runtime_sources_sha256": protocol["runtime_sources_sha256"],
               "state_head": head, "events": len(events), "active_generation": observation["after"]["active_generation"],
               "native_result_type": observation["native_result_type"], "native_selected_task": observation["native_selected_task"],
               "native_primitive_candidates": len(observation["native_primitive_candidates"]),
               "gates": observation["gates"], "fresh_hidden_cases_evaluated": 0,
               "baseline_journal_unchanged": unchanged,
               "baseline_regression": {"passed": sum(r["passed"] for r in baseline.values()),
                                       "total": sum(r["total"] for r in baseline.values()), "tasks": len(baseline)},
               "seconds": time.perf_counter() - started,
               "claim": "entry gate not passed; no grammar evolution and no generation 13"}
    write_json(output / "run-summary.json", summary)
    print(json.dumps(summary, ensure_ascii=False, sort_keys=True))
    return 2


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    launch = commands.add_parser("run")
    launch.add_argument("--protocol", type=Path, default=ROOT / "experience/grammar-challenge-v1/protocol.json")
    launch.add_argument("--protocol-commit", required=True)
    launch.add_argument("--state", type=Path, required=True)
    launch.add_argument("--output", type=Path, required=True)
    worker = commands.add_parser("observe")
    worker.add_argument("--state", type=Path, required=True)
    worker.add_argument("--expected-head", required=True)
    args = parser.parse_args()
    try:
        if args.command == "observe":
            with Kernel(args.state) as kernel:
                print(json.dumps(observe(kernel, args.expected_head), ensure_ascii=False, sort_keys=True, indent=2))
            return 0
        return run(args.protocol.resolve(), args.state.resolve(), args.output.resolve(), args.protocol_commit)
    except (ContractError, OSError, subprocess.SubprocessError) as exc:
        print(json.dumps({"execution_status": "ERROR", "error": str(exc)}), file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())

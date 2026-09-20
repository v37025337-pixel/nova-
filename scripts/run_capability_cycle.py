"""Run the frozen v3 mechanism trial and the separate strict G12 SHA milestone."""

import argparse
import hashlib
import json
import secrets
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from nova_core.contracts import ContractError, decode, digest, encode
from nova_core.evaluation import score
from nova_core.kernel import Kernel, context, runtime_manifest
from scripts.run_development_chain import restore, write_json


def announce(stage, body):
    print(json.dumps({"stage": stage, **body}, sort_keys=True), flush=True)


def export(kernel, destination):
    events, head = kernel.journal.read()
    write_json(destination, {"schema": "nova.journal.export.v1", "head": head, "events": events})
    return head


def restart(path, head, output):
    result = subprocess.run([sys.executable, "-m", "nova_core", "--state", str(path),
                             "verify", "--expected-head", head], cwd=ROOT,
                            capture_output=True, text=True, timeout=180)
    (output / "restart-stdout.json").write_text(result.stdout)
    (output / "restart-stderr.txt").write_text(result.stderr)
    if result.returncode:
        raise ContractError("cold replay failed")
    return decode(result.stdout)


def mechanism_trial(directory, state_path, output):
    fixture = decode((directory / "mechanism-fixture.json").read_text())
    output.mkdir(parents=True)
    with Kernel(state_path, create=True) as kernel:
        kernel.register(fixture["tasks"][:1])
        first = kernel.step()
        if first["status"] != "ADMITTED":
            raise ContractError("inherited skill setup failed")
        parent_genome = kernel.genome()
        kernel.register(fixture["tasks"][1:])
        failures = kernel.develop(2)["steps"]
        if [f["reason"] for f in failures] != ["SEARCH_EXHAUSTED"] * 2:
            raise ContractError("mechanism trial did not demonstrate the old grammar deficit")
        kernel.study(fixture["specification"])
        frozen = kernel.step()
        write_json(output / "freeze.json", frozen)
        if frozen["status"] != "FROZEN":
            raise ContractError("word mechanism was not synthesized")
        # Fresh entropy and an independent algebra oracle are used only AFTER
        # the candidate identity is durably frozen by Kernel.step().
        values = [(0, 0), (0xFFFFFFFF, 0), (0xFFFFFFFF, 0xFFFFFFFF), (1 << 31, 1)]
        values += [(secrets.randbits(32), secrets.randbits(32)) for _ in range(20)]
        rows = [{"input": {"a": a, "b": b}, "output": a ^ b} for a, b in values]
        admission = kernel.assess(frozen["freeze"], rows)
        write_json(output / "assessment.json", admission)
        # The second task has been pending since before synthesis. No caller
        # tells the selector to use it or which gene to compose.
        continuation = kernel.step()
        write_json(output / "continuation.json", continuation)
        audit = kernel.audit()
        write_json(output / "audit.json", audit)
        write_json(output / "genome.json", kernel.genome())
        head = export(kernel, output / "journal.json")
        rollback_path = state_path.with_name(state_path.stem + "-rollback.sqlite")
        kernel.journal.backup(rollback_path)
        checks = {"native_goal": frozen["selection"]["target"] == fixture["tasks"][1]["id"],
                  "generated_body": frozen["primitive"]["language"] == "nova.word-expression.v1",
                  "fresh_blind_admission": admission["status"] == "ADMITTED",
                  "causal_ablation": admission["report"]["ablation"]["without_primitive"]["passed"] == 0,
                  "regression": all(r["passed"] == r["total"] for r in admission["report"]["regression"].values()),
                  "native_continuation": continuation["status"] == "ADMITTED" and
                       continuation["selection"]["task"] == fixture["tasks"][2]["id"] and
                       frozen["primitive"]["id"] in continuation["program"]["parents"],
                  "independent_query": kernel.predict(fixture["tasks"][2]["id"], {"left": 0xDEAD, "right": 0xBEEF}) == 0x6042}
    restarted = restart(state_path, head, output)
    checks["cold_replay"] = restarted["head"] == head
    with Kernel(rollback_path) as reverted:
        reverted.rollback(1)
        reverted.audit()
        checks["rollback"] = reverted.genome() == parent_genome
        write_json(output / "rollback.json", {"status": reverted.status(), "genome": reverted.genome()})
    summary = {"status": "PASS" if all(checks.values()) else "WITHHOLD", "checks": checks,
               "head": head, "fresh_passed": admission["report"]["fresh_holdout"]["passed"],
               "fresh_total": len(rows), "claim": "word_equation_capability_transfer_only; not_SHA256_milestone"}
    write_json(output / "run-summary.json", summary)
    return summary


def run(directory, state_path, protocol_commit, output):
    positive_path = state_path.with_name(state_path.stem + "-mechanism.sqlite")
    if state_path.exists() or positive_path.exists() or output.exists():
        raise ContractError("use a new state path and output directory")
    protocol = decode((directory / "protocol.json").read_text())
    if list(sys.version_info[:2]) != protocol["python"] or digest(runtime_manifest()["sources"]) != protocol["runtime_sources_sha256"]:
        raise ContractError("frozen runtime/Python mismatch")
    for name in ["protocol.json", "mechanism-fixture.json"] + protocol["specification_files"]:
        path = directory / name
        committed = subprocess.check_output(["git", "show", protocol_commit + ":" + str(path.relative_to(ROOT))], cwd=ROOT)
        if committed != path.read_bytes():
            raise ContractError("pre-registered input changed: " + name)
    runner = Path(__file__).resolve()
    if subprocess.check_output(["git", "show", protocol_commit + ":" + str(runner.relative_to(ROOT))], cwd=ROOT) != runner.read_bytes():
        raise ContractError("runner differs from pre-registration")
    parent = decode((ROOT / protocol["parent_journal"]).read_text())
    if parent["head"] != protocol["parent_head"]:
        raise ContractError("parent anchor mismatch")
    output.mkdir(parents=True)
    started = time.perf_counter()
    mechanism = mechanism_trial(directory, positive_path, output / "mechanism")
    announce("mechanism", {"status": mechanism["status"], "fresh": mechanism["fresh_passed"]})
    if mechanism["status"] != "PASS":
        raise ContractError("mechanism verification failed")
    announce("g12", {"status": "RESTORING"})
    restore(parent, state_path)
    with Kernel(state_path) as kernel:
        before = kernel.status()
        if before["active_generation"] != 12:
            raise ContractError("expected G12")
        original_genome = kernel.genome()
        write_json(output / "upgrade.json", kernel.upgrade())
        without_knowledge = kernel.step()
        write_json(output / "diagnosis-before-specification.json", without_knowledge)
        for name in protocol["specification_files"]:
            kernel.study(decode((directory / name).read_text()))
        attempt = kernel.step()
        write_json(output / "capability-attempt.json", attempt)
        announce("sha256", {"status": attempt["status"], "reason": attempt["reason"],
                             "generated_partial_bodies": len(attempt["workspace"]["CODE"]["generated"])})
        assessment = None
        if attempt["status"] == "FROZEN":
            # Oracle stays in this external evaluator; neither its implementation
            # nor its fresh cases are arguments to Nova's specification learner.
            names = [secrets.token_hex(16) + "-" + suffix for suffix in ("", "nova", "é", "ядро")]
            names += [secrets.token_hex(80)[:length] for length in (55, 56, 63, 64, 65, 127)]
            rows = [{"input": {"document": json.dumps({"name": name}), "field": "name"},
                     "output": hashlib.sha256(name.encode()).hexdigest()} for name in names]
            assessment = kernel.assess(attempt["freeze"], rows)
            write_json(output / "sha256-assessment.json", assessment)
        continuation = kernel.step()
        write_json(output / "continuation.json", continuation)
        state, _, _ = kernel._load()
        active, memory, _ = context(state)
        regression = {tid: score(memory[pid], state["tasks"][tid]["train"] + state["tasks"][tid]["holdout"], memory)
                      for tid, pid in sorted(active.items())}
        write_json(output / "regression.json", regression)
        audit = kernel.audit()
        write_json(output / "audit.json", audit)
        head = export(kernel, output / "journal.json")
        events, _ = kernel.journal.read()
        if encode(events[:len(parent["events"])]) != encode(parent["events"]):
            raise ContractError("historical prefix changed")
        write_json(output / "causal-memory.json", kernel.causal_memory())
        unchanged = kernel.genome() == original_genome
    cold = restart(state_path, head, output)
    admitted = assessment is not None and assessment["status"] == "ADMITTED"
    gates = {"native_deficit_selection": attempt["selection"]["target"] == protocol["sha_task"],
             "native_goal_and_diagnosis": bool(attempt["report"]["diagnosis"]),
             "generated_full_candidate": attempt["status"] == "FROZEN",
             "isolated_fresh_holdout_regression_ablation_admission": admitted,
             "cold_restart": cold["status"] == "PASS",
             "native_next_goal": bool(continuation.get("selection"))}
    summary = {"mechanism_verdict": mechanism["status"],
               "sha256_milestone": "PASS" if all(gates.values()) else "WITHHOLD", "gates": gates,
               "reason": attempt["reason"], "protocol_commit": protocol_commit,
               "runtime_sources_sha256": protocol["runtime_sources_sha256"], "parent_head": parent["head"],
               "head": head, "active_generation": cold["active_generation"], "genome_unchanged": unchanged,
               "native_target": attempt["selection"]["target"],
               "generated_partial_bodies": len(attempt["workspace"]["CODE"]["generated"]),
               "hidden_sha_cases_evaluated": assessment["report"]["fresh_holdout"]["total"] if assessment else 0,
               "new_sha_capability_admitted": admitted,
               "regression": {"passed": sum(r["passed"] for r in regression.values()),
                              "total": sum(r["total"] for r in regression.values()), "skills": len(regression)},
               "cold_restart": cold["status"], "next_requirement": attempt["report"]["next_requirement"],
               "seconds": time.perf_counter() - started,
               "claim_boundary": "five_mechanisms_exist_for_bounded_word_equations; general_algorithm_learning_and_SHA256_are_unresolved"}
    if ((not admitted and not unchanged) or summary["regression"]["passed"] != summary["regression"]["total"]):
        raise ContractError("unexpected SHA milestone outcome; inspect full evidence")
    write_json(output / "run-summary.json", summary)
    announce("complete", summary)
    return 0 if summary["sha256_milestone"] == "PASS" else 2


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--directory", type=Path, default=ROOT / "experience/capability-cycle-v3")
    parser.add_argument("--state", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--protocol-commit", required=True)
    args = parser.parse_args()
    return run(args.directory.resolve(), args.state.resolve(), args.protocol_commit, args.output.resolve())


if __name__ == "__main__":
    raise SystemExit(main())

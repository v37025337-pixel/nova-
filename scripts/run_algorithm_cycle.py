"""Frozen G12 -> generated algorithm -> cold restart -> native next goal trial."""

import argparse
import hashlib
import json
import secrets
import string
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


def announce(stage, **values):
    print(json.dumps({"stage": stage, **values}, sort_keys=True), flush=True)


def export(kernel, path):
    events, head = kernel.journal.read()
    write_json(path, {"schema": "nova.journal.export.v1", "head": head, "events": events})
    return head


def cold(path, command, destination):
    result = subprocess.run([sys.executable, "-m", "nova_core", "--state", str(path), *command],
                            cwd=ROOT, capture_output=True, text=True, timeout=240)
    destination.write_text(result.stdout)
    destination.with_suffix(".stderr.txt").write_text(result.stderr)
    if result.returncode:
        raise ContractError("cold command failed: " + " ".join(command))
    return decode(result.stdout)


def fresh_names():
    # Invoked only after the frozen candidate event. Public conformance vectors
    # (empty, abc, repeated a) are deliberately not called fresh-blind cases.
    lengths = [17, 31, 55, 56, 57, 63, 64, 65, 111, 119, 120, 127, 128, 129,
               255, 256, 257, 511, 512, 513, 1023, 1024]
    values = ["".join(secrets.choice(string.ascii_letters + string.digits) for _ in range(n)) for n in lengths]
    values += [secrets.token_hex(24) + "\x00ядро-é", secrets.token_hex(120) + "東京-🚀"]
    return values


def example(name, record=False):
    digest_value = hashlib.sha256(name.encode("utf-8")).hexdigest()
    return {"input": {"document": json.dumps({"name": name}, ensure_ascii=False), "field": "name"},
            "output": {"digest": digest_value, "name": name.upper()} if record else digest_value}


def run(directory, path, output, protocol_commit):
    rollback_path = path.with_name(path.stem + "-rollback.sqlite")
    if any(p.exists() for p in (path, rollback_path, output)):
        raise ContractError("new state and evidence paths required")
    protocol = decode((directory / "protocol.json").read_text())
    if list(sys.version_info[:2]) != protocol["python"] or digest(runtime_manifest()["sources"]) != protocol["runtime_sources_sha256"]:
        raise ContractError("runtime differs from frozen protocol")
    for relative in protocol["frozen_files"]:
        local = ROOT / relative
        committed = subprocess.check_output(["git", "show", protocol_commit + ":" + relative], cwd=ROOT)
        if local.read_bytes() != committed:
            raise ContractError("pre-registered file changed: " + relative)
    parent = decode((ROOT / protocol["parent_journal"]).read_text())
    if parent["head"] != protocol["parent_head"]:
        raise ContractError("parent anchor mismatch")
    output.mkdir(parents=True)
    started = time.perf_counter()
    announce("restore", parent_generation=12)
    restore(parent, path)
    with Kernel(path) as kernel:
        old_genome = kernel.genome()
        write_json(output / "upgrade.json", kernel.upgrade())
        transfer = decode((directory / "transfer-task.json").read_text())
        kernel.register([transfer])
        old_search = kernel.step()
        write_json(output / "old-grammar-transfer-attempt.json", old_search)
        if old_search.get("selection", {}).get("task") != transfer["id"] or old_search["reason"] != "SEARCH_EXHAUSTED":
            raise ContractError("next-task deficit was not demonstrated before extension")
        for name in protocol["new_knowledge"]:
            kernel.study(decode((directory / name).read_text()))
        frozen = kernel.step()
        write_json(output / "freeze.json", frozen)
        announce("freeze", status=frozen["status"], reason=frozen["reason"], target=frozen["selection"]["target"])
        if frozen["status"] != "FROZEN":
            export(kernel, output / "journal.json")
            write_json(output / "run-summary.json", {"status": "WITHHOLD", "reason": frozen["reason"],
                       "head": kernel.status()["head"], "generation": kernel.status()["active_generation"]})
            return 2
        (output / "generated-primitive.py").write_text(frozen["primitive"]["source"])
        (output / "generated-adapter.py").write_text(frozen["program"]["source"])
        # Independent oracle and fresh entropy exist outside Nova's compiler.
        names = fresh_names()
        assessment = kernel.assess(frozen["freeze"], [example(name) for name in names])
        write_json(output / "assessment.json", assessment)
        announce("admission", status=assessment["status"], generation=assessment["generation"],
                 fresh=assessment["report"]["fresh_holdout"]["passed"])
        if assessment["status"] != "ADMITTED":
            export(kernel, output / "journal.json")
            write_json(output / "run-summary.json", {"status": "WITHHOLD", "reason": assessment["reason"],
                       "head": kernel.status()["head"], "generation": kernel.status()["active_generation"]})
            return 2
        admitted = kernel.audit()
        write_json(output / "g13-audit.json", admitted)
        g13_head = export(kernel, output / "g13-journal.json")
    # Both verification and continuation are new OS processes. The next goal
    # has been waiting since BEFORE synthesis; this caller passes no goal id.
    replay = cold(path, ["verify", "--expected-head", g13_head], output / "g13-cold-replay.json")
    resumed = cold(path, ["step", "--steps", "1"], output / "after-restart-continuation.json")
    next_step = resumed["steps"][0]
    announce("continuation", status=next_step["status"], generation=resumed["state"]["active_generation"],
             task=next_step.get("selection", {}).get("task"))
    with Kernel(path) as kernel:
        state, _, _ = kernel._load()
        active, memory, _ = context(state)
        regression = {tid: score(memory[pid], state["tasks"][tid]["train"] + state["tasks"][tid]["holdout"], memory)
                      for tid, pid in sorted(active.items())}
        queries = []
        for name in [secrets.token_hex(23) + suffix for suffix in ("nova", "ядро", "é", "\x00")]:
            for task, record in ((protocol["sha_task"], False), (transfer["id"], True)):
                row = example(name, record)
                observed = kernel.predict(task, row["input"])
                queries.append({"task": task, **row, "observed": observed, "passed": observed == row["output"]})
        audit = kernel.audit()
        write_json(output / "audit.json", audit)
        write_json(output / "regression.json", regression)
        write_json(output / "queries.json", queries)
        write_json(output / "genome.json", kernel.genome())
        write_json(output / "causal-memory.json", kernel.causal_memory())
        head = export(kernel, output / "journal.json")
        events, _ = kernel.journal.read()
        prefix_preserved = encode(events[:len(parent["events"])]) == encode(parent["events"])
        kernel.journal.backup(rollback_path)
    final_replay = cold(path, ["verify", "--expected-head", head], output / "g14-cold-replay.json")
    with Kernel(rollback_path) as reverted:
        reverted.rollback(12)
        rollback = reverted.audit()
        rollback_ok = reverted.genome() == old_genome and not rollback["capabilities_active"]
        try:
            reverted.predict(protocol["sha_task"], example("should-be-inactive")["input"])
            rollback_ok = False
        except ContractError:
            pass
        write_json(output / "rollback.json", {"audit": rollback, "genome": reverted.genome(), "passed": rollback_ok})
    checks = {"native_deficit_selection": frozen["selection"]["target"] == protocol["sha_task"],
              "native_goal": frozen["workspace"]["THINKING"]["origin"] == "kernel_causal_memory",
              "native_generated_sequence_body": frozen["primitive"]["language"] == "nova.sequence.v1" and
                    frozen["workspace"]["CODE"]["author"] == "kernel_document_compiler",
              "isolated_fresh_blind": assessment["report"]["isolation"] == "linux_seccomp_v1" and
                    assessment["report"]["fresh_holdout"]["passed"] == len(names),
              "inherited_regression": all(r["passed"] == r["total"] for r in regression.values()),
              "causal_ablation": assessment["report"]["ablation"]["without_primitive"]["passed"] == 0,
              "g13_admission": admitted["active_generation"] == 13,
              "g13_cold_replay": replay["head"] == g13_head and replay["status"] == "PASS",
              "native_next_goal_after_restart": next_step.get("selection", {}).get("task") == transfer["id"],
              "g14_uses_g13": next_step.get("status") == "ADMITTED" and
                    frozen["program"]["id"] in next_step["program"]["parents"],
              "post_admission_queries": all(q["passed"] for q in queries),
              "g14_cold_replay": final_replay["head"] == head and final_replay["active_generation"] == 14,
              "rollback": rollback_ok, "historical_prefix_preserved": prefix_preserved}
    summary = {"status": "PASS" if all(checks.values()) else "WITHHOLD", "checks": checks,
               "protocol_commit": protocol_commit, "parent_head": parent["head"], "g13_head": g13_head,
               "head": head, "generation": final_replay["active_generation"],
               "fresh_holdout": {"passed": assessment["report"]["fresh_holdout"]["passed"], "total": len(names)},
               "ablation_without_primitive": assessment["report"]["ablation"]["without_primitive"]["passed"],
               "regression": {"passed": sum(r["passed"] for r in regression.values()), "total": sum(r["total"] for r in regression.values()), "skills": len(regression)},
               "queries": {"passed": sum(q["passed"] for q in queries), "total": len(queries)},
               "seconds": time.perf_counter() - started,
               "claim_boundary": "specification-guided bounded capability evolution; maintainer supplied reader and interface, no ready SHA implementation; not autonomous algorithm invention",
               "input_domain": "UTF-8 text up to 1024 bytes"}
    write_json(output / "run-summary.json", summary)
    announce("complete", **summary)
    return 0 if summary["status"] == "PASS" else 2


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--directory", type=Path, default=ROOT / "experience/algorithm-cycle-v4")
    parser.add_argument("--state", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--protocol-commit", required=True)
    args = parser.parse_args()
    return run(args.directory.resolve(), args.state.resolve(), args.output.resolve(), args.protocol_commit)


if __name__ == "__main__":
    raise SystemExit(main())

"""Transport and evidence for native Python-tool requests; never supplies a gene.

Each invocation starts a new Kernel process and replays the complete journal.
Fresh labels are supplied only by a separate evaluator after candidate freeze.
"""
import argparse
import hashlib
import importlib.metadata
import json
import operator
import functools
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from nova_core.contracts import ContractError, digest, encode
from nova_core.kernel import Kernel, context, runtime_manifest
from nova_core.isolation import evaluate
from nova_core.python_tools import catalogue
from run_development_chain import restore, write_json


def environment():
    return {"python": list(sys.version_info[:2]), "python_version": sys.version,
            "executable_sha256": hashlib.sha256(Path(sys.executable).read_bytes()).hexdigest(),
            "stdlib_sources": {m.__name__: hashlib.sha256(Path(m.__file__).read_bytes()).hexdigest()
                               for m in (operator, functools)},
            "installed_packages": dict(sorted((d.metadata["Name"], d.version)
                                               for d in importlib.metadata.distributions())),
            "package_access": "inventory only; executable bridge exposes the pinned pure stdlib catalogue"}


def checkpoint(kernel, output, action):
    events, head = kernel.journal.read()
    write_json(output/"journal.json", {"schema": "nova.journal.export.v1", "head": head, "events": events})
    write_json(output/"status.json", kernel.status())
    write_json(output/"genome.json", kernel.genome())
    write_json(output/"next-action.json", action)
    print(json.dumps({k: action[k] for k in ("status", "phase", "reason", "freeze", "generation") if k in action}), flush=True)


def frozen_protocol(output, freeze):
    protocol_path = output/"protocol.json"
    protocol = json.loads(protocol_path.read_text())
    for name in protocol["frozen_files"] + [str(protocol_path.relative_to(ROOT))]:
        if subprocess.check_output(["git", "show", freeze+":"+name], cwd=ROOT) != (ROOT/name).read_bytes():
            raise ContractError("changed frozen file: "+name)
    if digest(runtime_manifest()) != protocol["runtime_sha256"]:
        raise ContractError("runtime changed after freeze")
    return protocol


def advance(kernel, output):
    for _ in range(16):
        action = kernel.step()
        checkpoint(kernel, output, action)
        if action["status"] == "REQUESTED":
            req = action["request"]
            if req["kind"] != "PYTHON_CATALOGUE":
                return
            receipt = {"kind": "PYTHON_CATALOGUE", "request": req["id"],
                       "catalogue": catalogue(), "environment": environment()}
            write_json(output/(req["id"]+"-tools.json"), receipt)
            kernel.autonomy_response(receipt)
        elif action["status"] in ("FROZEN", "WITHHOLD", "IDLE", "WAITING"):
            if action["status"] == "FROZEN":
                state, _, _ = kernel._load()
                artifact = {"goal": state["autonomy"]["current"], "candidate": action}
                write_json(output/(action["freeze"]+"-frozen.json"), artifact)
                write_json(output/(action["freeze"]+"-evaluation-request.json"),
                           {"goal": artifact["goal"], "freeze": action["freeze"]})
            return
    raise ContractError("native step budget exceeded")


def regression(kernel):
    state, _, _ = kernel._load()
    active, memory, _ = context(state)
    results = {}
    for tid, pid in sorted(active.items()):
        task = state["tasks"][tid]
        results[tid] = evaluate([{"program": memory[pid], "rows": task["train"]+task["holdout"]}], memory)["results"][0]
    return {"passed": sum(r["passed"] for r in results.values()),
            "total": sum(r["total"] for r in results.values()), "skills": len(results), "results": results}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("command", choices=["advance", "assess", "verify", "rollback-check"])
    parser.add_argument("--state", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--freeze", required=True)
    parser.add_argument("--evaluation", type=Path)
    parser.add_argument("--target", type=int)
    args = parser.parse_args()
    output = args.output.resolve()
    protocol = frozen_protocol(output, args.freeze)
    parent = json.loads((ROOT/protocol["parent_journal"]).read_text())
    if parent["head"] != protocol["parent_head"]:
        raise ContractError("parent journal anchor changed")
    if not args.state.exists():
        if args.command != "advance":
            raise ContractError("missing state")
        restore(parent, args.state)
    with Kernel(args.state) as kernel:
        events, _ = kernel.journal.read()
        if encode(events[:len(parent["events"])]) != encode(parent["events"]):
            raise ContractError("historical prefix changed")
        if kernel.status()["upgrade_required"]:
            if args.command != "advance":
                raise ContractError("upgrade is required before evaluation")
            write_json(output/"runtime-upgrade.json", kernel.upgrade())
        if args.command == "advance":
            kernel.start_autonomy()
            advance(kernel, output)
        elif args.command == "assess":
            raw = json.loads(args.evaluation.read_text())
            result = kernel.autonomy_assess(raw["freeze"], raw["rows"])
            write_json(output/(raw["freeze"]+"-assessment.json"), result)
            checkpoint(kernel, output, result)
        elif args.command == "verify":
            report = {"audit": kernel.audit(), "generation": kernel.status()["active_generation"],
                      "genome": kernel.genome()["id"], "regression": regression(kernel),
                      "runtime_sha256": digest(runtime_manifest()), "historical_prefix_preserved": True}
            write_json(output/("g"+str(report["generation"])+"-cold-replay.json"), report)
            print(json.dumps({"audit": report["audit"], "regression": {k: v for k,v in report["regression"].items() if k != "results"}}), flush=True)
        else:
            state, _, _ = kernel._load()
            if args.target not in state["genomes"]:
                raise ContractError("unknown rollback target")
            expected = state["genomes"][args.target]
            path = args.state.with_name(args.state.stem+"-rollback-to-"+str(args.target)+".sqlite")
            if path.exists():
                raise ContractError("refusing to overwrite rollback evidence")
            kernel.journal.backup(path)
            with Kernel(path) as copy:
                copy.rollback(args.target)
                actual = copy.genome()
                reg = regression(copy)
                if actual != expected or reg["passed"] != reg["total"]:
                    raise ContractError("rollback did not restore exact genome and behavior")
                report = {"status": "PASS", "target": args.target, "exact_genome": actual["id"],
                          "audit": copy.audit(), "regression": reg, "production_state_untouched": True}
                write_json(output/("rollback-g"+str(args.target)+".json"), report)
                print(json.dumps({k:v for k,v in report.items() if k not in ("regression", "audit")}), flush=True)


if __name__ == "__main__":
    main()

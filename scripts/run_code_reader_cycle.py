"""Apply UCR to pinned Nova sources and actual G22 execution observations.

Historical examples are open diagnostic data, never fresh validation. The
maintainer selects this protocol; Nova alone selects any subsequent goal.
"""

import argparse
from datetime import datetime, timezone
import gzip
import hashlib
import json
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from nova_core.contracts import equal
from nova_core.evaluation import score
from nova_core.kernel import Kernel, context
from nova_tools.code_reader_bridge import read_file, record
from nova_tools.universal_code_reader import UniversalCodeReader
from scripts.run_development_chain import restore


def write(path, obj):
    path.write_text(json.dumps(obj, ensure_ascii=True, allow_nan=False, sort_keys=True, indent=2) + "\n")


def run(parent_path, output, source_commit, steps):
    output.mkdir(parents=True, exist_ok=False)
    source_root = "https://github.com/v37025337-pixel/nova-/blob/" + source_commit + "/"
    parent = json.loads(parent_path.read_text())
    state_path = output / "state.sqlite"
    restore(parent, state_path)
    obtained_at = datetime.now(timezone.utc).isoformat()
    sources, receipts, samples, diagnostics = [], [], [], []
    with Kernel(state_path) as kernel:
        before = kernel.status()
        snapshot, _, _ = kernel._load()
        active, memory, _ = context(snapshot)
        runtime_hashes = json.loads((ROOT / "canonical/release.json").read_text())["source_sha256"]
        for relative, expected in sorted(runtime_hashes.items()):
            path = ROOT / relative
            raw = path.read_bytes()
            committed = subprocess.check_output(["git", "show", source_commit + ":" + relative], cwd=ROOT)
            if raw != committed or hashlib.sha256(raw).hexdigest() != expected:
                raise ValueError("source does not match pinned runtime: " + relative)
            result = read_file(path)
            if result.metadata["duplicate_node_ids"] or result.metadata["unresolved_links"]:
                raise ValueError("invalid source IR graph: " + relative)
            samples.append(raw)
            sources.append({"path": relative, "sha256": result.sha256,
                            "ir_sha256": hashlib.sha256(result.to_json().encode()).hexdigest(),
                            "parse_level": result.metadata["parse_level"], "nodes": len(result.nodes),
                            "byte_preservation": result.restore_bytes() == raw,
                            "passport": result.passport()})
            receipts.append({"source": relative, "receipt": record(kernel, result, source_root + relative, obtained_at)})
        grammar = UniversalCodeReader().learn_grammar(samples, language_hint="python")
        write(output / "grammar.json", grammar.to_dict())
        print(json.dumps({"phase": "source_observations", "files": len(sources)}), flush=True)

        # Pack whole task histories, without splitting one skill across bundles.
        bundles, bundle, nrows = [], [], 0
        verified_outputs = 0
        for index, (tid, pid) in enumerate(sorted(active.items())):
            task = snapshot["tasks"][tid]
            examples = task["train"] + task["holdout"]
            names = sorted(examples[0]["input"])
            arguments = {f"arg{i}": name for i, name in enumerate(names)}
            alias = f"N{index:03d}"
            code = "r = " + alias + "(" + ",".join(arguments) + ")"
            rows = []
            for example in examples:
                actual = kernel.predict(tid, example["input"])
                if not equal(actual, example["output"]):
                    raise ValueError("inherited skill regression: " + tid)
                verified_outputs += 1
                rows.append({"code": code, "inputs": {key: example["input"][name] for key, name in arguments.items()},
                             "output": actual, "source_task": tid, "source_program": pid})
            if nrows + len(rows) > 128:
                bundles.append(bundle)
                bundle, nrows = [], 0
            bundle.append({"task": tid, "program": memory[pid], "alias": alias,
                           "argument_mapping": arguments, "rows": rows})
            nrows += len(rows)
        if bundle:
            bundles.append(bundle)
        for index, bundle in enumerate(bundles):
            programs_path = output / f"programs-{index}.json"
            traces_path = output / f"traces-{index}.json"
            binding = {"origin": "historical_G22_programs_and_known_examples",
                       "parent_head": parent["head"], "source_commit": source_commit,
                       "programs": [{k: v for k, v in item.items() if k != "rows"} for item in bundle]}
            write(programs_path, binding)
            write(traces_path, [row for item in bundle for row in item["rows"]])
            result = read_file(programs_path, traces=traces_path)
            cycle = result.metadata["cognitive_cycle"]
            write(output / f"cognitive-cycle-{index}.json", cycle)
            for item in bundle:
                symbol = cycle["compositional_reasoning"]["symbols"].get(item["alias"], {})
                candidates = symbol.get("candidates", [])
                best = candidates[0] if candidates else None
                diagnostics.append({"task": item["task"], "alias": item["alias"], "observations": len(item["rows"]),
                                    "status": symbol.get("status", "unresolved"), "best": best,
                                    "diagnostics": symbol.get("diagnostics", {}),
                                    "validation": "historical_diagnostic_not_fresh_or_independent"})
            receipts.append({"source": programs_path.name,
                "receipt": record(kernel, result, source_root + str(parent_path.relative_to(ROOT)), obtained_at)})
        print(json.dumps({"phase": "trace_observations", "skills": len(active), "outputs": verified_outputs}), flush=True)

        actions = []
        for _ in range(steps):
            action = kernel.step()
            actions.append(action)
            print(json.dumps({"phase": "kernel_step", "status": action["status"], "reason": action.get("reason")}), flush=True)
            if action["status"] in ("IDLE", "WAITING"):
                break
        current, _, _ = kernel._load()
        active_after, memory_after, _ = context(current)
        regression = {tid: score(memory_after[pid], current["tasks"][tid]["train"] + current["tasks"][tid]["holdout"], memory_after)
                      for tid, pid in sorted(active_after.items())}
        after = kernel.status()
        events, head = kernel.journal.read()
        exported = {"schema": "nova.journal.export.v1", "head": head, "events": events}
        (output / "journal.json.gz").write_bytes(gzip.compress(json.dumps(exported, ensure_ascii=True).encode(), mtime=0))
        write(output / "actions.json", actions)
        write(output / "source-analysis.json", sources)
        write(output / "receipts.json", receipts)
        write(output / "trace-diagnostics.json", diagnostics)
        write(output / "regression.json", regression)

    process = subprocess.run([sys.executable, "-m", "nova_core", "--state", str(state_path.resolve()),
                              "verify", "--expected-head", head], cwd=ROOT, capture_output=True, text=True, timeout=180)
    (output / "restart-stdout.json").write_text(process.stdout)
    (output / "restart-stderr.txt").write_text(process.stderr)
    replay = json.loads(process.stdout) if process.returncode == 0 else None
    passed = sum(r["passed"] for r in regression.values())
    total = sum(r["total"] for r in regression.values())
    summary = {"schema": "nova.ucr-cycle.v1", "reader_version": "16.0", "source_commit": source_commit,
               "reader_sources": json.loads((ROOT / "canonical/code-reader.json").read_text())["source_sha256"],
               "obtained_at": obtained_at, "protocol_author": "maintainer",
               "source_files": len(sources), "grammar_rules": len(grammar.rules),
               "historical_execution_observations": verified_outputs,
               "hypotheses_internally_supported": sum(d["status"] == "holdout-supported" for d in diagnostics),
               "skills_analyzed": len(diagnostics), "documents_recorded": len(receipts),
               "before": before, "after": after,
               "new_tasks_events": sum(e["kind"] == "tasks" for e in events[len(parent["events"]):]),
               "new_admissions": after["admissions_total"] - before["admissions_total"],
               "regression": {"passed": passed, "total": total, "skills": len(regression)},
               "cold_replay": {"exit_code": process.returncode, "status": replay.get("status") if replay else "ERROR",
                               "events": replay.get("events") if replay else None, "head": head},
               "new_capability_proven": after["admissions_total"] > before["admissions_total"],
               "status": "PASS_INTEGRATION" if process.returncode == 0 and passed == total else "FAIL",
               "limitations": ["historical examples are reused open diagnostic data",
                   "UCR ranks candidates using its internal split; this is not a fresh independent holdout",
                   "UCR hypotheses do not become Nova executable programs automatically",
                   "the experiment does not establish intelligence growth, consciousness or architecture self-rewrite"]}
    write(output / "summary.json", summary)
    print(json.dumps({k: summary[k] for k in ("status", "source_files", "historical_execution_observations",
                                            "hypotheses_internally_supported", "new_admissions", "regression", "cold_replay")}), flush=True)
    return 0 if summary["status"] == "PASS_INTEGRATION" else 1


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--parent", type=Path, default=ROOT / "experience/observation-goals-v1/journal.json")
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--source-commit", required=True)
    parser.add_argument("--steps", type=int, choices=range(1, 6), default=3)
    args = parser.parse_args()
    return run(args.parent.resolve(), args.output.resolve(), args.source_commit, args.steps)


if __name__ == "__main__":
    raise SystemExit(main())

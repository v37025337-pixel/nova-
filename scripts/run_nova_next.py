"""Freeze the runtime, then let it select deficits and acquire fresh HTTPS sources."""

import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from nova_core.contracts import digest
from nova_next.kernel import Kernel, DEFAULT_FEEDS, manifest
from nova_next import snapshot


def save(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2) + "\n")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    folder = args.output
    folder.mkdir(parents=True, exist_ok=False)
    protocol = {"schema": "nova.next.experiment.v1", "created_at": datetime.now(timezone.utc).isoformat(),
                "runtime": manifest(), "feeds": DEFAULT_FEEDS, "max_steps": 24, "max_admissions": 3,
                "runner_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
                "input": "source feeds only; no chosen query, target program or supplied answer",
                "freshness": "candidate frozen before two new repository downloads; no retries on consumed fresh data",
                "lineage": "Nova G22 skills inherited; successor starts independent Next G0"}
    save(folder / "protocol.json", protocol)
    actions, error = [], None
    with Kernel(folder / "state.sqlite", create=True) as kernel:
        try:
            for index in range(protocol["max_steps"]):
                if manifest() != protocol["runtime"]:
                    raise RuntimeError("runtime changed after protocol freeze")
                action = kernel.step()
                actions.append(action)
                save(folder / "actions.json", actions)
                snapshot.write(folder / "journal.json.gz", kernel.export())
                short = {k: action[k] for k in ("status", "reason", "url", "bytes") if k in action}
                if "goal" in action:
                    short["goal"] = action["goal"]["law"]
                if "fresh" in action:
                    short["fresh"] = {k: action["fresh"][k] for k in ("passed", "total")}
                print(json.dumps({"step": index + 1, **short}), flush=True)
                if action["status"] in ("IDLE", "WAITING") or kernel.status()["admissions_total"] >= protocol["max_admissions"]:
                    break
        except Exception as exc:
            error = type(exc).__name__ + ": " + str(exc)
            print(json.dumps({"error": error}), flush=True)
        finally:
            exported = kernel.export()
            snapshot.write(folder / "journal.json.gz", exported)
            status = kernel.status()
    proposals = [a for a in actions if a["status"] == "CANDIDATE_FROZEN"]
    assessments = [a for a in actions if "fresh" in a]
    sources = []
    for event in exported["events"]:
        if event["kind"] == "response":
            body = event["body"]
            sources.append({k: body[k] for k in ("url", "final_url", "sha256", "bytes", "received_at", "status", "transport")})
    programs = folder / "programs"
    programs.mkdir()
    for i, candidate in enumerate(proposals, 1):
        (programs / f"candidate_{i}.py").write_text(candidate["search"]["program"]["source"])
    result = {"schema": "nova.next.experiment.result.v1", "protocol_sha256": digest(protocol),
              "status": "COMPLETED" if error is None else "ERROR", "error": error,
              "kernel": status, "sources": sources,
              "candidates": [{k: c[k] for k in ("goal", "freeze", "parent_generation", "search", "fresh_cases_seen")} for c in proposals],
              "assessments": [{k: v for k, v in a.items() if k != "rows"} for a in assessments],
              "withheld_searches": [{"goal": a["goal"], "reason": a["reason"], "attempts": a["search"]["attempts"]}
                                    for a in actions if a["status"] == "WITHHOLD" and "search" in a],
              "limits": ["three developer-supplied structural query specifications", "finite grammar and 2048-program budget",
                         "static call candidates, not runtime causality", "views are correlated within each repository",
                         "HTTPS provenance is a local capture, not third-party signed attestation"]}
    save(folder / "result.json", result)
    print(json.dumps({"final": status, "error": error}), flush=True)
    if error:
        raise SystemExit(1)


if __name__ == "__main__":
    main()

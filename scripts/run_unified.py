"""Frozen live experiment exercising one controller across all cognitive faculties."""

import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from nova_core.contracts import digest
from nova_core.cognition.kernel import Kernel, manifest
from nova_core.cognition import checkpoint
from nova_next.data import parse_source
from nova_next.oracle import measure

FEEDS = [
    {"url": "https://raw.githubusercontent.com/jd/tenacity/main/tenacity/__init__.py", "module": "tenacity"},
    {"url": "https://raw.githubusercontent.com/tornadoweb/tornado/master/tornado/httpclient.py", "module": "tornado.httpclient"},
]


def save(path, body):
    path.write_text(json.dumps(body, ensure_ascii=False, sort_keys=True, indent=2) + "\n")


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--output", type=Path, required=True)
    args = p.parse_args()
    folder = args.output
    folder.mkdir(parents=True, exist_ok=False)
    protocol = {"schema": "nova.unified.experiment.v1", "created_at": datetime.now(timezone.utc).isoformat(),
                "runtime": manifest(), "feeds": FEEDS, "max_steps": 28,
                "runner_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
                "native_evolution": "continue the inherited frozen candidate; no supplied mechanism or goal override",
                "integration_goal": "report on captured source using inherited naming, UCR, acquired graph programs and proof rules",
                "integration_goal_author": "maintainer; action plan selected by the kernel"}
    save(folder / "protocol.json", protocol)
    actions, error, report, reasoning = [], None, None, None
    with Kernel(folder / "state.sqlite", create=True) as kernel:
        before = kernel.status()
        kernel.connect(FEEDS)
        goal = kernel.goal("code.report", {"source.url": FEEDS[0]["url"], "input.text": "  Tenacity source  "})
        try:
            for i in range(protocol["max_steps"]):
                if manifest() != protocol["runtime"]:
                    raise ValueError("runtime changed during frozen experiment")
                item = kernel.step()
                actions.append(item)
                checkpoint.write(folder / "journal.json.gz", kernel.export())
                checkpoint.write(folder / "actions.json.gz", actions)
                short = {"step": i + 1, "status": item["status"], "action": item.get("action")}
                if "result" in item:
                    short["reason"] = item["result"].get("reason")
                print(json.dumps(short), flush=True)
                if kernel.result(goal)["status"] != "READY" or "action" not in item:
                    break
            report = kernel.result(goal)
            if report["status"] == "COMPLETED":
                state = kernel._load()[0]
                document = next(d for d in state["graph"]["documents"] if d["receipt"]["url"] == FEEDS[0]["url"])
                graph = document["analysis"]["graph"]
                actual = measure(graph)
                for key, value in report["output"]["metrics"].items():
                    if actual[key] != value:
                        raise ValueError("combined report differs from independent graph oracle")
                if report["output"]["label"] != {"name": "TENACITY SOURCE", "length": 15}:
                    raise ValueError("inherited label mechanism differs")
                edges = sorted({(e["src"], e["dst"]) for e in graph["edges"]})
                path = next(((a, b, d) for a, b in edges for c, d in edges if b == c and len({a, b, d}) == 3), None)
                if path:
                    a, b, c = path
                    rules = [{"id": "direct-call", "if": [["calls", "?x", "?y"]], "then": ["may-reach", "?x", "?y"]},
                             {"id": "compose-call", "if": [["may-reach", "?x", "?y"], ["calls", "?y", "?z"]], "then": ["may-reach", "?x", "?z"]}]
                    reasoning = kernel.invoke("logic.reason", {"facts": [["calls", a, b], ["calls", b, c]], "rules": rules,
                                                              "query": ["may-reach", a, c]})
                    if reasoning["status"] != "SUCCEEDED" or reasoning["output"]["verdict"] != "TRUE":
                        raise ValueError("transitive reasoning on observed source failed")
        except Exception as exc:
            error = type(exc).__name__ + ": " + str(exc)
        finally:
            checkpoint.write(folder / "journal.json.gz", kernel.export())
            after = kernel.status()
            memory = kernel.memory()
    summary = {"schema": "nova.unified.experiment.result.v1", "status": "COMPLETED" if error is None else "ERROR",
               "error": error, "protocol_digest": digest(protocol), "before": before, "after": after,
               "report_goal": goal, "report": report, "source_reasoning": reasoning,
               "actions": [{"action": a.get("action"), "status": a["status"], "reason": a.get("result", {}).get("reason")} for a in actions],
               "admissions": [{k: v for k, v in a["result"].items() if k != "rows"}
                              for a in actions if a.get("action") == "graph.assess"],
               "experience": memory["experience"], "catalog_entries": len(memory["catalog"]),
               "limits": ["maintainer-written cognitive algorithms", "bounded typed planning and Horn logic", "finite graph query ontology",
                          "local HTTPS capture, not signed source attestation", "no claim of digital consciousness or general intelligence"]}
    save(folder / "result.json", summary)
    print(json.dumps({"status": summary["status"], "error": error, "generation": after["generation"],
                      "active_learned_skills": after["active_learned_skills"], "report": report["status"] if report else None}), flush=True)
    if error:
        raise SystemExit(1)


if __name__ == "__main__":
    main()

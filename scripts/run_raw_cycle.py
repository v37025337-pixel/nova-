"""Freeze the runtime and expose only a URL stream; the kernel owns every goal."""

import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import sys
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from nova_core.contracts import digest
from nova_core.cognition.kernel import Kernel, manifest
from nova_core.cognition import checkpoint

# Opaque transport addresses. No roles, task, parser, language or answers are sent.
URLS = [
    "https://raw.githubusercontent.com/curl/curl/master/lib/url.c",
    "https://raw.githubusercontent.com/serde-rs/json/master/src/de.rs",
    "https://raw.githubusercontent.com/google/gson/main/gson/src/main/java/com/google/gson/stream/JsonReader.java",
    "https://raw.githubusercontent.com/pydantic/pydantic/main/pydantic/main.py",
]


def save(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2) + "\n")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    folder = args.output
    folder.mkdir(parents=True, exist_ok=False)
    protocol = {"schema": "nova.raw-cycle.protocol.v1", "created_at": datetime.now(timezone.utc).isoformat(),
                "runtime": manifest(), "urls": URLS, "max_steps": 12,
                "runner_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
                "input": "URL stream only; no supplied task, examples, answers, reader or blueprint",
                "prior": "exact retention and lower description length; adjacent-symbol grammar induction",
                "gate": "two post-freeze origins, exact bytes, executable model cost, ablation, all-skill regression",
                "claims_excluded": ["self-invention of the learning algorithm", "arbitrary semantic goals", "general intelligence"]}
    save(folder / "protocol.json", protocol)
    save(folder / "urls.json", URLS)
    error, actions = None, []
    with Kernel(folder / "state.sqlite", create=True) as kernel:
        before = kernel.status()
        kernel.sense(URLS)
        try:
            # Turn these paths into tripwires for this actual internet run as well as tests.
            with patch("nova_core.cognition.capabilities.catalog", side_effect=AssertionError("catalog used in raw cycle")), \
                 patch("nova_core.cognition.capabilities.UniversalCodeReader", side_effect=AssertionError("reader used")), \
                 patch("nova_next.data.parse_source", side_effect=AssertionError("graph parser used")), \
                 patch("nova_next.learning.propose", side_effect=AssertionError("graph task catalog used")):
                for index in range(protocol["max_steps"]):
                    if manifest() != protocol["runtime"]:
                        raise ValueError("runtime changed after protocol freeze")
                    action = kernel.step()
                    actions.append(action)
                    checkpoint.write(folder / "journal.json.gz", kernel.export())
                    print(json.dumps({"step": index + 1, "action": action.get("action"), "status": action["status"]}), flush=True)
                    if action["status"] == "GOAL_FORMED":
                        save(folder / "self-goal.json", action["result"]["goal"])
                    if action["status"] == "FROZEN":
                        candidate = action["result"]["candidate"]
                        save(folder / "frozen-candidate.json", candidate)
                        (folder / "generated_mechanism.py").write_text(candidate["program"]["source"])
                    if action["status"] in ("ADMITTED", "WITHHOLD", "IDLE", "WAITING"):
                        break
        except Exception as exc:
            error = type(exc).__name__ + ": " + str(exc)
        finally:
            checkpoint.write(folder / "journal.json.gz", kernel.export())
            after = kernel.status()
        final = actions[-1] if actions else None
        state = kernel._load()[0]
        recalls = [{"sha256": hashlib.sha256(kernel.recall(i)).hexdigest(), "bytes": len(kernel.recall(i))}
                   for i in range(len(state["raw"]["records"]))]
        assert all(r["sha256"] == old["sha256"] for r, old in zip(recalls, state["raw"]["records"]))
        events = kernel.export()["events"]
        admission = next((e["body"] for e in reversed(events) if e.get("body", {}).get("result", {}).get("status") == "ADMITTED"), None)
    result = {"schema": "nova.raw-cycle.result.v1", "status": "ERROR" if error else final["status"],
              "error": error, "protocol_digest": digest(protocol), "before": before, "after": after,
              "actions": [{"action": a.get("action"), "status": a["status"]} for a in actions],
              "assessment": final.get("result") if final else None, "recall": recalls,
              "regression": admission["regression"] if admission else None,
              "catalog_and_readers_called_during_cycle": 0,
              "storage_scope": "active raw observation payload plus full model; journal audit copies retained",
              "limits": ["maintainer-supplied MDL preference and grammar induction", "bounded learned rewrite programs",
                         "transfer is across repository origins, not cryptographic proof of independence",
                         "zlib reference is reported separately; no claim of a new compression algorithm"]}
    save(folder / "result.json", result)
    print(json.dumps({"status": result["status"], "error": error, "generation": after["generation"],
                      "raw_bytes": after["raw"]["raw_bytes"], "description_bytes": after["raw"]["description_bytes"]}), flush=True)
    if result["status"] != "ADMITTED":
        raise SystemExit(1)


if __name__ == "__main__":
    main()

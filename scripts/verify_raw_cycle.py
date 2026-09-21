"""Offline replay, frozen transfer, independent byte checks, use and rollback."""

import argparse
import hashlib
import json
from pathlib import Path
import sys
import tempfile
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from nova_core.contracts import digest
from nova_core.cognition import checkpoint, raw_cycle, rawcodec, raw_verifier
from nova_core.cognition.kernel import Kernel, manifest


def verify(folder):
    protocol = json.loads((folder / "protocol.json").read_text())
    result = json.loads((folder / "result.json").read_text())
    exported = checkpoint.read(folder / "journal.json.gz")
    assert protocol["runtime"] == manifest(), "runtime differs from pre-observation freeze"
    assert result["status"] == "ADMITTED" and result["error"] is None
    assert digest(protocol) == result["protocol_digest"]
    assert hashlib.sha256((ROOT / "scripts/run_raw_cycle.py").read_bytes()).hexdigest() == protocol["runner_sha256"]
    steps = [e["body"] for e in exported["events"] if e["kind"] == "step"]
    assert [s["decision"]["choice"]["kind"] for s in steps] == ["raw.fetch", "raw.fetch", "raw.discover",
            "raw.synthesize", "raw.fetch", "raw.fetch", "raw.assess"]
    candidate = steps[3]["result"]["candidate"]
    assert candidate == json.loads((folder / "frozen-candidate.json").read_text())
    assert steps[2]["result"]["goal"] == json.loads((folder / "self-goal.json").read_text())
    assert candidate["program"]["source"] == (folder / "generated_mechanism.py").read_text()
    assert all(s["result"]["receipt"]["transport"] == "stdlib_https" for s in steps if s["result"]["status"] == "OBSERVED")
    with tempfile.TemporaryDirectory() as directory, \
         patch("nova_core.cognition.raw_network.fetch", side_effect=AssertionError("network in replay")), \
         patch("nova_next.network.fetch", side_effect=AssertionError("network in replay")):
        path = Path(directory) / "restored.sqlite"
        Kernel.restore(exported, path)
        with Kernel(path) as kernel:
            assert kernel.status() == result["after"]
            audit = kernel.audit()
            assert audit["status"] == "PASS"
            state = kernel._load()[0]
            raw = state["raw"]
            for i, record in enumerate(raw["records"]):
                assert hashlib.sha256(kernel.recall(i)).hexdigest() == record["sha256"]
            assert all(r["storage"]["model"] == candidate["program"]["id"] for r in raw["records"])
            assert not set(candidate["exposure"]["hashes"]).intersection(raw["consumed"])
            # Application on a further exact-byte input is separate from transfer scoring.
            identity = candidate["program"]["id"]
            unseen = b"\x00\xff\xfeopaque\x00" + bytes(range(256)) * 4
            packed = kernel.invoke("raw.pack:" + identity, {"hex": unseen.hex()})
            restored = kernel.invoke("raw.unpack:" + identity, {"hex": packed["output"]})
            assert restored == {"status": "SUCCEEDED", "output": unseen.hex()}
            before = raw_cycle.summary(raw)
            rolled = kernel.rollback(result["before"]["generation"])
            assert rolled["active_learned_skills"] == result["before"]["active_learned_skills"] == 24
            assert rolled["raw"]["consumed"] == before["consumed"]
            assert rolled["raw"]["exposed_hashes"] == before["exposed_hashes"]
            assert all(hashlib.sha256(kernel.recall(i)).hexdigest() == r["sha256"] for i, r in enumerate(raw["records"]))
            assert not any(k.startswith("raw.") for k in kernel.memory()["catalog"])
            assert kernel.invoke("skill:30-record", {"text": "  preserved experience  "})["output"] == {"name": "PRESERVED EXPERIENCE", "length": 20}
    migration = json.loads((folder.parent / "migration.json").read_text())
    assert digest(checkpoint.read(ROOT / "nova_core/cognition/bootstrap-v2.json.gz")) == migration["bootstrap_digest"]
    return {"status": "PASS", "head": exported["head"], "genome": result["after"]["genome"],
            "generation": result["after"]["generation"], "learned_rules": len(candidate["program"]["rules"]),
            "goal": candidate["goal"], "freeze": candidate["freeze"], "program": identity,
            "transfer": result["assessment"], "regression": audit["regression"],
            "network_requests_during_replay": 0, "exact_recall": len(raw["records"]),
            "learned_mechanism_executes": True, "rollback_preserves_freshness_and_bytes": True,
            "retained_skills_after_rollback": 24}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--experiment", type=Path, default=ROOT / "experience/raw-cycle-v1/live")
    parser.add_argument("--write", action="store_true")
    args = parser.parse_args()
    proof = verify(args.experiment)
    target = args.experiment / "verification.json"
    if args.write:
        target.write_text(json.dumps(proof, ensure_ascii=False, sort_keys=True, indent=2) + "\n")
    else:
        assert json.loads(target.read_text()) == proof
        release = json.loads((ROOT / "canonical/raw-cycle.json").read_text())
        assert release["checkpoint"]["head"] == proof["head"]
        for name, expected in release["file_sha256"].items():
            assert hashlib.sha256((ROOT / name).read_bytes()).hexdigest() == expected, name
    print(json.dumps({"status": "PASS", "head": proof["head"], "rules": proof["learned_rules"],
                      "transfer_net_gain": proof["transfer"]["net_gain_bytes"], "rollback": True}), flush=True)


if __name__ == "__main__":
    main()

"""Offline replay and cross-domain verification of the unified live checkpoint."""

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
from nova_core.cognition.kernel import Kernel, manifest
from nova_core.cognition import checkpoint


def verify(folder):
    protocol = json.loads((folder / "protocol.json").read_text())
    result = json.loads((folder / "result.json").read_text())
    journal = checkpoint.read(folder / "journal.json.gz")
    assert result["status"] == "COMPLETED" and result["error"] is None
    assert protocol["runtime"] == manifest()
    assert result["protocol_digest"] == digest(protocol)
    assert hashlib.sha256((ROOT / "scripts/run_unified.py").read_bytes()).hexdigest() == protocol["runner_sha256"]
    with tempfile.TemporaryDirectory() as directory, patch("nova_next.network.fetch", side_effect=AssertionError("network during offline verification")):
        path = Path(directory) / "restored.sqlite"
        restored = Kernel.restore(journal, path)
        assert restored["state"] == result["after"]
        with Kernel(path) as kernel:
            report = kernel.result(result["report_goal"])
            assert report == result["report"] and report["status"] == "COMPLETED"
            used = {step["capability"] for step in report["trace"]}
            required = {"skill:30-record", "reader.read", "source.graph", "graph:maximum_impact",
                        "graph:reachable_pairs", "logic.code_evidence", "report.code"}
            assert required <= used, "faculties did not participate in the same executable plan"
            audit = kernel.audit()
            assert audit["status"] == "PASS"
            generation = kernel.status()["generation"]
            sources = kernel.memory()["sources"]
            consumed = kernel.memory()["consumed_fresh_views"]
            rolled = None
            if generation:
                rolled = kernel.rollback(0)
                assert rolled["generation"] == 0 and rolled["active_learned_skills"] == 23
                assert kernel.memory()["sources"] == sources
                assert kernel.memory()["consumed_fresh_views"] == consumed
            legacy = kernel.invoke("skill:30-record", {"text": "  unified core  "})
            assert legacy["output"] == {"name": "UNIFIED CORE", "length": 12}
    migration = json.loads((folder.parent / "migration.json").read_text())
    for name, expected in migration["parent_archive_sha256"].items():
        assert hashlib.sha256((ROOT / name).read_bytes()).hexdigest() == expected
    assert hashlib.sha256((ROOT / "nova_core/cognition/bootstrap.json.gz").read_bytes()).hexdigest() == migration["bootstrap_sha256"]
    return {"status": "PASS", "head": result["after"]["head"], "genome": result["after"]["genome"],
            "generation": generation, "active_learned_skills": result["after"]["active_learned_skills"],
            "offline_network_requests": 0, "single_plan_capabilities": sorted(used),
            "cross_domain_regression": audit["regression"], "rollback": rolled is not None,
            "freshness_preserved": rolled is not None, "parent_archives_and_bootstrap": "verified",
            "verification": "full unified semantic replay, cold restart, cross-domain execution and rollback"}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--experiment", type=Path, default=ROOT / "experience/unified-v1/live")
    parser.add_argument("--write", action="store_true")
    args = parser.parse_args()
    proof = verify(args.experiment)
    target = args.experiment / "verification.json"
    if args.write:
        target.write_text(json.dumps(proof, ensure_ascii=False, sort_keys=True, indent=2) + "\n")
    else:
        assert json.loads(target.read_text()) == proof
        release = json.loads((ROOT / "canonical/unified.json").read_text())
        assert release["checkpoint"]["head"] == proof["head"]
        for name, expected in release["file_sha256"].items():
            assert hashlib.sha256((ROOT / name).read_bytes()).hexdigest() == expected, name
    print(json.dumps(proof, ensure_ascii=False, sort_keys=True), flush=True)


if __name__ == "__main__":
    main()

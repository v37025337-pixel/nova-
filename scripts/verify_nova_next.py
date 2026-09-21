"""Recompute admissions from captured external sources without accessing the network."""

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
from nova_core.memory import ZERO
from nova_next.kernel import Kernel, manifest
from nova_next import snapshot
from nova_next.evaluation import legacy_regression
from nova_next.oracle import measure


def verify(folder):
    protocol = json.loads((folder / "protocol.json").read_text())
    result = json.loads((folder / "result.json").read_text())
    exported = snapshot.read(folder / "journal.json.gz")
    assert protocol["runtime"] == manifest(), "runtime differs from frozen protocol"
    assert result["protocol_sha256"] == digest(protocol), "protocol digest differs"
    assert result["status"] == "COMPLETED" and result["error"] is None, "experiment did not complete"
    with tempfile.TemporaryDirectory() as directory:
        path = Path(directory) / "restored.sqlite"
        # Replay must not depend on current internet responses or silently fetch anything.
        with patch("nova_next.network.fetch", side_effect=AssertionError("network during replay")):
            restored = Kernel.restore(exported, path)
            assert restored["head"] == result["kernel"]["head"]
            with Kernel(path) as kernel:
                assert kernel.status() == result["kernel"], "restart differs from original state"
                state, _, _ = kernel._load()
                predictions = []
                for acquired in state["admitted"]:
                    law, graph = acquired["goal"]["law"], acquired["rows"][0]["graph"]
                    output = kernel.predict(law, graph)
                    assert output == measure(graph)[law], "restored mechanism differs from oracle"
                    predictions.append({"law": law, "program": acquired["program"]["id"], "result": output})
                # A separate transfer check of the inherited UCR model fitter, not a new admission.
                stream = {"transitions": [{"seq": i, "action": "hex_bytes", "before": {"n": n},
                                           "after": {"n": len(bytes(n).hex())}} for i, n in enumerate((1, 2, 4, 7))]}
                kernel.observe_states("stdlib-bytes-hex", stream)
                transferred = []
                for n in (11, 19, 31):
                    prediction = kernel.predict_state("stdlib-bytes-hex", "hex_bytes", {"n": n})
                    expected = {"n": len(bytes(n).hex())}
                    assert prediction["after"] == expected and prediction["new_admission"] is False
                    transferred.append({"input": n, "predicted": prediction["after"], "actual": expected})
                regression = legacy_regression()
                assert regression["passed"] == regression["total"] == 192
            # Exercise rollback at the genuine historical checkpoint immediately after admission.
            # The final state may already have a frozen successor awaiting new repositories.
            end = max((i + 1 for i, e in enumerate(exported["events"])
                       if e["kind"] == "assessment" and e["body"]["status"] == "ADMITTED"), default=0)
            rollback = None
            checkpoint_head = ZERO
            if end:
                history = exported["events"][:end]
                for i, event in enumerate(history, 1):
                    checkpoint_head = digest([i, checkpoint_head, event])
                checkpoint = {"schema": exported["schema"], "head": checkpoint_head, "events": history}
                checkpoint_path = Path(directory) / "checkpoint.sqlite"
                Kernel.restore(checkpoint, checkpoint_path)
                with Kernel(checkpoint_path) as kernel:
                    previous, _, _ = kernel._load()
                    seen = set(previous["seen_inputs"])
                    rollback = kernel.rollback(0)
                    rolled_state, _, _ = kernel._load(force=True)
                    assert rollback["generation"] == 0 and not rolled_state["genes"]
                    assert seen == rolled_state["seen_inputs"], "rollback erased freshness history"
    return {"status": "PASS", "verification": "offline full semantic replay, process restart, compiled predictions, rollback",
            "head": restored["head"], "events": restored["events"], "generation": restored["generation"],
            "genome": restored["genome"], "network_requests_during_replay": 0,
            "predictions": predictions, "legacy_regression": regression,
            "inherited_state_model_transfer": {"cases": transferred, "new_admission": False},
            "rollback_checkpoint_head": checkpoint_head,
            "rollback_to_zero": rollback is not None, "freshness_retained_after_rollback": rollback is not None}


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--experiment", type=Path, default=ROOT / "experience/nova-next-v2")
    p.add_argument("--write", action="store_true")
    args = p.parse_args()
    proof = verify(args.experiment)
    target = args.experiment / "verification.json"
    if args.write:
        target.write_text(json.dumps(proof, ensure_ascii=False, sort_keys=True, indent=2) + "\n")
    else:
        assert json.loads(target.read_text()) == proof, "verification artifact differs from recomputed evidence"
        release = json.loads((ROOT / "canonical/nova-next.json").read_text())
        assert release["checkpoint"]["head"] == proof["head"]
        for name, expected in release["file_sha256"].items():
            assert hashlib.sha256((ROOT / name).read_bytes()).hexdigest() == expected, "release file differs: " + name
    print(json.dumps(proof, ensure_ascii=False, sort_keys=True), flush=True)


if __name__ == "__main__":
    main()

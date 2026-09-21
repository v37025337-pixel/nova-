"""Behavioral contract for discovery from opaque observations, without a task."""

from pathlib import Path
from copy import deepcopy
import hashlib
import random
import tempfile
import unittest
from unittest.mock import patch

from nova_core.cognition.kernel import Kernel
from nova_core.cognition import rawcodec, raw_cycle, raw_verifier
from nova_core.contracts import ContractError, IntegrityError, digest
from nova_core.memory import ZERO


URLS = [f"https://opaque-{i}.example/unknown" for i in range(4)]


def observations():
    # Intentionally not UTF-8, JSON, code, graphs or a task/answer dataset.
    return [(b"\xff\x00\x80" + b"alpha=" + str(i).encode() + b";beta=retained;gamma=") * 1300
            + bytes([i]) for i in range(4)]


def receipt(url, raw):
    return {"url": url, "final_url": url, "status": 200, "hex": raw.hex(),
            "sha256": hashlib.sha256(raw).hexdigest(), "bytes": len(raw),
            "received_at": "2026-09-21T00:00:00+00:00", "transport": "test_fixture", "dns_policy": "test_fixture"}


def rehash(exported):
    head = ZERO
    for i, event in enumerate(exported["events"], 1):
        head = digest([i, head, event])
    exported["head"] = head
    return exported


def drive(kernel, blobs, count=7):
    with patch("nova_core.cognition.raw_network.fetch", side_effect=lambda url: receipt(url, blobs[URLS.index(url)])):
        return [kernel.step() for _ in range(count)]


class RawCycleTests(unittest.TestCase):
    def test_urls_alone_start_observation_without_a_supplied_goal(self):
        with tempfile.TemporaryDirectory() as directory, Kernel(Path(directory) / "state.sqlite", create=True) as kernel:
            kernel.sense(["https://first.example/opaque", "https://second.example/opaque"])
            self.assertEqual(kernel.think()["choice"]["kind"], "raw.fetch")
            self.assertIsNone(kernel.memory()["raw"]["goal"])

    def test_closed_cycle_without_catalog_or_reader_and_offline_recovery(self):
        blobs = observations()
        with tempfile.TemporaryDirectory() as directory:
            with Kernel(Path(directory) / "state.sqlite", create=True) as kernel:
                self.assertEqual(kernel.status()["active_learned_skills"], 24)
                self.assertFalse(any(k.startswith("raw.") for k in kernel.memory()["catalog"]))
                kernel.sense(URLS)
                with patch("nova_core.cognition.capabilities.catalog", side_effect=AssertionError("catalog consulted")), \
                     patch("nova_core.cognition.capabilities.UniversalCodeReader", side_effect=AssertionError("reader used")), \
                     patch("nova_next.data.parse_source", side_effect=AssertionError("source parser used")), \
                     patch("nova_next.learning.propose", side_effect=AssertionError("graph catalog used")):
                    actions = drive(kernel, blobs)
                self.assertEqual([a["status"] for a in actions],
                                 ["OBSERVED", "OBSERVED", "GOAL_FORMED", "FROZEN", "OBSERVED", "OBSERVED", "ADMITTED"])
                self.assertEqual(kernel.status()["active_learned_skills"], 25)
                self.assertEqual(kernel.status()["generation"], 2)
                for i, raw in enumerate(blobs):
                    self.assertEqual(kernel.recall(i), raw)
                state = kernel.memory()["raw"]
                self.assertLess(state["description_bytes"], state["raw_bytes"])
                self.assertGreater(actions[-1]["result"]["net_gain_bytes"], 0)
                identity = state["active"][0]
                unseen = bytes(range(256)) * 5 + b"\xff\xfe new byte sequence"
                packed = kernel.invoke("raw.pack:" + identity, {"hex": unseen.hex()})
                self.assertEqual(packed["status"], "SUCCEEDED")
                unpacked = kernel.invoke("raw.unpack:" + identity, {"hex": packed["output"]})
                self.assertEqual(unpacked["output"], unseen.hex())
                journal = kernel.export()
            with patch("nova_core.cognition.raw_network.fetch", side_effect=AssertionError("network during replay")):
                Kernel.restore(journal, Path(directory) / "replayed.sqlite")
                with Kernel(Path(directory) / "replayed.sqlite") as restored:
                    self.assertEqual(restored.memory()["raw"], state)
                    self.assertEqual(restored.recall(3), blobs[3])
                    rolled = restored.rollback(1)
                    self.assertEqual(rolled["active_learned_skills"], 24)
                    self.assertEqual(rolled["raw"]["consumed"], state["consumed"])
                    self.assertEqual(restored.recall(3), blobs[3])
                    self.assertFalse(any(k.startswith("raw.") for k in restored.memory()["catalog"]))
            forged = deepcopy(journal)
            event = next(e for e in forged["events"] if e.get("body", {}).get("result", {}).get("status") == "ADMITTED")
            event["body"]["result"]["net_gain_bytes"] += 1
            with self.assertRaises(IntegrityError):
                Kernel.restore(rehash(forged), Path(directory) / "forged.sqlite")

    def test_fresh_blind_data_cannot_be_reused_or_acquired_by_other_faculties(self):
        blobs = observations()
        with tempfile.TemporaryDirectory() as directory, Kernel(Path(directory) / "state.sqlite", create=True) as kernel:
            kernel.sense(URLS[:2])
            self.assertEqual(drive(kernel, blobs, 4)[-1]["status"], "FROZEN")
            freeze = kernel.status()["raw"]["freeze"]
            self.assertEqual(kernel.step()["status"], "WAITING")
            with patch("nova_next.network.fetch", side_effect=AssertionError("unreserved fetch")):
                self.assertEqual(kernel.invoke("source.fetch", {"url": URLS[2]})["status"], "FAILED")
            kernel.sense(URLS[2:])
            with patch("nova_core.cognition.raw_network.fetch", return_value=receipt(URLS[2], blobs[0])):
                duplicate = kernel.step()
            self.assertEqual(duplicate["status"], "FETCH_FAILED")
            self.assertIn("already exposed", duplicate["result"]["error"])
            self.assertEqual(kernel.status()["raw"]["freeze"], freeze)
            self.assertEqual(kernel.status()["active_learned_skills"], 24)

    def test_nontransferring_mechanism_is_withheld_and_holdout_consumed(self):
        blobs = observations()
        rng = random.Random(11973)
        blobs[2:] = [rng.randbytes(24000), rng.randbytes(24000)]
        with tempfile.TemporaryDirectory() as directory, Kernel(Path(directory) / "state.sqlite", create=True) as kernel:
            kernel.sense(URLS)
            result = drive(kernel, blobs)[-1]
            self.assertEqual(result["status"], "WITHHOLD")
            self.assertEqual(result["result"]["reason"], "NO_NET_TRANSFER_GAIN")
            self.assertEqual(kernel.status()["active_learned_skills"], 24)
            self.assertEqual(len(kernel.memory()["raw"]["consumed"]), 2)

    def test_failed_global_regression_cannot_commit_a_positive_transfer(self):
        blobs = observations()
        with tempfile.TemporaryDirectory() as directory, Kernel(Path(directory) / "state.sqlite", create=True) as kernel:
            kernel.sense(URLS)
            drive(kernel, blobs, 6)
            head = kernel.status()["head"]
            with patch("nova_core.cognition.kernel.regression", return_value={"status": "FAIL"}):
                with self.assertRaises(IntegrityError):
                    kernel.step()
            self.assertEqual(kernel.status()["head"], head)
            self.assertEqual(kernel.status()["active_learned_skills"], 24)

    def test_noise_does_not_receive_a_fabricated_objective(self):
        rng = random.Random(4721)
        blobs = [rng.randbytes(30000), rng.randbytes(30000)]
        state = raw_cycle.initial()
        for i, raw in enumerate(blobs):
            raw_cycle.observe(state, {"url": URLS[i], "role": "discovery"}, receipt(URLS[i], raw), [])
        self.assertEqual(raw_cycle.discover(state)["status"], "IDLE")

    def test_generated_source_and_grammar_cannot_disagree(self):
        model = rawcodec.program([[97, 98], [256, 256]])
        tested = raw_verifier.score(model, [b"", bytes(range(256)), b"ab" * 200])
        self.assertEqual(tested["passed"], 3)
        model["source"] += "\nraise ValueError('unverified code')\n"
        with self.assertRaises(ContractError):
            rawcodec.isolated(model, [b"ab"])

    def test_corrupt_frame_and_exponential_expansion_are_rejected(self):
        with self.assertRaises(ContractError):
            rawcodec.program([[0, 0]] + [[i, i] for i in range(256, 270)])
        with self.assertRaises(ContractError):
            rawcodec.program([[True, 0]])
        with self.assertRaises(ContractError):
            raw_verifier.restore(rawcodec.program([]), b"\x01" + (1).to_bytes(4, "big") + (100).to_bytes(4, "big"))

    def test_task_metadata_is_not_an_observation_interface(self):
        with tempfile.TemporaryDirectory() as directory, Kernel(Path(directory) / "state.sqlite", create=True) as kernel:
            with self.assertRaises(ContractError):
                kernel.sense([{"url": URLS[0], "task": "compress"}, {"url": URLS[1]}])


if __name__ == "__main__":
    unittest.main()

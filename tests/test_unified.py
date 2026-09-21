import copy
from datetime import datetime, timezone
import hashlib
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from nova_core.contracts import ContractError, IntegrityError, digest
from nova_core.memory import ZERO
from nova_core.cognition.kernel import Kernel
from nova_core.cognition.logic import reason
from nova_core.cognition.planning import plan
from nova_core.cognition.capabilities import descriptor


def receipt(url):
    text = "\n".join(f"def f{i}():\n    return f{i+1}()\n" for i in range(19)) + "def f19():\n    return 1\n"
    # Different repositories have different actual captured bytes and node labels.
    if "second" in url:
        text = text.replace("f", "g") + "\n# second source\n"
        text = text.replace("deg ", "def ")
    raw = text.encode()
    return {"url": url, "final_url": url, "status": 200, "text": text, "sha256": hashlib.sha256(raw).hexdigest(),
            "bytes": len(raw), "received_at": datetime.now(timezone.utc).isoformat(), "transport": "stdlib_https"}


class ReasoningTests(unittest.TestCase):
    def test_transitive_reasoning_and_explicit_proof(self):
        r = reason([["edge", "a", "b"], ["edge", "b", "c"]],
                   [{"id": "direct", "if": [["edge", "?x", "?y"]], "then": ["reach", "?x", "?y"]},
                    {"id": "chain", "if": [["reach", "?x", "?y"], ["edge", "?y", "?z"]], "then": ["reach", "?x", "?z"]}],
                   ["reach", "a", "c"])
        self.assertEqual(r["verdict"], "TRUE")
        self.assertEqual(r["support"]["rule"], "chain")
        self.assertEqual(len(r["support"]["premises"]), 2)

    def test_contradiction_does_not_explode_or_become_certainty(self):
        facts = [["trusted", "x"], ["!trusted", "x"]]
        self.assertEqual(reason(facts, [], ["trusted", "x"])["verdict"], "BOTH")
        self.assertEqual(reason(facts, [], ["anything", "y"])["verdict"], "UNKNOWN")
        self.assertEqual(reason([["!trusted", "x"]], [], ["trusted", "x"])["verdict"], "FALSE")

    def test_unbound_variable_is_not_a_created_fact(self):
        with self.assertRaises(ContractError):
            reason([["a", "x"]], [{"id": "bad", "if": [["a", "?x"]], "then": ["b", "?y"]}], ["b", "anything"])

    def test_plan_composes_missing_intermediate_and_adapts_to_failure(self):
        actions = [descriptor("quick", {"x": "raw"}, "clean", "provided", 1),
                   descriptor("robust", {"x": "raw"}, "clean", "provided", 2),
                   descriptor("finish", {"x": "clean"}, "result", "provided", 1)]
        catalog = {a["id"]: a for a in actions}
        self.assertEqual(plan(catalog, {"raw"}, "result")["actions"], ["quick", "finish"])
        learned = {"quick": {"success": 0, "failure": 5}, "robust": {"success": 3, "failure": 0}}
        self.assertEqual(plan(catalog, {"raw"}, "result", learned)["actions"], ["robust", "finish"])
        self.assertEqual(plan(catalog, {}, "result")["status"], "UNREACHABLE")


class UnifiedTests(unittest.TestCase):
    def setUp(self):
        # Preserve the original U0 scenarios, including its pending graph candidate.
        # Normal v1.1 init instead retains the fully trained U1 checkpoint.
        original = Path(__file__).resolve().parents[1] / "nova_core/cognition/bootstrap.json.gz"
        switch = patch("nova_core.cognition.kernel.BOOTSTRAP", original)
        switch.start()
        self.addCleanup(switch.stop)

    def test_one_registry_retains_both_generations_and_legacy_execution(self):
        with tempfile.TemporaryDirectory() as directory, Kernel(Path(directory) / "state.sqlite", create=True) as kernel:
            self.assertEqual(kernel.status()["active_learned_skills"], 23)
            result = kernel.invoke("skill:30-record", {"text": "  новый разум  "})
            self.assertEqual(result["output"], {"name": "НОВЫЙ РАЗУМ", "length": 11})
            self.assertEqual(kernel.memory()["experience"]["skill:30-record"]["success"], 1)
            self.assertEqual(kernel.status()["events"], 2)

    def test_cross_domain_plan_is_executed_and_replays_without_network(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "state.sqlite"
            with Kernel(path, create=True) as kernel, patch("nova_next.network.fetch", side_effect=AssertionError("cached source must not be fetched")):
                url = kernel.memory()["sources"][0]["url"]
                identity = kernel.goal("code.report", {"source.url": url, "input.text": "  requests  "})
                for _ in range(16):
                    kernel.step()
                    if kernel.result(identity)["status"] != "READY":
                        break
                result = kernel.result(identity)
                self.assertEqual(result["status"], "COMPLETED")
                self.assertEqual(result["output"]["label"], {"name": "REQUESTS", "length": 8})
                self.assertEqual(result["output"]["logic"]["verdict"], "TRUE")
                used = {item["capability"] for item in result["trace"]}
                self.assertTrue({"reader.read", "skill:30-record", "graph:reachable_pairs", "logic.code_evidence", "report.code"} <= used)
                exported = kernel.export()
            with patch("nova_next.network.fetch", side_effect=AssertionError("network during restore")):
                Kernel.restore(exported, Path(directory) / "restored.sqlite")
                with Kernel(Path(directory) / "restored.sqlite") as restored:
                    self.assertEqual(restored.result(identity), result)

    def test_frozen_candidate_cannot_be_bypassed_by_unseen_report_source(self):
        with tempfile.TemporaryDirectory() as directory, Kernel(Path(directory) / "state.sqlite", create=True) as kernel:
            with patch("nova_next.network.fetch", side_effect=AssertionError("must not acquire before reservation")):
                result = kernel.invoke("source.fetch", {"url": "https://example.org/new.py"})
            self.assertEqual(result["status"], "FAILED")
            self.assertIn("reserves unseen sources", result["error"])

    def test_append_sources_continues_frozen_candidate_and_regresses_all_skills(self):
        feeds = [{"url": "https://raw.githubusercontent.com/first/example/main/code.py", "module": "first"},
                 {"url": "https://raw.githubusercontent.com/second/example/main/code.py", "module": "second"}]
        with tempfile.TemporaryDirectory() as directory, Kernel(Path(directory) / "state.sqlite", create=True) as kernel:
            frozen = kernel.status()["pending_graph_candidate"]
            kernel.connect(feeds)
            self.assertEqual(kernel.status()["pending_graph_candidate"], frozen)
            with patch("nova_next.network.fetch", side_effect=receipt):
                self.assertEqual(kernel.step()["status"], "OBSERVED")
                self.assertEqual(kernel.step()["status"], "OBSERVED")
                admitted = kernel.step()
            self.assertEqual(admitted["status"], "ADMITTED")
            self.assertEqual(kernel.status()["active_learned_skills"], 24)
            self.assertEqual(kernel.status()["generation"], 1)
            self.assertTrue(admitted["result"]["dependency_ablation"])
            consumed = kernel.memory()["consumed_fresh_views"]
            kernel.rollback(0)
            self.assertEqual(kernel.status()["active_learned_skills"], 23)
            self.assertEqual(kernel.memory()["consumed_fresh_views"], consumed)

    def test_rehashed_forged_execution_is_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            with Kernel(Path(directory) / "state.sqlite", create=True) as kernel:
                kernel.invoke("skill:30-record", {"text": "  hello  "})
                exported = copy.deepcopy(kernel.export())
            exported["events"][-1]["body"]["result"]["output"]["length"] = 99
            head = ZERO
            for i, event in enumerate(exported["events"], 1):
                head = digest([i, head, event])
            exported["head"] = head
            with self.assertRaises(IntegrityError):
                Kernel.restore(exported, Path(directory) / "forged.sqlite")

    def test_boolean_cannot_masquerade_as_integer_in_replay(self):
        with tempfile.TemporaryDirectory() as directory:
            with Kernel(Path(directory) / "state.sqlite", create=True) as kernel:
                result = kernel.invoke("skill:30-record", {"text": "x"})
                self.assertEqual(result["output"]["length"], 1)
                exported = kernel.export()
            exported["events"][-1]["body"]["result"]["output"]["length"] = True
            head = ZERO
            for i, event in enumerate(exported["events"], 1):
                head = digest([i, head, event])
            exported["head"] = head
            with self.assertRaises(IntegrityError):
                Kernel.restore(exported, Path(directory) / "forged.sqlite")

    def test_unsupported_goal_is_blocked_without_fabricated_result(self):
        with tempfile.TemporaryDirectory() as directory, Kernel(Path(directory) / "state.sqlite", create=True) as kernel:
            identity = kernel.goal("arbitrary.new.intelligence", {"input.text": "hello"})
            result = kernel.step()
            self.assertEqual(result["status"], "BLOCKED")
            self.assertIsNone(kernel.result(identity)["output"])

    def test_expression_learning_uses_the_same_journal_and_cross_domain_gate(self):
        task = {"id": "unified-double", "source": "independent arithmetic fixture",
                "train": [{"input": {"x": x}, "output": 2 * x} for x in (2, 7, 13)],
                "holdout": [{"input": {"x": x}, "output": 2 * x} for x in (-11, 19, 31)]}
        with tempfile.TemporaryDirectory() as directory, Kernel(Path(directory) / "state.sqlite", create=True) as kernel:
            kernel.register([task])
            result = kernel.step()
            self.assertEqual(result["action"], "legacy.develop")
            self.assertEqual(result["status"], "ADMITTED")
            self.assertEqual(kernel.status()["legacy_skills"], 22)
            self.assertEqual(kernel.invoke("skill:unified-double", {"x": 37})["output"], 74)
            last = kernel.export()["events"][-2]["body"]
            self.assertEqual(last["regression"]["status"], "PASS")
            self.assertEqual(set(last["regression"]["graph"]), {"maximum_impact", "reachable_pairs"})


if __name__ == "__main__":
    unittest.main()

"""Behavioral contracts for the successor; fixtures are not internet evidence."""

from copy import deepcopy
from datetime import datetime, timezone
import hashlib
import tempfile
from pathlib import Path
import unittest
from unittest.mock import patch

from nova_core.contracts import ContractError, IntegrityError, digest
from nova_core.memory import Journal, ZERO
from nova_next.data import parse_source, graph_views
from nova_next.kernel import Kernel, origin
from nova_next.network import public_url
from nova_next.oracle import measure
from nova_next.programs import make_program, synthesize, execute
from nova_next.evaluation import isolated, assess


def graph(count, pairs):
    return {"nodes": [{"id": str(i), "module": "m", "kind": "function"} for i in range(count)],
            "edges": [{"src": str(a), "dst": str(b), "kind": "call"} for a, b in pairs]}


def source(number):
    count = 10 + number
    parts = ["# Test fixture " + str(number)]
    for i in range(count):
        calls = [f"f{j}()" for j in (i + 1, i + 2) if j < count]
        parts.append(f"def f{i}():\n    return " + (" + ".join(calls) if calls else "1"))
    return "\n\n".join(parts) + "\n"


def feed(number):
    return {"url": f"https://raw.githubusercontent.com/test-owner/repo-{number}/main/code.py",
            "module": "test" + str(number)}


def receipt(url):
    number = int(url.split("repo-")[1].split("/")[0])
    text = source(number)
    return {"url": url, "final_url": url, "status": 200, "text": text,
            "sha256": hashlib.sha256(text.encode()).hexdigest(), "bytes": len(text.encode()),
            "received_at": datetime.now(timezone.utc).isoformat(), "transport": "stdlib_https",
            "content_type": "text/plain", "etag": "", "seconds": 0.0}


class GraphAndProgramTests(unittest.TestCase):
    def test_independent_oracle_has_mathematical_expectations(self):
        examples = [
            (graph(3, [(0, 1), (1, 2)]), (3, 1, 2)),
            (graph(4, [(0, 1), (0, 2), (1, 3), (2, 3)]), (5, 1, 3)),
            (graph(3, [(0, 1), (1, 2), (2, 0)]), (6, 3, 2)),
            (graph(2, [(0, 0)]), (0, 0, 0)),
        ]
        for value, expected in examples:
            result = measure(value)
            self.assertEqual(tuple(result[k] for k in ("reachable_pairs", "indirect_pairs", "maximum_impact")), expected)

    def test_synthesis_emits_and_executes_a_fixed_point_algorithm(self):
        training = []
        for size in range(3, 7):
            value = graph(size, [(i, i + 1) for i in range(size - 1)])
            training.append({"graph": value, "expected": size * (size - 1) // 2})
        generated = synthesize(training, {})
        program = generated["program"]
        self.assertIsNotNone(program)
        self.assertIn("for _ in range", program["source"])
        # Unseen branching and cyclic graphs; expected counts calculated by hand.
        unknown = [graph(4, [(0, 1), (0, 2), (1, 3), (2, 3)]), graph(3, [(0, 1), (1, 2), (2, 0)])]
        self.assertEqual(isolated(program, unknown, {}), [5, 6])

    def test_compiled_source_tampering_is_rejected(self):
        p = make_program(["count", ["edges"]], {})
        p["source"] = "def solve(graph, genes):\n    return 999\n"
        with self.assertRaises(ContractError):
            isolated(p, [graph(2, [(0, 1)])], {})

    def test_reuse_enlarges_search_and_removal_changes_behavior(self):
        closure = make_program(["count", ["fix", ["edges"], ["union", ["state"], ["compose", ["edges"], ["state"]]]]], {})
        genes = {closure["id"]: closure}
        rows = [{"graph": graph(n, [(i, i + 1) for i in range(n - 1)]), "expected": (n - 1) * (n - 2) // 2} for n in range(3, 8)]
        result = synthesize(rows, genes)
        p = result["program"]
        self.assertIsNotNone(p)
        self.assertIn(closure["id"], str(p["tree"]))
        self.assertEqual(isolated(p, [graph(4, [(0, 1), (0, 2), (1, 3), (2, 3)])], genes), [1])

    def test_source_is_parsed_without_execution(self):
        with tempfile.TemporaryDirectory() as directory:
            marker = Path(directory) / "executed"
            text = f"open({str(marker)!r}, 'w').write('bad')\ndef a():\n    return b()\ndef b():\n    return 1\n"
            result = parse_source(text, "example")
            self.assertFalse(marker.exists())
            self.assertEqual(len(result["graph"]["edges"]), 1)

    def test_shadowing_and_duplicate_definitions_are_not_silently_resolved(self):
        text = "def f():\n return 1\ndef g(f):\n return f()\ndef h():\n return g(1)\ndef d():\n return 1\ndef d():\n return 2\n"
        result = parse_source(text, "example")
        self.assertEqual(result["ambiguous_definitions"], 2)
        self.assertEqual([(e["src"], e["dst"]) for e in result["graph"]["edges"]], [("example:h", "example:g")])

    def test_induced_views_are_distinct_and_retain_source_edges(self):
        original = graph(20, [(i, i + 1) for i in range(19)])
        views = graph_views(original)
        self.assertEqual(len({digest(v) for v in views}), 12)
        for view in views:
            self.assertTrue(all(e in original["edges"] for e in view["edges"]))

    def test_ssrf_and_url_credentials_are_rejected_without_network(self):
        for url in ("http://example.org/a", "https://localhost/a", "https://127.0.0.1/a",
                    "https://[::1]/a", "https://u:p@example.org/a", "https://example.org:444/a"):
            with self.subTest(url=url), self.assertRaises(ContractError):
                public_url(url, resolve=False)


class SuccessorRuntimeTests(unittest.TestCase):
    def _run_one(self, path):
        with patch("nova_next.network.fetch", side_effect=receipt), Kernel(path, create=True, feeds=[feed(i) for i in range(1, 7)]) as kernel:
            actions = []
            for _ in range(12):
                action = kernel.step()
                actions.append(action)
                if action["status"] == "ADMITTED":
                    break
            self.assertEqual(actions[-1]["status"], "ADMITTED")
            return kernel.export(), actions

    def test_actual_pipeline_freezes_before_fresh_and_preserves_legacy(self):
        with tempfile.TemporaryDirectory() as directory:
            exported, actions = self._run_one(Path(directory) / "state.sqlite")
            last = actions[-1]
            self.assertEqual(last["fresh"]["passed"], 24)
            self.assertEqual(last["legacy_regression"]["passed"], 192)
            kinds = [e["kind"] for e in exported["events"]]
            freeze = kinds.index("proposal")
            fresh = [i for i, e in enumerate(exported["events"]) if e["kind"] == "request" and e["body"]["role"] == "fresh"]
            self.assertTrue(all(i > freeze for i in fresh))

    def test_semantic_replay_restart_and_rollback(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "state.sqlite"
            exported, _ = self._run_one(path)
            restored = Path(directory) / "restored.sqlite"
            result = Kernel.restore(exported, restored)
            self.assertEqual(result["generation"], 1)
            self.assertEqual(result["head"], exported["head"])
            with Kernel(restored) as kernel:
                self.assertEqual(kernel.rollback(0)["generation"], 0)
                self.assertEqual(kernel.status()["admissions_total"], 1)
                with self.assertRaises(ContractError):
                    kernel.rollback(1)
            with Kernel(restored) as kernel:
                self.assertEqual(kernel.status()["generation"], 0)

    def test_rehashed_forged_candidate_cannot_pass_replay(self):
        with tempfile.TemporaryDirectory() as directory:
            exported, _ = self._run_one(Path(directory) / "state.sqlite")
            event = next(e for e in exported["events"] if e["kind"] == "proposal")
            event["body"]["goal"]["utility"] = "forged goal"
            head = ZERO
            for i, e in enumerate(exported["events"], 1):
                head = digest([i, head, e])
            exported["head"] = head
            with self.assertRaises(IntegrityError):
                Kernel.restore(exported, Path(directory) / "tampered.sqlite")

    def test_rehashed_forged_admission_cannot_pass_replay(self):
        with tempfile.TemporaryDirectory() as directory:
            exported, _ = self._run_one(Path(directory) / "state.sqlite")
            event = next(e for e in exported["events"] if e["kind"] == "assessment")
            event["body"]["fresh"]["outputs"][0] += 1
            head = ZERO
            for i, e in enumerate(exported["events"], 1):
                head = digest([i, head, e])
            exported["head"] = head
            with self.assertRaises(IntegrityError):
                Kernel.restore(exported, Path(directory) / "tampered.sqlite")

    def test_known_graphs_and_origin_aliases_are_not_fresh(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "state.sqlite"
            with patch("nova_next.network.fetch", side_effect=receipt), Kernel(path, create=True, feeds=[feed(i) for i in range(1, 5)]) as kernel:
                for _ in range(3):
                    kernel.step()
                state, _, _ = kernel._load()
                self.assertIsNotNone(state["candidate"])
                with self.assertRaises(ContractError):
                    assess(state["candidate"], state["documents"], {}, [], set())
            self.assertEqual(origin(feed(1)["url"]), origin(feed(1)["url"].replace("code.py", "other.py")))

    def test_failed_network_is_recorded_and_not_admitted(self):
        with tempfile.TemporaryDirectory() as directory:
            with Kernel(Path(directory) / "state.sqlite", create=True) as kernel:
                with patch("nova_next.network.fetch", side_effect=TimeoutError("test transport failure")):
                    self.assertEqual(kernel.step()["status"], "FETCH_FAILED")
                self.assertEqual(kernel.status()["generation"], 0)
                self.assertEqual(kernel.status()["source_failures"], 1)

    def test_ambiguous_state_prediction_abstains(self):
        with tempfile.TemporaryDirectory() as directory:
            with Kernel(Path(directory) / "state.sqlite", create=True) as kernel:
                kernel.observe_states("one", {"transitions": [{"seq": i, "action": "change", "before": {"n": 1}, "after": {"n": 3}} for i in range(4)]})
                self.assertEqual(kernel.predict_state("one", "change", {"n": 5})["status"], "AMBIGUOUS")
                self.assertEqual(kernel.status()["generation"], 0)


if __name__ == "__main__":
    unittest.main()

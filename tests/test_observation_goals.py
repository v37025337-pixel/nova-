"""Observation-originated decisions must be measured, replayable and gated."""

import hashlib
import json
import tempfile
import unittest
from pathlib import Path

from nova_core.contracts import ContractError, IntegrityError, decode, digest, encode
from nova_core.kernel import Kernel


def document(index, rows, **changes):
    text = json.dumps({"records": rows})
    return {"source": f"https://data.example.org/stream/{index}",
            "media_type": "application/json", "text": text,
            "sha256": hashlib.sha256(text.encode()).hexdigest(),
            "obtained_at": "fixture", **changes}


class ObservationGoalTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.path = Path(self.tmp.name) / "state.sqlite"
        self.kernel = Kernel(self.path, create=True)
        self.kernel.start_autonomy()

    def tearDown(self):
        self.kernel.close()
        self.tmp.cleanup()

    def feed(self, identity=False):
        for i in range(3):
            self.kernel.observe(document(i, [
                {"a": x, "b": x if identity else x + 1}
                for x in range(10 + i * 10, 18 + i * 10)]))

    def freeze(self):
        self.feed()
        goal = self.kernel.step()
        self.assertEqual(goal.get("phase"), "GOAL_FROZEN")
        self.assertEqual(self.kernel.step()["phase"], "SEARCH_FROZEN")
        candidate = self.kernel.step()
        self.assertEqual(candidate["status"], "FROZEN")
        return goal["goal"], candidate

    def fresh(self, goal):
        field = goal["observation_contract"]["input_field"]
        return [{"input": {field: x}, "output": x + 1 if field == "a" else x - 1}
                for x in range(101, 117)]

    def test_unlabelled_records_produce_a_measured_goal_without_registered_tasks(self):
        self.feed()
        result = self.kernel.step()
        self.assertEqual(result.get("phase"), "GOAL_FROZEN")
        goal = result["goal"]
        self.assertEqual(goal["origin"], "native_observation_prediction_error")
        self.assertEqual(len(self.kernel._load()[0]["tasks"]), 0)
        self.assertGreaterEqual(goal["prediction_evidence"]["failed"], 3)
        self.assertGreaterEqual(len(goal["evidence_sources"]), 2)
        self.assertEqual(goal["contract"]["success_threshold"], 1)
        self.assertFalse(goal["predictability_proven"])

    def test_empty_or_already_predictable_stream_does_not_invent_a_deficit(self):
        self.assertEqual(self.kernel.step()["status"], "IDLE")
        self.feed(identity=True)
        self.assertEqual(self.kernel.step()["status"], "IDLE")

    def test_duplicate_payloads_do_not_become_independent_evidence(self):
        raw = document(0, [{"a": x, "b": x + 1} for x in range(20)])
        self.kernel.observe(raw)
        for i in range(1, 4):
            self.kernel.observe({**raw, "source": f"https://data.example.org/stream/{i}"})
        self.assertEqual(self.kernel.step()["status"], "IDLE")

    def test_malformed_or_changed_payload_is_rejected_without_mutation(self):
        head = self.kernel.status()["head"]
        for raw in (document(1, [], sha256="0" * 64),
                    document(1, [], source="http://data.example.org/"),
                    document(1, [], text="{", sha256=hashlib.sha256(b"{").hexdigest())):
            with self.subTest(raw=raw), self.assertRaises(ContractError):
                self.kernel.observe(raw)
            self.assertEqual(self.kernel.status()["head"], head)

    def test_fresh_gate_restart_and_rollback(self):
        goal, frozen = self.freeze()
        result = self.kernel.autonomy_assess(frozen["freeze"], self.fresh(goal))
        self.assertEqual(result["status"], "ADMITTED")
        self.assertEqual(result["report"]["fresh"]["passed"], 16)
        self.assertEqual(result["report"]["observation_baseline"]["passed"], 0)
        head = self.kernel.status()["head"]
        self.kernel.close()
        self.kernel = Kernel(self.path)
        self.assertEqual(self.kernel.audit(expected_head=head)["status"], "PASS")
        row = self.fresh(goal)[0]
        self.assertEqual(self.kernel.predict(goal["id"], row["input"]), row["output"])
        self.kernel.rollback(0)
        with self.assertRaises(ContractError):
            self.kernel.predict(goal["id"], row["input"])

    def test_observed_inputs_and_failed_assessments_cannot_be_reused_as_fresh(self):
        goal, frozen = self.freeze()
        rows = self.fresh(goal)
        field = goal["observation_contract"]["input_field"]
        rows[0] = {"input": {field: 37 if field == "a" else 38},
                   "output": 38 if field == "a" else 37}
        with self.assertRaises(ContractError):
            self.kernel.autonomy_assess(frozen["freeze"], rows)
        rows = self.fresh(goal)
        rows[0]["output"] = -100
        self.assertEqual(self.kernel.autonomy_assess(frozen["freeze"], rows)["status"], "WITHHOLD")
        self.assertEqual(self.kernel.status()["active_generation"], 0)
        with self.assertRaises(ContractError):
            self.kernel.autonomy_assess(frozen["freeze"], self.fresh(goal))

    def test_rehashed_fabricated_prediction_evidence_fails_semantic_replay(self):
        self.feed()
        self.kernel.step()
        db = self.kernel.journal.db
        seq, prev, raw = db.execute("SELECT seq,prev,body FROM events ORDER BY seq DESC LIMIT 1").fetchone()
        body = decode(raw)
        body["goal"]["prediction_evidence"]["failed"] = 0
        body["freeze"] = digest(body["goal"])
        db.execute("UPDATE events SET body=?,hash=? WHERE seq=?", (encode(body), digest([seq, prev, body]), seq))
        with self.assertRaises(IntegrityError):
            self.kernel.audit()

    def test_rolling_window_preserves_old_input_and_duplicate_exclusions(self):
        goal, frozen = self.freeze()
        raw = document("seen", [{"a": 101, "b": 102}])
        self.kernel.observe(raw)
        for i in range(33):
            self.kernel.observe(document(f"later-{i}", [{"a": 1000 + i, "b": 2000 + i}]))
        self.assertEqual(self.kernel.status()["observations"]["window_documents"], 32)
        self.assertEqual(self.kernel.observe(raw)["status"], "DUPLICATE")
        rows = self.fresh(goal)
        field = goal["observation_contract"]["input_field"]
        rows[0] = {"input": {field: 101 if field == "a" else 102},
                   "output": 102 if field == "a" else 101}
        with self.assertRaises(ContractError):
            self.kernel.autonomy_assess(frozen["freeze"], rows)

    def test_csv_width_duplicate_headers_and_nested_path_identity(self):
        for text in ("a,a\n1,2\n", "a,b\n1,2,3\n", "a,b\n1\n"):
            raw = document("csv", [], media_type="text/csv", text=text,
                           sha256=hashlib.sha256(text.encode()).hexdigest())
            with self.subTest(text=text), self.assertRaises(ContractError):
                self.kernel.observe(raw)
        raw = document("paths", [])
        raw["text"] = json.dumps({"a/b": [{"x": 1, "y": 2}], "a": {"b": [{"x": 3, "y": 4}]}})
        raw["sha256"] = hashlib.sha256(raw["text"].encode()).hexdigest()
        self.kernel.observe(raw)
        records = self.kernel._load()[0]["observations"][-1]["records"]
        self.assertEqual(len({r["path"] for r in records}), 2)


if __name__ == "__main__":
    unittest.main()

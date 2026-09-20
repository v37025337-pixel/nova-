import json
import tempfile
import unittest
from pathlib import Path

from nova_core.contracts import ContractError, IntegrityError, decode, digest, encode
from nova_core.kernel import Kernel
from nova_core.compatibility import legacy_manifest
from nova_core.memory import Journal, ZERO
from tests.test_kernel import example_task


def engine_trial(name="search-v2", bad=False):
    values = ['"  Luna "', '" Oslo  "', '" naïve "', '" İzmir  "']
    task = {"id": "deep-validation", "source": "test:engine-validation-independent-inputs",
            "train": [{"input": {"payload": x}, "output": json.dumps(json.loads(x).strip().upper(), ensure_ascii=False)} for x in values[:2]],
            "holdout": [{"input": {"payload": x}, "output": json.dumps(json.loads(x).strip().upper(), ensure_ascii=False)} for x in values[2:]]}
    if bad:
        task["holdout"][0]["output"] = "incorrect oracle"
    return {"id": name, "tasks": [task]}


class EngineEvolutionTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.path = Path(self.tmp.name) / "state.sqlite"
        self.kernel = Kernel(self.path, create=True)
        self.kernel.register([example_task("a"), example_task("b", lambda s: s.strip().upper())])
        self.kernel.develop(2)

    def tearDown(self):
        self.kernel.close()
        self.tmp.cleanup()

    def evolve(self, trial=None):
        self.kernel.register_engine_trial(trial or engine_trial())
        return self.kernel.step()

    def test_native_policy_admission_continuation_restart_and_rollback(self):
        before = self.kernel.genome()
        record = self.evolve()
        self.assertEqual(record["status"], "ADMITTED")
        self.assertEqual(record["mutation"]["kind"], "EVOLVE_ENGINE_POLICY")
        policy = self.kernel.genome()["engine"]
        self.assertEqual(record["engine_candidate"], policy)
        self.assertLess(record["gate"]["training"]["candidate_attempts"], record["gate"]["training"]["parent_attempts"])
        self.assertEqual(record["mutation"]["child_genome"]["bindings"], before["bindings"])
        task = engine_trial()["tasks"][0]
        task["id"] = "next-step"
        task["train"] = [{"input": {"payload": '"  Tokyo "'}, "output": '"TOKYO"'}, {"input": {"payload": '"  Rome "'}, "output": '"ROME"'}]
        task["holdout"] = [{"input": {"payload": '" Zürich "'}, "output": '"ZÜRICH"'}, {"input": {"payload": '" Lima "'}, "output": '"LIMA"'}]
        self.kernel.register([task])
        next_step = self.kernel.step()
        self.assertEqual(next_step["status"], "ADMITTED")
        self.assertEqual(next_step["selection"]["plan"]["engine"], policy["id"])
        self.assertEqual(self.kernel.predict("next-step", {"payload": '"  Berlin "'}), '"BERLIN"')
        self.kernel.close()
        self.kernel = Kernel(self.path)
        self.assertEqual(self.kernel.audit()["status"], "PASS")
        self.kernel.rollback(2)
        self.assertEqual(self.kernel.genome(), before)
        self.assertEqual(self.kernel.predict("a", {"text": " old skill "}), "old skill")

    def test_failed_validation_preserves_engine_and_consumes_trial(self):
        before = self.kernel.genome()
        bad = engine_trial(bad=True)
        record = self.evolve(bad)
        self.assertEqual(record["status"], "WITHHOLD")
        self.assertEqual(record["reason"], "ENGINE_VALIDATION_FAILED")
        self.assertEqual(self.kernel.genome(), before)
        self.assertEqual(self.kernel.step()["status"], "IDLE")
        bad["id"] = "renamed-trial"
        with self.assertRaises(ContractError):
            self.kernel.register_engine_trial(bad)
        self.assertEqual(self.kernel.step()["status"], "IDLE")

    def test_forged_policy_receipt_is_rejected_even_with_valid_hash(self):
        self.evolve()
        db = self.kernel.journal.db
        seq, prev, raw = db.execute("SELECT seq,prev,body FROM events ORDER BY seq DESC LIMIT 1").fetchone()
        body = decode(raw)
        body["engine_candidate"]["depth"] = 99
        db.execute("UPDATE events SET body=?,hash=? WHERE seq=?", (encode(body), digest([seq, prev, body]), seq))
        with self.assertRaises(IntegrityError):
            self.kernel.audit()

    def test_trial_cannot_reuse_existing_evaluation_inputs(self):
        with self.assertRaises(ContractError):
            self.kernel.register_engine_trial({"id": "leaked", "tasks": [example_task("a")]})

    def test_cached_reads_do_not_hide_rehashed_history_tampering(self):
        self.kernel.status()
        events, _ = self.kernel.journal.read()
        events[2]["gate"]["holdout"]["passed"] = 0
        previous = "0" * 64
        for seq, body in enumerate(events, 1):
            hashed = digest([seq, previous, body])
            self.kernel.journal.db.execute("UPDATE events SET prev=?,body=?,hash=? WHERE seq=?", (previous, encode(body), hashed, seq))
            previous = hashed
        with self.assertRaises(IntegrityError):
            self.kernel.status()

    def legacy_copy(self):
        events, _ = self.kernel.journal.read()
        events[0]["manifest"] = legacy_manifest()
        path = Path(self.tmp.name) / "legacy.sqlite"
        journal = Journal(path, create=True)
        try:
            head = ZERO
            for body in events:
                head = journal.append(body, head)
        finally:
            journal.close()
        return path, events, head

    def test_explicit_upgrade_preserves_legacy_prefix_and_all_skills(self):
        path, original, head = self.legacy_copy()
        with Kernel(path) as legacy:
            self.assertTrue(legacy.audit(expected_head=head)["upgrade_required"])
            self.assertEqual(legacy.predict("b", {"text": "  intact  "}), "INTACT")
            with self.assertRaises(ContractError):
                legacy.step()
            with self.assertRaises(ContractError):
                legacy.register([example_task("new")])
            result = legacy.upgrade()
            self.assertEqual(result["status"], "UPGRADED")
            events, _ = legacy.journal.read()
            self.assertEqual(encode(events[:-1]), encode(original))
            self.assertEqual(events[-1]["previous_head"], head)
            self.assertEqual(result["state"]["active_generation"], 2)
            legacy.register_engine_trial(engine_trial())
            self.assertEqual(legacy.step()["status"], "ADMITTED")
        with Kernel(path) as restored:
            self.assertFalse(restored.audit()["upgrade_required"])
            self.assertEqual(restored.predict("b", {"text": " old memory "}), "OLD MEMORY")

    def test_forged_upgrade_anchor_rejected_after_rehash(self):
        path, _, _ = self.legacy_copy()
        with Kernel(path) as legacy:
            legacy.upgrade()
            db = legacy.journal.db
            seq, prev, raw = db.execute("SELECT seq,prev,body FROM events ORDER BY seq DESC LIMIT 1").fetchone()
            body = decode(raw)
            body["previous_head"] = "0" * 64
            db.execute("UPDATE events SET body=?,hash=? WHERE seq=?", (encode(body), digest([seq, prev, body]), seq))
            with self.assertRaises(IntegrityError):
                legacy.audit()

    def test_adaptive_search_preserves_numeric_and_boolean_contracts(self):
        self.evolve()
        from nova_core.language import execute
        from nova_core.synthesis import synthesize
        policy = self.kernel.genome()["engine"]
        rows = [{"input": {"a": 3, "b": 5}, "output": 15},
                {"input": {"a": 7, "b": 4}, "output": 28}]
        program = synthesize(rows, {}, policy)["program"]
        self.assertIsNotNone(program)
        self.assertEqual(execute(program, {"a": -2, "b": 6}, {}), -12)
        with self.assertRaises(ContractError):
            execute(program, {"a": True, "b": 6}, {})


if __name__ == "__main__":
    unittest.main()

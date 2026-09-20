import copy
import json
import tempfile
import unittest
from pathlib import Path

from nova_core.contracts import ContractError, IntegrityError, StaleState, decode, digest, encode
from nova_core.kernel import Kernel


def example_task(name="trim", transform=str.strip):
    def rows(values):
        return [{"input": {"text": s}, "output": transform(s)} for s in values]
    return {"id": name, "source": "test:independent-string-examples",
            "train": rows(["  Alice ", " Bob  ", "  Straße   "]),
            "holdout": rows(["  Carol  ", " dAVID ", "\téva \n"])}


class KernelTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.path = Path(self.tmp.name) / "nova.sqlite"
        self.kernel = Kernel(self.path, create=True)

    def tearDown(self):
        self.kernel.close()
        self.tmp.cleanup()

    def learn(self, task=None):
        self.kernel.register([task or example_task()])
        return self.kernel.step()

    def restart(self):
        self.kernel.close()
        self.kernel = Kernel(self.path)

    def test_learn_execute_restart_and_replay(self):
        result = self.learn()
        self.assertEqual(result["status"], "ADMITTED")
        self.assertEqual(self.kernel.predict("trim", {"text": "  нового дня \n"}), "нового дня")
        before = self.kernel.status()
        self.restart()
        self.assertEqual(self.kernel.status(), before)
        self.assertEqual(self.kernel.audit()["status"], "PASS")

    def test_three_admissions_reuse_predecessor_programs(self):
        tasks = [example_task("10-trim"),
                 example_task("20-normalize", lambda s: s.strip().upper()),
                 example_task("30-record", lambda s: {"name": s.strip().upper(), "length": len(s.strip().upper())})]
        self.kernel.register(tasks)
        records = self.kernel.develop(3)["steps"]
        self.assertEqual([r["status"] for r in records], ["ADMITTED"] * 3)
        for previous, current in zip(records, records[1:]):
            self.assertIn(previous["program"]["id"], current["program"]["parents"])
            self.assertEqual(current["parent_generation"], previous["generation"])
            self.assertTrue(all(x["failed_without_parent"] for x in current["gate"]["ablation"]))
        self.assertEqual(self.kernel.predict("30-record", {"text": "  weiß\n"}), {"name": "WEISS", "length": 5})
        self.assertEqual(self.kernel.step()["status"], "IDLE")

    def test_bad_holdout_never_admitted_or_reused(self):
        task = example_task()
        task["holdout"][0]["output"] = "deliberately wrong"
        result = self.learn(task)
        self.assertEqual(result["status"], "WITHHOLD")
        self.assertEqual(result["reason"], "HOLDOUT_FAILED")
        self.assertEqual(self.kernel.status()["active_generation"], 0)
        self.assertEqual(self.kernel.step()["status"], "IDLE")
        alias = copy.deepcopy(task)
        alias["id"] = "renamed"
        self.kernel.register([alias])
        self.assertEqual(self.kernel.step()["status"], "IDLE")

    def test_input_overlap_rejected_before_any_event(self):
        task = example_task()
        task["holdout"][0] = copy.deepcopy(task["train"][0])
        before = self.kernel.status()
        with self.assertRaises(ContractError):
            self.kernel.register([task])
        self.assertEqual(self.kernel.status(), before)

    def test_registration_atomic_and_task_immutable(self):
        task = example_task()
        self.kernel.register([task])
        changed = copy.deepcopy(task)
        changed["source"] = "changed"
        before = self.kernel.status()
        with self.assertRaises(ContractError):
            self.kernel.register([example_task("another"), changed])
        self.assertEqual(self.kernel.status(), before)
        self.kernel.register([task])
        self.assertEqual(self.kernel.status(), before)

    def test_rollback_survives_restart_and_preserves_history(self):
        self.kernel.register([example_task("a"), example_task("b", lambda s: s.strip().upper())])
        first, second = self.kernel.step(), self.kernel.step()
        self.kernel.rollback(first["generation"])
        self.restart()
        self.assertEqual(self.kernel.status()["active_generation"], first["generation"])
        self.assertEqual(self.kernel.status()["admissions_total"], 2)
        self.assertEqual(self.kernel.predict("a", {"text": " x "}), "x")
        with self.assertRaises(ContractError):
            self.kernel.predict("b", {"text": " x "})
        with self.assertRaises(ContractError):
            self.kernel.rollback(second["generation"])
        self.assertEqual(self.kernel.audit()["status"], "PASS")

    def test_online_backup_is_restorable(self):
        self.learn()
        backup = Path(self.tmp.name) / "backup.sqlite"
        self.kernel.backup(backup)
        with Kernel(backup) as restored:
            self.assertEqual(restored.status(), self.kernel.status())
            self.assertEqual(restored.predict("trim", {"text": " abc "}), "abc")
        with self.assertRaises(ContractError):
            self.kernel.backup(backup)

    def test_stale_writer_cannot_append(self):
        old_head = self.kernel.status()["head"]
        self.kernel.register([example_task()])
        with self.assertRaises(StaleState):
            self.kernel.journal.append({"kind": "rollback", "target": 0}, old_head)
        self.assertEqual(self.kernel.audit()["status"], "PASS")

    def test_broken_hash_detected(self):
        self.learn()
        self.kernel.journal.db.execute("UPDATE events SET hash=? WHERE seq=2", ("f" * 64,))
        with self.assertRaises(IntegrityError):
            self.kernel.audit()

    def test_rehashed_false_receipt_detected(self):
        self.learn()
        db = self.kernel.journal.db
        seq, prev, raw, _ = db.execute("SELECT seq,prev,body,hash FROM events ORDER BY seq DESC LIMIT 1").fetchone()
        body = decode(raw)
        body["gate"]["holdout"]["passed"] = 0
        rewritten = encode(body)
        db.execute("UPDATE events SET body=?,hash=? WHERE seq=?", (rewritten, digest([seq, prev, body]), seq))
        with self.assertRaises(IntegrityError):
            self.kernel.audit()

    def test_tail_truncation_detected_with_external_head(self):
        self.learn()
        expected = self.kernel.status()["head"]
        self.kernel.journal.db.execute("DELETE FROM events WHERE seq=(SELECT MAX(seq) FROM events)")
        with self.assertRaises(IntegrityError):
            self.kernel.audit(expected_head=expected)

    def test_missing_database_not_silently_recreated(self):
        with self.assertRaises(ContractError):
            Kernel(Path(self.tmp.name) / "missing.sqlite")

    def test_new_memory_reopens_an_exhausted_goal(self):
        values = ['"  Alice "', '" Bob  "', '" Straße  "', '" Carol  "', '" David  "']
        def task(name, fn):
            return {"id": name, "source": "test:memory-transfer",
                    "train": [{"input": {"text": s}, "output": fn(s)} for s in values[:3]],
                    "holdout": [{"input": {"text": s}, "output": fn(s)} for s in values[3:]]}
        self.kernel.register([
            task("10-deep", lambda s: json.dumps(json.loads(s).strip().upper(), ensure_ascii=False)),
            task("20-parse", json.loads)])
        first, second, third = [self.kernel.step() for _ in range(3)]
        self.assertEqual(first["reason"], "SEARCH_EXHAUSTED")
        self.assertEqual(second["status"], "ADMITTED")
        self.assertEqual(third["status"], "ADMITTED")
        self.assertEqual(first["selection"]["task"], third["selection"]["task"])
        self.assertNotEqual(first["selection"]["memory_context"], third["selection"]["memory_context"])
        self.assertIn(second["program"]["id"], third["program"]["parents"])
        self.restart()
        self.assertEqual(self.kernel.predict("10-deep", {"text": '"  другой мир  "'}), '"ДРУГОЙ МИР"')

    def test_concurrent_writers_publish_exactly_one_event(self):
        from concurrent.futures import ThreadPoolExecutor
        from threading import Barrier
        from nova_core.memory import Journal
        barrier = Barrier(2)
        head = self.kernel.status()["head"]
        def writer(name):
            journal = Journal(self.path)
            try:
                barrier.wait(timeout=5)
                journal.append({"kind": "tasks", "tasks": [example_task(name)]}, head)
                return "committed"
            except StaleState:
                return "stale"
            finally:
                journal.close()
        with ThreadPoolExecutor(max_workers=2) as pool:
            outcomes = list(pool.map(writer, ["a", "b"]))
        self.assertEqual(sorted(outcomes), ["committed", "stale"])
        self.assertEqual(self.kernel.status()["tasks_total"], 1)
        self.assertEqual(self.kernel.audit()["status"], "PASS")

    def test_uncommitted_write_does_not_survive_connection_loss(self):
        before = self.kernel.status()
        body = {"kind": "tasks", "tasks": [example_task()]}
        db = self.kernel.journal.db
        db.execute("BEGIN IMMEDIATE")
        db.execute("INSERT INTO events VALUES (?,?,?,?)", (2, before["head"], encode(body), digest([2, before["head"], body])))
        self.restart()
        self.assertEqual(self.kernel.status(), before)

    def test_runtime_manifest_mismatch_fails_on_restart(self):
        db = self.kernel.journal.db
        row = db.execute("SELECT seq,prev,body FROM events WHERE seq=1").fetchone()
        body = decode(row[2])
        body["manifest"]["sources"]["kernel.py"] = "0" * 64
        db.execute("UPDATE events SET body=?,hash=? WHERE seq=1", (encode(body), digest([1, row[1], body])))
        with self.assertRaises(IntegrityError):
            Kernel(self.path)

    def test_generation_float_alias_rejected_even_after_rehash(self):
        self.learn()
        db = self.kernel.journal.db
        seq, prev, raw = db.execute("SELECT seq,prev,body FROM events ORDER BY seq DESC LIMIT 1").fetchone()
        body = decode(raw)
        body["generation"] = 1.0
        db.execute("UPDATE events SET body=?,hash=? WHERE seq=?", (encode(body), digest([seq, prev, body]), seq))
        with self.assertRaises(IntegrityError):
            self.kernel.audit()

    def test_genome_inheritance_and_exact_rollback(self):
        birth = self.kernel.genome()
        self.kernel.register([example_task("a"), example_task("b", lambda s: s.strip().upper())])
        first = self.kernel.step()
        parent = self.kernel.genome()
        second = self.kernel.step()
        child = self.kernel.genome()
        self.assertEqual(parent["parent"], birth["id"])
        self.assertEqual(child["parent"], parent["id"])
        self.assertEqual(second["mutation"]["kind"], "COMPOSE_AND_ADD_GENE")
        self.assertTrue(set(parent["genes"]) < set(child["genes"]))
        self.assertEqual(second["gate"]["genetics"]["candidate_genome"], child["id"])
        self.kernel.rollback(first["generation"])
        self.restart()
        self.assertEqual(self.kernel.genome(), parent)

    def test_common_workspace_queue_and_causal_memory(self):
        self.kernel.register([example_task("a"), example_task("b", lambda s: s.strip().upper())])
        self.assertEqual([r["status"] for r in self.kernel.queue()], ["PENDING", "PENDING"])
        first, second = self.kernel.develop(2)["steps"]
        for step in (first, second):
            self.assertEqual(set(step["workspace"]), {"context", "CODE", "LOGIC", "THINKING", "INTELLIGENCE"})
            self.assertEqual(step["workspace"]["CODE"]["program"], step["program"]["id"])
            self.assertEqual(step["workspace"]["LOGIC"]["evidence"], digest(step["gate"]))
        causes = second["workspace"]["THINKING"]["causes"]
        self.assertEqual(causes["gene_events"][first["program"]["id"]], first["event"])
        memory = self.kernel.causal_memory()
        self.assertEqual(memory["experiences"]["b"][0]["context"], second["workspace"]["context"])
        self.restart()
        self.assertEqual(self.kernel.causal_memory(), memory)
        self.assertEqual([r["status"] for r in self.kernel.queue()], ["ADMITTED", "ADMITTED"])

    def test_false_mutation_is_rejected_after_rehash(self):
        self.learn()
        db = self.kernel.journal.db
        seq, prev, raw = db.execute("SELECT seq,prev,body FROM events ORDER BY seq DESC LIMIT 1").fetchone()
        body = decode(raw)
        body["mutation"]["child_genome"]["bindings"]["trim"] = "f" * 64
        db.execute("UPDATE events SET body=?,hash=? WHERE seq=?", (encode(body), digest([seq, prev, body]), seq))
        with self.assertRaises(IntegrityError):
            self.kernel.audit()

    def test_missing_faculty_receipt_invalidates_step(self):
        self.learn()
        db = self.kernel.journal.db
        seq, prev, raw = db.execute("SELECT seq,prev,body FROM events ORDER BY seq DESC LIMIT 1").fetchone()
        body = decode(raw)
        del body["workspace"]["INTELLIGENCE"]
        db.execute("UPDATE events SET body=?,hash=? WHERE seq=?", (encode(body), digest([seq, prev, body]), seq))
        with self.assertRaises(IntegrityError):
            self.kernel.audit()

    def test_oversized_event_is_rejected_before_commit(self):
        before = self.kernel.status()
        with self.assertRaises(ContractError):
            self.kernel.journal.append({"data": "я" * 1_000_001}, before["head"])
        self.assertEqual(self.kernel.status(), before)

    def test_birth_manifest_requires_exact_field_types(self):
        db = self.kernel.journal.db
        seq, prev, raw = db.execute("SELECT seq,prev,body FROM events WHERE seq=1").fetchone()
        body = decode(raw)
        body["manifest"]["search"]["depth"] = 3.0
        db.execute("UPDATE events SET body=?,hash=? WHERE seq=1", (encode(body), digest([seq, prev, body])))
        with self.assertRaises(IntegrityError):
            self.kernel.audit()


if __name__ == "__main__":
    unittest.main()

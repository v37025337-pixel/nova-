"""Independent contracts for endogenous goals, frozen I/O and admission."""

import hashlib
import tempfile
import unittest
from pathlib import Path

from nova_core import autonomy
from nova_core.contracts import ContractError, IntegrityError, decode, digest, encode
from nova_core.kernel import Kernel


def failed_permutation():
    training = [[1, 4, 7, 10, 15], [2, 5, 8, 11, 16]]
    heldout = [[30, 19, 24, 21, 27], [32, 13, 28, 15, 22]]
    return {"id": "ordinary-observed-failure", "source": "test:permutation-observations",
            "train": [{"input": {"values": v}, "output": sorted(v)} for v in training],
            "holdout": [{"input": {"values": v}, "output": sorted(v)} for v in heldout]}


def fresh_rows():
    rows = []
    for i in range(8):
        left, right = 101 + i * 7, 300 + i * 11
        rows.extend([{"input": {"left": left, "right": right}, "output": True},
                     {"input": {"left": right, "right": left}, "output": False}])
    return rows


class AutonomyTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.path = Path(self.tmp.name) / "state.sqlite"
        self.kernel = Kernel(self.path, create=True)

    def tearDown(self):
        self.kernel.close()
        self.tmp.cleanup()

    def goal(self):
        self.kernel.register([failed_permutation()])
        self.assertEqual(self.kernel.step()["reason"], "HOLDOUT_FAILED")
        self.assertEqual(self.kernel.step()["status"], "IDLE")
        self.kernel.start_autonomy()
        goal = self.kernel.step()
        self.assertEqual(goal["phase"], "GOAL_FROZEN")
        return goal

    def sources(self):
        self.kernel.step()  # native change type
        search = self.kernel.step()["request"]
        self.assertEqual(search["kind"], "SEARCH")
        self.kernel.autonomy_response({"kind": "SEARCH_RESULTS", "request": search["id"], "results": [
            {"url": "https://docs.python.org/3/reference/expressions.html", "title": "Numeric comparisons",
             "snippet": "Numeric comparison ordering specification"}]})
        read = self.kernel.step()["request"]
        self.assertEqual(read["kind"], "READ")
        text = "Comparisons of numeric values use their mathematical order."
        response = {"kind": "DOCUMENT", "request": read["id"], "url": read["url"], "title": read["title"],
                    "text": text, "sha256": hashlib.sha256(text.encode()).hexdigest(),
                    "source_sha256": hashlib.sha256(text.encode()).hexdigest(), "obtained_at": "test-fixture"}
        return response

    def frozen(self):
        goal = self.goal()
        self.kernel.autonomy_response(self.sources())
        self.assertEqual(self.kernel.step()["phase"], "SEARCH_FROZEN")
        frozen = self.kernel.step()
        self.assertEqual(frozen["status"], "FROZEN")
        return goal, frozen

    def test_goal_is_derived_not_registered_and_frozen_before_code(self):
        record = self.goal()
        goal = record["goal"]
        self.assertNotEqual(goal["id"], goal["root_task"])
        self.assertEqual(goal["root_task_origin"], "operator")
        self.assertEqual(goal["observed_failure"], "HOLDOUT_FAILED")
        self.assertEqual(goal["contract"]["law"], "numeric_less")
        self.assertEqual(record["freeze"], digest(goal))
        self.assertEqual(goal["contract"]["success_threshold"], 1)
        self.assertNotIn(goal["id"], self.kernel._load()[0]["tasks"])
        self.assertFalse(self.kernel.status()["autonomy"]["autonomous_capability_evolution_proven"])

    def test_missing_error_evidence_never_invents_a_goal(self):
        self.kernel.start_autonomy()
        self.assertEqual(self.kernel.step()["reason"], "NO_SUPPORTED_ENDOGENOUS_DEFICIT")

    def test_wrong_source_and_hash_are_rejected_without_journal_write(self):
        self.goal()
        response = self.sources()
        head = self.kernel.status()["head"]
        with self.assertRaises(ContractError):
            self.kernel.autonomy_response({**response, "url": "https://docs.python.org/another"})
        with self.assertRaises(ContractError):
            self.kernel.autonomy_response({**response, "text": "changed after hashing"})
        self.assertEqual(self.kernel.status()["head"], head)

    def test_source_rank_is_deterministic_and_domain_boundary_is_enforced(self):
        goal = {"search_terms": ["numeric", "ordering"]}
        rows = [{"url": "https://docs.python.org/3/index.html", "title": "Manual", "snippet": "Reference"},
                {"url": "https://peps.python.org/pep-0440/", "title": "Numeric version ordering", "snippet": "Ordering"}]
        self.assertEqual(autonomy.rank_sources(goal, rows)[0]["url"], rows[1]["url"])
        for url in ("http://docs.python.org/", "https://docs.python.org.evil.example/", "https://127.0.0.1/",
                    "https://x:y@docs.python.org/", "https://docs.python.org:444/"):
            with self.subTest(url=url), self.assertRaises(ContractError):
                autonomy.source_url(url)

    def test_fresh_admission_isolated_restart_and_rollback(self):
        goal, frozen = self.frozen()
        result = self.kernel.autonomy_assess(frozen["freeze"], fresh_rows())
        self.assertEqual(result["status"], "ADMITTED")
        self.assertEqual(result["report"]["fresh"]["passed"], 16)
        self.assertEqual(result["report"]["isolation"], "linux_seccomp_v1")
        self.assertTrue(self.kernel.predict(goal["goal"]["id"], {"left": -20, "right": 0}))
        head = self.kernel.status()["head"]
        self.kernel.close()
        self.kernel = Kernel(self.path)
        self.assertEqual(self.kernel.audit(expected_head=head)["status"], "PASS")
        self.kernel.rollback(0)
        with self.assertRaises(ContractError):
            self.kernel.predict(goal["goal"]["id"], {"left": -20, "right": 0})
        self.assertEqual(self.kernel.step()["status"], "IDLE")

    def test_failed_fresh_assessment_is_consumed_and_never_activates(self):
        _, frozen = self.frozen()
        rows = fresh_rows()
        rows[0]["output"] = False
        result = self.kernel.autonomy_assess(frozen["freeze"], rows)
        self.assertEqual(result["status"], "WITHHOLD")
        self.assertEqual(self.kernel.status()["active_generation"], 0)
        with self.assertRaises(ContractError):
            self.kernel.autonomy_assess(frozen["freeze"], fresh_rows())

    def test_known_inputs_cannot_be_relabelled_fresh(self):
        goal, frozen = self.frozen()
        rows = fresh_rows()
        rows[0] = goal["goal"]["original_holdout"][0]
        with self.assertRaises(ContractError):
            self.kernel.autonomy_assess(frozen["freeze"], rows)
        self.assertEqual(self.kernel.status()["autonomy"]["phase"], "CANDIDATE_FROZEN")

    def test_rehashed_changed_goal_fails_semantic_replay(self):
        self.goal()
        db = self.kernel.journal.db
        seq, prev, raw = db.execute("SELECT seq,prev,body FROM events ORDER BY seq DESC LIMIT 1").fetchone()
        body = decode(raw)
        body["goal"]["contract"]["success_threshold"] = 0.5
        body["freeze"] = digest(body["goal"])
        db.execute("UPDATE events SET body=?,hash=? WHERE seq=?", (encode(body), digest([seq, prev, body]), seq))
        with self.assertRaises(IntegrityError):
            self.kernel.audit()


if __name__ == "__main__":
    unittest.main()

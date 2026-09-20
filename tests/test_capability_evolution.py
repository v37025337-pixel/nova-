import copy
import json
import random
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from nova_core.contracts import ContractError, IntegrityError, decode, digest, encode
from nova_core.extensions import execute, gene, learn
from nova_core.isolation import SandboxError, evaluate
from nova_core.kernel import Kernel
from tests.test_kernel import example_task


SPEC = {"id": "word-laws", "source": "test:unsigned-word-algebra", "width": 32,
        "title": "Word equations", "text": "mix(x,y) = x ^ y\nflip(x) = ~x",
        "provenance": "maintainer_supplied_equations; kernel_generates_implementation"}


def xor_task(name="xor"):
    values = [(7, 11), (42, 19), (53, 84), (100, 79)]
    rows = [{"input": {"a": a, "b": b}, "output": a ^ b} for a, b in values]
    return {"id": name, "source": "test:independent-xor-oracle", "train": rows[:2], "holdout": rows[2:]}


def fresh_rows():
    rng = random.Random(57329)
    # Called after freeze; this oracle never participates in candidate selection.
    values = [(rng.getrandbits(32), rng.getrandbits(32)) for _ in range(12)]
    return [{"input": {"a": a, "b": b}, "output": a ^ b} for a, b in values]


class CapabilityTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.path = Path(self.tmp.name) / "state.sqlite"
        self.k = Kernel(self.path, create=True)

    def tearDown(self):
        self.k.close()
        self.tmp.cleanup()

    def freeze(self):
        self.k.register([xor_task()])
        self.assertEqual(self.k.step()["reason"], "SEARCH_EXHAUSTED")
        self.k.study(SPEC)
        body = self.k.step()
        self.assertEqual(body["status"], "FROZEN")
        self.assertEqual(body["report"]["hidden_cases_seen"], 0)
        self.assertEqual(body["workspace"]["THINKING"]["origin"], "kernel_causal_memory")
        return body

    def test_complete_native_extension_admission_transfer_restart_and_rollback(self):
        self.k.register([example_task()])
        self.k.step()
        prior = self.k.genome()
        frozen = self.freeze()
        self.assertEqual(self.k.genome(), prior)  # Freeze cannot activate a body.
        receipt = self.k.assess(frozen["freeze"], fresh_rows())
        self.assertEqual(receipt["status"], "ADMITTED")
        self.assertEqual(receipt["report"]["fresh_holdout"]["passed"], 12)
        self.assertEqual(receipt["report"]["ablation"]["without_primitive"]["passed"], 0)
        self.assertEqual(receipt["report"]["regression"]["trim"]["passed"], 6)
        self.assertEqual(self.k.predict("xor", {"a": 0xDEAD, "b": 0xBEEF}), 0x6042)
        self.assertEqual(self.k.genome()["capabilities"], [frozen["primitive"]["id"]])
        # A new task is selected by the existing queue and reuses the new gene.
        next_task = xor_task("xor-next")
        for split in ("train", "holdout"):
            for row in next_task[split]:
                row["input"]["a"] += 4096
                row["output"] = row["input"]["a"] ^ row["input"]["b"]
        self.k.register([next_task])
        continuation = self.k.step()
        self.assertEqual(continuation["selection"]["task"], "xor-next")
        self.assertEqual(continuation["status"], "ADMITTED")
        self.assertIn(frozen["primitive"]["id"], self.k.genome()["genes"])
        self.k.close()
        self.k = Kernel(self.path)
        self.assertEqual(self.k.audit()["status"], "PASS")
        self.k.rollback(1)
        self.assertEqual(self.k.genome(), prior)
        with self.assertRaises(ContractError):
            self.k.predict("xor", {"a": 1, "b": 2})
        self.assertEqual(self.k.predict("trim", {"text": " old skill "}), "old skill")
        self.assertEqual(self.k.audit()["status"], "PASS")

    def test_missing_knowledge_is_diagnosed_and_does_not_busy_loop(self):
        self.k.register([xor_task()])
        self.k.step()
        body = self.k.step()
        self.assertEqual(body["reason"], "KNOWLEDGE_MISSING")
        self.assertFalse(body["report"]["diagnosis"]["proof_of_global_impossibility"])
        self.assertEqual(self.k.step()["status"], "IDLE")
        self.k.study(SPEC)
        self.assertEqual(self.k.step()["status"], "FROZEN")

    def test_holdout_cannot_exist_in_candidate_selection_or_be_reused(self):
        frozen = self.freeze()
        count = self.k.status()["events"]
        self.assertEqual(self.k.step()["status"], "WAITING")
        self.assertEqual(self.k.status()["events"], count)
        with self.assertRaises(ContractError):
            self.k.assess(frozen["freeze"], xor_task()["holdout"])
        renamed_numbers = xor_task()["holdout"]
        for row in renamed_numbers:
            row["input"] = {key: float(value) for key, value in row["input"].items()}
        with self.assertRaises(ContractError):
            self.k.assess(frozen["freeze"], renamed_numbers)
        self.assertEqual(self.k.status()["events"], count)
        rows = fresh_rows()
        rows[0]["output"] ^= 1
        result = self.k.assess(frozen["freeze"], rows)
        self.assertEqual(result["reason"], "CAPABILITY_VALIDATION_FAILED")
        self.assertEqual(self.k.status()["active_generation"], 0)
        with self.assertRaises(ContractError):
            self.k.assess(frozen["freeze"], fresh_rows())
        self.assertEqual(self.k.step()["status"], "IDLE")

    def test_unavailable_sandbox_cannot_admit_or_consume_evaluation(self):
        frozen = self.freeze()
        before = self.k.status()
        with patch("nova_core.capability.evaluate", side_effect=SandboxError("unavailable")):
            with self.assertRaises(SandboxError):
                self.k.assess(frozen["freeze"], fresh_rows())
        self.assertEqual(self.k.status(), before)
        self.assertEqual(self.k.assess(frozen["freeze"], fresh_rows())["status"], "ADMITTED")

    def test_rehashed_forged_evaluation_is_detected_by_reexecution(self):
        frozen = self.freeze()
        self.k.assess(frozen["freeze"], fresh_rows())
        db = self.k.journal.db
        seq, prev, raw = db.execute("SELECT seq,prev,body FROM events ORDER BY seq DESC LIMIT 1").fetchone()
        body = decode(raw)
        body["report"]["fresh_holdout"]["passed"] = 0
        db.execute("UPDATE events SET body=?,hash=? WHERE seq=?", (encode(body), digest([seq, prev, body]), seq))
        with self.assertRaises(IntegrityError):
            self.k.audit()

    def test_rehashed_changed_generated_source_is_rejected(self):
        self.freeze()
        db = self.k.journal.db
        seq, prev, raw = db.execute("SELECT seq,prev,body FROM events ORDER BY seq DESC LIMIT 1").fetchone()
        body = decode(raw)
        body["primitive"]["source"] = "def solve(inputs):\n    return 0\n"
        db.execute("UPDATE events SET body=?,hash=? WHERE seq=?", (encode(body), digest([seq, prev, body]), seq))
        with self.assertRaises(IntegrityError):
            self.k.audit()

    def test_new_state_invalidates_pending_candidate(self):
        frozen = self.freeze()
        self.k.register([example_task()])
        self.k.step()
        with self.assertRaises(ContractError):
            self.k.assess(frozen["freeze"], fresh_rows())

    def test_unsigned_word_contract_and_source_identity(self):
        g = learn(SPEC)["genes"][0]
        for values in ({"x": -1, "y": 0}, {"x": 2 ** 32, "y": 0}, {"x": True, "y": 0}, {"x": 1}):
            with self.assertRaises(ContractError):
                execute(g, values)
        bad = copy.deepcopy(g)
        bad["ir"] = ["literal", 0]
        with self.assertRaises(ContractError):
            execute(bad, {"x": 1, "y": 2})

    def test_unsafe_specification_never_becomes_python_plugin(self):
        for expr in ("__import__('os').system('id')", "x.__class__", "(lambda: x)()", "x ** 999999",
                     "x << 1000000", "[x for x in range(9)]", "ROTR(x,y)"):
            with self.assertRaises(ContractError):
                gene({"name": "unsafe", "parameters": ["x", "y"], "width": 32, "expression": expr}, "0" * 64)

    def test_formula_compiler_generalizes_and_is_actually_isolated(self):
        spec = {**SPEC, "text": "blend(x,y) = (ROTL(x,3) + y) ^ (x >> 7)"}
        g = learn(spec)["genes"][0]
        rows = []
        for x, y in ((0, 0), (1, 7), (0xFFFFFFFF, 4), (123456789, 87654321)):
            rotated = ((x << 3) | (x >> 29)) & 0xFFFFFFFF
            expected = ((rotated + y) & 0xFFFFFFFF) ^ (x >> 7)
            rows.append({"input": {"x": x, "y": y}, "output": expected})
        receipt = evaluate([{"program": g, "rows": rows}], {})
        self.assertEqual(receipt["isolation"], "linux_seccomp_v1")
        self.assertEqual(receipt["results"][0]["passed"], 4)

    def test_nist_document_extracts_functions_without_hash_implementation(self):
        root = Path(__file__).resolve().parents[1] / "experience/capability-cycle-v3"
        raw = json.loads((root / "specification-functions.json").read_text())
        learned = learn(raw)
        self.assertEqual(len(learned["genes"]), 6)
        self.assertEqual(learned["rejected"], [])
        genes = {g["definition"]["name"]: g for g in learned["genes"]}
        x, y, z = 0xDEADBEEF, 0x12345678, 0x87654321
        ch = (x & y) | ((0xFFFFFFFF ^ x) & z)
        maj = (x & y) | (x & z) | (y & z)
        self.assertEqual(execute(genes["Ch"], {"x": x, "y": y, "z": z}), ch)
        self.assertEqual(execute(genes["Maj"], {"x": x, "y": y, "z": z}), maj)
        # Independent bit-string rotation oracle, not the compiler's word helper.
        bits = format(x, "032b")
        rotate = lambda n: int(bits[-n:] + bits[:-n], 2)
        for name, expected in (("Sigma_256_0", rotate(2) ^ rotate(13) ^ rotate(22)),
                               ("Sigma_256_1", rotate(6) ^ rotate(11) ^ rotate(25)),
                               ("sigma_256_0", rotate(7) ^ rotate(18) ^ (x // 8)),
                               ("sigma_256_1", rotate(17) ^ rotate(19) ^ (x // 1024))):
            self.assertEqual(execute(genes[name], {"x": x}), expected)

    def test_partial_equations_cannot_be_misreported_as_sha256_admission(self):
        root = Path(__file__).resolve().parents[1]
        corpus = json.loads((root / "experience/development-chain-v1/corpus.json").read_text())
        task = next(t for t in corpus if t["id"] == "90-sha256-deficit-control")
        self.k.register([task])
        self.assertEqual(self.k.step()["reason"], "SEARCH_EXHAUSTED")
        for path in sorted((root / "experience/capability-cycle-v3").glob("specification-*.json")):
            self.k.study(json.loads(path.read_text()))
        result = self.k.step()
        self.assertEqual(result["status"], "WITHHOLD")
        self.assertEqual(result["reason"], "SPECIFICATION_LANGUAGE_INCOMPLETE")
        self.assertEqual(len(result["workspace"]["CODE"]["generated"]), 6)
        self.assertIsNone(result["primitive"])
        self.assertEqual(result["report"]["hidden_cases_seen"], 0)
        self.assertEqual(self.k.status()["active_generation"], 0)


if __name__ == "__main__":
    unittest.main()

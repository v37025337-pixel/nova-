import copy
import hashlib
import json
import tempfile
import unittest
from pathlib import Path

from nova_core.contracts import ContractError
from nova_core.extensions import execute
from nova_core.isolation import evaluate
from nova_core.kernel import Kernel
from nova_core.sequence import gene
from nova_core.specifications import compile_documents, learn

ROOT = Path(__file__).resolve().parents[1]


def documents():
    paths = list((ROOT / "experience/capability-cycle-v3").glob("specification-*.json"))
    paths += list((ROOT / "experience/algorithm-cycle-v4").glob("specification-*.json"))
    return [json.loads(p.read_text()) for p in sorted(paths)]


TOY = '''The "little-endian" convention is used for words.
Text inputs use UTF-8. Return lowercase hexadecimal.
Mix(x,y) = (x ^ y) + ROTL(x,5)
Append the bit "1" to the end of the message, then zero bits so that
λ + 1 + k ≡ 16 mod 32 . Then append the 16-bit block equal to its bit length.
V 0(0) = 1234
V 1(0) = 00ff
The sequence C0, C1, C2, C3 supplies constants. In hex, these constant words are (from left to right)
0003 0005 0007 000b

The algorithm processes a message, P, as blocks.
For j=1 to B:
{
 1. Prepare the message schedule, {Rq}:
       P q(j)                    0 <= q <= 1
 Rq =
       Rq-1 + Rq-2               2 <= q <= 3
 2. Initialize the two working variables:
       u = V 0(j-1)
       v = V 1(j-1)
 3. For q=0 to 3:
 {
       u = Mix(u,v) + Cq + Rq
       v = v + u
 }
 4. Compute the next state:
       V 0(j) = u + V 0(j-1)
       V 1(j) = v ^ V 1(j-1)
}
The output is V 0(B) V 1(B).
'''


def toy_oracle(message):
    data = message.encode()
    payload = data + b"\x80" + bytes((2 - len(data) - 1) % 4) + (8 * len(data)).to_bytes(2, "little")
    state = [0x1234, 0x00FF]
    for pos in range(0, len(payload), 4):
        block = payload[pos:pos+4]
        schedule = [int.from_bytes(block[:2], "little"), int.from_bytes(block[2:], "little")]
        schedule.append(sum(schedule) & 65535)
        schedule.append((schedule[1] + schedule[2]) & 65535)
        u, v = state
        for k, w in zip((3, 5, 7, 11), schedule):
            rotate = ((u << 5) | (u >> 11)) & 65535
            u = ((u ^ v) + rotate + k + w) & 65535
            v = (v + u) & 65535
        state = [(u + state[0]) & 65535, v ^ state[1]]
    return b"".join(n.to_bytes(2, "little") for n in state).hex()


def toy_document():
    return {"id": "independent-recurrence", "source": "test:independent-mathematical-specification",
            "title": "Two-word recurrence", "text": TOY, "width": 16,
            "provenance": "Maintainer test specification, not SHA or a SHA implementation"}


class SequenceSpecificationTests(unittest.TestCase):
    def test_standard_document_compiles_and_matches_public_conformance_vectors(self):
        g = compile_documents(documents())
        self.assertEqual(g["language"], "nova.sequence.v1")
        self.assertIn("for v_", g["source"])
        self.assertNotIn("hashlib", g["source"])
        self.assertNotIn("import", g["source"])
        self.assertEqual(execute(g, {"message": "abc"}),
                         "ba7816bf8f01cfea414140de5dae2223b00361a396177a9cb410ff61f20015ad")
        rows = [{"input": {"message": s}, "output": hashlib.sha256(s.encode()).hexdigest()}
                for s in ("", "a" * 55, "a" * 56, "a" * 63, "a" * 64, "a" * 65, "a" * 127,
                          "a" * 128, "a" * 511, "a" * 512, "a" * 1024, "ядро\x00é")]
        result = evaluate([{"program": g, "rows": rows}], {})
        self.assertEqual(result["results"][0]["passed"], len(rows))

    def test_same_reader_compiles_different_state_rounds_endian_width_and_formula(self):
        g = compile_documents([toy_document()])
        self.assertEqual(g["definition"]["width"], 16)
        self.assertEqual(g["derivation"]["constant_counts"], {"C": 4})
        self.assertEqual(g["derivation"]["initial_counts"], {"V": 2})
        self.assertEqual(g["derivation"]["byte_order"], "little")
        rows = [{"input": {"message": s}, "output": toy_oracle(s)}
                for s in ("", "a", "ab", "abc", "abcd", "abcdefg", "nova", "тест", "x" * 129)]
        self.assertEqual(evaluate([{"program": g, "rows": rows}], {})["results"][0]["passed"], len(rows))

    def test_document_changes_cause_body_and_behavior_changes(self):
        original = toy_document()
        first = compile_documents([original])
        for text in (TOY.replace("0007", "0009"), TOY.replace("ROTL(x,5)", "ROTL(x,7)"),
                     TOY.replace("For q=0 to 3:", "For q=0 to 2:")):
            changed = compile_documents([{**original, "text": text}])
            self.assertNotEqual(first["id"], changed["id"])
            self.assertNotEqual(execute(first, {"message": "nova"}), execute(changed, {"message": "nova"}))

    def test_algorithm_name_is_not_dispatch_and_knowledge_is_required(self):
        renamed = [{**d, "text": d["text"].replace("SHA-256", "UNNAMED-EXPERIMENT")} for d in documents()]
        g = compile_documents(renamed)
        self.assertEqual(execute(g, {"message": "abc"}), hashlib.sha256(b"abc").hexdigest())
        incomplete = [d for d in documents() if d["id"] != "fips180-4-algorithm"]
        with self.assertRaises(ContractError):
            compile_documents(incomplete)
        self.assertFalse(learn({d["id"]: d for d in incomplete})["genes"])

    def test_source_tampering_and_unknown_statements_fail_closed(self):
        original = compile_documents([toy_document()])
        bad = copy.deepcopy(original)
        bad["source"] += "\nimport os\n"
        with self.assertRaises(ContractError):
            execute(bad, {"message": "abc"})
        for text in (TOY.replace("v = v + u", "v = __import__('os').getpid()"),
                     TOY.replace("For q=0 to 3:", "For q=0 to 1000000:"),
                     TOY.replace("2 <= q <= 3", "1 <= q <= 3")):
            with self.assertRaises(ContractError):
                compile_documents([{**toy_document(), "text": text}])

    def test_input_allocation_and_iteration_budgets(self):
        g = compile_documents([toy_document()])
        for message in ("x" * 1025, "я" * 513, 123):
            with self.assertRaises(ContractError):
                execute(g, {"message": message})
        ir = {"functions": {}, "body": [["set", "oversized", ["zeros", ["literal", 1000000]]]],
              "result": ["literal", 1]}
        allocated = gene(ir, 32, ["0" * 64], {})
        with self.assertRaises(ContractError):
            execute(allocated, {"message": ""})
        ir["body"] = [["for", "i", ["literal", 0], ["literal", 2048],
                       [["for", "j", ["literal", 0], ["literal", 2048], []]]]]
        looping = gene(ir, 32, ["0" * 64], {})
        with self.assertRaises(ContractError):
            execute(looping, {"message": ""})

    def test_kernel_freezes_algorithm_then_requires_new_oracle_rows(self):
        values = ("closed-loop", "learning-test", "preserved", "boundary")
        rows = [{"input": {"payload": s}, "output": hashlib.sha256(s.encode()).hexdigest()} for s in values]
        task = {"id": "external-deficit", "source": "test:public-training", "train": rows[:2], "holdout": rows[2:]}
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "state.sqlite"
            with Kernel(path, create=True) as kernel:
                kernel.register([task])
                self.assertEqual(kernel.step()["reason"], "SEARCH_EXHAUSTED")
                for d in documents():
                    kernel.study(d)
                frozen = kernel.step()
                self.assertEqual(frozen["status"], "FROZEN")
                self.assertEqual(frozen["primitive"]["language"], "nova.sequence.v1")
                self.assertEqual(frozen["report"]["hidden_cases_seen"], 0)
                rows = [{"input": {"payload": s}, "output": hashlib.sha256(s.encode()).hexdigest()}
                        for s in ("post-freeze-1", "post-freeze-2")]
                result = kernel.assess(frozen["freeze"], rows)
                self.assertEqual(result["status"], "ADMITTED")
                self.assertEqual(result["report"]["ablation"]["without_primitive"]["passed"], 0)
                head = kernel.audit()["head"]
            with Kernel(path) as restarted:
                self.assertEqual(restarted.audit(expected_head=head)["active_generation"], 1)
                self.assertEqual(restarted.predict(task["id"], {"payload": "independent-query"}),
                                 hashlib.sha256(b"independent-query").hexdigest())
                restarted.rollback(0)
                self.assertEqual(restarted.genome()["genes"], [])


if __name__ == "__main__":
    unittest.main()

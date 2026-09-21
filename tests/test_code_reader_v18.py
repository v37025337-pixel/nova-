"""Version upgrade, seeded challenge splits and closed grammar persistence."""

import ast
import hashlib
import json
from pathlib import Path
import unittest

from nova_core import ucr_development
from nova_tools.universal_code_reader import UniversalCodeReader


class ReaderV18Tests(unittest.TestCase):
    def test_v8_induction_code_matches_the_frozen_source_contract(self):
        root = Path(__file__).resolve().parents[1]
        contract = json.loads((root / "canonical/ucr-v8-replay.json").read_text())
        source = (root / "nova_tools/universal_code_reader.py").read_text()
        module = ast.parse(source)
        reader = next(c for c in module.body if isinstance(c, ast.ClassDef) and c.name == "UniversalCodeReader")
        methods = {m.name: m for m in reader.body if isinstance(m, ast.FunctionDef)}
        for name, expected in contract["method_source_sha256"].items():
            with self.subTest(method=name):
                method = methods[name]
                start = min([method.lineno] + [d.lineno for d in method.decorator_list])
                text = "".join(source.splitlines(keepends=True)[start - 1:method.end_lineno])
                actual = hashlib.sha256(text.encode()).hexdigest()
                self.assertEqual(actual, expected)

    def test_uploaded_version_is_active_and_bytes_survive(self):
        raw = b"\xff\xfex\x00=\x001\x00\n\x00"
        result = UniversalCodeReader().read(raw, "sample.py")
        self.assertEqual(result.metadata["reader_version"], "18.0")
        self.assertEqual(result.restore_bytes(), raw)
        self.assertEqual(json.loads(result.to_json())["schema"], "ucr.ai-ir/17.0")

    def test_challenge_seed_changes_inputs_without_overlap_between_splits(self):
        reader = UniversalCodeReader()
        first = reader._v18_challenge_grids(18001)
        self.assertEqual(first, reader._v18_challenge_grids(18001))
        self.assertNotEqual(first, reader._v18_challenge_grids(18002))
        self.assertEqual([len(first[k]) for k in ("train", "hidden", "fresh")], [42, 36, 42])
        values = [x for split in first.values() for x in split]
        self.assertEqual(len(values), len(set(values)))

    def test_compose3_requires_explicit_grammar_and_restores_as_data(self):
        reader = UniversalCodeReader()
        blueprint = {"family": "meta.compose_unary3", "arity": 1, "params": {
            "first": {"family": "integer.popcount_abs", "arity": 1},
            "second": {"family": "integer.digital_root_abs", "arity": 1},
            "third": {"family": "integer.mod_equal", "arity": 1, "params": {"modulus": 2, "residue": 0}}}}
        with self.assertRaises(ValueError):
            reader._compile_safe_primitive_blueprint(blueprint)
        state = {"grammar_rules": [{"rule_id": "unary.compose3", "admitted": True}],
                 "mutation_strategy_routes": [{"signature": "representation-gap|compose3-required",
                                                "action": "expand-grammar-unary-compose3", "admitted": True}],
                 "primitives": [{"blueprint": blueprint}]}
        restored = reader.load_evolved_state(state)
        self.assertEqual(restored["rejected"], [])
        self.assertEqual(restored["loaded"], 1)
        label = next(iter(reader.evolved_primitive_registry))
        function = reader.semantic_primitives[label]["function"]
        for x in (-1023, -29, 0, 5, 17, 31, 255):
            bits = abs(x).bit_count()
            root = 0 if bits == 0 else 1 + (bits - 1) % 9
            self.assertEqual(function(x), root % 2 == 0)
        exported = json.loads(json.dumps(reader.export_evolved_state()))
        self.assertEqual(exported["schema"], "ucr.evolved-state/4")
        self.assertEqual(UniversalCodeReader().load_evolved_state(exported)["loaded"], 1)
        with self.assertRaises(ValueError):
            reader._compile_safe_primitive_blueprint({"family": "python.exec", "source": "pass"})

    def test_v8_receipts_replay_exactly_with_preserved_inference_semantics(self):
        cases = json.loads((Path(__file__).parent / "fixtures/ucr-v8-search.json").read_text())
        for case in cases:
            with self.subTest(case=case["name"]):
                legacy = ucr_development.synthesize_v8(case["training"], {})
                self.assertEqual(legacy, case["expected"])
                current = ucr_development.synthesize(case["training"], {})
                self.assertEqual(current["ucr"]["reader_version"], "18.0")
                self.assertEqual(current["program"], legacy["program"])


if __name__ == "__main__":
    unittest.main()

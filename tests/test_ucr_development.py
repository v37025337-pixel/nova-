"""UCR proposals must enter the real frozen-candidate and fresh-data gate."""

import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from nova_core.contracts import ContractError, digest
from nova_core.kernel import Kernel, runtime_manifest
from nova_core.language import execute
from nova_core import ucr_development
from nova_tools.universal_code_reader import UniversalCodeReader
from test_observation_goals import document


class UCRDevelopmentTests(unittest.TestCase):
    def test_composition_is_translated_to_native_ir_and_runs_on_unseen_values(self):
        training = [{"input": {"text": f"  MiXeD-{i}  "}, "output": f"mixed-{i}"} for i in range(8)]
        result = ucr_development.synthesize(training, {})
        self.assertEqual(result["ucr"]["status"], "TRAINING_FIT")
        self.assertEqual(result["native_attempts"], 0)
        self.assertEqual(execute(result["program"], {"text": "  STRASSE\n"}, {}), "strasse")
        self.assertEqual(result["ucr"]["training_sha256"], digest(training))
        self.assertEqual(result["ucr"]["fresh_cases_seen"], 0)

    def test_unsupported_tree_cannot_become_executable(self):
        for tree in (("op", "os.system", (("arg", 0),)),
                     ("arg", -1), ("arg", True),
                     ("op", "nova.add", (("arg", 0),))):
            with self.subTest(tree=tree), self.assertRaises(ContractError):
                ucr_development.translate(tree, "value")

    def test_native_fallback_preserves_unsupported_search(self):
        training = [{"input": {"a": i, "b": 2 * i}, "output": 3 * i} for i in range(8)]
        result = ucr_development.synthesize(training, {})
        self.assertEqual(result["ucr"]["status"], "UNSUPPORTED_INPUT_SHAPE")
        self.assertGreater(result["native_attempts"], 0)
        self.assertEqual(execute(result["program"], {"a": 19, "b": 27}, {}), 46)

    def test_unexplained_observations_exhaust_both_searches_without_a_program(self):
        labels = ("oak", "moon", "river", "stone", "cloud", "fern", "moss", "sand")
        training = [{"input": {"value": i + 11}, "output": label} for i, label in enumerate(labels)]
        result = ucr_development.synthesize(training, {})
        self.assertIsNone(result["program"])
        self.assertEqual(result["ucr"]["status"], "NO_EXACT_TRAINING_FIT")
        self.assertGreater(result["native_attempts"], 0)
        self.assertEqual(len(result["ucr"]["rounds"]), 3)
        self.assertTrue(all(r["generated"] <= 2048 for r in result["ucr"]["rounds"]))

    def test_kernel_uses_only_training_then_freezes_and_checks_fresh_rows(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "state.sqlite"
            with Kernel(path, create=True) as kernel:
                kernel.start_autonomy()
                for part in range(3):
                    kernel.observe(document(part, [{"a": x, "b": x + 1}
                        for x in range(10 + 10 * part, 18 + 10 * part)]))
                goal = kernel.step()["goal"]
                self.assertEqual(kernel.step()["phase"], "SEARCH_FROZEN")
                captured = []
                original = UniversalCodeReader.infer_compositional_reasoning

                def capture(reader, observations, **kwargs):
                    rows = list(observations)
                    captured.append(rows)
                    return original(reader, rows, **kwargs)

                with patch.object(UniversalCodeReader, "infer_compositional_reasoning", capture):
                    frozen = kernel.step()
                self.assertTrue(captured)
                for rows in captured:
                    self.assertEqual([r["inputs"]["arg0"] for r in rows],
                                     [next(iter(r["input"].values())) for r in goal["training"]])
                    self.assertEqual([r["output"] for r in rows], [r["output"] for r in goal["training"]])
                self.assertEqual(frozen["report"]["ucr"]["status"], "TRAINING_FIT")
                self.assertEqual(kernel.status()["active_generation"], 0)
                field = goal["observation_contract"]["input_field"]
                fresh = [{"input": {field: x}, "output": x + 1 if field == "a" else x - 1}
                         for x in range(101, 117)]
                result = kernel.autonomy_assess(frozen["freeze"], fresh)
                self.assertEqual(result["status"], "ADMITTED")
                self.assertEqual(result["report"]["fresh"]["passed"], 16)
                head = kernel.status()["head"]
            with Kernel(path) as restored:
                self.assertEqual(restored.audit(expected_head=head)["status"], "PASS")
                self.assertEqual(restored.predict(goal["id"], fresh[0]["input"]), fresh[0]["output"])

    def test_runtime_pins_the_external_reader_dependency(self):
        manifest = runtime_manifest()
        self.assertEqual(manifest["schema"], "nova.kernel.v9")
        self.assertIn("nova_tools/universal_code_reader.py", manifest["ucr_development"]["sources"])
        self.assertIn("nova_tools/__init__.py", manifest["ucr_development"]["sources"])


if __name__ == "__main__":
    unittest.main()

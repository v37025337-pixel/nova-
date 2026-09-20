import tempfile
import unittest
from pathlib import Path

from nova_core.contracts import ContractError
from nova_core.kernel import Kernel
from scripts.run_grammar_challenge import classify_result, observe, grammar_boundary_probes
from tests.test_kernel import example_task


class GrammarChallengeTests(unittest.TestCase):
    def test_idle_is_not_a_new_generation_or_native_diagnosis(self):
        with tempfile.TemporaryDirectory() as directory:
            with Kernel(Path(directory) / "state.sqlite", create=True) as kernel:
                kernel.register([example_task()])
                kernel.step()
                before = kernel.status()
                result = observe(kernel, before["head"])
                self.assertEqual(result["evolution_verdict"], "WITHHOLD")
                self.assertEqual(result["first_unmet_gate"], "native_deficit_selection")
                self.assertEqual(result["native_result"], {"steps": [{"status": "IDLE", "reason": "NO_ELIGIBLE_DEFICIT"}], "state": before})
                self.assertIsNone(result["native_diagnosis"])
                self.assertEqual(result["after"], before)
                self.assertEqual(result["hidden_holdout"]["evaluated_cases"], 0)

    def test_real_program_admission_is_not_grammar_evolution(self):
        with tempfile.TemporaryDirectory() as directory:
            with Kernel(Path(directory) / "state.sqlite", create=True) as kernel:
                kernel.register([example_task()])
                step = kernel.step()
                self.assertEqual(step["status"], "ADMITTED")
                self.assertEqual(classify_result(step), "FIXED_GRAMMAR_PROGRAM")

    def test_engine_policy_and_unrecognized_claims_are_not_grammar_evidence(self):
        self.assertEqual(classify_result({"domain": "ENGINE", "status": "ADMITTED", "generation": 13}), "ENGINE_POLICY")
        self.assertEqual(classify_result({"domain": "CAPABILITY", "status": "ADMITTED", "generation": 13}), "UNRECOGNIZED_RESULT")

    def test_anchor_mismatch_stops_before_step(self):
        with tempfile.TemporaryDirectory() as directory:
            with Kernel(Path(directory) / "state.sqlite", create=True) as kernel:
                kernel.register([example_task()])
                before = kernel.status()
                with self.assertRaises(ContractError):
                    observe(kernel, "0" * 64)
                self.assertEqual(kernel.status(), before)

    def test_contract_probes_reject_a_new_operation_without_installing_it(self):
        probes = grammar_boundary_probes()
        self.assertTrue(probes["new_expression_operation"]["rejected"])
        self.assertTrue(probes["expanded_policy_operator_set"]["rejected"])
        self.assertNotIn("probe_new_primitive", probes["unary"])
        self.assertEqual(len(probes["unary"]) + len(probes["binary"]), 15)


if __name__ == "__main__":
    unittest.main()

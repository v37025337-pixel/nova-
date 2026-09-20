import copy
import unittest

from nova_core.contracts import ContractError, decode, equal, normalized, task_spec
from nova_core.language import candidate, execute, interpret
from nova_core.synthesis import synthesize


class LanguageTests(unittest.TestCase):
    def test_json_semantics(self):
        self.assertTrue(equal({"a": [1, {"b": 2}], "c": None}, {"c": None, "a": [1.0, {"b": 2}]}))
        self.assertFalse(equal(True, 1))
        self.assertFalse(equal([1, 2], [2, 1]))
        self.assertFalse(equal({"x": None}, {}))

    def test_reject_nonfinite_duplicate_keys_huge_values(self):
        for text in ('NaN', 'Infinity', '{"a":1,"a":2}'):
            with self.assertRaises(ContractError):
                decode(text)
        for value in (float("inf"), 10**1000, "x" * 8193, list(range(129))):
            with self.assertRaises(ContractError):
                normalized(value)

    def test_source_cannot_be_substituted(self):
        program = candidate(["input", "x"], {})
        program["source"] = "raise RuntimeError('injected')"
        with self.assertRaises(ContractError):
            execute(program, {"x": 3}, {})

    def test_unknown_operation_and_arbitrary_python_rejected(self):
        for ir in (["call", "__import__", ["const", "os"]], ["exec", "print(1)"], ["ref", "absent"]):
            with self.assertRaises(ContractError):
                candidate(ir, {})
        key = "x']; __import__('os'); #"
        program = candidate(["input", key], {})
        self.assertEqual(execute(program, {key: 7}, {}), 7)

    def test_native_arithmetic_synthesis_and_unseen_queries(self):
        training = [{"input": {"x": x, "y": y}, "output": x + y}
                    for x, y in [(2, 7), (5, -3), (-4, 13)]]
        result = synthesize(training, {})
        self.assertIsNotNone(result["program"])
        for x, y in [(31, 17), (-18, -7), (0, 0), (0.5, 1.25)]:
            self.assertEqual(execute(result["program"], {"x": x, "y": y}, {}), x + y)

    def test_ast_and_interpreter_agree_on_structured_json(self):
        ir = ["object", {"equivalent": ["call", "equal", ["call", "parse_json", ["input", "a"]],
                                     ["call", "parse_json", ["input", "b"]]],
                         "count": ["call", "length", ["input", "a"]]}]
        program = candidate(ir, {})
        for a, b in [('{"x":1,"y":[2]}', '{"y":[2],"x":1.0}'), ('true', '1'), ('[1,2]', '[2,1]')]:
            inputs = {"a": a, "b": b}
            self.assertEqual(execute(program, inputs, {}), interpret(ir, inputs, {}))
            self.assertEqual(execute(program, inputs, {})["equivalent"], equal(decode(a), decode(b)))

    def test_generation_does_not_receive_holdout(self):
        # Same training freezes exactly the same candidate regardless of future labels.
        from tests.test_kernel import example_task
        original = example_task()
        altered = copy.deepcopy(original)
        altered["holdout"][0]["output"] = "different oracle"
        self.assertEqual(synthesize(original["train"], {}), synthesize(altered["train"], {}))

    def test_boolean_input_cannot_leak_through_numeric_alias(self):
        from tests.test_kernel import example_task
        task = example_task()
        task["train"][0]["input"] = {"text": 1}
        task["holdout"][0]["input"] = {"text": 1.0}
        with self.assertRaises(ContractError):
            task_spec(task)

    def test_inconsistent_training_is_withheld_with_finite_budget(self):
        # Distinct inputs, no deterministic expression in the supplied grammar.
        train = [{"input": {"x": n}, "output": s} for n, s in [(1, "pear"), (2, "plum"), (3, "lime")]]
        result = synthesize(train, {})
        self.assertIsNone(result["program"])
        self.assertLessEqual(result["attempts"], 12000)


if __name__ == "__main__":
    unittest.main()

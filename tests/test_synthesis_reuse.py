"""Regress duplicate inherited execution without relying on timing thresholds."""

import unittest
from unittest.mock import patch

from nova_core import extensions
from nova_core.language import execute, interpret, primitive
from nova_core.synthesis import synthesize


class OperandReuseTests(unittest.TestCase):
    def test_inherited_primitive_is_not_reexecuted_for_every_composite(self):
        learned = extensions.learn({"id": "reuse-fixture", "source": "test:reuse", "title": "Fixture",
                                    "width": 32, "text": "double(x) = x + x", "provenance": "unit fixture"})
        gene = learned["genes"][0]
        memory = {gene["id"]: gene}
        rows = [{"input": {"x": i}, "output": label} for i, label in [(3, "unavailable-A"), (5, "unavailable-B"), (8, "unavailable-C")]]
        with patch.object(extensions, "execute", wraps=extensions.execute) as calls:
            result = synthesize(rows, memory)
        self.assertIsNone(result["program"])
        self.assertGreater(result["attempts"], 100)
        self.assertEqual(calls.call_count, len(rows))

    def test_reused_values_agree_with_recursive_ir_interpretation(self):
        cases = [("parse_json", ['{"a":[1,2]}']), ("sort", [[3, 1, 2]]),
                 ("sum", [[1, 2, 3]]), ("get", [{"a": [2, 3]}, "a"]),
                 ("equal", [True, 1]), ("less", [-2, 3]), ("json", [{"x": [True, None]}])]
        for op, args in cases:
            with self.subTest(op=op):
                inputs = {str(i): value for i, value in enumerate(args)}
                node = ["call", op] + [["input", str(i)] for i in range(len(args))]
                self.assertEqual(primitive(op, *args), interpret(node, inputs, {}))

    def test_generated_program_still_executes_on_unseen_inputs(self):
        rows = [{"input": {"x": x}, "output": 2*x + 1} for x in (2, 4, 7)]
        result = synthesize(rows, {})
        self.assertIsNotNone(result["program"])
        self.assertEqual(execute(result["program"], {"x": 101}, {}), 203)


if __name__ == "__main__":
    unittest.main()

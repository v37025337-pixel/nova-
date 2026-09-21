"""Exercise the upgraded reader at the real file/journal boundary."""

import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

from nova_core.kernel import Kernel
from nova_tools.code_reader_bridge import observation, read_file, record
from nova_tools.universal_code_reader import UniversalCodeReader


class ReaderV16Tests(unittest.TestCase):
    def test_fallback_graph_has_one_canonical_layer(self):
        for text, name in [("const plus = (x) => x + 1;", "a.js"),
                           ("def broken(:\n    return 1", "a.py"),
                           ('{"same":1,"same":2}', "a.json"),
                           ("fn main() { let x = 2; }", "a.rs")]:
            with self.subTest(name=name):
                result = UniversalCodeReader().read(text, name)
                ids = [n.id for n in result.nodes]
                self.assertEqual(len(ids), len(set(ids)))
                self.assertEqual(result.metadata["unresolved_links"], [])
                self.assertTrue(result.nodes_of("canonical.statement"))
                self.assertEqual(result.restore_bytes(), text.encode())

    def test_jsonl_is_strict_and_keeps_distinct_pointer_paths(self):
        reader = UniversalCodeReader()
        good = reader.read('{"a/b":1,"a":{"b":2}}\n{"x":3}\n', "a.jsonl")
        self.assertEqual(good.metadata["parse_level"], "json_lines")
        self.assertEqual(good.metadata["duplicate_node_ids"], [])
        for text in ['{"a":1,"a":2}\n', '{"a":NaN}\n', '{"a":1e999}\n']:
            result = reader.read(text, "a.jsonl", language_hint="jsonl")
            self.assertIn("parser_error", result.metadata)
            self.assertEqual(result.metadata["parse_level"], "tokens")
            json.loads(result.to_json(), parse_constant=lambda n: self.fail(n))

    def test_xml_tree_and_forward_graph_declarations(self):
        reader = UniversalCodeReader()
        xml = reader.read('<root><x a="1">one</x><x>two</x></root>', "a.xml")
        self.assertEqual(xml.metadata["parse_level"], "xml_tree")
        self.assertEqual(len(xml.nodes_of("xml.element")), 3)
        self.assertEqual(xml.metadata["unresolved_links"], [])
        graph = reader.read("A:\n  relation -> B\nB:\n  reverse -> A\n", "a.aic")
        self.assertEqual(graph.metadata["implicit_symbols"], [])
        self.assertEqual(graph.metadata["duplicate_node_ids"], [])

    def test_surface_grammar_and_passport_are_available(self):
        reader = UniversalCodeReader()
        grammar = reader.learn_grammar(["x = Ω(a,b)\n", "y = Ω(c,d)\n"], language_hint="ai-native")
        self.assertEqual(grammar.sample_count, 2)
        self.assertTrue(grammar.rules)
        self.assertEqual(grammar.metadata["semantic_status"], "surface-grammar-only")
        result = reader.read("x = Ω(a,b)\n", "a.aic")
        self.assertEqual(result.passport()["sha256"], result.sha256)
        self.assertEqual(result.metadata["reader_version"], UniversalCodeReader.VERSION)

    def test_unary_calls_and_vectors_accept_single_input_nova_traces(self):
        rows = [{"inputs": {"text": text}, "output": len(text)}
                for text in ["a", "\tbb\n", "CCC", "DDDD", " EEEEE\n", " FFFFFF ", "g", " hhhhhhhh\n"]]
        for code in ["r = Ω(text)", "r = [Ω, text]"]:
            with self.subTest(code=code):
                _, cycle = UniversalCodeReader().read_with_cognitive_observations(code, rows)
                symbol = cycle["compositional_reasoning"]["symbols"]["Ω"]
                self.assertEqual(symbol["arity"], 1)
                self.assertEqual(symbol["candidates"][0]["train_score"], 1.0)
                self.assertEqual(symbol["candidates"][0]["holdout_score"], 1.0)

    def test_trace_hypotheses_reach_nova_without_becoming_admitted_skills(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source, traces, state = root / "a.aic", root / "traces.json", root / "nova.sqlite"
            source.write_text("x = 1\n" * 80 + "r = Ω(a,b)\n")
            pairs = [(-4, 7), (2, 3), (4, 5), (7, 2), (3, 6), (5, -2), (8, -1), (0, 9)]
            rows = [{"code": "r = Ω(a,b)", "inputs": {"a": a, "b": b}, "output": a + b} for a, b in pairs]
            traces.write_text(json.dumps(rows))
            result = read_file(source, traces=traces)
            cycle = result.metadata["cognitive_cycle"]
            symbol = cycle["compositional_reasoning"]["symbols"]["Ω"]
            self.assertEqual(symbol["candidates"][0]["expression"], "numeric.add(a, b)")
            body = json.loads(observation(result, "https://example.org/a.aic", "fixture")["text"])
            self.assertTrue(body["nodes_truncated"])
            self.assertEqual(body["nodes"][0]["kind"], "cognitive.reasoning_hypothesis")
            self.assertFalse(body["reader"]["trace_evidence"]["nova_capability_admitted"])
            self.assertIn("not_independent_fresh", body["reader"]["trace_evidence"]["validation"])
            with Kernel(state, create=True) as kernel:
                self.assertEqual(record(kernel, result, "https://example.org/a.aic", "fixture")["status"], "RECORDED")
                self.assertEqual(kernel.status()["tasks_total"], 0)
                self.assertEqual(kernel.status()["active_generation"], 0)
                head = kernel.status()["head"]
            with Kernel(state) as kernel:
                self.assertEqual(kernel.audit(expected_head=head)["status"], "PASS")

    def test_uninterpretable_traces_do_not_invent_a_hypothesis(self):
        reader = UniversalCodeReader()
        _, cycle = reader.read_with_cognitive_observations(
            "opaque text", [{"inputs": {"a": 1}, "output": 99}])
        self.assertEqual(cycle["compositional_reasoning"]["symbols"], {})
        self.assertTrue(cycle["compositional_reasoning"]["unresolved"])

    def test_cli_analyzes_traces_and_protects_all_inputs(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source, traces, out = root / "a.aic", root / "traces.json", root / "out.json"
            source.write_text("r = Ω(a,b)\n")
            traces.write_text(json.dumps([{"inputs": {"a": i, "b": 2*i+1}, "output": 3*i+1} for i in range(8)]))
            command = [sys.executable, "-m", "nova_tools.code_reader_bridge", str(source), "--traces", str(traces)]
            result = subprocess.run(command + ["--output", str(out)], capture_output=True, text=True)
            self.assertEqual(result.returncode, 0, result.stderr)
            parsed = json.loads(out.read_text())
            self.assertEqual(len(parsed["metadata"]["trace_observations"]), 8)
            before = traces.read_bytes()
            failed = subprocess.run(command + ["--output", str(traces)], capture_output=True, text=True)
            self.assertNotEqual(failed.returncode, 0)
            self.assertEqual(traces.read_bytes(), before)

    def test_bridge_rejects_oversized_source_and_invalid_trace_shape(self):
        with tempfile.TemporaryDirectory() as tmp:
            source, traces = Path(tmp) / "a.py", Path(tmp) / "trace.json"
            source.write_bytes(b"x" * 262145)
            with self.assertRaises(ValueError):
                read_file(source)
            source.write_text("x = 1")
            for payload in [{}, [], [1], [{}] * 129]:
                traces.write_text(json.dumps(payload))
                with self.assertRaises(ValueError):
                    read_file(source, traces=traces)


if __name__ == "__main__":
    unittest.main()

"""Byte preservation, graph integrity, and the actual Nova observation bridge."""

import base64
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from nova_tools.universal_code_reader import UniversalCodeReader
from nova_tools.code_reader_bridge import observation, record
from nova_core.kernel import Kernel


class CodeReaderTests(unittest.TestCase):
    def setUp(self):
        self.reader = UniversalCodeReader()

    def test_python_graph_has_unique_connected_occurrence_ids(self):
        result = self.reader.read(b"x = 1\ny = x + 2\nz = y + 3\n", "sample.py")
        ids = [node.id for node in result.nodes]
        self.assertEqual(len(ids), len(set(ids)))
        self.assertTrue(all(link in ids for node in result.nodes for link in node.links))
        self.assertTrue(any(node.kind == "python.Constant" and node.value == 2 for node in result.nodes))

    def test_arbitrary_bytes_survive_boms_binary_and_invalid_encoding(self):
        fixtures = [b"", b"hello", bytes(range(256)), b"\xef\xbb\xbf\xff",
                    b"\xff\xfe\x00", b"\xfe\xff" + "print('Я')".encode("utf-16-be"),
                    b"\xef\xbb\xbfprint('hi')", b"\x00asm\x01\x00\x00\x00"]
        for payload in fixtures:
            with self.subTest(payload=payload):
                result = self.reader.read(payload)
                self.assertEqual(result.restore_bytes(), payload)
                self.assertEqual(base64.b64decode(json.loads(result.to_json())["source_base64"]), payload)

    def test_json_pointer_collisions_and_duplicate_keys(self):
        result = self.reader.read('{"a/b": 1, "a": {"b": 2}, "a~1b": 3}', "input.json")
        ids = [n.id for n in result.nodes]
        self.assertEqual(len(ids), len(set(ids)))
        bad = self.reader.read('{"a":1,"a":2}', "input.json")
        self.assertEqual(bad.metadata["parse_level"], "tokens")
        self.assertTrue(any(n.kind == "parser_error" for n in bad.nodes))

    def test_binary_is_not_misreported_as_wasm_syntax(self):
        result = self.reader.read(b"\x00asm\x01\x00\x00\x00", "sample.wasm")
        self.assertEqual(result.language, "wasm")
        self.assertEqual(result.metadata["parse_level"], "bytes")
        # v16 adds a byte-level summary, without claiming WASM instructions.
        self.assertTrue(any(n.kind == "binary.chunk" for n in result.nodes))
        self.assertTrue(all(n.kind.startswith("binary.") or n.kind == "summary.binary" for n in result.nodes))

    def test_surrogates_and_nonfinite_python_literals_produce_portable_json(self):
        result = self.reader.read(b"x='\\ud800'\ny=1e999\n", "input.py")
        encoded = result.to_json().encode("utf-8")
        json.loads(encoded, parse_constant=lambda x: self.fail("nonstandard number: " + x))

    def test_reading_source_never_executes_it(self):
        with tempfile.TemporaryDirectory() as tmp:
            marker = Path(tmp) / "executed"
            payload = f"from pathlib import Path\nPath({str(marker)!r}).write_text('bad')\n"
            self.reader.read(payload, "untrusted.py")
            self.assertFalse(marker.exists())

    def test_generic_language_is_explicitly_tokens_and_ai_links_are_reported(self):
        js = self.reader.read("const plus = (x) => x + 1;", "test.js")
        self.assertEqual(js.metadata["parse_level"], "tokens")
        graph = self.reader.read("A:\n  relation -> B\n", "test.aic")
        # v16 represents undeclared symbols as explicit implicit atoms.
        self.assertIn("B", graph.metadata["implicit_symbols"])
        self.assertEqual(graph.metadata["unresolved_links"], [])
        self.assertTrue(any(n.kind == "ai.atom" and n.value == "B" and n.meta["implicit"] for n in graph.nodes))

    def test_derived_syntax_reaches_kernel_and_survives_restart(self):
        result = self.reader.read(b"def plus(x):\n    return x + 1\ntext='\\ud800'\n", "sample.py")
        source = "https://code.example.org/sample.py"
        doc = observation(result, source, "fixture")
        body = json.loads(doc["text"])
        self.assertEqual(body["representation"], "derived_syntax_not_source_execution")
        self.assertEqual(body["source_sha256"], result.sha256)
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "nova.sqlite"
            with Kernel(path, create=True) as kernel:
                self.assertEqual(record(kernel, result, source, "fixture")["status"], "RECORDED")
                self.assertEqual(kernel.status()["tasks_total"], 0)
                head = kernel.status()["head"]
            with Kernel(path) as kernel:
                self.assertEqual(kernel.audit(expected_head=head)["status"], "PASS")
                self.assertEqual(kernel.status()["observations"]["documents_seen"], 1)

    def test_bridge_exposes_projection_limits_and_cli_preserves_full_input(self):
        raw = b"x = 1\n" * 100
        result = self.reader.read(raw, "many.py")
        body = json.loads(observation(result, "https://code.example.org/many.py", "fixture")["text"])
        self.assertTrue(body["nodes_truncated"])
        self.assertEqual(body["nodes_included"], 96)
        with tempfile.TemporaryDirectory() as tmp:
            inp, out = Path(tmp) / "many.py", Path(tmp) / "many.json"
            inp.write_bytes(raw)
            process = subprocess.run([sys.executable, "-m", "nova_tools.code_reader_bridge", str(inp),
                                      "--output", str(out)], capture_output=True, text=True)
            self.assertEqual(process.returncode, 0, process.stderr)
            self.assertEqual(base64.b64decode(json.loads(out.read_text())["source_base64"]), raw)

    def test_forged_retained_bytes_are_rejected(self):
        result = self.reader.read(b"print('original')", "source.py")
        result.source_base64 = base64.b64encode(b"changed").decode()
        with self.assertRaises(ValueError):
            result.restore_bytes()


if __name__ == "__main__":
    unittest.main()

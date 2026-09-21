"""Preserve supplied graph data without losing rows or inventing evidence."""

from copy import deepcopy
import hashlib
import json
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch

from nova_core.contracts import ContractError, encode
from nova_core.kernel import Kernel
from nova_core.observations import extract, groups
from scripts.import_static_codeflow import documents, validate, SOURCE_LIMIT
from scripts import import_static_codeflow

ROOT = Path(__file__).resolve().parents[1]
SOURCE = "https://example.org/supplied-graph.json"
WHEN = "2026-09-21T00:00:00Z"


def graph(count=2):
    return {"pkg": {"schema": "ucr.external-static-codeflow/1", "project": "pkg", "version": "1.0",
                    "projection": "intermodule-causal-core",
                    "nodes": [{"id": f"pkg.m:f{i}", "module": "pkg.m", "name": f"f{i}", "kind": "function"}
                              for i in range(count)],
                    "edges": [{"src": "pkg.m:f0", "dst": "pkg.m:f1", "kind": "call"}]}}


class StaticCodeflowTests(unittest.TestCase):
    def test_actual_attachment_keeps_every_node_and_edge(self):
        raw = (ROOT / "experience/codeflow-v25-input/ucr_v25_real_flow_cores.json").read_bytes()
        self.assertEqual(hashlib.sha256(raw).hexdigest(), "ecf01e81c7cd39b851e1da30bb86304a9610a9d384651fab89793927e3c73c36")
        direct = extract({"source": SOURCE, "media_type": "application/json", "text": raw.decode(),
                          "sha256": hashlib.sha256(raw).hexdigest(), "obtained_at": WHEN})
        self.assertTrue(direct["receipt"]["limited"])
        self.assertEqual(direct["receipt"]["records"], 128)
        projected = documents(raw, SOURCE, WHEN)
        self.assertEqual(len(projected), 4)
        self.assertEqual({d["source"] for d in projected}, {SOURCE})
        counts = {"/nodes/*": 0, "/edges/*": 0}
        reconstructed = {name: {"nodes": [], "edges": []} for name in json.loads(raw)}
        for doc in projected:
            body = json.loads(doc["text"])
            meta = body["metadata"]
            self.assertFalse(meta["upstream_source_verified"])
            self.assertFalse(meta["dynamic_execution_verified"])
            parsed = extract(doc)
            self.assertFalse(parsed["receipt"]["limited"])
            for record in parsed["records"]:
                if record["path"] in counts:
                    counts[record["path"]] += 1
                    reconstructed[meta["project"]][meta["section"]].append(record["values"])
        self.assertEqual(counts, {"/nodes/*": 122, "/edges/*": 135})
        for name, original in json.loads(raw).items():
            self.assertEqual(reconstructed[name], {k: original[k] for k in ("nodes", "edges")})

    def test_chunks_below_parser_limit_do_not_claim_independent_sources(self):
        source = graph(160)
        source["pkg"]["edges"] = []
        docs = documents(encode(source).encode(), SOURCE, WHEN)
        self.assertEqual(len(docs), 2)
        retained = [r for doc in docs for r in extract(doc)["records"] if r["path"] == "/nodes/*"]
        self.assertEqual(len(retained), 160)
        self.assertTrue(all(not extract(d)["receipt"]["limited"] for d in docs))
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "state.sqlite"
            with Kernel(path, create=True) as kernel:
                before = kernel.status()
                for doc in docs:
                    self.assertEqual(kernel.observe(doc)["status"], "RECORDED")
                state, head, _ = kernel._load()
                self.assertEqual(groups(state), [])
                self.assertEqual(kernel.status()["genome"], before["genome"])
                self.assertEqual(kernel.observe(docs[0])["status"], "DUPLICATE")
                self.assertEqual(kernel.status()["events"], 3)
            with Kernel(path) as restarted:
                result = restarted.audit(expected_head=head)
                self.assertEqual(result["status"], "PASS")
                self.assertEqual(result["observations"]["documents_seen"], 2)
                self.assertEqual(result["admissions_total"], 0)

    def test_rejects_broken_topology_and_wrong_identity(self):
        variants = []
        bad = graph(); bad["pkg"]["nodes"].append(deepcopy(bad["pkg"]["nodes"][0])); variants.append(bad)
        bad = graph(); bad["pkg"]["edges"][0]["dst"] = "pkg.m:missing"; variants.append(bad)
        bad = graph(); bad["pkg"]["edges"].append(deepcopy(bad["pkg"]["edges"][0])); variants.append(bad)
        bad = graph(); bad["pkg"]["nodes"][0]["module"] = "other.m"; variants.append(bad)
        bad = graph(); bad["pkg"]["edges"][0]["kind"] = "python.exec"; variants.append(bad)
        bad = graph(); bad["pkg"]["project"] = "other"; variants.append(bad)
        for value in variants:
            with self.subTest(value=value):
                with self.assertRaises(ContractError):
                    validate(encode(value).encode())

    def test_rejects_noncanonical_or_nonportable_input(self):
        values = [b'{"pkg":{},"pkg":{}}', b'{"pkg":NaN}', b'\xff', b'{}', b'[]', b' ' * (SOURCE_LIMIT + 1)]
        bad = graph(); bad["pkg"]["version"] = "\ud800"
        values.append(json.dumps(bad).encode())
        for raw in values:
            with self.subTest(prefix=repr(raw[:40])):
                with self.assertRaises(ContractError):
                    validate(raw)

    def test_static_recursion_is_data_and_unknown_fields_are_rejected(self):
        value = graph()
        value["pkg"]["edges"] = [{"src": "pkg.m:f0", "dst": "pkg.m:f0", "kind": "call"}]
        self.assertEqual(validate(encode(value).encode()), value)
        value["pkg"]["nodes"][0]["source"] = "raise RuntimeError('must not execute')"
        with self.assertRaises(ContractError):
            validate(encode(value).encode())

    def test_provenance_uses_the_existing_kernel_url_contract(self):
        for source in ("http://example.org/graph", "https://user:password@example.org/graph", "https://example.org/graph#chunk"):
            with self.subTest(source=source):
                with self.assertRaises(ContractError):
                    documents(encode(graph()).encode(), source, WHEN)

    def test_pinned_source_rejects_changed_file_before_projection(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            path = root / "graph.json"
            original = encode(graph()).encode()
            path.write_bytes(original)
            subprocess.run(["git", "init", "-q", str(root)], check=True)
            subprocess.run(["git", "add", "graph.json"], cwd=root, check=True)
            subprocess.run(["git", "-c", "user.name=Nova Test", "-c", "user.email=nova-test@example.invalid",
                            "commit", "-qm", "Freeze test input"], cwd=root, check=True)
            commit = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=root, text=True).strip()
            with patch.object(import_static_codeflow, "ROOT", root):
                raw, url = import_static_codeflow.pinned_source(path, commit)
                self.assertEqual(raw, original)
                self.assertIn("/blob/" + commit + "/graph.json", url)
                path.write_bytes(original.replace(b'"1.0"', b'"2.0"'))
                with self.assertRaises(ContractError):
                    import_static_codeflow.pinned_source(path, commit)


if __name__ == "__main__":
    unittest.main()

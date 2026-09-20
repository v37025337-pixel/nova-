import copy
import sys
import tempfile
import unittest
from pathlib import Path

from nova_core import library_evolution, python_tools
from nova_core.contracts import ContractError, digest
from nova_core.isolation import evaluate
from nova_core.kernel import Kernel
from nova_core.language import execute


def key(value):
    return tuple(int(x) for x in value.split("."))


def task():
    train = [["1.2", "1.3", "1.10", "2.0", "2.1"], ["3.1", "3.2", "3.10", "4.0", "5.0"]]
    holdout = [["6.20", "6.3", "6.2", "6.11", "7.0"], ["8.10", "8.2", "8.30", "8.5", "9.1"]]
    return {"id": "observed-ordering", "source": "test:unresolved-observation",
            "train": [{"input": {"items": v}, "output": sorted(v, key=key)} for v in train],
            "holdout": [{"input": {"items": v}, "output": sorted(v, key=key)} for v in holdout]}


def relation_rows():
    result = []
    for i in range(8):
        a, b = str(50+i)+".2", str(50+i)+".11"
        result.extend([{"input": {"left": a, "right": b}, "output": True},
                       {"input": {"left": b, "right": a}, "output": False}])
    return result


class PythonToolsTests(unittest.TestCase):
    def test_composes_tools_for_different_data_without_a_version_template(self):
        for sep in (":", "/", "|"):
            rows = [{"input": {"left": a.replace(".", sep), "right": b.replace(".", sep)},
                     "output": key(a) < key(b)} for a, b in
                    [("2.10", "2.3"), ("4.2", "4.11"), ("1.10", "2.0"), ("8.3", "1.2")]]
            found = python_tools.synthesize(rows, "a"*64)
            self.assertIsNotNone(found["gene"])
            gene = found["gene"]
            self.assertLessEqual(found["attempts"], 12000)
            result = evaluate([{"program": gene, "rows": [
                {"input": {"left": "12"+sep+"2", "right": "12"+sep+"20"}, "output": True}]}], {gene["id"]: gene})
            self.assertEqual(result["results"][0]["passed"], 1)
            self.assertEqual(result["isolation"], "linux_seccomp_v1")

    def test_unlisted_imports_and_changed_generated_code_are_rejected(self):
        for tool in ("os.system", "builtins.eval", "builtins.open", "numpy.load"):
            with self.assertRaises(ContractError):
                python_tools.gene(["call", tool, ["input", "x"]], ["x"], "b"*64)
        gene = python_tools.gene(["call", "builtins.int", ["input", "x"]], ["x"], "b"*64)
        for change in ({"source": "def solve(inputs, recall): return 123\n"}, {"tools": []}, {"catalogue": "c"*64}):
            with self.assertRaises(ContractError):
                execute({**gene, **change}, {"x": "3"}, {})
        with self.assertRaises(ContractError):
            python_tools.invoke("builtins.int", "9"*200)

    def test_retry_requires_new_runtime_and_no_previous_fresh_evaluation(self):
        state = {"runtime_manifest": {"schema": "nova.kernel.v6"}}
        record = {"goal": {"runtime_digest": "older"}, "outcome": {
            "reason": "KNOWLEDGE_NOT_EXECUTABLE_IN_CURRENT_GRAMMAR", "report": {"fresh_cases_seen": 0}}}
        self.assertTrue(library_evolution.retryable(record, state))
        record["goal"]["runtime_digest"] = digest(state["runtime_manifest"])
        self.assertFalse(library_evolution.retryable(record, state))
        record["goal"]["runtime_digest"] = "older"
        record["outcome"]["reason"] = "AUTONOMOUS_HOLDOUT_FAILED"
        self.assertFalse(library_evolution.retryable(record, state))

    def test_restart_transfer_dependency_ablation_and_exact_rollback(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory)/"state.sqlite"
            with Kernel(path, create=True) as kernel:
                kernel.register([task()])
                self.assertEqual(kernel.step()["reason"], "HOLDOUT_FAILED")
                kernel.start_autonomy()
                first = kernel.step()["goal"]
                frozen = self.freeze(kernel)
                result = kernel.autonomy_assess(frozen["freeze"], relation_rows())
                self.assertEqual(result["status"], "ADMITTED")
                self.assertEqual(result["report"]["fresh"]["passed"], 16)
                prior = kernel.genome()
            with Kernel(path) as kernel:
                transfer = kernel.step()["goal"]
                self.assertEqual(transfer["transfer_from"], first["id"])
                self.assertEqual(transfer["required_capability"], result["program"]["id"])
                frozen = self.freeze(kernel)
                rows = []
                for i in range(16):
                    values = [f"{100+i}.11", f"{100+i}.2", f"{100+i}.1", f"{100+i}.2"]
                    rows.append({"input": {"items": values}, "output": sorted(values, key=key)})
                admitted = kernel.autonomy_assess(frozen["freeze"], rows)
                self.assertEqual(admitted["status"], "ADMITTED")
                self.assertEqual(admitted["report"]["ablation"][result["program"]["id"]]["passed"], 0)
                self.assertEqual(admitted["report"]["ablation"][result["primitive"]["id"]]["passed"], 0)
                self.assertEqual(kernel.predict(transfer["id"], {"items": ["1.10", "1.2"]}), ["1.2", "1.10"])
                kernel.rollback(1)
                self.assertEqual(kernel.genome(), prior)
                with self.assertRaises(ContractError):
                    kernel.predict(transfer["id"], {"items": ["1.10", "1.2"]})
                self.assertEqual(kernel.step()["status"], "IDLE")

    def freeze(self, kernel):
        kernel.step()
        req = kernel.step()["request"]
        self.assertEqual(req["kind"], "PYTHON_CATALOGUE")
        raw = {"kind": "PYTHON_CATALOGUE", "request": req["id"], "catalogue": python_tools.catalogue(),
               "environment": {"python": list(sys.version_info[:2])}}
        tampered = copy.deepcopy(raw)
        tampered["catalogue"]["tools"][0]["name"] = "os.system"
        head = kernel.status()["head"]
        with self.assertRaises(ContractError):
            kernel.autonomy_response(tampered)
        self.assertEqual(kernel.status()["head"], head)
        kernel.autonomy_response(raw)
        self.assertEqual(kernel.step()["phase"], "SEARCH_FROZEN")
        result = kernel.step()
        self.assertEqual(result["status"], "FROZEN")
        return result


if __name__ == "__main__":
    unittest.main()

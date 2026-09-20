import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


class CliTests(unittest.TestCase):
    def invoke(self, state, *args):
        return subprocess.run([sys.executable, "-m", "nova_core", "--state", str(state), *args],
                              cwd=ROOT, text=True, capture_output=True, timeout=30)

    def test_documented_workflow_across_separate_processes(self):
        with tempfile.TemporaryDirectory() as tmp:
            state = Path(tmp) / "run.sqlite"
            learned = self.invoke(state, "learn", "examples/three_generations.json", "--steps", "3")
            self.assertEqual(learned.returncode, 0, learned.stderr)
            data = json.loads(learned.stdout)
            self.assertEqual([r["status"] for r in data["steps"]], ["ADMITTED"] * 3)
            result = self.invoke(state, "predict", "30-record", "--input", '{"text":"  новый разум  "}')
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(json.loads(result.stdout), {"output": {"name": "НОВЫЙ РАЗУМ", "length": 11}})
            verified = self.invoke(state, "verify", "--expected-head", data["state"]["head"])
            self.assertEqual(verified.returncode, 0, verified.stderr)
            self.assertEqual(json.loads(verified.stdout)["status"], "PASS")

    def test_invalid_commands_do_not_create_a_state(self):
        with tempfile.TemporaryDirectory() as tmp:
            state = Path(tmp) / "absent.sqlite"
            for args in [("status",), ("learn", "examples/three_generations.json", "--steps", "0")]:
                result = self.invoke(state, *args)
                self.assertEqual(result.returncode, 2)
                self.assertFalse(state.exists())
                self.assertEqual(json.loads(result.stderr)["status"], "ERROR")


if __name__ == "__main__":
    unittest.main()

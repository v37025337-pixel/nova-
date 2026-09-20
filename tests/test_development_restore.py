import copy
import tempfile
import unittest
from pathlib import Path

from nova_core.contracts import ContractError, IntegrityError, digest
from nova_core.kernel import Kernel
from nova_core.memory import ZERO
from scripts.run_development_chain import restore
from tests.test_kernel import example_task


class DevelopmentRestoreTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.destination = Path(self.tmp.name) / "restored.sqlite"
        with Kernel(Path(self.tmp.name) / "source.sqlite", create=True) as kernel:
            kernel.register([example_task()])
            self.assertEqual(kernel.step()["status"], "ADMITTED")
            events, head = kernel.journal.read()
            self.exported = {"schema": "nova.journal.export.v1", "head": head, "events": events}

    def tearDown(self):
        self.tmp.cleanup()

    def test_verified_export_restores_executable_memory(self):
        restore(self.exported, self.destination)
        with Kernel(self.destination) as kernel:
            self.assertEqual(kernel.audit(expected_head=self.exported["head"])["status"], "PASS")
            self.assertEqual(kernel.predict("trim", {"text": "  память  "}), "память")

    def test_wrong_external_head_does_not_publish_state(self):
        altered = copy.deepcopy(self.exported)
        altered["head"] = "f" * 64
        with self.assertRaises(ContractError):
            restore(altered, self.destination)
        self.assertFalse(self.destination.exists())

    def test_rehashed_false_receipt_does_not_publish_state(self):
        altered = copy.deepcopy(self.exported)
        altered["events"][-1]["gate"]["holdout"]["passed"] = 0
        previous = ZERO
        for seq, body in enumerate(altered["events"], 1):
            previous = digest([seq, previous, body])
        altered["head"] = previous
        with self.assertRaises(IntegrityError):
            restore(altered, self.destination)
        self.assertFalse(self.destination.exists())

    def test_existing_file_is_not_overwritten(self):
        self.destination.write_bytes(b"existing data")
        with self.assertRaises(ContractError):
            restore(self.exported, self.destination)
        self.assertEqual(self.destination.read_bytes(), b"existing data")


if __name__ == "__main__":
    unittest.main()

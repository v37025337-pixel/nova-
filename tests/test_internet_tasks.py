"""Boundary contracts for the operator-owned internet adapter."""

import unittest
import tempfile
from pathlib import Path

from nova_core.contracts import ContractError
from scripts.run_internet_tasks import checked_url, example, save_program


class InternetAdapterTests(unittest.TestCase):
    def test_only_explicit_public_api_paths_are_accepted(self):
        for url in ("https://pypi.org/pypi/PyYAML/json", "https://api.github.com/repos/pallets/flask"):
            self.assertEqual(checked_url(url), url)
        for url in ("http://pypi.org/pypi/pip/json", "https://127.0.0.1/pypi/pip/json",
                    "https://pypi.org.evil.example/pypi/pip/json", "https://api.github.com/user",
                    "https://user:password@pypi.org/pypi/pip/json", "https://pypi.org:444/pypi/pip/json",
                    "https://pypi.org/pypi/pip/json?token=x", "https://pypi.org/pypi/../json"):
            with self.subTest(url=url), self.assertRaises(ContractError):
                checked_url(url)

    def test_numeric_version_oracle_is_not_lexical_sort(self):
        receipt = {"projection": {"versions": ["2.9", "10.0", "2.10", "1.0"]}}
        self.assertEqual(example("290-numeric-version-order", receipt)["output"],
                         ["1.0", "2.9", "2.10", "10.0"])

    def test_independent_sha_reference_uses_original_name(self):
        receipt = {"projection": {"name": "abc", "version": "1.0"}}
        self.assertEqual(example("250-online-hash-json", receipt)["output"],
                         '{"digest":"ba7816bf8f01cfea414140de5dae2223b00361a396177a9cb410ff61f20015ad","name":"ABC"}')

    def test_rejected_candidate_preserves_admitted_source(self):
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory)
            accepted = {"generation": 20, "status": "ADMITTED", "selection": {"task": "hash"},
                        "program": {"source": "accepted code\n"}}
            rejected = {"generation": 20, "status": "WITHHOLD", "selection": {"task": "versions"},
                        "program": {"source": "rejected code\n"}}
            a = save_program(accepted, output)
            b = save_program(rejected, output)
            self.assertNotEqual(a, b)
            self.assertEqual(a.read_text(), "accepted code\n")
            self.assertEqual(b.read_text(), "rejected code\n")


if __name__ == "__main__":
    unittest.main()

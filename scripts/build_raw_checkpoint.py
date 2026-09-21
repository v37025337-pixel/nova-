"""Reproduce the 1.1 bootstrap by fully replaying the frozen U1 journal offline."""

import subprocess
import sys

from unified_v1_archive import ROOT, extracted

DRIVER = r'''
from pathlib import Path
import sys, tempfile
from unittest.mock import patch
from nova_core.cognition.kernel import Kernel, manifest
from nova_core.cognition import checkpoint
from nova_core.contracts import digest
target = Path(sys.argv[1])
exported = checkpoint.read("experience/unified-v1/live/journal.json.gz")
with tempfile.TemporaryDirectory() as directory, patch("nova_next.network.fetch", side_effect=AssertionError("network during migration")):
    path = Path(directory) / "prior.sqlite"
    Kernel.restore(exported, path)
    with Kernel(path) as kernel:
        proof = kernel.audit()
        assert proof["status"] == "PASS"
        state, head, _ = kernel._load()
        body = {"schema": "nova.unified.bootstrap.v2", "state": checkpoint.pack(state),
                "proof": {"status": "PASS", "parents": {"unified_v1": {"head": head,
                          "runtime": digest(manifest()), "genome": proof["state"]["genome"]}},
                          "regression": proof["regression"]}}
        assert checkpoint.read(target) == body, "bootstrap differs from fully replayed parent"
        print("PASS: full U1 replay reproduces the 1.1 bootstrap and all 24 retained skills", flush=True)
'''


if __name__ == "__main__":
    with extracted() as root:
        result = subprocess.run([sys.executable, "-c", DRIVER, str(ROOT / "nova_core/cognition/bootstrap-v2.json.gz")], cwd=root)
        raise SystemExit(result.returncode)

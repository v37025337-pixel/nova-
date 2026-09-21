"""Replay the historical U1 release using its exact, digest-pinned runtime."""

import subprocess
import sys

from unified_v1_archive import extracted


if __name__ == "__main__":
    with extracted() as root:
        result = subprocess.run([sys.executable, str(root / "scripts/verify_unified.py"), *sys.argv[1:]], cwd=root)
        raise SystemExit(result.returncode)

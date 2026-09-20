"""Verify the committed runtime manifest, independently of a mutable state."""

import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def main():
    manifest = json.loads((ROOT / "canonical/release.json").read_text())
    expected = manifest["source_sha256"]
    actual = {str(p.relative_to(ROOT)): hashlib.sha256(p.read_bytes()).hexdigest()
              for p in sorted((ROOT / "nova_core").glob("*.py"))}
    if actual != expected:
        raise SystemExit("FAIL: runtime manifest does not match source files")
    print(json.dumps({"status": "PASS", "source_files": len(actual),
                      "version": manifest["version"]}, sort_keys=True))


if __name__ == "__main__":
    main()

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
    tools_manifest = ROOT / "canonical/code-reader.json"
    tool_count = 0
    if tools_manifest.exists() or (ROOT / "nova_tools").exists():
        expected_tools = json.loads(tools_manifest.read_text())["source_sha256"]
        actual_tools = {str(p.relative_to(ROOT)): hashlib.sha256(p.read_bytes()).hexdigest()
                        for p in sorted((ROOT / "nova_tools").glob("*.py"))}
        if actual_tools != expected_tools:
            raise SystemExit("FAIL: code-reader manifest does not match source files")
        tool_count = len(actual_tools)
    print(json.dumps({"status": "PASS", "source_files": len(actual),
                      "tool_files": tool_count, "version": manifest["version"]}, sort_keys=True))


if __name__ == "__main__":
    main()

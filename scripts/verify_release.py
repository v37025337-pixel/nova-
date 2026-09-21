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
    codeflow_count = 0
    codeflow_manifest = ROOT / "canonical/static-codeflow.json"
    if codeflow_manifest.exists():
        expected_codeflow = json.loads(codeflow_manifest.read_text())["file_sha256"]
        actual_codeflow = {name: hashlib.sha256((ROOT / name).read_bytes()).hexdigest()
                           for name in expected_codeflow}
        if actual_codeflow != expected_codeflow:
            raise SystemExit("FAIL: static-codeflow manifest does not match its files")
        codeflow_count = len(actual_codeflow)
    probe_count = 0
    probe_manifest = ROOT / "canonical/codeflow-goal-probe.json"
    if probe_manifest.exists():
        expected_probe = json.loads(probe_manifest.read_text())["file_sha256"]
        actual_probe = {name: hashlib.sha256((ROOT / name).read_bytes()).hexdigest()
                        for name in expected_probe}
        if actual_probe != expected_probe:
            raise SystemExit("FAIL: codeflow goal probe manifest does not match its files")
        probe_count = len(actual_probe)
    print(json.dumps({"status": "PASS", "source_files": len(actual),
                      "tool_files": tool_count, "static_codeflow_files": codeflow_count,
                      "codeflow_goal_probe_files": probe_count,
                      "version": manifest["version"]}, sort_keys=True))


if __name__ == "__main__":
    main()

"""Verify both parent histories once and produce the lossless unified trust root."""

import hashlib
import json
from pathlib import Path
import sys
import tempfile
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from nova_core.contracts import digest
from nova_core.kernel import Kernel as HistoricalKernel
from nova_core.cognition.checkpoint import pack, write, read
from nova_core.memory import Journal, ZERO
from nova_next.kernel import Kernel as GraphHistory
from nova_next.evaluation import legacy_regression


def reconstruct(archive, destination):
    exported = read(archive)
    journal, head = Journal(destination, create=True), ZERO
    try:
        for event in exported["events"]:
            head = journal.append(event, head)
        if head != exported["head"]:
            raise ValueError("parent archive head differs")
        events, checked = journal.read()
        return {"head": checked, "events": len(events)}
    finally:
        journal.close()


def main():
    started = time.monotonic()
    with tempfile.TemporaryDirectory() as directory:
        old_path, graph_path = Path(directory) / "nova.sqlite", Path(directory) / "graph.sqlite"
        reconstruct(ROOT / "experience/codeflow-goal-probe-v1/journal.json.gz", old_path)
        reconstruct(ROOT / "experience/nova-next-v2/journal.json.gz", graph_path)
        with HistoricalKernel(old_path) as parent:
            legacy, old_head, old_events = parent._load()
            print(json.dumps({"parent": "Nova G22", "head": old_head, "events": old_events}), flush=True)
        with GraphHistory(graph_path) as parent:
            graph, graph_head, graph_events = parent._load()
            print(json.dumps({"parent": "Next G2", "head": graph_head, "events": graph_events}), flush=True)
    regression = legacy_regression()
    if regression["passed"] != regression["total"]:
        raise ValueError("parent regression failed")
    proof = {"status": "PASS", "method": "full semantic replay of both original parent journals",
             "parents": {"nova": {"head": old_head, "events": old_events, "generation": legacy["current"]},
                         "graph": {"head": graph_head, "events": graph_events, "generation": graph["generation"]}},
             "legacy_regression": regression,
             "parent_archive_sha256": {name: hashlib.sha256((ROOT / name).read_bytes()).hexdigest() for name in
                                       ("experience/codeflow-goal-probe-v1/journal.json.gz", "experience/nova-next-v2/journal.json.gz")}}
    body = {"schema": "nova.unified.bootstrap.v1", "proof": proof,
            "legacy": pack(legacy), "graph": pack(graph)}
    target = ROOT / "nova_core/cognition/bootstrap.json.gz"
    if target.exists():
        if digest(read(target)) != digest(body):
            raise ValueError("rebuilt checkpoint differs; do not overwrite the released trust root")
    else:
        write(target, body)
    output = ROOT / "experience/unified-v1"
    output.mkdir(exist_ok=True)
    (output / "migration.json").write_text(json.dumps({**proof, "bootstrap_digest": digest(body),
          "bootstrap_sha256": hashlib.sha256(target.read_bytes()).hexdigest(),
          "seconds": time.monotonic() - started}, indent=2) + "\n")
    print(json.dumps({"status": "PASS", "bootstrap_digest": digest(body), "bytes": target.stat().st_size}), flush=True)


if __name__ == "__main__":
    main()

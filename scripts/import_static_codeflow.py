"""Import bounded, source-labelled static graphs through Kernel.observe().

Project versions and call edges are supplied data, not verified execution.
All chunks retain one source identity; splitting never creates fresh evidence.
"""

import argparse
from datetime import datetime, timezone
import gzip
import hashlib
import json
from pathlib import Path
import re
import sqlite3
import subprocess
import sys
import time
from urllib.parse import quote

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from nova_core.contracts import ContractError, decode, digest, encode
from nova_core.evaluation import score
from nova_core.kernel import Kernel, context, runtime_manifest
from nova_core.observations import CONFIG, extract
from scripts.run_development_chain import restore

INPUT_SCHEMA = "ucr.external-static-codeflow/1"
REPOSITORY = "v37025337-pixel/nova-"
SOURCE_LIMIT = 262144
ROWS_PER_DOCUMENT = CONFIG["records_per_document"] - 2


def write(path, value):
    path.write_text(json.dumps(value, ensure_ascii=True, allow_nan=False,
                               sort_keys=True, indent=2) + "\n", encoding="utf-8")


def text_field(value, label, limit=512):
    if type(value) is not str or not 1 <= len(value) <= limit:
        raise ContractError("invalid graph field: " + label)
    if any(ord(c) < 32 for c in value):
        raise ContractError("control character in graph field: " + label)
    try:
        value.encode("utf-8")
    except UnicodeError as exc:
        raise ContractError("nonportable graph field: " + label) from exc
    return value


def validate(raw):
    if type(raw) is not bytes or not 1 <= len(raw) <= SOURCE_LIMIT:
        raise ContractError("static graph input must contain 1..262144 bytes")
    try:
        graphs = decode(raw.decode("utf-8"))
    except (UnicodeError, ValueError, RecursionError) as exc:
        raise ContractError("static graph input must be strict UTF-8 JSON") from exc
    if type(graphs) is not dict or not 1 <= len(graphs) <= 16:
        raise ContractError("static graph input requires 1..16 projects")
    for project, graph in graphs.items():
        text_field(project, "project", 128)
        if type(graph) is not dict or set(graph) != {"schema", "project", "version", "projection", "nodes", "edges"}:
            raise ContractError("unsupported static graph fields")
        if graph["schema"] != INPUT_SCHEMA or graph["project"] != project:
            raise ContractError("static graph schema/project mismatch")
        if graph["projection"] != "intermodule-causal-core":
            raise ContractError("unsupported static graph projection")
        text_field(graph["version"], "version", 64)
        nodes, edges = graph["nodes"], graph["edges"]
        if type(nodes) is not list or not 1 <= len(nodes) <= 4096:
            raise ContractError("static graph requires 1..4096 nodes")
        if type(edges) is not list or len(edges) > 8192:
            raise ContractError("static graph accepts at most 8192 edges")
        identities = set()
        for node in nodes:
            if type(node) is not dict or set(node) != {"id", "module", "name", "kind"}:
                raise ContractError("invalid static graph node")
            for key, value in node.items():
                text_field(value, key)
            if (node["kind"] not in ("function", "method") or
                    node["id"] != node["module"] + ":" + node["name"] or
                    not (node["module"] == project or node["module"].startswith(project + "."))):
                raise ContractError("inconsistent static graph node identity")
            if node["id"] in identities:
                raise ContractError("duplicate static graph node")
            identities.add(node["id"])
        seen_edges = set()
        for edge in edges:
            if type(edge) is not dict or set(edge) != {"src", "dst", "kind"}:
                raise ContractError("invalid static graph edge")
            for key, value in edge.items():
                text_field(value, key)
            if edge["kind"] not in ("assign_call", "call", "return_call"):
                raise ContractError("unsupported static call relation")
            if edge["src"] not in identities or edge["dst"] not in identities:
                raise ContractError("static graph edge has an unknown endpoint")
            token = (edge["src"], edge["dst"], edge["kind"])
            if token in seen_edges:
                raise ContractError("duplicate static graph edge")
            seen_edges.add(token)
    return graphs


def documents(raw, source_url, obtained_at):
    graphs = validate(raw)
    source_hash = hashlib.sha256(raw).hexdigest()
    result = []
    for project, graph in sorted(graphs.items()):
        for section in ("nodes", "edges"):
            for start in range(0, len(graph[section]), ROWS_PER_DOCUMENT):
                rows = graph[section][start:start + ROWS_PER_DOCUMENT]
                body = {"metadata": {
                    "schema": "nova.static-codeflow-observation.v1",
                    "representation": "user_supplied_static_call_graph",
                    "project": project, "claimed_version": graph["version"],
                    "original_schema": graph["schema"], "original_sha256": source_hash,
                    "upstream_source_verified": False, "dynamic_execution_verified": False,
                    "section": section, "start": start, "rows": len(rows)}, section: rows}
                text = encode(body)
                doc = {"source": source_url, "media_type": "application/json", "text": text,
                       "sha256": hashlib.sha256(text.encode("utf-8")).hexdigest(), "obtained_at": obtained_at}
                extracted = extract(doc)
                retained = [r["values"] for r in extracted["records"] if r["path"] == "/" + section + "/*"]
                if extracted["receipt"]["limited"] or retained != rows:
                    raise ContractError("static graph projection lost or changed a record")
                result.append(doc)
    if len(result) > CONFIG["window_documents"]:
        raise ContractError("static graph chunks exceed the observation window")
    return result


def pinned_source(path, commit):
    if not re.fullmatch(r"[0-9a-f]{40}", commit):
        raise ContractError("source commit must be a full Git SHA")
    relative = path.resolve().relative_to(ROOT).as_posix()
    with path.open("rb") as stream:
        raw = stream.read(SOURCE_LIMIT + 1)
    if len(raw) > SOURCE_LIMIT:
        raise ContractError("static graph input exceeds the byte limit")
    size = int(subprocess.check_output(["git", "cat-file", "-s", commit + ":" + relative], cwd=ROOT))
    if size != len(raw):
        raise ContractError("graph input size differs from the pinned source commit")
    if raw != subprocess.check_output(["git", "show", commit + ":" + relative], cwd=ROOT):
        raise ContractError("graph input differs from the pinned source commit")
    return raw, "https://github.com/" + REPOSITORY + "/blob/" + commit + "/" + quote(relative, safe="/")


def run(source, parent_path, output, source_commit, checkpoint=None, replay_timeout=600):
    if type(replay_timeout) is not int or not 1 <= replay_timeout <= 3600:
        raise ContractError("replay timeout must be in 1..3600 seconds")
    raw, source_url = pinned_source(source, source_commit)
    obtained_at = datetime.now(timezone.utc).isoformat()
    incoming = documents(raw, source_url, obtained_at)
    parent_raw = parent_path.read_bytes()
    parent = decode((gzip.decompress(parent_raw) if parent_path.suffix == ".gz" else parent_raw).decode("utf-8"))
    if set(parent) != {"schema", "head", "events"} or parent["schema"] != "nova.journal.export.v1":
        raise ContractError("unsupported parent journal export")
    output.mkdir(parents=True, exist_ok=False)
    state_path = output / "state.sqlite"
    protocol = {"schema": "nova.static-codeflow-import.v1", "author": "maintainer",
                "source_commit": source_commit, "source_url": source_url,
                "source_sha256": hashlib.sha256(raw).hexdigest(),
                "parent_path": str(parent_path.relative_to(ROOT)), "parent_head": parent["head"],
                "parent_file_sha256": hashlib.sha256(parent_raw).hexdigest(),
                "runtime_manifest": runtime_manifest(), "importer_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
                "new_tasks": 0, "development_steps": 0, "fresh_rows": 0,
                "source_identities": 1, "replay_timeout_seconds": replay_timeout,
                "checkpoint_used": checkpoint is not None}
    write(output / "protocol.json", protocol)
    write(output / "observations.json", incoming)
    print(json.dumps({"phase": "verify_parent", "events": len(parent["events"])}), flush=True)
    if checkpoint is None:
        restore(parent, state_path)
    else:
        # The copy is only an acceleration of transport. Kernel construction
        # below replays it before any import, and exact parent equality is required.
        with sqlite3.connect(checkpoint.resolve().as_uri() + "?mode=ro", uri=True) as origin:
            with sqlite3.connect(state_path) as target:
                origin.backup(target)
    with Kernel(state_path) as kernel:
        events, head = kernel.journal.read()
        if events != parent["events"] or head != parent["head"]:
            raise ContractError("checkpoint does not match the anchored parent journal")
        before = kernel.status()
        if before["upgrade_required"]:
            raise ContractError("import requires a current runtime checkpoint")
        receipts = [kernel.observe(doc) for doc in incoming]
        if any(r["status"] != "RECORDED" or r["limited"] for r in receipts):
            raise ContractError("static graph import did not record every complete document")
        snapshot, _, _ = kernel._load()
        active, memory, _ = context(snapshot)
        regression = {tid: score(memory[pid], snapshot["tasks"][tid]["train"] + snapshot["tasks"][tid]["holdout"], memory)
                      for tid, pid in sorted(active.items())}
        after = kernel.status()
        events, head = kernel.journal.read()
        delta = events[len(parent["events"]):]
        if events[:len(parent["events"])] != parent["events"] or any(e["kind"] != "observation" for e in delta):
            raise ContractError("import changed historical decisions or wrote unexpected events")
        if after["genome"] != before["genome"] or after["admissions_total"] != before["admissions_total"]:
            raise ContractError("data import changed the admitted genome")
        exported = {"schema": "nova.journal.export.v1", "events": events, "head": head}
        (output / "journal.json.gz").write_bytes(gzip.compress(encode(exported).encode("utf-8"), mtime=0))
        write(output / "receipts.json", receipts)
        write(output / "regression.json", regression)
        graphs = validate(raw)
        summary = {"schema": "nova.static-codeflow-import-result.v1", "status": "AWAITING_REPLAY",
                   "before": before, "after": after, "protocol_sha256": digest(protocol),
                   "projects": {name: {"claimed_version": g["version"], "nodes": len(g["nodes"]), "edges": len(g["edges"])}
                                for name, g in sorted(graphs.items())},
                   "documents_recorded": len(receipts), "source_identities": 1,
                   "parent_prefix_unchanged": True, "new_admissions": 0, "new_tasks": 0,
                   "development_steps": 0, "fresh_rows": 0,
                   "regression": {"passed": sum(r["passed"] for r in regression.values()),
                                  "total": sum(r["total"] for r in regression.values()), "skills": len(active)},
                   "limitations": ["Static call edges are supplied data, not proof of runtime causality.",
                                   "Project versions and edges were not checked against upstream source.",
                                   "This import does not install UCR 25 or admit a new capability."]}
        write(output / "summary.json", summary)
    print(json.dumps({"phase": "separate_process_replay", "events": len(events), "head": head}), flush=True)
    started = time.monotonic()
    command = [sys.executable, "-m", "nova_core", "--state", str(state_path), "verify", "--expected-head", head]
    try:
        replay = subprocess.run(command, cwd=ROOT, text=True, capture_output=True, timeout=replay_timeout)
        stdout, stderr, code = replay.stdout, replay.stderr, replay.returncode
    except subprocess.TimeoutExpired as exc:
        stdout, stderr, code = exc.stdout or b"", exc.stderr or b"", 124
        if isinstance(stdout, bytes):
            stdout = stdout.decode("utf-8", errors="replace")
        if isinstance(stderr, bytes):
            stderr = stderr.decode("utf-8", errors="replace")
    (output / "restart-stdout.json").write_text(stdout, encoding="utf-8")
    (output / "restart-stderr.txt").write_text(stderr, encoding="utf-8")
    checked = decode(stdout) if code == 0 else {}
    summary["cold_replay"] = {"exit_code": code, "status": checked.get("status", "TIMEOUT" if code == 124 else "ERROR"),
                              "events": checked.get("events"), "head": checked.get("head"),
                              "seconds": time.monotonic() - started, "timeout_seconds": replay_timeout}
    summary["status"] = ("PASS_IMPORT" if code == 0 and checked.get("status") == "PASS" and
                         checked.get("head") == head and checked.get("events") == len(events) and
                         summary["regression"]["passed"] == summary["regression"]["total"] else "FAIL")
    write(output / "summary.json", summary)
    print(json.dumps({k: summary[k] for k in ("status", "projects", "documents_recorded", "new_admissions", "regression", "cold_replay")}), flush=True)
    return 0 if summary["status"] == "PASS_IMPORT" else 1


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("input", type=Path)
    parser.add_argument("--parent", type=Path, required=True)
    parser.add_argument("--source-commit", required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--checkpoint", type=Path, help="optional SQLite copy, fully replayed against the parent before import")
    parser.add_argument("--replay-timeout", type=int, default=600)
    args = parser.parse_args()
    return run(args.input.resolve(), args.parent.resolve(), args.output.resolve(), args.source_commit,
               args.checkpoint.resolve() if args.checkpoint else None, args.replay_timeout)


if __name__ == "__main__":
    raise SystemExit(main())

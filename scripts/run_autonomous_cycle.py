"""I/O broker for native goals; never registers a task or supplies a program.

The process stays alive while the operator fulfils recorded SEARCH/READ requests.
Send one JSON command per line: {"response": "path"}, {"evaluation": "path"},
or {"finish": true}. Search is performed by the connected search service; document
transport and deterministic text extraction are available via the read subcommand.
"""

import argparse
from datetime import datetime, timezone
import gzip
import hashlib
from html.parser import HTMLParser
import json
from pathlib import Path
import re
import subprocess
import sys
import time
import urllib.request

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from nova_core.autonomy import source_url
from nova_core.contracts import ContractError, digest, encode
from nova_core.isolation import evaluate
from nova_core.kernel import Kernel, context, runtime_manifest
from nova_core.memory import Journal, ZERO
from run_development_chain import write_json


def emit(value):
    print(json.dumps(value, ensure_ascii=False), flush=True)


def checkpoint(kernel, output, action=None):
    events, head = kernel.journal.read()
    write_json(output / "journal.json", {"schema": "nova.journal.export.v1", "head": head, "events": events})
    write_json(output / "status.json", kernel.status())
    write_json(output / "genome.json", kernel.genome())
    if action is not None:
        write_json(output / "next-action.json", action)
    return events, head


def advance(kernel, output):
    for _ in range(24):
        action = kernel.step()
        checkpoint(kernel, output, action)
        emit({k: action[k] for k in ("status", "reason", "phase", "request", "freeze", "report") if k in action})
        if action["status"] in ("REQUESTED", "WAITING", "FROZEN", "WITHHOLD", "IDLE"):
            return action
    raise ContractError("native step budget exhausted")


def finish(kernel, output, protocol, freeze, started):
    snapshot, _, _ = kernel._load()
    active, memory, _ = context(snapshot)
    results = {}
    for tid, pid in sorted(active.items()):
        task = snapshot["tasks"][tid]
        results[tid] = evaluate([{"program": memory[pid], "rows": task["train"] + task["holdout"]}], memory)["results"][0]
    write_json(output / "regression.json", results)
    events, head = checkpoint(kernel, output)
    backup = ROOT / "state/autonomous-cycle-v1-backup.sqlite"
    if backup.exists():
        raise ContractError("refusing to overwrite an earlier backup")
    kernel.journal.backup(backup)
    parent = json.loads((ROOT / protocol["parent_journal"]).read_text())
    summary = {"schema": "nova.autonomy-attempt.v1", "status": "PENDING_EXTERNAL_REPLAY",
        "protocol_commit": freeze, "protocol_sha256": digest(protocol),
        "head": head, "events": len(events), "parent_generation": protocol["parent_generation"],
        "active_generation": snapshot["current"], "parent_genome": protocol["parent_genome"],
        "active_genome": kernel.genome()["id"],
        "historical_prefix_preserved": encode(events[:len(parent["events"])]) == encode(parent["events"]),
        "runtime_unchanged_after_freeze": digest(runtime_manifest()) == protocol["runtime_sha256"],
        "new_admissions": sum(x["outcome"]["status"] == "ADMITTED" for x in snapshot["autonomy"]["completed"]),
        "completed": snapshot["autonomy"]["completed"],
        "regression": {"passed": sum(r["passed"] for r in results.values()),
            "total": sum(r["total"] for r in results.values()), "skills": len(results)},
        "seconds": time.perf_counter() - started, "backup": str(backup)}
    write_json(output / "run-summary.json", summary)
    emit({"phase": "CHECKPOINT_SAVED", "head": head, "regression": summary["regression"],
          "admissions": summary["new_admissions"], "backup": str(backup)})


def serve(output, state_path, freeze):
    protocol = json.loads((output / "protocol.json").read_text())
    for relative in protocol["frozen_files"] + [str((output / "protocol.json").relative_to(ROOT))]:
        expected = subprocess.check_output(["git", "show", freeze + ":" + relative], cwd=ROOT)
        if expected != (ROOT / relative).read_bytes():
            raise ContractError("changed frozen file: " + relative)
    if digest(runtime_manifest()) != protocol["runtime_sha256"]:
        raise ContractError("runtime differs from pre-registration")
    if state_path.exists() or (output / "journal.json").exists():
        raise ContractError("experiment requires a fresh state and output")
    parent = json.loads((ROOT / protocol["parent_journal"]).read_text())
    if parent["head"] != protocol["parent_head"]:
        raise ContractError("parent anchor mismatch")
    state_path.parent.mkdir(parents=True, exist_ok=True)
    started = time.perf_counter()
    # Kernel initialization independently replays every copied event. A failed
    # import is never exported as an accepted checkpoint.
    journal = Journal(state_path, create=True)
    try:
        head = ZERO
        for body in parent["events"]:
            head = journal.append(body, head)
        if head != parent["head"]:
            raise ContractError("restored chain differs from parent anchor")
    finally:
        journal.close()
    emit({"phase": "REPLAYING_PARENT", "head": head})
    with Kernel(state_path) as kernel:
        if kernel.genome()["id"] != protocol["parent_genome"]:
            raise ContractError("parent genome mismatch")
        write_json(output / "initial-state.json", kernel.status())
        emit({"phase": "UPGRADING_RUNTIME", "genome": kernel.genome()["id"]})
        write_json(output / "runtime-upgrade.json", kernel.upgrade())
        kernel.start_autonomy()
        action = advance(kernel, output)
        for line in sys.stdin:
            command = json.loads(line)
            if command == {"finish": True}:
                finish(kernel, output, protocol, freeze, started)
                return
            if set(command) == {"response"}:
                if action["status"] not in ("REQUESTED", "WAITING"):
                    raise ContractError("native kernel did not request I/O")
                kernel.autonomy_response(json.loads(Path(command["response"]).read_text()))
                action = advance(kernel, output)
            elif set(command) == {"evaluation"}:
                assessment = json.loads(Path(command["evaluation"]).read_text())
                action = kernel.autonomy_assess(assessment["freeze"], assessment["rows"])
                checkpoint(kernel, output, action)
                emit({"status": action["status"], "reason": action["reason"],
                      "next": "restart required before any transfer or next goal"})
            else:
                raise ContractError("unknown broker command")
    raise ContractError("broker input closed without finish")


class TextBlocks(HTMLParser):
    def __init__(self):
        super().__init__()
        self.hidden = 0
        self.parts = []

    def handle_starttag(self, tag, attrs):
        if tag in ("script", "style", "nav", "header", "footer"):
            self.hidden += 1
        elif not self.hidden and tag in ("p", "li", "pre", "h1", "h2", "h3", "dt", "dd"):
            self.parts.append("\n\n")

    def handle_endtag(self, tag):
        if tag in ("script", "style", "nav", "header", "footer"):
            self.hidden = max(0, self.hidden - 1)

    def handle_data(self, data):
        if not self.hidden:
            self.parts.append(data)


class PublicRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        source_url(newurl)
        return super().redirect_request(req, fp, code, msg, headers, newurl)


def read_document(action_path, destination):
    req = json.loads(action_path.read_text())["request"]
    if req["kind"] != "READ":
        raise ContractError("not a native READ request")
    source_url(req["url"])
    with urllib.request.build_opener(PublicRedirect()).open(
            urllib.request.Request(req["url"], headers={"User-Agent": "Nova-evidence-broker/0.5"}), timeout=40) as response:
        raw = response.read(2_000_001)
        if len(raw) > 2_000_000:
            raise ContractError("document exceeds public transport budget")
        final_url, status = response.url, response.status
        charset = response.headers.get_content_charset() or "utf-8"
    parser = TextBlocks()
    parser.feed(raw.decode(charset))
    blocks = [re.sub(r"\s+", " ", b).strip() for b in "".join(parser.parts).split("\n\n")]
    blocks = [(i, b) for i, b in enumerate(blocks) if b]
    terms = set(req["terms"])
    ranked = sorted(blocks, key=lambda p: (-len(terms & set(re.findall(r"[a-z]+", p[1].lower()))), p[0]))
    chosen, remaining = [], 8000
    for index, block in ranked:
        if remaining < 80:
            break
        block = block[:remaining]
        chosen.append((index, block))
        remaining -= len(block) + 2
    text = "\n\n".join(b for _, b in sorted(chosen))
    destination.parent.mkdir(parents=True, exist_ok=True)
    source_hash = hashlib.sha256(raw).hexdigest()
    raw_path = destination.with_suffix(".html.gz")
    raw_path.write_bytes(gzip.compress(raw, mtime=0))
    result = {"kind": "DOCUMENT", "request": req["id"], "url": req["url"], "title": req["title"],
        "text": text, "sha256": hashlib.sha256(text.encode()).hexdigest(), "source_sha256": source_hash,
        "obtained_at": datetime.now(timezone.utc).isoformat()}
    write_json(destination, result)
    write_json(destination.with_suffix(".receipt.json"), {"request": req, "http_status": status,
        "final_url": final_url, "raw_bytes": len(raw), "source_sha256": source_hash,
        "text_sha256": result["sha256"], "response_sha256": digest(result), "raw_file": raw_path.name,
        "extraction": "literal HTML text blocks ranked by native query terms; at most 8000 characters"})
    emit({"response": str(destination), "url": req["url"], "status": status,
          "raw_bytes": len(raw), "text_characters": len(text), "source_sha256": source_hash})


def main():
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="command", required=True)
    run = sub.add_parser("serve")
    run.add_argument("--output", type=Path, required=True)
    run.add_argument("--state", type=Path, required=True)
    run.add_argument("--freeze", required=True)
    read = sub.add_parser("read")
    read.add_argument("action", type=Path)
    read.add_argument("destination", type=Path)
    args = parser.parse_args()
    if args.command == "serve":
        serve(args.output.resolve(), args.state.resolve(), args.freeze)
    else:
        read_document(args.action, args.destination)


if __name__ == "__main__":
    main()

"""An unchanged-G22 experiment: raw external data, no task or answer oracle.

The transport selects no deficits and does not synthesize programs. Existing
knowledge limits remain effective. Stored documents and native understanding
are measured separately. Every fetch, refusal and decision is retained.
"""
import argparse
from collections import Counter
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
import csv
import gzip
import hashlib
import io
import json
from pathlib import Path
import subprocess
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from nova_core.contracts import ContractError, digest, encode
from nova_core.isolation import evaluate
from nova_core.kernel import Kernel, context, runtime_manifest
from nova_core.memory import Journal
from run_development_chain import write_json


def now():
    return datetime.now(timezone.utc).isoformat()


def emit(**fields):
    print(json.dumps(fields, ensure_ascii=False), flush=True)


def frozen(output, commit):
    path = output/"protocol.json"
    protocol = json.loads(path.read_text())
    for name in protocol["frozen_files"] + [str(path.relative_to(ROOT))]:
        if subprocess.check_output(["git", "show", commit+":"+name], cwd=ROOT) != (ROOT/name).read_bytes():
            raise ContractError("changed frozen input: "+name)
    if digest(runtime_manifest()) != protocol["runtime_sha256"]:
        raise ContractError("the experiment requires unchanged G22 runtime sources")
    sources = json.loads((output/"sources.json").read_text())
    if digest(sources) != protocol["sources_sha256"]:
        raise ContractError("source selection changed after freeze")
    return protocol, sources


def checked_url(url, host):
    value = urllib.parse.urlsplit(url)
    if (value.scheme != "https" or value.hostname != host or value.username is not None or
            value.password is not None or value.port not in (None, 443) or value.fragment):
        raise ContractError("transport must stay on its selected public HTTPS source")


class SourceRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        checked_url(newurl, urllib.parse.urlsplit(req.full_url).hostname)
        return super().redirect_request(req, fp, code, msg, headers, newurl)


def fetch(item, output, transport):
    started = time.monotonic()
    receipt = {**item, "requested_at": now(), "status": "FAILED"}
    try:
        checked_url(item["url"], urllib.parse.urlsplit(item["url"]).hostname)
        req = urllib.request.Request(item["url"], headers={
            "User-Agent": "Nova-unlabelled-observation-experiment/1.0",
            "Accept-Encoding": "identity"})
        with urllib.request.build_opener(SourceRedirect()).open(req, timeout=transport["timeout_seconds"]) as response:
            raw = response.read(transport["max_response_bytes"]+1)
            receipt.update(http_status=response.status, final_url=response.url,
                content_type=response.headers.get("Content-Type"), server_date=response.headers.get("Date"),
                last_modified=response.headers.get("Last-Modified"))
            if len(raw) > transport["max_response_bytes"] or response.status != 200:
                raise ContractError("HTTP response or byte budget rejected")
            text = raw.decode(response.headers.get_content_charset() or "utf-8")
        name = "sources/"+item["id"]+".raw.gz"
        (output/name).write_bytes(gzip.compress(raw, mtime=0))
        receipt.update(raw_file=name, bytes=len(raw), characters=len(text), sha256=hashlib.sha256(raw).hexdigest())
        if item["format"] == "json":
            json.loads(text)
        elif item["format"] == "xml":
            if "<!DOCTYPE" in text:
                raise ContractError("external XML DTD is outside this data experiment")
            ET.fromstring(text)
        elif item["format"] == "csv":
            if len(list(csv.reader(io.StringIO(text)))) < 2:
                raise ContractError("CSV source contains no data rows")
        if not text.strip():
            raise ContractError("empty source response")
        receipt.update(status="FETCHED", text=text)
    except (OSError, ValueError, urllib.error.URLError, ET.ParseError) as exc:
        receipt.update(error=type(exc).__name__, message=str(exc)[:400])
        if isinstance(exc, urllib.error.HTTPError):
            receipt["http_status"] = exc.code
    receipt.update(completed_at=now(), seconds=time.monotonic()-started)
    emit(stage="fetch", source=item["id"], status=receipt["status"], http=receipt.get("http_status"))
    return receipt


def collect(output, protocol, sources):
    if (output/"receipts.json").exists() or (output/"stream-freeze.json").exists():
        raise ContractError("this stream has already been collected; no silent retries")
    (output/"sources").mkdir(exist_ok=True)
    with ThreadPoolExecutor(max_workers=protocol["transport"]["concurrency"]) as executor:
        responses = list(executor.map(lambda s: fetch(s, output, protocol["transport"]), sources))
    packets = []
    for number in sorted({s["packet"] for s in sources}):
        members = [r for r in responses if r["packet"] == number and r["status"] == "FETCHED"]
        blocks = ["SOURCE_ID: "+r["id"]+"\nURL: "+r["url"]+"\nFORMAT: "+r["format"]+
                  "\nRAW_SHA256: "+r["sha256"]+"\nRETRIEVED_AT: "+r["completed_at"]+
                  "\nRAW_CHARACTERS: 0.."+str(min(1500, len(r["text"])))+"\n"+
                  r["text"][:1500]+"\nEND_SOURCE\n" for r in members]
        text = "\n".join(blocks)
        if len(text) > protocol["packetization"]["max_document_characters"]:
            raise ContractError("fixed neutral packet exceeds the existing document limit")
        if not members:
            packets.append({"packet": number, "source_ids": [], "specification": None})
            continue
        provenance = {r["id"]: r["sha256"] for r in members}
        spec = {"id": "unlabelled-packet-"+str(number)+"-"+digest(provenance)[:20],
                "source": "stream:unlabelled-public-data:packet-"+str(number),
                "title": "Unlabelled external data packet "+str(number), "width": 32,
                "text": text, "provenance": "raw-source-bundle-sha256:"+digest(provenance)}
        packets.append({"packet": number, "source_ids": [r["id"] for r in members],
                        "specification": spec, "source_hashes": provenance,
                        "literal_characters": sum(min(1500,len(r["text"])) for r in members),
                        "complete_sources": [r["id"] for r in members if len(r["text"]) <= 1500]})
    receipts = [{k:v for k,v in r.items() if k != "text"} for r in responses]
    write_json(output/"receipts.json", receipts)
    write_json(output/"packets.json", packets)
    write_json(output/"stream-freeze.json", {"created_at": now(), "parent_head": protocol["parent_head"],
        "runtime_sha256": protocol["runtime_sha256"], "receipts_sha256": digest(receipts),
        "packets_sha256": digest(packets), "operator_tasks": 0, "operator_answer_labels": 0})
    emit(stage="stream_frozen", fetched=sum(r["status"]=="FETCHED" for r in receipts), packets=len(packets))


def traced_step(kernel):
    counts = Counter()
    watched = {"nova_core.autonomy.propose", "nova_core.autonomy.relation_goal",
        "nova_core.library_evolution.transfer_goal", "nova_core.capability.diagnosis",
        "nova_core.specifications.learn", "nova_core.python_tools.synthesize", "nova_core.synthesis.synthesize"}
    def profile(frame, event, arg):
        if event == "call":
            name = frame.f_globals.get("__name__", "")+"."+frame.f_code.co_name
            if name in watched:
                counts[name] += 1
    old = sys.getprofile()
    try:
        sys.setprofile(profile)
        action = kernel.step()
    finally:
        sys.setprofile(old)
    return {"action": action, "native_call_counts": dict(counts)}


def full_regression(kernel):
    state, _, _ = kernel._load()
    active, memory, _ = context(state)
    results = {}
    for tid, pid in sorted(active.items()):
        task = state["tasks"][tid]
        results[tid] = evaluate([{"program": memory[pid], "rows": task["train"]+task["holdout"]}], memory)["results"][0]
    return {"passed": sum(r["passed"] for r in results.values()),
            "total": sum(r["total"] for r in results.values()), "skills": len(results), "results": results}


def run(output, state_path, parent_state, protocol):
    if state_path.exists() or (output/"observations.json").exists():
        raise ContractError("experiment state/results already exist")
    receipts = json.loads((output/"receipts.json").read_text())
    packets = json.loads((output/"packets.json").read_text())
    anchor = json.loads((output/"stream-freeze.json").read_text())
    if digest(receipts) != anchor["receipts_sha256"] or digest(packets) != anchor["packets_sha256"]:
        raise ContractError("stream changed after freeze")
    parent = json.loads((ROOT/protocol["parent_journal"]).read_text())
    journal = Journal(parent_state)
    try:
        events, head = journal.read()
        if head != protocol["parent_head"] or encode(events) != encode(parent["events"]):
            raise ContractError("experiment must start from the exact verified G22 state")
        journal.backup(state_path)
    finally:
        journal.close()
    emit(stage="replaying_G22", parent_head=head)
    observations = []
    with Kernel(state_path) as kernel:
        initial, head, _ = kernel._load()
        if kernel.genome()["id"] != protocol["parent_genome"]:
            raise ContractError("wrong parent genome")
        baseline = traced_step(kernel)
        write_json(output/"baseline.json", {**baseline, "head": head,
            "knowledge_documents": len(initial["knowledge"]), "tasks": len(initial["tasks"]),
            "generation": initial["current"], "genome": kernel.genome()["id"]})
        emit(stage="baseline", **baseline["action"])
        for packet in packets:
            before, before_head, _ = kernel._load()
            outcome = {"packet": packet["packet"], "source_ids": packet["source_ids"],
                       "before_head": before_head, "before_knowledge_count": len(before["knowledge"])}
            if packet["specification"] is None:
                outcome.update(ingress="NOT_ATTEMPTED", reason="NO_FETCHED_DATA")
            else:
                try:
                    outcome.update(ingress="ACCEPTED", receipt=kernel.study(packet["specification"]))
                except ContractError as exc:
                    outcome.update(ingress="REJECTED", error=type(exc).__name__, reason=str(exc))
            observed = traced_step(kernel)
            after, after_head, _ = kernel._load()
            outcome.update(observed, after_head=after_head, knowledge_count=len(after["knowledge"]),
                           generation=after["current"], genome=kernel.genome()["id"])
            observations.append(outcome)
            write_json(output/"observations.json", observations)
            emit(stage="packet", packet=packet["packet"], ingress=outcome["ingress"],
                 knowledge_count=outcome["knowledge_count"], action=observed["action"])
            if observed["action"].get("phase") == "GOAL_FROZEN":
                break
        final, final_head, _ = kernel._load()
        events, _ = kernel.journal.read()
        regression = full_regression(kernel)
        write_json(output/"regression.json", regression)
        write_json(output/"journal.json", {"schema": "nova.journal.export.v1", "head": final_head, "events": events})
        write_json(output/"status.json", kernel.status())
        write_json(output/"genome.json", kernel.genome())
        received_ids = {sid for o in observations if o["ingress"]=="ACCEPTED" for sid in o["source_ids"]}
        received = [r for r in receipts if r["id"] in received_ids]
        coverage = {"successful_unique_responses": len({r["sha256"] for r in received}),
                    "domains": len({r["domain"] for r in received}), "formats": len({r["format"] for r in received})}
        coverage_met = all(coverage[k]>=v for k,v in protocol["minimum_delivered_coverage"].items())
        goals = [o["action"] for o in observations if o["action"].get("phase")=="GOAL_FROZEN"]
        new_events = events[len(parent["events"]):]
        result = {"schema": "nova.unlabelled-stream.result.v1", "status": "PENDING_COLD_REPLAY",
            "selection_verdict": "NATIVE_GOAL_REQUIRES_EVIDENCE_REVIEW" if goals else
                "WITHHOLD_NO_NATIVE_DEFICIT" if coverage_met else "INCONCLUSIVE_INPUT_COVERAGE",
            "http_successes": sum(r["status"]=="FETCHED" for r in receipts), "http_attempts": len(receipts),
            "accepted_packets": sum(o["ingress"]=="ACCEPTED" for o in observations),
            "rejected_packets": sum(o["ingress"]=="REJECTED" for o in observations),
            "delivered_coverage": coverage, "coverage_threshold_met": coverage_met,
            "delivered_source_ids": sorted(received_ids), "native_goals": goals,
            "new_admissions": final["admissions"]-initial["admissions"],
            "new_operator_task_events": sum(e["kind"]=="tasks" for e in new_events),
            "historical_prefix_preserved": encode(events[:len(parent["events"])])==encode(parent["events"]),
            "genome_unchanged": kernel.genome()["id"]==protocol["parent_genome"],
            "runtime_unchanged": digest(runtime_manifest())==protocol["runtime_sha256"],
            "initial_knowledge_count": len(initial["knowledge"]), "final_knowledge_count": len(final["knowledge"]),
            "head": final_head, "events": len(events), "active_generation": final["current"],
            "regression": {k:v for k,v in regression.items() if k!="results"},
            "native_diagnosis": None if not goals else "review the native goal artifact",
            "operator_analysis": {"author": "external verifier, not Nova",
                "evidence": ["native call traces in observations.json", "unchanged autonomy.py relation_goal and library_evolution.py transfer_goal", "capability.py validate_knowledge"],
                "finding": "goal discovery reads historical failed tasks and admitted transfer records; newly stored raw knowledge is not an input to either goal constructor",
                "ingress_limit": "knowledge budget is eight documents; G22 already stores five"},
            "limits": protocol["limits"], "completed_at": now()}
        write_json(output/"run-summary.json", result)
        emit(stage="run_complete", **{k:result[k] for k in ("selection_verdict","accepted_packets","rejected_packets","delivered_coverage","new_admissions","regression")})


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("command", choices=["collect", "run", "replay"])
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--freeze", required=True)
    parser.add_argument("--state", type=Path)
    parser.add_argument("--parent-state", type=Path)
    args = parser.parse_args()
    output = args.output.resolve()
    protocol, sources = frozen(output, args.freeze)
    if args.command == "collect":
        collect(output, protocol, sources)
    elif args.command == "run":
        run(output, args.state, args.parent_state, protocol)
    else:
        summary = json.loads((output/"run-summary.json").read_text())
        with Kernel(args.state) as kernel:
            audit = kernel.audit(expected_head=summary["head"])
            write_json(output/"cold-replay.json", audit)
            observed = traced_step(kernel)
            write_json(output/"restart-selection.json", observed)
            summary.update(status=summary["selection_verdict"], cold_replay=audit["status"],
                           restart_selection=observed["action"])
            write_json(output/"run-summary.json", summary)
            emit(stage="cold_replay", status=audit["status"], next_action=observed["action"])


if __name__ == "__main__":
    main()

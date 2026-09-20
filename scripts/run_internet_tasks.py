"""Connect NOVA G14 to public HTTPS data and retain a reproducible task run.

The operator supplies tasks, projections and reference answers. NOVA chooses
goals and synthesizes programs. Fresh sources are requested only after learning.
The adapter never installs or executes code from an internet response.
"""

import argparse
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
import gzip
import hashlib
import json
from pathlib import Path
import re
import secrets
import subprocess
import sys
import time
import urllib.parse
import urllib.request

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from nova_core.contracts import ContractError, decode, digest, encode, equal, task_spec
from nova_core.evaluation import score
from nova_core.kernel import Kernel, context, runtime_manifest
from scripts.run_development_chain import restore, write_json

PARENT = "experience/algorithm-cycle-v4/result/journal.json"
PACKAGES = {
    "train": ["packaging", "cryptography", "PyYAML"],
    "holdout": ["urllib3", "cffi", "MarkupSafe"],
    "fresh": ["certifi", "charset-normalizer", "Pillow"],
}
REPOSITORIES = {
    "train": ["pallets/flask", "psf/requests", "encode/httpx"],
    "holdout": ["pallets/click", "pytest-dev/pytest", "python/cpython"],
    "fresh": ["pypa/pip", "psf/black", "pydantic/pydantic"],
}
TASKS = {
    "200-distribution-bytes": "Sum byte sizes of up to 32 current distribution files",
    "210-distribution-summary": "Count, sum and numerically sort the same byte sizes",
    "220-distribution-json": "Serialize that summary into canonical JSON",
    "230-repository-counts": "Add GitHub star and fork counts",
    "240-repository-record": "Return their sum and their difference",
    "250-online-hash-json": "Serialize the inherited name/SHA-256 record",
    "290-numeric-version-order": "Sort dotted numeric releases by integer components",
}
MAX_RESPONSE = 8_000_000


def now():
    return datetime.now(timezone.utc).isoformat()


def announce(stage, **data):
    print(json.dumps({"stage": stage, **data}, ensure_ascii=False), flush=True)


def checked_url(url):
    parsed = urllib.parse.urlsplit(url)
    if (parsed.scheme != "https" or parsed.username is not None or
            parsed.password is not None or parsed.port not in (None, 443) or
            parsed.query or parsed.fragment):
        raise ContractError("only credential-free HTTPS API URLs are accepted")
    allowed = (
        parsed.hostname == "pypi.org" and
        re.fullmatch(r"/pypi/[A-Za-z0-9][A-Za-z0-9_.-]*/json", parsed.path)
    ) or (
        parsed.hostname == "api.github.com" and
        re.fullmatch(r"/repos/[A-Za-z0-9][A-Za-z0-9_.-]*/[A-Za-z0-9][A-Za-z0-9_.-]*", parsed.path)
    )
    if not allowed:
        raise ContractError("URL is outside the two public data APIs")
    return url


class CheckedRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, request, fp, code, message, headers, new_url):
        checked_url(new_url)
        return super().redirect_request(request, fp, code, message, headers, new_url)


def fetch(item, output):
    kind, split, name = item
    url = (f"https://pypi.org/pypi/{name}/json" if kind == "pypi" else
           f"https://api.github.com/repos/{name}")
    checked_url(url)
    request = urllib.request.Request(url, headers={
        "User-Agent": "NOVA-public-data-experiment/0.4",
        "Accept": "application/json", "Accept-Encoding": "identity",
    })
    begun = now()
    started = time.monotonic()
    with urllib.request.build_opener(CheckedRedirect()).open(request, timeout=20) as response:
        checked_url(response.url)
        body = response.read(MAX_RESPONSE + 1)
        if len(body) > MAX_RESPONSE:
            raise ContractError("public API response exceeds the byte budget")
        if response.status != 200:
            raise ContractError("public API returned a non-200 status")
        metadata = {"status": response.status, "final_url": response.url,
                    "content_type": response.headers.get("Content-Type"),
                    "server_date": response.headers.get("Date")}
    data = json.loads(body)
    if kind == "pypi":
        # The selection is a documented bounded projection, not all files.
        files = data["urls"][:32]
        releases = sorted(v for v in data["releases"]
                          if re.fullmatch(r"[0-9]+(?:\.[0-9]+){1,2}", v))
        if len(releases) > 32:
            releases = [releases[i * (len(releases) - 1) // 31] for i in range(32)]
        projected = {"name": data["info"]["name"], "version": data["info"]["version"],
                     "sizes": [f["size"] for f in files], "versions": releases,
                     "available_files": len(data["urls"]), "selected_files": len(files)}
        if not files or len(releases) < 2:
            raise ContractError("source does not supply sufficient distribution/release data")
    else:
        projected = {"name": data["full_name"], "stars": data["stargazers_count"],
                     "forks": data["forks_count"]}
    filename = f"{kind}-{split}-{name.replace('/', '--')}.json.gz"
    (output / "sources" / filename).write_bytes(gzip.compress(body, mtime=0))
    receipt = {"kind": kind, "split": split, "name": name, "url": url,
               "started_at": begun, "completed_at": now(), "bytes": len(body),
               "sha256": hashlib.sha256(body).hexdigest(), "raw_file": "sources/" + filename,
               "seconds": time.monotonic() - started, **metadata, "projection": projected}
    announce("https", source=url, status=200, bytes=len(body), split=split)
    return receipt


def collect(splits, output):
    items = [(kind, split, name) for split in splits
             for kind, groups in (("pypi", PACKAGES), ("github", REPOSITORIES))
             for name in groups[split]]
    # Independent GET requests with a small fixed concurrency limit.
    with ThreadPoolExecutor(max_workers=3) as workers:
        receipts = list(workers.map(lambda item: fetch(item, output), items))
    return receipts


def example(task, receipt):
    """Independent operator oracle; its implementation is never sent to Nova."""
    p = receipt["projection"]
    if task in ("200-distribution-bytes", "210-distribution-summary", "220-distribution-json"):
        values = p["sizes"]
        inputs = {"values": values}
        result = {"bytes": sum(values), "files": len(values), "sizes": sorted(values)}
        if task == "200-distribution-bytes":
            result = sum(values)
        elif task == "220-distribution-json":
            result = json.dumps(result, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    elif task in ("230-repository-counts", "240-repository-record"):
        inputs = {"stars": p["stars"], "forks": p["forks"]}
        result = p["stars"] + p["forks"]
        if task == "240-repository-record":
            result = {"combined": result, "difference": p["stars"] - p["forks"]}
    elif task == "250-online-hash-json":
        document = {"name": p["name"], "version": p["version"]}
        inputs = {"document": json.dumps(document, ensure_ascii=False), "field": "name"}
        result = json.dumps({"name": p["name"].upper(),
                             "digest": hashlib.sha256(p["name"].encode("utf-8")).hexdigest()},
                            sort_keys=True, ensure_ascii=False, separators=(",", ":"))
    else:
        inputs = {"versions": p["versions"]}
        result = sorted(p["versions"], key=lambda v: tuple(int(x) for x in v.split(".")))
    return {"input": inputs, "output": result}


def task_kind(task):
    return "github" if task in ("230-repository-counts", "240-repository-record") else "pypi"


def corpus_from(receipts):
    return [task_spec({
        "id": task,
        "source": "live-https:internet-tasks-v1:" + task + "; raw response hashes in sources.json",
        **{split: [example(task, r) for r in receipts
                   if r["split"] == split and r["kind"] == task_kind(task)]
           for split in ("train", "holdout")},
    }) for task in TASKS]


def query(kernel, task, row, source):
    result = {"task": task, "source": source, **row}
    try:
        observed = kernel.predict(task, row["input"])
        result.update(observed=observed, passed=equal(observed, row["output"]))
    except ContractError as exc:
        result.update(passed=False, error=str(exc))
    return result


def export(kernel, output):
    events, head = kernel.journal.read()
    write_json(output / "journal.json", {"schema": "nova.journal.export.v1", "head": head, "events": events})
    write_json(output / "genome.json", kernel.genome())
    write_json(output / "causal-memory.json", kernel.causal_memory())
    return head, events


def save_program(record, output):
    """A rejected candidate must never replace an admitted generation's source."""
    if not record.get("program"):
        return None
    task = re.sub(r"[^A-Za-z0-9_.-]", "_", record["selection"]["task"])
    filename = f"generated-g{record.get('generation', 'pending')}-{task}-{record['status']}.py"
    path = output / filename
    path.write_text(record["program"]["source"], encoding="utf-8")
    return path


def run(output, state_path):
    if output.exists() or state_path.exists():
        raise ContractError("use new output and state paths; previous experiments are immutable")
    output.mkdir(parents=True)
    (output / "sources").mkdir()
    parent = decode((ROOT / PARENT).read_text())
    script_sha = hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
    manifest = runtime_manifest()
    started = time.monotonic()
    protocol = {"schema": "nova.internet-tasks.v1", "created_at": now(),
                "base_commit": subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip(),
                "parent_journal": PARENT, "parent_head": parent["head"], "parent_generation": 14,
                "runtime_sha256": digest(manifest), "runner_sha256": script_sha,
                "packages": PACKAGES, "repositories": REPOSITORIES, "tasks": TASKS,
                "max_steps": 9, "source_byte_limit": MAX_RESPONSE,
                "projection": "first 32 PyPI urls; at most 32 evenly selected numeric releases; GitHub counts",
                "claim_boundary": "operator-authored task/oracle; native goal selection and synthesis; bounded HTTPS adapter"}
    write_json(output / "protocol.json", protocol)
    receipts = collect(("train", "holdout"), output)
    write_json(output / "sources.json", receipts)
    corpus = corpus_from(receipts)
    write_json(output / "corpus.json", corpus)
    write_json(output / "input-freeze.json", {"created_at": now(), "corpus_sha256": digest(corpus),
                                              "sources_sha256": digest(receipts), "protocol_sha256": digest(protocol)})
    announce("restore", generation=14, head=parent["head"])
    restore(parent, state_path)
    records = []
    with Kernel(state_path) as kernel:
        write_json(output / "initial-state.json", kernel.status())
        kernel.register(corpus)
        for _ in range(protocol["max_steps"]):
            step_started = time.monotonic()
            record = kernel.step()
            records.append(record)
            write_json(output / "steps.json", records)
            announce("step", task=record.get("selection", {}).get("task"), status=record["status"],
                     reason=record["reason"], generation=record.get("generation"),
                     attempts=record.get("synthesis", {}).get("attempts"), seconds=time.monotonic()-step_started)
            save_program(record, output)
            if record["status"] in ("IDLE", "WAITING", "FROZEN"):
                break
        frozen = kernel.status()
        write_json(output / "post-learning-freeze.json", {"created_at": now(), **frozen})
        export(kernel, output)
        # No candidate or runtime edits take place from this point onward.
        announce("fresh_sources", frozen_head=frozen["head"])
        fresh = collect(("fresh",), output)
        receipts.extend(fresh)
        write_json(output / "sources.json", receipts)
        results = [query(kernel, task, example(task, r), r["url"])
                   for task in TASKS for r in fresh if r["kind"] == task_kind(task)]
        write_json(output / "fresh-query-results.json", results)
        # Separately labelled random boundary checks of the inherited hash skill.
        boundary = []
        for length in (1, 17, 31, 55, 56, 57, 63, 64, 65, 119, 120, 127, 128, 255, 511, 512, 513, 1023, 1024):
            name = secrets.token_hex((length + 1) // 2)[:length]
            row = {"input": {"document": json.dumps({"name": name}), "field": "name"},
                   "output": hashlib.sha256(name.encode()).hexdigest()}
            boundary.append(query(kernel, "90-sha256-deficit-control", row, "fresh-random-boundary"))
        name = secrets.token_hex(20) + "\x00ядро-é-東京-🚀"
        boundary.append(query(kernel, "90-sha256-deficit-control",
                              {"input": {"document": json.dumps({"name": name}), "field": "name"},
                               "output": hashlib.sha256(name.encode()).hexdigest()}, "fresh-unicode-boundary"))
        write_json(output / "hash-boundary-results.json", boundary)
        state, head, _ = kernel._load()
        active, memory, _ = context(state)
        regressions = {tid: score(memory[pid], state["tasks"][tid]["train"] + state["tasks"][tid]["holdout"], memory)
                       for tid, pid in sorted(active.items())}
        write_json(output / "regression.json", regressions)
        final = kernel.status()
        final_head, events = export(kernel, output)
        if frozen["head"] != final_head:
            raise ContractError("state changed during fresh evaluation")
        backup = state_path.with_name(state_path.stem + "-backup.sqlite")
        kernel.journal.backup(backup)
    announce("cold_replay", head=final_head)
    cold = subprocess.run([sys.executable, "-m", "nova_core", "--state", str(backup),
                           "verify", "--expected-head", final_head], cwd=ROOT,
                          text=True, capture_output=True, timeout=300)
    (output / "cold-replay.json").write_text(cold.stdout)
    (output / "cold-replay.stderr.txt").write_text(cold.stderr)
    replay = json.loads(cold.stdout) if cold.returncode == 0 else None
    admitted = [r for r in records if r["status"] == "ADMITTED"]
    admitted_ids = {r["selection"]["task"] for r in admitted}
    checks = {
        "live_https": len(receipts) == 18 and all(r["status"] == 200 for r in receipts),
        "all_tasks_attempted": set(TASKS) <= {r.get("selection", {}).get("task") for r in records},
        "frozen_runtime": runtime_manifest() == manifest and hashlib.sha256(Path(__file__).read_bytes()).hexdigest() == script_sha,
        "historical_prefix_preserved": events[:len(parent["events"])] == parent["events"],
        "fresh_sources_after_freeze": all(r["started_at"] > json.loads((output / "post-learning-freeze.json").read_text())["created_at"] for r in fresh),
        "admitted_fresh_queries": all(r["passed"] for r in results if r["task"] in admitted_ids),
        "inherited_hash_boundaries": all(r["passed"] for r in boundary),
        "regression": all(r["passed"] == r["total"] for r in regressions.values()),
        "cold_replay": cold.returncode == 0 and replay["head"] == final_head and replay["status"] == "PASS",
    }
    task_results = []
    for task, title in TASKS.items():
        attempts = [r for r in records if r.get("selection", {}).get("task") == task]
        last = attempts[-1] if attempts else {}
        rows = [r for r in results if r["task"] == task]
        task_results.append({"task": task, "description": title, "status": last.get("status", "UNATTEMPTED"),
                             "reason": last.get("reason"), "generation": last.get("generation"),
                             "holdout": ({k: last["gate"]["holdout"][k] for k in ("passed", "total")}
                                         if last.get("gate") else None),
                             "fresh_passed": sum(r["passed"] for r in rows), "fresh_total": len(rows),
                             "parents": last.get("program", {}).get("parents", []) if last.get("program") else []})
    summary = {"schema": "nova.internet-task-results.v1",
               "status": "PASS" if all(checks.values()) and all(r["passed"] for r in results) else "PARTIAL",
               "execution_checks": checks, "source_requests": len(receipts),
               "source_domains": ["pypi.org", "api.github.com"],
               "parent_generation": 14, "active_generation": final["active_generation"],
               "new_admissions": len(admitted), "tasks": task_results,
               "fresh_queries": {"passed": sum(r["passed"] for r in results), "total": len(results)},
               "hash_boundaries": {"passed": sum(r["passed"] for r in boundary), "total": len(boundary)},
               "regression": {"passed": sum(r["passed"] for r in regressions.values()),
                              "total": sum(r["total"] for r in regressions.values()), "skills": len(regressions)},
               "head": final_head, "seconds": time.monotonic() - started,
               "claim_boundary": protocol["claim_boundary"],
               "state": str(state_path), "state_backup": str(backup)}
    write_json(output / "run-summary.json", summary)
    announce("complete", status=summary["status"], generation=summary["active_generation"],
             admissions=summary["new_admissions"], fresh=summary["fresh_queries"],
             regression=summary["regression"], checks=checks)
    return 0 if all(checks.values()) else 2


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--state", type=Path, required=True)
    args = parser.parse_args()
    raise SystemExit(run(args.output.resolve(), args.state.resolve()))

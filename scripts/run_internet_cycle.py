"""Live-internet development cycle for NOVA without changing the kernel runtime.

The environment adapter fetches fresh public GitHub repository metadata. NOVA
receives two tasks built from disjoint live snapshots, selects the next goal with
its own queue policy, synthesizes programs from training rows only, and gates
them on held-out rows. No candidate program or answer rule enters nova_core.
"""

import argparse
import json
import os
import subprocess
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from nova_core.contracts import ContractError, decode, digest, equal
from nova_core.kernel import Kernel
from scripts.run_development_chain import restore


PARENT = ROOT / "experience/algorithm-cycle-v4/result/journal.json"

STATS_REPOS = [
    "pydantic/pydantic",
    "django/django",
    "numpy/numpy",
    "pandas-dev/pandas",
    "scikit-learn/scikit-learn",
    "rust-lang/rust",
]
OWNER_REPOS = [
    "python/cpython",
    "pallets/flask",
    "psf/requests",
    "encode/httpx",
    "astral-sh/ruff",
    "tiangolo/fastapi",
]
QUERY_REPOS = {
    "140-live-stars-plus-forks": ["facebook/react", "vuejs/core"],
    "150-live-owner-uppercase": ["golang/go", "BurntSushi/ripgrep"],
}


def write_json(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(
        json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2, allow_nan=False) + "\n",
        encoding="utf-8",
    )
    temporary.replace(path)


def fetch_repository(slug):
    url = "https://api.github.com/repos/" + slug
    headers = {
        "Accept": "application/vnd.github+json",
        "User-Agent": "nova-internet-cycle-v1",
        "X-GitHub-Api-Version": "2022-11-28",
    }
    token = os.environ.get("GITHUB_TOKEN")
    if token:
        headers["Authorization"] = "Bearer " + token
    request = urllib.request.Request(url, headers=headers)
    last = None
    for attempt in range(3):
        try:
            with urllib.request.urlopen(request, timeout=20) as response:
                raw = response.read()
                if len(raw) > 2_000_000:
                    raise ContractError("internet response exceeds 2 MB")
                data = json.loads(raw)
                if type(data) is not dict:
                    raise ContractError("GitHub API response is not an object")
                return data, {
                    "slug": slug,
                    "url": url,
                    "etag": response.headers.get("ETag"),
                    "last_modified": response.headers.get("Last-Modified"),
                    "bytes": len(raw),
                }
        except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as exc:
            last = exc
            if attempt < 2:
                time.sleep(1 + attempt)
    raise ContractError("internet fetch failed for " + slug + ": " + str(last))


def canonical_document(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False)


def stats_row(data):
    subset = {
        "full_name": data["full_name"],
        "forks_count": data["forks_count"],
        "stargazers_count": data["stargazers_count"],
    }
    if type(subset["forks_count"]) is not int or type(subset["stargazers_count"]) is not int:
        raise ContractError("GitHub numeric metadata has unexpected type")
    return {
        "input": {
            "document": canonical_document(subset),
            "field_a": "stargazers_count",
            "field_b": "forks_count",
        },
        "output": subset["stargazers_count"] + subset["forks_count"],
    }


def owner_row(data):
    owner = data.get("owner")
    if type(owner) is not dict or type(owner.get("login")) is not str:
        raise ContractError("GitHub owner metadata missing")
    subset = {
        "full_name": data["full_name"],
        "owner": {"login": owner["login"], "type": owner.get("type")},
    }
    return {
        "input": {
            "document": canonical_document(subset),
            "field": "owner",
            "subfield": "login",
        },
        "output": owner["login"].upper(),
    }


def task(task_id, rows, snapshot_digest):
    if len(rows) != 6:
        raise ContractError("internet task requires exactly six snapshots")
    return {
        "id": task_id,
        "source": "github-live-api:internet-cycle-v1:" + snapshot_digest[:16],
        "train": rows[:3],
        "holdout": rows[3:],
    }


def fetch_rows(repositories, projector):
    rows, provenance = [], []
    for slug in repositories:
        data, source = fetch_repository(slug)
        rows.append(projector(data))
        provenance.append(source)
    return rows, provenance


def run(state_path, output_directory):
    output_directory.mkdir(parents=True, exist_ok=True)
    summary_path = output_directory / "run-summary.json"
    if summary_path.exists() or state_path.exists():
        raise ContractError("use fresh state and output paths")

    parent = decode(PARENT.read_text(encoding="utf-8"))
    restore(parent, state_path)

    stats_rows, stats_sources = fetch_rows(STATS_REPOS, stats_row)
    owner_rows, owner_sources = fetch_rows(OWNER_REPOS, owner_row)
    snapshot = {"stats": stats_sources, "owner": owner_sources}
    snapshot_digest = digest({
        "stats": stats_rows,
        "owner": owner_rows,
        "sources": snapshot,
    })
    corpus = [
        task("140-live-stars-plus-forks", stats_rows, snapshot_digest),
        task("150-live-owner-uppercase", owner_rows, snapshot_digest),
    ]

    write_json(output_directory / "live-corpus.json", corpus)
    write_json(output_directory / "network-provenance.json", {
        "schema": "nova.internet-provenance.v1",
        "adapter": "stdlib_https_github_api",
        "snapshot_digest": snapshot_digest,
        "sources": snapshot,
    })

    with Kernel(state_path) as kernel:
        before = kernel.audit(expected_head=parent["head"])
        if before["active_generation"] != 14 or before["next_task"] is not None:
            raise ContractError("internet cycle requires the verified idle G14 checkpoint")

        registered = kernel.register(corpus)
        queue_before = kernel.queue()
        development = kernel.develop(steps=2)
        status = kernel.status()

        queries = []
        for task_id, slugs in QUERY_REPOS.items():
            projector = stats_row if task_id.startswith("140-") else owner_row
            if task_id not in status["active_tasks"]:
                queries.append({
                    "task": task_id,
                    "passed": False,
                    "reason": "task_not_admitted",
                })
                continue
            for slug in slugs:
                data, source = fetch_repository(slug)
                row = projector(data)
                observed = kernel.predict(task_id, row["input"])
                queries.append({
                    "task": task_id,
                    "source": source,
                    "expected": row["output"],
                    "output": observed,
                    "passed": equal(observed, row["output"]),
                })

        audit = kernel.audit()
        backup = output_directory / "replay.sqlite"
        kernel.journal.backup(backup)

    replay = subprocess.run(
        [
            sys.executable,
            "-m",
            "nova_core",
            "--state",
            str(backup),
            "verify",
            "--expected-head",
            audit["head"],
        ],
        cwd=ROOT,
        text=True,
        capture_output=True,
        timeout=180,
    )
    replay_result = decode(replay.stdout) if replay.returncode == 0 else None

    steps = development["steps"]
    admissions = [step for step in steps if step.get("status") == "ADMITTED"]
    chosen_order = [
        step.get("selection", {}).get("task")
        for step in steps
        if step.get("selection")
    ]
    all_queries_pass = bool(queries) and all(q["passed"] for q in queries)
    passed = (
        len(admissions) >= 1
        and all(step.get("workspace", {}).get("CODE", {}).get("selection") == "training_only" for step in admissions)
        and replay.returncode == 0
        and replay_result is not None
        and replay_result["head"] == audit["head"]
        and all_queries_pass
    )

    summary = {
        "schema": "nova.internet-cycle.v1",
        "status": "PASS" if passed else "WITHHOLD",
        "claim": "live internet data ingestion with native NOVA goal selection and bounded program synthesis",
        "runtime_changed": False,
        "parent_generation": 14,
        "parent_head": parent["head"],
        "registered": registered["registered"],
        "queue_before": queue_before,
        "chosen_order": chosen_order,
        "steps": [
            {
                "task": step.get("selection", {}).get("task"),
                "status": step["status"],
                "reason": step["reason"],
                "generation": step.get("generation"),
                "search_attempts": step.get("synthesis", {}).get("attempts"),
                "holdout": (
                    {
                        "passed": step["gate"]["holdout"]["passed"],
                        "total": step["gate"]["holdout"]["total"],
                    }
                    if step.get("gate")
                    else None
                ),
                "program": step["program"]["id"] if step.get("program") else None,
                "parents": step["program"]["parents"] if step.get("program") else [],
            }
            for step in steps
        ],
        "active_generation": audit["active_generation"],
        "head": audit["head"],
        "snapshot_digest": snapshot_digest,
        "live_sources": len(stats_sources) + len(owner_sources),
        "fresh_queries": {
            "passed": sum(q["passed"] for q in queries),
            "total": len(queries),
            "rows": queries,
        },
        "replay": {
            "returncode": replay.returncode,
            "status": replay_result["status"] if replay_result else "ERROR",
            "head": replay_result["head"] if replay_result else None,
            "stderr": replay.stderr[-2000:],
        },
        "boundaries": [
            "The network adapter is outside nova_core so historical deterministic replay remains unchanged.",
            "The adapter chooses public GitHub endpoints and constructs task/oracle rows; NOVA chooses the queued goal and candidate program.",
            "Synthesis receives training rows only; registered holdout rows are evaluated by the existing gate.",
            "This cycle tests live external-data learning, not unrestricted web browsing or autonomous host-source rewriting.",
        ],
    }
    write_json(summary_path, summary)
    print(json.dumps({
        "status": summary["status"],
        "chosen_order": summary["chosen_order"],
        "active_generation": summary["active_generation"],
        "fresh_queries": summary["fresh_queries"]["passed"],
        "fresh_query_total": summary["fresh_queries"]["total"],
        "head": summary["head"],
    }, sort_keys=True))
    return summary


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--state", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    run(args.state.resolve(), args.output.resolve())

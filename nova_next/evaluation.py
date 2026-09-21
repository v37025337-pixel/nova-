"""Evaluator-side oracle, compiled execution and regression; no synthesis."""

from pathlib import Path
import subprocess
import sys

from nova_core.contracts import ContractError, digest, encode, decode
from nova_core.isolation import evaluate as legacy_evaluate
from .data import graph_views
from .oracle import measure
from .programs import execute, dependencies, make_program


def cases(documents, law, views=12):
    result = []
    for document in documents:
        for graph in graph_views(document["analysis"]["graph"], views):
            result.append({"graph": graph, "expected": measure(graph)[law],
                           "source_sha256": document["receipt"]["sha256"],
                           "source": document["feed"]["url"], "origin": document["feed"]["origin"]})
    return result


def isolated(program, graphs, genes):
    request = encode({"program": program, "graphs": graphs, "genes": genes})
    if len(request.encode()) > 2_000_000:
        raise ContractError("execution payload exceeds 2 MB")
    p = subprocess.run([sys.executable, "-I", "-S", str(Path(__file__).with_name("worker.py"))],
                       input=request, capture_output=True, text=True, timeout=10,
                       cwd="/", env={}, close_fds=True)
    if p.returncode:
        raise ContractError("compiled sandbox failed: " + p.stderr[-300:])
    result = decode(p.stdout)
    if result.get("status") != "PASS" or result.get("isolation") != "linux_seccomp_v1":
        raise ContractError("missing actual isolation receipt")
    return result["outputs"]


def score(program, rows, genes):
    outputs = isolated(program, [r["graph"] for r in rows], genes)
    outcomes = [type(got) is int and got == row["expected"] for got, row in zip(outputs, rows)]
    if len(outputs) != len(rows):
        raise ContractError("sandbox output count differs")
    return {"passed": sum(outcomes), "total": len(rows), "outputs": outputs}


def legacy_bundle():
    return decode(Path(__file__).with_name("inherited.json").read_text())


def legacy_regression():
    bundle = legacy_bundle()
    jobs = [{"program": bundle["programs"][pid],
             "rows": bundle["tasks"][name]["train"] + bundle["tasks"][name]["holdout"]}
            for name, pid in sorted(bundle["bindings"].items())]
    result = legacy_evaluate(jobs, bundle["programs"])
    return {"passed": sum(r["passed"] for r in result["results"]),
            "total": sum(r["total"] for r in result["results"]),
            "skills": len(jobs), "isolation": result["isolation"]}


def assess(candidate, fresh_documents, genes, admitted, seen_inputs):
    rows = cases(fresh_documents, candidate["goal"]["law"])
    training = candidate["training"]
    known = set(seen_inputs) | {digest(r["graph"]) for r in training + candidate["diagnostic"]}
    tokens = [digest(r["graph"]) for r in rows]
    old_origins = set(candidate["known_origins"])
    fresh_origins = {r["origin"] for r in rows}
    if (not 16 <= len(rows) <= 48 or len(set(tokens)) != len(tokens) or known.intersection(tokens)
            or len(fresh_origins) < 2 or old_origins.intersection(fresh_origins)
            or set(candidate["known_content_hashes"]).intersection(r["source_sha256"] for r in rows)):
        raise ContractError("fresh evaluation needs 16..48 distinct views from two new repositories")
    program = candidate["search"]["program"]
    fresh = score(program, rows, genes)
    diagnostic = score(program, candidate["diagnostic"], genes)
    previous = {}
    for item in admitted:
        previous[item["program"]["id"]] = score(item["program"], item["rows"], genes)
    legacy = legacy_regression()
    baselines = [make_program(["const", 0], genes), make_program(["nodes"], genes),
                 make_program(["count", ["edges"]], genes)] + list(genes.values())
    baseline_scores = []
    for baseline in baselines:
        outputs = [execute(baseline["tree"], r["graph"], genes) for r in rows]
        baseline_scores.append(sum(type(got) is int and got == row["expected"] for got, row in zip(outputs, rows)))
    best = max(baseline_scores)
    ablation = {}
    # Replace each actual inherited dependency with the pre-existing zero program.
    # Compile the resulting experiment, rather than manufacture a failure count.
    for key in sorted(dependencies(program["tree"])):
        def substitute(tree):
            if tree == ["call", key]:
                return ["const", 0]
            return [substitute(x) if isinstance(x, list) else x for x in tree]
        removed = make_program(substitute(program["tree"]), genes)
        ablation[key] = score(removed, rows, genes)
    reason = "VERIFIED_EXTERNAL_GRAPH_IMPROVEMENT"
    if fresh["passed"] != fresh["total"] or diagnostic["passed"] != diagnostic["total"]:
        reason = "HOLDOUT_FAILED"
    elif legacy["passed"] != legacy["total"] or any(r["passed"] != r["total"] for r in previous.values()):
        reason = "REGRESSION_FAILED"
    elif best >= fresh["passed"]:
        reason = "NO_IMPROVEMENT_OVER_ACTIVE_PROGRAMS"
    elif any(r["passed"] == r["total"] for r in ablation.values()):
        reason = "INHERITED_DEPENDENCY_NOT_NECESSARY"
    return {"status": "ADMITTED" if reason == "VERIFIED_EXTERNAL_GRAPH_IMPROVEMENT" else "WITHHOLD",
            "reason": reason, "rows": rows, "fresh": fresh, "diagnostic": diagnostic,
            "legacy_regression": legacy, "new_skill_regression": previous,
            "best_without_candidate": best, "dependency_ablation": ablation,
            "oracle": "independent_bit_matrix_warshall_v1", "isolation": "linux_seccomp_v1",
            "independent_repositories": sorted(fresh_origins),
            "claim": "new composed graph program; finite search, supplied ontology, static source-derived views"}

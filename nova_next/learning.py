"""Native goal selection from measured structural deficits; training-only synthesis."""

from nova_core.contracts import digest
from .evaluation import cases, score
from .oracle import LAWS
from .programs import execute, make_program, synthesize


def propose(state):
    documents = state["documents"]
    if len({d["feed"]["origin"] for d in documents}) < 2:
        return {"status": "WAITING", "reason": "TWO_OBSERVED_REPOSITORIES_REQUIRED"}
    genes = state["genes"]
    options = []
    solved = {a["goal"]["law"] for a in state["admitted"]}
    for law, utility in LAWS.items():
        if law in solved:
            continue
        all_rows = cases(documents, law, views=8)
        training = [row for i, row in enumerate(all_rows) if i % 2 == 0]
        diagnostic = [row for i, row in enumerate(all_rows) if i % 2]
        if len(training) < 8 or len(diagnostic) < 8 or len({r["expected"] for r in all_rows}) < 2:
            continue
        identity = digest([law, [r["source_sha256"] for r in all_rows]])
        if identity in state["attempted"]:
            continue
        baselines = [make_program(["const", 0], genes), make_program(["nodes"], genes),
                     make_program(["count", ["edges"]], genes)] + list(genes.values())
        def errors(program, rows):
            return sum(execute(program["tree"], r["graph"], genes) != r["expected"] for r in rows)
        baseline = min(baselines, key=lambda p: (errors(p, training), p["id"]))
        failed = errors(baseline, diagnostic)
        if failed < 3:
            continue
        # Every goal answers a stated structural query, never hash -> arbitrary label.
        magnitude = sum(abs(execute(baseline["tree"], r["graph"], genes) - r["expected"]) for r in diagnostic)
        options.append({"goal": {"law": law, "utility": utility, "deficit_id": identity,
                                 "diagnostic_errors": failed, "diagnostic_total": len(diagnostic),
                                 "magnitude": magnitude, "origin": "observed_graph_prediction_errors",
                                 "ontology_author": "maintainer", "instance_selector": "kernel"},
                        "training": training, "diagnostic": diagnostic,
                        "baseline": baseline,
                        "known_origins": sorted({d["feed"]["origin"] for d in documents}),
                        "known_content_hashes": sorted({d["receipt"]["sha256"] for d in documents})})
    if not options:
        return {"status": "IDLE", "reason": "NO_SUPPORTED_STRUCTURAL_DEFICIT"}
    selected = min(options, key=lambda o: (-o["goal"]["diagnostic_errors"], -o["goal"]["magnitude"], o["goal"]["law"]))
    search = synthesize(selected["training"], genes)
    result = {**selected, "search": search, "parent_generation": state["generation"],
              "parent_genome": digest(genes), "fresh_cases_seen": 0,
              "author": "native_training_only_program_synthesis"}
    if search["program"] is None:
        return {**result, "status": "WITHHOLD", "reason": "SEARCH_EXHAUSTED"}
    isolated = score(search["program"], selected["training"], genes)
    if isolated["passed"] != isolated["total"]:
        return {**result, "status": "WITHHOLD", "reason": "COMPILED_TRAINING_FAILED", "isolated_training": isolated}
    result.update(status="CANDIDATE_FROZEN", reason="AWAITING_NEW_REPOSITORIES", isolated_training=isolated)
    return {**result, "freeze": digest(result)}

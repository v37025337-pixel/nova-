"""Summarize retained receipts; does not create goals, programs or test labels."""
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from nova_core.contracts import digest, encode
from nova_core.kernel import runtime_manifest
from run_development_chain import write_json


def main():
    output = ROOT/"experience/python-learning-v1"
    read = lambda name: json.loads((output/name).read_text())
    protocol, journal, status = read("protocol.json"), read("journal.json"), read("status.json")
    parent = json.loads((ROOT/protocol["parent_journal"]).read_text())
    events = journal["events"][len(parent["events"]):]
    admissions = [e for e in events if e["kind"] == "autonomy_evaluation" and e["status"] == "ADMITTED"]
    stages = []
    for event in admissions:
        generation = event["generation"]
        frozen = read(event["freeze"]+"-frozen.json")
        fresh = read("g"+str(generation)+"-fresh.json")
        cold = read("g"+str(generation)+"-cold-replay.json")
        rollback = read("rollback-g"+str(generation-1)+".json")
        stages.append({"generation": generation, "goal": event["task"]["id"],
            "goal_origin": frozen["goal"]["origin"], "root_task": frozen["goal"]["root_task"],
            "transfer_from": frozen["goal"].get("transfer_from"),
            "genome": event["mutation"]["child_genome"]["id"],
            "parent_genome": frozen["goal"]["parent_genome"], "freeze": event["freeze"],
            "native_search_attempts": frozen["candidate"]["report"]["search_attempts"],
            "tools_used": frozen["candidate"]["report"]["tools_used"],
            "fresh": {k:v for k,v in event["report"]["fresh"].items() if k != "outcomes"},
            "original_holdout": {k:v for k,v in event["report"]["original_holdout"].items() if k != "outcomes"},
            "ablation": {pid:{k:v for k,v in r.items() if k != "outcomes"} for pid,r in event["report"]["ablation"].items()},
            "required_inherited_dependency": frozen["goal"].get("required_capability"),
            "isolation": event["report"]["isolation"], "cold_replay": cold["audit"]["status"],
            "full_regression": {k:v for k,v in cold["regression"].items() if k != "results"},
            "rollback": {"status": rollback["status"], "generation": rollback["target"], "genome": rollback["exact_genome"]},
            "fresh_matches_journal": encode(fresh["rows"]) == encode(event["rows"]) and fresh["freeze"] == event["freeze"],
            "replayed_genome_matches": cold["genome"] == event["mutation"]["child_genome"]["id"],
            "rollback_genome_matches": rollback["exact_genome"] == frozen["goal"]["parent_genome"]})
    prefix = encode(journal["events"][:len(parent["events"])]) == encode(parent["events"])
    unchanged = digest(runtime_manifest()) == protocol["runtime_sha256"]
    transfer_verified = any(s["transfer_from"] and s["required_inherited_dependency"] in s["ablation"]
                           and s["ablation"][s["required_inherited_dependency"]]["passed"] == 0 for s in stages)
    lineage = all(b["parent_genome"] == a["genome"] and b["transfer_from"] == a["goal"]
                  for a, b in zip(stages, stages[1:]))
    no_operator_tasks = not any(e["kind"] == "tasks" for e in events)
    ok = len(stages) >= 2 and transfer_verified and lineage and no_operator_tasks and prefix and unchanged and all(
        s["fresh"]["passed"] == s["fresh"]["total"] == protocol["fresh_evaluation"]["rows"] and s["fresh_matches_journal"] and
        s["replayed_genome_matches"] and s["rollback_genome_matches"] and
        s["cold_replay"] == "PASS" and s["rollback"]["status"] == "PASS" and
        s["full_regression"]["passed"] == s["full_regression"]["total"] and
        all(a["passed"] < a["total"] for a in s["ablation"].values()) for s in stages)
    report = {"schema": "nova.python-learning-report.v1", "status": "PASS_FOR_LIBRARY_ASSISTED_RECOVERY" if ok else "WITHHOLD",
        "runtime_version": "0.6.0", "parent_generation": 20, "active_generation": status["active_generation"],
        "new_admissions": len(stages), "required_autonomous_generations": 3,
        "strict_autonomous_capability_evolution_proven": False,
        "runtime_and_goal_constructor_author": "maintainer", "generated_composition_author": "native kernel",
        "pre_freeze_development": "maintainer ran training-only composition smoke checks on public G20 feedback before release freeze; fresh labels did not yet exist",
        "evaluator_independence": "separate process with post-freeze OS entropy; authored by the same maintainer, not a third-party audit",
        "library_algorithm_invention_claim": False, "historical_prefix_preserved": prefix,
        "runtime_unchanged_after_freeze": unchanged,
        "no_new_operator_task_events": no_operator_tasks, "causal_lineage_verified": lineage,
        "head": journal["head"], "events": len(journal["events"]), "stages": stages,
        "stopping_action": read("next-action.json"), "code_freeze": read("code-freeze.json"),
        "gates": {
            "1_native_deficit": "PARTIAL: analysis of a retained operator-originated failure",
            "2_verifiable_goal": "PASS: native contract, inputs, utility and thresholds in journal",
            "3_freeze": "PASS_FOR_RECORDED_RUN: source tree, runtime, goal, tool catalogue and candidate pinned before fresh labels; development used public training feedback",
            "4_native_change_type": "PARTIAL: native choice within maintainer-written bounded routing",
            "5_native_knowledge": "PARTIAL: native catalogue request and function selection; bridge and API semantics supplied by maintainer",
            "6_generated_mechanism": "PASS_FOR_COMPOSITION: native IR and source, isolated execution; Python algorithms borrowed",
            "7_fresh_blind": "PASS: 24 fresh cases per candidate, strict 100%, no candidate retry from answers",
            "8_regression": "PASS: all active inherited skills and new capabilities",
            "9_causal_ablation": "PASS: new primitive and inherited transitive dependencies removed individually",
            "10_restart_replay_rollback": "PASS: journal admission, separate-process replay, exact rollback on backups",
            "11_transfer": ("PASS_BOUNDED: next native goal applies G21 relation to retained permutation task after restart"
                            if transfer_verified else "NOT_VERIFIED"),
            "12_three_autonomous_generations": "NOT_MET: bounded library-assisted admissions; unrestricted endogenous chain is unproven"},
        "limits": ["goal discovery covers two relation laws and one transfer rule, not unrestricted problem invention",
                   "original parent task was supplied by the operator; it is preserved as a historical failure",
                   "fresh test domain is bounded numeric dotted strings, not the whole PEP 440 version language",
                   "native search selected float conversion; precision is verified only in the recorded bounded domain",
                   "scientific packages are inventoried, not exposed as arbitrary executable imports"]}
    write_json(output/"run-summary.json", report)
    print(json.dumps({k: report[k] for k in ("status", "active_generation", "new_admissions", "head", "events")}))
    if not ok:
        raise SystemExit(1)


if __name__ == "__main__":
    main()

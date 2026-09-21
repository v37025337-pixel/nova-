"""Exercise UCR 18's own closed curriculum; this is not a Nova generation."""

import argparse
import hashlib
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from nova_tools.universal_code_reader import UniversalCodeReader


def write(path, value):
    path.write_text(json.dumps(value, ensure_ascii=True, allow_nan=False, sort_keys=True, indent=2) + "\n")


def run(output, seed):
    output.mkdir(parents=True, exist_ok=False)
    reader = UniversalCodeReader()
    protocol = {"schema": "nova.ucr18-feature-probe.v1", "reader_version": reader.VERSION,
                "reader_sha256": hashlib.sha256((ROOT / "nova_tools/universal_code_reader.py").read_bytes()).hexdigest(),
                "seed": seed, "steps": ["grammar_evolution_once", "novel_challenge_development_once", "state_roundtrip"],
                "data": "UCR builtin closed synthetic blueprint curriculum",
                "validation_boundary": "discovery and strategy selection inspect internal evaluation splits; these are diagnostic, not independent Nova holdouts",
                "nova_generation_changed": False}
    write(output / "protocol.json", protocol)
    write(output / "initial-state.json", reader.export_evolved_state())
    print(json.dumps({"phase": "ucr_builtin_grammar_evolution"}), flush=True)
    grammar = reader.run_autonomous_grammar_evolution(max_generations=1)
    write(output / "grammar-report.json", grammar)
    write(output / "grammar-state.json", reader.export_evolved_state())
    print(json.dumps({"phase": "ucr_novel_challenge_development", "seed": seed}), flush=True)
    novel = reader.run_autonomous_novel_challenge_development(seed=seed)
    write(output / "novel-report.json", novel)
    state = reader.export_evolved_state()
    write(output / "evolved-state.json", state)
    restored = UniversalCodeReader()
    loaded = restored.load_evolved_state(json.loads(json.dumps(state)))
    roundtrip = []
    for label in sorted(reader.evolved_primitive_registry):
        original = reader.semantic_primitives[label]["function"]
        recovered = restored.semantic_primitives[label]["function"]
        for value in (-1023, -255, -81, 0, 17, 128, 511, 1024):
            a, b = original(value), recovered(value)
            roundtrip.append({"primitive": label, "input": value, "original": a, "restored": b,
                              "equal": type(a) is type(b) and a == b})
    write(output / "state-roundtrip.json", {"load": loaded, "checks": roundtrip})
    summary = {"schema": "nova.ucr18-feature-probe-result.v1", "reader_version": reader.VERSION,
               "novel_status_reported_by_ucr": novel["status"],
               "new_challenges": len(novel.get("discovered", [])),
               "grammar_rules": len(state["grammar_rules"]), "mutation_routes": len(state["mutation_strategy_routes"]),
               "primitives": len(state["primitives"]), "roundtrip_checks": len(roundtrip),
               "roundtrip_passed": not loaded["rejected"] and all(r["equal"] for r in roundtrip),
               "nova_admissions": 0, "validation_boundary": protocol["validation_boundary"]}
    write(output / "summary.json", summary)
    print(json.dumps(summary), flush=True)
    return 0 if summary["roundtrip_passed"] else 1


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--seed", type=int, default=18001)
    args = parser.parse_args()
    return run(args.output.resolve(), args.seed)


if __name__ == "__main__":
    raise SystemExit(main())

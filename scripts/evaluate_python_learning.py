"""External fresh-case constructor. Does not import Nova or read generated code.

The evaluator reads only the frozen goal contract and freeze identifier. Seeds
are drawn after freeze from OS entropy. Reference ordering uses integer tuples,
independently of the kernel's searched representation and compiled execution.
"""
import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import random
import secrets


def key(value):
    return tuple(int(part) for part in value.split("."))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("frozen", type=Path)
    parser.add_argument("destination", type=Path)
    args = parser.parse_args()
    if args.destination.exists():
        raise SystemExit("fresh evaluation output already exists")
    artifact = json.loads(args.frozen.read_text())
    if set(artifact) != {"goal", "freeze"}:
        raise SystemExit("evaluator accepts only a goal and freeze, never candidate code")
    goal, freeze = artifact["goal"], artifact["freeze"]
    seed = secrets.token_hex(32)
    rng = random.Random(int(seed, 16))
    rows, categories = [], []
    if goal["contract"]["law"] == "lexicographic_integer_components":
        for i in range(24):
            base = str(rng.randrange(10000, 900000))
            prefix = base+"."+str(rng.randrange(1000))
            case = i % 8
            a, b, category = [
                (prefix+".2", prefix+".11", "shared_prefix_numeric"),
                (prefix+".12", prefix+".3", "shared_prefix_reverse"),
                (prefix, prefix, "irreflexive"),
                (prefix, prefix+".0", "shorter_prefix"),
                (prefix+".0", prefix, "longer_prefix"),
                ("0"+base+".02", base+".2", "leading_zero_equivalence"),
                (prefix+".999999", prefix+".999998", "large_components"),
                (prefix+".0.0.2", prefix+".0.0.10", "deep_shared_prefix")][case]
            rows.append({"input": {"left": a, "right": b}, "output": key(a) < key(b)})
            categories.append(category)
    elif goal["contract"]["law"] == "stable_permutation_by_inherited_relation":
        field = goal["contract"]["input_fields"][0]
        for i in range(24):
            base = str(rng.randrange(10000, 900000))
            values = [base+suffix for suffix in (".2", ".11", ".1", ".1.0", ".02", ".2", ".999999", ".20")]
            rng.shuffle(values)
            rows.append({"input": {field: values}, "output": sorted(values, key=key)})
            categories.append("stable_duplicate_prefix_numeric_permutation")
    else:
        raise SystemExit("unsupported frozen law; evaluator never changes it")
    result = {"freeze": freeze, "rows": rows, "seed": seed,
              "created_at": datetime.now(timezone.utc).isoformat(), "categories": categories,
              "oracle": "independent Python integer tuple comparison and stable reference ordering",
              "input_domain": "nonnegative decimal components 0..999999; 2..5 components; permutation length 8",
              "frozen_artifact_sha256": hashlib.sha256(args.frozen.read_bytes()).hexdigest(),
              "candidate_code_read_for_evaluation": False, "cases_generated_after_candidate_freeze": True}
    args.destination.write_text(json.dumps(result, ensure_ascii=False, indent=2)+"\n")
    print(json.dumps({"freeze": freeze, "fresh_cases": len(rows), "created_at": result["created_at"]}))


if __name__ == "__main__":
    main()

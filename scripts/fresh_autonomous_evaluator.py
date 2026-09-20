"""Independent post-freeze inputs; oracle code never enters native synthesis.

Receives the frozen goal and candidate ID only, not source or training examples.
This evaluator checks two declared laws; it cannot certify arbitrary new goals.
"""

import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import secrets


def generate(goal, freeze):
    law = goal["contract"]["law"]
    rows = []
    for index in range(24):
        if law == "numeric_less":
            left, right = (secrets.randbelow(10**9) - 5 * 10**8 for _ in range(2))
        elif law == "lexicographic_integer_components":
            def value():
                # Large random components separate these inputs from old small
                # releases; unequal lengths and leading zeroes are intentional.
                components = [str(secrets.randbelow(100000) + 1000) for _ in range(secrets.randbelow(4) + 2)]
                if index % 4 == 0:
                    components[0] = "00" + components[0]
                return ".".join(components)
            left, right = value(), value()
            if index % 6 == 1:
                right = left + ".0"
        else:
            raise ValueError("unsupported declared law")
        if index % 6 == 0:
            right = left
        if law == "numeric_less":
            expected = left < right
        else:
            expected = tuple(map(int, left.split("."))) < tuple(map(int, right.split(".")))
        rows.append({"input": {"left": left, "right": right}, "output": expected})
    return {"freeze": freeze, "rows": rows}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("frozen_request", type=Path)
    parser.add_argument("destination", type=Path)
    args = parser.parse_args()
    request = json.loads(args.frozen_request.read_text())
    if set(request) != {"goal", "freeze"}:
        raise ValueError("only the frozen goal and candidate identity are accepted")
    if set(request["goal"]) != {"id", "contract"}:
        raise ValueError("goal must contain only id and contract; no training or candidate source")
    result = generate(request["goal"], request["freeze"])
    # Creation is exclusive: this is a single-use hidden evaluation set.
    with args.destination.open("x") as handle:
        json.dump(result, handle, ensure_ascii=False, sort_keys=True, indent=2)
        handle.write("\n")
    receipt = {"created_at": datetime.now(timezone.utc).isoformat(), "freeze": request["freeze"],
        "entropy": "OS secrets after candidate freeze", "cases": len(result["rows"]),
        "file_sha256": hashlib.sha256(args.destination.read_bytes()).hexdigest(),
        "evaluator_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest()}
    args.destination.with_suffix(".receipt.json").write_text(json.dumps(receipt, indent=2) + "\n")
    print(json.dumps(receipt))


if __name__ == "__main__":
    main()

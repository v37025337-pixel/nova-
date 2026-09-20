"""Run with python -m nova_core; all work stops at the requested step budget."""

import argparse
import json
import sqlite3
import sys
from pathlib import Path

from .contracts import ContractError, decode
from .kernel import Kernel, runtime_manifest


def main(argv=None):
    parser = argparse.ArgumentParser(description="NOVA persistent program-learning kernel")
    parser.add_argument("--state", type=Path, default=Path("state/nova.sqlite"))
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("init")
    commands.add_parser("status")
    commands.add_parser("manifest")
    commands.add_parser("queue")
    commands.add_parser("memory")
    commands.add_parser("genome")
    commands.add_parser("upgrade")
    autonomous = commands.add_parser("autonomous")
    autonomous.add_argument("--steps", type=int, default=3)
    response = commands.add_parser("respond")
    response.add_argument("response", type=Path)
    auto_assess = commands.add_parser("assess-autonomous")
    auto_assess.add_argument("evaluation", type=Path)
    study = commands.add_parser("study")
    study.add_argument("specification", type=Path)
    study.add_argument("--steps", type=int, default=1)
    assess = commands.add_parser("assess")
    assess.add_argument("evaluation", type=Path)
    evolve = commands.add_parser("evolve")
    evolve.add_argument("suite", type=Path)
    evolve.add_argument("--steps", type=int, default=1)
    learn = commands.add_parser("learn")
    learn.add_argument("corpus", type=Path)
    learn.add_argument("--steps", type=int, default=3)
    step = commands.add_parser("step")
    step.add_argument("--steps", type=int, default=1)
    develop = commands.add_parser("develop")
    develop.add_argument("--steps", type=int, default=3)
    verify = commands.add_parser("verify")
    verify.add_argument("--expected-head")
    predict = commands.add_parser("predict")
    predict.add_argument("task")
    predict.add_argument("--input", required=True, help="JSON input object")
    rollback = commands.add_parser("rollback")
    rollback.add_argument("generation", type=int)
    backup = commands.add_parser("backup")
    backup.add_argument("destination", type=Path)
    commands.add_parser("export")
    args = parser.parse_args(argv)
    try:
        if hasattr(args, "steps") and not 1 <= args.steps <= 100:
            raise ContractError("steps must be in 1..100")
        if args.command == "manifest":
            result = runtime_manifest()
        else:
            # Validate a corpus before creating a new state file.
            corpus = None
            if args.command == "learn":
                from .contracts import task_spec
                corpus = decode(args.corpus.read_text(encoding="utf-8"))
                if type(corpus) is not list or not 1 <= len(corpus) <= 64:
                    raise ContractError("corpus must contain 1..64 tasks")
                corpus = [task_spec(t) for t in corpus]
            with Kernel(args.state, create=args.command in ("init", "learn")) as kernel:
                if args.command in ("init", "status"):
                    result = kernel.status()
                elif args.command in ("learn", "step", "develop"):
                    if corpus is not None:
                        kernel.register(corpus)
                    result = kernel.develop(args.steps)
                elif args.command == "queue":
                    result = kernel.queue()
                elif args.command == "memory":
                    result = kernel.causal_memory()
                elif args.command == "genome":
                    result = kernel.genome()
                elif args.command == "upgrade":
                    result = kernel.upgrade()
                elif args.command == "autonomous":
                    kernel.start_autonomy()
                    result = kernel.develop(args.steps)
                elif args.command == "respond":
                    result = kernel.autonomy_response(decode(args.response.read_text(encoding="utf-8")))
                elif args.command == "assess-autonomous":
                    evaluation = decode(args.evaluation.read_text(encoding="utf-8"))
                    if set(evaluation) != {"freeze", "rows"}:
                        raise ContractError("evaluation requires frozen identity and fresh rows")
                    result = kernel.autonomy_assess(evaluation["freeze"], evaluation["rows"])
                elif args.command == "evolve":
                    kernel.register_engine_trial(decode(args.suite.read_text(encoding="utf-8")))
                    result = kernel.develop(args.steps)
                elif args.command == "study":
                    kernel.study(decode(args.specification.read_text(encoding="utf-8")))
                    result = kernel.develop(args.steps)
                elif args.command == "assess":
                    evaluation = decode(args.evaluation.read_text(encoding="utf-8"))
                    if set(evaluation) != {"freeze", "rows"}:
                        raise ContractError("evaluation requires frozen identity and fresh rows")
                    result = kernel.assess(evaluation["freeze"], evaluation["rows"])
                elif args.command == "predict":
                    result = {"output": kernel.predict(args.task, decode(args.input))}
                elif args.command == "verify":
                    result = kernel.audit(expected_head=args.expected_head)
                elif args.command == "rollback":
                    result = kernel.rollback(args.generation)
                elif args.command == "backup":
                    result = kernel.backup(args.destination)
                else:
                    # Export uses a verified, single read of the event sequence.
                    kernel.audit()
                    events, head = kernel.journal.read()
                    result = {"schema": "nova.journal.export.v1", "head": head, "events": events}
        print(json.dumps(result, ensure_ascii=False, sort_keys=True, indent=2, allow_nan=False))
        return 0
    except (ContractError, OSError, ValueError, TypeError, KeyError, RecursionError, sqlite3.Error) as exc:
        print(json.dumps({"status": "ERROR", "error": type(exc).__name__, "message": str(exc)}, ensure_ascii=False), file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())

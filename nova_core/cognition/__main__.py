"""The active NOVA command: one persistent cognitive runtime."""

import argparse
import json
from pathlib import Path
import sys

from nova_core.contracts import ContractError, decode, encode
from .kernel import Kernel, manifest
from . import checkpoint


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--state", type=Path, default=Path("state/nova-unified.sqlite"))
    commands = p.add_subparsers(dest="command", required=True)
    for name in ("init", "status", "think", "memory", "catalog", "verify", "manifest"):
        commands.add_parser(name)
    for name in ("run", "step"):
        q = commands.add_parser(name)
        q.add_argument("--steps", type=int, default=16 if name == "run" else 1)
    q = commands.add_parser("connect")
    q.add_argument("feeds", type=Path)
    q = commands.add_parser("sense", help="observe opaque URLs without a task or reader")
    q.add_argument("urls", type=Path, help="JSON list of public HTTPS URLs")
    q = commands.add_parser("recall", help="restore exact observed bytes from active memory")
    q.add_argument("index", type=int)
    q.add_argument("--output", type=Path, required=True)
    q = commands.add_parser("invoke")
    q.add_argument("capability")
    q.add_argument("--input", required=True, help="JSON argument object")
    q = commands.add_parser("goal")
    q.add_argument("target")
    q.add_argument("--input", required=True, help="JSON object mapping input types to values")
    q = commands.add_parser("inspect")
    q.add_argument("url")
    q.add_argument("--label", default="source")
    q.add_argument("--steps", type=int, default=20)
    q = commands.add_parser("result")
    q.add_argument("identity")
    for name in ("learn", "study", "engine-trial"):
        q = commands.add_parser(name)
        q.add_argument("document", type=Path)
    q = commands.add_parser("observe-state")
    q.add_argument("identity")
    q.add_argument("document", type=Path)
    q = commands.add_parser("assess")
    q.add_argument("document", type=Path)
    q = commands.add_parser("rollback")
    q.add_argument("generation", type=int)
    q = commands.add_parser("export")
    q.add_argument("--output", type=Path, required=True)
    q = commands.add_parser("restore")
    q.add_argument("journal", type=Path)
    args = p.parse_args(argv)
    try:
        if args.command == "manifest":
            print(encode(manifest()))
            return 0
        if args.command == "restore":
            print(encode(Kernel.restore(checkpoint.read(args.journal), args.state)))
            return 0
        if hasattr(args, "steps") and not 1 <= args.steps <= 100:
            raise ContractError("step budget must be 1..100")
        with Kernel(args.state, create=args.command == "init") as kernel:
            command = args.command
            if command in ("init", "status"):
                result = kernel.status()
            elif command in ("run", "step"):
                actions = kernel.run(args.steps)
                result = {"actions": [{k: v for k, v in a.items() if k in ("status", "action")} for a in actions], "state": kernel.status()}
            elif command == "connect":
                result = kernel.connect(decode(args.feeds.read_text()))
            elif command == "sense":
                result = kernel.sense(decode(args.urls.read_text()))
            elif command == "recall":
                with args.output.open("xb") as output:
                    output.write(kernel.recall(args.index))
                result = {"status": "RECALLED", "index": args.index, "output": str(args.output)}
            elif command == "invoke":
                result = kernel.invoke(args.capability, decode(args.input))
            elif command == "goal":
                result = {"goal": kernel.goal(args.target, decode(args.input))}
            elif command == "inspect":
                identity = kernel.goal("code.report", {"source.url": args.url, "input.text": args.label})
                for _ in range(args.steps):
                    if kernel.result(identity)["status"] != "READY":
                        break
                    if "action" not in kernel.step():
                        break
                result = {"goal": identity, **kernel.result(identity)}
            elif command == "result":
                result = kernel.result(args.identity)
            elif command == "think":
                result = kernel.think()
            elif command in ("memory", "catalog"):
                result = kernel.memory()
                if command == "catalog":
                    result = result["catalog"]
            elif command == "verify":
                result = kernel.audit()
            elif command == "learn":
                result = kernel.register(decode(args.document.read_text()))
            elif command == "study":
                result = kernel.study(decode(args.document.read_text()))
            elif command == "engine-trial":
                result = kernel.engine_trial(decode(args.document.read_text()))
            elif command == "assess":
                body = decode(args.document.read_text())
                result = kernel.assess(body["freeze"], body["rows"])
            elif command == "observe-state":
                result = kernel.observe_states(args.identity, decode(args.document.read_text()))
            elif command == "rollback":
                result = kernel.rollback(args.generation)
            else:
                checkpoint.write(args.output, kernel.export())
                result = {"status": "EXPORTED", "head": kernel.status()["head"]}
        print(json.dumps(result, ensure_ascii=False, sort_keys=True, indent=2))
        return 0
    except (ValueError, TypeError, KeyError, OSError, RecursionError) as exc:
        print(encode({"status": "ERROR", "error": type(exc).__name__, "message": str(exc)}), file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())

"""Finite, restartable commands; no implicit background execution."""

import argparse
from pathlib import Path

from nova_core.contracts import decode, encode
from .kernel import Kernel
from . import snapshot


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--state", type=Path, required=True)
    sub = p.add_subparsers(dest="command", required=True)
    initialize = sub.add_parser("init")
    initialize.add_argument("--feeds", type=Path, help="JSON list of public HTTPS sources; no tasks or labels")
    sub.add_parser("status")
    r = sub.add_parser("run")
    r.add_argument("--steps", type=int, default=16)
    e = sub.add_parser("export")
    e.add_argument("--output", type=Path, required=True)
    restore = sub.add_parser("restore")
    restore.add_argument("journal", type=Path)
    q = sub.add_parser("predict")
    q.add_argument("law")
    q.add_argument("graph", type=Path)
    rb = sub.add_parser("rollback")
    rb.add_argument("generation", type=int)
    args = p.parse_args()
    if args.command == "restore":
        print(encode(Kernel.restore(snapshot.read(args.journal), args.state)))
        return
    feeds = decode(args.feeds.read_text()) if args.command == "init" and args.feeds else None
    with Kernel(args.state, create=args.command == "init", feeds=feeds) as kernel:
        if args.command == "run":
            if not 1 <= args.steps <= 100:
                p.error("steps must be 1..100")
            for _ in range(args.steps):
                action = kernel.step()
                print(encode({k: action[k] for k in ("status", "reason", "url", "bytes") if k in action}), flush=True)
                if action["status"] in ("IDLE", "WAITING"):
                    break
        elif args.command == "export":
            snapshot.write(args.output, kernel.export())
        elif args.command == "predict":
            print(encode({"result": kernel.predict(args.law, decode(args.graph.read_text()))}))
        elif args.command == "rollback":
            kernel.rollback(args.generation)
        print(encode(kernel.status()))


if __name__ == "__main__":
    main()

"""Run only compiler-reconstructed programs under Nova's actual seccomp boundary."""

from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from nova_core.contracts import ContractError, decode, encode
from nova_core.sandbox_worker import confine
from nova_next.data import validate_graph
from nova_next.programs import make_program


def main():
    body = decode(sys.stdin.read(2_000_001))
    if set(body) != {"program", "genes", "graphs"} or not 1 <= len(body["graphs"]) <= 96:
        raise ContractError("worker request contract")
    genes = body["genes"]
    if type(genes) is not dict or len(genes) > 32:
        raise ContractError("worker gene budget")
    programs = {**genes, body["program"]["id"]: body["program"]}
    functions = {}
    allowed = {"len": len, "sum": sum, "max": max, "range": range, "set": set, "ValueError": ValueError}
    for identity, program in programs.items():
        if make_program(program["tree"], genes) != program or identity != program["id"]:
            raise ContractError("generated source/tree/identity mismatch")
        namespace = {"__builtins__": allowed}
        exec(compile(program["source"], "<nova-next-generated>", "exec"), namespace)
        functions[identity] = namespace["solve"]
    graphs = [validate_graph(g) for g in body["graphs"]]
    confine()
    outputs = [functions[body["program"]["id"]](g, functions) for g in graphs]
    print(encode({"status": "PASS", "isolation": "linux_seccomp_v1", "outputs": outputs}))


if __name__ == "__main__":
    main()

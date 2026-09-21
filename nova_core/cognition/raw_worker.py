"""Execute compiler-reconstructed byte programs only after actual confinement."""

from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from nova_core.contracts import ContractError, decode, encode
from nova_core.sandbox_worker import confine
from nova_core.cognition.rawcodec import MAX_BYTES, frame, program


def main():
    body = decode(sys.stdin.read(1_800_001))
    if set(body) != {"program", "hex"} or not 1 <= len(body["hex"]) <= 16:
        raise ContractError("raw worker contract")
    model = program(body["program"]["rules"])
    if encode(model) != encode(body["program"]):
        raise ContractError("raw source/grammar/identity mismatch")
    blobs = [bytes.fromhex(item) for item in body["hex"]]
    if any(len(b) > MAX_BYTES for b in blobs):
        raise ContractError("raw worker byte budget")
    executable = compile(model["source"], "<nova-induced-byte-program>", "exec")
    namespace = {"__builtins__": {}}
    confine()
    exec(executable, namespace)
    frames = []
    for raw in blobs:
        tokens = namespace["encode_tokens"](raw.decode("latin1"))
        rebuilt = namespace["decode_tokens"](tokens).encode("latin1")
        if rebuilt != raw:
            raise ContractError("generated inverse failed")
        frames.append(frame(raw, tokens).hex())
    print(encode({"isolation": "linux_seccomp_v1", "frames": frames}))


if __name__ == "__main__":
    main()

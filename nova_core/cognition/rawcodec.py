"""Induce a byte grammar from observations; compile its learned rewrite program.

No language names, field readers, task families, expected outputs or seed phrases.
The inductive bias is adjacent-symbol substitution and minimum description length.
"""

from collections import Counter
from pathlib import Path
import subprocess
import sys

from nova_core.contracts import ContractError, decode, digest, encode

MAX_BYTES = 262144
MAX_RULES = 192
MAX_EXPANSION = 128


def validate_rules(rules):
    if type(rules) is not list or len(rules) > MAX_RULES:
        raise ContractError("byte grammar rule budget")
    sizes = [1] * 256
    seen = set()
    for pair in rules:
        if (type(pair) is not list or len(pair) != 2 or
                any(type(x) is not int or not 0 <= x < len(sizes) for x in pair)):
            raise ContractError("grammar must be an acyclic pair DAG over preceding symbols")
        size = sizes[pair[0]] + sizes[pair[1]]
        if size > MAX_EXPANSION or tuple(pair) in seen:
            raise ContractError("duplicate or oversized grammar expansion")
        sizes.append(size)
        seen.add(tuple(pair))
    return sizes


def program(rules):
    validate_rules(rules)
    forward, backward = [], []
    for i, (left, right) in enumerate(rules, 256):
        pair, symbol = ascii(chr(left) + chr(right)), ascii(chr(i))
        forward.append(f"    s = s.replace({pair}, {symbol})")
        backward.insert(0, f"    s = s.replace({symbol}, {pair})")
    source = "\n".join(["def encode_tokens(s):", *forward, "    return s", "",
                         "def decode_tokens(s):", *backward, "    return s", ""])
    body = {"schema": "nova.byte-grammar.v1", "rules": rules, "source": source}
    return {**body, "id": digest(body)}


def cost(model):
    # Charge the complete portable artifact, including generated source and identity.
    return len(encode(model).encode("utf-8"))


def frame(raw, tokens):
    """A 9-bit token stream, or literal fallback; no source meaning is interpreted."""
    literal = b"\x00" + raw
    if 9 + (len(tokens) * 9 + 7) // 8 >= len(literal):
        return literal
    out = bytearray(b"\x01" + len(raw).to_bytes(4, "big") + len(tokens).to_bytes(4, "big"))
    accumulator = bits = 0
    for token in tokens:
        accumulator = (accumulator << 9) | ord(token)
        bits += 9
        while bits >= 8:
            bits -= 8
            out.append((accumulator >> bits) & 255)
        accumulator &= (1 << bits) - 1
    if bits:
        out.append(accumulator << (8 - bits))
    return bytes(out)


def induce(blobs):
    if (not 1 <= len(blobs) <= 4 or any(type(b) is not bytes or len(b) > MAX_BYTES for b in blobs)):
        raise ContractError("bounded byte observations required")
    streams = [b.decode("latin1") for b in blobs]
    rules, sizes, history = [], [1] * 256, []
    best, best_size = None, sum(len(b) + 1 for b in blobs)
    for i in range(MAX_RULES):
        counts = Counter()
        for stream in streams:
            counts.update(zip(stream, stream[1:]))
        eligible = [(n, a, b) for (a, b), n in counts.items()
                    if n >= 4 and sizes[ord(a)] + sizes[ord(b)] <= MAX_EXPANSION]
        if not eligible:
            break
        count, a, b = min(eligible, key=lambda row: (-row[0], row[1], row[2]))
        rules.append([ord(a), ord(b)])
        sizes.append(sizes[ord(a)] + sizes[ord(b)])
        streams = [s.replace(a + b, chr(256 + i)) for s in streams]
        model = program([list(p) for p in rules])
        size = cost(model) + sum(min(len(raw) + 1, 9 + (len(s) * 9 + 7) // 8)
                                for raw, s in zip(blobs, streams))
        history.append({"rules": i + 1, "description_bytes": size, "pair_occurrences": count})
        if size < best_size:
            best, best_size = model, size
    return {"program": best, "description_bytes": best_size, "search": history,
            "method": "data-induced adjacent-symbol grammar, charged executable MDL"}


def isolated(model, blobs):
    request = encode({"program": model, "hex": [b.hex() for b in blobs]})
    if len(request.encode()) > 1_800_000 or not 1 <= len(blobs) <= 16:
        raise ContractError("raw execution request budget")
    worker = Path(__file__).with_name("raw_worker.py")
    process = subprocess.run([sys.executable, "-I", "-S", str(worker)], input=request,
                             text=True, capture_output=True, timeout=12, cwd="/", env={}, close_fds=True)
    if process.returncode:
        raise ContractError("raw compiled sandbox failed: " + process.stderr[-400:])
    result = decode(process.stdout)
    if result.get("isolation") != "linux_seccomp_v1" or len(result.get("frames", [])) != len(blobs):
        raise ContractError("missing raw isolation/output receipt")
    return [bytes.fromhex(item) for item in result["frames"]]

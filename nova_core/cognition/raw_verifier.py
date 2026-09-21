"""Independent wire decoder and exact-byte oracle; no fitting or source reader."""

import hashlib
import zlib

from nova_core.contracts import ContractError
from .rawcodec import MAX_BYTES, cost, isolated, validate_rules


def restore(model, wire):
    if not wire or len(wire) > MAX_BYTES + 1:
        raise ContractError("invalid raw memory frame budget")
    if wire[0] == 0:
        return wire[1:]
    if wire[0] != 1 or len(wire) < 9:
        raise ContractError("unknown memory wire format")
    length, count = int.from_bytes(wire[1:5], "big"), int.from_bytes(wire[5:9], "big")
    if not 0 < count <= length <= MAX_BYTES or len(wire) != 9 + (9 * count + 7) // 8:
        raise ContractError("invalid memory frame lengths")
    validate_rules(model["rules"])
    table = [bytes([i]) for i in range(256)]
    for a, b in model["rules"]:
        table.append(table[a] + table[b])
    bits = "".join(format(byte, "08b") for byte in wire[9:])
    if "1" in bits[9 * count:]:
        raise ContractError("non-canonical padding")
    result = bytearray()
    for offset in range(0, count * 9, 9):
        symbol = int(bits[offset:offset + 9], 2)
        if symbol >= len(table):
            raise ContractError("unknown learned symbol")
        result.extend(table[symbol])
        if len(result) > length:
            raise ContractError("memory expansion exceeds declared length")
    if len(result) != length:
        raise ContractError("memory expansion length mismatch")
    return bytes(result)


def score(model, blobs):
    # Keep each execution bounded even when a regression corpus has grown.
    frames = [isolated(model, [blob])[0] for blob in blobs]
    rows = []
    for raw, wire in zip(blobs, frames):
        actual = restore(model, wire)
        rows.append({"sha256": hashlib.sha256(raw).hexdigest(), "raw_bytes": len(raw),
                     "stored_bytes": len(wire), "wire_sha256": hashlib.sha256(wire).hexdigest(),
                     "exact": actual == raw})
    raw_size = sum(len(b) + 1 for b in blobs)
    stored = cost(model) + sum(len(frame) for frame in frames)
    return {"passed": sum(r["exact"] for r in rows), "total": len(rows), "rows": rows,
            "literal_bytes": raw_size, "model_bytes": cost(model), "description_bytes": stored,
            "net_saved_bytes": raw_size - stored, "isolation": "linux_seccomp_v1",
            "zlib_reference_bytes": sum(len(zlib.compress(b, 9)) for b in blobs),
            "oracle": "original external bytes, independent DAG expansion and bit decoder"}

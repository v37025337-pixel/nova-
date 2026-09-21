"""Lossless JSON checkpoints; preserve sets, tuple keys and integer-keyed maps."""

import gzip
import json
from pathlib import Path

from nova_core.contracts import ContractError, _pairs, encode


def pack(value):
    if isinstance(value, dict):
        pairs = [[pack(k), pack(v)] for k, v in value.items()]
        return {"map": sorted(pairs, key=lambda p: encode(p[0]))}
    if isinstance(value, set):
        return {"set": sorted((pack(v) for v in value), key=encode)}
    if isinstance(value, tuple):
        return {"tuple": [pack(v) for v in value]}
    if isinstance(value, list):
        return [pack(v) for v in value]
    if type(value) not in (str, int, float, bool, type(None)):
        raise ContractError("unsupported checkpoint value")
    return value


def unpack(value):
    if isinstance(value, list):
        return [unpack(v) for v in value]
    if isinstance(value, dict):
        if set(value) == {"map"}:
            result = {}
            for k, v in value["map"]:
                key = unpack(k)
                if key in result:
                    raise ContractError("duplicate checkpoint key")
                result[key] = unpack(v)
            return result
        if set(value) == {"set"}:
            items = [unpack(v) for v in value["set"]]
            if len(set(items)) != len(items):
                raise ContractError("duplicate checkpoint set member")
            return set(items)
        if set(value) == {"tuple"}:
            return tuple(unpack(v) for v in value["tuple"])
        raise ContractError("unknown checkpoint encoding")
    return value


def read(path):
    opener = gzip.open if str(path).endswith(".gz") else open
    with opener(path, "rb") as source:
        raw = source.read(32_000_001)
    if len(raw) > 32_000_000:
        raise ContractError("checkpoint exceeds 32 MB")
    def reject(_):
        raise ContractError("non-finite checkpoint number")
    return json.loads(raw, object_pairs_hook=_pairs, parse_constant=reject)


def write(path, value):
    raw = (encode(value) + "\n").encode()
    if len(raw) > 32_000_000:
        raise ContractError("checkpoint exceeds 32 MB")
    path = Path(path)
    path.write_bytes(gzip.compress(raw, mtime=0) if path.suffix == ".gz" else raw)

"""Bounded journal files; each replayed event retains the original 2 MB limit."""

import gzip
import json
from pathlib import Path

from nova_core.contracts import ContractError, _pairs, encode

LIMIT = 32_000_000


def read(path):
    path = Path(path)
    opener = gzip.open if path.suffix == ".gz" else open
    with opener(path, "rb") as stream:
        raw = stream.read(LIMIT + 1)
    if len(raw) > LIMIT:
        raise ContractError("journal exceeds 32 MB")
    def reject(_):
        raise ContractError("non-finite JSON number")
    body = json.loads(raw, object_pairs_hook=_pairs, parse_constant=reject)
    if type(body) is not dict or type(body.get("events")) is not list or not 1 <= len(body["events"]) <= 1024:
        raise ContractError("journal requires 1..1024 events")
    return body


def write(path, exported):
    raw = (encode(exported) + "\n").encode()
    if len(raw) > LIMIT:
        raise ContractError("journal exceeds 32 MB")
    path = Path(path)
    path.write_bytes(gzip.compress(raw, mtime=0) if path.suffix == ".gz" else raw)

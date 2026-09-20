"""Versioned JSON contracts shared by memory, learning and execution."""

import hashlib
import json
import math
import re


class ContractError(ValueError):
    pass


class IntegrityError(ContractError):
    pass


class StaleState(ContractError):
    pass


def normalized(value, depth=0):
    if depth > 16:
        raise ContractError("JSON depth exceeds 16")
    if value is None or type(value) is bool:
        return value
    if type(value) in (int, float):
        if abs(value) > 10**15 or not math.isfinite(value):
            raise ContractError("number must be finite and bounded")
        return int(value) if value == int(value) else value
    if type(value) is str:
        if len(value) > 8192:
            raise ContractError("text exceeds 8192 characters")
        value.encode("utf-8")
        return value
    if type(value) is list and len(value) <= 128:
        return [normalized(v, depth + 1) for v in value]
    if type(value) is dict and len(value) <= 128:
        if any(type(k) is not str or len(k) > 128 for k in value):
            raise ContractError("object keys must be short strings")
        return {k: normalized(v, depth + 1) for k, v in value.items()}
    raise ContractError("unsupported or oversized JSON value")


def encode(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"),
                      ensure_ascii=False, allow_nan=False)


def digest(value):
    return hashlib.sha256(encode(value).encode("utf-8")).hexdigest()


def equal(left, right):
    # Canonical JSON distinguishes true/1, ignores object order, preserves arrays.
    return encode(normalized(left)) == encode(normalized(right))


def _pairs(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ContractError("duplicate JSON key: " + key)
        result[key] = value
    return result


def decode(text):
    if len(text.encode("utf-8")) > 2_000_000:
        raise ContractError("JSON document exceeds 2 MB")
    return json.loads(text, object_pairs_hook=_pairs,
                      parse_constant=lambda _: (_ for _ in ()).throw(
                          ContractError("non-finite JSON number")))


def task_spec(raw):
    if type(raw) is not dict or set(raw) != {"id", "source", "train", "holdout"}:
        raise ContractError("task requires exactly id, source, train, holdout")
    if type(raw["id"]) is not str or not re.fullmatch(r"[a-zA-Z0-9_.-]{1,80}", raw["id"]):
        raise ContractError("invalid task id")
    if type(raw["source"]) is not str or not 1 <= len(raw["source"]) <= 1024:
        raise ContractError("task source is required")
    result = {"id": raw["id"], "source": raw["source"]}
    seen = set()
    keys = None
    for split in ("train", "holdout"):
        rows = raw[split]
        if type(rows) is not list or not 2 <= len(rows) <= 32:
            raise ContractError("each split requires 2..32 examples")
        result[split] = []
        for row in rows:
            if type(row) is not dict or set(row) != {"input", "output"}:
                raise ContractError("example requires input and output")
            item = normalized(row)
            inputs = item["input"]
            if type(inputs) is not dict or not 1 <= len(inputs) <= 8:
                raise ContractError("input must be an object with 1..8 fields")
            if keys is None:
                keys = set(inputs)
            if set(inputs) != keys:
                raise ContractError("inconsistent input fields")
            token = digest(inputs)
            if token in seen:
                raise ContractError("duplicate input or train/holdout overlap")
            seen.add(token)
            result[split].append(item)
    return result


def dataset_id(task):
    # Renaming a task/source cannot reset an already consumed holdout.
    return digest({k: sorted(task[k], key=lambda row: digest(row["input"]))
                   for k in ("train", "holdout")})

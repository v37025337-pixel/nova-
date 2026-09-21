"""One observable -> endogenous objective -> induced program -> transfer cycle.

The supplied preference is exact retention with shorter descriptions. Concrete
deficits, evidence, byte rules and programs are derived from observations. This is
bounded grammar learning, not a claim to invent arbitrary goals or algorithms.
"""

from collections import Counter
from copy import deepcopy
import hashlib
import math

from nova_core.contracts import ContractError, IntegrityError, digest, encode
from nova_next.kernel import origin
from nova_next.network import public_url
from . import rawcodec, raw_verifier


def initial():
    return {"feeds": [], "used": [], "records": [], "discovery": [], "fresh": [],
            "phase": "OFF", "goal": None, "candidate": None, "history": [],
            "models": {}, "active": [], "admitted": [], "failures": [], "consumed": []}


def read(state, index):
    if type(index) is not int or not 0 <= index < len(state["records"]):
        raise ContractError("unknown raw observation index")
    record = state["records"][index]
    storage = record["storage"]
    wire = bytes.fromhex(storage["hex"])
    raw = raw_verifier.restore(state["models"][storage["model"]], wire) if storage["model"] else wire
    if len(raw) != record["bytes"] or hashlib.sha256(raw).hexdigest() != record["sha256"]:
        raise IntegrityError("raw memory no longer matches its observation")
    return raw


def connect(state, urls):
    if (type(urls) is not list or not 2 <= len(urls) <= 16 or len(state["feeds"]) + len(urls) > 32
            or any(type(url) is not str for url in urls) or len(set(urls)) != len(urls)
            or set(urls).intersection(state["feeds"])):
        raise ContractError("sense accepts 2..16 new URLs only, with a lifetime limit of 32")
    for url in urls:
        public_url(url, resolve=False)
    state["feeds"].extend(urls)
    if state["phase"] in ("OFF", "DONE"):
        if len(state["history"]) >= 8:
            raise ContractError("raw cycle lifetime budget")
        state.update(phase="OBSERVING", goal=None, candidate=None, discovery=[], fresh=[])


def choice(state):
    if state["phase"] in ("OFF", "DONE"):
        return None
    if state["candidate"] and len(state["fresh"]) >= 2:
        kind = "raw.assess"
    elif state["goal"] and not state["candidate"]:
        kind = "raw.synthesize"
    elif not state["goal"] and len(state["discovery"]) >= 2:
        kind = "raw.discover"
    elif any(url not in state["used"] for url in state["feeds"]):
        kind = "raw.fetch"
    else:
        return {"kind": "raw.wait", "reason": "OPAQUE_SOURCE_POOL_EXHAUSTED"}
    result = {"kind": kind, "priority": 130, "cost": 8 if kind == "raw.fetch" else 4,
              "cause": state["candidate"]["freeze"] if state["candidate"] else "observed description cost"}
    if kind == "raw.fetch":
        result["url"] = next(url for url in state["feeds"] if url not in state["used"])
        result["role"] = "transfer" if state["candidate"] else "discovery"
    return result


def known(state, inherited):
    origins, hashes = set(), set()
    for r in [*inherited, *state["records"]]:
        origins.update(origin(r[url]) for url in ("url", "final_url") if url in r)
        hashes.add(r["sha256"])
    return {"origins": sorted(origins), "hashes": sorted(hashes)}


def observe(state, request, receipt, inherited):
    required = {"url", "final_url", "status", "hex", "sha256", "bytes", "received_at", "transport", "dns_policy"}
    if type(receipt) is not dict or set(receipt) != required or receipt["url"] != request["url"]:
        raise ContractError("opaque receipt contract")
    if (type(receipt["status"]) is not int or receipt["status"] != 200 or
            type(receipt["bytes"]) is not int or not 1 <= receipt["bytes"] <= rawcodec.MAX_BYTES or
            type(receipt["hex"]) is not str or len(receipt["hex"]) != 2 * receipt["bytes"] or
            type(receipt["received_at"]) is not str or len(receipt["received_at"]) > 64 or
            receipt["transport"] not in ("stdlib_https", "test_fixture") or
            receipt["dns_policy"] not in ("configured_proxy", "local_public_resolution", "test_fixture")):
        raise ContractError("opaque receipt types or bounds")
    public_url(receipt["url"], resolve=False)
    public_url(receipt["final_url"], resolve=False)
    raw = bytes.fromhex(receipt["hex"])
    if raw.hex() != receipt["hex"] or hashlib.sha256(raw).hexdigest() != receipt["sha256"]:
        raise IntegrityError("opaque receipt content mismatch")
    exposure = known(state, inherited)
    source_origins = {origin(receipt["url"]), origin(receipt["final_url"])}
    if receipt["sha256"] in exposure["hashes"] or source_origins.intersection(exposure["origins"]):
        raise ContractError("source/content is already exposed; aliases cannot reset freshness")
    index = len(state["records"])
    record = {k: v for k, v in receipt.items() if k != "hex"}
    record.update(storage={"model": None, "hex": raw.hex()}, role=request["role"],
                  freeze=state["candidate"]["freeze"] if state["candidate"] else None)
    state["records"].append(record)
    state["fresh" if request["role"] == "transfer" else "discovery"].append(index)
    state["used"].append(request["url"])


def baseline(state, blobs):
    rows = [{"id": "literal", "bytes": sum(len(b) + 1 for b in blobs)}]
    for identity in state["active"]:
        result = raw_verifier.score(state["models"][identity], blobs)
        if result["passed"] != result["total"]:
            raise IntegrityError("existing raw memory mechanism regressed")
        rows.append({"id": identity, "bytes": result["description_bytes"]})
    return min(rows, key=lambda r: (r["bytes"], r["id"]))


def discover(state):
    blobs = [read(state, i) for i in state["discovery"]]
    pairs, prefixes = Counter(), Counter()
    for raw in blobs:
        pairs.update(zip(raw, raw[1:]))
        prefixes.update(raw[:-1])
    size = sum(len(b) for b in blobs)
    # A diagnostic lower bound, never an admission score or generated target label.
    conditional_bits = sum(n * math.log2(prefixes[a] / n) for (a, _), n in pairs.items())
    lower_bound = math.ceil(conditional_bits / 8) + len(blobs) + 2 * len(pairs)
    active = baseline(state, blobs)
    gap = active["bytes"] - lower_bound
    if size < 4096 or gap < max(2048, size // 20):
        return {"status": "IDLE", "reason": "NO_MEASURED_DESCRIPTION_DEFICIT", "bytes": size,
                "conditional_bound_bytes": lower_bound, "baseline": active}
    body = {"objective": "retain exact observations in a shorter reusable description",
            "origin": "self: measured byte-transition redundancy against active memory cost",
            "observations": [state["records"][i]["sha256"] for i in state["discovery"]],
            "baseline": active, "conditional_bound_bytes": lower_bound, "deficit_bytes": gap,
            "acceptance": {"fresh_origins": 2, "exact_reconstruction": True,
                           "minimum_net_gain_basis_points": 100, "charge_full_program": True,
                           "preserve_all_active_skills": True},
            "provided_preference": "lossless retention with minimum description length"}
    return {"status": "GOAL_FORMED", "goal": {**body, "id": digest(body)}}


def synthesize(state, inherited):
    blobs = [read(state, i) for i in state["discovery"]]
    learned = rawcodec.induce(blobs)
    model = learned["program"]
    if model is None:
        return {"status": "WITHHOLD", "reason": "NO_EXECUTABLE_MDL_GAIN", "search": learned["search"]}
    tested = raw_verifier.score(model, blobs)
    active = baseline(state, blobs)
    if tested["passed"] != tested["total"] or tested["description_bytes"] >= active["bytes"]:
        return {"status": "WITHHOLD", "reason": "DISCOVERY_GAIN_FAILED", "score": tested}
    body = {"goal": state["goal"]["id"], "program": model, "training": tested,
            "training_indices": list(state["discovery"]), "exposure": known(state, inherited),
            "search": learned["search"], "method": learned["method"],
            "transfer_policy": state["goal"]["acceptance"]}
    return {"status": "FROZEN", "candidate": {**body, "freeze": digest(body)}}


def assess(state):
    candidate = state["candidate"]
    rows = [state["records"][i] for i in state["fresh"]]
    if (len(rows) != 2 or any(r["freeze"] != candidate["freeze"] for r in rows) or
            any(r["sha256"] in state["consumed"] for r in rows)):
        raise IntegrityError("transfer requires two reserved, unconsumed post-freeze observations")
    blobs = [read(state, i) for i in state["fresh"]]
    model = candidate["program"]
    transfer = raw_verifier.score(model, blobs)
    active = baseline(state, blobs)
    # Actually execute a program with all data-derived rewrites removed.
    ablation = raw_verifier.score(rawcodec.program([]), blobs)
    gain = active["bytes"] - transfer["description_bytes"]
    sufficient = gain * 10000 >= active["bytes"] * candidate["transfer_policy"]["minimum_net_gain_basis_points"]
    reason = "TRANSFERRED_DESCRIPTION_GAIN"
    if transfer["passed"] != transfer["total"]:
        reason = "EXACT_RECONSTRUCTION_FAILED"
    elif not sufficient:
        reason = "NO_NET_TRANSFER_GAIN"
    elif any(row["stored_bytes"] >= row["raw_bytes"] for row in transfer["rows"]):
        reason = "NO_PER_SOURCE_TRANSFER_GAIN"
    elif ablation["description_bytes"] <= transfer["description_bytes"]:
        reason = "LEARNED_RULES_NOT_NECESSARY"
    return {"status": "ADMITTED" if reason == "TRANSFERRED_DESCRIPTION_GAIN" else "WITHHOLD",
            "reason": reason, "freeze": candidate["freeze"], "program": model["id"],
            "transfer": transfer, "baseline": active, "net_gain_bytes": gain,
            "ablation": ablation, "origins": sorted({origin(r["final_url"]) for r in rows}),
            "fresh_indices": list(state["fresh"])}


def materialize(state, identity):
    indices = list(range(len(state["records"])))
    # One document per worker call keeps the IPC and CPU budgets independent of history size.
    for index in indices:
        raw = read(state, index)
        if identity is None:
            storage = {"model": None, "hex": raw.hex()}
        else:
            wire = rawcodec.isolated(state["models"][identity], [raw])[0]
            if raw_verifier.restore(state["models"][identity], wire) != raw:
                raise IntegrityError("materialized memory differs")
            storage = {"model": identity, "hex": wire.hex()}
        state["records"][index]["storage"] = storage


def apply(state, request, result, inherited):
    kind, status = request["kind"], result["status"]
    if kind == "raw.fetch":
        if status == "OBSERVED":
            observe(state, request, result["receipt"], inherited)
        elif status == "FETCH_FAILED":
            if set(result) != {"status", "error"} or type(result["error"]) is not str or len(result["error"]) > 4096:
                raise IntegrityError("raw failure evidence contract")
            state["failures"].append({"url": request["url"], "error": result["error"]})
            state["used"].append(request["url"])
        else:
            raise IntegrityError("unknown raw acquisition outcome")
        return
    expected = discover(state) if kind == "raw.discover" else synthesize(state, inherited) if kind == "raw.synthesize" else assess(state)
    if encode(result) != encode(expected):
        raise IntegrityError("raw goal/program/transfer semantic replay differs")
    if status == "GOAL_FORMED":
        state["goal"] = deepcopy(result["goal"])
        state["phase"] = "SYNTHESIZING"
    elif status == "FROZEN":
        state["candidate"] = deepcopy(result["candidate"])
        state["phase"] = "TRANSFER"
    else:
        if kind == "raw.assess":
            state["consumed"].extend(state["records"][i]["sha256"] for i in state["fresh"])
        if status == "ADMITTED":
            model = state["candidate"]["program"]
            state["models"][model["id"]] = model
            state["active"].append(model["id"])
            state["admitted"].append({"program": model["id"], "result": deepcopy(result),
                                      "indices": list(state["discovery"] + state["fresh"])})
            materialize(state, model["id"])
        state["history"].append({"goal": state["goal"], "candidate": state["candidate"], "result": deepcopy(result)})
        state.update(phase="DONE", candidate=None)


def regression(state):
    results = {}
    for admission in state["admitted"]:
        identity = admission["program"]
        if identity in state["active"]:
            results[identity] = raw_verifier.score(state["models"][identity], [read(state, i) for i in admission["indices"]])
    return results


def summary(state):
    storage = sum(len(bytes.fromhex(r["storage"]["hex"])) for r in state["records"])
    models = {r["storage"]["model"] for r in state["records"]} - {None}
    model_cost = sum(rawcodec.cost(state["models"][i]) for i in models)
    return {"phase": state["phase"], "goal": state["goal"],
            "freeze": state["candidate"]["freeze"] if state["candidate"] else None,
            "active": state["active"], "observations": len(state["records"]),
            "exposed_hashes": [r["sha256"] for r in state["records"]], "consumed": state["consumed"],
            "raw_bytes": sum(r["bytes"] for r in state["records"]),
            "stored_bytes": storage, "model_bytes": model_cost, "description_bytes": storage + model_cost,
            "history": [{"goal": item["goal"]["id"] if item["goal"] else None, "result": item["result"]} for item in state["history"]],
            "failures": state["failures"]}

"""One typed catalog and executor for learned genes, source reading and reasoning."""

from pathlib import PurePosixPath
from urllib.parse import urlsplit

from nova_core.contracts import ContractError, normalized
from nova_core.kernel import context
from nova_core.isolation import evaluate
from nova_next import data, evaluation, network, seed_ucr
from nova_tools.universal_code_reader import UniversalCodeReader
from .logic import reason


def descriptor(identity, inputs, output, origin, cost=1):
    return {"id": identity, "inputs": inputs, "output": output, "origin": origin, "cost": cost}


def catalog(state):
    result = {}
    def add(identity, inputs, output, origin="maintainer infrastructure", cost=1):
        result[identity] = descriptor(identity, inputs, output, origin, cost)
    bindings, memory, _ = context(state["legacy"])
    for name, pid in sorted(bindings.items()):
        fields = state["legacy"]["tasks"][name]["train"][0]["input"]
        add("skill:" + name, {k: "input." + k for k in fields}, "skill." + name,
            {"kind": "inherited_or_admitted_program", "program": pid})
    for pid in state["legacy"]["genomes"][state["legacy"]["current"]].get("capabilities", []):
        add("primitive:" + pid, {"inputs": "primitive.inputs"}, "primitive." + pid,
            {"kind": "inherited_extension", "program": pid})
    for acquired in state["graph"]["admitted"]:
        law = acquired["goal"]["law"]
        add("graph:" + law, {"graph": "code.graph"}, "graph." + law,
            {"kind": "admitted_graph_program", "program": acquired["program"]["id"]}, 2)
    for item in seed_ucr.KERNEL_BLUEPRINT["primitives"]:
        add("seed:" + item["machine_id"], {"args": "seed.args"}, "seed." + item["machine_id"],
            {"kind": "provided_UCR_primitive", "independent_new_admission": False})
    add("source.fetch", {"url": "source.url"}, "source.capture", cost=8)
    add("reader.read", {"capture": "source.capture"}, "source.ir", cost=2)
    add("reader.cognitive", {"capture": "source.capture", "traces": "reader.traces"}, "reader.hypotheses", cost=4)
    add("source.graph", {"capture": "source.capture"}, "code.graph", cost=2)
    add("logic.reason", {"facts": "logic.facts", "rules": "logic.rules", "query": "logic.query"}, "logic.conclusion")
    add("state.predict", {"identity": "state.identity", "action": "state.action", "before": "state.before"}, "state.prediction")
    metrics = {a["goal"]["law"]: "graph." + a["goal"]["law"] for a in state["graph"]["admitted"]}
    if "maximum_impact" in metrics and "reachable_pairs" in metrics and "30-record" in bindings:
        common = {"capture": "source.capture", "ir": "source.ir", "graph": "code.graph", **metrics}
        add("logic.code_evidence", common, "code.support")
        add("report.code", {**common, "label": "skill.30-record", "support": "code.support"}, "code.report")
    return result


def module_name(capture):
    return PurePosixPath(urlsplit(capture["url"]).path).stem[:80] or "source"


def captures(state):
    documents = state["graph"]["documents"] + state["graph"]["fresh"]
    rows = [d["receipt"] for d in documents] + state["captures"]
    return list({(row["url"], row["sha256"]): row for row in rows}.values())


def validate_capture(capture, url):
    import hashlib
    from datetime import datetime
    network.public_url(url, resolve=False)
    network.public_url(capture["final_url"], resolve=False)
    if (capture["url"] != url or capture["status"] != 200 or capture["transport"] != "stdlib_https"
            or not 0 < len(capture["text"].encode()) <= data.MAX_BYTES
            or len(capture["text"].encode()) != capture["bytes"]
            or hashlib.sha256(capture["text"].encode()).hexdigest() != capture["sha256"]
            or datetime.fromisoformat(capture["received_at"]).tzinfo is None):
        raise ContractError("captured response identity/content mismatch")
    return capture


def invoke(state, identity, inputs, captured=None):
    item = catalog(state).get(identity)
    if item is None or type(inputs) is not dict or set(inputs) != set(item["inputs"]):
        raise ContractError("capability or argument contract differs")
    if identity.startswith(("skill:", "primitive:")):
        bindings, memory, _ = context(state["legacy"])
        if identity.startswith("skill:"):
            program, args = memory[bindings[identity[6:]]], normalized(inputs)
        else:
            program, args = memory[identity[10:]], normalized(inputs["inputs"])
        result = evaluate([{"program": program, "rows": [{"input": args, "output": None}]}], memory)
        outcome = result["results"][0]["outcomes"][0]
        if "error" in outcome:
            raise ContractError("inherited execution failed: " + outcome["error"])
        return outcome["output"]
    if identity.startswith("graph:"):
        law = identity[6:]
        acquired = next(a for a in state["graph"]["admitted"] if a["goal"]["law"] == law)
        return evaluation.isolated(acquired["program"], [data.validate_graph(inputs["graph"])], state["graph"]["genes"])[0]
    if identity.startswith("seed:"):
        primitive = next(p for p in seed_ucr.KERNEL_BLUEPRINT["primitives"] if p["machine_id"] == identity[5:])
        args = normalized(inputs["args"])
        if type(args) is not list or len(args) != primitive["blueprint"]["arity"]:
            raise ContractError("primitive arity differs")
        return normalized(seed_ucr._eval_blueprint(primitive["blueprint"], args))
    if identity == "source.fetch":
        url = inputs["url"]
        previous = next((r for r in captures(state) if r["url"] == url), None)
        if previous is not None:
            if captured is not None and captured != previous:
                raise ContractError("cached source differs from known receipt")
            return previous
        if state["graph"]["candidate"] is not None:
            raise ContractError("frozen candidate reserves unseen sources; connect feeds and evaluate first")
        return validate_capture(network.fetch(url) if captured is None else captured, url)
    if identity in ("reader.read", "reader.cognitive"):
        receipt = inputs["capture"]
        validate_capture(receipt, receipt["url"])
        raw = receipt["text"].encode()
        reader = UniversalCodeReader()
        if identity == "reader.cognitive":
            traces = inputs["traces"]
            if type(traces) is not list or not 1 <= len(traces) <= 128:
                raise ContractError("trace budget")
            result, cycle = reader.read_with_cognitive_observations(raw, traces, filename=module_name(receipt) + ".py", max_depth=2)
            return {"hypotheses": cycle, "origin": "caller supplied traces", "new_admission": False}
        result = reader.read(raw, module_name(receipt) + ".py")
        return {"sha256": result.sha256, "language": result.language, "nodes": len(result.nodes),
                "roundtrip": result.restore_bytes() == raw, "passport": result.passport(),
                "semantics": "static source representation; source not executed"}
    if identity == "source.graph":
        receipt = inputs["capture"]
        validate_capture(receipt, receipt["url"])
        return data.parse_source(receipt["text"], module_name(receipt))["graph"]
    if identity == "logic.reason":
        return reason(inputs["facts"], inputs["rules"], inputs["query"])
    if identity == "state.predict":
        stream = state["graph"]["state_streams"][inputs["identity"]]
        fitted = seed_ucr._learn_state_prediction_models_v29(stream, {"affine_int", "mod_add_int"})
        after = seed_ucr._predict_with_models_v29(fitted, inputs["action"], inputs["before"])
        return {"status": "PREDICTED" if after is not None else "AMBIGUOUS", "after": after,
                "new_admission": False, "origin": "inherited UCR fitter"}
    if identity == "logic.code_evidence":
        n = len(inputs["graph"]["nodes"])
        valid = (type(inputs["maximum_impact"]) is int and 0 <= inputs["maximum_impact"] < n
                 and type(inputs["reachable_pairs"]) is int and 0 <= inputs["reachable_pairs"] <= n * (n - 1))
        if "indirect_pairs" in inputs:
            valid = valid and type(inputs["indirect_pairs"]) is int and 0 <= inputs["indirect_pairs"] <= inputs["reachable_pairs"]
        preserved = inputs["ir"]["roundtrip"] and inputs["ir"]["sha256"] == inputs["capture"]["sha256"]
        facts = [["source", "captured"], ["roundtrip" if preserved else "!roundtrip", "preserved"],
                 ["bounds" if valid else "!bounds", "valid"]]
        rules = [{"id": "source-preserved", "if": [["source", "captured"], ["roundtrip", "preserved"]], "then": ["evidence", "grounded"]},
                 {"id": "report-bounds", "if": [["evidence", "grounded"], ["bounds", "valid"]], "then": ["report", "supported"]},
                 {"id": "report-invalid", "if": [["!bounds", "valid"]], "then": ["!report", "supported"]},
                 {"id": "source-invalid", "if": [["!roundtrip", "preserved"]], "then": ["!report", "supported"]}]
        return reason(facts, rules, ["report", "supported"])
    if identity == "report.code":
        if inputs["support"]["verdict"] != "TRUE" or not inputs["support"]["complete"]:
            raise ContractError("report lacks complete consistent support")
        metrics = {key: inputs[key] for key in ("maximum_impact", "reachable_pairs", "indirect_pairs") if key in inputs}
        return {"source": inputs["capture"]["url"], "source_sha256": inputs["capture"]["sha256"],
                "label": inputs["label"], "language": inputs["ir"]["language"],
                "functions": len(inputs["graph"]["nodes"]), "static_call_edges": len(inputs["graph"]["edges"]),
                "metrics": metrics, "logic": inputs["support"],
                "claim": "inherited and acquired mechanisms jointly applied to captured source; not runtime causality"}
    raise ContractError("capability has no executor")

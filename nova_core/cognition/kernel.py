"""One journal, active genome, scheduler and workspace for all NOVA capabilities."""

from copy import deepcopy
import hashlib
from pathlib import Path
import sys
import tempfile

from nova_core import kernel as expression, capability
from nova_core.adaptation import trial_spec, input_tokens
from nova_core.contracts import ContractError, IntegrityError, digest, encode, task_spec
from nova_core.isolation import evaluate
from nova_core.memory import Journal, ZERO
from nova_next import kernel as graph_engine, learning, evaluation, network, data
from . import capabilities, checkpoint, planning, raw_cycle, raw_network

ROOT = Path(__file__).resolve().parents[2]
BOOTSTRAP = Path(__file__).with_name("bootstrap-v2.json.gz")


def same(left, right):
    return encode(left) == encode(right)


def manifest():
    paths = [p for folder in ("nova_core", "nova_next", "nova_tools") for p in (ROOT / folder).rglob("*.py")]
    paths += [BOOTSTRAP, ROOT / "nova_next/inherited.json", ROOT / "nova_next/seed_blueprint.json"]
    return {"schema": "nova.unified.runtime.v1", "version": "1.1.0", "python": list(sys.version_info[:2]),
            "source_sha256": {str(p.relative_to(ROOT)): hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(paths)},
            "state": "one journal, scheduler, capability catalog, active genome and cognitive workspace",
            "faculties": {"logic": "bounded four-valued Horn inference with evidence",
                          "thinking": "typed action planning and dependency resolution",
                          "intelligence": "experience-conditioned action cost and goal selection"}}


def genome(state):
    legacy = state["legacy"]
    body = {"legacy": legacy["genomes"][legacy["current"]]["id"], "graph": state["graph"]["genes"]}
    if state.get("raw", {}).get("active"):
        body["raw"] = state["raw"]["active"]
    return digest(body)


def active_snapshot(state):
    return {"legacy_generation": state["legacy"]["current"],
            "graph_generation": state["graph"]["generation"],
            "graph_genes": deepcopy(state["graph"]["genes"]), "graph_admitted": deepcopy(state["graph"]["admitted"]),
            "raw_active": list(state.get("raw", {}).get("active", []))}


def initial(bootstrap):
    if bootstrap["schema"] == "nova.unified.bootstrap.v2" and bootstrap["proof"]["status"] == "PASS":
        state = checkpoint.unpack(bootstrap["state"])
        state["raw"] = raw_cycle.initial()
        for snapshot in state["snapshots"].values():
            snapshot["raw_active"] = []
        return state
    if bootstrap["schema"] != "nova.unified.bootstrap.v1" or bootstrap["proof"]["status"] != "PASS":
        raise IntegrityError("unsupported unified bootstrap")
    state = {"legacy": checkpoint.unpack(bootstrap["legacy"]), "graph": checkpoint.unpack(bootstrap["graph"]),
             "generation": 0, "admissions": 0, "parents": {0: None}, "snapshots": {},
             "goals": {}, "experience": {}, "captures": [], "idle": set(), "workspace": None, "executions": 0,
             "raw": raw_cycle.initial()}
    state["snapshots"][0] = active_snapshot(state)
    return state


def context(state):
    return digest({"genome": genome(state), "feeds": state["graph"]["feeds"],
                   "used": sorted(state["graph"]["used"]), "candidate": state["graph"]["candidate"],
                   "documents": [d["receipt"]["sha256"] for d in state["graph"]["documents"]],
                   "graph_attempts": sorted(state["graph"]["attempted"]),
                   "goals": {k: {"status": v["status"], "values": digest(v["values"])} for k, v in state["goals"].items()},
                   "experience": state["experience"], "legacy_attempts": state["legacy"]["attempts"],
                   "raw": digest(state["raw"])})


def legacy_proposal(state):
    # Replace the old independent autonomous scheduler with this shared scheduler.
    # Preserve its memory, genes, engine policy and native learning implementations.
    projection = {**state["legacy"], "autonomy": {**state["legacy"]["autonomy"], "enabled": False}}
    return expression.propose(projection)


def think(state):
    shared = context(state)
    raw = raw_cycle.choice(state["raw"])
    if raw is not None:
        waiting = raw["kind"] == "raw.wait"
        return {"context": shared, "choice": None if waiting else raw, "alternatives": [],
                "blocked": [raw] if waiting else [],
                "policy": "raw observations, measured deficit, induced program, reserved transfer, global regression"}
    graph, options, blocked = state["graph"], [], []
    if graph["candidate"]:
        if len({d["feed"]["origin"] for d in graph["fresh"]}) >= 2:
            options.append({"kind": "graph.assess", "priority": 120, "cost": 5, "cause": graph["candidate"]["freeze"]})
        elif graph_engine.next_request(graph) is not None:
            options.append({"kind": "graph.fetch", "priority": 110, "cost": 8, "cause": graph["candidate"]["freeze"]})
        else:
            blocked.append({"kind": "graph", "reason": "FRESH_SOURCE_POOL_EXHAUSTED", "freeze": graph["candidate"]["freeze"]})
    elif ("graph", shared) not in state["idle"]:
        if len({d["feed"]["origin"] for d in graph["documents"]}) >= 2:
            options.append({"kind": "graph.discover", "priority": 60, "cost": 4, "cause": "measured prediction deficits"})
        elif graph_engine.next_request(graph) is not None:
            options.append({"kind": "graph.fetch", "priority": 50, "cost": 8, "cause": "insufficient observations"})
    catalog = capabilities.catalog(state)
    for identity, goal in state["goals"].items():
        if goal["status"] != "READY":
            continue
        plan = planning.plan(catalog, goal["values"], goal["target"], state["experience"])
        if plan["status"] == "PLANNED":
            options.append({"kind": "goal.execute", "goal": identity, "priority": 80,
                            "cost": plan["cost"], "plan": plan, "cause": goal["origin"]})
        else:
            options.append({"kind": "goal.block", "goal": identity, "priority": 80,
                            "cost": 0, "plan": plan, "cause": "missing supported plan"})
    selection = expression.choose(state["legacy"])
    if selection and ("legacy", shared) not in state["idle"]:
        options.append({"kind": "legacy.develop", "priority": 40, "cost": 8, "cause": selection["task"]})
    options.sort(key=lambda item: (-item["priority"], item["cost"], item.get("goal", ""), item["kind"]))
    return {"context": shared, "choice": options[0] if options else None, "alternatives": options[1:],
            "blocked": blocked, "policy": "frozen evaluation first, requested plans, measured deficits, inherited learning",
            "intelligence": "plan costs include observed success and failure; pending fresh data remain reserved"}


def regression(state):
    active, memory, _ = expression.context(state["legacy"])
    jobs = [{"program": memory[pid], "rows": state["legacy"]["tasks"][name]["train"] + state["legacy"]["tasks"][name]["holdout"]}
            for name, pid in sorted(active.items())]
    tested = evaluate(jobs, memory)["results"]
    legacy = {"passed": sum(x["passed"] for x in tested), "total": sum(x["total"] for x in tested), "skills": len(jobs)}
    graph = {a["goal"]["law"]: evaluation.score(a["program"], a["rows"], state["graph"]["genes"])
             for a in state["graph"]["admitted"]}
    raw = raw_cycle.regression(state["raw"])
    return {"status": "PASS" if legacy["passed"] == legacy["total"] and all(v["passed"] == v["total"] for v in [*graph.values(), *raw.values()]) else "FAIL",
            "legacy": legacy, "graph": graph, "raw": raw, "isolation": "linux_seccomp_v1"}


def outcome(state, identity, inputs, captured=None):
    try:
        return {"status": "SUCCEEDED", "output": capabilities.invoke(state, identity, inputs, captured)}
    except (ValueError, TypeError, KeyError, OSError, TimeoutError) as exc:
        return {"status": "FAILED", "error": type(exc).__name__ + ": " + str(exc)}


class Kernel:
    def __init__(self, path, create=False):
        self.manifest = manifest()
        self.bootstrap = checkpoint.read(BOOTSTRAP)
        self.bootstrap_id = digest(self.bootstrap)
        self.cache = None
        self.journal = Journal(path, create=create)
        try:
            events, head = self.journal.read()
            if not events:
                if not create:
                    raise IntegrityError("unified genesis is missing")
                self.journal.append({"kind": "genesis", "manifest": self.manifest, "bootstrap": self.bootstrap_id,
                                     "parents": self.bootstrap["proof"]["parents"]}, head)
            self._load()
        except Exception:
            self.close()
            raise

    def _load(self, force=False):
        events, head = self.journal.read()
        genesis = {"kind": "genesis", "manifest": self.manifest, "bootstrap": self.bootstrap_id,
                   "parents": self.bootstrap["proof"]["parents"]}
        if not events or not same(events[0], genesis):
            raise IntegrityError("unified runtime/bootstrap mismatch; historical journals require their replay adapter")
        start, state = 1, None
        if self.cache and not force and len(events) >= self.cache[0]:
            count, old_head, cached = self.cache
            token = ZERO
            for i, event in enumerate(events[:count], 1):
                token = digest([i, token, event])
            if token == old_head:
                start, state = count, deepcopy(cached)
        if state is None:
            state = initial(self.bootstrap)
        for event in events[start:]:
            self._apply(state, event)
        self.cache = (len(events), head, deepcopy(state))
        return state, head, len(events)

    def _remember_execution(self, state, identity, inputs, result):
        counts = state["experience"].setdefault(identity, {"success": 0, "failure": 0})
        counts["success" if result["status"] == "SUCCEEDED" else "failure"] += 1
        state["executions"] += 1
        if identity == "source.fetch" and result["status"] == "SUCCEEDED":
            receipt = result["output"]
            if receipt["sha256"] not in {c["sha256"] for c in capabilities.captures(state)}:
                if state["graph"]["candidate"] is not None:
                    raise IntegrityError("unreserved observation during frozen candidate")
                state["captures"].append(receipt)
                try:
                    analysis = data.parse_source(receipt["text"], capabilities.module_name(receipt))
                except (ValueError, TypeError, RecursionError):
                    return
                state["graph"]["documents"].append({"feed": {"url": receipt["url"], "module": capabilities.module_name(receipt),
                                                            "origin": graph_engine.origin(receipt["url"])},
                                                      "receipt": receipt, "analysis": analysis})

    def _verify_outcome(self, state, identity, inputs, result):
        if identity == "source.fetch":
            if result["status"] == "SUCCEEDED":
                expected = outcome(state, identity, inputs, result["output"])
            else:
                # External transport failures are observations, not reproducible computation.
                if set(result) != {"status", "error"} or type(result["error"]) is not str or len(result["error"]) > 4096:
                    raise IntegrityError("invalid transport failure")
                expected = result
        else:
            expected = outcome(state, identity, inputs)
        if not same(expected, result):
            raise IntegrityError("capability result replay differs")

    def _promote(self, state, proof):
        actual = regression(state)
        if not same(proof, actual) or actual["status"] != "PASS":
            raise IntegrityError("unified cross-domain regression failed")
        parent = state["generation"]
        state["admissions"] += 1
        state["generation"] = state["admissions"]
        state["parents"][state["generation"]] = parent
        state["snapshots"][state["generation"]] = active_snapshot(state)

    def _apply(self, state, event):
        if type(event) is not dict or set(event) != {"kind", "body"}:
            raise IntegrityError("unified event envelope differs")
        kind, body = event["kind"], event["body"]
        if kind == "raw.feeds":
            if set(body) != {"urls"}:
                raise ContractError("raw feed fields differ")
            raw_cycle.connect(state["raw"], body["urls"])
        elif kind == "feeds":
            if set(body) != {"feeds"}:
                raise ContractError("feed event fields differ")
            added = graph_engine.initial(body["feeds"])["feeds"]
            existing = {f["url"] for f in state["graph"]["feeds"]}
            if len(existing) + len(added) > 256 or existing.intersection(f["url"] for f in added):
                raise ContractError("duplicate feed or lifetime feed budget")
            state["graph"]["feeds"].extend(added)
        elif kind == "goal":
            expected = self._goal(state, body["target"], body["inputs"])
            if not same(body, expected) or body["id"] in state["goals"] or len(state["goals"]) >= 128:
                raise IntegrityError("goal contract/identity differs")
            state["goals"][body["id"]] = {**body, "values": deepcopy(body["inputs"]), "status": "READY", "trace": []}
        elif kind == "invoke":
            self._verify_outcome(state, body["capability"], body["inputs"], body["result"])
            self._remember_execution(state, body["capability"], body["inputs"], body["result"])
        elif kind == "state.observe":
            graph_engine.Kernel._apply(None, state["graph"], {"kind": "state_observation", "body": body})
        elif kind == "tasks":
            tasks = [task_spec(t) for t in body]
            if not 1 <= len(tasks) <= 64:
                raise ContractError("task batch budget")
            known = state["legacy"]["tasks"]
            for task in tasks:
                if task["id"] in known:
                    raise ContractError("task already exists")
                reserved = [t for trial in state["legacy"]["engine_trials"].values() for t in trial["tasks"]]
                if input_tokens([task]) & input_tokens(reserved):
                    raise ContractError("task overlaps reserved validation")
                known[task["id"]] = task
                state["legacy"]["last_event"] += 1
                state["legacy"]["task_events"][task["id"]] = state["legacy"]["last_event"]
        elif kind == "study":
            item = capability.validate_knowledge(state["legacy"], body)
            state["legacy"]["knowledge"][item["id"]] = item
        elif kind == "engine_trial":
            trial = trial_spec(body)
            expression.validate_trial(state["legacy"], trial)
            identity = "@engine:" + trial["id"]
            state["legacy"]["engine_trials"][identity] = trial
            state["legacy"]["last_event"] += 1
            state["legacy"]["task_events"][identity] = state["legacy"]["last_event"]
        elif kind == "legacy.assess":
            frozen = state["legacy"]["capability_pending"][body["assessment"]["target"]]
            _, memory, _ = expression.context(state["legacy"])
            expected = capability.evaluate_frozen(state["legacy"], frozen, body["assessment"]["rows"], memory)
            if not same(body["assessment"], expected):
                raise IntegrityError("legacy fresh assessment differs")
            capability.apply_evaluation(state["legacy"], expected)
            if expected["status"] == "ADMITTED":
                self._promote(state, body["regression"])
        elif kind == "step":
            decision = think(state)
            if not same(body["decision"], decision) or decision["choice"] is None:
                raise IntegrityError("shared thinking/intelligence replay differs")
            choice, result = decision["choice"], body["result"]
            action = choice["kind"]
            if action.startswith("raw."):
                raw_cycle.apply(state["raw"], choice, result, capabilities.captures(state))
                if result["status"] == "ADMITTED":
                    self._promote(state, body["regression"])
            elif action == "graph.fetch":
                request = graph_engine.next_request(state["graph"])
                if not same(body["request"], request):
                    raise IntegrityError("shared source selection differs")
                if state["graph"]["pending"] is None:
                    graph_engine.Kernel._apply(None, state["graph"], {"kind": "request", "body": request})
                if result["status"] == "OBSERVED":
                    graph_engine.Kernel._apply(None, state["graph"], {"kind": "response", "body": result["receipt"]})
                elif result["status"] == "FETCH_FAILED":
                    graph_engine.Kernel._apply(None, state["graph"], {"kind": "fetch_failed", "body": {"request": request, "error": result["error"]}})
                else:
                    raise IntegrityError("unsupported network outcome")
            elif action == "graph.discover":
                expected = learning.propose(state["graph"])
                if not same(expected, result):
                    raise IntegrityError("graph goal/program replay differs")
                if result["status"] in ("IDLE", "WAITING"):
                    state["idle"].add(("graph", decision["context"]))
                else:
                    graph_engine.Kernel._apply(None, state["graph"], {"kind": "proposal", "body": result})
            elif action == "graph.assess":
                graph = state["graph"]
                expected = evaluation.assess(graph["candidate"], graph["fresh"], graph["genes"], graph["admitted"], graph["seen_inputs"])
                if not same(expected, result):
                    raise IntegrityError("graph assessment JSON/type identity differs")
                graph_engine.Kernel._apply(None, state["graph"], {"kind": "assessment", "body": result})
                if result["status"] == "ADMITTED":
                    self._promote(state, body["regression"])
            elif action in ("goal.execute", "goal.block"):
                goal = state["goals"][choice["goal"]]
                if action == "goal.block":
                    if not same(result, {"status": "BLOCKED", "reason": choice["plan"]["reason"]}):
                        raise IntegrityError("blocked plan evidence differs")
                    goal["status"] = "BLOCKED"
                elif not choice["plan"]["actions"]:
                    if not same(result, {"status": "SUCCEEDED", "output": goal["values"][goal["target"]]}):
                        raise IntegrityError("goal completion output differs")
                    goal["status"] = "COMPLETED"
                else:
                    identity = choice["plan"]["actions"][0]
                    descriptor = capabilities.catalog(state)[identity]
                    inputs = {k: goal["values"][v] for k, v in descriptor["inputs"].items()}
                    if body["capability"] != identity or not same(body["inputs"], inputs):
                        raise IntegrityError("planned action binding differs")
                    self._verify_outcome(state, identity, inputs, result)
                    self._remember_execution(state, identity, inputs, result)
                    if result["status"] == "SUCCEEDED":
                        goal["values"][descriptor["output"]] = result["output"]
                        if goal["target"] in goal["values"]:
                            goal["status"] = "COMPLETED"
                    else:
                        goal["status"] = "BLOCKED"
                goal["trace"].append({"context": decision["context"], "capability": body.get("capability"),
                                       "result": digest(result), "status": result["status"]})
            elif action == "legacy.develop":
                expected = legacy_proposal(state)
                if not same(result, expected):
                    raise IntegrityError("inherited learning replay differs")
                if result["status"] in ("IDLE", "WAITING"):
                    state["idle"].add(("legacy", decision["context"]))
                elif result["kind"] == "capability_freeze":
                    capability.apply_freeze(state["legacy"], result)
                elif result["kind"] == "step":
                    expression.apply_step(state["legacy"], result)
                    state["legacy"]["last_event"] = result["event"]
                    if result["status"] == "ADMITTED":
                        self._promote(state, body["regression"])
                else:
                    raise IntegrityError("unsupported inherited learning event")
            else:
                raise IntegrityError("unknown selected action")
            state["workspace"] = {"context": decision["context"], "thinking": choice,
                                  "logic": {"status": result["status"], "reason": result.get("reason"), "evidence": digest(result)},
                                  "intelligence": {"policy": decision["policy"], "cost": choice["cost"]}}
        elif kind == "rollback":
            target = body["generation"]
            parent, ancestors = state["parents"][state["generation"]], set()
            while parent is not None:
                ancestors.add(parent)
                parent = state["parents"][parent]
            if (type(target) is not int or target not in ancestors or state["graph"]["candidate"]
                    or state["graph"]["pending"] or state["legacy"]["capability_pending"] or state["raw"]["candidate"]):
                raise ContractError("rollback requires an idle strict active ancestor")
            snapshot = state["snapshots"][target]
            state["legacy"]["current"] = snapshot["legacy_generation"]
            state["graph"].update(generation=snapshot["graph_generation"], genes=deepcopy(snapshot["graph_genes"]),
                                   admitted=deepcopy(snapshot["graph_admitted"]))
            state["generation"] = target
            state["raw"]["active"] = list(snapshot["raw_active"])
            raw_cycle.materialize(state["raw"], state["raw"]["active"][-1] if state["raw"]["active"] else None)
            # Source exposure, execution experience and consumed fresh inputs remain remembered.
        else:
            raise IntegrityError("unknown unified event")

    def _append(self, kind, body):
        state, head, count = self._load()
        event = {"kind": kind, "body": deepcopy(body)}
        self._apply(state, event)
        new_head = self.journal.append(event, head)
        self.cache = (count + 1, new_head, deepcopy(state))
        return body

    def _goal(self, state, target, inputs):
        if (type(target) is not str or not target or len(target) > 160 or type(inputs) is not dict
                or not 1 <= len(inputs) <= 16 or any(type(k) is not str or len(k) > 160 for k in inputs)
                or len(encode(inputs).encode()) > 500_000):
            raise ContractError("goal/input contract")
        body = {"target": target, "inputs": deepcopy(inputs), "genome": genome(state), "origin": "operator goal; mechanism and plan selected by kernel"}
        return {**body, "id": digest(body)}

    def connect(self, feeds):
        return self._append("feeds", {"feeds": feeds})

    def sense(self, urls):
        """Attach opaque observations only; no task, reader or objective argument."""
        return self._append("raw.feeds", {"urls": urls})

    def recall(self, index):
        return raw_cycle.read(self._load()[0]["raw"], index)

    def goal(self, target, inputs):
        state, _, _ = self._load()
        body = self._goal(state, target, inputs)
        if body["id"] not in state["goals"]:
            self._append("goal", body)
        return body["id"]

    def invoke(self, identity, inputs):
        state, _, _ = self._load()
        result = outcome(state, identity, inputs)
        self._append("invoke", {"capability": identity, "inputs": inputs, "result": result})
        return result

    def step(self):
        state, _, _ = self._load()
        decision = think(state)
        choice = decision["choice"]
        if choice is None:
            return {"status": "WAITING" if decision["blocked"] else "IDLE", "decision": decision}
        kind = choice["kind"]
        body = {"decision": decision}
        if kind == "raw.fetch":
            try:
                receipt = raw_network.fetch(choice["url"])
                staged = deepcopy(state["raw"])
                raw_cycle.observe(staged, choice, receipt, capabilities.captures(state))
                result = {"status": "OBSERVED", "receipt": receipt}
            except (ValueError, OSError, TimeoutError, UnicodeError) as exc:
                result = {"status": "FETCH_FAILED", "error": type(exc).__name__ + ": " + str(exc)}
        elif kind == "raw.discover":
            result = raw_cycle.discover(state["raw"])
        elif kind == "raw.synthesize":
            result = raw_cycle.synthesize(state["raw"], capabilities.captures(state))
        elif kind == "raw.assess":
            result = raw_cycle.assess(state["raw"])
            if result["status"] == "ADMITTED":
                staged = deepcopy(state)
                raw_cycle.apply(staged["raw"], choice, result, capabilities.captures(staged))
                body["regression"] = regression(staged)
        elif kind == "graph.fetch":
            request = graph_engine.next_request(state["graph"])
            body["request"] = request
            try:
                receipt = network.fetch(request["feed"]["url"])
                staged = deepcopy(state["graph"])
                if staged["pending"] is None:
                    graph_engine.Kernel._apply(None, staged, {"kind": "request", "body": request})
                graph_engine.Kernel._apply(None, staged, {"kind": "response", "body": receipt})
                result = {"status": "OBSERVED", "receipt": receipt}
            except (ValueError, OSError, TimeoutError, UnicodeError) as exc:
                result = {"status": "FETCH_FAILED", "error": type(exc).__name__ + ": " + str(exc)}
        elif kind == "graph.discover":
            result = learning.propose(state["graph"])
        elif kind == "graph.assess":
            graph = state["graph"]
            result = evaluation.assess(graph["candidate"], graph["fresh"], graph["genes"], graph["admitted"], graph["seen_inputs"])
            if result["status"] == "ADMITTED":
                staged = deepcopy(state)
                graph_engine.Kernel._apply(None, staged["graph"], {"kind": "assessment", "body": result})
                body["regression"] = regression(staged)
        elif kind == "legacy.develop":
            result = legacy_proposal(state)
            if result["status"] == "ADMITTED":
                staged = deepcopy(state)
                expression.apply_step(staged["legacy"], result)
                body["regression"] = regression(staged)
        elif kind == "goal.block":
            result = {"status": "BLOCKED", "reason": choice["plan"]["reason"]}
        else:
            goal = state["goals"][choice["goal"]]
            if not choice["plan"]["actions"]:
                result = {"status": "SUCCEEDED", "output": goal["values"][goal["target"]]}
            else:
                identity = choice["plan"]["actions"][0]
                item = capabilities.catalog(state)[identity]
                inputs = {k: goal["values"][v] for k, v in item["inputs"].items()}
                body.update(capability=identity, inputs=inputs)
                result = outcome(state, identity, inputs)
        body["result"] = result
        self._append("step", body)
        return {"status": result["status"], "action": kind, "result": result, "decision": decision}

    def run(self, steps=16):
        if type(steps) is not int or not 1 <= steps <= 100:
            raise ContractError("step budget must be 1..100")
        results = []
        for _ in range(steps):
            item = self.step()
            results.append(item)
            if "action" not in item:
                break
        return results

    def observe_states(self, identity, stream):
        return self._append("state.observe", {"id": identity, "stream": stream})

    def register(self, tasks):
        return self._append("tasks", tasks)

    def study(self, specification):
        return self._append("study", specification)

    def engine_trial(self, trial):
        return self._append("engine_trial", trial)

    def assess(self, freeze, rows):
        state, _, _ = self._load()
        frozen = next((v for v in state["legacy"]["capability_pending"].values() if v["freeze"] == freeze), None)
        if frozen is None:
            raise ContractError("unknown inherited frozen candidate")
        _, memory, _ = expression.context(state["legacy"])
        result = capability.evaluate_frozen(state["legacy"], frozen, rows, memory)
        body = {"assessment": result}
        if result["status"] == "ADMITTED":
            staged = deepcopy(state)
            capability.apply_evaluation(staged["legacy"], result)
            body["regression"] = regression(staged)
        return self._append("legacy.assess", body)

    def status(self):
        state, head, count = self._load()
        active, _, _ = expression.context(state["legacy"])
        return {"name": "NOVA Unified", "version": "1.1.0", "head": head, "events": count,
                "generation": state["generation"], "genome": genome(state), "admissions_total": state["admissions"],
                "active_learned_skills": len(active) + len(state["graph"]["admitted"]) + len(state["raw"]["active"]),
                "legacy_skills": len(active), "graph_skills": [a["goal"]["law"] for a in state["graph"]["admitted"]],
                "catalog_entries": len(capabilities.catalog(state)), "executions": state["executions"],
                "goals": {k: v["status"] for k, v in state["goals"].items()},
                "pending_graph_candidate": state["graph"]["candidate"]["freeze"] if state["graph"]["candidate"] else None,
                "known_sources": len(capabilities.captures(state)), "source_failures": len(state["graph"]["failures"]),
                "workspace": state["workspace"], "raw": raw_cycle.summary(state["raw"]), "parent_lineages": self.bootstrap["proof"]["parents"],
                "runtime": digest(self.manifest), "claim": "integrated bounded cognition; digital consciousness is unproven"}

    def memory(self):
        state, _, _ = self._load()
        return {"catalog": capabilities.catalog(state), "experience": state["experience"],
                "goals": state["goals"], "workspace": state["workspace"],
                "sources": [{k: r[k] for k in ("url", "sha256", "bytes")} for r in capabilities.captures(state)],
                "legacy_knowledge": sorted(state["legacy"]["knowledge"]),
                "consumed_fresh_views": len(state["graph"]["seen_inputs"]), "raw": raw_cycle.summary(state["raw"])}

    def think(self):
        return think(self._load()[0])

    def result(self, identity):
        goal = self._load()[0]["goals"][identity]
        return {"status": goal["status"], "output": goal["values"].get(goal["target"]), "trace": goal["trace"]}

    def audit(self):
        state, _, _ = self._load(force=True)
        proof = regression(state)
        return {"status": proof["status"], "verification": "full unified semantic replay and all-domain regression",
                "regression": proof, "state": self.status()}

    def rollback(self, generation):
        self._append("rollback", {"generation": generation})
        return self.status()

    def export(self):
        self._load()
        events, head = self.journal.read()
        return {"schema": "nova.unified.journal.v1", "head": head, "events": events}

    @classmethod
    def restore(cls, exported, destination):
        destination = Path(destination)
        if (destination.exists() or set(exported) != {"schema", "head", "events"}
                or exported["schema"] != "nova.unified.journal.v1" or not 1 <= len(exported["events"]) <= 4096):
            raise ContractError("restore requires a bounded unified journal and a new destination")
        destination.parent.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory(dir=destination.parent) as folder:
            path = Path(folder) / "state.sqlite"
            journal, head = Journal(path, create=True), ZERO
            try:
                for event in exported["events"]:
                    head = journal.append(event, head)
                if head != exported["head"]:
                    raise IntegrityError("unified export head differs")
            finally:
                journal.close()
            with cls(path) as verified:
                status = verified.status()
                verified.journal.backup(destination)
            return {"status": "PASS", "state": status}

    def close(self):
        self.journal.close()

    def __enter__(self):
        return self

    def __exit__(self, *_):
        self.close()

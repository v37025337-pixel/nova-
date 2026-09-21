"""One event-driven successor runtime with native HTTPS and verified program admission."""

from copy import deepcopy
from datetime import datetime
import hashlib
from pathlib import Path
import sys
import tempfile
from urllib.parse import urlsplit

from nova_core.contracts import ContractError, IntegrityError, digest
from nova_core.memory import Journal, ZERO
from .data import parse_source
from . import evaluation, learning, network, seed_ucr

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_FEEDS = [
    {"url": "https://raw.githubusercontent.com/psf/requests/main/src/requests/sessions.py", "module": "requests.sessions"},
    {"url": "https://raw.githubusercontent.com/urllib3/urllib3/main/src/urllib3/connectionpool.py", "module": "urllib3.connectionpool"},
    {"url": "https://raw.githubusercontent.com/encode/httpx/master/httpx/_client.py", "module": "httpx.client"},
    {"url": "https://raw.githubusercontent.com/pallets/werkzeug/main/src/werkzeug/routing/map.py", "module": "werkzeug.routing.map"},
    {"url": "https://raw.githubusercontent.com/encode/starlette/main/starlette/routing.py", "module": "starlette.routing"},
    {"url": "https://raw.githubusercontent.com/aio-libs/aiohttp/master/aiohttp/client.py", "module": "aiohttp.client"},
    {"url": "https://raw.githubusercontent.com/pallets/flask/main/src/flask/app.py", "module": "flask.app"},
    {"url": "https://raw.githubusercontent.com/pallets/click/main/src/click/parser.py", "module": "click.parser"},
]


def origin(url):
    p = urlsplit(url)
    if p.hostname == "raw.githubusercontent.com":
        parts = p.path.strip("/").split("/")
        if len(parts) < 4:
            raise ContractError("raw repository source requires owner/repository/ref/path")
        return "github:" + "/".join(parts[:2]).lower()
    return p.hostname.lower()


def manifest():
    files = list((ROOT / "nova_next").glob("*.py")) + list((ROOT / "nova_core").glob("*.py"))
    files += [ROOT / "nova_next/inherited.json", ROOT / "nova_next/seed_blueprint.json"]
    return {"schema": "nova.next.runtime.v1", "python": list(sys.version_info[:2]),
            "source_sha256": {str(p.relative_to(ROOT)): hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(files)},
            "evolution": "bounded typed relational program synthesis with compiled sandbox execution",
            "oracle": "independently implemented graph specification; no UCR-generated target labels",
            "network": "public_https_source_capture", "autonomy": "maintainer query ontology; native deficit and program selection"}


def initial(feeds):
    if type(feeds) is not list or not 2 <= len(feeds) <= 32:
        raise ContractError("configure 2..32 public source feeds")
    normalized = []
    for f in feeds:
        if type(f) is not dict or set(f) != {"url", "module"}:
            raise ContractError("feed requires url and module, without tasks or answers")
        network.public_url(f["url"], resolve=False)
        if type(f["module"]) is not str or not f["module"] or len(f["module"]) > 100:
            raise ContractError("invalid module name")
        normalized.append({**f, "origin": origin(f["url"])})
    if len({f["url"] for f in normalized}) != len(normalized):
        raise ContractError("duplicate source feed")
    return {"feeds": normalized, "used": set(), "documents": [], "pending": None,
            "candidate": None, "fresh": [], "genes": {}, "admitted": [], "generation": 0,
            "admissions": 0, "attempted": set(), "seen_inputs": set(), "failures": [],
            "parents": {0: None}, "snapshots": {0: {"genes": {}, "admitted": []}}, "state_streams": {}}


def next_request(state):
    if state["pending"]:
        return state["pending"]
    for i, feed in enumerate(state["feeds"]):
        if i in state["used"]:
            continue
        if state["candidate"] and feed["origin"] in state["candidate"]["known_origins"]:
            continue
        return {"index": i, "feed": feed, "role": "fresh" if state["candidate"] else "observation",
                "freeze": state["candidate"]["freeze"] if state["candidate"] else None}
    return None


def validate_receipt(request, receipt):
    if receipt["url"] != request["feed"]["url"] or receipt["status"] != 200 or receipt["transport"] != "stdlib_https":
        raise ContractError("source response identity/status mismatch")
    network.public_url(receipt["final_url"], resolve=False)
    if origin(receipt["final_url"]) != request["feed"]["origin"]:
        raise ContractError("redirect changed source identity")
    raw = receipt["text"].encode("utf-8")
    if receipt["bytes"] != len(raw) or hashlib.sha256(raw).hexdigest() != receipt["sha256"]:
        raise ContractError("captured source hash/size mismatch")
    if datetime.fromisoformat(receipt["received_at"]).tzinfo is None:
        raise ContractError("source receipt needs timezone")
    return parse_source(receipt["text"], request["feed"]["module"])


class Kernel:
    def __init__(self, path, create=False, feeds=None):
        self.manifest = manifest()
        self.journal = Journal(path, create=create)
        self.cache = None
        try:
            events, head = self.journal.read()
            if not events:
                if not create:
                    raise IntegrityError("missing genesis")
                selected = DEFAULT_FEEDS if feeds is None else feeds
                initial(selected)
                self.journal.append({"kind": "genesis", "manifest": self.manifest, "feeds": selected,
                                     "inheritance": digest(evaluation.legacy_bundle())}, head)
            self._load()
        except Exception:
            self.close()
            raise

    def _apply(self, state, event):
        kind, body = event["kind"], event["body"]
        if kind == "request":
            if state["pending"] or body != next_request(state):
                raise IntegrityError("request was not selected by scheduler")
            state["pending"] = body
            state["used"].add(body["index"])
        elif kind == "response":
            request = state["pending"]
            if not request:
                raise IntegrityError("response without request")
            analysis = validate_receipt(request, body)
            if body["sha256"] in {d["receipt"]["sha256"] for d in state["documents"] + state["fresh"]}:
                raise IntegrityError("aliased or repeated source content")
            document = {"feed": request["feed"], "receipt": body, "analysis": analysis}
            state["fresh" if request["role"] == "fresh" else "documents"].append(document)
            state["pending"] = None
        elif kind == "fetch_failed":
            if not state["pending"] or body["request"] != state["pending"]:
                raise IntegrityError("failure without matching request")
            state["failures"].append(body)
            state["pending"] = None
        elif kind == "proposal":
            if state["pending"] or state["candidate"] or body != learning.propose(state):
                raise IntegrityError("goal/program synthesis replay mismatch")
            if body["status"] == "CANDIDATE_FROZEN":
                state["candidate"] = body
                state["fresh"] = []
            elif body["status"] == "WITHHOLD":
                state["attempted"].add(body["goal"]["deficit_id"])
            else:
                raise IntegrityError("idle result cannot masquerade as a proposal")
        elif kind == "assessment":
            candidate = state["candidate"]
            if not candidate or state["pending"]:
                raise IntegrityError("assessment without a frozen candidate")
            expected = evaluation.assess(candidate, state["fresh"], state["genes"], state["admitted"], state["seen_inputs"])
            if expected != body:
                raise IntegrityError("independent assessment replay mismatch")
            state["seen_inputs"].update(digest(r["graph"]) for r in body["rows"])
            state["attempted"].add(candidate["goal"]["deficit_id"])
            if body["status"] == "ADMITTED":
                previous = state["generation"]
                state["admissions"] += 1
                state["generation"] = state["admissions"]
                program = candidate["search"]["program"]
                state["genes"][program["id"]] = program
                state["admitted"].append({"goal": candidate["goal"], "program": program, "rows": body["rows"],
                                          "freeze": candidate["freeze"], "generation": state["generation"]})
                state["parents"][state["generation"]] = previous
                state["snapshots"][state["generation"]] = deepcopy({k: state[k] for k in ("genes", "admitted")})
            state["documents"].extend(state["fresh"])
            state["fresh"], state["candidate"] = [], None
        elif kind == "rollback":
            target = body["generation"]
            parent = state["parents"][state["generation"]]
            ancestors = set()
            while parent is not None:
                ancestors.add(parent)
                parent = state["parents"][parent]
            if type(target) is not int or target not in ancestors or state["candidate"] or state["pending"]:
                raise IntegrityError("rollback needs an idle strict active ancestor")
            state.update(deepcopy(state["snapshots"][target]))
            state["generation"] = target
        elif kind == "state_observation":
            key, stream = body["id"], seed_ucr._validate_state_stream(body["stream"])
            if not isinstance(key, str) or not key or len(key) > 100 or key in state["state_streams"]:
                raise IntegrityError("invalid/duplicate state stream")
            state["state_streams"][key] = stream
        else:
            raise IntegrityError("unknown successor event")

    def _load(self, force=False):
        events, head = self.journal.read()
        first = events[0]
        if (set(first) != {"kind", "manifest", "feeds", "inheritance"} or first["kind"] != "genesis"
                or first["manifest"] != self.manifest or first["inheritance"] != digest(evaluation.legacy_bundle())):
            raise IntegrityError("runtime or inheritance differs from genesis")
        state, start = initial(first["feeds"]), 1
        if not force and self.cache and len(events) >= self.cache[0]:
            count, old_head, cached = self.cache
            prefix = ZERO
            for i, event in enumerate(events[:count], 1):
                prefix = digest([i, prefix, event])
            if prefix == old_head:
                state, start = deepcopy(cached), count
        for event in events[start:]:
            if set(event) != {"kind", "body"}:
                raise IntegrityError("invalid successor event envelope")
            self._apply(state, event)
        self.cache = (len(events), head, deepcopy(state))
        return state, head, len(events)

    def _append(self, kind, body):
        state, head, count = self._load()
        event = {"kind": kind, "body": deepcopy(body)}
        self._apply(state, event)
        new_head = self.journal.append(event, head)
        self.cache = (count + 1, new_head, deepcopy(state))
        return body

    def step(self):
        state, _, _ = self._load()
        if state["candidate"]:
            if len({d["feed"]["origin"] for d in state["fresh"]}) >= 2:
                result = evaluation.assess(state["candidate"], state["fresh"], state["genes"], state["admitted"], state["seen_inputs"])
                return self._append("assessment", result)
        elif len({d["feed"]["origin"] for d in state["documents"]}) >= 2:
            proposal = learning.propose(state)
            if proposal["status"] in ("IDLE", "WAITING"):
                return proposal
            return self._append("proposal", proposal)
        request = next_request(state)
        if request is None:
            return {"status": "WAITING", "reason": "MORE_INDEPENDENT_SOURCE_FEEDS_REQUIRED"}
        if not state["pending"]:
            self._append("request", request)
        try:
            receipt = network.fetch(request["feed"]["url"])
            self._append("response", receipt)
        except (OSError, UnicodeError, ValueError, TimeoutError) as exc:
            failure = {"request": request, "error": type(exc).__name__ + ": " + str(exc)}
            self._append("fetch_failed", failure)
            return {"status": "FETCH_FAILED", **failure}
        return {"status": "OBSERVED", "role": request["role"], "url": receipt["url"],
                "sha256": receipt["sha256"], "bytes": receipt["bytes"]}

    def status(self):
        state, head, count = self._load()
        phase = "AWAITING_FRESH" if state["candidate"] else "DISCOVER"
        return {"name": "Nova Next", "version": "0.1.0", "head": head, "events": count,
                "generation": state["generation"], "admissions_total": state["admissions"],
                "genome": digest(state["genes"]), "phase": phase,
                "skills": [{"law": a["goal"]["law"], "program": a["program"]["id"]} for a in state["admitted"]],
                "inherited_nova_skills": len(evaluation.legacy_bundle()["bindings"]),
                "seed_primitives": len(seed_ucr.KERNEL_BLUEPRINT["primitives"]),
                "observed_documents": len(state["documents"]), "fresh_documents": len(state["fresh"]),
                "source_failures": len(state["failures"]), "state_streams": len(state["state_streams"]),
                "runtime": digest(self.manifest), "claim": "bounded verified successor; not unrestricted autonomous intelligence"}

    def predict(self, law, graph):
        from .data import validate_graph
        state, _, _ = self._load()
        item = next((a for a in state["admitted"] if a["goal"]["law"] == law), None)
        if not item:
            raise ContractError("query mechanism is not admitted")
        return evaluation.isolated(item["program"], [validate_graph(graph)], state["genes"])[0]

    def inherited_predict(self, name, inputs):
        from nova_core.language import execute as inherited_execute
        bundle = evaluation.legacy_bundle()
        if name not in bundle["bindings"]:
            raise ContractError("unknown inherited Nova skill")
        return inherited_execute(bundle["programs"][bundle["bindings"][name]], inputs, bundle["programs"])

    def observe_states(self, identity, stream):
        return self._append("state_observation", {"id": identity, "stream": stream})

    def predict_state(self, identity, action, before):
        state, _, _ = self._load()
        learned = seed_ucr._learn_state_prediction_models_v29(state["state_streams"][identity], {"affine_int", "mod_add_int"})
        after = seed_ucr._predict_with_models_v29(learned, action, before)
        return {"status": "PREDICTED" if after is not None else "AMBIGUOUS", "after": after,
                "origin": "inherited_UCR29_model_fitter", "independent_validation": "required", "new_admission": False}

    def rollback(self, generation):
        self._append("rollback", {"generation": generation})
        return self.status()

    def export(self):
        self._load()
        events, head = self.journal.read()
        return {"schema": "nova.next.journal.v1", "head": head, "events": events}

    def close(self):
        self.journal.close()

    def __enter__(self):
        return self

    def __exit__(self, *_):
        self.close()

    @classmethod
    def restore(cls, exported, destination):
        destination = Path(destination)
        if destination.exists() or set(exported) != {"schema", "head", "events"} or exported["schema"] != "nova.next.journal.v1":
            raise ContractError("restore requires an exact journal and a new destination")
        destination.parent.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory(dir=destination.parent) as temporary:
            path = Path(temporary) / "state.sqlite"
            journal = Journal(path, create=True)
            try:
                head = ZERO
                for event in exported["events"]:
                    head = journal.append(event, head)
                if head != exported["head"]:
                    raise IntegrityError("export head mismatch")
            finally:
                journal.close()
            with cls(path) as verified:
                status = verified.status()
                verified.journal.backup(destination)
            return {"status": "PASS", "verification": "full_semantic_replay", **status}

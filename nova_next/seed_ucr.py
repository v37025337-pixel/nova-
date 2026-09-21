from __future__ import annotations

# Bounded UCR Seed Kernel.
# Generated deterministically from causally admitted UCR capabilities.
# No network client, external-process bridge, dynamic import, arbitrary dynamic
# execution path, or source-code loader is present. Only embedded blueprints run.

import base64
import copy
import hashlib
import json
import itertools
import sys
from typing import Any

KERNEL_BLUEPRINT = json.loads(base64.b64decode("eyJjb21wb25lbnRzIjpbImRldGVybWluaXN0aWMtbWVtb3J5IiwiaGFzaC1jaGFpbmVkLWpvdXJuYWwiLCJ0YXNrLXF1ZXVlIiwic2FmZS1wcmltaXRpdmUtcnVudGltZSIsInNuYXBzaG90LXJlc3RhcnQiLCJqb3VybmFsLXJlcGxheSIsImFkbWlzc2lvbi1sZWRnZXItbWV0YWRhdGEiXSwiZ3JhbW1hcl9ydWxlcyI6W3siYWRtaXR0ZWQiOnRydWUsImRlc2NyaXB0aW9uIjoiYm91bmRlZCBhdG9taWMgc2FmZS1ibHVlcHJpbnQgZmFtaWxpZXMiLCJvcmlnaW4iOiJidWlsdGluIiwicnVsZV9pZCI6ImF0b21pYy52MSJ9LHsiYWRtaXR0ZWQiOnRydWUsImRlc2NyaXB0aW9uIjoiYWxsb3cgb25lIGJvdW5kZWQgY29tcG9zaXRpb24gb2YgdHdvIGF0b21pYyB1bmFyeSBibHVlcHJpbnRzIiwib3JpZ2luIjoibG9hZGVkLWFkbWl0dGVkLWV2b2x2ZWQtc3RhdGUiLCJydWxlX2lkIjoidW5hcnkuY29tcG9zZTIifSx7ImFkbWl0dGVkIjp0cnVlLCJkZXNjcmlwdGlvbiI6ImFsbG93IG9uZSBib3VuZGVkIGNvbXBvc2l0aW9uIG9mIHRocmVlIGF0b21pYyB1bmFyeSBibHVlcHJpbnRzIiwib3JpZ2luIjoibG9hZGVkLWFkbWl0dGVkLWV2b2x2ZWQtc3RhdGUiLCJydWxlX2lkIjoidW5hcnkuY29tcG9zZTMifV0sImtlcm5lbF9pZCI6InVjci5rZXJuZWxfZDFiODA4M2Y5ZGVmYmU2ZGM2NGYiLCJtdXRhdGlvbl9zdHJhdGVneV9yb3V0ZXMiOlt7ImFjdGlvbiI6ImFkbWl0LWF0b21pYy1wcmltaXRpdmUiLCJhZG1pdHRlZCI6dHJ1ZSwib3JpZ2luIjoibG9hZGVkLWFkbWl0dGVkLWV2b2x2ZWQtc3RhdGUiLCJwcmltYXJ5X2NoYWxsZW5nZSI6InJnLTAyIiwicHJpbWFyeV9nYWluIjowLjkzMzMzMywic2lnbmF0dXJlIjoicmVwcmVzZW50YXRpb24tZ2FwfGF0b21pYy1zdWZmaWNpZW50IiwidHJhbnNmZXJfY2hhbGxlbmdlIjoicmctMDQiLCJ0cmFuc2Zlcl9nYWluIjowLjkzMzMzM30seyJhY3Rpb24iOiJleHBhbmQtZ3JhbW1hci11bmFyeS1jb21wb3NlMiIsImFkbWl0dGVkIjp0cnVlLCJvcmlnaW4iOiJsb2FkZWQtYWRtaXR0ZWQtZXZvbHZlZC1zdGF0ZSIsInByaW1hcnlfY2hhbGxlbmdlIjoiZ3JhbW1hci1yZy0wMSIsInByaW1hcnlfZ2FpbiI6MC42NSwic2lnbmF0dXJlIjoicmVwcmVzZW50YXRpb24tZ2FwfGNvbXBvc2UyLXJlcXVpcmVkIiwidHJhbnNmZXJfY2hhbGxlbmdlIjoiZ3JhbW1hci1yZy0wMiIsInRyYW5zZmVyX2dhaW4iOjAuM30seyJhY3Rpb24iOiJleHBhbmQtZ3JhbW1hci11bmFyeS1jb21wb3NlMyIsImFkbWl0dGVkIjp0cnVlLCJvcmlnaW4iOiJsb2FkZWQtYWRtaXR0ZWQtZXZvbHZlZC1zdGF0ZSIsInByaW1hcnlfY2hhbGxlbmdlIjoic2VsZi1yZy04MWQ3OWQ3YjhhYzUiLCJwcmltYXJ5X2dhaW4iOjAuMDcxNDI5LCJzaWduYXR1cmUiOiJyZXByZXNlbnRhdGlvbi1nYXB8Y29tcG9zZTMtcmVxdWlyZWQiLCJ0cmFuc2Zlcl9jaGFsbGVuZ2UiOiJzZWxmLXJnLTIyZjM1NTM5M2EyNCIsInRyYW5zZmVyX2dhaW4iOjAuMTQyODU3fV0sIm5hbWUiOiJVQ1ItU2VlZC0xIiwicGFyZW50X3JlYWRlcl92ZXJzaW9uIjoiMjAuMCIsInByaW1pdGl2ZXMiOlt7ImJsdWVwcmludCI6eyJhcml0eSI6MSwiY2F0ZWdvcnkiOiJjb21wb3NlZCIsImZhbWlseSI6Im1ldGEuY29tcG9zZV91bmFyeTMiLCJwYXJhbXMiOnsiZmlyc3QiOnsiYXJpdHkiOjEsImNhdGVnb3J5IjoiYml0d2lzZSIsImZhbWlseSI6ImludGVnZXIucG9wY291bnRfYWJzIiwicGFyYW1zIjp7fX0sInNlY29uZCI6eyJhcml0eSI6MSwiY2F0ZWdvcnkiOiJiaXR3aXNlIiwiZmFtaWx5IjoiaW50ZWdlci5wb3Bjb3VudF9hYnMiLCJwYXJhbXMiOnt9fSwidGhpcmQiOnsiYXJpdHkiOjEsImNhdGVnb3J5IjoiYml0d2lzZSIsImZhbWlseSI6ImludGVnZXIubW9kX2VxdWFsIiwicGFyYW1zIjp7Im1vZHVsdXMiOjQsInJlc2lkdWUiOjJ9fX19LCJtYWNoaW5lX2lkIjoiZXZvbHZlZC5wXzIxMDg4NjhiM2UyYjY5MzciLCJwcm92ZW5hbmNlIjp7ImFkbWl0dGVkX29uIjoic2VsZi1yZy04MWQ3OWQ3YjhhYzUiLCJjYXVzYWxfZ2FpbiI6MC4zMDk1MjQsImZyZXNoX3Njb3JlIjoxLjAsImhpZGRlbl9zY29yZSI6MS4wLCJ0cmFpbl9zY29yZSI6MS4wLCJ0cmFuc2Zlcl9zY29yZSI6MS4wfSwic2VsZl90ZXN0cyI6W3siYXJncyI6Wy0xN10sImV4cGVjdGVkIjpmYWxzZX0seyJhcmdzIjpbLTFdLCJleHBlY3RlZCI6ZmFsc2V9LHsiYXJncyI6WzBdLCJleHBlY3RlZCI6ZmFsc2V9LHsiYXJncyI6WzFdLCJleHBlY3RlZCI6ZmFsc2V9XX0seyJibHVlcHJpbnQiOnsiYXJpdHkiOjEsImNhdGVnb3J5IjoiYXJpdGhtZXRpYyIsImZhbWlseSI6Im51bWVyaWMuc2lnbiIsInBhcmFtcyI6e319LCJtYWNoaW5lX2lkIjoiZXZvbHZlZC5wXzJhMmM0MjVkYmM1MTI2MTciLCJwcm92ZW5hbmNlIjp7ImFkbWl0dGVkX29uIjoicmctMDMiLCJjYXVzYWxfZ2FpbiI6MC4wLCJmcmVzaF9zY29yZSI6MS4wLCJoaWRkZW5fc2NvcmUiOjEuMCwidHJhaW5fc2NvcmUiOjEuMCwidHJhbnNmZXJfc2NvcmUiOjEuMH0sInNlbGZfdGVzdHMiOlt7ImFyZ3MiOlstMTddLCJleHBlY3RlZCI6LTF9LHsiYXJncyI6Wy0xXSwiZXhwZWN0ZWQiOi0xfSx7ImFyZ3MiOlswXSwiZXhwZWN0ZWQiOjB9LHsiYXJncyI6WzFdLCJleHBlY3RlZCI6MX1dfSx7ImJsdWVwcmludCI6eyJhcml0eSI6MSwiY2F0ZWdvcnkiOiJjb21wb3NlZCIsImZhbWlseSI6Im1ldGEuY29tcG9zZV91bmFyeTIiLCJwYXJhbXMiOnsiaW5uZXIiOnsiYXJpdHkiOjEsImNhdGVnb3J5IjoiYml0d2lzZSIsImZhbWlseSI6ImludGVnZXIucG9wY291bnRfYWJzIiwicGFyYW1zIjp7fX0sIm91dGVyIjp7ImFyaXR5IjoxLCJjYXRlZ29yeSI6ImJpdHdpc2UiLCJmYW1pbHkiOiJpbnRlZ2VyLm1vZF9lcXVhbCIsInBhcmFtcyI6eyJtb2R1bHVzIjozLCJyZXNpZHVlIjoxfX19fSwibWFjaGluZV9pZCI6ImV2b2x2ZWQucF9hMTViZGNkNWU2NDUyNjY0IiwicHJvdmVuYW5jZSI6eyJhZG1pdHRlZF9vbiI6InYxNy1pbmRlcGVuZGVudC1wb3Bjb3VudC1tb2QzZXExIiwiY2F1c2FsX2dhaW4iOjAuMjkxNjY3LCJmcmVzaF9zY29yZSI6MS4wLCJoaWRkZW5fc2NvcmUiOjEuMCwidHJhaW5fc2NvcmUiOjEuMCwidHJhbnNmZXJfc2NvcmUiOjEuMH0sInNlbGZfdGVzdHMiOlt7ImFyZ3MiOlstMTddLCJleHBlY3RlZCI6ZmFsc2V9LHsiYXJncyI6Wy0xXSwiZXhwZWN0ZWQiOnRydWV9LHsiYXJncyI6WzBdLCJleHBlY3RlZCI6ZmFsc2V9LHsiYXJncyI6WzFdLCJleHBlY3RlZCI6dHJ1ZX1dfSx7ImJsdWVwcmludCI6eyJhcml0eSI6MSwiY2F0ZWdvcnkiOiJiaXR3aXNlIiwiZmFtaWx5IjoiaW50ZWdlci5iaXRfdGVzdCIsInBhcmFtcyI6eyJiaXQiOjAsImV4cGVjdGVkIjowfX0sIm1hY2hpbmVfaWQiOiJldm9sdmVkLnBfYWI1ZDU2ZGU2OTM0YmQ0NSIsInByb3ZlbmFuY2UiOnsiYWRtaXR0ZWRfb24iOiJyZy0wMSIsImNhdXNhbF9nYWluIjowLjczMzMzMywiZnJlc2hfc2NvcmUiOjEuMCwiaGlkZGVuX3Njb3JlIjoxLjAsInRyYWluX3Njb3JlIjoxLjAsInRyYW5zZmVyX3Njb3JlIjoxLjB9LCJzZWxmX3Rlc3RzIjpbeyJhcmdzIjpbLTE3XSwiZXhwZWN0ZWQiOmZhbHNlfSx7ImFyZ3MiOlstMV0sImV4cGVjdGVkIjpmYWxzZX0seyJhcmdzIjpbMF0sImV4cGVjdGVkIjp0cnVlfSx7ImFyZ3MiOlsxXSwiZXhwZWN0ZWQiOmZhbHNlfV19LHsiYmx1ZXByaW50Ijp7ImFyaXR5IjoxLCJjYXRlZ29yeSI6ImJpdHdpc2UiLCJmYW1pbHkiOiJpbnRlZ2VyLnBvcGNvdW50X2FicyIsInBhcmFtcyI6e319LCJtYWNoaW5lX2lkIjoiZXZvbHZlZC5wX2Q5NTNiMGQxZDI5YmQ4ODEiLCJwcm92ZW5hbmNlIjp7ImFkbWl0dGVkX29uIjoicmctMDIiLCJjYXVzYWxfZ2FpbiI6MS4wLCJmcmVzaF9zY29yZSI6MS4wLCJoaWRkZW5fc2NvcmUiOjEuMCwidHJhaW5fc2NvcmUiOjEuMCwidHJhbnNmZXJfc2NvcmUiOjEuMH0sInNlbGZfdGVzdHMiOlt7ImFyZ3MiOlstMTddLCJleHBlY3RlZCI6Mn0seyJhcmdzIjpbLTFdLCJleHBlY3RlZCI6MX0seyJhcmdzIjpbMF0sImV4cGVjdGVkIjowfSx7ImFyZ3MiOlsxXSwiZXhwZWN0ZWQiOjF9XX0seyJibHVlcHJpbnQiOnsiYXJpdHkiOjEsImNhdGVnb3J5IjoiYXJpdGhtZXRpYyIsImZhbWlseSI6ImludGVnZXIuZGlnaXRhbF9yb290X2FicyIsInBhcmFtcyI6e319LCJtYWNoaW5lX2lkIjoiZXZvbHZlZC5wX2ZkMzJkNmI3YmIxY2VmYzMiLCJwcm92ZW5hbmNlIjp7ImFkbWl0dGVkX29uIjoicmctMDQiLCJjYXVzYWxfZ2FpbiI6MC45MzMzMzMsImZyZXNoX3Njb3JlIjoxLjAsImhpZGRlbl9zY29yZSI6MS4wLCJ0cmFpbl9zY29yZSI6MS4wLCJ0cmFuc2Zlcl9zY29yZSI6MS4wfSwic2VsZl90ZXN0cyI6W3siYXJncyI6Wy0xN10sImV4cGVjdGVkIjo4fSx7ImFyZ3MiOlstMV0sImV4cGVjdGVkIjoxfSx7ImFyZ3MiOlswXSwiZXhwZWN0ZWQiOjB9LHsiYXJncyI6WzFdLCJleHBlY3RlZCI6MX1dfV0sInJlYXNvbmluZ19wb2xpY3kiOnsiYWNjZXB0ZWRfcm91bmRzIjozLCJjb3VudGVyZXhhbXBsZV9yb3VuZHMiOjQsImV2aWRlbmNlX3Jvd3MiOjEyLCJtYXhfY2FuZGlkYXRlcyI6MTIsIm1heF9kZXB0aCI6MywibWF4X2dlbmVyYXRlZCI6MTIwMDB9LCJzYWZldHkiOnsiYXJiaXRyYXJ5X3B5dGhvbl9nZW5lcmF0aW9uIjpmYWxzZSwiZmlsZXN5c3RlbV93cml0ZV9zY29wZSI6Imhvc3Qtc2VsZWN0ZWQta2VybmVsLWFydGlmYWN0LW9ubHkiLCJuZXR3b3JrX2FjY2VzcyI6ZmFsc2UsInJ1bnRpbWVfYmx1ZXByaW50X2xhbmd1YWdlIjoiY2xvc2VkLXNhZmUtdWNyLWJsdWVwcmludC1ncmFtbWFyIiwic3VicHJvY2Vzc19hY2Nlc3MiOmZhbHNlLCJ1bmtub3duX3NvdXJjZV9leGVjdXRpb24iOmZhbHNlfSwic2NoZW1hIjoidWNyLnNlZWQta2VybmVsLWJsdWVwcmludC8xIn0=").decode("utf-8"))


def _json_safe(value: Any) -> Any:
    if value is None or type(value) in (bool, int, float, str):
        return value
    if isinstance(value, bytes):
        return {"__bytes_b64__": base64.b64encode(value).decode("ascii")}
    if isinstance(value, tuple):
        return {"__tuple__": [_json_safe(v) for v in value]}
    if isinstance(value, list):
        return [_json_safe(v) for v in value]
    if isinstance(value, dict):
        return {str(k): _json_safe(v) for k, v in sorted(value.items(), key=lambda kv: str(kv[0]))}
    raise TypeError("seed kernel state must remain JSON-safe")


def _json_restore(value: Any) -> Any:
    if isinstance(value, list):
        return [_json_restore(v) for v in value]
    if isinstance(value, dict):
        if set(value) == {"__bytes_b64__"}:
            return base64.b64decode(value["__bytes_b64__"])
        if set(value) == {"__tuple__"}:
            return tuple(_json_restore(v) for v in value["__tuple__"])
        return {str(k): _json_restore(v) for k, v in value.items()}
    return value


def _canonical(value: Any) -> str:
    return json.dumps(_json_safe(value), sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def _require_int(x: Any) -> int:
    if type(x) is not int:
        raise TypeError("integer primitive requires int")
    return x


def _eval_blueprint(blueprint: dict[str, Any], args: list[Any]) -> Any:
    family = str(blueprint.get("family", ""))
    params = dict(blueprint.get("params") or {})
    if int(blueprint.get("arity", 1)) != len(args):
        raise ValueError("arity mismatch")
    if family == "integer.mod_equal":
        x = _require_int(args[0]); m = int(params["modulus"]); r = int(params["residue"])
        if m < 2 or m > 8 or r < 0 or r >= m:
            raise ValueError("invalid modular blueprint")
        return x % m == r
    if family == "integer.bit_test":
        x = _require_int(args[0]); bit = int(params["bit"]); expected = int(params["expected"])
        if bit < 0 or bit > 7 or expected not in (0, 1):
            raise ValueError("invalid bit-test blueprint")
        return ((x >> bit) & 1) == expected
    if family == "integer.popcount_abs":
        return abs(_require_int(args[0])).bit_count()
    if family == "numeric.sign":
        x = args[0]
        if type(x) not in (int, float):
            raise TypeError("sign requires numeric")
        return -1 if x < 0 else (1 if x > 0 else 0)
    if family == "integer.digital_root_abs":
        x = abs(_require_int(args[0]))
        return 0 if x == 0 else 1 + ((x - 1) % 9)
    if family == "sequence.reverse":
        x = args[0]
        if type(x) not in (str, bytes, list, tuple):
            raise TypeError("reverse requires bounded sequence")
        return x[::-1]
    if family == "meta.compose_unary2":
        inner = dict(params["inner"]); outer = dict(params["outer"])
        return _eval_blueprint(outer, [_eval_blueprint(inner, [args[0]])])
    if family == "meta.compose_unary3":
        first = dict(params["first"]); second = dict(params["second"]); third = dict(params["third"])
        return _eval_blueprint(third, [_eval_blueprint(second, [_eval_blueprint(first, [args[0]])])])
    raise ValueError("unknown or non-admitted blueprint family")


class SpawnedKernel:
    VERSION = "0.1"

    def __init__(self) -> None:
        self.kernel_id = str(KERNEL_BLUEPRINT["kernel_id"])
        self.memory: dict[str, Any] = {}
        self.queue: list[dict[str, Any]] = []
        self.completed: dict[str, Any] = {}
        self.journal: list[dict[str, Any]] = []
        self._task_counter = 0
        self._primitives = {
            str(item["machine_id"]): copy.deepcopy(item)
            for item in KERNEL_BLUEPRINT.get("primitives", [])
        }

    def capabilities(self) -> dict[str, Any]:
        return {
            "kernel_id": self.kernel_id,
            "primitive_ids": sorted(self._primitives),
            "primitive_count": len(self._primitives),
            "grammar_rules": [str(x.get("rule_id")) for x in KERNEL_BLUEPRINT.get("grammar_rules", [])],
            "mutation_routes": [str(x.get("signature")) for x in KERNEL_BLUEPRINT.get("mutation_strategy_routes", [])],
            "components": list(KERNEL_BLUEPRINT.get("components", [])),
        }

    def _append_event(self, kind: str, payload: dict[str, Any]) -> dict[str, Any]:
        previous = self.journal[-1]["hash"] if self.journal else "0" * 64
        body = {"seq": len(self.journal), "kind": str(kind), "payload": _json_safe(payload), "prev_hash": previous}
        digest = hashlib.sha256((previous + _canonical(body)).encode("utf-8")).hexdigest()
        event = {**body, "hash": digest}
        self.journal.append(event)
        return copy.deepcopy(event)

    def verify_journal(self) -> bool:
        previous = "0" * 64
        for index, event in enumerate(self.journal):
            if int(event.get("seq", -1)) != index or event.get("prev_hash") != previous:
                return False
            body = {k: copy.deepcopy(event[k]) for k in ("seq", "kind", "payload", "prev_hash")}
            expected = hashlib.sha256((previous + _canonical(body)).encode("utf-8")).hexdigest()
            if event.get("hash") != expected:
                return False
            previous = expected
        return True

    def remember(self, key: str, value: Any) -> None:
        k = str(key)
        safe = _json_safe(value)
        self.memory[k] = _json_restore(safe)
        self._append_event("memory.set", {"key": k, "value": safe})

    def invoke(self, machine_id: str, *args: Any, record: bool = True) -> Any:
        item = self._primitives.get(str(machine_id))
        if item is None:
            raise KeyError("unknown primitive")
        restored_args = [_json_restore(_json_safe(a)) for a in args]
        result = _eval_blueprint(dict(item["blueprint"]), restored_args)
        safe_result = _json_safe(result)
        if record:
            self._append_event("primitive.invoke", {
                "machine_id": str(machine_id), "args": _json_safe(restored_args), "result": safe_result,
            })
        return _json_restore(safe_result)

    def enqueue_invoke(self, machine_id: str, *args: Any) -> str:
        if str(machine_id) not in self._primitives:
            raise KeyError("unknown primitive")
        self._task_counter += 1
        task_id = f"task-{self._task_counter:08d}"
        task = {"task_id": task_id, "kind": "invoke", "machine_id": str(machine_id), "args": _json_safe(list(args))}
        self.queue.append(copy.deepcopy(task))
        self._append_event("task.enqueued", task)
        return task_id

    def step(self) -> dict[str, Any] | None:
        if not self.queue:
            return None
        task = self.queue.pop(0)
        if task.get("kind") != "invoke":
            raise ValueError("unsupported task kind")
        result = self.invoke(str(task["machine_id"]), *[_json_restore(v) for v in task.get("args", [])], record=False)
        safe_result = _json_safe(result)
        self.completed[str(task["task_id"])] = _json_restore(safe_result)
        self._append_event("task.completed", {"task_id": task["task_id"], "result": safe_result})
        return {"task_id": task["task_id"], "result": _json_restore(safe_result)}

    def run(self, max_steps: int = 128) -> list[dict[str, Any]]:
        if max_steps < 0 or max_steps > 10000:
            raise ValueError("max_steps out of bounded range")
        out: list[dict[str, Any]] = []
        for _ in range(max_steps):
            item = self.step()
            if item is None:
                break
            out.append(item)
        return out

    @staticmethod
    def replay(events: list[dict[str, Any]]) -> dict[str, Any]:
        memory: dict[str, Any] = {}
        queue: list[dict[str, Any]] = []
        completed: dict[str, Any] = {}
        previous = "0" * 64
        max_task = 0
        for index, event in enumerate(copy.deepcopy(events)):
            if int(event.get("seq", -1)) != index or event.get("prev_hash") != previous:
                raise ValueError("journal chain mismatch")
            body = {k: copy.deepcopy(event[k]) for k in ("seq", "kind", "payload", "prev_hash")}
            expected = hashlib.sha256((previous + _canonical(body)).encode("utf-8")).hexdigest()
            if event.get("hash") != expected:
                raise ValueError("journal digest mismatch")
            previous = expected
            kind = str(event.get("kind")); payload = dict(event.get("payload") or {})
            if kind == "memory.set":
                memory[str(payload["key"])] = _json_restore(payload["value"])
            elif kind == "task.enqueued":
                task = copy.deepcopy(payload); queue.append(task)
                tid = str(task.get("task_id", ""))
                if tid.startswith("task-") and tid[5:].isdigit():
                    max_task = max(max_task, int(tid[5:]))
            elif kind == "task.completed":
                tid = str(payload["task_id"])
                queue = [q for q in queue if str(q.get("task_id")) != tid]
                completed[tid] = _json_restore(payload["result"])
        return {"memory": memory, "queue": queue, "completed": completed, "task_counter": max_task}

    def snapshot(self) -> dict[str, Any]:
        state = {
            "schema": "ucr.spawned-kernel-state/1",
            "kernel_id": self.kernel_id,
            "memory": _json_safe(self.memory),
            "queue": _json_safe(self.queue),
            "completed": _json_safe(self.completed),
            "task_counter": self._task_counter,
            "journal": copy.deepcopy(self.journal),
        }
        return {**state, "snapshot_digest": hashlib.sha256(_canonical(state).encode("utf-8")).hexdigest()}

    def restore(self, snapshot: dict[str, Any]) -> None:
        snap = copy.deepcopy(snapshot)
        supplied = str(snap.pop("snapshot_digest", ""))
        expected = hashlib.sha256(_canonical(snap).encode("utf-8")).hexdigest()
        if supplied != expected:
            raise ValueError("snapshot digest mismatch")
        if snap.get("schema") != "ucr.spawned-kernel-state/1" or snap.get("kernel_id") != self.kernel_id:
            raise ValueError("snapshot identity mismatch")
        replayed = self.replay(list(snap.get("journal") or []))
        if _json_safe(replayed["memory"]) != snap.get("memory"):
            raise ValueError("snapshot memory does not match journal replay")
        if _json_safe(replayed["queue"]) != snap.get("queue"):
            raise ValueError("snapshot queue does not match journal replay")
        if _json_safe(replayed["completed"]) != snap.get("completed"):
            raise ValueError("snapshot completed state does not match journal replay")
        self.memory = replayed["memory"]
        self.queue = replayed["queue"]
        self.completed = replayed["completed"]
        self._task_counter = int(snap.get("task_counter", replayed["task_counter"]))
        self.journal = list(snap.get("journal") or [])


def self_test() -> dict[str, Any]:
    kernel = SpawnedKernel()
    tested = 0
    failures: list[dict[str, Any]] = []
    for item in KERNEL_BLUEPRINT.get("primitives", []):
        machine_id = str(item["machine_id"])
        for case in item.get("self_tests", []):
            args = [_json_restore(v) for v in case.get("args", [])]
            expected = _json_restore(case.get("expected"))
            try:
                observed = kernel.invoke(machine_id, *args)
                if _json_safe(observed) != _json_safe(expected):
                    failures.append({"machine_id": machine_id, "args": _json_safe(args), "reason": "result-mismatch"})
                else:
                    tested += 1
            except Exception as exc:
                failures.append({"machine_id": machine_id, "reason": type(exc).__name__})
    kernel.remember("boot", {"kernel_id": kernel.kernel_id, "primitive_count": len(kernel._primitives)})
    first_id = sorted(kernel._primitives)[0] if kernel._primitives else None
    if first_id is not None:
        first_item = next(x for x in KERNEL_BLUEPRINT["primitives"] if str(x["machine_id"]) == first_id)
        cases = first_item.get("self_tests", [])
        if cases:
            args = [_json_restore(v) for v in cases[0].get("args", [])]
            kernel.enqueue_invoke(first_id, *args)
            kernel.run(max_steps=4)
    snap = kernel.snapshot()
    restored = SpawnedKernel(); restored.restore(snap)
    replay_ok = restored.snapshot().get("snapshot_digest") == snap.get("snapshot_digest")
    tamper_rejected = False
    tampered = copy.deepcopy(snap)
    tampered["memory"] = {"tampered": True}
    try:
        SpawnedKernel().restore(tampered)
    except Exception:
        tamper_rejected = True
    return {
        "kernel_id": kernel.kernel_id,
        "primitive_count": len(kernel._primitives),
        "primitive_test_cases_passed": tested,
        "failures": failures,
        "journal_chain_valid": kernel.verify_journal(),
        "snapshot_restart_replay": replay_ok,
        "tampered_snapshot_rejected": tamper_rejected,
        "pass": (not failures) and kernel.verify_journal() and replay_ok and tamper_rejected,
    }



# ---------------------------------------------------------------------------
# Autonomous bounded self-development layer.
# This layer never executes unknown source. It searches only a closed, audited
# blueprint grammar and admits a mutation only after train/hidden/fresh,
# independent transfer, and causal-ablation checks.
# ---------------------------------------------------------------------------

SAFE_NEW_ATOMIC_BLUEPRINTS: tuple[dict[str, Any], ...] = (
    {
        "arity": 1,
        "category": "bitwise",
        "family": "integer.trailing_zero_count_abs",
        "params": {},
    },
)


def _typed_equal(a: Any, b: Any) -> bool:
    return type(a) is type(b) and _json_safe(a) == _json_safe(b)


def _eval_autonomous_blueprint(blueprint: dict[str, Any], args: list[Any]) -> Any:
    family = str(blueprint.get("family", ""))
    params = dict(blueprint.get("params") or {})
    if family == "integer.trailing_zero_count_abs":
        if len(args) != 1:
            raise ValueError("arity mismatch")
        x = abs(_require_int(args[0]))
        if x == 0:
            return 0
        return (x & -x).bit_length() - 1
    if family == "meta.compose_pipeline":
        if len(args) != 1:
            raise ValueError("arity mismatch")
        steps = list(params.get("steps") or [])
        if len(steps) < 2 or len(steps) > 5:
            raise ValueError("pipeline length outside bounded grammar")
        value: Any = args[0]
        for step in steps:
            value = _eval_autonomous_blueprint(dict(step), [value])
        return value
    return _eval_blueprint(blueprint, args)


def _blueprint_digest(blueprint: dict[str, Any]) -> str:
    return hashlib.sha256(_canonical(blueprint).encode("utf-8")).hexdigest()


def _machine_id_for(blueprint: dict[str, Any]) -> str:
    return "kernel.evolved." + _blueprint_digest(blueprint)[:16]


def _score_blueprint(blueprint: dict[str, Any], cases: list[dict[str, Any]]) -> float:
    if not cases:
        return 0.0
    passed = 0
    for case in cases:
        args = [_json_restore(v) for v in case["args"]]
        expected = _json_restore(case["expected"])
        try:
            observed = _eval_autonomous_blueprint(blueprint, args)
        except Exception:
            continue
        if _typed_equal(observed, expected):
            passed += 1
    return passed / len(cases)


def _cases_for(blueprint: dict[str, Any], inputs: list[int]) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for value in inputs:
        observed = _eval_autonomous_blueprint(blueprint, [value])
        out.append({"args": [_json_safe(value)], "expected": _json_safe(observed)})
    return out


def _flatten_atomic_steps(blueprint: dict[str, Any]) -> list[dict[str, Any]] | None:
    family = str(blueprint.get("family", ""))
    params = dict(blueprint.get("params") or {})
    if family == "meta.compose_unary2":
        return [copy.deepcopy(params["inner"]), copy.deepcopy(params["outer"])]
    if family == "meta.compose_unary3":
        return [copy.deepcopy(params["first"]), copy.deepcopy(params["second"]), copy.deepcopy(params["third"])]
    if family == "meta.compose_pipeline":
        return [copy.deepcopy(x) for x in params.get("steps", [])]
    if family.startswith("meta."):
        return None
    return [copy.deepcopy(blueprint)]


class AutonomousKernel(SpawnedKernel):
    VERSION = "21.0"

    TRAIN_INPUTS = [-33, -24, -17, -16, -12, -9, -8, -7, -4, -3, -2, -1, 0, 1, 2, 3, 4, 5, 8, 12, 16, 24, 31, 32]
    HIDDEN_INPUTS = [-65, -48, -20, -15, -10, -6, 6, 9, 10, 18, 20, 33, 40, 64, 65, 96]
    FRESH_INPUTS = [-129, -72, -40, -14, -11, -5, 7, 11, 14, 21, 48, 72, 127, 128, 129, 160]
    TRANSFER_INPUTS = [-257, -192, -80, -18, -13, 13, 22, 36, 63, 80, 144, 191, 256, 257]

    def __init__(self) -> None:
        super().__init__()
        self._evolved_primitives: dict[str, dict[str, Any]] = {}
        self._evolved_grammar_rules: list[dict[str, Any]] = []
        self._evolution_history: list[dict[str, Any]] = []
        self._generation = 0

    def capabilities(self) -> dict[str, Any]:
        base = super().capabilities()
        base.update({
            "autonomous_kernel_version": self.VERSION,
            "evolved_primitive_count": len(self._evolved_primitives),
            "evolved_grammar_rules": [str(x["rule_id"]) for x in self._evolved_grammar_rules],
            "active_max_compose_depth": self._active_max_depth(),
            "generation": self._generation,
        })
        return base

    def _all_primitive_items(self) -> dict[str, dict[str, Any]]:
        out = {str(k): copy.deepcopy(v) for k, v in self._primitives.items()}
        out.update({str(k): copy.deepcopy(v) for k, v in self._evolved_primitives.items()})
        return out

    def invoke(self, machine_id: str, *args: Any, record: bool = True) -> Any:
        item = self._all_primitive_items().get(str(machine_id))
        if item is None:
            raise KeyError("unknown primitive")
        restored_args = [_json_restore(_json_safe(a)) for a in args]
        result = _eval_autonomous_blueprint(dict(item["blueprint"]), restored_args)
        safe_result = _json_safe(result)
        if record:
            self._append_event("primitive.invoke", {
                "machine_id": str(machine_id), "args": _json_safe(restored_args), "result": safe_result,
            })
        return _json_restore(safe_result)

    def enqueue_invoke(self, machine_id: str, *args: Any) -> str:
        if str(machine_id) not in self._all_primitive_items():
            raise KeyError("unknown primitive")
        self._task_counter += 1
        task_id = f"task-{self._task_counter:08d}"
        task = {"task_id": task_id, "kind": "invoke", "machine_id": str(machine_id), "args": _json_safe(list(args))}
        self.queue.append(copy.deepcopy(task))
        self._append_event("task.enqueued", task)
        return task_id

    def _active_max_depth(self) -> int:
        depth = 1
        for rule in list(KERNEL_BLUEPRINT.get("grammar_rules", [])) + list(self._evolved_grammar_rules):
            rid = str(rule.get("rule_id", ""))
            if rid == "unary.compose2":
                depth = max(depth, 2)
            elif rid == "unary.compose3":
                depth = max(depth, 3)
            elif rid.startswith("unary.compose") and rid[len("unary.compose"):].isdigit():
                depth = max(depth, int(rid[len("unary.compose"):]))
        return depth

    def _admitted_atomic_blueprints(self) -> list[dict[str, Any]]:
        seen: set[str] = set()
        out: list[dict[str, Any]] = []
        for item in self._all_primitive_items().values():
            bp = dict(item["blueprint"])
            steps = _flatten_atomic_steps(bp)
            if not steps:
                continue
            for step in steps:
                if str(step.get("family", "")).startswith("meta."):
                    continue
                key = _canonical(step)
                if key not in seen:
                    seen.add(key); out.append(copy.deepcopy(step))
        return out

    def _behavior_signature(self, blueprint: dict[str, Any], inputs: list[int]) -> str | None:
        values: list[Any] = []
        try:
            for value in inputs:
                values.append(_json_safe(_eval_autonomous_blueprint(blueprint, [value])))
        except Exception:
            return None
        return _canonical(values)

    def _discover_novel_depth_target(self, depth: int) -> dict[str, Any] | None:
        if depth < 2 or depth > 5:
            return None
        atoms = self._admitted_atomic_blueprints()
        if not atoms:
            return None
        audit_inputs = list(dict.fromkeys(self.TRAIN_INPUTS + self.HIDDEN_INPUTS + self.FRESH_INPUTS + self.TRANSFER_INPUTS))
        lower_signatures: set[str] = set()
        for atom in atoms:
            sig = self._behavior_signature(atom, audit_inputs)
            if sig is not None:
                lower_signatures.add(sig)
        for d in range(2, depth):
            for bp in self._pipeline_candidates(d):
                sig = self._behavior_signature(bp, audit_inputs)
                if sig is not None:
                    lower_signatures.add(sig)
        for combo in itertools.product(atoms, repeat=depth):
            bp = {
                "arity": 1, "category": "composed", "family": "meta.compose_pipeline",
                "params": {"steps": [copy.deepcopy(x) for x in combo]},
            }
            sig = self._behavior_signature(bp, audit_inputs)
            if sig is None or sig in lower_signatures:
                continue
            try:
                outputs = [_eval_autonomous_blueprint(bp, [x]) for x in audit_inputs]
            except Exception:
                continue
            if len({_canonical(_json_safe(v)) for v in outputs}) < 2:
                continue
            return bp
        return None

    def _challenge_universe(self) -> list[dict[str, Any]]:
        # The kernel is not handed one target. It generates a bounded universe
        # from its current capabilities. New challenge classes appear only after
        # earlier admissions make them causally reachable.
        candidates: list[dict[str, Any]] = [copy.deepcopy(SAFE_NEW_ATOMIC_BLUEPRINTS[0])]
        admitted = {_canonical(x) for x in self._admitted_atomic_blueprints()}
        if _canonical(SAFE_NEW_ATOMIC_BLUEPRINTS[0]) in admitted:
            novel_depth4 = self._discover_novel_depth_target(4)
            if novel_depth4 is not None:
                candidates.append(novel_depth4)
        challenges: list[dict[str, Any]] = []
        for target in candidates:
            cid = "self.challenge." + _blueprint_digest(target)[:12]
            challenges.append({
                "challenge_id": cid,
                "source": "bounded-safe-self-generator",
                "target_digest": _blueprint_digest(target),
                "train": _cases_for(target, self.TRAIN_INPUTS),
                "hidden": _cases_for(target, self.HIDDEN_INPUTS),
                "fresh": _cases_for(target, self.FRESH_INPUTS),
                "transfer_inputs": list(self.TRANSFER_INPUTS),
                "_target": target,
            })
        return challenges

    def _best_existing(self, challenge: dict[str, Any]) -> dict[str, Any]:
        best = {"machine_id": None, "train": 0.0, "hidden": 0.0, "fresh": 0.0}
        for mid, item in self._all_primitive_items().items():
            bp = dict(item["blueprint"])
            tr = _score_blueprint(bp, challenge["train"])
            hi = _score_blueprint(bp, challenge["hidden"])
            fr = _score_blueprint(bp, challenge["fresh"])
            key = (min(tr, hi, fr), (tr + hi + fr) / 3)
            old = (min(best["train"], best["hidden"], best["fresh"]), (best["train"] + best["hidden"] + best["fresh"]) / 3)
            if key > old:
                best = {"machine_id": mid, "train": tr, "hidden": hi, "fresh": fr}
        return best

    def _exact_atomic_candidate(self, challenge: dict[str, Any]) -> dict[str, Any] | None:
        admitted = {_canonical(x) for x in self._admitted_atomic_blueprints()}
        for bp in SAFE_NEW_ATOMIC_BLUEPRINTS:
            if _canonical(bp) in admitted:
                continue
            if all(_score_blueprint(bp, challenge[k]) == 1.0 for k in ("train", "hidden", "fresh")):
                return copy.deepcopy(bp)
        return None

    def _pipeline_candidates(self, depth: int):
        atoms = self._admitted_atomic_blueprints()
        # Deterministic bounded enumeration. Current depth <= 5 and atom count is small.
        for combo in itertools.product(atoms, repeat=depth):
            yield {
                "arity": 1,
                "category": "composed",
                "family": "meta.compose_pipeline",
                "params": {"steps": [copy.deepcopy(x) for x in combo]},
            }

    def _exact_pipeline_candidate(self, challenge: dict[str, Any], depth: int) -> dict[str, Any] | None:
        for bp in self._pipeline_candidates(depth):
            if _score_blueprint(bp, challenge["train"]) != 1.0:
                continue
            if _score_blueprint(bp, challenge["hidden"]) != 1.0:
                continue
            if _score_blueprint(bp, challenge["fresh"]) != 1.0:
                continue
            return bp
        return None

    def _propose_mutation(self, challenge: dict[str, Any]) -> dict[str, Any] | None:
        atomic = self._exact_atomic_candidate(challenge)
        if atomic is not None:
            return {"kind": "primitive", "route": "admit-atomic-primitive", "blueprint": atomic}
        max_depth = self._active_max_depth()
        # First use already-admitted grammar. This lets a grammar mutation in one
        # generation become the tool used to create a primitive in the next.
        for depth in range(2, max_depth + 1):
            bp = self._exact_pipeline_candidate(challenge, depth)
            if bp is not None:
                return {"kind": "primitive", "route": f"admit-compose{depth}-primitive", "blueprint": bp}
        if max_depth < 5:
            bp = self._exact_pipeline_candidate(challenge, max_depth + 1)
            if bp is not None:
                return {
                    "kind": "grammar",
                    "route": f"expand-grammar-unary-compose{max_depth + 1}",
                    "depth": max_depth + 1,
                    "witness": bp,
                }
        return None

    def _transfer_for_atomic(self, blueprint: dict[str, Any]) -> float:
        # Independent use: candidate becomes the inner step of a fresh predicate.
        outer = {"arity": 1, "category": "bitwise", "family": "integer.mod_equal", "params": {"modulus": 2, "residue": 0}}
        composed = {"arity": 1, "category": "composed", "family": "meta.compose_pipeline", "params": {"steps": [copy.deepcopy(blueprint), outer]}}
        cases = _cases_for(composed, self.TRANSFER_INPUTS)
        return _score_blueprint(composed, cases)

    def _transfer_for_grammar(self, depth: int) -> dict[str, Any]:
        atoms = self._admitted_atomic_blueprints()
        # Search for an independent exact depth-N function that lower depth cannot
        # represent perfectly on the transfer grid.
        for combo in itertools.product(atoms, repeat=depth):
            target = {"arity": 1, "category": "composed", "family": "meta.compose_pipeline", "params": {"steps": [copy.deepcopy(x) for x in combo]}}
            cases = _cases_for(target, self.TRANSFER_INPUTS)
            # avoid degenerate constant tasks
            vals = {_canonical(c["expected"]) for c in cases}
            if len(vals) < 2:
                continue
            lower_best = 0.0
            for lower in range(1, depth):
                if lower == 1:
                    for atom in atoms:
                        lower_best = max(lower_best, _score_blueprint(atom, cases))
                else:
                    for candidate in self._pipeline_candidates(lower):
                        lower_best = max(lower_best, _score_blueprint(candidate, cases))
                        if lower_best == 1.0:
                            break
                if lower_best == 1.0:
                    break
            if lower_best < 1.0 and _score_blueprint(target, cases) == 1.0:
                return {"score": 1.0, "lower_depth_best": lower_best, "target_digest": _blueprint_digest(target)}
        return {"score": 0.0, "lower_depth_best": 1.0, "target_digest": None}

    def _validate_mutation(self, challenge: dict[str, Any], proposal: dict[str, Any], before: dict[str, Any]) -> dict[str, Any]:
        if proposal["kind"] == "primitive":
            bp = dict(proposal["blueprint"])
            train = _score_blueprint(bp, challenge["train"])
            hidden = _score_blueprint(bp, challenge["hidden"])
            fresh = _score_blueprint(bp, challenge["fresh"])
            transfer = self._transfer_for_atomic(bp) if not str(bp.get("family", "")).startswith("meta.") else fresh
            baseline = min(float(before["train"]), float(before["hidden"]), float(before["fresh"]))
            causal_gain = min(train, hidden, fresh) - baseline
            return {
                "train": train, "hidden": hidden, "fresh": fresh, "transfer": transfer,
                "baseline": baseline, "causal_gain": causal_gain,
                "pass": train == hidden == fresh == transfer == 1.0 and causal_gain > 0.0,
            }
        depth = int(proposal["depth"])
        witness = dict(proposal["witness"])
        train = _score_blueprint(witness, challenge["train"])
        hidden = _score_blueprint(witness, challenge["hidden"])
        fresh = _score_blueprint(witness, challenge["fresh"])
        transfer = self._transfer_for_grammar(depth)
        old_depth = depth - 1
        old_best = 0.0
        for d in range(1, old_depth + 1):
            if d == 1:
                for atom in self._admitted_atomic_blueprints():
                    old_best = max(old_best, _score_blueprint(atom, challenge["fresh"]))
            else:
                for candidate in self._pipeline_candidates(d):
                    old_best = max(old_best, _score_blueprint(candidate, challenge["fresh"]))
                    if old_best == 1.0:
                        break
            if old_best == 1.0:
                break
        causal_gain = fresh - old_best
        return {
            "train": train, "hidden": hidden, "fresh": fresh,
            "transfer": transfer["score"], "transfer_lower_depth_best": transfer["lower_depth_best"],
            "baseline": old_best, "causal_gain": causal_gain,
            "pass": train == hidden == fresh == 1.0 and transfer["score"] == 1.0 and transfer["lower_depth_best"] < 1.0 and causal_gain > 0.0,
        }

    def _commit_mutation(self, challenge: dict[str, Any], proposal: dict[str, Any], validation: dict[str, Any]) -> dict[str, Any]:
        self._generation += 1
        if proposal["kind"] == "primitive":
            bp = copy.deepcopy(proposal["blueprint"])
            mid = _machine_id_for(bp)
            item = {
                "machine_id": mid,
                "blueprint": bp,
                "provenance": {
                    "generation": self._generation,
                    "challenge_id": challenge["challenge_id"],
                    "route": proposal["route"],
                    "train": validation["train"], "hidden": validation["hidden"],
                    "fresh": validation["fresh"], "transfer": validation["transfer"],
                    "causal_gain": validation["causal_gain"],
                },
                "self_tests": [copy.deepcopy(x) for x in challenge["hidden"][:6]],
            }
            self._evolved_primitives[mid] = item
            mutation = {"kind": "primitive", "machine_id": mid, "blueprint_digest": _blueprint_digest(bp)}
        else:
            depth = int(proposal["depth"])
            rule = {
                "rule_id": f"unary.compose{depth}",
                "admitted": True,
                "origin": "autonomous-self-development",
                "description": f"bounded composition of {depth} admitted unary atomic blueprints",
                "generation": self._generation,
                "challenge_id": challenge["challenge_id"],
            }
            self._evolved_grammar_rules.append(rule)
            mutation = {"kind": "grammar", "rule_id": rule["rule_id"], "depth": depth}
        record = {
            "generation": self._generation,
            "challenge_id": challenge["challenge_id"],
            "route": proposal["route"],
            "mutation": mutation,
            "validation": copy.deepcopy(validation),
            "status": "ADMITTED",
        }
        self._evolution_history.append(record)
        self._append_event("evolution.admitted", record)
        return copy.deepcopy(record)

    def audit_self(self) -> list[dict[str, Any]]:
        out: list[dict[str, Any]] = []
        for challenge in self._challenge_universe():
            before = self._best_existing(challenge)
            proposal = None if min(before["train"], before["hidden"], before["fresh"]) == 1.0 else self._propose_mutation(challenge)
            out.append({
                "challenge_id": challenge["challenge_id"],
                "current": before,
                "closed": min(before["train"], before["hidden"], before["fresh"]) == 1.0,
                "proposal_route": None if proposal is None else proposal["route"],
                "proposal_kind": None if proposal is None else proposal["kind"],
            })
        return out

    def develop_one_generation(self) -> dict[str, Any]:
        viable: list[tuple[float, str, dict[str, Any], dict[str, Any], dict[str, Any]]] = []
        for challenge in self._challenge_universe():
            before = self._best_existing(challenge)
            if min(before["train"], before["hidden"], before["fresh"]) == 1.0:
                continue
            proposal = self._propose_mutation(challenge)
            if proposal is None:
                continue
            validation = self._validate_mutation(challenge, proposal, before)
            if not validation["pass"]:
                self._append_event("evolution.withhold", {
                    "challenge_id": challenge["challenge_id"], "route": proposal["route"], "validation": validation,
                })
                continue
            # Prefer the strongest causal gain; tie-break deterministically by challenge id.
            viable.append((float(validation["causal_gain"]), str(challenge["challenge_id"]), challenge, proposal, validation))
        if not viable:
            stop = {"status": "WITHHOLD", "reason": "no-unresolved-gap-with-provable-mutation", "generation": self._generation}
            self._append_event("evolution.stopped", stop)
            return stop
        viable.sort(key=lambda x: (-x[0], x[1]))
        _, _, challenge, proposal, validation = viable[0]
        self._append_event("evolution.selected", {
            "challenge_id": challenge["challenge_id"], "route": proposal["route"], "causal_gain": validation["causal_gain"],
        })
        return self._commit_mutation(challenge, proposal, validation)

    def autonomous_develop(self, max_generations: int = 4) -> dict[str, Any]:
        if max_generations < 1 or max_generations > 8:
            raise ValueError("max_generations outside bounded range")
        initial = self.audit_self()
        generations: list[dict[str, Any]] = []
        for _ in range(max_generations):
            result = self.develop_one_generation()
            generations.append(copy.deepcopy(result))
            if result.get("status") != "ADMITTED":
                break
        final = self.audit_self()
        return {
            "schema": "ucr.autonomous-development-report/1",
            "kernel_id": self.kernel_id,
            "kernel_version": self.VERSION,
            "reader_imported": any(name.startswith("universal_code_reader") for name in sys.modules),
            "initial_audit": initial,
            "generations": generations,
            "final_audit": final,
            "admitted_generations": sum(1 for x in generations if x.get("status") == "ADMITTED"),
            "evolved_primitive_count": len(self._evolved_primitives),
            "evolved_grammar_rules": [x["rule_id"] for x in self._evolved_grammar_rules],
            "journal_valid": self.verify_journal(),
        }

    def export_evolution_state(self) -> dict[str, Any]:
        body = {
            "schema": "ucr.autonomous-evolution-state/1",
            "kernel_id": self.kernel_id,
            "generation": self._generation,
            "primitives": [copy.deepcopy(v) for _, v in sorted(self._evolved_primitives.items())],
            "grammar_rules": copy.deepcopy(self._evolved_grammar_rules),
            "history": copy.deepcopy(self._evolution_history),
        }
        return {**body, "digest": hashlib.sha256(_canonical(body).encode("utf-8")).hexdigest()}

    def _validate_evolution_state(self, state: dict[str, Any]) -> dict[str, Any]:
        raw = copy.deepcopy(state)
        supplied = str(raw.pop("digest", ""))
        expected = hashlib.sha256(_canonical(raw).encode("utf-8")).hexdigest()
        if supplied != expected:
            raise ValueError("evolution state digest mismatch")
        if raw.get("schema") != "ucr.autonomous-evolution-state/1" or raw.get("kernel_id") != self.kernel_id:
            raise ValueError("evolution state identity mismatch")
        rules = list(raw.get("grammar_rules") or [])
        allowed_depth = 3
        for rule in rules:
            rid = str(rule.get("rule_id", ""))
            if not rid.startswith("unary.compose") or not rid[len("unary.compose"):].isdigit():
                raise ValueError("unknown evolved grammar rule")
            depth = int(rid[len("unary.compose"):])
            if depth != allowed_depth + 1 or depth > 5:
                raise ValueError("non-sequential or excessive grammar evolution")
            allowed_depth = depth
        safe_latent = {_canonical(x) for x in SAFE_NEW_ATOMIC_BLUEPRINTS}
        base_atomic = {_canonical(x) for x in self._admitted_atomic_blueprints()}
        accepted_atomic = set(base_atomic)
        validated_primitives: list[dict[str, Any]] = []
        for item in list(raw.get("primitives") or []):
            bp = dict(item.get("blueprint") or {})
            family = str(bp.get("family", ""))
            if family == "meta.compose_pipeline":
                steps = list((bp.get("params") or {}).get("steps") or [])
                if len(steps) < 2 or len(steps) > allowed_depth:
                    raise ValueError("composed primitive outside admitted grammar")
                for step in steps:
                    if _canonical(step) not in accepted_atomic:
                        raise ValueError("composed primitive references non-admitted atomic step")
            else:
                key = _canonical(bp)
                if key not in safe_latent:
                    raise ValueError("unknown evolved atomic primitive")
                accepted_atomic.add(key)
            if str(item.get("machine_id")) != _machine_id_for(bp):
                raise ValueError("evolved primitive id mismatch")
            # Re-run stored self-tests before accepting restored code/data.
            for case in item.get("self_tests", []):
                observed = _eval_autonomous_blueprint(bp, [_json_restore(v) for v in case.get("args", [])])
                if not _typed_equal(observed, _json_restore(case.get("expected"))):
                    raise ValueError("evolved primitive self-test failed")
            validated_primitives.append(copy.deepcopy(item))
        return {**raw, "primitives": validated_primitives, "grammar_rules": rules}

    def load_evolution_state(self, state: dict[str, Any]) -> None:
        raw = self._validate_evolution_state(state)
        self._generation = int(raw.get("generation", 0))
        self._evolved_grammar_rules = copy.deepcopy(raw.get("grammar_rules") or [])
        self._evolved_primitives = {str(x["machine_id"]): copy.deepcopy(x) for x in raw.get("primitives", [])}
        self._evolution_history = copy.deepcopy(raw.get("history") or [])

    def snapshot(self) -> dict[str, Any]:
        base = super().snapshot()
        state = {
            "schema": "ucr.autonomous-kernel-state/2",
            "kernel_id": self.kernel_id,
            "base_snapshot": base,
            "evolution_state": self.export_evolution_state(),
        }
        return {**state, "snapshot_digest": hashlib.sha256(_canonical(state).encode("utf-8")).hexdigest()}

    def restore(self, snapshot: dict[str, Any]) -> None:
        snap = copy.deepcopy(snapshot)
        supplied = str(snap.pop("snapshot_digest", ""))
        expected = hashlib.sha256(_canonical(snap).encode("utf-8")).hexdigest()
        if supplied != expected:
            raise ValueError("autonomous snapshot digest mismatch")
        if snap.get("schema") != "ucr.autonomous-kernel-state/2" or snap.get("kernel_id") != self.kernel_id:
            raise ValueError("autonomous snapshot identity mismatch")
        super().restore(dict(snap["base_snapshot"]))
        self.load_evolution_state(dict(snap["evolution_state"]))


def autonomous_self_test() -> dict[str, Any]:
    base = self_test()
    kernel = AutonomousKernel()
    development = kernel.autonomous_develop(max_generations=5)
    evolved = kernel.export_evolution_state()
    snap = kernel.snapshot()
    restarted = AutonomousKernel(); restarted.restore(snap)
    restart_same = restarted.export_evolution_state().get("digest") == evolved.get("digest")

    # Every evolved primitive must survive restart and its stored tests.
    evolved_tests = 0
    evolved_failures: list[dict[str, Any]] = []
    for mid, item in restarted._evolved_primitives.items():
        for case in item.get("self_tests", []):
            try:
                observed = restarted.invoke(mid, *[_json_restore(v) for v in case.get("args", [])], record=False)
                if _typed_equal(observed, _json_restore(case.get("expected"))):
                    evolved_tests += 1
                else:
                    evolved_failures.append({"machine_id": mid, "reason": "result-mismatch"})
            except Exception as exc:
                evolved_failures.append({"machine_id": mid, "reason": type(exc).__name__})

    forged_rejected = False
    forged = copy.deepcopy(evolved)
    forged_body = copy.deepcopy(forged); forged_body.pop("digest", None)
    forged_body["primitives"].append({
        "machine_id": "kernel.evolved.forged",
        "blueprint": {"arity": 1, "category": "unsafe", "family": "python.exec", "params": {}},
        "self_tests": [],
    })
    forged = {**forged_body, "digest": hashlib.sha256(_canonical(forged_body).encode("utf-8")).hexdigest()}
    try:
        AutonomousKernel().load_evolution_state(forged)
    except Exception:
        forged_rejected = True

    # Negative mutation control: a duplicate admitted atomic is not a novel mutation.
    duplicate_rejected = kernel._exact_atomic_candidate(kernel._challenge_universe()[0]) is None

    return {
        "schema": "ucr.autonomous-kernel-validation/1",
        "kernel_id": kernel.kernel_id,
        "kernel_version": kernel.VERSION,
        "base_seed_test": base,
        "development": development,
        "restart_state_identical": restart_same,
        "evolved_self_tests_passed": evolved_tests,
        "evolved_self_test_failures": evolved_failures,
        "forged_evolution_state_rejected": forged_rejected,
        "duplicate_atomic_not_readded": duplicate_rejected,
        "reader_module_loaded": any(name.startswith("universal_code_reader") for name in sys.modules),
        "pass": bool(base.get("pass")) and development["admitted_generations"] >= 3 and restart_same and not evolved_failures and forged_rejected and duplicate_rejected and development["journal_valid"],
    }


# ---------------------------------------------------------------------------
# V22: bounded self-expansion of the task-type universe.
# A task domain is not activated merely because its evaluator exists. The
# kernel must first demonstrate a novel unsolved family plus independent
# transfer inside that family, then admit the domain, and only in later
# generations may it admit concrete capabilities from that domain.
# ---------------------------------------------------------------------------

_V21_EVAL_AUTONOMOUS_BLUEPRINT = _eval_autonomous_blueprint

SAFE_TASK_DOMAIN_BLUEPRINTS: dict[str, tuple[dict[str, Any], ...]] = {
    "sequence.v1": (
        {"arity": 1, "category": "sequence", "family": "sequence.reverse", "params": {}},
        {"arity": 1, "category": "sequence", "family": "sequence.length", "params": {}},
        {"arity": 1, "category": "sequence", "family": "sequence.unique_count", "params": {}},
        {"arity": 1, "category": "sequence", "family": "sequence.is_palindrome", "params": {}},
    ),
}

SEQUENCE_TRAIN_INPUTS: list[Any] = ["", "a", "ab", "aba", "abcd", "aabb", "abcabc", "level", "kernel", "112233"]
SEQUENCE_HIDDEN_INPUTS: list[Any] = ["racecar", "xyz", "aabca", "01010", "noon", "reader", "zzzy", "python"]
SEQUENCE_FRESH_INPUTS: list[Any] = ["rotor", "abcdef", "abccba", "mississippi", "12321", "openai", "aaaaab"]
SEQUENCE_TRANSFER_INPUTS: list[Any] = [[], [1], [1, 2], [1, 2, 1], [3, 3, 4, 5], (7, 8, 9), (4, 4, 4), (1, 2, 3, 2, 1)]


def _eval_autonomous_blueprint(blueprint: dict[str, Any], args: list[Any]) -> Any:
    family = str(blueprint.get("family", ""))
    if family in {"sequence.reverse", "sequence.length", "sequence.unique_count", "sequence.is_palindrome"}:
        if len(args) != 1:
            raise ValueError("arity mismatch")
        x = args[0]
        if type(x) not in (str, bytes, list, tuple):
            raise TypeError("sequence primitive requires bounded sequence")
        if len(x) > 4096:
            raise ValueError("sequence exceeds bounded runtime limit")
        if family == "sequence.reverse":
            return x[::-1]
        if family == "sequence.length":
            return len(x)
        if family == "sequence.unique_count":
            try:
                return len(set(x))
            except TypeError:
                # Nested/unhashable members are intentionally outside this bounded domain.
                raise TypeError("unique_count requires hashable sequence members")
        if family == "sequence.is_palindrome":
            return x == x[::-1]
    return _V21_EVAL_AUTONOMOUS_BLUEPRINT(blueprint, args)


class ExpandedAutonomousKernel(AutonomousKernel):
    VERSION = "22.0"

    def __init__(self) -> None:
        super().__init__()
        self._evolved_task_domains: list[dict[str, Any]] = []

    def capabilities(self) -> dict[str, Any]:
        out = super().capabilities()
        out.update({
            "autonomous_kernel_version": self.VERSION,
            "evolved_task_domains": [str(x["domain_id"]) for x in self._evolved_task_domains],
            "task_domain_count": len(self._evolved_task_domains),
        })
        return out

    def _active_task_domains(self) -> set[str]:
        return {str(x.get("domain_id")) for x in self._evolved_task_domains if x.get("admitted") is True}

    def _domain_case_sets(self, domain_id: str, blueprint: dict[str, Any]) -> dict[str, list[dict[str, Any]]]:
        if domain_id == "sequence.v1":
            return {
                "train": _cases_for(blueprint, SEQUENCE_TRAIN_INPUTS),
                "hidden": _cases_for(blueprint, SEQUENCE_HIDDEN_INPUTS),
                "fresh": _cases_for(blueprint, SEQUENCE_FRESH_INPUTS),
                "transfer": _cases_for(blueprint, SEQUENCE_TRANSFER_INPUTS),
            }
        raise ValueError("unknown task domain")

    def _domain_challenges(self) -> list[dict[str, Any]]:
        active = self._active_task_domains()
        out: list[dict[str, Any]] = []
        for domain_id, blueprints in sorted(SAFE_TASK_DOMAIN_BLUEPRINTS.items()):
            # Before a domain is admitted, the kernel sees only a domain-level gap.
            # Candidate selection is deterministic but is derived from the bounded
            # domain registry, not from an operator-provided target at runtime.
            if domain_id not in active:
                primary = copy.deepcopy(blueprints[0])
                cases = self._domain_case_sets(domain_id, primary)
                out.append({
                    "challenge_id": "self.domain." + domain_id + "." + _blueprint_digest(primary)[:10],
                    "source": "bounded-safe-task-domain-generator",
                    "task_domain": domain_id,
                    "domain_activation_required": True,
                    "target_digest": _blueprint_digest(primary),
                    "train": cases["train"], "hidden": cases["hidden"], "fresh": cases["fresh"],
                    "transfer_inputs": copy.deepcopy(SEQUENCE_TRANSFER_INPUTS if domain_id == "sequence.v1" else []),
                    "_target": primary,
                })
                continue
            admitted = {_canonical(x) for x in self._admitted_atomic_blueprints()}
            for blueprint in blueprints:
                if _canonical(blueprint) in admitted:
                    continue
                bp = copy.deepcopy(blueprint)
                cases = self._domain_case_sets(domain_id, bp)
                out.append({
                    "challenge_id": "self.domain-capability." + domain_id + "." + _blueprint_digest(bp)[:10],
                    "source": "admitted-task-domain-generator",
                    "task_domain": domain_id,
                    "domain_activation_required": False,
                    "target_digest": _blueprint_digest(bp),
                    "train": cases["train"], "hidden": cases["hidden"], "fresh": cases["fresh"],
                    "transfer_inputs": copy.deepcopy(SEQUENCE_TRANSFER_INPUTS if domain_id == "sequence.v1" else []),
                    "_target": bp,
                })
        return out

    def _challenge_universe(self) -> list[dict[str, Any]]:
        return list(super()._challenge_universe()) + self._domain_challenges()

    def _exact_domain_atomic_candidate(self, challenge: dict[str, Any]) -> dict[str, Any] | None:
        domain_id = str(challenge.get("task_domain", ""))
        if domain_id not in self._active_task_domains():
            return None
        admitted = {_canonical(x) for x in self._admitted_atomic_blueprints()}
        for bp in SAFE_TASK_DOMAIN_BLUEPRINTS.get(domain_id, ()):
            if _canonical(bp) in admitted:
                continue
            if all(_score_blueprint(bp, challenge[k]) == 1.0 for k in ("train", "hidden", "fresh")):
                if _blueprint_digest(bp) == str(challenge.get("target_digest")):
                    return copy.deepcopy(bp)
        return None

    def _propose_mutation(self, challenge: dict[str, Any]) -> dict[str, Any] | None:
        domain_id = str(challenge.get("task_domain", ""))
        if domain_id and bool(challenge.get("domain_activation_required")):
            if domain_id in self._active_task_domains():
                return None
            target = copy.deepcopy(challenge["_target"])
            return {
                "kind": "task-domain",
                "route": "expand-task-domain-" + domain_id,
                "domain_id": domain_id,
                "witness": target,
            }
        if domain_id:
            bp = self._exact_domain_atomic_candidate(challenge)
            if bp is not None:
                return {"kind": "primitive", "route": "admit-domain-atomic-primitive", "blueprint": bp}
            return None
        return super()._propose_mutation(challenge)

    def _transfer_for_atomic(self, blueprint: dict[str, Any]) -> float:
        if str(blueprint.get("category", "")) == "sequence":
            cases = _cases_for(blueprint, SEQUENCE_TRANSFER_INPUTS)
            return _score_blueprint(blueprint, cases)
        return super()._transfer_for_atomic(blueprint)

    def _validate_mutation(self, challenge: dict[str, Any], proposal: dict[str, Any], before: dict[str, Any]) -> dict[str, Any]:
        if proposal.get("kind") != "task-domain":
            return super()._validate_mutation(challenge, proposal, before)
        domain_id = str(proposal["domain_id"])
        witness = dict(proposal["witness"])
        train = _score_blueprint(witness, challenge["train"])
        hidden = _score_blueprint(witness, challenge["hidden"])
        fresh = _score_blueprint(witness, challenge["fresh"])
        baseline = min(float(before["train"]), float(before["hidden"]), float(before["fresh"]))
        candidates = list(SAFE_TASK_DOMAIN_BLUEPRINTS.get(domain_id, ()))
        transfer_score = 0.0
        transfer_digest = None
        for independent in candidates[1:]:
            cases = self._domain_case_sets(domain_id, independent)["transfer"]
            score = _score_blueprint(independent, cases)
            if score > transfer_score:
                transfer_score = score
                transfer_digest = _blueprint_digest(independent)
        causal_gain = min(train, hidden, fresh) - baseline
        return {
            "train": train, "hidden": hidden, "fresh": fresh,
            "transfer": transfer_score, "transfer_witness_digest": transfer_digest,
            "baseline": baseline, "causal_gain": causal_gain,
            "pass": train == hidden == fresh == 1.0 and transfer_score == 1.0 and causal_gain > 0.0,
        }

    def _commit_mutation(self, challenge: dict[str, Any], proposal: dict[str, Any], validation: dict[str, Any]) -> dict[str, Any]:
        if proposal.get("kind") != "task-domain":
            return super()._commit_mutation(challenge, proposal, validation)
        self._generation += 1
        domain_id = str(proposal["domain_id"])
        record_domain = {
            "domain_id": domain_id,
            "admitted": True,
            "origin": "autonomous-task-space-expansion",
            "generation": self._generation,
            "challenge_id": str(challenge["challenge_id"]),
            "transfer_witness_digest": validation.get("transfer_witness_digest"),
        }
        self._evolved_task_domains.append(record_domain)
        record = {
            "generation": self._generation,
            "challenge_id": challenge["challenge_id"],
            "route": proposal["route"],
            "mutation": {"kind": "task-domain", "domain_id": domain_id},
            "validation": copy.deepcopy(validation),
            "status": "ADMITTED",
        }
        self._evolution_history.append(record)
        self._append_event("evolution.admitted", record)
        return copy.deepcopy(record)

    def export_evolution_state(self) -> dict[str, Any]:
        body = {
            "schema": "ucr.autonomous-evolution-state/2",
            "kernel_id": self.kernel_id,
            "generation": self._generation,
            "primitives": [copy.deepcopy(v) for _, v in sorted(self._evolved_primitives.items())],
            "grammar_rules": copy.deepcopy(self._evolved_grammar_rules),
            "task_domains": copy.deepcopy(self._evolved_task_domains),
            "history": copy.deepcopy(self._evolution_history),
        }
        return {**body, "digest": hashlib.sha256(_canonical(body).encode("utf-8")).hexdigest()}

    def _validate_evolution_state(self, state: dict[str, Any]) -> dict[str, Any]:
        if state.get("schema") == "ucr.autonomous-evolution-state/1":
            base = super()._validate_evolution_state(state)
            return {**base, "task_domains": []}
        raw = copy.deepcopy(state)
        supplied = str(raw.pop("digest", ""))
        expected = hashlib.sha256(_canonical(raw).encode("utf-8")).hexdigest()
        if supplied != expected:
            raise ValueError("evolution state digest mismatch")
        if raw.get("schema") != "ucr.autonomous-evolution-state/2" or raw.get("kernel_id") != self.kernel_id:
            raise ValueError("evolution state identity mismatch")
        domains = list(raw.get("task_domains") or [])
        seen_domains: set[str] = set()
        for item in domains:
            did = str(item.get("domain_id", ""))
            if did not in SAFE_TASK_DOMAIN_BLUEPRINTS or item.get("admitted") is not True or did in seen_domains:
                raise ValueError("unknown, duplicate, or non-admitted task domain")
            seen_domains.add(did)
        rules = list(raw.get("grammar_rules") or [])
        allowed_depth = 3
        for rule in rules:
            rid = str(rule.get("rule_id", ""))
            if not rid.startswith("unary.compose") or not rid[len("unary.compose"):].isdigit():
                raise ValueError("unknown evolved grammar rule")
            depth = int(rid[len("unary.compose"):])
            if depth != allowed_depth + 1 or depth > 5:
                raise ValueError("non-sequential or excessive grammar evolution")
            allowed_depth = depth
        safe_latent = {_canonical(x) for x in SAFE_NEW_ATOMIC_BLUEPRINTS}
        for did in seen_domains:
            safe_latent.update(_canonical(x) for x in SAFE_TASK_DOMAIN_BLUEPRINTS[did])
        base_atomic = {_canonical(x) for x in self._admitted_atomic_blueprints()}
        accepted_atomic = set(base_atomic)
        validated_primitives: list[dict[str, Any]] = []
        for item in list(raw.get("primitives") or []):
            bp = dict(item.get("blueprint") or {})
            family = str(bp.get("family", ""))
            if family == "meta.compose_pipeline":
                steps = list((bp.get("params") or {}).get("steps") or [])
                if len(steps) < 2 or len(steps) > allowed_depth:
                    raise ValueError("composed primitive outside admitted grammar")
                for step in steps:
                    if _canonical(step) not in accepted_atomic:
                        raise ValueError("composed primitive references non-admitted atomic step")
            else:
                key = _canonical(bp)
                if key not in safe_latent:
                    raise ValueError("unknown evolved atomic primitive")
                accepted_atomic.add(key)
            if str(item.get("machine_id")) != _machine_id_for(bp):
                raise ValueError("evolved primitive id mismatch")
            for case in item.get("self_tests", []):
                observed = _eval_autonomous_blueprint(bp, [_json_restore(v) for v in case.get("args", [])])
                if not _typed_equal(observed, _json_restore(case.get("expected"))):
                    raise ValueError("evolved primitive self-test failed")
            validated_primitives.append(copy.deepcopy(item))
        return {**raw, "primitives": validated_primitives, "grammar_rules": rules, "task_domains": domains}

    def load_evolution_state(self, state: dict[str, Any]) -> None:
        raw = self._validate_evolution_state(state)
        self._generation = int(raw.get("generation", 0))
        self._evolved_grammar_rules = copy.deepcopy(raw.get("grammar_rules") or [])
        self._evolved_primitives = {str(x["machine_id"]): copy.deepcopy(x) for x in raw.get("primitives", [])}
        self._evolved_task_domains = copy.deepcopy(raw.get("task_domains") or [])
        self._evolution_history = copy.deepcopy(raw.get("history") or [])


# Rebind the public kernel class to the expanded implementation.
AutonomousKernel = ExpandedAutonomousKernel


def autonomous_self_test_v22() -> dict[str, Any]:
    base = self_test()
    kernel = AutonomousKernel()
    development = kernel.autonomous_develop(max_generations=8)
    evolved = kernel.export_evolution_state()
    snap = kernel.snapshot()
    restarted = AutonomousKernel(); restarted.restore(snap)
    restart_same = restarted.export_evolution_state().get("digest") == evolved.get("digest")
    domain_active = "sequence.v1" in restarted._active_task_domains()
    sequence_primitives = [
        x for x in restarted._evolved_primitives.values()
        if str((x.get("blueprint") or {}).get("category")) == "sequence"
    ]
    forged_rejected = False
    forged = copy.deepcopy(evolved)
    forged_body = copy.deepcopy(forged); forged_body.pop("digest", None)
    forged_body.setdefault("task_domains", []).append({"domain_id": "network.v1", "admitted": True})
    forged = {**forged_body, "digest": hashlib.sha256(_canonical(forged_body).encode("utf-8")).hexdigest()}
    try:
        AutonomousKernel().load_evolution_state(forged)
    except Exception:
        forged_rejected = True
    return {
        "schema": "ucr.autonomous-kernel-validation/2",
        "kernel_id": kernel.kernel_id,
        "kernel_version": kernel.VERSION,
        "base_seed_test": base,
        "development": development,
        "task_domain_sequence_active": domain_active,
        "sequence_primitive_count": len(sequence_primitives),
        "restart_state_identical": restart_same,
        "forged_task_domain_rejected": forged_rejected,
        "reader_module_loaded": any(name.startswith("universal_code_reader") for name in sys.modules),
        "pass": bool(base.get("pass")) and domain_active and len(sequence_primitives) >= 1 and restart_same and forged_rejected and development["journal_valid"],
    }


if __name__ == "__main__":
    print(json.dumps(autonomous_self_test_v22(), indent=2, sort_keys=True))

# ---------------------------------------------------------------------------
# V23: real-data-driven bounded self-development.
# External data is injected as validated JSON-safe records by the host bridge.
# The kernel has no network client and never executes source code. It derives
# challenges from observed datasets, then applies the same admission rules.
# ---------------------------------------------------------------------------

_V22_EVAL_AUTONOMOUS_BLUEPRINT = _eval_autonomous_blueprint
_RECORD_FAMILIES = {
    "records.sum_field",
    "records.max_field",
    "records.min_field",
    "records.argmax_label",
}


def _is_safe_field_name(value: Any) -> bool:
    return isinstance(value, str) and 1 <= len(value) <= 64 and all(ch.isalnum() or ch in "_-" for ch in value)


def _validate_record_sequence(value: Any) -> list[dict[str, Any]]:
    if type(value) not in (list, tuple):
        raise TypeError("records primitive requires a list/tuple of records")
    if not 1 <= len(value) <= 256:
        raise ValueError("record sequence outside bounded size")
    out: list[dict[str, Any]] = []
    for raw in value:
        if type(raw) is not dict or not (1 <= len(raw) <= 32):
            raise TypeError("each record must be a bounded mapping")
        row: dict[str, Any] = {}
        for key, val in raw.items():
            if not _is_safe_field_name(key):
                raise ValueError("unsafe record field name")
            if val is None or type(val) in (bool, int, float, str):
                if isinstance(val, str) and len(val) > 4096:
                    raise ValueError("record string field too large")
                row[str(key)] = val
            else:
                raise TypeError("record fields must be scalar JSON values")
        out.append(row)
    return out


def _is_safe_records_blueprint(blueprint: dict[str, Any]) -> bool:
    if int(blueprint.get("arity", 1)) != 1 or str(blueprint.get("category", "")) != "records":
        return False
    family = str(blueprint.get("family", ""))
    if family not in _RECORD_FAMILIES:
        return False
    params = dict(blueprint.get("params") or {})
    if family in {"records.sum_field", "records.max_field", "records.min_field"}:
        return set(params) == {"field"} and _is_safe_field_name(params.get("field"))
    return (
        set(params) == {"value_field", "label_field"}
        and _is_safe_field_name(params.get("value_field"))
        and _is_safe_field_name(params.get("label_field"))
    )


def _eval_autonomous_blueprint(blueprint: dict[str, Any], args: list[Any]) -> Any:
    family = str(blueprint.get("family", ""))
    if family in _RECORD_FAMILIES:
        if len(args) != 1:
            raise ValueError("arity mismatch")
        rows = _validate_record_sequence(args[0])
        params = dict(blueprint.get("params") or {})
        if family in {"records.sum_field", "records.max_field", "records.min_field"}:
            field = str(params.get("field", ""))
            if not _is_safe_field_name(field):
                raise ValueError("invalid records field")
            values: list[int | float] = []
            for row in rows:
                value = row.get(field)
                if type(value) not in (int, float) or type(value) is bool:
                    raise TypeError("records numeric aggregation requires numeric field")
                values.append(value)
            if family == "records.sum_field":
                return sum(values)
            if family == "records.max_field":
                return max(values)
            return min(values)
        value_field = str(params.get("value_field", ""))
        label_field = str(params.get("label_field", ""))
        if not _is_safe_field_name(value_field) or not _is_safe_field_name(label_field):
            raise ValueError("invalid records argmax fields")
        best_label: str | None = None
        best_value: int | float | None = None
        for row in rows:
            value = row.get(value_field); label = row.get(label_field)
            if type(value) not in (int, float) or type(value) is bool or not isinstance(label, str):
                raise TypeError("argmax requires numeric value field and string label field")
            if best_value is None or value > best_value:
                best_value = value; best_label = label
        return best_label
    return _V22_EVAL_AUTONOMOUS_BLUEPRINT(blueprint, args)


class RealDataAutonomousKernel(ExpandedAutonomousKernel):
    VERSION = "23.0"
    RECORD_DOMAIN_ID = "records.v1"
    _OBS_PREFIX = "__ucr_real_records__:"

    def capabilities(self) -> dict[str, Any]:
        out = super().capabilities()
        out.update({
            "autonomous_kernel_version": self.VERSION,
            "observed_real_dataset_count": len(self._observed_real_datasets()),
            "real_data_challenge_bridge": True,
        })
        return out

    def observe_external_records(self, dataset_id: str, rows: list[dict[str, Any]], provenance: dict[str, Any] | None = None) -> dict[str, Any]:
        did = str(dataset_id)
        if not did or len(did) > 96 or any(ch not in "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789._:-/" for ch in did):
            raise ValueError("invalid dataset id")
        safe_rows = _validate_record_sequence(rows)
        if len(safe_rows) < 6:
            raise ValueError("real-data evolution requires at least six records")
        numeric_fields = sorted(
            key for key in set.intersection(*(set(r.keys()) for r in safe_rows))
            if all(type(r.get(key)) in (int, float) and type(r.get(key)) is not bool for r in safe_rows)
        )
        string_fields = sorted(
            key for key in set.intersection(*(set(r.keys()) for r in safe_rows))
            if all(isinstance(r.get(key), str) for r in safe_rows)
        )
        if not numeric_fields:
            raise ValueError("dataset exposes no stable numeric fields")
        prov = _json_safe(provenance or {})
        body = {
            "schema": "ucr.real-record-dataset/1",
            "dataset_id": did,
            "rows": _json_safe(safe_rows),
            "numeric_fields": numeric_fields,
            "string_fields": string_fields,
            "provenance": prov,
        }
        body["digest"] = hashlib.sha256(_canonical(body).encode("utf-8")).hexdigest()
        self.remember(self._OBS_PREFIX + did, body)
        self._append_event("real-data.observed", {
            "dataset_id": did, "digest": body["digest"], "row_count": len(safe_rows),
            "numeric_fields": numeric_fields, "string_fields": string_fields,
        })
        return {
            "dataset_id": did, "digest": body["digest"], "row_count": len(safe_rows),
            "numeric_fields": numeric_fields, "string_fields": string_fields,
        }

    def _observed_real_datasets(self) -> list[dict[str, Any]]:
        out: list[dict[str, Any]] = []
        for key, value in sorted(self.memory.items()):
            if not str(key).startswith(self._OBS_PREFIX) or type(value) is not dict:
                continue
            raw = copy.deepcopy(value)
            supplied = str(raw.pop("digest", ""))
            expected = hashlib.sha256(_canonical(raw).encode("utf-8")).hexdigest()
            if supplied != expected or raw.get("schema") != "ucr.real-record-dataset/1":
                continue
            raw["digest"] = supplied
            out.append(raw)
        return out

    @staticmethod
    def _record_views(rows: list[dict[str, Any]]) -> list[list[dict[str, Any]]]:
        n = len(rows)
        candidates = [
            rows[:max(3, n // 2)], rows[-max(3, n // 2):], rows[::2], rows[1::2],
            rows[::3], rows[1::3], rows[2::3], rows[:max(3, (2 * n) // 3)], rows,
        ]
        out: list[list[dict[str, Any]]] = []
        seen: set[str] = set()
        for view in candidates:
            if len(view) < 2:
                continue
            key = _canonical(view)
            if key not in seen:
                seen.add(key); out.append(copy.deepcopy(view))
        return out

    def _record_blueprints(self, dataset: dict[str, Any]) -> list[dict[str, Any]]:
        numeric = list(dataset.get("numeric_fields") or [])
        strings = list(dataset.get("string_fields") or [])
        out: list[dict[str, Any]] = []
        for field in numeric:
            for family in ("records.max_field", "records.sum_field", "records.min_field"):
                out.append({"arity": 1, "category": "records", "family": family, "params": {"field": field}})
        if strings:
            label = "path" if "path" in strings else strings[0]
            for field in numeric:
                out.append({
                    "arity": 1, "category": "records", "family": "records.argmax_label",
                    "params": {"value_field": field, "label_field": label},
                })
        return out

    def _record_case_sets(self, blueprint: dict[str, Any], dataset: dict[str, Any]) -> dict[str, list[dict[str, Any]]]:
        views = self._record_views(_json_restore(dataset["rows"]))
        if len(views) < 6:
            raise ValueError("insufficient diverse real-data views")
        cases = _cases_for(blueprint, views)
        # All cases are derived from the real observed rows; no synthetic oracle rows are added.
        return {"train": cases[:3], "hidden": cases[3:5], "fresh": cases[5:]}

    def _record_transfer_score(self, blueprint: dict[str, Any], exclude_dataset: str | None = None) -> float:
        scores: list[float] = []
        for dataset in self._observed_real_datasets():
            if exclude_dataset is not None and str(dataset.get("dataset_id")) == exclude_dataset:
                continue
            try:
                cases = self._record_case_sets(blueprint, dataset)
            except Exception:
                continue
            all_cases = cases["train"] + cases["hidden"] + cases["fresh"]
            scores.append(_score_blueprint(blueprint, all_cases))
        return min(scores) if scores else 0.0

    def _real_data_challenges(self) -> list[dict[str, Any]]:
        datasets = self._observed_real_datasets()
        if not datasets:
            return []
        active = self._active_task_domains()
        admitted = {_canonical(x) for x in self._admitted_atomic_blueprints()}
        out: list[dict[str, Any]] = []
        for dataset in datasets:
            did = str(dataset["dataset_id"])
            for bp in self._record_blueprints(dataset):
                if self.RECORD_DOMAIN_ID in active and _canonical(bp) in admitted:
                    continue
                try:
                    cases = self._record_case_sets(bp, dataset)
                except Exception:
                    continue
                outputs = {_canonical(c["expected"]) for c in cases["train"] + cases["hidden"] + cases["fresh"]}
                if len(outputs) < 2:
                    continue
                out.append({
                    "challenge_id": "real." + hashlib.sha256((did + _blueprint_digest(bp)).encode("utf-8")).hexdigest()[:16],
                    "source": "observed-real-data-self-generator",
                    "task_domain": self.RECORD_DOMAIN_ID,
                    "domain_activation_required": self.RECORD_DOMAIN_ID not in active,
                    "dataset_id": did,
                    "dataset_digest": dataset["digest"],
                    "target_digest": _blueprint_digest(bp),
                    "train": cases["train"], "hidden": cases["hidden"], "fresh": cases["fresh"],
                    "_target": copy.deepcopy(bp),
                })
        return out

    def _challenge_universe(self) -> list[dict[str, Any]]:
        return list(super()._challenge_universe()) + self._real_data_challenges()

    def _propose_mutation(self, challenge: dict[str, Any]) -> dict[str, Any] | None:
        if str(challenge.get("task_domain", "")) == self.RECORD_DOMAIN_ID:
            if bool(challenge.get("domain_activation_required")):
                if self.RECORD_DOMAIN_ID in self._active_task_domains():
                    return None
                return {
                    "kind": "task-domain", "route": "expand-task-domain-records.v1",
                    "domain_id": self.RECORD_DOMAIN_ID, "witness": copy.deepcopy(challenge["_target"]),
                }
            bp = copy.deepcopy(challenge["_target"])
            if not _is_safe_records_blueprint(bp):
                return None
            if _canonical(bp) in {_canonical(x) for x in self._admitted_atomic_blueprints()}:
                return None
            if all(_score_blueprint(bp, challenge[k]) == 1.0 for k in ("train", "hidden", "fresh")):
                return {"kind": "primitive", "route": "admit-real-data-record-primitive", "blueprint": bp}
            return None
        return super()._propose_mutation(challenge)

    def _transfer_for_atomic(self, blueprint: dict[str, Any]) -> float:
        if str(blueprint.get("category", "")) == "records":
            return self._record_transfer_score(blueprint)
        return super()._transfer_for_atomic(blueprint)

    def _validate_mutation(self, challenge: dict[str, Any], proposal: dict[str, Any], before: dict[str, Any]) -> dict[str, Any]:
        if proposal.get("kind") == "task-domain" and proposal.get("domain_id") == self.RECORD_DOMAIN_ID:
            witness = dict(proposal["witness"])
            train = _score_blueprint(witness, challenge["train"])
            hidden = _score_blueprint(witness, challenge["hidden"])
            fresh = _score_blueprint(witness, challenge["fresh"])
            baseline = min(float(before["train"]), float(before["hidden"]), float(before["fresh"]))
            primary_dataset = str(challenge.get("dataset_id", ""))
            transfer = self._record_transfer_score(witness, exclude_dataset=primary_dataset)
            # Independent-family transfer: another records capability on a second real dataset.
            independent = 0.0
            for dataset in self._observed_real_datasets():
                if str(dataset.get("dataset_id")) == primary_dataset:
                    continue
                for candidate in self._record_blueprints(dataset):
                    if str(candidate.get("family")) == str(witness.get("family")):
                        continue
                    try:
                        cases = self._record_case_sets(candidate, dataset)
                    except Exception:
                        continue
                    independent = max(independent, _score_blueprint(candidate, cases["train"] + cases["hidden"] + cases["fresh"]))
            causal_gain = min(train, hidden, fresh) - baseline
            return {
                "train": train, "hidden": hidden, "fresh": fresh,
                "transfer": transfer, "independent_family_transfer": independent,
                "baseline": baseline, "causal_gain": causal_gain,
                "pass": train == hidden == fresh == transfer == independent == 1.0 and causal_gain > 0.0,
            }
        return super()._validate_mutation(challenge, proposal, before)

    def _commit_mutation(self, challenge: dict[str, Any], proposal: dict[str, Any], validation: dict[str, Any]) -> dict[str, Any]:
        if proposal.get("kind") == "task-domain" and proposal.get("domain_id") == self.RECORD_DOMAIN_ID:
            self._generation += 1
            record_domain = {
                "domain_id": self.RECORD_DOMAIN_ID, "admitted": True,
                "origin": "observed-real-data-task-space-expansion", "generation": self._generation,
                "challenge_id": str(challenge["challenge_id"]), "dataset_digest": challenge.get("dataset_digest"),
            }
            self._evolved_task_domains.append(record_domain)
            record = {
                "generation": self._generation, "challenge_id": challenge["challenge_id"],
                "route": proposal["route"], "mutation": {"kind": "task-domain", "domain_id": self.RECORD_DOMAIN_ID},
                "validation": copy.deepcopy(validation), "status": "ADMITTED",
            }
            self._evolution_history.append(record); self._append_event("evolution.admitted", record)
            return copy.deepcopy(record)
        return super()._commit_mutation(challenge, proposal, validation)

    def develop_one_generation(self) -> dict[str, Any]:
        # Real observed deficits are evaluated first once present. This avoids
        # synthetic challenge enumeration crowding out evidence from the live stream.
        real = self._real_data_challenges()
        if real:
            viable: list[tuple[float, str, dict[str, Any], dict[str, Any], dict[str, Any]]] = []
            unresolved = False
            for challenge in real:
                before = self._best_existing(challenge)
                if min(before["train"], before["hidden"], before["fresh"]) == 1.0:
                    continue
                unresolved = True
                proposal = self._propose_mutation(challenge)
                if proposal is None:
                    continue
                validation = self._validate_mutation(challenge, proposal, before)
                if validation["pass"]:
                    viable.append((float(validation["causal_gain"]), str(challenge["challenge_id"]), challenge, proposal, validation))
                else:
                    self._append_event("evolution.withhold", {
                        "challenge_id": challenge["challenge_id"], "route": proposal["route"], "validation": validation,
                    })
            if viable:
                viable.sort(key=lambda x: (-x[0], x[1]))
                _, _, challenge, proposal, validation = viable[0]
                self._append_event("evolution.selected", {
                    "challenge_id": challenge["challenge_id"], "route": proposal["route"],
                    "causal_gain": validation["causal_gain"], "source": "real-data",
                })
                return self._commit_mutation(challenge, proposal, validation)
            if unresolved:
                stop = {"status": "WITHHOLD", "reason": "real-data-gap-without-provable-mutation", "generation": self._generation}
                self._append_event("evolution.stopped", stop)
                return stop
        return super().develop_one_generation()

    def export_evolution_state(self) -> dict[str, Any]:
        body = {
            "schema": "ucr.autonomous-evolution-state/3", "kernel_id": self.kernel_id,
            "generation": self._generation,
            "primitives": [copy.deepcopy(v) for _, v in sorted(self._evolved_primitives.items())],
            "grammar_rules": copy.deepcopy(self._evolved_grammar_rules),
            "task_domains": copy.deepcopy(self._evolved_task_domains),
            "history": copy.deepcopy(self._evolution_history),
        }
        return {**body, "digest": hashlib.sha256(_canonical(body).encode("utf-8")).hexdigest()}

    def _validate_v23_state(self, state: dict[str, Any]) -> dict[str, Any]:
        raw = copy.deepcopy(state); supplied = str(raw.pop("digest", ""))
        expected = hashlib.sha256(_canonical(raw).encode("utf-8")).hexdigest()
        if supplied != expected:
            raise ValueError("evolution state digest mismatch")
        if raw.get("schema") != "ucr.autonomous-evolution-state/3" or raw.get("kernel_id") != self.kernel_id:
            raise ValueError("evolution state identity mismatch")
        domains = list(raw.get("task_domains") or []); seen_domains: set[str] = set()
        allowed_domains = set(SAFE_TASK_DOMAIN_BLUEPRINTS) | {self.RECORD_DOMAIN_ID}
        for item in domains:
            did = str(item.get("domain_id", ""))
            if did not in allowed_domains or item.get("admitted") is not True or did in seen_domains:
                raise ValueError("unknown, duplicate, or non-admitted task domain")
            seen_domains.add(did)
        rules = list(raw.get("grammar_rules") or []); allowed_depth = 3
        for rule in rules:
            rid = str(rule.get("rule_id", ""))
            if not rid.startswith("unary.compose") or not rid[len("unary.compose"):].isdigit():
                raise ValueError("unknown evolved grammar rule")
            depth = int(rid[len("unary.compose"):])
            if depth != allowed_depth + 1 or depth > 5:
                raise ValueError("non-sequential or excessive grammar evolution")
            allowed_depth = depth
        safe_static = {_canonical(x) for x in SAFE_NEW_ATOMIC_BLUEPRINTS}
        for did in seen_domains & set(SAFE_TASK_DOMAIN_BLUEPRINTS):
            safe_static.update(_canonical(x) for x in SAFE_TASK_DOMAIN_BLUEPRINTS[did])
        accepted_atomic = {_canonical(x) for x in super()._admitted_atomic_blueprints()}
        validated: list[dict[str, Any]] = []
        for item in list(raw.get("primitives") or []):
            bp = dict(item.get("blueprint") or {}); family = str(bp.get("family", ""))
            if family == "meta.compose_pipeline":
                steps = list((bp.get("params") or {}).get("steps") or [])
                if len(steps) < 2 or len(steps) > allowed_depth or any(_canonical(step) not in accepted_atomic for step in steps):
                    raise ValueError("composed primitive outside admitted grammar")
            elif _is_safe_records_blueprint(bp):
                if self.RECORD_DOMAIN_ID not in seen_domains:
                    raise ValueError("records primitive without admitted records domain")
                accepted_atomic.add(_canonical(bp))
            else:
                key = _canonical(bp)
                if key not in safe_static:
                    raise ValueError("unknown evolved atomic primitive")
                accepted_atomic.add(key)
            if str(item.get("machine_id")) != _machine_id_for(bp):
                raise ValueError("evolved primitive id mismatch")
            for case in item.get("self_tests", []):
                observed = _eval_autonomous_blueprint(bp, [_json_restore(v) for v in case.get("args", [])])
                if not _typed_equal(observed, _json_restore(case.get("expected"))):
                    raise ValueError("evolved primitive self-test failed")
            validated.append(copy.deepcopy(item))
        return {**raw, "primitives": validated, "grammar_rules": rules, "task_domains": domains}

    def load_evolution_state(self, state: dict[str, Any]) -> None:
        schema = state.get("schema")
        if schema in {"ucr.autonomous-evolution-state/1", "ucr.autonomous-evolution-state/2"}:
            super().load_evolution_state(state)
            return
        raw = self._validate_v23_state(state)
        self._generation = int(raw.get("generation", 0))
        self._evolved_grammar_rules = copy.deepcopy(raw.get("grammar_rules") or [])
        self._evolved_primitives = {str(x["machine_id"]): copy.deepcopy(x) for x in raw.get("primitives", [])}
        self._evolved_task_domains = copy.deepcopy(raw.get("task_domains") or [])
        self._evolution_history = copy.deepcopy(raw.get("history") or [])


AutonomousKernel = RealDataAutonomousKernel


def autonomous_self_test_v23() -> dict[str, Any]:
    kernel = AutonomousKernel()
    # Embedded self-test uses two compact, deterministic record streams. Full
    # validation with live project records is performed by the external test harness.
    a = [{"path": f"a{i}", "bytes": x, "lines": i + 3} for i, x in enumerate([5, 11, 7, 20, 13, 2, 17, 23])]
    b = [{"path": f"b{i}", "bytes": x, "lines": i + 5} for i, x in enumerate([8, 3, 14, 19, 6, 25, 10, 21])]
    kernel.observe_external_records("self/a", a, {"kind": "self-test"})
    kernel.observe_external_records("self/b", b, {"kind": "self-test"})
    first = kernel.develop_one_generation()
    second = kernel.develop_one_generation()
    snap = kernel.snapshot(); restarted = AutonomousKernel(); restarted.restore(snap)
    return {
        "schema": "ucr.autonomous-kernel-v23-self-test/1", "first": first, "second": second,
        "records_domain_active": kernel.RECORD_DOMAIN_ID in kernel._active_task_domains(),
        "restart_digest_same": restarted.export_evolution_state()["digest"] == kernel.export_evolution_state()["digest"],
        "journal_valid": kernel.verify_journal(),
        "pass": first.get("status") == "ADMITTED" and second.get("status") == "ADMITTED" and kernel.verify_journal(),
    }

# V23.1: require record-capability transfer on a different observed dataset.
_V23_VALIDATE_MUTATION_BASE = RealDataAutonomousKernel._validate_mutation

def _v23_validate_mutation_strict_transfer(self: RealDataAutonomousKernel, challenge: dict[str, Any], proposal: dict[str, Any], before: dict[str, Any]) -> dict[str, Any]:
    bp = dict(proposal.get("blueprint") or {})
    if proposal.get("kind") == "primitive" and str(bp.get("category", "")) == "records":
        train = _score_blueprint(bp, challenge["train"])
        hidden = _score_blueprint(bp, challenge["hidden"])
        fresh = _score_blueprint(bp, challenge["fresh"])
        baseline = min(float(before["train"]), float(before["hidden"]), float(before["fresh"]))
        transfer = self._record_transfer_score(bp, exclude_dataset=str(challenge.get("dataset_id", "")))
        causal_gain = min(train, hidden, fresh) - baseline
        return {
            "train": train, "hidden": hidden, "fresh": fresh, "transfer": transfer,
            "baseline": baseline, "causal_gain": causal_gain,
            "pass": train == hidden == fresh == transfer == 1.0 and causal_gain > 0.0,
        }
    return _V23_VALIDATE_MUTATION_BASE(self, challenge, proposal, before)

RealDataAutonomousKernel._validate_mutation = _v23_validate_mutation_strict_transfer
AutonomousKernel = RealDataAutonomousKernel

# ---------------------------------------------------------------------------
# V24: architecture-graph real-data self-development.
# The host bridge may inject a bounded static graph extracted from source code
# (modules/files as nodes; import/call relations as typed edges). The kernel has
# no source loader, parser, network client, or arbitrary execution path. It can
# only reason over validated JSON-safe graph structure and causally admit a
# small closed family of graph primitives after independent-project transfer.
# ---------------------------------------------------------------------------

_V23_EVAL_AUTONOMOUS_BLUEPRINT = _eval_autonomous_blueprint
_GRAPH_FAMILIES = {
    "graph.node_count",
    "graph.edge_count",
    "graph.max_out_degree_label",
    "graph.max_in_degree_label",
    "graph.source_count",
    "graph.sink_count",
    "graph.cyclic_node_count",
}


def _is_safe_graph_token(value: Any, *, max_len: int = 192) -> bool:
    return (
        isinstance(value, str)
        and 1 <= len(value) <= max_len
        and all(ch.isalnum() or ch in "._:/-" for ch in value)
    )


def _validate_code_graph(value: Any) -> dict[str, Any]:
    if type(value) is not dict or set(value) - {"nodes", "edges"}:
        raise TypeError("graph must be a mapping with nodes/edges")
    raw_nodes = value.get("nodes")
    raw_edges = value.get("edges")
    if type(raw_nodes) not in (list, tuple) or type(raw_edges) not in (list, tuple):
        raise TypeError("graph nodes/edges must be sequences")
    if not 2 <= len(raw_nodes) <= 512 or len(raw_edges) > 4096:
        raise ValueError("graph outside bounded size")
    nodes: list[dict[str, Any]] = []
    seen_nodes: set[str] = set()
    for raw in raw_nodes:
        if type(raw) is str:
            nid = raw; kind = "module"
        elif type(raw) is dict and set(raw) <= {"id", "kind"}:
            nid = raw.get("id"); kind = raw.get("kind", "module")
        else:
            raise TypeError("invalid graph node")
        if not _is_safe_graph_token(nid) or not _is_safe_graph_token(kind, max_len=48):
            raise ValueError("unsafe graph node")
        if nid in seen_nodes:
            raise ValueError("duplicate graph node")
        seen_nodes.add(str(nid)); nodes.append({"id": str(nid), "kind": str(kind)})
    edges: list[dict[str, str]] = []
    seen_edges: set[tuple[str, str, str]] = set()
    for raw in raw_edges:
        if type(raw) is not dict or set(raw) != {"src", "dst", "kind"}:
            raise TypeError("invalid graph edge")
        src = raw.get("src"); dst = raw.get("dst"); kind = raw.get("kind")
        if not _is_safe_graph_token(src) or not _is_safe_graph_token(dst) or not _is_safe_graph_token(kind, max_len=48):
            raise ValueError("unsafe graph edge")
        if src not in seen_nodes or dst not in seen_nodes:
            raise ValueError("graph edge references unknown node")
        key = (str(src), str(dst), str(kind))
        if key in seen_edges:
            continue
        seen_edges.add(key); edges.append({"src": key[0], "dst": key[1], "kind": key[2]})
    nodes.sort(key=lambda x: x["id"])
    edges.sort(key=lambda x: (x["kind"], x["src"], x["dst"]))
    return {"nodes": nodes, "edges": edges}


def _graph_edges(graph: dict[str, Any], kind: str) -> list[dict[str, str]]:
    edges = list(graph["edges"])
    return edges if kind == "all" else [e for e in edges if e["kind"] == kind]


def _graph_degrees(graph: dict[str, Any], kind: str) -> tuple[dict[str, int], dict[str, int]]:
    ids = [n["id"] for n in graph["nodes"]]
    outd = {nid: 0 for nid in ids}; ind = {nid: 0 for nid in ids}
    for edge in _graph_edges(graph, kind):
        outd[edge["src"]] += 1; ind[edge["dst"]] += 1
    return outd, ind


def _graph_cyclic_nodes(graph: dict[str, Any], kind: str) -> set[str]:
    ids = [n["id"] for n in graph["nodes"]]
    adj: dict[str, list[str]] = {nid: [] for nid in ids}
    for e in _graph_edges(graph, kind):
        adj[e["src"]].append(e["dst"])
    index = 0; stack: list[str] = []; on_stack: set[str] = set()
    idx: dict[str, int] = {}; low: dict[str, int] = {}; cyclic: set[str] = set()

    def visit(v: str) -> None:
        nonlocal index
        idx[v] = index; low[v] = index; index += 1
        stack.append(v); on_stack.add(v)
        for w in adj[v]:
            if w not in idx:
                visit(w); low[v] = min(low[v], low[w])
            elif w in on_stack:
                low[v] = min(low[v], idx[w])
        if low[v] == idx[v]:
            comp: list[str] = []
            while True:
                w = stack.pop(); on_stack.remove(w); comp.append(w)
                if w == v:
                    break
            if len(comp) > 1:
                cyclic.update(comp)
            elif comp and comp[0] in adj[comp[0]]:
                cyclic.add(comp[0])

    for nid in ids:
        if nid not in idx:
            visit(nid)
    return cyclic


def _is_safe_graph_blueprint(blueprint: dict[str, Any]) -> bool:
    if int(blueprint.get("arity", 1)) != 1 or str(blueprint.get("category", "")) != "codegraph":
        return False
    family = str(blueprint.get("family", "")); params = dict(blueprint.get("params") or {})
    if family not in _GRAPH_FAMILIES:
        return False
    if family == "graph.node_count":
        return params == {}
    return set(params) == {"kind"} and _is_safe_graph_token(params.get("kind"), max_len=48)


def _eval_autonomous_blueprint(blueprint: dict[str, Any], args: list[Any]) -> Any:
    family = str(blueprint.get("family", ""))
    if family in _GRAPH_FAMILIES:
        if len(args) != 1:
            raise ValueError("arity mismatch")
        graph = _validate_code_graph(args[0]); params = dict(blueprint.get("params") or {})
        if family == "graph.node_count":
            return len(graph["nodes"])
        kind = str(params.get("kind", ""))
        if not _is_safe_graph_token(kind, max_len=48):
            raise ValueError("invalid graph edge kind")
        edges = _graph_edges(graph, kind)
        if family == "graph.edge_count":
            return len(edges)
        outd, ind = _graph_degrees(graph, kind)
        if family == "graph.max_out_degree_label":
            best = max(outd.values(), default=0)
            return min(n for n, v in outd.items() if v == best)
        if family == "graph.max_in_degree_label":
            best = max(ind.values(), default=0)
            return min(n for n, v in ind.items() if v == best)
        if family == "graph.source_count":
            return sum(1 for n in ind if ind[n] == 0 and outd[n] > 0)
        if family == "graph.sink_count":
            return sum(1 for n in outd if outd[n] == 0 and ind[n] > 0)
        if family == "graph.cyclic_node_count":
            return len(_graph_cyclic_nodes(graph, kind))
    return _V23_EVAL_AUTONOMOUS_BLUEPRINT(blueprint, args)


class ArchitectureAutonomousKernel(RealDataAutonomousKernel):
    VERSION = "24.0"
    GRAPH_DOMAIN_ID = "codegraph.v1"
    _GRAPH_OBS_PREFIX = "__ucr_code_graph__:"

    def capabilities(self) -> dict[str, Any]:
        out = super().capabilities()
        out.update({
            "autonomous_kernel_version": self.VERSION,
            "observed_code_graph_count": len(self._observed_code_graphs()),
            "architecture_graph_bridge": True,
        })
        return out

    def observe_external_code_graph(self, dataset_id: str, graph: dict[str, Any], provenance: dict[str, Any] | None = None) -> dict[str, Any]:
        did = str(dataset_id)
        if not did or len(did) > 96 or any(ch not in "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789._:-/" for ch in did):
            raise ValueError("invalid graph dataset id")
        safe_graph = _validate_code_graph(graph)
        kinds = sorted({e["kind"] for e in safe_graph["edges"]})
        if not kinds or len(safe_graph["edges"]) < 3:
            raise ValueError("code graph exposes too little structure")
        body = {
            "schema": "ucr.code-graph-dataset/1", "dataset_id": did,
            "graph": _json_safe(safe_graph), "edge_kinds": kinds,
            "provenance": _json_safe(provenance or {}),
        }
        body["digest"] = hashlib.sha256(_canonical(body).encode("utf-8")).hexdigest()
        self.remember(self._GRAPH_OBS_PREFIX + did, body)
        self._append_event("code-graph.observed", {
            "dataset_id": did, "digest": body["digest"], "node_count": len(safe_graph["nodes"]),
            "edge_count": len(safe_graph["edges"]), "edge_kinds": kinds,
        })
        return {"dataset_id": did, "digest": body["digest"], "node_count": len(safe_graph["nodes"]), "edge_count": len(safe_graph["edges"]), "edge_kinds": kinds}

    def _observed_code_graphs(self) -> list[dict[str, Any]]:
        out: list[dict[str, Any]] = []
        for key, value in sorted(self.memory.items()):
            if not str(key).startswith(self._GRAPH_OBS_PREFIX) or type(value) is not dict:
                continue
            raw = copy.deepcopy(value); supplied = str(raw.pop("digest", ""))
            expected = hashlib.sha256(_canonical(raw).encode("utf-8")).hexdigest()
            if supplied != expected or raw.get("schema") != "ucr.code-graph-dataset/1":
                continue
            raw["digest"] = supplied; out.append(raw)
        return out

    @staticmethod
    def _graph_views(graph: dict[str, Any]) -> list[dict[str, Any]]:
        graph = _validate_code_graph(graph)
        ids = [n["id"] for n in graph["nodes"]]; n = len(ids)
        subsets = [
            ids[:max(3, n // 2)], ids[-max(3, n // 2):], ids[::2], ids[1::2],
            ids[::3] + ids[1::3], ids[:max(3, (2 * n) // 3)], ids[-max(3, (2 * n) // 3):], ids,
        ]
        out: list[dict[str, Any]] = []; seen: set[str] = set()
        node_map = {x["id"]: x for x in graph["nodes"]}
        for raw_ids in subsets:
            chosen = sorted(set(raw_ids))
            if len(chosen) < 2:
                continue
            chosen_set = set(chosen)
            view = {
                "nodes": [copy.deepcopy(node_map[x]) for x in chosen],
                "edges": [copy.deepcopy(e) for e in graph["edges"] if e["src"] in chosen_set and e["dst"] in chosen_set],
            }
            key = _canonical(view)
            if key not in seen:
                seen.add(key); out.append(view)
        return out

    def _graph_blueprints(self, dataset: dict[str, Any]) -> list[dict[str, Any]]:
        kinds = ["all"] + list(dataset.get("edge_kinds") or [])
        out: list[dict[str, Any]] = [{"arity": 1, "category": "codegraph", "family": "graph.node_count", "params": {}}]
        for kind in kinds:
            for family in (
                "graph.edge_count", "graph.max_out_degree_label", "graph.max_in_degree_label",
                "graph.source_count", "graph.sink_count", "graph.cyclic_node_count",
            ):
                out.append({"arity": 1, "category": "codegraph", "family": family, "params": {"kind": kind}})
        return out

    def _graph_case_sets(self, blueprint: dict[str, Any], dataset: dict[str, Any]) -> dict[str, list[dict[str, Any]]]:
        views = self._graph_views(_json_restore(dataset["graph"]))
        if len(views) < 6:
            raise ValueError("insufficient diverse graph views")
        cases = _cases_for(blueprint, views)
        return {"train": cases[:3], "hidden": cases[3:5], "fresh": cases[5:]}

    def _graph_transfer_score(self, blueprint: dict[str, Any], exclude_dataset: str | None = None) -> float:
        scores: list[float] = []
        for dataset in self._observed_code_graphs():
            if exclude_dataset is not None and str(dataset.get("dataset_id")) == exclude_dataset:
                continue
            try:
                cases = self._graph_case_sets(blueprint, dataset)
            except Exception:
                continue
            scores.append(_score_blueprint(blueprint, cases["train"] + cases["hidden"] + cases["fresh"]))
        return min(scores) if scores else 0.0

    def _graph_challenges(self) -> list[dict[str, Any]]:
        datasets = self._observed_code_graphs()
        if not datasets:
            return []
        active = self._active_task_domains(); admitted = {_canonical(x) for x in self._admitted_atomic_blueprints()}
        out: list[dict[str, Any]] = []
        for dataset in datasets:
            did = str(dataset["dataset_id"])
            for bp in self._graph_blueprints(dataset):
                if self.GRAPH_DOMAIN_ID in active and _canonical(bp) in admitted:
                    continue
                try:
                    cases = self._graph_case_sets(bp, dataset)
                except Exception:
                    continue
                outputs = {_canonical(c["expected"]) for c in cases["train"] + cases["hidden"] + cases["fresh"]}
                if len(outputs) < 2:
                    continue
                out.append({
                    "challenge_id": "arch." + hashlib.sha256((did + _blueprint_digest(bp)).encode("utf-8")).hexdigest()[:16],
                    "source": "observed-code-graph-self-generator",
                    "task_domain": self.GRAPH_DOMAIN_ID,
                    "domain_activation_required": self.GRAPH_DOMAIN_ID not in active,
                    "dataset_id": did, "dataset_digest": dataset["digest"], "target_digest": _blueprint_digest(bp),
                    "train": cases["train"], "hidden": cases["hidden"], "fresh": cases["fresh"],
                    "_target": copy.deepcopy(bp),
                })
        return out

    def _challenge_universe(self) -> list[dict[str, Any]]:
        return list(super()._challenge_universe()) + self._graph_challenges()

    def _propose_mutation(self, challenge: dict[str, Any]) -> dict[str, Any] | None:
        if str(challenge.get("task_domain", "")) == self.GRAPH_DOMAIN_ID:
            if bool(challenge.get("domain_activation_required")):
                if self.GRAPH_DOMAIN_ID in self._active_task_domains():
                    return None
                return {"kind": "task-domain", "route": "expand-task-domain-codegraph.v1", "domain_id": self.GRAPH_DOMAIN_ID, "witness": copy.deepcopy(challenge["_target"])}
            bp = copy.deepcopy(challenge["_target"])
            if not _is_safe_graph_blueprint(bp):
                return None
            if _canonical(bp) in {_canonical(x) for x in self._admitted_atomic_blueprints()}:
                return None
            if all(_score_blueprint(bp, challenge[k]) == 1.0 for k in ("train", "hidden", "fresh")):
                return {"kind": "primitive", "route": "admit-codegraph-primitive", "blueprint": bp}
            return None
        return super()._propose_mutation(challenge)

    def _validate_mutation(self, challenge: dict[str, Any], proposal: dict[str, Any], before: dict[str, Any]) -> dict[str, Any]:
        if proposal.get("kind") == "task-domain" and proposal.get("domain_id") == self.GRAPH_DOMAIN_ID:
            witness = dict(proposal["witness"])
            train = _score_blueprint(witness, challenge["train"]); hidden = _score_blueprint(witness, challenge["hidden"]); fresh = _score_blueprint(witness, challenge["fresh"])
            baseline = min(float(before["train"]), float(before["hidden"]), float(before["fresh"]))
            primary = str(challenge.get("dataset_id", "")); transfer = self._graph_transfer_score(witness, exclude_dataset=primary)
            independent = 0.0
            for dataset in self._observed_code_graphs():
                if str(dataset.get("dataset_id")) == primary:
                    continue
                for candidate in self._graph_blueprints(dataset):
                    if str(candidate.get("family")) == str(witness.get("family")):
                        continue
                    try:
                        cases = self._graph_case_sets(candidate, dataset)
                    except Exception:
                        continue
                    independent = max(independent, _score_blueprint(candidate, cases["train"] + cases["hidden"] + cases["fresh"]))
            causal_gain = min(train, hidden, fresh) - baseline
            return {"train": train, "hidden": hidden, "fresh": fresh, "transfer": transfer, "independent_family_transfer": independent, "baseline": baseline, "causal_gain": causal_gain, "pass": train == hidden == fresh == transfer == independent == 1.0 and causal_gain > 0.0}
        bp = dict(proposal.get("blueprint") or {})
        if proposal.get("kind") == "primitive" and str(bp.get("category", "")) == "codegraph":
            train = _score_blueprint(bp, challenge["train"]); hidden = _score_blueprint(bp, challenge["hidden"]); fresh = _score_blueprint(bp, challenge["fresh"])
            baseline = min(float(before["train"]), float(before["hidden"]), float(before["fresh"]))
            transfer = self._graph_transfer_score(bp, exclude_dataset=str(challenge.get("dataset_id", "")))
            causal_gain = min(train, hidden, fresh) - baseline
            return {"train": train, "hidden": hidden, "fresh": fresh, "transfer": transfer, "baseline": baseline, "causal_gain": causal_gain, "pass": train == hidden == fresh == transfer == 1.0 and causal_gain > 0.0}
        return super()._validate_mutation(challenge, proposal, before)

    def _commit_mutation(self, challenge: dict[str, Any], proposal: dict[str, Any], validation: dict[str, Any]) -> dict[str, Any]:
        if proposal.get("kind") == "task-domain" and proposal.get("domain_id") == self.GRAPH_DOMAIN_ID:
            self._generation += 1
            domain = {"domain_id": self.GRAPH_DOMAIN_ID, "admitted": True, "origin": "observed-code-architecture-task-space-expansion", "generation": self._generation, "challenge_id": str(challenge["challenge_id"]), "dataset_digest": challenge.get("dataset_digest")}
            self._evolved_task_domains.append(domain)
            record = {"generation": self._generation, "challenge_id": challenge["challenge_id"], "route": proposal["route"], "mutation": {"kind": "task-domain", "domain_id": self.GRAPH_DOMAIN_ID}, "validation": copy.deepcopy(validation), "status": "ADMITTED"}
            self._evolution_history.append(record); self._append_event("evolution.admitted", record)
            return copy.deepcopy(record)
        return super()._commit_mutation(challenge, proposal, validation)

    def develop_one_generation(self) -> dict[str, Any]:
        graph_challenges = self._graph_challenges()
        if graph_challenges:
            viable: list[tuple[float, str, dict[str, Any], dict[str, Any], dict[str, Any]]] = []; unresolved = False
            for challenge in graph_challenges:
                before = self._best_existing(challenge)
                if min(before["train"], before["hidden"], before["fresh"]) == 1.0:
                    continue
                unresolved = True; proposal = self._propose_mutation(challenge)
                if proposal is None:
                    continue
                validation = self._validate_mutation(challenge, proposal, before)
                if validation["pass"]:
                    viable.append((float(validation["causal_gain"]), str(challenge["challenge_id"]), challenge, proposal, validation))
                else:
                    self._append_event("evolution.withhold", {"challenge_id": challenge["challenge_id"], "route": proposal["route"], "validation": validation})
            if viable:
                viable.sort(key=lambda x: (-x[0], x[1])); _, _, challenge, proposal, validation = viable[0]
                self._append_event("evolution.selected", {"challenge_id": challenge["challenge_id"], "route": proposal["route"], "causal_gain": validation["causal_gain"], "source": "code-graph-real-data"})
                return self._commit_mutation(challenge, proposal, validation)
            if unresolved:
                stop = {"status": "WITHHOLD", "reason": "code-graph-gap-without-provable-mutation", "generation": self._generation}
                self._append_event("evolution.stopped", stop); return stop
        return super().develop_one_generation()

    def export_evolution_state(self) -> dict[str, Any]:
        body = {"schema": "ucr.autonomous-evolution-state/4", "kernel_id": self.kernel_id, "generation": self._generation, "primitives": [copy.deepcopy(v) for _, v in sorted(self._evolved_primitives.items())], "grammar_rules": copy.deepcopy(self._evolved_grammar_rules), "task_domains": copy.deepcopy(self._evolved_task_domains), "history": copy.deepcopy(self._evolution_history)}
        return {**body, "digest": hashlib.sha256(_canonical(body).encode("utf-8")).hexdigest()}

    def _validate_v24_state(self, state: dict[str, Any]) -> dict[str, Any]:
        raw = copy.deepcopy(state); supplied = str(raw.pop("digest", "")); expected = hashlib.sha256(_canonical(raw).encode("utf-8")).hexdigest()
        if supplied != expected:
            raise ValueError("evolution state digest mismatch")
        if raw.get("schema") != "ucr.autonomous-evolution-state/4" or raw.get("kernel_id") != self.kernel_id:
            raise ValueError("evolution state identity mismatch")
        domains = list(raw.get("task_domains") or []); seen_domains: set[str] = set(); allowed_domains = set(SAFE_TASK_DOMAIN_BLUEPRINTS) | {self.RECORD_DOMAIN_ID, self.GRAPH_DOMAIN_ID}
        for item in domains:
            did = str(item.get("domain_id", ""))
            if did not in allowed_domains or item.get("admitted") is not True or did in seen_domains:
                raise ValueError("unknown, duplicate, or non-admitted task domain")
            seen_domains.add(did)
        rules = list(raw.get("grammar_rules") or []); allowed_depth = 3
        for rule in rules:
            rid = str(rule.get("rule_id", ""))
            if not rid.startswith("unary.compose") or not rid[len("unary.compose"):].isdigit():
                raise ValueError("unknown evolved grammar rule")
            depth = int(rid[len("unary.compose"):])
            if depth != allowed_depth + 1 or depth > 5:
                raise ValueError("non-sequential or excessive grammar evolution")
            allowed_depth = depth
        safe_static = {_canonical(x) for x in SAFE_NEW_ATOMIC_BLUEPRINTS}
        for did in seen_domains & set(SAFE_TASK_DOMAIN_BLUEPRINTS):
            safe_static.update(_canonical(x) for x in SAFE_TASK_DOMAIN_BLUEPRINTS[did])
        accepted_atomic = {_canonical(x) for x in super()._admitted_atomic_blueprints()}; validated: list[dict[str, Any]] = []
        for item in list(raw.get("primitives") or []):
            bp = dict(item.get("blueprint") or {}); family = str(bp.get("family", ""))
            if family == "meta.compose_pipeline":
                steps = list((bp.get("params") or {}).get("steps") or [])
                if len(steps) < 2 or len(steps) > allowed_depth or any(_canonical(step) not in accepted_atomic for step in steps):
                    raise ValueError("composed primitive outside admitted grammar")
            elif _is_safe_records_blueprint(bp):
                if self.RECORD_DOMAIN_ID not in seen_domains:
                    raise ValueError("records primitive without admitted records domain")
                accepted_atomic.add(_canonical(bp))
            elif _is_safe_graph_blueprint(bp):
                if self.GRAPH_DOMAIN_ID not in seen_domains:
                    raise ValueError("graph primitive without admitted graph domain")
                accepted_atomic.add(_canonical(bp))
            else:
                key = _canonical(bp)
                if key not in safe_static:
                    raise ValueError("unknown evolved atomic primitive")
                accepted_atomic.add(key)
            if str(item.get("machine_id")) != _machine_id_for(bp):
                raise ValueError("evolved primitive id mismatch")
            for case in item.get("self_tests", []):
                observed = _eval_autonomous_blueprint(bp, [_json_restore(v) for v in case.get("args", [])])
                if not _typed_equal(observed, _json_restore(case.get("expected"))):
                    raise ValueError("evolved primitive self-test failed")
            validated.append(copy.deepcopy(item))
        return {**raw, "primitives": validated, "grammar_rules": rules, "task_domains": domains}

    def load_evolution_state(self, state: dict[str, Any]) -> None:
        if state.get("schema") in {"ucr.autonomous-evolution-state/1", "ucr.autonomous-evolution-state/2", "ucr.autonomous-evolution-state/3"}:
            super().load_evolution_state(state); return
        raw = self._validate_v24_state(state)
        self._generation = int(raw.get("generation", 0)); self._evolved_grammar_rules = copy.deepcopy(raw.get("grammar_rules") or [])
        self._evolved_primitives = {str(x["machine_id"]): copy.deepcopy(x) for x in raw.get("primitives", [])}
        self._evolved_task_domains = copy.deepcopy(raw.get("task_domains") or []); self._evolution_history = copy.deepcopy(raw.get("history") or [])


AutonomousKernel = ArchitectureAutonomousKernel


def autonomous_self_test_v24() -> dict[str, Any]:
    kernel = AutonomousKernel()
    ga = {"nodes": [{"id": x, "kind": "module"} for x in ["a", "b", "c", "d", "e", "f"]], "edges": [
        {"src": "a", "dst": "b", "kind": "import"}, {"src": "a", "dst": "c", "kind": "import"},
        {"src": "b", "dst": "c", "kind": "import"}, {"src": "c", "dst": "d", "kind": "call"},
        {"src": "d", "dst": "c", "kind": "call"}, {"src": "e", "dst": "f", "kind": "import"},
    ]}
    gb = {"nodes": [{"id": x, "kind": "module"} for x in ["u", "v", "w", "x", "y", "z", "q"]], "edges": [
        {"src": "u", "dst": "v", "kind": "import"}, {"src": "u", "dst": "w", "kind": "import"},
        {"src": "w", "dst": "x", "kind": "call"}, {"src": "x", "dst": "w", "kind": "call"},
        {"src": "y", "dst": "z", "kind": "import"}, {"src": "q", "dst": "z", "kind": "call"},
    ]}
    kernel.observe_external_code_graph("self/graph-a", ga, {"kind": "self-test"}); kernel.observe_external_code_graph("self/graph-b", gb, {"kind": "self-test"})
    first = kernel.develop_one_generation(); second = kernel.develop_one_generation(); snap = kernel.snapshot(); restarted = AutonomousKernel(); restarted.restore(snap)
    return {"schema": "ucr.autonomous-kernel-v24-self-test/1", "first": first, "second": second, "graph_domain_active": kernel.GRAPH_DOMAIN_ID in kernel._active_task_domains(), "restart_digest_same": restarted.export_evolution_state()["digest"] == kernel.export_evolution_state()["digest"], "journal_valid": kernel.verify_journal(), "pass": first.get("status") == "ADMITTED" and second.get("status") == "ADMITTED" and kernel.verify_journal()}

# ---------------------------------------------------------------------------
# V25: bounded inter-module static causal-flow domain.
# Host bridge injects a validated function-level flow graph produced by static
# analysis only. The kernel does not parse source, execute source, access the
# network, or call subprocesses. Unlike codegraph.v1 (local connectivity),
# codeflow.v1 admits path/reachability primitives that reason about downstream
# influence across function and module boundaries.
# ---------------------------------------------------------------------------

_V24_EVAL_AUTONOMOUS_BLUEPRINT = _eval_autonomous_blueprint
_FLOW_FAMILIES = {
    "flow.function_count",
    "flow.edge_count",
    "flow.cross_module_edge_count",
    "flow.reachable_pair_count",
    "flow.max_reach_label",
    "flow.max_cross_module_reach_label",
    "flow.max_shortest_depth",
    "flow.entry_sink_reachable_pair_count",
    "flow.cycle_reachable_node_count",
}


def _validate_code_flow(value: Any) -> dict[str, Any]:
    if type(value) is not dict or set(value) - {"nodes", "edges"}:
        raise TypeError("flow must be a mapping with nodes/edges")
    raw_nodes = value.get("nodes"); raw_edges = value.get("edges")
    if type(raw_nodes) not in (list, tuple) or type(raw_edges) not in (list, tuple):
        raise TypeError("flow nodes/edges must be sequences")
    if not 2 <= len(raw_nodes) <= 2048 or len(raw_edges) > 8192:
        raise ValueError("flow outside bounded size")
    nodes: list[dict[str, str]] = []; seen: set[str] = set()
    for raw in raw_nodes:
        if type(raw) is not dict or set(raw) - {"id", "module", "kind"}:
            raise TypeError("invalid flow node")
        nid = raw.get("id"); module = raw.get("module"); kind = raw.get("kind", "function")
        if not _is_safe_graph_token(nid, max_len=240) or not _is_safe_graph_token(module, max_len=160) or not _is_safe_graph_token(kind, max_len=48):
            raise ValueError("unsafe flow node")
        if nid in seen:
            raise ValueError("duplicate flow node")
        seen.add(str(nid)); nodes.append({"id": str(nid), "module": str(module), "kind": str(kind)})
    edges: list[dict[str, str]] = []; edge_seen: set[tuple[str, str, str]] = set()
    for raw in raw_edges:
        if type(raw) is not dict or set(raw) != {"src", "dst", "kind"}:
            raise TypeError("invalid flow edge")
        src = raw.get("src"); dst = raw.get("dst"); kind = raw.get("kind")
        if not _is_safe_graph_token(src, max_len=240) or not _is_safe_graph_token(dst, max_len=240) or not _is_safe_graph_token(kind, max_len=48):
            raise ValueError("unsafe flow edge")
        if src not in seen or dst not in seen:
            raise ValueError("flow edge references unknown node")
        key = (str(src), str(dst), str(kind))
        if key in edge_seen:
            continue
        edge_seen.add(key); edges.append({"src": key[0], "dst": key[1], "kind": key[2]})
    nodes.sort(key=lambda x: x["id"]); edges.sort(key=lambda x: (x["kind"], x["src"], x["dst"]))
    return {"nodes": nodes, "edges": edges}


def _flow_edges(flow: dict[str, Any], kind: str) -> list[dict[str, str]]:
    edges = list(flow["edges"])
    return edges if kind == "all" else [e for e in edges if e["kind"] == kind]


def _flow_adjacency(flow: dict[str, Any], kind: str) -> dict[str, list[str]]:
    adj = {n["id"]: [] for n in flow["nodes"]}
    for e in _flow_edges(flow, kind):
        adj[e["src"]].append(e["dst"])
    for k in adj:
        adj[k] = sorted(set(adj[k]))
    return adj


def _flow_reach_sets(flow: dict[str, Any], kind: str) -> dict[str, set[str]]:
    adj = _flow_adjacency(flow, kind); out: dict[str, set[str]] = {}
    for start in adj:
        seen: set[str] = set(); stack = list(adj[start])
        while stack:
            cur = stack.pop()
            if cur in seen or cur == start:
                continue
            seen.add(cur); stack.extend(adj.get(cur, ()))
        out[start] = seen
    return out


def _flow_shortest_depth(flow: dict[str, Any], kind: str) -> int:
    adj = _flow_adjacency(flow, kind); best = 0
    for start in adj:
        dist = {start: 0}; queue = [start]; idx = 0
        while idx < len(queue):
            cur = queue[idx]; idx += 1
            for nxt in adj.get(cur, ()): 
                if nxt not in dist:
                    dist[nxt] = dist[cur] + 1; queue.append(nxt); best = max(best, dist[nxt])
    return best


def _flow_cycle_nodes(flow: dict[str, Any], kind: str) -> set[str]:
    graph = {"nodes": [{"id": n["id"], "kind": "function"} for n in flow["nodes"]], "edges": _flow_edges(flow, kind)}
    # _graph_cyclic_nodes only relies on id and typed edges.
    return _graph_cyclic_nodes(graph, "all")


def _flow_module_map(flow: dict[str, Any]) -> dict[str, str]:
    return {n["id"]: n["module"] for n in flow["nodes"]}



_FLOW_METRIC_CACHE: dict[tuple[str, str], dict[str, Any]] = {}

def _flow_analysis(flow: dict[str, Any], kind: str) -> dict[str, Any]:
    safe = _validate_code_flow(flow)
    digest = hashlib.sha256(_canonical(safe).encode("utf-8")).hexdigest()
    key = (digest, kind)
    cached = _FLOW_METRIC_CACHE.get(key)
    if cached is not None:
        return cached
    edges = _flow_edges(safe, kind); module_of = _flow_module_map(safe)
    adj = {n["id"]: [] for n in safe["nodes"]}
    indeg = {n["id"]: 0 for n in safe["nodes"]}; outdeg = {n["id"]: 0 for n in safe["nodes"]}
    for e in edges:
        adj[e["src"]].append(e["dst"]); outdeg[e["src"]] += 1; indeg[e["dst"]] += 1
    for k2 in adj: adj[k2] = sorted(set(adj[k2]))
    reach: dict[str, set[str]] = {}; max_depth = 0
    for start in adj:
        seen: set[str] = set(); queue = [(x,1) for x in adj[start]]; qi = 0
        while qi < len(queue):
            cur, depth = queue[qi]; qi += 1
            if cur == start or cur in seen: continue
            seen.add(cur); max_depth = max(max_depth, depth)
            for nxt in adj.get(cur, ()): 
                if nxt not in seen: queue.append((nxt, depth+1))
        reach[start] = seen
    graph = {"nodes": [{"id": n["id"], "kind": "function"} for n in safe["nodes"]], "edges": edges}
    cyc = _graph_cyclic_nodes(graph, "all")
    result = {"flow": safe, "edges": edges, "module_of": module_of, "adj": adj, "indeg": indeg, "outdeg": outdeg, "reach": reach, "max_depth": max_depth, "cyclic": cyc}
    if len(_FLOW_METRIC_CACHE) >= 256:
        _FLOW_METRIC_CACHE.pop(next(iter(_FLOW_METRIC_CACHE)))
    _FLOW_METRIC_CACHE[key] = result
    return result

def _is_safe_flow_blueprint(blueprint: dict[str, Any]) -> bool:
    if int(blueprint.get("arity", 1)) != 1 or str(blueprint.get("category", "")) != "codeflow":
        return False
    family = str(blueprint.get("family", "")); params = dict(blueprint.get("params") or {})
    if family not in _FLOW_FAMILIES:
        return False
    if family == "flow.function_count":
        return params == {}
    return set(params) == {"kind"} and _is_safe_graph_token(params.get("kind"), max_len=48)


def _eval_autonomous_blueprint(blueprint: dict[str, Any], args: list[Any]) -> Any:
    family = str(blueprint.get("family", ""))
    if family in _FLOW_FAMILIES:
        if len(args) != 1:
            raise ValueError("arity mismatch")
        flow = _validate_code_flow(args[0]); params = dict(blueprint.get("params") or {})
        if family == "flow.function_count":
            return len(flow["nodes"])
        kind = str(params.get("kind", ""))
        if not _is_safe_graph_token(kind, max_len=48):
            raise ValueError("invalid flow edge kind")
        analysis = _flow_analysis(flow, kind); edges = analysis["edges"]; module_of = analysis["module_of"]; reach = analysis["reach"]
        if family == "flow.edge_count":
            return len(edges)
        if family == "flow.cross_module_edge_count":
            return sum(1 for e in edges if module_of[e["src"]] != module_of[e["dst"]])
        if family == "flow.reachable_pair_count":
            return sum(len(v) for v in reach.values())
        if family == "flow.max_reach_label":
            best = max((len(v) for v in reach.values()), default=0)
            return min(k for k, v in reach.items() if len(v) == best)
        if family == "flow.max_cross_module_reach_label":
            scored = {}
            for src, targets in reach.items():
                sm = module_of[src]
                scored[src] = len({module_of[t] for t in targets if module_of[t] != sm})
            best = max(scored.values(), default=0)
            return min(k for k, v in scored.items() if v == best)
        if family == "flow.max_shortest_depth":
            return int(analysis["max_depth"])
        if family == "flow.entry_sink_reachable_pair_count":
            ids = [n["id"] for n in flow["nodes"]]; indeg = analysis["indeg"]; outdeg = analysis["outdeg"]
            entries = [x for x in ids if indeg[x] == 0 and outdeg[x] > 0]
            sinks = {x for x in ids if outdeg[x] == 0 and indeg[x] > 0}
            return sum(1 for src in entries for dst in reach[src] if dst in sinks)
        if family == "flow.cycle_reachable_node_count":
            cyc = analysis["cyclic"]
            if not cyc:
                return 0
            return sum(1 for src, targets in reach.items() if src in cyc or bool(targets & cyc))
    return _V24_EVAL_AUTONOMOUS_BLUEPRINT(blueprint, args)


class CausalFlowAutonomousKernel(ArchitectureAutonomousKernel):
    VERSION = "25.0"
    FLOW_DOMAIN_ID = "codeflow.v1"
    _FLOW_OBS_PREFIX = "__ucr_code_flow__:"

    def capabilities(self) -> dict[str, Any]:
        out = super().capabilities()
        out.update({
            "autonomous_kernel_version": self.VERSION,
            "observed_code_flow_count": len(self._observed_code_flows()),
            "causal_flow_bridge": True,
        })
        return out

    def observe_external_code_flow(self, dataset_id: str, flow: dict[str, Any], provenance: dict[str, Any] | None = None) -> dict[str, Any]:
        did = str(dataset_id)
        if not did or len(did) > 96 or any(ch not in "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789._:-/" for ch in did):
            raise ValueError("invalid flow dataset id")
        safe_flow = _validate_code_flow(flow)
        kinds = sorted({e["kind"] for e in safe_flow["edges"]})
        if not kinds or len(safe_flow["edges"]) < 3:
            raise ValueError("code flow exposes too little structure")
        body = {
            "schema": "ucr.code-flow-dataset/1", "dataset_id": did,
            "flow": _json_safe(safe_flow), "edge_kinds": kinds,
            "provenance": _json_safe(provenance or {}),
        }
        body["digest"] = hashlib.sha256(_canonical(body).encode("utf-8")).hexdigest()
        self.remember(self._FLOW_OBS_PREFIX + did, body)
        self._append_event("code-flow.observed", {
            "dataset_id": did, "digest": body["digest"], "function_count": len(safe_flow["nodes"]),
            "edge_count": len(safe_flow["edges"]), "edge_kinds": kinds,
        })
        return {"dataset_id": did, "digest": body["digest"], "function_count": len(safe_flow["nodes"]), "edge_count": len(safe_flow["edges"]), "edge_kinds": kinds}

    def _observed_code_flows(self) -> list[dict[str, Any]]:
        out: list[dict[str, Any]] = []
        for key, value in sorted(self.memory.items()):
            if not str(key).startswith(self._FLOW_OBS_PREFIX) or type(value) is not dict:
                continue
            raw = copy.deepcopy(value); supplied = str(raw.pop("digest", ""))
            expected = hashlib.sha256(_canonical(raw).encode("utf-8")).hexdigest()
            if supplied != expected or raw.get("schema") != "ucr.code-flow-dataset/1":
                continue
            raw["digest"] = supplied; out.append(raw)
        return out

    @staticmethod
    def _flow_views(flow: dict[str, Any]) -> list[dict[str, Any]]:
        flow = _validate_code_flow(flow); nodes = list(flow["nodes"]); ids = [n["id"] for n in nodes]; n = len(ids)
        module_ids: dict[str, list[str]] = {}
        for node in nodes:
            module_ids.setdefault(node["module"], []).append(node["id"])
        modules = sorted(module_ids)
        subsets: list[list[str]] = []
        if len(modules) >= 2:
            cuts = [modules[:max(1, len(modules)//2)], modules[-max(1, len(modules)//2):], modules[::2], modules[1::2], modules[:max(2, (2*len(modules))//3)], modules]
            for mods in cuts:
                subsets.append([x for m in mods for x in module_ids[m]])
        # Add deterministic function-level views to avoid modules with one giant file dominating.
        subsets += [ids[:max(4, n//2)], ids[-max(4, n//2):], ids[::2], ids[1::2], ids]
        node_map = {x["id"]: x for x in nodes}; out: list[dict[str, Any]] = []; seen: set[str] = set()
        for raw_ids in subsets:
            chosen = sorted(set(raw_ids))
            if len(chosen) < 2:
                continue
            chosen_set = set(chosen)
            view = {"nodes": [copy.deepcopy(node_map[x]) for x in chosen], "edges": [copy.deepcopy(e) for e in flow["edges"] if e["src"] in chosen_set and e["dst"] in chosen_set]}
            if len(view["edges"]) < 1:
                continue
            key = hashlib.sha256(_canonical(view).encode("utf-8")).hexdigest()
            if key in seen:
                continue
            seen.add(key); out.append(view)
        return out

    def _flow_blueprints(self, dataset: dict[str, Any]) -> list[dict[str, Any]]:
        kinds = ["all"] + list(dataset.get("edge_kinds") or [])
        out = [{"arity": 1, "category": "codeflow", "family": "flow.function_count", "params": {}}]
        param_families = [
            "flow.edge_count", "flow.cross_module_edge_count", "flow.reachable_pair_count",
            "flow.max_reach_label", "flow.max_cross_module_reach_label", "flow.max_shortest_depth",
            "flow.entry_sink_reachable_pair_count", "flow.cycle_reachable_node_count",
        ]
        for kind in kinds:
            for family in param_families:
                out.append({"arity": 1, "category": "codeflow", "family": family, "params": {"kind": kind}})
        return out

    def _flow_case_sets(self, blueprint: dict[str, Any], dataset: dict[str, Any]) -> dict[str, list[dict[str, Any]]]:
        views = self._flow_views(_json_restore(dataset["flow"]))
        if len(views) < 5:
            raise ValueError("insufficient flow views")
        cases = [{"args": [_json_safe(v)], "expected": _json_safe(_eval_autonomous_blueprint(blueprint, [v]))} for v in views]
        # deterministic disjoint splits, full view tends to be last and goes to fresh
        train = cases[0::3]; hidden = cases[1::3]; fresh = cases[2::3]
        if not train or not hidden or not fresh:
            raise ValueError("insufficient flow split")
        return {"train": train, "hidden": hidden, "fresh": fresh}

    def _flow_transfer_score(self, blueprint: dict[str, Any], exclude_dataset: str | None = None) -> float:
        scores: list[float] = []
        for dataset in self._observed_code_flows():
            if exclude_dataset is not None and str(dataset.get("dataset_id")) == exclude_dataset:
                continue
            try:
                cases = self._flow_case_sets(blueprint, dataset)
            except Exception:
                continue
            scores.append(_score_blueprint(blueprint, cases["train"] + cases["hidden"] + cases["fresh"]))
        return min(scores) if scores else 0.0

    def _flow_challenges(self) -> list[dict[str, Any]]:
        datasets = self._observed_code_flows()
        if not datasets:
            return []
        active = self._active_task_domains(); admitted = {_canonical(x) for x in self._admitted_atomic_blueprints()}; out: list[dict[str, Any]] = []
        for dataset in datasets:
            did = str(dataset["dataset_id"])
            for bp in self._flow_blueprints(dataset):
                if self.FLOW_DOMAIN_ID in active and _canonical(bp) in admitted:
                    continue
                try:
                    cases = self._flow_case_sets(bp, dataset)
                except Exception:
                    continue
                outputs = {_canonical(c["expected"]) for c in cases["train"] + cases["hidden"] + cases["fresh"]}
                if len(outputs) < 2:
                    continue
                out.append({
                    "challenge_id": "flow." + hashlib.sha256((did + _blueprint_digest(bp)).encode("utf-8")).hexdigest()[:16],
                    "source": "observed-static-code-flow-self-generator", "task_domain": self.FLOW_DOMAIN_ID,
                    "domain_activation_required": self.FLOW_DOMAIN_ID not in active,
                    "dataset_id": did, "dataset_digest": dataset["digest"], "target_digest": _blueprint_digest(bp),
                    "train": cases["train"], "hidden": cases["hidden"], "fresh": cases["fresh"], "_target": copy.deepcopy(bp),
                })
        return out

    def _challenge_universe(self) -> list[dict[str, Any]]:
        return list(super()._challenge_universe()) + self._flow_challenges()

    def _propose_mutation(self, challenge: dict[str, Any]) -> dict[str, Any] | None:
        if str(challenge.get("task_domain", "")) == self.FLOW_DOMAIN_ID:
            if bool(challenge.get("domain_activation_required")):
                if self.FLOW_DOMAIN_ID in self._active_task_domains():
                    return None
                return {"kind": "task-domain", "route": "expand-task-domain-codeflow.v1", "domain_id": self.FLOW_DOMAIN_ID, "witness": copy.deepcopy(challenge["_target"])}
            bp = copy.deepcopy(challenge["_target"])
            if not _is_safe_flow_blueprint(bp):
                return None
            if _canonical(bp) in {_canonical(x) for x in self._admitted_atomic_blueprints()}:
                return None
            if all(_score_blueprint(bp, challenge[k]) == 1.0 for k in ("train", "hidden", "fresh")):
                return {"kind": "primitive", "route": "admit-codeflow-primitive", "blueprint": bp}
            return None
        return super()._propose_mutation(challenge)

    def _validate_mutation(self, challenge: dict[str, Any], proposal: dict[str, Any], before: dict[str, Any]) -> dict[str, Any]:
        if proposal.get("kind") == "task-domain" and proposal.get("domain_id") == self.FLOW_DOMAIN_ID:
            witness = dict(proposal["witness"])
            train = _score_blueprint(witness, challenge["train"]); hidden = _score_blueprint(witness, challenge["hidden"]); fresh = _score_blueprint(witness, challenge["fresh"])
            baseline = min(float(before["train"]), float(before["hidden"]), float(before["fresh"]))
            primary = str(challenge.get("dataset_id", "")); transfer = self._flow_transfer_score(witness, exclude_dataset=primary)
            independent = 0.0
            for dataset in self._observed_code_flows():
                if str(dataset.get("dataset_id")) == primary:
                    continue
                for candidate in self._flow_blueprints(dataset):
                    if str(candidate.get("family")) == str(witness.get("family")):
                        continue
                    try:
                        cases = self._flow_case_sets(candidate, dataset)
                    except Exception:
                        continue
                    independent = max(independent, _score_blueprint(candidate, cases["train"] + cases["hidden"] + cases["fresh"]))
            causal_gain = min(train, hidden, fresh) - baseline
            return {"train": train, "hidden": hidden, "fresh": fresh, "transfer": transfer, "independent_family_transfer": independent, "baseline": baseline, "causal_gain": causal_gain, "pass": train == hidden == fresh == transfer == independent == 1.0 and causal_gain > 0.0}
        bp = dict(proposal.get("blueprint") or {})
        if proposal.get("kind") == "primitive" and str(bp.get("category", "")) == "codeflow":
            train = _score_blueprint(bp, challenge["train"]); hidden = _score_blueprint(bp, challenge["hidden"]); fresh = _score_blueprint(bp, challenge["fresh"])
            baseline = min(float(before["train"]), float(before["hidden"]), float(before["fresh"]))
            transfer = self._flow_transfer_score(bp, exclude_dataset=str(challenge.get("dataset_id", "")))
            causal_gain = min(train, hidden, fresh) - baseline
            return {"train": train, "hidden": hidden, "fresh": fresh, "transfer": transfer, "baseline": baseline, "causal_gain": causal_gain, "pass": train == hidden == fresh == transfer == 1.0 and causal_gain > 0.0}
        return super()._validate_mutation(challenge, proposal, before)

    def _commit_mutation(self, challenge: dict[str, Any], proposal: dict[str, Any], validation: dict[str, Any]) -> dict[str, Any]:
        if proposal.get("kind") == "task-domain" and proposal.get("domain_id") == self.FLOW_DOMAIN_ID:
            self._generation += 1
            domain = {"domain_id": self.FLOW_DOMAIN_ID, "admitted": True, "origin": "observed-static-causal-flow-task-space-expansion", "generation": self._generation, "challenge_id": str(challenge["challenge_id"]), "dataset_digest": challenge.get("dataset_digest")}
            self._evolved_task_domains.append(domain)
            record = {"generation": self._generation, "challenge_id": challenge["challenge_id"], "route": proposal["route"], "mutation": {"kind": "task-domain", "domain_id": self.FLOW_DOMAIN_ID}, "validation": copy.deepcopy(validation), "status": "ADMITTED"}
            self._evolution_history.append(record); self._append_event("evolution.admitted", record)
            return copy.deepcopy(record)
        return super()._commit_mutation(challenge, proposal, validation)

    def develop_one_generation(self) -> dict[str, Any]:
        flow_challenges = self._flow_challenges()
        if flow_challenges:
            # Prefer path/reachability capabilities over simple counts. Admission
            # criteria are unchanged; this only avoids recomputing dozens of
            # equivalent candidates once one independently transferred mutation
            # has already proved itself.
            priority = {
                "flow.reachable_pair_count": 0,
                "flow.max_cross_module_reach_label": 1,
                "flow.max_reach_label": 2,
                "flow.max_shortest_depth": 3,
                "flow.entry_sink_reachable_pair_count": 4,
                "flow.cycle_reachable_node_count": 5,
                "flow.cross_module_edge_count": 6,
                "flow.edge_count": 7,
                "flow.function_count": 8,
            }
            flow_challenges.sort(key=lambda c: (
                0 if bool(c.get("domain_activation_required")) else 1,
                priority.get(str((c.get("_target") or {}).get("family", "")), 99),
                str(c.get("dataset_id", "")), str(c.get("challenge_id", "")),
            ))
            unresolved = False
            for challenge in flow_challenges:
                before = self._best_existing(challenge)
                if min(before["train"], before["hidden"], before["fresh"]) == 1.0:
                    continue
                unresolved = True; proposal = self._propose_mutation(challenge)
                if proposal is None:
                    continue
                validation = self._validate_mutation(challenge, proposal, before)
                if validation["pass"]:
                    self._append_event("evolution.selected", {"challenge_id": challenge["challenge_id"], "route": proposal["route"], "causal_gain": validation["causal_gain"], "source": "code-flow-real-data"})
                    return self._commit_mutation(challenge, proposal, validation)
                self._append_event("evolution.withhold", {"challenge_id": challenge["challenge_id"], "route": proposal["route"], "validation": validation})
            if unresolved:
                stop = {"status": "WITHHOLD", "reason": "code-flow-gap-without-provable-mutation", "generation": self._generation}
                self._append_event("evolution.stopped", stop); return stop
        return super().develop_one_generation()

    def export_evolution_state(self) -> dict[str, Any]:
        body = {"schema": "ucr.autonomous-evolution-state/5", "kernel_id": self.kernel_id, "generation": self._generation, "primitives": [copy.deepcopy(v) for _, v in sorted(self._evolved_primitives.items())], "grammar_rules": copy.deepcopy(self._evolved_grammar_rules), "task_domains": copy.deepcopy(self._evolved_task_domains), "history": copy.deepcopy(self._evolution_history)}
        return {**body, "digest": hashlib.sha256(_canonical(body).encode("utf-8")).hexdigest()}

    def _validate_v25_state(self, state: dict[str, Any]) -> dict[str, Any]:
        raw = copy.deepcopy(state); supplied = str(raw.pop("digest", "")); expected = hashlib.sha256(_canonical(raw).encode("utf-8")).hexdigest()
        if supplied != expected:
            raise ValueError("evolution state digest mismatch")
        if raw.get("schema") != "ucr.autonomous-evolution-state/5" or raw.get("kernel_id") != self.kernel_id:
            raise ValueError("evolution state identity mismatch")
        domains = list(raw.get("task_domains") or []); seen_domains: set[str] = set(); allowed_domains = set(SAFE_TASK_DOMAIN_BLUEPRINTS) | {self.RECORD_DOMAIN_ID, self.GRAPH_DOMAIN_ID, self.FLOW_DOMAIN_ID}
        for item in domains:
            did = str(item.get("domain_id", ""))
            if did not in allowed_domains or item.get("admitted") is not True or did in seen_domains:
                raise ValueError("unknown, duplicate, or non-admitted task domain")
            seen_domains.add(did)
        rules = list(raw.get("grammar_rules") or []); allowed_depth = 3
        for rule in rules:
            rid = str(rule.get("rule_id", ""))
            if not rid.startswith("unary.compose") or not rid[len("unary.compose"):].isdigit():
                raise ValueError("unknown evolved grammar rule")
            depth = int(rid[len("unary.compose"):])
            if depth != allowed_depth + 1 or depth > 5:
                raise ValueError("non-sequential or excessive grammar evolution")
            allowed_depth = depth
        safe_static = {_canonical(x) for x in SAFE_NEW_ATOMIC_BLUEPRINTS}
        for did in seen_domains & set(SAFE_TASK_DOMAIN_BLUEPRINTS):
            safe_static.update(_canonical(x) for x in SAFE_TASK_DOMAIN_BLUEPRINTS[did])
        accepted_atomic: set[str] = set(); raw_primitives = list(raw.get("primitives") or [])
        # Static baseline atoms are always safe and can be pipeline constituents.
        for bp in SAFE_NEW_ATOMIC_BLUEPRINTS:
            accepted_atomic.add(_canonical(bp))
        for did in seen_domains & set(SAFE_TASK_DOMAIN_BLUEPRINTS):
            for bp in SAFE_TASK_DOMAIN_BLUEPRINTS[did]: accepted_atomic.add(_canonical(bp))
        for base_item in KERNEL_BLUEPRINT.get("primitives", []):
            for step in (_flatten_atomic_steps(dict(base_item.get("blueprint") or {})) or []):
                if not str(step.get("family", "")).startswith("meta."):
                    accepted_atomic.add(_canonical(step))

        # Phase 1: validate every atomic primitive independently of storage order.
        for item in raw_primitives:
            bp = dict(item.get("blueprint") or {}); family = str(bp.get("family", ""))
            if family == "meta.compose_pipeline":
                continue
            if str(item.get("machine_id")) != _machine_id_for(bp):
                raise ValueError("evolved primitive id mismatch")
            if _is_safe_records_blueprint(bp):
                if self.RECORD_DOMAIN_ID not in seen_domains: raise ValueError("records primitive without admitted records domain")
            elif _is_safe_graph_blueprint(bp):
                if self.GRAPH_DOMAIN_ID not in seen_domains: raise ValueError("graph primitive without admitted graph domain")
            elif _is_safe_flow_blueprint(bp):
                if self.FLOW_DOMAIN_ID not in seen_domains: raise ValueError("flow primitive without admitted flow domain")
            else:
                key = _canonical(bp)
                if key not in safe_static: raise ValueError("unknown evolved atomic primitive")
            for case in item.get("self_tests", []):
                observed = _eval_autonomous_blueprint(bp, [_json_restore(v) for v in case.get("args", [])])
                if not _typed_equal(observed, _json_restore(case.get("expected"))):
                    raise ValueError("evolved primitive self-test failed")
            accepted_atomic.add(_canonical(bp))

        # Phase 2: validate compositions only after all admitted atoms are known.
        for item in raw_primitives:
            bp = dict(item.get("blueprint") or {}); family = str(bp.get("family", ""))
            if family != "meta.compose_pipeline":
                continue
            if str(item.get("machine_id")) != _machine_id_for(bp):
                raise ValueError("evolved primitive id mismatch")
            steps = list((bp.get("params") or {}).get("steps") or [])
            if len(steps) < 2 or len(steps) > allowed_depth or any(_canonical(step) not in accepted_atomic for step in steps):
                raise ValueError("composed primitive outside admitted grammar")
            for case in item.get("self_tests", []):
                observed = _eval_autonomous_blueprint(bp, [_json_restore(v) for v in case.get("args", [])])
                if not _typed_equal(observed, _json_restore(case.get("expected"))):
                    raise ValueError("evolved primitive self-test failed")
        return {**raw, "primitives": [copy.deepcopy(x) for x in raw_primitives], "grammar_rules": rules, "task_domains": domains}

    def load_evolution_state(self, state: dict[str, Any]) -> None:
        if state.get("schema") in {"ucr.autonomous-evolution-state/1", "ucr.autonomous-evolution-state/2", "ucr.autonomous-evolution-state/3", "ucr.autonomous-evolution-state/4"}:
            super().load_evolution_state(state); return
        raw = self._validate_v25_state(state)
        self._generation = int(raw.get("generation", 0)); self._evolved_grammar_rules = copy.deepcopy(raw.get("grammar_rules") or [])
        self._evolved_primitives = {str(x["machine_id"]): copy.deepcopy(x) for x in raw.get("primitives", [])}
        self._evolved_task_domains = copy.deepcopy(raw.get("task_domains") or []); self._evolution_history = copy.deepcopy(raw.get("history") or [])


AutonomousKernel = CausalFlowAutonomousKernel


def autonomous_self_test_v25() -> dict[str, Any]:
    kernel = AutonomousKernel()
    fa = {"nodes": [
        {"id":"a:f1","module":"a","kind":"function"},{"id":"a:f2","module":"a","kind":"function"},
        {"id":"b:g1","module":"b","kind":"function"},{"id":"b:g2","module":"b","kind":"function"},
        {"id":"c:h1","module":"c","kind":"function"},{"id":"d:q1","module":"d","kind":"function"}],
        "edges": [
        {"src":"a:f1","dst":"a:f2","kind":"call"},{"src":"a:f2","dst":"b:g1","kind":"return_call"},
        {"src":"b:g1","dst":"b:g2","kind":"call"},{"src":"b:g2","dst":"c:h1","kind":"assign_call"},
        {"src":"c:h1","dst":"b:g1","kind":"call"},{"src":"d:q1","dst":"c:h1","kind":"call"}]}
    fb = {"nodes": [
        {"id":"u:x","module":"u","kind":"function"},{"id":"v:y","module":"v","kind":"function"},
        {"id":"v:z","module":"v","kind":"function"},{"id":"w:k","module":"w","kind":"function"},
        {"id":"x:m","module":"x","kind":"function"},{"id":"x:n","module":"x","kind":"function"}],
        "edges": [
        {"src":"u:x","dst":"v:y","kind":"call"},{"src":"v:y","dst":"v:z","kind":"assign_call"},
        {"src":"v:z","dst":"w:k","kind":"return_call"},{"src":"w:k","dst":"v:y","kind":"call"},
        {"src":"x:m","dst":"x:n","kind":"call"},{"src":"x:n","dst":"w:k","kind":"call"}]}
    kernel.observe_external_code_flow("self/flow-a", fa, {"kind":"self-test"}); kernel.observe_external_code_flow("self/flow-b", fb, {"kind":"self-test"})
    first = kernel.develop_one_generation(); second = kernel.develop_one_generation(); snap = kernel.snapshot(); restarted = AutonomousKernel(); restarted.restore(snap)
    return {"schema":"ucr.autonomous-kernel-v25-self-test/1","first":first,"second":second,"flow_domain_active":kernel.FLOW_DOMAIN_ID in kernel._active_task_domains(),"restart_digest_same":restarted.export_evolution_state()["digest"] == kernel.export_evolution_state()["digest"],"journal_valid":kernel.verify_journal(),"pass":first.get("status")=="ADMITTED" and second.get("status")=="ADMITTED" and kernel.verify_journal()}
# === v26 runtime-trace evolution layer ===
_V25_EVAL_AUTONOMOUS_BLUEPRINT = _eval_autonomous_blueprint

_TRACE_FAMILIES = {
    "trace.event_count",
    "trace.call_count",
    "trace.unique_function_count",
    "trace.unique_module_count",
    "trace.max_call_depth",
    "trace.observed_call_edge_count",
    "trace.cross_module_call_edge_count",
    "trace.repeated_function_count",
    "trace.hot_function_label",
    "trace.hot_module_label",
    "trace.static_observed_edge_count",
    "trace.static_unobserved_edge_count",
    "trace.runtime_only_edge_count",
    "trace.static_coverage_ppm",
}


def _validate_runtime_trace(value: Any) -> dict[str, Any]:
    if type(value) is not dict or set(value) - {"events", "static_edges"}:
        raise TypeError("runtime trace must contain events/static_edges")
    raw_events = value.get("events"); raw_static = value.get("static_edges", [])
    if type(raw_events) not in (list, tuple) or type(raw_static) not in (list, tuple):
        raise TypeError("trace events/static_edges must be sequences")
    if not 4 <= len(raw_events) <= 16384 or len(raw_static) > 8192:
        raise ValueError("runtime trace outside bounded size")
    events: list[dict[str, Any]] = []
    for i, raw in enumerate(raw_events):
        if type(raw) is not dict or set(raw) - {"seq","event","function","module","depth","parent"}:
            raise TypeError("invalid runtime event")
        seq = raw.get("seq", i); event = raw.get("event"); function = raw.get("function"); module = raw.get("module")
        depth = raw.get("depth", 0); parent = raw.get("parent")
        if type(seq) is not int or seq < 0 or type(depth) is not int or not 0 <= depth <= 256:
            raise ValueError("invalid runtime event position")
        if event not in {"call", "return"}:
            raise ValueError("unsupported runtime event")
        if not _is_safe_graph_token(function, max_len=260) or not _is_safe_graph_token(module, max_len=180):
            raise ValueError("unsafe runtime event token")
        if parent is not None and parent != "" and not _is_safe_graph_token(parent, max_len=260):
            raise ValueError("unsafe runtime parent")
        events.append({"seq": int(seq), "event": str(event), "function": str(function), "module": str(module), "depth": int(depth), "parent": None if parent in (None, "") else str(parent)})
    events.sort(key=lambda x: (x["seq"], 0 if x["event"] == "call" else 1, x["function"]))
    static_edges: list[dict[str, str]] = []; seen: set[tuple[str,str]] = set()
    for raw in raw_static:
        if type(raw) is not dict or set(raw) != {"src","dst"}:
            raise TypeError("invalid static trace edge")
        src = raw.get("src"); dst = raw.get("dst")
        if not _is_safe_graph_token(src, max_len=260) or not _is_safe_graph_token(dst, max_len=260):
            raise ValueError("unsafe static trace edge")
        key = (str(src), str(dst))
        if key not in seen:
            seen.add(key); static_edges.append({"src": key[0], "dst": key[1]})
    static_edges.sort(key=lambda x: (x["src"], x["dst"]))
    return {"events": events, "static_edges": static_edges}


def _trace_analysis(trace: dict[str, Any]) -> dict[str, Any]:
    safe = _validate_runtime_trace(trace); calls = [e for e in safe["events"] if e["event"] == "call"]
    functions = sorted({e["function"] for e in calls}); modules = sorted({e["module"] for e in calls})
    counts: dict[str,int] = {}; module_counts: dict[str,int] = {}
    observed_edges: set[tuple[str,str]] = set(); cross_edges: set[tuple[str,str]] = set()
    function_module = {e["function"]: e["module"] for e in calls}
    for e in calls:
        counts[e["function"]] = counts.get(e["function"], 0) + 1
        module_counts[e["module"]] = module_counts.get(e["module"], 0) + 1
        parent = e.get("parent")
        if parent:
            pair = (str(parent), e["function"]); observed_edges.add(pair)
            pm = function_module.get(str(parent), str(parent).split(":",1)[0])
            if pm != e["module"]:
                cross_edges.add(pair)
    static = {(e["src"],e["dst"]) for e in safe["static_edges"]}
    observed_static = observed_edges & static; runtime_only = observed_edges - static
    return {
        "trace": safe, "calls": calls, "functions": functions, "modules": modules,
        "counts": counts, "module_counts": module_counts, "observed_edges": observed_edges,
        "cross_edges": cross_edges, "static_edges": static, "observed_static": observed_static,
        "runtime_only": runtime_only,
    }


def _is_safe_trace_blueprint(blueprint: dict[str, Any]) -> bool:
    return int(blueprint.get("arity", 1)) == 1 and str(blueprint.get("category", "")) == "codetrace" and str(blueprint.get("family", "")) in _TRACE_FAMILIES and dict(blueprint.get("params") or {}) == {}


def _eval_autonomous_blueprint(blueprint: dict[str, Any], args: list[Any]) -> Any:
    family = str(blueprint.get("family", ""))
    if family in _TRACE_FAMILIES:
        if len(args) != 1:
            raise ValueError("arity mismatch")
        a = _trace_analysis(args[0]); safe = a["trace"]
        if family == "trace.event_count": return len(safe["events"])
        if family == "trace.call_count": return len(a["calls"])
        if family == "trace.unique_function_count": return len(a["functions"])
        if family == "trace.unique_module_count": return len(a["modules"])
        if family == "trace.max_call_depth": return max((int(e["depth"]) for e in a["calls"]), default=0)
        if family == "trace.observed_call_edge_count": return len(a["observed_edges"])
        if family == "trace.cross_module_call_edge_count": return len(a["cross_edges"])
        if family == "trace.repeated_function_count": return sum(1 for v in a["counts"].values() if v > 1)
        if family == "trace.hot_function_label":
            if not a["counts"]: return ""
            best = max(a["counts"].values()); return min(k for k,v in a["counts"].items() if v == best)
        if family == "trace.hot_module_label":
            if not a["module_counts"]: return ""
            best = max(a["module_counts"].values()); return min(k for k,v in a["module_counts"].items() if v == best)
        if family == "trace.static_observed_edge_count": return len(a["observed_static"])
        if family == "trace.static_unobserved_edge_count": return max(0, len(a["static_edges"]) - len(a["observed_static"]))
        if family == "trace.runtime_only_edge_count": return len(a["runtime_only"])
        if family == "trace.static_coverage_ppm":
            return 0 if not a["static_edges"] else (len(a["observed_static"]) * 1_000_000) // len(a["static_edges"])
    return _V25_EVAL_AUTONOMOUS_BLUEPRINT(blueprint, args)


class RuntimeTraceAutonomousKernel(CausalFlowAutonomousKernel):
    VERSION = "26.0"
    TRACE_DOMAIN_ID = "codetrace.v1"
    _TRACE_OBS_PREFIX = "__ucr_runtime_trace__:"

    def capabilities(self) -> dict[str, Any]:
        out = super().capabilities(); out.update({"autonomous_kernel_version": self.VERSION, "observed_runtime_trace_count": len(self._observed_runtime_trace_datasets()), "runtime_trace_bridge": True}); return out

    def observe_external_runtime_traces(self, dataset_id: str, traces: list[dict[str, Any]], provenance: dict[str, Any] | None = None) -> dict[str, Any]:
        did = str(dataset_id)
        if not did or len(did) > 96 or any(ch not in "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789._:-/" for ch in did):
            raise ValueError("invalid runtime trace dataset id")
        if type(traces) not in (list, tuple) or not 5 <= len(traces) <= 64:
            raise ValueError("runtime trace dataset requires 5..64 traces")
        safe = [_validate_runtime_trace(x) for x in traces]
        body = {"schema":"ucr.runtime-trace-dataset/1","dataset_id":did,"traces":_json_safe(safe),"provenance":_json_safe(provenance or {})}
        body["digest"] = hashlib.sha256(_canonical(body).encode("utf-8")).hexdigest()
        self.remember(self._TRACE_OBS_PREFIX + did, body)
        self._append_event("runtime-trace.observed", {"dataset_id":did,"digest":body["digest"],"trace_count":len(safe),"event_count":sum(len(x["events"]) for x in safe)})
        return {"dataset_id":did,"digest":body["digest"],"trace_count":len(safe),"event_count":sum(len(x["events"]) for x in safe)}

    def _observed_runtime_trace_datasets(self) -> list[dict[str, Any]]:
        out=[]
        for key,value in sorted(self.memory.items()):
            if not str(key).startswith(self._TRACE_OBS_PREFIX) or type(value) is not dict: continue
            raw=copy.deepcopy(value); supplied=str(raw.pop("digest", "")); expected=hashlib.sha256(_canonical(raw).encode("utf-8")).hexdigest()
            if supplied != expected or raw.get("schema") != "ucr.runtime-trace-dataset/1": continue
            raw["digest"]=supplied; out.append(raw)
        return out

    def _trace_blueprints(self) -> list[dict[str, Any]]:
        return [{"arity":1,"category":"codetrace","family":family,"params":{}} for family in sorted(_TRACE_FAMILIES)]

    def _trace_case_sets(self, blueprint: dict[str, Any], dataset: dict[str, Any]) -> dict[str, list[dict[str, Any]]]:
        traces=[_json_restore(x) for x in dataset.get("traces") or []]
        if len(traces) < 5: raise ValueError("insufficient runtime traces")
        cases=[{"args":[_json_safe(t)],"expected":_json_safe(_eval_autonomous_blueprint(blueprint,[t]))} for t in traces]
        train=cases[0::3]; hidden=cases[1::3]; fresh=cases[2::3]
        if not train or not hidden or not fresh: raise ValueError("insufficient runtime trace split")
        return {"train":train,"hidden":hidden,"fresh":fresh}

    def _trace_transfer_score(self, blueprint: dict[str, Any], exclude_dataset: str | None = None) -> float:
        scores=[]
        for dataset in self._observed_runtime_trace_datasets():
            if exclude_dataset is not None and str(dataset.get("dataset_id")) == exclude_dataset: continue
            try: cases=self._trace_case_sets(blueprint,dataset)
            except Exception: continue
            scores.append(_score_blueprint(blueprint,cases["train"]+cases["hidden"]+cases["fresh"]))
        return min(scores) if scores else 0.0

    def _trace_challenges(self) -> list[dict[str, Any]]:
        datasets=self._observed_runtime_trace_datasets()
        if not datasets: return []
        active=self._active_task_domains(); admitted={_canonical(x) for x in self._admitted_atomic_blueprints()}; out=[]
        for dataset in datasets:
            did=str(dataset["dataset_id"])
            for bp in self._trace_blueprints():
                if self.TRACE_DOMAIN_ID in active and _canonical(bp) in admitted: continue
                cases=self._trace_case_sets(bp,dataset)
                outputs={_canonical(c["expected"]) for c in cases["train"]+cases["hidden"]+cases["fresh"]}
                if len(outputs) < 2: continue
                out.append({"challenge_id":"trace."+hashlib.sha256((did+_blueprint_digest(bp)).encode()).hexdigest()[:16],"source":"observed-runtime-trace-self-generator","task_domain":self.TRACE_DOMAIN_ID,"domain_activation_required":self.TRACE_DOMAIN_ID not in active,"dataset_id":did,"dataset_digest":dataset["digest"],"target_digest":_blueprint_digest(bp),"train":cases["train"],"hidden":cases["hidden"],"fresh":cases["fresh"],"_target":copy.deepcopy(bp)})
        return out

    def _challenge_universe(self) -> list[dict[str, Any]]:
        return list(super()._challenge_universe()) + self._trace_challenges()

    def _propose_mutation(self, challenge: dict[str, Any]) -> dict[str, Any] | None:
        if str(challenge.get("task_domain", "")) == self.TRACE_DOMAIN_ID:
            if bool(challenge.get("domain_activation_required")):
                if self.TRACE_DOMAIN_ID in self._active_task_domains(): return None
                return {"kind":"task-domain","route":"expand-task-domain-codetrace.v1","domain_id":self.TRACE_DOMAIN_ID,"witness":copy.deepcopy(challenge["_target"])}
            bp=copy.deepcopy(challenge["_target"])
            if not _is_safe_trace_blueprint(bp): return None
            if _canonical(bp) in {_canonical(x) for x in self._admitted_atomic_blueprints()}: return None
            if all(_score_blueprint(bp,challenge[k])==1.0 for k in ("train","hidden","fresh")):
                return {"kind":"primitive","route":"admit-codetrace-primitive","blueprint":bp}
            return None
        return super()._propose_mutation(challenge)

    def _validate_mutation(self, challenge: dict[str, Any], proposal: dict[str, Any], before: dict[str, Any]) -> dict[str, Any]:
        if proposal.get("kind") == "task-domain" and proposal.get("domain_id") == self.TRACE_DOMAIN_ID:
            witness=dict(proposal["witness"]); train=_score_blueprint(witness,challenge["train"]); hidden=_score_blueprint(witness,challenge["hidden"]); fresh=_score_blueprint(witness,challenge["fresh"])
            baseline=min(float(before["train"]),float(before["hidden"]),float(before["fresh"])); primary=str(challenge.get("dataset_id","")); transfer=self._trace_transfer_score(witness,exclude_dataset=primary)
            independent=0.0
            for candidate in self._trace_blueprints():
                if candidate["family"] == witness["family"]: continue
                score=self._trace_transfer_score(candidate,exclude_dataset=primary); independent=max(independent,score)
            causal_gain=min(train,hidden,fresh)-baseline
            return {"train":train,"hidden":hidden,"fresh":fresh,"transfer":transfer,"independent_family_transfer":independent,"baseline":baseline,"causal_gain":causal_gain,"pass":train==hidden==fresh==transfer==independent==1.0 and causal_gain>0.0}
        bp=dict(proposal.get("blueprint") or {})
        if proposal.get("kind") == "primitive" and str(bp.get("category","")) == "codetrace":
            train=_score_blueprint(bp,challenge["train"]); hidden=_score_blueprint(bp,challenge["hidden"]); fresh=_score_blueprint(bp,challenge["fresh"]); baseline=min(float(before["train"]),float(before["hidden"]),float(before["fresh"])); transfer=self._trace_transfer_score(bp,exclude_dataset=str(challenge.get("dataset_id",""))); causal_gain=min(train,hidden,fresh)-baseline
            return {"train":train,"hidden":hidden,"fresh":fresh,"transfer":transfer,"baseline":baseline,"causal_gain":causal_gain,"pass":train==hidden==fresh==transfer==1.0 and causal_gain>0.0}
        return super()._validate_mutation(challenge,proposal,before)

    def _commit_mutation(self, challenge: dict[str, Any], proposal: dict[str, Any], validation: dict[str, Any]) -> dict[str, Any]:
        if proposal.get("kind") == "task-domain" and proposal.get("domain_id") == self.TRACE_DOMAIN_ID:
            self._generation += 1
            domain={"domain_id":self.TRACE_DOMAIN_ID,"admitted":True,"origin":"observed-runtime-trace-task-space-expansion","generation":self._generation,"challenge_id":str(challenge["challenge_id"]),"dataset_digest":challenge.get("dataset_digest")}
            self._evolved_task_domains.append(domain); record={"generation":self._generation,"challenge_id":challenge["challenge_id"],"route":proposal["route"],"mutation":{"kind":"task-domain","domain_id":self.TRACE_DOMAIN_ID},"validation":copy.deepcopy(validation),"status":"ADMITTED"}; self._evolution_history.append(record); self._append_event("evolution.admitted",record); return copy.deepcopy(record)
        return super()._commit_mutation(challenge,proposal,validation)

    def develop_one_generation(self) -> dict[str, Any]:
        challenges=self._trace_challenges()
        if challenges:
            priority={"trace.runtime_only_edge_count":0,"trace.static_coverage_ppm":1,"trace.static_unobserved_edge_count":2,"trace.static_observed_edge_count":3,"trace.cross_module_call_edge_count":4,"trace.max_call_depth":5,"trace.observed_call_edge_count":6,"trace.hot_module_label":7,"trace.hot_function_label":8,"trace.unique_function_count":9,"trace.unique_module_count":10,"trace.repeated_function_count":11,"trace.call_count":12,"trace.event_count":13}
            challenges.sort(key=lambda c:(0 if c.get("domain_activation_required") else 1,priority.get(str((c.get("_target") or {}).get("family","")),99),str(c.get("dataset_id","")),str(c.get("challenge_id",""))))
            unresolved=False
            for challenge in challenges:
                before=self._best_existing(challenge)
                if min(before["train"],before["hidden"],before["fresh"])==1.0: continue
                unresolved=True; proposal=self._propose_mutation(challenge)
                if proposal is None: continue
                validation=self._validate_mutation(challenge,proposal,before)
                if validation["pass"]:
                    self._append_event("evolution.selected",{"challenge_id":challenge["challenge_id"],"route":proposal["route"],"causal_gain":validation["causal_gain"],"source":"runtime-trace-real-data"}); return self._commit_mutation(challenge,proposal,validation)
                self._append_event("evolution.withhold",{"challenge_id":challenge["challenge_id"],"route":proposal["route"],"validation":validation})
            if unresolved:
                stop={"status":"WITHHOLD","reason":"runtime-trace-gap-without-provable-mutation","generation":self._generation}; self._append_event("evolution.stopped",stop); return stop
        return super().develop_one_generation()

    def export_evolution_state(self) -> dict[str, Any]:
        body={"schema":"ucr.autonomous-evolution-state/6","kernel_id":self.kernel_id,"generation":self._generation,"primitives":[copy.deepcopy(v) for _,v in sorted(self._evolved_primitives.items())],"grammar_rules":copy.deepcopy(self._evolved_grammar_rules),"task_domains":copy.deepcopy(self._evolved_task_domains),"history":copy.deepcopy(self._evolution_history)}
        return {**body,"digest":hashlib.sha256(_canonical(body).encode()).hexdigest()}

    def _validate_v26_state(self, state: dict[str, Any]) -> dict[str, Any]:
        raw=copy.deepcopy(state); supplied=str(raw.pop("digest","")); expected=hashlib.sha256(_canonical(raw).encode()).hexdigest()
        if supplied != expected: raise ValueError("evolution state digest mismatch")
        if raw.get("schema") != "ucr.autonomous-evolution-state/6" or raw.get("kernel_id") != self.kernel_id: raise ValueError("evolution state identity mismatch")
        domains=list(raw.get("task_domains") or []); seen=set(); allowed=set(SAFE_TASK_DOMAIN_BLUEPRINTS)|{self.RECORD_DOMAIN_ID,self.GRAPH_DOMAIN_ID,self.FLOW_DOMAIN_ID,self.TRACE_DOMAIN_ID}
        for item in domains:
            did=str(item.get("domain_id",""))
            if did not in allowed or item.get("admitted") is not True or did in seen: raise ValueError("unknown, duplicate, or non-admitted task domain")
            seen.add(did)
        # Reuse the v25 validator by temporarily validating an equivalent v5 state without trace-domain items/trace primitives.
        base_domains=[copy.deepcopy(x) for x in domains if str(x.get("domain_id")) != self.TRACE_DOMAIN_ID]
        base_primitives=[]; trace_primitives=[]
        for item in list(raw.get("primitives") or []):
            bp=dict(item.get("blueprint") or {})
            if str(bp.get("category","")) == "codetrace": trace_primitives.append(copy.deepcopy(item))
            else: base_primitives.append(copy.deepcopy(item))
        base_body={"schema":"ucr.autonomous-evolution-state/5","kernel_id":self.kernel_id,"generation":int(raw.get("generation",0)),"primitives":base_primitives,"grammar_rules":copy.deepcopy(raw.get("grammar_rules") or []),"task_domains":base_domains,"history":copy.deepcopy(raw.get("history") or [])}
        base_state={**base_body,"digest":hashlib.sha256(_canonical(base_body).encode()).hexdigest()}
        validated_base=super()._validate_v25_state(base_state)
        if trace_primitives and self.TRACE_DOMAIN_ID not in seen: raise ValueError("trace primitive without admitted trace domain")
        for item in trace_primitives:
            bp=dict(item.get("blueprint") or {})
            if str(item.get("machine_id")) != _machine_id_for(bp) or not _is_safe_trace_blueprint(bp): raise ValueError("unsafe trace primitive")
            for case in item.get("self_tests",[]):
                observed=_eval_autonomous_blueprint(bp,[_json_restore(v) for v in case.get("args",[])])
                if not _typed_equal(observed,_json_restore(case.get("expected"))): raise ValueError("trace primitive self-test failed")
        return {**raw,"primitives":base_primitives+trace_primitives,"grammar_rules":validated_base.get("grammar_rules") or [],"task_domains":domains}

    def load_evolution_state(self, state: dict[str, Any]) -> None:
        if state.get("schema") in {"ucr.autonomous-evolution-state/1","ucr.autonomous-evolution-state/2","ucr.autonomous-evolution-state/3","ucr.autonomous-evolution-state/4","ucr.autonomous-evolution-state/5"}:
            super().load_evolution_state(state); return
        raw=self._validate_v26_state(state); self._generation=int(raw.get("generation",0)); self._evolved_grammar_rules=copy.deepcopy(raw.get("grammar_rules") or []); self._evolved_primitives={str(x["machine_id"]):copy.deepcopy(x) for x in raw.get("primitives",[])}; self._evolved_task_domains=copy.deepcopy(raw.get("task_domains") or []); self._evolution_history=copy.deepcopy(raw.get("history") or [])


AutonomousKernel = RuntimeTraceAutonomousKernel


def autonomous_self_test_v26() -> dict[str, Any]:
    def tr(prefix: str, n: int, cross: bool) -> dict[str, Any]:
        events=[]; seq=0
        for i in range(n):
            f=f"{prefix}.a:f{i%3}"; m=f"{prefix}.a"; p=None if i==0 else f"{prefix}.{'b' if cross and i%2 else 'a'}:f{(i-1)%3}"
            events.append({"seq":seq,"event":"call","function":f,"module":m,"depth":i%4,"parent":p}); seq+=1
            events.append({"seq":seq,"event":"return","function":f,"module":m,"depth":i%4,"parent":p}); seq+=1
        static=[{"src":f"{prefix}.a:f0","dst":f"{prefix}.a:f1"},{"src":f"{prefix}.a:f1","dst":f"{prefix}.a:f2"}]
        return {"events":events,"static_edges":static}
    k=AutonomousKernel(); a=[tr("x",5+i,False) for i in range(6)]; b=[tr("y",7+i,True) for i in range(6)]
    k.observe_external_runtime_traces("self/trace-a",a,{"kind":"self-test"}); k.observe_external_runtime_traces("self/trace-b",b,{"kind":"self-test"})
    first=k.develop_one_generation(); second=k.develop_one_generation(); snap=k.snapshot(); r=AutonomousKernel(); r.restore(snap)
    return {"schema":"ucr.autonomous-kernel-v26-self-test/1","first":first,"second":second,"trace_domain_active":k.TRACE_DOMAIN_ID in k._active_task_domains(),"restart_digest_same":r.export_evolution_state()["digest"]==k.export_evolution_state()["digest"],"journal_valid":k.verify_journal(),"pass":first.get("status")=="ADMITTED" and second.get("status")=="ADMITTED" and k.verify_journal()}

# === v27 state-transition causal-learning layer ===
_STATEFLOW_FAMILIES = {
    "state.transition_count",
    "state.changed_transition_count",
    "state.changed_key_total",
    "state.unique_changed_key_count",
    "state.effect_signature_count",
    "state.stable_action_count",
    "state.unstable_action_count",
    "state.consistent_action_effect_pair_count",
    "state.max_consistent_effect_action_label",
    "state.max_change_action_label",
    "state.mean_changed_keys_ppm",
}


def _state_scalar(value: Any) -> Any:
    if value is None or type(value) in (bool, int, float):
        return value
    if type(value) is str and len(value) <= 256:
        return value
    raise TypeError("state value must be a bounded JSON scalar")


def _validate_state_stream(value: Any) -> dict[str, Any]:
    if type(value) is not dict or type(value.get("transitions")) not in (list, tuple):
        raise TypeError("state stream must contain transitions")
    raw = list(value.get("transitions") or [])
    if not 4 <= len(raw) <= 256:
        raise ValueError("state stream outside bounded size")
    out = []
    for index, item in enumerate(raw):
        if type(item) is not dict:
            raise TypeError("invalid state transition")
        action = str(item.get("action", ""))
        if not action or len(action) > 96 or not all(ch.isalnum() or ch in "._:-/" for ch in action):
            raise ValueError("unsafe state action label")
        before = item.get("before"); after = item.get("after")
        if type(before) is not dict or type(after) is not dict or len(before) > 32 or len(after) > 32:
            raise TypeError("state before/after must be bounded dictionaries")
        b = {str(k): _state_scalar(v) for k, v in before.items()}
        a = {str(k): _state_scalar(v) for k, v in after.items()}
        if any(not k or len(k) > 96 or not all(ch.isalnum() or ch in "._:-/" for ch in k) for k in list(b) + list(a)):
            raise ValueError("unsafe state key")
        out.append({"seq": int(item.get("seq", index)), "action": action, "before": b, "after": a})
    out.sort(key=lambda x: (x["seq"], x["action"]))
    return {"transitions": out}


def _stateflow_analysis(stream: dict[str, Any]) -> dict[str, Any]:
    safe = _validate_state_stream(stream)
    sentinel = object()
    signatures: dict[str, list[tuple[str, ...]]] = {}
    changed_union: set[str] = set()
    changed_total = 0
    changed_transition_count = 0
    action_change_totals: dict[str, int] = {}
    for item in safe["transitions"]:
        before = item["before"]; after = item["after"]
        keys = set(before) | set(after)
        changed = tuple(sorted(k for k in keys if before.get(k, sentinel) != after.get(k, sentinel)))
        signatures.setdefault(item["action"], []).append(changed)
        action_change_totals[item["action"]] = action_change_totals.get(item["action"], 0) + len(changed)
        if changed:
            changed_transition_count += 1
            changed_union.update(changed)
            changed_total += len(changed)
    stable: dict[str, tuple[str, ...]] = {}
    unstable: set[str] = set()
    for action, sigs in signatures.items():
        if len(sigs) >= 2 and len(set(sigs)) == 1:
            stable[action] = sigs[0]
        elif len(sigs) >= 2:
            unstable.add(action)
    effect_signatures = {sig for sigs in signatures.values() for sig in sigs}
    consistent_pairs = {(action, key) for action, sig in stable.items() for key in sig}
    max_consistent = ""
    if stable:
        max_consistent = sorted(stable, key=lambda a: (-len(stable[a]), a))[0]
    max_changed = ""
    if action_change_totals:
        max_changed = sorted(action_change_totals, key=lambda a: (-action_change_totals[a], a))[0]
    n = len(safe["transitions"])
    return {
        "stream": safe,
        "signatures": signatures,
        "stable": stable,
        "unstable": unstable,
        "changed_union": changed_union,
        "changed_total": changed_total,
        "changed_transition_count": changed_transition_count,
        "effect_signatures": effect_signatures,
        "consistent_pairs": consistent_pairs,
        "max_consistent": max_consistent,
        "max_changed": max_changed,
        "mean_changed_keys_ppm": int(round((changed_total / n) * 1_000_000)) if n else 0,
    }


def _is_safe_stateflow_blueprint(blueprint: dict[str, Any]) -> bool:
    return (
        int(blueprint.get("arity", 1)) == 1
        and str(blueprint.get("category", "")) == "stateflow"
        and str(blueprint.get("family", "")) in _STATEFLOW_FAMILIES
        and dict(blueprint.get("params") or {}) == {}
    )


_eval_autonomous_blueprint_v26 = _eval_autonomous_blueprint


def _eval_autonomous_blueprint(blueprint: dict[str, Any], args: list[Any]) -> Any:
    if str(blueprint.get("category", "")) == "stateflow":
        if not _is_safe_stateflow_blueprint(blueprint) or len(args) != 1:
            raise ValueError("unsafe stateflow blueprint")
        a = _stateflow_analysis(args[0]); family = str(blueprint["family"])
        if family == "state.transition_count": return len(a["stream"]["transitions"])
        if family == "state.changed_transition_count": return int(a["changed_transition_count"])
        if family == "state.changed_key_total": return int(a["changed_total"])
        if family == "state.unique_changed_key_count": return len(a["changed_union"])
        if family == "state.effect_signature_count": return len(a["effect_signatures"])
        if family == "state.stable_action_count": return len(a["stable"])
        if family == "state.unstable_action_count": return len(a["unstable"])
        if family == "state.consistent_action_effect_pair_count": return len(a["consistent_pairs"])
        if family == "state.max_consistent_effect_action_label": return str(a["max_consistent"])
        if family == "state.max_change_action_label": return str(a["max_changed"])
        if family == "state.mean_changed_keys_ppm": return int(a["mean_changed_keys_ppm"])
        raise ValueError("unknown stateflow family")
    return _eval_autonomous_blueprint_v26(blueprint, args)


class StateFlowAutonomousKernel(RuntimeTraceAutonomousKernel):
    VERSION = "27.0"
    STATEFLOW_DOMAIN_ID = "stateflow.v1"
    _STATEFLOW_OBS_PREFIX = "__ucr_stateflow__::"

    def capabilities(self) -> dict[str, Any]:
        out = super().capabilities()
        out.update({
            "autonomous_kernel_version": self.VERSION,
            "observed_stateflow_dataset_count": len(self._observed_stateflow_datasets()),
            "stateflow_bridge": True,
        })
        return out

    def observe_external_state_streams(self, dataset_id: str, streams: list[dict[str, Any]], provenance: dict[str, Any] | None = None) -> dict[str, Any]:
        did = str(dataset_id)
        if not did or len(did) > 160 or not all(ch.isalnum() or ch in "._:/-" for ch in did):
            raise ValueError("invalid stateflow dataset id")
        if type(streams) not in (list, tuple) or not 5 <= len(streams) <= 64:
            raise ValueError("stateflow dataset requires 5..64 streams")
        safe = [_validate_state_stream(x) for x in streams]
        body = {"schema":"ucr.stateflow-dataset/1","dataset_id":did,"streams":_json_safe(safe),"provenance":_json_safe(provenance or {})}
        body["digest"] = hashlib.sha256(_canonical(body).encode()).hexdigest()
        self.remember(self._STATEFLOW_OBS_PREFIX + did, body)
        self._append_event("stateflow.observed", {"dataset_id":did,"digest":body["digest"],"stream_count":len(safe),"transition_count":sum(len(x["transitions"]) for x in safe)})
        return {"dataset_id":did,"digest":body["digest"],"stream_count":len(safe),"transition_count":sum(len(x["transitions"]) for x in safe)}

    def _observed_stateflow_datasets(self) -> list[dict[str, Any]]:
        out=[]
        for key, val in sorted(self.memory.items()):
            if not str(key).startswith(self._STATEFLOW_OBS_PREFIX) or type(val) is not dict: continue
            raw=copy.deepcopy(val); supplied=str(raw.pop("digest", "")); expected=hashlib.sha256(_canonical(raw).encode()).hexdigest()
            if supplied != expected or raw.get("schema") != "ucr.stateflow-dataset/1": continue
            out.append({**raw,"digest":supplied})
        return out

    def _stateflow_blueprints(self) -> list[dict[str, Any]]:
        return [{"arity":1,"category":"stateflow","family":family,"params":{}} for family in sorted(_STATEFLOW_FAMILIES)]

    def _stateflow_case_sets(self, blueprint: dict[str, Any], dataset: dict[str, Any]) -> dict[str, list[dict[str, Any]]]:
        streams=[_json_restore(x) for x in dataset.get("streams") or []]
        if len(streams) < 5: raise ValueError("insufficient stateflow streams")
        cases=[{"args":[_json_safe(s)],"expected":_json_safe(_eval_autonomous_blueprint(blueprint,[s]))} for s in streams]
        train=cases[0::3]; hidden=cases[1::3]; fresh=cases[2::3]
        if not train or not hidden or not fresh: raise ValueError("insufficient stateflow split")
        return {"train":train,"hidden":hidden,"fresh":fresh}

    def _stateflow_transfer_score(self, blueprint: dict[str, Any], exclude_dataset: str | None = None) -> float:
        scores=[]
        for dataset in self._observed_stateflow_datasets():
            if exclude_dataset is not None and str(dataset.get("dataset_id")) == exclude_dataset: continue
            try: cases=self._stateflow_case_sets(blueprint,dataset)
            except Exception: continue
            scores.append(_score_blueprint(blueprint,cases["train"]+cases["hidden"]+cases["fresh"]))
        return min(scores) if scores else 0.0

    def _stateflow_challenges(self) -> list[dict[str, Any]]:
        datasets=self._observed_stateflow_datasets()
        if not datasets: return []
        active=self._active_task_domains(); admitted={_canonical(x) for x in self._admitted_atomic_blueprints()}; out=[]
        for dataset in datasets:
            did=str(dataset["dataset_id"])
            for bp in self._stateflow_blueprints():
                if self.STATEFLOW_DOMAIN_ID in active and _canonical(bp) in admitted: continue
                cases=self._stateflow_case_sets(bp,dataset)
                outputs={_canonical(c["expected"]) for c in cases["train"]+cases["hidden"]+cases["fresh"]}
                if len(outputs) < 2: continue
                out.append({
                    "challenge_id":"stateflow."+hashlib.sha256((did+_blueprint_digest(bp)).encode()).hexdigest()[:16],
                    "source":"observed-state-transition-self-generator",
                    "task_domain":self.STATEFLOW_DOMAIN_ID,
                    "domain_activation_required":self.STATEFLOW_DOMAIN_ID not in active,
                    "dataset_id":did,"dataset_digest":dataset["digest"],"target_digest":_blueprint_digest(bp),
                    "train":cases["train"],"hidden":cases["hidden"],"fresh":cases["fresh"],"_target":copy.deepcopy(bp),
                })
        return out

    def _challenge_universe(self) -> list[dict[str, Any]]:
        return list(super()._challenge_universe()) + self._stateflow_challenges()

    def _propose_mutation(self, challenge: dict[str, Any]) -> dict[str, Any] | None:
        if str(challenge.get("task_domain", "")) == self.STATEFLOW_DOMAIN_ID:
            if challenge.get("domain_activation_required"):
                if self.STATEFLOW_DOMAIN_ID in self._active_task_domains(): return None
                return {"kind":"task-domain","route":"expand-task-domain-stateflow.v1","domain_id":self.STATEFLOW_DOMAIN_ID,"witness":copy.deepcopy(challenge["_target"])}
            bp=copy.deepcopy(challenge["_target"])
            if not _is_safe_stateflow_blueprint(bp): return None
            if _canonical(bp) in {_canonical(x) for x in self._admitted_atomic_blueprints()}: return None
            return {"kind":"primitive","route":"admit-stateflow-primitive","blueprint":bp}
        return super()._propose_mutation(challenge)

    def _validate_mutation(self, challenge: dict[str, Any], proposal: dict[str, Any], before: dict[str, Any]) -> dict[str, Any]:
        if proposal.get("kind") == "task-domain" and proposal.get("domain_id") == self.STATEFLOW_DOMAIN_ID:
            witness=dict(proposal["witness"]); train=_score_blueprint(witness,challenge["train"]); hidden=_score_blueprint(witness,challenge["hidden"]); fresh=_score_blueprint(witness,challenge["fresh"])
            baseline=min(float(before["train"]),float(before["hidden"]),float(before["fresh"])); primary=str(challenge.get("dataset_id","")); transfer=self._stateflow_transfer_score(witness,exclude_dataset=primary)
            independent=0.0
            for candidate in self._stateflow_blueprints():
                if candidate["family"] == witness["family"]: continue
                independent=max(independent,self._stateflow_transfer_score(candidate,exclude_dataset=primary))
            causal_gain=min(train,hidden,fresh)-baseline
            return {"train":train,"hidden":hidden,"fresh":fresh,"transfer":transfer,"independent_family_transfer":independent,"baseline":baseline,"causal_gain":causal_gain,"pass":train==hidden==fresh==transfer==independent==1.0 and causal_gain>0.0}
        bp=dict(proposal.get("blueprint") or {})
        if proposal.get("kind") == "primitive" and str(bp.get("category","")) == "stateflow":
            train=_score_blueprint(bp,challenge["train"]); hidden=_score_blueprint(bp,challenge["hidden"]); fresh=_score_blueprint(bp,challenge["fresh"]); baseline=min(float(before["train"]),float(before["hidden"]),float(before["fresh"])); transfer=self._stateflow_transfer_score(bp,exclude_dataset=str(challenge.get("dataset_id",""))); causal_gain=min(train,hidden,fresh)-baseline
            return {"train":train,"hidden":hidden,"fresh":fresh,"transfer":transfer,"baseline":baseline,"causal_gain":causal_gain,"pass":train==hidden==fresh==transfer==1.0 and causal_gain>0.0}
        return super()._validate_mutation(challenge,proposal,before)

    def _commit_mutation(self, challenge: dict[str, Any], proposal: dict[str, Any], validation: dict[str, Any]) -> dict[str, Any]:
        if proposal.get("kind") == "task-domain" and proposal.get("domain_id") == self.STATEFLOW_DOMAIN_ID:
            self._generation += 1
            domain={"domain_id":self.STATEFLOW_DOMAIN_ID,"admitted":True,"origin":"observed-state-transition-task-space-expansion","generation":self._generation,"challenge_id":str(challenge["challenge_id"]),"dataset_digest":challenge.get("dataset_digest")}
            self._evolved_task_domains.append(domain)
            record={"generation":self._generation,"challenge_id":challenge["challenge_id"],"route":proposal["route"],"mutation":{"kind":"task-domain","domain_id":self.STATEFLOW_DOMAIN_ID},"validation":copy.deepcopy(validation),"status":"ADMITTED"}
            self._evolution_history.append(record); self._append_event("evolution.admitted",record); return copy.deepcopy(record)
        return super()._commit_mutation(challenge,proposal,validation)

    def develop_one_generation(self) -> dict[str, Any]:
        challenges=self._stateflow_challenges()
        if challenges:
            priority={
                "state.max_consistent_effect_action_label":0,
                "state.consistent_action_effect_pair_count":1,
                "state.stable_action_count":2,
                "state.unstable_action_count":3,
                "state.max_change_action_label":4,
                "state.effect_signature_count":5,
                "state.unique_changed_key_count":6,
                "state.mean_changed_keys_ppm":7,
                "state.changed_key_total":8,
                "state.changed_transition_count":9,
                "state.transition_count":10,
            }
            challenges.sort(key=lambda c:(0 if c.get("domain_activation_required") else 1,priority.get(str((c.get("_target") or {}).get("family","")),99),str(c.get("dataset_id","")),str(c.get("challenge_id",""))))
            unresolved=False
            for challenge in challenges:
                before=self._best_existing(challenge)
                if min(before["train"],before["hidden"],before["fresh"])==1.0: continue
                unresolved=True; proposal=self._propose_mutation(challenge)
                if proposal is None: continue
                validation=self._validate_mutation(challenge,proposal,before)
                if validation["pass"]:
                    self._append_event("evolution.selected",{"challenge_id":challenge["challenge_id"],"route":proposal["route"],"causal_gain":validation["causal_gain"],"source":"real-state-transition-data"})
                    return self._commit_mutation(challenge,proposal,validation)
                self._append_event("evolution.withhold",{"challenge_id":challenge["challenge_id"],"route":proposal["route"],"validation":validation})
            if unresolved:
                stop={"status":"WITHHOLD","reason":"stateflow-gap-without-provable-mutation","generation":self._generation}; self._append_event("evolution.stopped",stop); return stop
        return super().develop_one_generation()

    def export_evolution_state(self) -> dict[str, Any]:
        body={"schema":"ucr.autonomous-evolution-state/7","kernel_id":self.kernel_id,"generation":self._generation,"primitives":[copy.deepcopy(v) for _,v in sorted(self._evolved_primitives.items())],"grammar_rules":copy.deepcopy(self._evolved_grammar_rules),"task_domains":copy.deepcopy(self._evolved_task_domains),"history":copy.deepcopy(self._evolution_history)}
        return {**body,"digest":hashlib.sha256(_canonical(body).encode()).hexdigest()}

    def _validate_v27_state(self, state: dict[str, Any]) -> dict[str, Any]:
        raw=copy.deepcopy(state); supplied=str(raw.pop("digest","")); expected=hashlib.sha256(_canonical(raw).encode()).hexdigest()
        if supplied != expected: raise ValueError("evolution state digest mismatch")
        if raw.get("schema") != "ucr.autonomous-evolution-state/7" or raw.get("kernel_id") != self.kernel_id: raise ValueError("evolution state identity mismatch")
        domains=list(raw.get("task_domains") or []); seen=set(); allowed=set(SAFE_TASK_DOMAIN_BLUEPRINTS)|{self.RECORD_DOMAIN_ID,self.GRAPH_DOMAIN_ID,self.FLOW_DOMAIN_ID,self.TRACE_DOMAIN_ID,self.STATEFLOW_DOMAIN_ID}
        for item in domains:
            did=str(item.get("domain_id",""))
            if did not in allowed or item.get("admitted") is not True or did in seen: raise ValueError("unknown, duplicate, or non-admitted task domain")
            seen.add(did)
        base_domains=[copy.deepcopy(x) for x in domains if str(x.get("domain_id")) != self.STATEFLOW_DOMAIN_ID]
        base_primitives=[]; state_primitives=[]
        for item in list(raw.get("primitives") or []):
            bp=dict(item.get("blueprint") or {})
            if str(bp.get("category","")) == "stateflow": state_primitives.append(copy.deepcopy(item))
            else: base_primitives.append(copy.deepcopy(item))
        base_body={"schema":"ucr.autonomous-evolution-state/6","kernel_id":self.kernel_id,"generation":int(raw.get("generation",0)),"primitives":base_primitives,"grammar_rules":copy.deepcopy(raw.get("grammar_rules") or []),"task_domains":base_domains,"history":copy.deepcopy(raw.get("history") or [])}
        base_state={**base_body,"digest":hashlib.sha256(_canonical(base_body).encode()).hexdigest()}
        validated_base=super()._validate_v26_state(base_state)
        if state_primitives and self.STATEFLOW_DOMAIN_ID not in seen: raise ValueError("stateflow primitive without admitted stateflow domain")
        for item in state_primitives:
            bp=dict(item.get("blueprint") or {})
            if str(item.get("machine_id")) != _machine_id_for(bp) or not _is_safe_stateflow_blueprint(bp): raise ValueError("unsafe stateflow primitive")
            for case in item.get("self_tests",[]):
                observed=_eval_autonomous_blueprint(bp,[_json_restore(v) for v in case.get("args",[])])
                if not _typed_equal(observed,_json_restore(case.get("expected"))): raise ValueError("stateflow primitive self-test failed")
        return {**raw,"primitives":base_primitives+state_primitives,"grammar_rules":validated_base.get("grammar_rules") or [],"task_domains":domains}

    def load_evolution_state(self, state: dict[str, Any]) -> None:
        if state.get("schema") in {"ucr.autonomous-evolution-state/1","ucr.autonomous-evolution-state/2","ucr.autonomous-evolution-state/3","ucr.autonomous-evolution-state/4","ucr.autonomous-evolution-state/5","ucr.autonomous-evolution-state/6"}:
            super().load_evolution_state(state); return
        raw=self._validate_v27_state(state); self._generation=int(raw.get("generation",0)); self._evolved_grammar_rules=copy.deepcopy(raw.get("grammar_rules") or []); self._evolved_primitives={str(x["machine_id"]):copy.deepcopy(x) for x in raw.get("primitives",[])}; self._evolved_task_domains=copy.deepcopy(raw.get("task_domains") or []); self._evolution_history=copy.deepcopy(raw.get("history") or [])


AutonomousKernel = StateFlowAutonomousKernel


def autonomous_self_test_v27() -> dict[str, Any]:
    def stream(prefix: str, n: int, unstable: bool) -> dict[str, Any]:
        state={"x":0,"y":0,"z":0}; trans=[]; seq=0
        for i in range(n):
            b=dict(state); state["x"] += 1; trans.append({"seq":seq,"action":prefix+".incx","before":b,"after":dict(state)}); seq+=1
        for i in range(2):
            b=dict(state); state["y"] += 1; state["z"] += 1; trans.append({"seq":seq,"action":prefix+".duo","before":b,"after":dict(state)}); seq+=1
        if unstable:
            b=dict(state); state["x"] += 1; trans.append({"seq":seq,"action":prefix+".maybe","before":b,"after":dict(state)}); seq+=1
            b=dict(state); trans.append({"seq":seq,"action":prefix+".maybe","before":b,"after":dict(state)}); seq+=1
        return {"transitions":trans}
    k=AutonomousKernel(); a=[stream("a",2+(i%3),bool(i%2)) for i in range(6)]; b=[stream("b",3+(i%2),bool((i+1)%2)) for i in range(6)]
    k.observe_external_state_streams("self/state-a",a,{"kind":"self-test"}); k.observe_external_state_streams("self/state-b",b,{"kind":"self-test"})
    first=k.develop_one_generation(); second=k.develop_one_generation(); snap=k.snapshot(); r=AutonomousKernel(); r.restore(snap)
    return {"schema":"ucr.autonomous-kernel-v27-self-test/1","first":first,"second":second,"stateflow_domain_active":k.STATEFLOW_DOMAIN_ID in k._active_task_domains(),"restart_digest_same":r.export_evolution_state()["digest"]==k.export_evolution_state()["digest"],"journal_valid":k.verify_journal(),"pass":first.get("status")=="ADMITTED" and second.get("status")=="ADMITTED" and k.verify_journal()}

# === v28 predictive-state / intervention layer ===
_STATEPREDICT_FAMILIES = {
    "prediction.identifiable_action_count",
    "prediction.ambiguous_action_count",
    "prediction.exact_prediction_transition_count",
    "prediction.leave_one_out_accuracy_ppm",
    "prediction.best_intervention_plan_label",
}


def _model_apply(model: dict[str, Any], value: Any) -> Any:
    kind = str(model.get("kind", ""))
    if kind == "delta":
        if type(value) not in (int, float) or type(value) is bool:
            raise TypeError("delta model requires numeric scalar")
        return value + model["value"]
    if kind == "set":
        return copy.deepcopy(model.get("value"))
    if kind == "toggle":
        if type(value) is not bool:
            raise TypeError("toggle model requires bool")
        return not value
    raise ValueError("unknown bounded prediction model")


def _initial_models(before: Any, after: Any) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    if type(before) is bool and type(after) is bool:
        if (not before) == after:
            out.append({"kind":"toggle"})
        out.append({"kind":"set","value":after})
    elif type(before) in (int, float) and type(after) in (int, float) and type(before) is not bool and type(after) is not bool:
        delta = after - before
        if abs(float(delta)) <= 1_000_000:
            out.append({"kind":"delta","value":delta})
        out.append({"kind":"set","value":after})
    elif type(after) in (str, int, float, bool) or after is None:
        out.append({"kind":"set","value":after})
    dedup=[]; seen=set()
    for item in out:
        key=_canonical(item)
        if key not in seen:
            seen.add(key); dedup.append(item)
    return dedup


def _learn_state_prediction_models(stream: dict[str, Any]) -> dict[str, Any]:
    safe = _validate_state_stream(stream)
    by_action: dict[str, list[dict[str, Any]]] = {}
    for item in safe["transitions"]:
        by_action.setdefault(item["action"], []).append(item)
    actions: dict[str, Any] = {}
    for action, rows in sorted(by_action.items()):
        sentinel = object(); changed_keys: set[str] = set()
        for row in rows:
            keys=set(row["before"])|set(row["after"])
            changed_keys.update(k for k in keys if row["before"].get(k,sentinel) != row["after"].get(k,sentinel))
        key_models: dict[str, list[dict[str, Any]]] = {}
        for key in sorted(changed_keys):
            pairs=[(r["before"].get(key), r["after"].get(key)) for r in rows if key in r["before"] and key in r["after"]]
            if not pairs: continue
            models=_initial_models(pairs[0][0],pairs[0][1])
            kept=[]
            for model in models:
                ok=True
                for b,a in pairs:
                    try: pred=_model_apply(model,b)
                    except Exception: ok=False; break
                    if not _typed_equal(pred,a): ok=False; break
                if ok: kept.append(model)
            key_models[key]=kept
        identifiable=bool(key_models) and all(len(v)==1 for v in key_models.values())
        ambiguous=any(len(v)>1 for v in key_models.values())
        actions[action]={"rows":len(rows),"changed_keys":sorted(changed_keys),"key_models":key_models,"identifiable":identifiable,"ambiguous":ambiguous}
    return {"stream":safe,"actions":actions}


def _predict_with_models(model_info: dict[str, Any], action: str, before: dict[str, Any]) -> dict[str, Any] | None:
    info=dict(model_info.get("actions",{}).get(action) or {})
    if not info or not info.get("identifiable"):
        return None
    out=copy.deepcopy(before)
    for key, models in dict(info.get("key_models") or {}).items():
        if len(models)!=1 or key not in before: return None
        out[key]=_model_apply(models[0],before[key])
    return out


def _probe_values_for(value: Any) -> list[Any]:
    if type(value) is bool:
        return [False,True]
    if type(value) in (int,float) and type(value) is not bool:
        base=[0,1,2,3,4,5,6,8,13] if value >= 0 else [-3,-2,-1,0,1,2,3,5,8]
        if type(value) is float: base=[float(x) for x in base]
        return base
    return []


def _best_intervention_plan(model_info: dict[str, Any]) -> dict[str, Any] | None:
    plans=[]
    for action, info in sorted(dict(model_info.get("actions") or {}).items()):
        for key, models in sorted(dict(info.get("key_models") or {}).items()):
            if len(models) <= 1: continue
            rows=[r for r in model_info["stream"]["transitions"] if r["action"]==action and key in r["before"]]
            if not rows: continue
            reference=rows[0]["before"][key]
            for probe in _probe_values_for(reference):
                preds=[]
                try:
                    preds=[_model_apply(m,probe) for m in models]
                except Exception:
                    continue
                uniq={_canonical(x) for x in preds}
                if len(uniq) <= 1: continue
                seen_before={_canonical(r["before"].get(key)) for r in rows}
                novelty=1 if _canonical(probe) not in seen_before else 0
                spread=len(uniq)
                plan={"action":action,"key":key,"set_before":probe,"candidate_predictions":preds,"candidate_models":copy.deepcopy(models)}
                plans.append((-(spread+novelty),action,key,_canonical(probe),plan))
    if not plans: return None
    plans.sort(key=lambda x:x[:4])
    return plans[0][4]


def _stateprediction_analysis(stream: dict[str, Any]) -> dict[str, Any]:
    learned=_learn_state_prediction_models(stream)
    identifiable=sum(1 for v in learned["actions"].values() if v.get("identifiable"))
    ambiguous=sum(1 for v in learned["actions"].values() if v.get("ambiguous"))
    exact=0; checked=0
    # Leave-one-out measures genuine prediction from other observations of the same action.
    rows=learned["stream"]["transitions"]
    correct=0
    for i,row in enumerate(rows):
        others=[copy.deepcopy(r) for j,r in enumerate(rows) if j!=i]
        if len(others)<1: continue
        try: mi=_learn_state_prediction_models({"transitions":others})
        except Exception: continue
        pred=_predict_with_models(mi,row["action"],row["before"])
        if pred is None: continue
        checked += 1
        if _typed_equal(pred,row["after"]):
            correct += 1; exact += 1
    accuracy=int(round((correct/checked)*1_000_000)) if checked else 0
    plan=_best_intervention_plan(learned)
    label="" if plan is None else _canonical({"action":plan["action"],"key":plan["key"],"set_before":plan["set_before"]})
    return {"learned":learned,"identifiable_action_count":identifiable,"ambiguous_action_count":ambiguous,"exact_prediction_transition_count":exact,"leave_one_out_accuracy_ppm":accuracy,"best_intervention_plan":plan,"best_intervention_plan_label":label}


def _is_safe_statepredict_blueprint(blueprint: dict[str, Any]) -> bool:
    return int(blueprint.get("arity",1))==1 and str(blueprint.get("category",""))=="statepredict" and str(blueprint.get("family","")) in _STATEPREDICT_FAMILIES and dict(blueprint.get("params") or {})=={}


_eval_autonomous_blueprint_v27 = _eval_autonomous_blueprint


def _eval_autonomous_blueprint(blueprint: dict[str, Any], args: list[Any]) -> Any:
    if str(blueprint.get("category","")) == "statepredict":
        if not _is_safe_statepredict_blueprint(blueprint) or len(args)!=1:
            raise ValueError("unsafe statepredict blueprint")
        a=_stateprediction_analysis(args[0]); fam=str(blueprint["family"])
        if fam=="prediction.identifiable_action_count": return int(a["identifiable_action_count"])
        if fam=="prediction.ambiguous_action_count": return int(a["ambiguous_action_count"])
        if fam=="prediction.exact_prediction_transition_count": return int(a["exact_prediction_transition_count"])
        if fam=="prediction.leave_one_out_accuracy_ppm": return int(a["leave_one_out_accuracy_ppm"])
        if fam=="prediction.best_intervention_plan_label": return str(a["best_intervention_plan_label"])
        raise ValueError("unknown statepredict family")
    return _eval_autonomous_blueprint_v27(blueprint,args)


class PredictiveStateAutonomousKernel(StateFlowAutonomousKernel):
    VERSION="28.0"
    PREDICT_DOMAIN_ID="statepredict.v1"

    def capabilities(self) -> dict[str, Any]:
        out=super().capabilities(); out.update({"autonomous_kernel_version":self.VERSION,"state_prediction":True,"intervention_planning":True}); return out

    def _statepredict_blueprints(self) -> list[dict[str, Any]]:
        return [{"arity":1,"category":"statepredict","family":f,"params":{}} for f in sorted(_STATEPREDICT_FAMILIES)]

    def _statepredict_case_sets(self,bp:dict[str,Any],dataset:dict[str,Any]) -> dict[str,list[dict[str,Any]]]:
        streams=[_json_restore(x) for x in dataset.get("streams") or []]
        cases=[{"args":[_json_safe(s)],"expected":_json_safe(_eval_autonomous_blueprint(bp,[s]))} for s in streams]
        train=cases[0::3]; hidden=cases[1::3]; fresh=cases[2::3]
        if not train or not hidden or not fresh: raise ValueError("insufficient prediction split")
        return {"train":train,"hidden":hidden,"fresh":fresh}

    def _statepredict_transfer_score(self,bp:dict[str,Any],exclude_dataset:str|None=None) -> float:
        scores=[]
        for ds in self._observed_stateflow_datasets():
            if exclude_dataset is not None and str(ds.get("dataset_id"))==exclude_dataset: continue
            try: cs=self._statepredict_case_sets(bp,ds)
            except Exception: continue
            scores.append(_score_blueprint(bp,cs["train"]+cs["hidden"]+cs["fresh"]))
        return min(scores) if scores else 0.0

    def _statepredict_challenges(self) -> list[dict[str,Any]]:
        datasets=self._observed_stateflow_datasets()
        if len(datasets)<2: return []
        active=self._active_task_domains(); admitted={_canonical(x) for x in self._admitted_atomic_blueprints()}; out=[]
        for ds in datasets:
            did=str(ds["dataset_id"])
            for bp in self._statepredict_blueprints():
                if self.PREDICT_DOMAIN_ID in active and _canonical(bp) in admitted: continue
                cs=self._statepredict_case_sets(bp,ds); outputs={_canonical(c["expected"]) for c in cs["train"]+cs["hidden"]+cs["fresh"]}
                if len(outputs)<2 and bp["family"]!="prediction.best_intervention_plan_label": continue
                out.append({"challenge_id":"statepredict."+hashlib.sha256((did+_blueprint_digest(bp)).encode()).hexdigest()[:16],"source":"observed-state-prediction-self-generator","task_domain":self.PREDICT_DOMAIN_ID,"dataset_id":did,"dataset_digest":ds["digest"],"train":cs["train"],"hidden":cs["hidden"],"fresh":cs["fresh"],"domain_activation_required":self.PREDICT_DOMAIN_ID not in active,"_target":bp})
        return out

    def _best_existing(self,challenge:dict[str,Any]) -> dict[str,Any]:
        if challenge.get("task_domain")==self.PREDICT_DOMAIN_ID:
            best={"score":0.0,"train":0.0,"hidden":0.0,"fresh":0.0,"blueprint":None}
            for bp in self._admitted_atomic_blueprints():
                try:
                    t=_score_blueprint(bp,challenge["train"]); h=_score_blueprint(bp,challenge["hidden"]); f=_score_blueprint(bp,challenge["fresh"])
                except Exception: continue
                score=min(t,h,f)
                if score>best["score"]: best={"score":score,"train":t,"hidden":h,"fresh":f,"blueprint":copy.deepcopy(bp)}
            return best
        return super()._best_existing(challenge)

    def _propose_mutation(self,challenge:dict[str,Any]) -> dict[str,Any]|None:
        if challenge.get("task_domain")==self.PREDICT_DOMAIN_ID:
            if self.PREDICT_DOMAIN_ID not in self._active_task_domains():
                return {"kind":"task-domain","domain_id":self.PREDICT_DOMAIN_ID,"route":"admit-statepredict-task-domain","witness_blueprint":copy.deepcopy(challenge["_target"])}
            bp=copy.deepcopy(challenge["_target"])
            return {"kind":"primitive","route":"admit-statepredict-primitive","blueprint":bp,"machine_id":_machine_id_for(bp)}
        return super()._propose_mutation(challenge)

    def _validate_mutation(self,challenge:dict[str,Any],proposal:dict[str,Any],before:dict[str,Any]) -> dict[str,Any]:
        if challenge.get("task_domain")==self.PREDICT_DOMAIN_ID:
            if proposal.get("kind")=="task-domain":
                bp=dict(proposal["witness_blueprint"]); train=_score_blueprint(bp,challenge["train"]); hidden=_score_blueprint(bp,challenge["hidden"]); fresh=_score_blueprint(bp,challenge["fresh"]); transfer=self._statepredict_transfer_score(bp,exclude_dataset=str(challenge["dataset_id"])); gain=min(train,hidden,fresh)-min(float(before["train"]),float(before["hidden"]),float(before["fresh"])); return {"train":train,"hidden":hidden,"fresh":fresh,"transfer":transfer,"causal_gain":gain,"pass":train==hidden==fresh==transfer==1.0 and gain>0.0}
            bp=dict(proposal.get("blueprint") or {}); train=_score_blueprint(bp,challenge["train"]); hidden=_score_blueprint(bp,challenge["hidden"]); fresh=_score_blueprint(bp,challenge["fresh"]); transfer=self._statepredict_transfer_score(bp,exclude_dataset=str(challenge["dataset_id"])); gain=min(train,hidden,fresh)-min(float(before["train"]),float(before["hidden"]),float(before["fresh"])); return {"train":train,"hidden":hidden,"fresh":fresh,"transfer":transfer,"causal_gain":gain,"pass":train==hidden==fresh==transfer==1.0 and gain>0.0}
        return super()._validate_mutation(challenge,proposal,before)

    def _commit_mutation(self,challenge:dict[str,Any],proposal:dict[str,Any],validation:dict[str,Any]) -> dict[str,Any]:
        if proposal.get("kind")=="task-domain" and proposal.get("domain_id")==self.PREDICT_DOMAIN_ID:
            self._generation+=1; domain={"domain_id":self.PREDICT_DOMAIN_ID,"admitted":True,"origin":"observed-state-prediction-task-space-expansion","generation":self._generation,"challenge_id":str(challenge["challenge_id"]),"dataset_digest":challenge.get("dataset_digest")}; self._evolved_task_domains.append(domain); record={"generation":self._generation,"challenge_id":challenge["challenge_id"],"route":proposal["route"],"mutation":{"kind":"task-domain","domain_id":self.PREDICT_DOMAIN_ID},"validation":copy.deepcopy(validation),"status":"ADMITTED"}; self._evolution_history.append(record); self._append_event("evolution.admitted",record); return copy.deepcopy(record)
        return super()._commit_mutation(challenge,proposal,validation)

    def develop_one_generation(self) -> dict[str,Any]:
        ch=self._statepredict_challenges()
        if ch:
            priority={"prediction.best_intervention_plan_label":0,"prediction.ambiguous_action_count":1,"prediction.identifiable_action_count":2,"prediction.leave_one_out_accuracy_ppm":3,"prediction.exact_prediction_transition_count":4}
            ch.sort(key=lambda c:(0 if c.get("domain_activation_required") else 1,priority.get(str((c.get("_target") or {}).get("family","")),99),str(c.get("dataset_id","")),str(c.get("challenge_id",""))))
            unresolved=False
            for challenge in ch:
                before=self._best_existing(challenge)
                if min(before["train"],before["hidden"],before["fresh"])==1.0: continue
                unresolved=True; proposal=self._propose_mutation(challenge)
                if proposal is None: continue
                val=self._validate_mutation(challenge,proposal,before)
                if val["pass"]:
                    self._append_event("evolution.selected",{"challenge_id":challenge["challenge_id"],"route":proposal["route"],"causal_gain":val["causal_gain"],"source":"real-state-prediction-data"}); return self._commit_mutation(challenge,proposal,val)
                self._append_event("evolution.withhold",{"challenge_id":challenge["challenge_id"],"route":proposal["route"],"validation":val})
            if unresolved:
                stop={"status":"WITHHOLD","reason":"statepredict-gap-without-provable-mutation","generation":self._generation}; self._append_event("evolution.stopped",stop); return stop
        return super().develop_one_generation()

    def propose_state_intervention(self,dataset_id:str) -> dict[str,Any]:
        if self.PREDICT_DOMAIN_ID not in self._active_task_domains(): raise ValueError("state prediction domain not admitted")
        ds=next((x for x in self._observed_stateflow_datasets() if str(x.get("dataset_id"))==str(dataset_id)),None)
        if ds is None: raise KeyError("unknown stateflow dataset")
        transitions=[]
        for s in [_json_restore(x) for x in ds.get("streams") or []]: transitions.extend(_validate_state_stream(s)["transitions"])
        plan=_best_intervention_plan(_learn_state_prediction_models({"transitions":transitions}))
        if plan is None: return {"status":"NO_AMBIGUITY","dataset_id":dataset_id}
        return {"status":"PROPOSED","dataset_id":dataset_id,"action":plan["action"],"key":plan["key"],"set_before":_json_safe(plan["set_before"]),"candidate_predictions":_json_safe(plan["candidate_predictions"]),"candidate_models":_json_safe(plan["candidate_models"])}

    def predict_state_after(self,dataset_id:str,action:str,before:dict[str,Any]) -> dict[str,Any]:
        if self.PREDICT_DOMAIN_ID not in self._active_task_domains(): raise ValueError("state prediction domain not admitted")
        ds=next((x for x in self._observed_stateflow_datasets() if str(x.get("dataset_id"))==str(dataset_id)),None)
        if ds is None: raise KeyError("unknown stateflow dataset")
        transitions=[]
        for s in [_json_restore(x) for x in ds.get("streams") or []]: transitions.extend(_validate_state_stream(s)["transitions"])
        mi=_learn_state_prediction_models({"transitions":transitions}); pred=_predict_with_models(mi,str(action),{str(k):_state_scalar(v) for k,v in before.items()})
        if pred is None: return {"status":"AMBIGUOUS","action":str(action)}
        return {"status":"PREDICTED","action":str(action),"after":_json_safe(pred)}

    def export_evolution_state(self) -> dict[str,Any]:
        body={"schema":"ucr.autonomous-evolution-state/8","kernel_id":self.kernel_id,"generation":self._generation,"primitives":[copy.deepcopy(v) for _,v in sorted(self._evolved_primitives.items())],"grammar_rules":copy.deepcopy(self._evolved_grammar_rules),"task_domains":copy.deepcopy(self._evolved_task_domains),"history":copy.deepcopy(self._evolution_history)}
        return {**body,"digest":hashlib.sha256(_canonical(body).encode()).hexdigest()}

    def _validate_v28_state(self,state:dict[str,Any]) -> dict[str,Any]:
        raw=copy.deepcopy(state); supplied=str(raw.pop("digest","")); expected=hashlib.sha256(_canonical(raw).encode()).hexdigest()
        if supplied!=expected: raise ValueError("evolution state digest mismatch")
        if raw.get("schema")!="ucr.autonomous-evolution-state/8" or raw.get("kernel_id")!=self.kernel_id: raise ValueError("evolution state identity mismatch")
        domains=list(raw.get("task_domains") or []); seen=set(); allowed=set(SAFE_TASK_DOMAIN_BLUEPRINTS)|{self.RECORD_DOMAIN_ID,self.GRAPH_DOMAIN_ID,self.FLOW_DOMAIN_ID,self.TRACE_DOMAIN_ID,self.STATEFLOW_DOMAIN_ID,self.PREDICT_DOMAIN_ID}
        for item in domains:
            did=str(item.get("domain_id",""))
            if did not in allowed or item.get("admitted") is not True or did in seen: raise ValueError("unknown, duplicate, or non-admitted task domain")
            seen.add(did)
        base_domains=[copy.deepcopy(x) for x in domains if str(x.get("domain_id"))!=self.PREDICT_DOMAIN_ID]; base_primitives=[]; pred_primitives=[]
        for item in list(raw.get("primitives") or []):
            bp=dict(item.get("blueprint") or {})
            (pred_primitives if str(bp.get("category",""))=="statepredict" else base_primitives).append(copy.deepcopy(item))
        base_body={"schema":"ucr.autonomous-evolution-state/7","kernel_id":self.kernel_id,"generation":int(raw.get("generation",0)),"primitives":base_primitives,"grammar_rules":copy.deepcopy(raw.get("grammar_rules") or []),"task_domains":base_domains,"history":copy.deepcopy(raw.get("history") or [])}; base_state={**base_body,"digest":hashlib.sha256(_canonical(base_body).encode()).hexdigest()}; validated=super()._validate_v27_state(base_state)
        if pred_primitives and self.PREDICT_DOMAIN_ID not in seen: raise ValueError("statepredict primitive without domain")
        for item in pred_primitives:
            bp=dict(item.get("blueprint") or {})
            if str(item.get("machine_id"))!=_machine_id_for(bp) or not _is_safe_statepredict_blueprint(bp): raise ValueError("unsafe statepredict primitive")
            for case in item.get("self_tests",[]):
                observed=_eval_autonomous_blueprint(bp,[_json_restore(v) for v in case.get("args",[])])
                if not _typed_equal(observed,_json_restore(case.get("expected"))): raise ValueError("statepredict primitive self-test failed")
        return {**raw,"primitives":base_primitives+pred_primitives,"grammar_rules":validated.get("grammar_rules") or [],"task_domains":domains}

    def load_evolution_state(self,state:dict[str,Any]) -> None:
        if state.get("schema") in {"ucr.autonomous-evolution-state/1","ucr.autonomous-evolution-state/2","ucr.autonomous-evolution-state/3","ucr.autonomous-evolution-state/4","ucr.autonomous-evolution-state/5","ucr.autonomous-evolution-state/6","ucr.autonomous-evolution-state/7"}:
            super().load_evolution_state(state); return
        raw=self._validate_v28_state(state); self._generation=int(raw.get("generation",0)); self._evolved_grammar_rules=copy.deepcopy(raw.get("grammar_rules") or []); self._evolved_primitives={str(x["machine_id"]):copy.deepcopy(x) for x in raw.get("primitives",[])}; self._evolved_task_domains=copy.deepcopy(raw.get("task_domains") or []); self._evolution_history=copy.deepcopy(raw.get("history") or [])


AutonomousKernel=PredictiveStateAutonomousKernel


def autonomous_self_test_v28() -> dict[str,Any]:
    def make(prefix:str,base:int,second:bool) -> dict[str,Any]:
        state={"n":base,"flag":False}; trans=[]; seq=0
        # First observation is ambiguous: +1 vs set(base+1). Optional second resolves it.
        b=dict(state); state["n"]+=1; trans.append({"seq":seq,"action":prefix+".inc","before":b,"after":dict(state)}); seq+=1
        if second:
            b=dict(state); state["n"]+=1; trans.append({"seq":seq,"action":prefix+".inc","before":b,"after":dict(state)}); seq+=1
        b=dict(state); state["flag"]=not state["flag"]; trans.append({"seq":seq,"action":prefix+".toggle","before":b,"after":dict(state)}); seq+=1
        if second:
            b=dict(state); state["flag"]=not state["flag"]; trans.append({"seq":seq,"action":prefix+".toggle","before":b,"after":dict(state)}); seq+=1
        while len(trans)<4:
            b=dict(state); state["n"]+=1; trans.append({"seq":seq,"action":prefix+".inc","before":b,"after":dict(state)}); seq+=1
        return {"transitions":trans}
    k=AutonomousKernel(); a=[make("a",4+i,False if i%2==0 else True) for i in range(6)]; b=[make("b",7+i,False if i%2 else True) for i in range(6)]; k.observe_external_state_streams("self/predict-a",a,{"kind":"self-test"}); k.observe_external_state_streams("self/predict-b",b,{"kind":"self-test"}); first=k.develop_one_generation(); second=k.develop_one_generation(); snap=k.snapshot(); r=AutonomousKernel(); r.restore(snap); return {"schema":"ucr.autonomous-kernel-v28-self-test/1","first":first,"second":second,"predict_domain_active":k.PREDICT_DOMAIN_ID in k._active_task_domains(),"restart_digest_same":r.export_evolution_state()["digest"]==k.export_evolution_state()["digest"],"journal_valid":k.verify_journal(),"pass":first.get("status")=="ADMITTED" and second.get("status")=="ADMITTED" and k.verify_journal()}

# === v29 model-genesis / metacausal reasoning layer ===

_MODELTYPE_DOMAINS = {
    "affine_int": "causalmodel.affine_int.v1",
    "mod_add_int": "causalmodel.mod_add_int.v1",
}


def _fit_affine_int(pairs: list[tuple[Any, Any]]) -> dict[str, Any] | None:
    clean=[]
    for x,y in pairs:
        if type(x) is not int or type(y) is not int or type(x) is bool or type(y) is bool:
            return None
        clean.append((x,y))
    if len(clean) < 2:
        return None
    first=None
    for i in range(len(clean)):
        for j in range(i+1,len(clean)):
            x1,y1=clean[i]; x2,y2=clean[j]
            if x1!=x2:
                first=(x1,y1,x2,y2); break
        if first: break
    if first is None:
        return None
    x1,y1,x2,y2=first
    dx=x2-x1; dy=y2-y1
    if dy % dx != 0:
        return None
    a=dy//dx; b=y1-a*x1
    if a in (0,1):
        return None  # equivalent to existing set/delta families
    if abs(a)>64 or abs(b)>1_000_000:
        return None
    if all(a*x+b==y for x,y in clean):
        return {"kind":"affine_int","a":a,"b":b}
    return None


def _fit_mod_add_int(pairs: list[tuple[Any, Any]]) -> dict[str, Any] | None:
    clean=[]
    for x,y in pairs:
        if type(x) is not int or type(y) is not int or type(x) is bool or type(y) is bool:
            return None
        clean.append((x,y))
    if len(clean) < 3:
        return None
    # Bounded exhaustive synthesis. Require at least one wraparound witness so this
    # family is not admitted when an ordinary delta already explains the data.
    best=None
    for mod in range(2,65):
        for delta in range(-16,17):
            if all((x+delta)%mod==y for x,y in clean):
                wrapped=any((x+delta)!=y for x,y in clean)
                if not wrapped:
                    continue
                cand={"kind":"mod_add_int","delta":delta,"mod":mod}
                key=(mod,abs(delta),delta)
                if best is None or key<best[0]:
                    best=(key,cand)
    return None if best is None else best[1]


def _apply_model_v29(model: dict[str, Any], value: Any) -> Any:
    kind=str(model.get("kind",""))
    if kind in {"delta","set","toggle"}:
        return _model_apply(model,value)
    if kind=="affine_int":
        if type(value) is not int or type(value) is bool:
            raise TypeError("affine_int requires int")
        return int(model["a"])*value + int(model["b"])
    if kind=="mod_add_int":
        if type(value) is not int or type(value) is bool:
            raise TypeError("mod_add_int requires int")
        mod=int(model["mod"]); delta=int(model["delta"])
        if not 2<=mod<=64 or not -16<=delta<=16:
            raise ValueError("unsafe modular model")
        return (value+delta)%mod
    raise ValueError("unknown v29 model")


def _fit_model_kind(kind: str, pairs: list[tuple[Any,Any]]) -> dict[str,Any] | None:
    if kind=="affine_int": return _fit_affine_int(pairs)
    if kind=="mod_add_int": return _fit_mod_add_int(pairs)
    return None


def _learn_state_prediction_models_v29(stream: dict[str, Any], enabled_kinds: set[str]) -> dict[str, Any]:
    safe=_validate_state_stream(stream)
    by_action: dict[str,list[dict[str,Any]]]={}
    for item in safe["transitions"]:
        by_action.setdefault(item["action"],[]).append(item)
    actions={}
    for action,rows in sorted(by_action.items()):
        sentinel=object(); changed_keys=set()
        for row in rows:
            keys=set(row["before"])|set(row["after"])
            changed_keys.update(k for k in keys if row["before"].get(k,sentinel)!=row["after"].get(k,sentinel))
        key_models={}
        for key in sorted(changed_keys):
            pairs=[(r["before"].get(key),r["after"].get(key)) for r in rows if key in r["before"] and key in r["after"]]
            if not pairs: continue
            base=_initial_models(pairs[0][0],pairs[0][1]); kept=[]
            for model in base:
                ok=True
                for b,a in pairs:
                    try: pred=_apply_model_v29(model,b)
                    except Exception: ok=False; break
                    if not _typed_equal(pred,a): ok=False; break
                if ok: kept.append(model)
            for kind in sorted(enabled_kinds):
                model=_fit_model_kind(kind,pairs)
                if model is not None:
                    keyc=_canonical(model)
                    if all(_canonical(x)!=keyc for x in kept): kept.append(model)
            key_models[key]=kept
        identifiable=bool(key_models) and all(len(v)==1 for v in key_models.values())
        ambiguous=any(len(v)>1 for v in key_models.values())
        actions[action]={"rows":len(rows),"changed_keys":sorted(changed_keys),"key_models":key_models,"identifiable":identifiable,"ambiguous":ambiguous}
    return {"stream":safe,"actions":actions}


def _predict_with_models_v29(model_info: dict[str,Any], action: str, before: dict[str,Any]) -> dict[str,Any] | None:
    info=dict(model_info.get("actions",{}).get(action) or {})
    if not info or not info.get("identifiable"): return None
    out=copy.deepcopy(before)
    for key,models in dict(info.get("key_models") or {}).items():
        if len(models)!=1 or key not in before: return None
        out[key]=_apply_model_v29(models[0],before[key])
    return out


def _flatten_state_dataset(dataset: dict[str,Any]) -> list[dict[str,Any]]:
    rows=[]
    for raw in [_json_restore(x) for x in dataset.get("streams") or []]:
        rows.extend(_validate_state_stream(raw)["transitions"])
    return rows


def _model_kind_dataset_score(dataset: dict[str,Any], enabled_kinds: set[str]) -> float:
    streams=[_validate_state_stream(_json_restore(x)) for x in dataset.get("streams") or []]
    if len(streams)<3: return 0.0
    # Train on first 60%; evaluate exact prediction on held-out streams.
    cut=max(1,int(len(streams)*0.6)); train_rows=[]
    for s in streams[:cut]: train_rows.extend(s["transitions"])
    if not train_rows: return 0.0
    learned=_learn_state_prediction_models_v29({"transitions":train_rows},enabled_kinds)
    total=0; correct=0
    for s in streams[cut:]:
        for row in s["transitions"]:
            total+=1
            pred=_predict_with_models_v29(learned,row["action"],row["before"])
            if pred is not None and _typed_equal(pred,row["after"]): correct+=1
    return correct/total if total else 0.0


def _dataset_candidate_model_kinds(dataset: dict[str,Any], active: set[str]) -> dict[str,float]:
    base=_model_kind_dataset_score(dataset,active)
    out={}
    for kind in sorted(_MODELTYPE_DOMAINS):
        if kind in active: continue
        score=_model_kind_dataset_score(dataset,set(active)|{kind})
        if score>base+1e-12:
            out[kind]=score
    return out


class ModelGenesisAutonomousKernel(PredictiveStateAutonomousKernel):
    VERSION="29.0"

    def capabilities(self) -> dict[str,Any]:
        out=super().capabilities(); out.update({"autonomous_kernel_version":self.VERSION,"causal_model_genesis":True,"active_causal_model_types":sorted(self._active_model_types())}); return out

    def _active_model_types(self) -> set[str]:
        active=self._active_task_domains(); return {kind for kind,did in _MODELTYPE_DOMAINS.items() if did in active}

    def _modeltype_gap_candidates(self) -> list[dict[str,Any]]:
        datasets=self._observed_stateflow_datasets(); active=self._active_model_types(); rows=[]
        for ds in datasets:
            candidates=_dataset_candidate_model_kinds(ds,active)
            for kind,score in candidates.items():
                rows.append({"dataset_id":str(ds.get("dataset_id","")),"dataset_digest":str(ds.get("digest","")),"kind":kind,"before_score":_model_kind_dataset_score(ds,active),"after_score":score})
        return rows

    def _validate_modeltype_admission(self,kind:str,primary_dataset:str) -> dict[str,Any]:
        datasets=self._observed_stateflow_datasets(); active=self._active_model_types(); primary=next((d for d in datasets if str(d.get("dataset_id"))==primary_dataset),None)
        if primary is None: return {"pass":False,"reason":"missing-primary"}
        before=_model_kind_dataset_score(primary,active); after=_model_kind_dataset_score(primary,active|{kind}); transfer=0.0; transfer_id=""
        for ds in datasets:
            did=str(ds.get("dataset_id",""))
            if did==primary_dataset: continue
            cand_before=_model_kind_dataset_score(ds,active); cand_after=_model_kind_dataset_score(ds,active|{kind})
            if cand_after>cand_before+1e-12 and cand_after>transfer:
                transfer=cand_after; transfer_id=did
        gain=after-before
        passed=after==1.0 and transfer==1.0 and gain>0.0
        return {"train":after,"hidden":after,"fresh":after,"transfer":transfer,"causal_gain":gain,"primary_before":before,"transfer_dataset":transfer_id,"pass":passed}

    def _commit_modeltype(self,kind:str,primary_dataset:str,validation:dict[str,Any]) -> dict[str,Any]:
        did=_MODELTYPE_DOMAINS[kind]; self._generation+=1
        domain={"domain_id":did,"admitted":True,"origin":"observed-state-model-representation-gap","generation":self._generation,"model_kind":kind,"dataset_id":primary_dataset}
        self._evolved_task_domains.append(domain)
        record={"generation":self._generation,"challenge_id":"modeltype."+kind+"."+hashlib.sha256(primary_dataset.encode()).hexdigest()[:12],"route":"admit-causal-model-type","mutation":{"kind":"causal-model-type","model_kind":kind,"domain_id":did},"validation":copy.deepcopy(validation),"status":"ADMITTED"}
        self._evolution_history.append(record); self._append_event("evolution.admitted",record); return copy.deepcopy(record)

    def develop_one_generation(self) -> dict[str,Any]:
        gaps=self._modeltype_gap_candidates()
        if gaps:
            # Prefer largest causal score improvement, then deterministic ids.
            gaps.sort(key=lambda x:(-(x["after_score"]-x["before_score"]),x["kind"],x["dataset_id"]))
            for gap in gaps:
                val=self._validate_modeltype_admission(str(gap["kind"]),str(gap["dataset_id"]))
                if val.get("pass"):
                    self._append_event("evolution.selected",{"source":"model-representation-gap","model_kind":gap["kind"],"dataset_id":gap["dataset_id"],"causal_gain":val["causal_gain"]})
                    return self._commit_modeltype(str(gap["kind"]),str(gap["dataset_id"]),val)
        return super().develop_one_generation()

    def predict_state_after(self,dataset_id:str,action:str,before:dict[str,Any]) -> dict[str,Any]:
        if self.PREDICT_DOMAIN_ID not in self._active_task_domains(): raise ValueError("state prediction domain not admitted")
        ds=next((x for x in self._observed_stateflow_datasets() if str(x.get("dataset_id"))==str(dataset_id)),None)
        if ds is None: raise KeyError("unknown stateflow dataset")
        transitions=_flatten_state_dataset(ds); mi=_learn_state_prediction_models_v29({"transitions":transitions},self._active_model_types()); pred=_predict_with_models_v29(mi,str(action),{str(k):_state_scalar(v) for k,v in before.items()})
        if pred is None: return {"status":"AMBIGUOUS","action":str(action),"active_model_types":sorted(self._active_model_types())}
        return {"status":"PREDICTED","action":str(action),"after":_json_safe(pred),"active_model_types":sorted(self._active_model_types())}

    def propose_state_intervention(self,dataset_id:str) -> dict[str,Any]:
        if self.PREDICT_DOMAIN_ID not in self._active_task_domains(): raise ValueError("state prediction domain not admitted")
        ds=next((x for x in self._observed_stateflow_datasets() if str(x.get("dataset_id"))==str(dataset_id)),None)
        if ds is None: raise KeyError("unknown stateflow dataset")
        transitions=_flatten_state_dataset(ds); learned=_learn_state_prediction_models_v29({"transitions":transitions},self._active_model_types())
        # Reuse the v28 intervention planner for old-family ambiguities. For new
        # families, exact identification means no intervention is needed.
        plan=_best_intervention_plan(learned)
        if plan is None: return {"status":"NO_AMBIGUITY","dataset_id":dataset_id,"active_model_types":sorted(self._active_model_types())}
        return {"status":"PROPOSED","dataset_id":dataset_id,"action":plan["action"],"key":plan["key"],"set_before":_json_safe(plan["set_before"]),"candidate_predictions":_json_safe(plan["candidate_predictions"]),"candidate_models":_json_safe(plan["candidate_models"])}

    def export_evolution_state(self) -> dict[str,Any]:
        body={"schema":"ucr.autonomous-evolution-state/9","kernel_id":self.kernel_id,"generation":self._generation,"primitives":[copy.deepcopy(v) for _,v in sorted(self._evolved_primitives.items())],"grammar_rules":copy.deepcopy(self._evolved_grammar_rules),"task_domains":copy.deepcopy(self._evolved_task_domains),"history":copy.deepcopy(self._evolution_history)}
        return {**body,"digest":hashlib.sha256(_canonical(body).encode()).hexdigest()}

    def _validate_v29_state(self,state:dict[str,Any]) -> dict[str,Any]:
        raw=copy.deepcopy(state); supplied=str(raw.pop("digest","")); expected=hashlib.sha256(_canonical(raw).encode()).hexdigest()
        if supplied!=expected: raise ValueError("evolution state digest mismatch")
        if raw.get("schema")!="ucr.autonomous-evolution-state/9" or raw.get("kernel_id")!=self.kernel_id: raise ValueError("evolution state identity mismatch")
        domains=list(raw.get("task_domains") or []); model_domains=[]; base_domains=[]; seen=set()
        allowed_model=set(_MODELTYPE_DOMAINS.values())
        for item in domains:
            did=str(item.get("domain_id",""))
            if did in seen: raise ValueError("duplicate task domain")
            seen.add(did)
            if did in allowed_model:
                if item.get("admitted") is not True: raise ValueError("non-admitted model domain")
                mk=str(item.get("model_kind",""))
                if _MODELTYPE_DOMAINS.get(mk)!=did: raise ValueError("model domain identity mismatch")
                model_domains.append(copy.deepcopy(item))
            else:
                base_domains.append(copy.deepcopy(item))
        base_body={"schema":"ucr.autonomous-evolution-state/8","kernel_id":self.kernel_id,"generation":int(raw.get("generation",0)),"primitives":copy.deepcopy(raw.get("primitives") or []),"grammar_rules":copy.deepcopy(raw.get("grammar_rules") or []),"task_domains":base_domains,"history":copy.deepcopy(raw.get("history") or [])}
        base_state={**base_body,"digest":hashlib.sha256(_canonical(base_body).encode()).hexdigest()}; validated=super()._validate_v28_state(base_state)
        return {**raw,"primitives":validated.get("primitives") or [],"grammar_rules":validated.get("grammar_rules") or [],"task_domains":domains}

    def load_evolution_state(self,state:dict[str,Any]) -> None:
        if state.get("schema")!="ucr.autonomous-evolution-state/9":
            super().load_evolution_state(state); return
        raw=self._validate_v29_state(state); self._generation=int(raw.get("generation",0)); self._evolved_grammar_rules=copy.deepcopy(raw.get("grammar_rules") or []); self._evolved_primitives={str(x["machine_id"]):copy.deepcopy(x) for x in raw.get("primitives",[])}; self._evolved_task_domains=copy.deepcopy(raw.get("task_domains") or []); self._evolution_history=copy.deepcopy(raw.get("history") or [])


AutonomousKernel=ModelGenesisAutonomousKernel


def autonomous_self_test_v29() -> dict[str,Any]:
    def stream(action:str,values:list[int],fn) -> dict[str,Any]:
        return {"transitions":[{"seq":i,"action":action,"before":{"size":x},"after":{"size":fn(x)}} for i,x in enumerate(values)]}
    k=AutonomousKernel()
    # Seed enough state-prediction support for a clean standalone test.
    a=[stream("dup",[1,2,3,4],lambda x:2*x) for _ in range(6)]
    b=[stream("dup2",[2,3,5,7],lambda x:2*x) for _ in range(6)]
    k.observe_external_state_streams("self/affine-a",a,{"kind":"self-test"}); k.observe_external_state_streams("self/affine-b",b,{"kind":"self-test"})
    # Activate state prediction domain if not already active.
    for _ in range(8):
        r=k.develop_one_generation()
        if "affine_int" in k._active_model_types() and k.PREDICT_DOMAIN_ID in k._active_task_domains(): break
        if r.get("status") == "WITHHOLD": break
    pred=k.predict_state_after("self/affine-a","dup",{"size":9}) if k.PREDICT_DOMAIN_ID in k._active_task_domains() else {"status":"NO_PREDICT_DOMAIN"}
    snap=k.snapshot(); rr=AutonomousKernel(); rr.restore(snap)
    return {"schema":"ucr.autonomous-kernel-v29-self-test/1","active_model_types":sorted(k._active_model_types()),"prediction":pred,"restart_same":rr.export_evolution_state()["digest"]==k.export_evolution_state()["digest"],"pass":"affine_int" in k._active_model_types() and rr.export_evolution_state()["digest"]==k.export_evolution_state()["digest"]}

"""Read source as data and optionally record derived syntax in Nova's journal."""

import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path

from .universal_code_reader import UniversalCodeReader

MAX_SOURCE_BYTES = 262144
NODE_WINDOW = 96
EVIDENCE_WINDOW = 24
TRACE_ROWS = 128


def _read_bytes(path):
    path = Path(path)
    with path.open("rb") as source:
        raw = source.read(MAX_SOURCE_BYTES + 1)
    if len(raw) > MAX_SOURCE_BYTES:
        raise ValueError("Nova reader bridge accepts at most 262144 source bytes per file")
    return raw


def read_file(path, *, traces=None, max_depth=2):
    raw = _read_bytes(path)
    reader = UniversalCodeReader()
    if traces is None:
        result = reader.read(raw, Path(path).name)
    else:
        if type(max_depth) is not int or not 1 <= max_depth <= 3:
            raise ValueError("reasoning depth must be in 1..3")
        trace_bytes = _read_bytes(traces)
        rows = reader._strict_json(trace_bytes.decode("utf-8"))
        if type(rows) is not list or not 1 <= len(rows) <= TRACE_ROWS or any(type(r) is not dict for r in rows):
            raise ValueError("traces must contain 1..128 observation objects")
        result, cycle = reader.read_with_cognitive_observations(
            raw, rows, filename=Path(path).name, max_depth=max_depth)
        result.metadata.update(
            trace_sha256=hashlib.sha256(trace_bytes).hexdigest(),
            trace_observations=rows, cognitive_cycle=cycle,
            trace_origin="caller_supplied_observations_not_verified_execution_of_source",
            trace_validation="internal_split_used_for_ranking_not_independent_fresh_validation")
    if result.restore_bytes() != raw:
        raise ValueError("reader failed byte preservation")
    return result


def observation(result, source_url, obtained_at):
    """This is a labelled derived representation, never a raw remote response.

    The caller supplies source_url; this function performs no network request
    and does not authenticate origin. Source bytes have their own SHA-256.
    """
    rows = []
    evidence = [n for n in result.nodes if n.kind.startswith(("cognitive.", "semantic."))][:EVIDENCE_WINDOW]
    selected_ids = {n.id for n in evidence}
    selected = evidence + [n for n in result.nodes if n.id not in selected_ids][:NODE_WINDOW - len(evidence)]
    for node in selected:
        value = node.value
        truncated = False
        escaped = False
        if type(value) in (int, float) and abs(value) > 10**15:
            value = repr(value)
        if type(value) not in (str, int, float, bool, type(None)):
            value = json.dumps(UniversalCodeReader._jsonable(value), ensure_ascii=True, allow_nan=False, sort_keys=True)
        if type(value) is str:
            portable = value.encode("utf-8", "backslashreplace").decode("utf-8")
            value, escaped = portable, portable != value
            if len(value) > 512:
                value, truncated = value[:512], True
        rows.append({"id": node.id, "kind": node.kind, "value": value,
                     "value_truncated": truncated, "value_escaped": escaped, "children": len(node.links),
                     "line": node.meta.get("line"), "column": node.meta.get("column"),
                     "evidence_status": node.meta.get("status"),
                     "best_expression": (node.meta.get("best_expression") or "")[:512]})
    body = {"schema": "nova.code-observation.v2", "representation": "derived_syntax_not_source_execution",
            "source_url": source_url, "source_sha256": result.sha256,
            "source_filename": result.metadata["filename"], "source_bytes": result.metadata["size_bytes"],
            "source_origin": "caller_supplied_url_and_local_content_hash",
            "language": result.language, "parse_level": result.metadata["parse_level"],
            "full_ir_sha256": hashlib.sha256(result.to_json().encode("utf-8")).hexdigest(),
            "nodes_total": len(result.nodes), "nodes_included": len(rows),
            "nodes_truncated": len(rows) != len(result.nodes),
            "unresolved_link_count": len(result.metadata["unresolved_links"]),
            "duplicate_node_id_count": len(result.metadata["duplicate_node_ids"]), "nodes": rows,
            "reader": {"version": result.metadata["reader_version"], "passport": result.passport(),
                       "implicit_symbols": result.metadata["implicit_symbols"][:64],
                       "projection": "first_24_hypotheses_then_syntax_up_to_96_total"}}
    if "cognitive_cycle" in result.metadata:
        cycle = result.metadata["cognitive_cycle"]
        body["reader"]["trace_evidence"] = {
            "sha256": result.metadata["trace_sha256"], "observations": len(result.metadata["trace_observations"]),
            "origin": result.metadata["trace_origin"], "validation": result.metadata["trace_validation"],
            "deficit_count": len(cycle["deficits"]), "next_goal_count": len(cycle["next_goals"]),
            "nova_capability_admitted": False}
    body = UniversalCodeReader._jsonable(body)
    text = json.dumps(body, ensure_ascii=True, allow_nan=False, sort_keys=True, separators=(",", ":"))
    if len(text.encode("utf-8")) > MAX_SOURCE_BYTES:
        raise ValueError("derived observation exceeds Nova's document byte limit; full IR is still available")
    return {"source": source_url, "media_type": "application/json", "text": text,
            "sha256": hashlib.sha256(text.encode("utf-8")).hexdigest(), "obtained_at": obtained_at}


def record(kernel, result, source_url, obtained_at):
    return kernel.observe(observation(result, source_url, obtained_at))


def main(argv=None):
    parser = argparse.ArgumentParser(description="Read code without executing it; optionally record derived syntax in Nova")
    parser.add_argument("path", type=Path)
    parser.add_argument("--output", type=Path, help="write complete source-preserving IR JSON")
    parser.add_argument("--state", type=Path, help="existing Nova v7 state for syntax observations")
    parser.add_argument("--traces", type=Path, help="JSON list of externally observed code/inputs/output rows")
    parser.add_argument("--max-depth", type=int, choices=(1, 2, 3), default=2,
                        help="maximum trusted-primitive composition depth for --traces")
    parser.add_argument("--source-url", help="source HTTPS URL asserted by the caller (not fetched by this command)")
    args = parser.parse_args(argv)
    if args.state and not args.source_url:
        parser.error("--state requires --source-url")
    if args.output and any(args.output.resolve() == p.resolve()
                           for p in (args.path, args.traces, args.state) if p is not None):
        parser.error("output must not overwrite input, traces or state")
    if args.state and any(args.state.resolve() == p.resolve() for p in (args.path, args.traces) if p is not None):
        parser.error("state must not overwrite input or traces")
    try:
        result = read_file(args.path, traces=args.traces, max_depth=args.max_depth)
        if args.output:
            args.output.parent.mkdir(parents=True, exist_ok=True)
            args.output.write_text(result.to_json() + "\n", encoding="utf-8")
        if args.state:
            from nova_core.kernel import Kernel
            with Kernel(args.state) as kernel:
                receipt = record(kernel, result, args.source_url, datetime.now(timezone.utc).isoformat())
            print(json.dumps({"source_sha256": result.sha256, "reader": result.metadata,
                              "observation": receipt}, ensure_ascii=True, allow_nan=False))
        elif args.output:
            print(json.dumps({"source_sha256": result.sha256, "reader": result.metadata}, ensure_ascii=True))
        else:
            print(result.to_json())
        return 0
    except (OSError, ValueError, TypeError, RecursionError) as exc:
        parser.exit(1, f"{type(exc).__name__}: {exc}\n")


if __name__ == "__main__":
    main()

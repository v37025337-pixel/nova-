"""Read source as data and optionally record derived syntax in Nova's journal."""

import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path

from .universal_code_reader import UniversalCodeReader

MAX_SOURCE_BYTES = 262144
NODE_WINDOW = 96


def read_file(path):
    path = Path(path)
    with path.open("rb") as source:
        raw = source.read(MAX_SOURCE_BYTES + 1)
    if len(raw) > MAX_SOURCE_BYTES:
        raise ValueError("Nova reader bridge accepts at most 262144 source bytes per file")
    result = UniversalCodeReader().read(raw, path.name)
    if result.restore_bytes() != raw:
        raise ValueError("reader failed byte preservation")
    return result


def observation(result, source_url, obtained_at):
    """This is a labelled derived representation, never a raw remote response.

    The caller supplies source_url; this function performs no network request
    and does not authenticate origin. Source bytes have their own SHA-256.
    """
    rows = []
    for node in result.nodes[:NODE_WINDOW]:
        value = node.value
        truncated = False
        escaped = False
        if type(value) in (int, float) and abs(value) > 10**15:
            value = repr(value)
        if type(value) is str and len(value) > 512:
            value, truncated = value[:512], True
        if type(value) is str:
            portable = value.encode("utf-8", "backslashreplace").decode("utf-8")
            value, escaped = portable, portable != value
        rows.append({"id": node.id, "kind": node.kind, "value": value,
                     "value_truncated": truncated, "value_escaped": escaped, "children": len(node.links),
                     "line": node.meta.get("line"), "column": node.meta.get("column")})
    body = {"schema": "nova.code-observation.v1", "representation": "derived_syntax_not_source_execution",
            "source_url": source_url, "source_sha256": result.sha256,
            "source_filename": result.metadata["filename"], "source_bytes": result.metadata["size_bytes"],
            "source_origin": "caller_supplied_url_and_local_content_hash",
            "language": result.language, "parse_level": result.metadata["parse_level"],
            "full_ir_sha256": hashlib.sha256(result.to_json().encode("utf-8")).hexdigest(),
            "nodes_total": len(result.nodes), "nodes_included": len(rows),
            "nodes_truncated": len(rows) != len(result.nodes),
            "unresolved_link_count": len(result.metadata["unresolved_links"]),
            "duplicate_node_id_count": len(result.metadata["duplicate_node_ids"]), "nodes": rows}
    text = json.dumps(body, ensure_ascii=True, allow_nan=False, sort_keys=True, separators=(",", ":"))
    return {"source": source_url, "media_type": "application/json", "text": text,
            "sha256": hashlib.sha256(text.encode("utf-8")).hexdigest(), "obtained_at": obtained_at}


def record(kernel, result, source_url, obtained_at):
    return kernel.observe(observation(result, source_url, obtained_at))


def main(argv=None):
    parser = argparse.ArgumentParser(description="Read code without executing it; optionally record derived syntax in Nova")
    parser.add_argument("path", type=Path)
    parser.add_argument("--output", type=Path, help="write complete source-preserving IR JSON")
    parser.add_argument("--state", type=Path, help="existing Nova v7 state for syntax observations")
    parser.add_argument("--source-url", help="source HTTPS URL asserted by the caller (not fetched by this command)")
    args = parser.parse_args(argv)
    if args.state and not args.source_url:
        parser.error("--state requires --source-url")
    if args.output and args.output.resolve() == args.path.resolve():
        parser.error("output must not overwrite the input source")
    try:
        result = read_file(args.path)
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
    except (OSError, ValueError) as exc:
        parser.exit(1, f"{type(exc).__name__}: {exc}\n")


if __name__ == "__main__":
    main()

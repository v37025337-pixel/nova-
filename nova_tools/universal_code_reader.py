
from __future__ import annotations

import ast
import base64
import hashlib
import json
import math
import re
from collections import Counter
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Any, Callable


@dataclass
class IRNode:
    id: str
    kind: str
    value: Any = None
    links: list[str] = field(default_factory=list)
    meta: dict[str, Any] = field(default_factory=dict)


@dataclass
class ReadResult:
    sha256: str
    language: str
    encoding: str
    lossless_source: str
    nodes: list[IRNode]
    metadata: dict[str, Any] = field(default_factory=dict)
    source_base64: str = ""

    def restore_bytes(self) -> bytes:
        raw = base64.b64decode(self.source_base64, validate=True)
        if hashlib.sha256(raw).hexdigest() != self.sha256:
            raise ValueError("original source hash does not match retained bytes")
        return raw

    def to_json(self) -> str:
        return json.dumps(
            {
                "sha256": self.sha256,
                "language": self.language,
                "encoding": self.encoding,
                "source": self.lossless_source,
                "source_base64": self.source_base64,
                "nodes": [asdict(n) for n in self.nodes],
                "metadata": self.metadata,
            },
            ensure_ascii=True,
            allow_nan=False,
            separators=(",", ":"),
        )


class UniversalCodeReader:
    """
    Reads arbitrary bytes without executing them.

    Layer 1: lossless ingestion
    Layer 2: syntax recognition when possible
    Layer 3: normalized AI-readable IR
    """

    EXTENSIONS = {
        ".py": "python",
        ".pyw": "python",
        ".json": "json",
        ".js": "javascript",
        ".mjs": "javascript",
        ".cjs": "javascript",
        ".ts": "typescript",
        ".tsx": "typescript",
        ".jsx": "javascript",
        ".java": "java",
        ".c": "c",
        ".h": "c",
        ".cc": "cpp",
        ".cpp": "cpp",
        ".cxx": "cpp",
        ".hpp": "cpp",
        ".rs": "rust",
        ".go": "go",
        ".rb": "ruby",
        ".php": "php",
        ".cs": "csharp",
        ".swift": "swift",
        ".kt": "kotlin",
        ".kts": "kotlin",
        ".scala": "scala",
        ".sh": "shell",
        ".bash": "shell",
        ".zsh": "shell",
        ".ps1": "powershell",
        ".sql": "sql",
        ".html": "html",
        ".htm": "html",
        ".xml": "xml",
        ".css": "css",
        ".wasm": "wasm",
        ".class": "jvm-bytecode",
        ".dll": "binary",
        ".exe": "binary",
        ".bin": "binary",
        ".aic": "ai-native",
    }

    TOKEN_RE = re.compile(
        r"""
        (?P<ws>\s+)
      | (?P<comment>//[^\n]*|/\*.*?\*/|\#[^\n]*)
      | (?P<string>"(?:\\.|[^"\\])*"|'(?:\\.|[^'\\])*')
      | (?P<number>\b(?:0x[0-9A-Fa-f]+|0b[01]+|\d+(?:\.\d+)?)\b)
      | (?P<identifier>[A-Za-z_$][A-Za-z0-9_$]*)
      | (?P<operator>==|!=|<=|>=|=>|->|::|\+\+|--|&&|\|\||<<|>>|[-+*/%=<>!&|^~?:.]+)
      | (?P<punct>[()\[\]{};,])
      | (?P<other>.)
        """,
        re.VERBOSE | re.DOTALL,
    )

    def __init__(self):
        self.parsers: dict[str, Callable[[str], list[IRNode]]] = {
            "python": self._parse_python,
            "json": self._parse_json,
            "ai-native": self._parse_ai_native,
        }

    def register_parser(
        self, language: str, parser: Callable[[str], list[IRNode]]
    ) -> None:
        self.parsers[language.lower()] = parser

    def read(
        self,
        payload: bytes | bytearray | memoryview | str,
        filename: str | None = None,
    ) -> ReadResult:
        raw = payload.encode("utf-8") if isinstance(payload, str) else bytes(payload)
        digest = hashlib.sha256(raw).hexdigest()

        text, encoding, is_binary = self._decode_lossless(raw)
        language = self._detect_language(text, filename, is_binary)

        if is_binary or language in {"binary", "wasm", "jvm-bytecode"}:
            text, encoding, is_binary = base64.b64encode(raw).decode("ascii"), "base64", True
            nodes = self._parse_binary(raw)
            parse_level = "bytes"
        else:
            parser = self.parsers.get(language, self._parse_generic)
            parse_level = ("ast" if language == "python" else "json_tree" if language == "json"
                           else "graph_syntax" if language == "ai-native" else
                           "custom_syntax" if language in self.parsers else "tokens")
            try:
                nodes = parser(text)
            except Exception as exc:
                # Never lose the original input because a parser failed.
                nodes = self._parse_generic(text)
                parse_level = "tokens"
                nodes.insert(
                    0,
                    IRNode(
                        id="parser-error",
                        kind="parser_error",
                        value=type(exc).__name__,
                        meta={"message": str(exc)},
                    ),
                )

        ids = Counter(n.id for n in nodes)
        return ReadResult(
            sha256=digest,
            language=language,
            encoding=encoding,
            lossless_source=text,
            nodes=nodes,
            source_base64=base64.b64encode(raw).decode("ascii"),
            metadata={
                "size_bytes": len(raw),
                "filename": filename,
                "binary": is_binary,
                "node_count": len(nodes),
                "parse_level": parse_level,
                "unresolved_links": sorted({link for n in nodes for link in n.links if link not in ids}),
                "duplicate_node_ids": sorted(nid for nid, count in ids.items() if count > 1),
                "executes_source": False,
            },
        )

    def _decode_lossless(self, raw: bytes) -> tuple[str, str, bool]:
        if not raw:
            return "", "utf-8", False

        if raw.startswith(b"\xef\xbb\xbf"):
            try:
                return raw.decode("utf-8-sig"), "utf-8-sig", False
            except UnicodeDecodeError:
                return base64.b64encode(raw).decode("ascii"), "base64", True
        if raw.startswith((b"\xff\xfe", b"\xfe\xff")):
            try:
                return raw.decode("utf-16"), "utf-16", False
            except UnicodeDecodeError:
                pass

        # NUL-heavy inputs are probably binary.
        if raw.count(b"\x00") / len(raw) > 0.03:
            return base64.b64encode(raw).decode("ascii"), "base64", True

        for enc in ("utf-8", "utf-16-le", "utf-16-be"):
            try:
                text = raw.decode(enc)
                # Avoid accepting a nonsensical UTF-16 interpretation.
                if enc.startswith("utf-16") and "\x00" in text:
                    continue
                return text, enc, False
            except UnicodeDecodeError:
                pass

        # latin-1 is byte-preserving: every byte maps 1:1 to a code point.
        text = raw.decode("latin-1")
        control = sum(ord(ch) < 32 and ch not in "\n\r\t" for ch in text)
        if control / max(1, len(text)) > 0.08:
            return base64.b64encode(raw).decode("ascii"), "base64", True
        return text, "latin-1", False

    def _detect_language(
        self, text: str, filename: str | None, is_binary: bool
    ) -> str:
        if filename:
            ext = Path(filename).suffix.lower()
            if ext in self.EXTENSIONS:
                return self.EXTENSIONS[ext]

        if is_binary:
            return "binary"

        s = text.lstrip()

        if s.startswith(("{", "[")):
            try:
                json.loads(text)
                return "json"
            except Exception:
                pass

        if re.search(r"^\s*(async\s+)?def\s+\w+\s*\(", text, re.M) or \
           re.search(r"^\s*class\s+\w+\s*[:(]", text, re.M):
            return "python"

        if re.search(r"\b(function|const|let|var)\b", text) and \
           ("=>" in text or "{" in text):
            return "javascript"

        if "#include" in text or re.search(r"\b(int|char|void|struct)\s+\w+\s*\(", text):
            return "c-like"

        if re.search(r"^\s*[A-Za-z0-9_-]+\s*:\s*$", text, re.M) and \
           "->" in text:
            return "ai-native"

        return "unknown-text"

    def _node_id(self, *parts: Any) -> str:
        data = "\x1f".join(map(str, parts)).encode("utf-8", "surrogatepass")
        return hashlib.sha256(data).hexdigest()[:16]

    def _parse_python(self, text: str) -> list[IRNode]:
        tree = ast.parse(text)
        nodes: list[IRNode] = []

        def visit(item: ast.AST, path: str) -> str:
            value = None
            if isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                value = item.name
            elif isinstance(item, ast.Name):
                value = item.id
            elif isinstance(item, ast.Constant):
                value = item.value if isinstance(
                    item.value, (str, int, float, bool, type(None))
                ) else repr(item.value)
                if isinstance(value, float) and not math.isfinite(value):
                    value = repr(value)

            lineno = getattr(item, "lineno", None)
            col = getattr(item, "col_offset", None)
            # AST context/operator objects can be shared singleton instances.
            # Identify each occurrence by its tree path, using the exact same
            # returned identity in parent edges (including Constant nodes).
            nid = self._node_id("python", path, type(item).__name__)
            children = [visit(child, f"{path}/{index}")
                        for index, child in enumerate(ast.iter_child_nodes(item))]

            nodes.append(
                IRNode(
                    id=nid,
                    kind=f"python.{type(item).__name__}",
                    value=value,
                    links=children,
                    meta={"line": lineno, "column": col, "path": path},
                )
            )
            return nid

        visit(tree, "$")
        return nodes

    def _parse_json(self, text: str) -> list[IRNode]:
        def unique_pairs(pairs):
            result = {}
            for key, value in pairs:
                if key in result:
                    raise ValueError("duplicate JSON key: " + key)
                result[key] = value
            return result

        def reject_constant(value):
            raise ValueError("nonstandard JSON constant: " + value)

        obj = json.loads(text, object_pairs_hook=unique_pairs, parse_constant=reject_constant)
        nodes: list[IRNode] = []

        def walk(value: Any, path: str) -> str:
            nid = self._node_id("json", path)
            links: list[str] = []

            if isinstance(value, dict):
                for key, child in value.items():
                    segment = key.replace("~", "~0").replace("/", "~1")
                    links.append(walk(child, f"{path}/{segment}"))
                node_value = None
                kind = "json.object"
            elif isinstance(value, list):
                for i, child in enumerate(value):
                    links.append(walk(child, f"{path}/{i}"))
                node_value = None
                kind = "json.array"
            else:
                if isinstance(value, float) and not math.isfinite(value):
                    raise ValueError("JSON number exceeds finite representation")
                node_value = value
                kind = f"json.{type(value).__name__}"

            nodes.append(
                IRNode(
                    id=nid,
                    kind=kind,
                    value=node_value,
                    links=links,
                    meta={"path": path},
                )
            )
            return nid

        walk(obj, "$")
        return nodes

    def _parse_ai_native(self, text: str) -> list[IRNode]:
        """
        Accepts lines such as:
            08A1:
                01 -> 011F
                02 -> 77C2
        Unknown syntax is retained as raw nodes.
        """
        nodes: list[IRNode] = []
        current: str | None = None

        for lineno, raw_line in enumerate(text.splitlines(), 1):
            line = raw_line.strip()
            if not line:
                continue

            m_head = re.fullmatch(r"([A-Za-z0-9_-]+):", line)
            if m_head:
                current = m_head.group(1)
                nodes.append(
                    IRNode(
                        id=current,
                        kind="ai.atom",
                        meta={"line": lineno},
                    )
                )
                continue

            m_edge = re.fullmatch(
                r"([A-Za-z0-9_.-]+)\s*->\s*([A-Za-z0-9_.-]+)", line
            )
            if m_edge and current:
                relation, target = m_edge.groups()
                nodes.append(
                    IRNode(
                        id=self._node_id(current, relation, target, lineno),
                        kind="ai.edge",
                        value=relation,
                        links=[current, target],
                        meta={"line": lineno},
                    )
                )
                continue

            nodes.append(
                IRNode(
                    id=self._node_id("raw", lineno, line),
                    kind="ai.raw",
                    value=line,
                    links=[current] if current else [],
                    meta={"line": lineno},
                )
            )

        return nodes

    def _parse_generic(self, text: str) -> list[IRNode]:
        """
        Language-independent fallback lexer.
        It does not claim semantic understanding, but it preserves structure.
        """
        nodes: list[IRNode] = []
        bracket_stack: list[tuple[str, str]] = []
        matching = {")": "(", "]": "[", "}": "{"}

        token_index = 0
        for match in self.TOKEN_RE.finditer(text):
            kind = match.lastgroup or "other"
            value = match.group(0)

            if kind == "ws":
                continue

            nid = self._node_id("token", token_index, kind, value)
            links: list[str] = []

            if kind == "punct":
                if value in "([{":
                    bracket_stack.append((value, nid))
                elif value in ")]}":
                    expected = matching[value]
                    if bracket_stack and bracket_stack[-1][0] == expected:
                        _, opener_id = bracket_stack.pop()
                        links.append(opener_id)

            nodes.append(
                IRNode(
                    id=nid,
                    kind=f"token.{kind}",
                    value=value,
                    links=links,
                    meta={"start": match.start(), "end": match.end()},
                )
            )
            token_index += 1

        return nodes

    def _parse_binary(self, raw: bytes) -> list[IRNode]:
        nodes: list[IRNode] = []
        chunk_size = 64

        for offset in range(0, len(raw), chunk_size):
            chunk = raw[offset : offset + chunk_size]
            nodes.append(
                IRNode(
                    id=self._node_id("binary", offset, chunk.hex()),
                    kind="binary.chunk",
                    value=base64.b64encode(chunk).decode("ascii"),
                    meta={
                        "offset": offset,
                        "length": len(chunk),
                        "hex_prefix": chunk[:16].hex(),
                    },
                )
            )
        return nodes


if __name__ == "__main__":
    reader = UniversalCodeReader()

    sample = b"""
08A1:
    01 -> 011F
    02 -> 77C2
    03 -> A901
"""

    result = reader.read(sample, "sample.aic")
    print(result.to_json())

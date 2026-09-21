from __future__ import annotations

"""
Universal Code Reader (UCR)
===========================
A safe, dependency-free reader that converts arbitrary source/binary input into a
stable AI-readable intermediate representation (AI-IR) *without executing it*.

Design goals:
- lossless ingestion of text or bytes;
- detect common formats, but never require a known language;
- structural fallback for unknown / machine-created languages;
- expose relations (sequence, nesting, calls, assignments, repeated forms);
- infer recurring surface grammar patterns without pretending to know semantics;
- infer bounded stateful/chain semantics from externally observed traces;
- reconstruct data-flow and observed control-flow without executing unknown code;
- infer trace-derived ISA roles such as load/store, call/return and indirect jumps;
- infer observed addressing modes and bounded calling-convention evidence;
- reconstruct function entries/invocations and bounded ABI carrier evidence;
- infer observed inter-component message protocols from annotated external traces;
- build a bounded behavioral emulator from trace-supported rules without executing unknown code;
- diagnose reasoning deficits as capacity, search-budget or evidence problems;
- choose bounded strategy changes and validate them on fresh data before admission;
- expose a bounded cognitive profile without claiming human IQ/general intelligence;
- discover representation gaps and synthesize/admit bounded safe semantic primitives;
- validate self-development with hidden/fresh tests, transfer, ablation and rollback;
- evolve the active safe primitive-generation grammar through causally admitted bounded rules;
- preserve binary inputs as chunks + printable-string evidence;
- deterministic IDs and JSON output;
- extensible parser registry.

This module does not promise semantic understanding of every possible language.
For an unknown language it produces evidence-rich structure that another system
can use to infer semantics experimentally.
"""

import ast
import copy
import base64
import bisect
import difflib
import hashlib
import itertools
import json
import math
import re
import statistics
import unicodedata
import xml.etree.ElementTree as ET
from collections import Counter, defaultdict
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Callable, Iterable, Iterator


# ---------------------------------------------------------------------------
# Public IR
# ---------------------------------------------------------------------------

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
        """Recover the exact input, including BOMs and original byte order."""
        raw = base64.b64decode(self.source_base64, validate=True)
        if hashlib.sha256(raw).hexdigest() != self.sha256:
            raise ValueError("original source hash does not match retained bytes")
        return raw

    def to_dict(self) -> dict[str, Any]:
        return UniversalCodeReader._jsonable({
            "schema": "ucr.ai-ir/16.0",
            "sha256": self.sha256,
            "language": self.language,
            "encoding": self.encoding,
            "source": self.lossless_source,
            "source_base64": self.source_base64,
            "nodes": [asdict(n) for n in self.nodes],
            "metadata": self.metadata,
        })

    def to_json(self, *, pretty: bool = False) -> str:
        return json.dumps(
            self.to_dict(),
            ensure_ascii=True,
            allow_nan=False,
            indent=2 if pretty else None,
            separators=None if pretty else (",", ":"),
            default=str,
        )

    def nodes_of(self, prefix: str) -> list[IRNode]:
        return [n for n in self.nodes if n.kind.startswith(prefix)]

    def passport(self) -> dict[str, Any]:
        """Compact structural summary intended for transfer to another AI."""
        kind_counts = Counter(n.kind for n in self.nodes)
        families = Counter(n.kind.split(".", 1)[0] for n in self.nodes)
        operators = []
        semantic_hypotheses = []
        for node in self.nodes:
            if node.kind == "learned.operator_profile":
                operators.append({
                    "symbol": node.value,
                    "role": node.meta.get("role_hypothesis"),
                })
            elif node.kind == "semantic.symbol_hypothesis":
                semantic_hypotheses.append({
                    "symbol": node.value,
                    "status": node.meta.get("status"),
                    "confidence": node.meta.get("confidence"),
                    "form": node.meta.get("form"),
                    "arity": node.meta.get("arity"),
                })
        statements = [n.value for n in self.nodes if n.kind == "canonical.statement"]
        signature_material = json.dumps(statements, ensure_ascii=True, sort_keys=True, default=str)
        return {
            "schema": "ucr.passport/4",
            "sha256": self.sha256,
            "language": self.language,
            "encoding": self.encoding,
            "families": dict(families),
            "top_node_kinds": kind_counts.most_common(32),
            "operators": operators[:64],
            "semantic_hypotheses": semantic_hypotheses[:64],
            "stateful_semantics": self.metadata.get("stateful_semantics"),
            "vm_profile": self.metadata.get("vm_profile"),
            "function_model": self.metadata.get("function_model"),
            "abi_profile": self.metadata.get("abi_profile"),
            "protocol_model": self.metadata.get("protocol_model"),
            "isa_summary": {
                "instruction_count": self.metadata.get("stateful_semantics", {}).get("isa_instruction_count"),
                "addressing_mode_count": self.metadata.get("stateful_semantics", {}).get("addressing_mode_count"),
            },
            "structural_digest": hashlib.sha256(signature_material.encode("utf-8")).hexdigest(),
            "safe_mode": self.metadata.get("safe_mode"),
        }


@dataclass
class GrammarRule:
    pattern: tuple[str, ...]
    count: int
    probability: float
    examples: list[str] = field(default_factory=list)


@dataclass
class GrammarModel:
    language: str
    sample_count: int
    token_count: int
    rules: list[GrammarRule] = field(default_factory=list)
    operator_profiles: dict[str, dict[str, Any]] = field(default_factory=dict)
    vocabulary: dict[str, int] = field(default_factory=dict)
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "language": self.language,
            "sample_count": self.sample_count,
            "token_count": self.token_count,
            "rules": [asdict(r) for r in self.rules],
            "operator_profiles": self.operator_profiles,
            "vocabulary": self.vocabulary,
            "metadata": self.metadata,
        }

    def to_json(self, *, pretty: bool = False) -> str:
        return json.dumps(
            self.to_dict(),
            ensure_ascii=False,
            indent=2 if pretty else None,
            separators=None if pretty else (",", ":"),
            default=str,
        )


@dataclass
class SemanticCandidate:
    semantic_id: str
    label: str
    score: float
    matched: int
    total: int
    behavioral_digest: str
    meta: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class SymbolSemantics:
    symbol: str
    form: str
    arity: int
    observations: int
    confidence: float
    status: str
    candidates: list[SemanticCandidate] = field(default_factory=list)
    suggested_probes: list[dict[str, Any]] = field(default_factory=list)
    evidence: list[dict[str, Any]] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "symbol": self.symbol,
            "form": self.form,
            "arity": self.arity,
            "observations": self.observations,
            "confidence": self.confidence,
            "status": self.status,
            "candidates": [c.to_dict() for c in self.candidates],
            "suggested_probes": self.suggested_probes,
            "evidence": self.evidence,
        }


@dataclass
class SemanticModel:
    observation_count: int
    symbols: dict[str, SymbolSemantics] = field(default_factory=dict)
    unresolved: list[dict[str, Any]] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema": "ucr.semantic-model/1",
            "observation_count": self.observation_count,
            "symbols": {k: v.to_dict() for k, v in self.symbols.items()},
            "unresolved": self.unresolved,
            "metadata": self.metadata,
        }

    def to_json(self, *, pretty: bool = False) -> str:
        return json.dumps(
            self.to_dict(),
            ensure_ascii=False,
            indent=2 if pretty else None,
            separators=None if pretty else (",", ":"),
            default=str,
        )


@dataclass
class ReasoningCandidate:
    expression: str
    train_score: float
    holdout_score: float | None
    combined_score: float
    complexity: int
    depth: int
    matched_train: int
    train_total: int
    matched_holdout: int
    holdout_total: int
    behavioral_digest: str
    tree: Any = None
    meta: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data.pop("tree", None)
        return data


@dataclass
class ReasoningSymbol:
    symbol: str
    form: str
    arity: int
    observations: int
    status: str
    confidence: float
    candidates: list[ReasoningCandidate] = field(default_factory=list)
    suggested_probes: list[dict[str, Any]] = field(default_factory=list)
    diagnostics: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "symbol": self.symbol,
            "form": self.form,
            "arity": self.arity,
            "observations": self.observations,
            "status": self.status,
            "confidence": self.confidence,
            "candidates": [c.to_dict() for c in self.candidates],
            "suggested_probes": self.suggested_probes,
            "diagnostics": self.diagnostics,
        }


@dataclass
class CognitiveReasoningModel:
    observation_count: int
    symbols: dict[str, ReasoningSymbol] = field(default_factory=dict)
    profile: dict[str, Any] = field(default_factory=dict)
    unresolved: list[dict[str, Any]] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema": "ucr.cognitive-reasoning-model/1",
            "observation_count": self.observation_count,
            "symbols": {k: v.to_dict() for k, v in self.symbols.items()},
            "profile": self.profile,
            "unresolved": self.unresolved,
            "metadata": self.metadata,
        }

    def to_json(self, *, pretty: bool = False) -> str:
        return json.dumps(
            self.to_dict(), ensure_ascii=False,
            indent=2 if pretty else None, separators=None if pretty else (",", ":"), default=str,
        )


@dataclass
class StateTransition:
    observation: int
    step: int
    line: int | None
    instruction: str | None
    symbol: str | None
    target: str | None
    reads: list[str] = field(default_factory=list)
    writes: list[str] = field(default_factory=list)
    deletes: list[str] = field(default_factory=list)
    side_effect_writes: list[str] = field(default_factory=list)
    before_digest: str = ""
    after_digest: str = ""
    confidence: float = 0.0

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class ProgramSemanticCandidate:
    mapping: dict[str, str]
    score: float
    matched_checks: int
    total_checks: int
    successful_runs: int
    total_runs: int
    behavioral_digest: str
    meta: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)




@dataclass
class EmulatorRule:
    symbol: str
    kind: str
    confidence: float
    evidence: int
    executable: bool = False
    source_control: Any = None
    target_control: Any = None
    destination: str | None = None
    sources: list[str] = field(default_factory=list)
    semantic: str | None = None
    value: Any = None
    memory_space: str | None = None
    address_source: str | None = None
    offset: int = 0
    stack: str | None = None
    predicate: dict[str, Any] | None = None
    true_target: Any = None
    false_target: Any = None
    meta: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class BehavioralEmulatorModel:
    status: str
    control_register: str | None
    fallthrough_delta: int | None
    rules: dict[str, list[EmulatorRule]] = field(default_factory=dict)
    unresolved_symbols: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema": "ucr.behavioral-emulator-model/1",
            "status": self.status,
            "control_register": self.control_register,
            "fallthrough_delta": self.fallthrough_delta,
            "rules": {symbol: [rule.to_dict() for rule in rules] for symbol, rules in self.rules.items()},
            "unresolved_symbols": self.unresolved_symbols,
            "metadata": self.metadata,
        }

    def to_json(self, *, pretty: bool = False) -> str:
        return json.dumps(
            self.to_dict(), ensure_ascii=False,
            indent=2 if pretty else None, separators=None if pretty else (",", ":"), default=str,
        )


@dataclass
class EmulationResult:
    status: str
    halted_reason: str
    steps: int
    final_state: dict[str, Any]
    trace: list[dict[str, Any]] = field(default_factory=list)
    unresolved: list[dict[str, Any]] = field(default_factory=list)
    confidence: float = 0.0
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema": "ucr.behavioral-emulation-result/1",
            "status": self.status,
            "halted_reason": self.halted_reason,
            "steps": self.steps,
            "final_state": self.final_state,
            "trace": self.trace,
            "unresolved": self.unresolved,
            "confidence": self.confidence,
            "metadata": self.metadata,
        }

    def to_json(self, *, pretty: bool = False) -> str:
        return json.dumps(
            self.to_dict(), ensure_ascii=False,
            indent=2 if pretty else None, separators=None if pretty else (",", ":"), default=str,
        )


@dataclass
class StatefulSemanticModel:
    observation_count: int
    symbols: dict[str, SymbolSemantics] = field(default_factory=dict)
    transitions: list[StateTransition] = field(default_factory=list)
    dependencies: list[dict[str, Any]] = field(default_factory=list)
    control_flow_edges: list[dict[str, Any]] = field(default_factory=list)
    branch_hypotheses: list[dict[str, Any]] = field(default_factory=list)
    loop_hypotheses: list[dict[str, Any]] = field(default_factory=list)
    memory_model: dict[str, Any] = field(default_factory=dict)
    instruction_set: list[dict[str, Any]] = field(default_factory=list)
    addressing_modes: list[dict[str, Any]] = field(default_factory=list)
    calling_convention: dict[str, Any] = field(default_factory=dict)
    function_model: dict[str, Any] = field(default_factory=dict)
    abi_profile: dict[str, Any] = field(default_factory=dict)
    protocol_model: dict[str, Any] = field(default_factory=dict)
    emulator_model: BehavioralEmulatorModel | None = None
    vm_profile: dict[str, Any] = field(default_factory=dict)
    program_candidates: list[ProgramSemanticCandidate] = field(default_factory=list)
    unresolved: list[dict[str, Any]] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema": "ucr.stateful-semantic-model/5",
            "observation_count": self.observation_count,
            "symbols": {k: v.to_dict() for k, v in self.symbols.items()},
            "transitions": [t.to_dict() for t in self.transitions],
            "dependencies": self.dependencies,
            "control_flow_edges": self.control_flow_edges,
            "branch_hypotheses": self.branch_hypotheses,
            "loop_hypotheses": self.loop_hypotheses,
            "memory_model": self.memory_model,
            "instruction_set": self.instruction_set,
            "addressing_modes": self.addressing_modes,
            "calling_convention": self.calling_convention,
            "function_model": self.function_model,
            "abi_profile": self.abi_profile,
            "protocol_model": self.protocol_model,
            "emulator_model": self.emulator_model.to_dict() if self.emulator_model is not None else None,
            "vm_profile": self.vm_profile,
            "program_candidates": [c.to_dict() for c in self.program_candidates],
            "unresolved": self.unresolved,
            "metadata": self.metadata,
        }

    def to_json(self, *, pretty: bool = False) -> str:
        return json.dumps(
            self.to_dict(),
            ensure_ascii=False,
            indent=2 if pretty else None,
            separators=None if pretty else (",", ":"),
            default=str,
        )


Parser = Callable[[str], list[IRNode]]


# ---------------------------------------------------------------------------
# Reader
# ---------------------------------------------------------------------------

class UniversalCodeReader:
    """Read arbitrary code/data into AI-IR without executing the input."""

    VERSION = "16.0"

    EXTENSIONS = {
        ".py": "python", ".pyw": "python",
        ".json": "json", ".jsonl": "jsonl",
        ".js": "javascript", ".mjs": "javascript", ".cjs": "javascript",
        ".ts": "typescript", ".tsx": "typescript", ".jsx": "javascript",
        ".java": "java", ".c": "c", ".h": "c", ".cc": "cpp",
        ".cpp": "cpp", ".cxx": "cpp", ".hpp": "cpp",
        ".rs": "rust", ".go": "go", ".rb": "ruby", ".php": "php",
        ".cs": "csharp", ".swift": "swift", ".kt": "kotlin",
        ".kts": "kotlin", ".scala": "scala", ".dart": "dart",
        ".sh": "shell", ".bash": "shell", ".zsh": "shell",
        ".fish": "shell", ".ps1": "powershell",
        ".sql": "sql", ".lua": "lua", ".r": "r",
        ".html": "html", ".htm": "html", ".xml": "xml",
        ".svg": "xml", ".css": "css", ".scss": "scss",
        ".yaml": "yaml", ".yml": "yaml", ".toml": "toml",
        ".md": "markdown",
        ".wasm": "wasm", ".class": "jvm-bytecode",
        ".dll": "pe-binary", ".exe": "pe-binary", ".so": "elf-binary",
        ".o": "binary", ".a": "binary", ".bin": "binary",
        ".aic": "ai-native", ".air": "ai-native",
        ".wat": "webassembly-text", ".ll": "llvm-ir", ".bc": "llvm-bitcode",
        ".dex": "android-dex", ".smali": "smali", ".zig": "zig",
        ".nim": "nim", ".ex": "elixir", ".exs": "elixir",
        ".erl": "erlang", ".hrl": "erlang", ".fs": "fsharp", ".fsx": "fsharp",
        ".clj": "clojure", ".cljs": "clojure", ".hs": "haskell",
        ".ml": "ocaml", ".mli": "ocaml", ".asm": "assembly", ".s": "assembly",
        ".v": "verilog", ".sv": "systemverilog",
    }

    # Order matters: comments/strings must be recognized before operators.
    TOKEN_RE = re.compile(
        r"""
        (?P<ws>\s+)
      | (?P<block_comment>/\*.*?\*/|\(\*.*?\*\)|<!--.*?-->)
      | (?P<directive>\#\s*(?:include|define|if|ifdef|ifndef|endif|elif|else|pragma|error|line|undef)\b[^\n]*)
      | (?P<line_comment>//[^\n]*|\#[^\n]*)
      | (?P<triple_string>\"\"\"(?:\\.|[\s\S])*?\"\"\"|'''(?:\\.|[\s\S])*?''')
      | (?P<string>\"(?:\\.|[^\"\\])*\"|'(?:\\.|[^'\\])*'|`(?:\\.|[^`\\])*`)
      | (?P<number>\b(?:0[xX][0-9A-Fa-f_]+|0[bB][01_]+|0[oO][0-7_]+|(?:\d[\d_]*)(?:\.\d[\d_]*)?(?:[eE][+-]?\d[\d_]*)?)\b)
      | (?P<identifier>(?:[^\W\d]|[$_])(?:\w|[$])*)
      | (?P<operator><=>|===|!==|>>>|<<=|>>=|\*\*|:=|::|=>|->|<-|==|!=|<=|>=|\+\+|--|&&|\|\||\?\?|\?\.|<<|>>|[-+*/%=<>!&|^~?:.@]+)
      | (?P<punct>[()\[\]{};,])
      | (?P<other>.)
        """,
        re.VERBOSE | re.DOTALL | re.UNICODE,
    )

    MAGIC = (
        (b"\x00asm", "wasm"),
        (b"\xca\xfe\xba\xbe", "jvm-bytecode"),
        (b"dex\n", "android-dex"),
        (b"BC\xc0\xde", "llvm-bitcode"),
        (b"\x7fELF", "elf-binary"),
        (b"MZ", "pe-binary"),
        (b"\xfe\xed\xfa\xce", "mach-o"),
        (b"\xce\xfa\xed\xfe", "mach-o"),
        (b"\xfe\xed\xfa\xcf", "mach-o"),
        (b"\xcf\xfa\xed\xfe", "mach-o"),
        (b"PK\x03\x04", "zip-container"),
    )

    OPEN_TO_CLOSE = {"(": ")", "[": "]", "{": "}"}
    CLOSE_TO_OPEN = {v: k for k, v in OPEN_TO_CLOSE.items()}

    CONTROL_WORDS = {
        "if", "else", "elif", "for", "while", "switch", "case", "match",
        "try", "catch", "except", "finally", "return", "yield", "break",
        "continue", "throw", "raise", "await", "async", "with", "when",
    }
    DECL_WORDS = {
        "def", "function", "func", "fn", "class", "struct", "interface",
        "enum", "trait", "impl", "module", "namespace", "let", "var",
        "const", "type", "typedef", "record", "proc", "sub",
    }

    ASSIGN_SYMBOLS = {"=", ":=", "<-", "≔", "←", "⟵"}
    FLOW_SYMBOLS = {"->", "=>", "→", "⟶", "⟹"}
    SAFE_SCALAR_TYPES = (type(None), bool, int, float, str, bytes)

    def __init__(self) -> None:
        self.parsers: dict[str, Parser] = {
            "python": self._parse_python,
            "json": self._parse_json,
            "jsonl": self._parse_jsonl,
            "xml": self._parse_xml,
            "ai-native": self._parse_ai_native,
        }
        # Trusted host-side primitives used only for semantic hypothesis testing.
        # Unknown input code is never eval/exec'd and can never register functions.
        self.semantic_primitives: dict[str, dict[str, Any]] = {}
        self._install_builtin_semantic_primitives()
        # Adaptive reasoning policy.  Curriculum may change these bounded
        # search parameters, but only after blind-suite improvement.  This is
        # runtime strategy adaptation; it never executes or rewrites unknown
        # source code.
        # v14 boots from the causally admitted v13 strategy instead of
        # relearning the same depth/evidence frontier on every fresh instance.
        # Iterative deepening still starts shallow, so simple tasks remain cheap.
        self.reasoning_policy: dict[str, Any] = {
            "max_depth": 3,
            "max_candidates": 12,
            "max_generated": 12000,
            "evidence_rows": 12,
            "counterexample_rounds": 4,
            "accepted_rounds": 3,
        }
        self.curriculum_history: list[dict[str, Any]] = []
        self.causal_evolution_history: list[dict[str, Any]] = []
        self.metacognitive_history: list[dict[str, Any]] = []
        # v15: safely admitted runtime capabilities.  These are compiled only
        # from UCR's bounded primitive-blueprint grammar; unknown source code can
        # never become executable Python through this mechanism.
        self.evolved_primitive_registry: dict[str, dict[str, Any]] = {}
        self.self_development_history: list[dict[str, Any]] = []
        # v16: the *active* primitive-generation grammar can itself grow, but
        # only by admitting named rules from a closed host-defined meta-catalog.
        # Grammar evolution changes which safe blueprints may be synthesized; it
        # never compiles arbitrary source text or rewrites this Python module.
        self.primitive_grammar_registry: dict[str, dict[str, Any]] = {
            "atomic.v1": {
                "rule_id": "atomic.v1",
                "admitted": True,
                "origin": "builtin",
                "description": "bounded atomic safe-blueprint families",
            }
        }
        self.grammar_evolution_history: list[dict[str, Any]] = []

    # ---------------------------- public API ----------------------------

    def register_parser(self, language: str, parser: Parser) -> None:
        """Register/replace a text parser. The parser must not execute input."""
        self.parsers[language.lower()] = parser

    def register_semantic_primitive(
        self,
        label: str,
        function: Callable[..., Any],
        *,
        arity: int = 2,
        category: str = "custom",
        commutative: bool = False,
        provenance: dict[str, Any] | None = None,
    ) -> None:
        """
        Register a trusted host-side semantic hypothesis.

        Important: ``function`` is supplied by the host/developer, never loaded
        from the code being analyzed. Unknown input remains read-only and is
        never eval/exec'd by UCR.
        """
        if not label or not isinstance(label, str):
            raise ValueError("semantic primitive label must be a non-empty string")
        if not callable(function):
            raise TypeError("semantic primitive must be callable")
        if not isinstance(arity, int) or arity < 1 or arity > 8:
            raise ValueError("semantic primitive arity must be in 1..8")
        self.semantic_primitives[label] = {
            "function": function,
            "arity": arity,
            "category": category,
            "commutative": bool(commutative),
            "provenance": copy.deepcopy(provenance or {"origin": "host-or-builtin"}),
        }

    def infer_semantics(
        self,
        observations: Iterable[dict[str, Any]],
        *,
        program: bytes | bytearray | memoryview | str | None = None,
        max_candidates: int = 8,
        max_evidence: int = 32,
    ) -> SemanticModel:
        """
        Infer candidate meanings for unknown symbols from observed I/O behavior.

        Expected observation form::

            {
                "code": "r ≔ a ⊗ b",      # optional when ``program`` is given
                "inputs": {"a": 2, "b": 3},
                "output": 6               # or "outputs": {"r": 6}
            }

        UCR never executes ``code``.  It extracts small observable expression
        forms and tests only trusted, host-side primitives against the supplied
        input/output examples.  The result is therefore hypothesis induction,
        not arbitrary-program execution or a proof of semantics.
        """
        obs_list = list(observations)
        unresolved: list[dict[str, Any]] = []
        trials: dict[tuple[str, str, int], list[dict[str, Any]]] = defaultdict(list)

        default_code: str | None = None
        if program is not None:
            raw_program = program.encode("utf-8") if isinstance(program, str) else bytes(program)
            default_code, _, is_binary = self._decode_lossless(raw_program)
            if is_binary:
                default_code = None
                unresolved.append({
                    "reason": "binary-program-needs-external-trace",
                    "detail": "semantic induction currently requires textual expression evidence",
                })

        for obs_index, obs in enumerate(obs_list):
            if not isinstance(obs, dict):
                unresolved.append({"observation": obs_index, "reason": "observation-not-a-mapping"})
                continue

            code_value = obs.get("code", default_code)
            if code_value is None:
                unresolved.append({"observation": obs_index, "reason": "missing-code"})
                continue
            if isinstance(code_value, str):
                code = code_value
            elif isinstance(code_value, (bytes, bytearray, memoryview)):
                code, _, binary_code = self._decode_lossless(bytes(code_value))
                if binary_code:
                    unresolved.append({"observation": obs_index, "reason": "binary-code-observation"})
                    continue
            else:
                unresolved.append({"observation": obs_index, "reason": "unsupported-code-type"})
                continue

            inputs = obs.get("inputs", {})
            if not isinstance(inputs, dict):
                unresolved.append({"observation": obs_index, "reason": "inputs-not-a-mapping"})
                continue
            if not all(isinstance(k, str) and self._is_safe_semantic_value(v) for k, v in inputs.items()):
                unresolved.append({"observation": obs_index, "reason": "unsafe-or-unsupported-input-value"})
                continue

            forms = self._extract_semantic_forms(code, inputs=inputs)
            if not forms:
                unresolved.append({"observation": obs_index, "reason": "no-simple-observable-form"})
                continue

            accepted = 0
            for form in forms:
                expected_found, expected = self._expected_for_semantic_form(obs, form, len(forms))
                if not expected_found or not self._is_safe_semantic_value(expected):
                    continue

                args: list[Any] = []
                resolvable = True
                for operand in form["operands"]:
                    ok, value = self._resolve_semantic_operand(operand, inputs)
                    if not ok:
                        resolvable = False
                        break
                    args.append(value)
                if not resolvable:
                    continue

                key = (str(form["symbol"]), str(form["form"]), len(args))
                trials[key].append({
                    "args": tuple(args),
                    "expected": expected,
                    "target": form.get("target"),
                    "line": form.get("line"),
                    "operand_names": tuple(form.get("operand_names", [])),
                    "observation": obs_index,
                })
                accepted += 1

            if accepted == 0:
                unresolved.append({
                    "observation": obs_index,
                    "reason": "forms-found-but-no-resolvable-io-pair",
                    "form_count": len(forms),
                })

        symbols: dict[str, SymbolSemantics] = {}
        for (symbol, form_name, arity), symbol_trials in sorted(trials.items()):
            ranked: list[SemanticCandidate] = []
            for label, spec in sorted(self.semantic_primitives.items()):
                if spec["arity"] != arity:
                    continue
                matched = 0
                applicable = 0
                failures = 0
                for trial in symbol_trials:
                    ok, predicted = self._apply_semantic_primitive(spec["function"], trial["args"])
                    if not ok:
                        failures += 1
                        continue
                    applicable += 1
                    if self._semantic_equal(predicted, trial["expected"]):
                        matched += 1
                total = len(symbol_trials)
                score = matched / max(1, total)
                digest = self._primitive_behavioral_digest(spec["function"], arity)
                ranked.append(SemanticCandidate(
                    semantic_id=f"sem:{digest[:20]}",
                    label=label,
                    score=round(score, 6),
                    matched=matched,
                    total=total,
                    behavioral_digest=digest,
                    meta={
                        "applicable": applicable,
                        "failures": failures,
                        "category": spec["category"],
                        "commutative": spec["commutative"],
                    },
                ))

            ranked.sort(key=lambda c: (c.score, c.matched, -c.meta.get("failures", 0), c.label), reverse=True)
            ranked = ranked[:max(1, max_candidates)]
            best = ranked[0].score if ranked else 0.0
            near_best = [c for c in ranked if best > 0 and abs(c.score - best) <= 1e-12]
            evidence_factor = min(1.0, 0.45 + 0.2 * len(symbol_trials))
            ambiguity_factor = 1.0 if len(near_best) == 1 else (1.0 / max(2, len(near_best)))
            confidence = round(best * evidence_factor * ambiguity_factor, 6)

            if best <= 0:
                status = "unresolved"
            elif len(near_best) > 1:
                status = "ambiguous"
            elif best == 1.0 and len(symbol_trials) >= 3:
                status = "strong-hypothesis"
            elif best >= 0.8:
                status = "supported-hypothesis"
            else:
                status = "weak-hypothesis"

            operand_names: tuple[str, ...] = ()
            for trial in symbol_trials:
                names = trial.get("operand_names") or ()
                if len(names) == arity:
                    operand_names = tuple(str(x) for x in names)
                    break
            probes = self._suggest_discriminating_probes(
                ranked,
                arity=arity,
                operand_names=operand_names,
                max_probes=5,
            )

            evidence = [
                {
                    "observation": t["observation"],
                    "line": t["line"],
                    "target": t["target"],
                    "args": [self._canonical_semantic_value(x) for x in t["args"]],
                    "expected": self._canonical_semantic_value(t["expected"]),
                }
                for t in symbol_trials[:max_evidence]
            ]
            key_name = symbol
            if key_name in symbols:
                key_name = f"{form_name}:{symbol}"
            symbols[key_name] = SymbolSemantics(
                symbol=symbol,
                form=form_name,
                arity=arity,
                observations=len(symbol_trials),
                confidence=confidence,
                status=status,
                candidates=ranked,
                suggested_probes=probes,
                evidence=evidence,
            )

        return SemanticModel(
            observation_count=len(obs_list),
            symbols=symbols,
            unresolved=unresolved,
            metadata={
                "reader_version": self.VERSION,
                "safe_mode": "read-only/no-execution",
                "method": "behavioral-hypothesis-induction",
                "semantic_status": "hypotheses-from-observed-io-not-proof",
                "trusted_primitive_count": len(self.semantic_primitives),
            },
        )

    def infer_compositional_reasoning(
        self,
        observations: Iterable[dict[str, Any]],
        *,
        program: bytes | bytearray | memoryview | str | None = None,
        max_depth: int = 2,
        max_candidates: int = 12,
        max_generated: int = 12000,
    ) -> CognitiveReasoningModel:
        """
        Infer small *compositions* of trusted semantic primitives from observed I/O.

        This is a bounded program-induction layer.  Unknown source code is never
        executed.  Candidate explanations are expression trees made only from
        input arguments and host-registered trusted primitives.  Evidence is
        split deterministically into train/holdout partitions when enough
        observations exist, so a perfect training fit is not confused with
        demonstrated generalization.

        Example: observations for ``R(a,b,c)`` may support the hypothesis
        ``numeric.add(numeric.multiply(a,b), c)`` even though no ternary
        primitive was pre-registered.
        """
        obs_list = list(observations)
        unresolved: list[dict[str, Any]] = []
        trials: dict[tuple[str, str, int], list[dict[str, Any]]] = defaultdict(list)

        default_code: str | None = None
        if program is not None:
            raw_program = program.encode("utf-8") if isinstance(program, str) else bytes(program)
            default_code, _, is_binary = self._decode_lossless(raw_program)
            if is_binary:
                default_code = None
                unresolved.append({"reason": "binary-program-needs-external-trace"})

        for obs_index, obs in enumerate(obs_list):
            if not isinstance(obs, dict):
                unresolved.append({"observation": obs_index, "reason": "observation-not-a-mapping"})
                continue
            code_value = obs.get("code", default_code)
            if code_value is None:
                unresolved.append({"observation": obs_index, "reason": "missing-code"})
                continue
            if isinstance(code_value, str):
                code_text = code_value
            elif isinstance(code_value, (bytes, bytearray, memoryview)):
                code_text, _, binary_code = self._decode_lossless(bytes(code_value))
                if binary_code:
                    unresolved.append({"observation": obs_index, "reason": "binary-code-observation"})
                    continue
            else:
                unresolved.append({"observation": obs_index, "reason": "unsupported-code-type"})
                continue

            inputs = obs.get("inputs")
            if not isinstance(inputs, dict) or not all(
                isinstance(k, str) and self._is_safe_semantic_value(v) for k, v in inputs.items()
            ):
                unresolved.append({"observation": obs_index, "reason": "unsafe-or-missing-inputs"})
                continue

            forms = self._extract_semantic_forms(code_text, inputs=inputs)
            if not forms:
                unresolved.append({"observation": obs_index, "reason": "no-simple-semantic-form"})
                continue
            for form in forms:
                expected_found, expected = self._expected_for_semantic_form(obs, form, len(forms))
                if not expected_found or not self._is_safe_semantic_value(expected):
                    continue
                values: list[Any] = []
                ok = True
                for operand in form.get("operands", []):
                    resolved, value = self._resolve_semantic_operand(operand, inputs)
                    if not resolved or not self._is_safe_semantic_value(value):
                        ok = False
                        break
                    values.append(value)
                if not ok or not values:
                    continue
                key = (str(form.get("symbol")), str(form.get("form")), len(values))
                trials[key].append({
                    "observation": obs_index,
                    "args": tuple(values),
                    "expected": expected,
                    "operand_names": tuple(str(x) for x in form.get("operand_names", [])),
                    "line": form.get("line"),
                })

        symbols: dict[str, ReasoningSymbol] = {}
        for (symbol, form_name, arity), symbol_trials in sorted(trials.items()):
            if not 1 <= arity <= 4:
                unresolved.append({"symbol": symbol, "reason": "compositional-arity-out-of-range", "arity": arity})
                continue

            holdout_idx: set[int] = set()
            if len(symbol_trials) >= 4:
                holdout_idx = {i for i in range(len(symbol_trials)) if i % 4 == 3}
                if not holdout_idx:
                    holdout_idx = {len(symbol_trials) - 1}
            train_trials = [t for i, t in enumerate(symbol_trials) if i not in holdout_idx]
            holdout_trials = [t for i, t in enumerate(symbol_trials) if i in holdout_idx]
            if not train_trials:
                train_trials, holdout_trials = symbol_trials, []

            expressions = self._synthesize_reasoning_trees(
                arity=arity,
                train_trials=train_trials,
                max_depth=max(1, min(int(max_depth), 3)),
                max_generated=max(256, int(max_generated)),
            )
            ranked: list[ReasoningCandidate] = []
            for tree in expressions:
                train_matched, train_total, _ = self._score_reasoning_tree(tree, train_trials)
                train_score = train_matched / max(1, train_total)
                if train_score <= 0:
                    continue
                hold_matched, hold_total, _ = self._score_reasoning_tree(tree, holdout_trials)
                hold_score = (hold_matched / hold_total) if hold_total else None
                combined = (
                    0.65 * train_score + 0.35 * float(hold_score)
                    if hold_score is not None else 0.85 * train_score
                )
                complexity, depth = self._reasoning_tree_complexity(tree)
                expression = self._reasoning_tree_text(tree, symbol_trials[0].get("operand_names") or ())
                digest = self._reasoning_behavioral_digest(tree, symbol_trials)
                ranked.append(ReasoningCandidate(
                    expression=expression,
                    train_score=round(train_score, 6),
                    holdout_score=None if hold_score is None else round(hold_score, 6),
                    combined_score=round(combined, 6),
                    complexity=complexity,
                    depth=depth,
                    matched_train=train_matched,
                    train_total=train_total,
                    matched_holdout=hold_matched,
                    holdout_total=hold_total,
                    behavioral_digest=digest,
                    tree=tree,
                ))

            ranked.sort(
                key=lambda c: (
                    c.combined_score,
                    c.holdout_score if c.holdout_score is not None else -1.0,
                    c.train_score,
                    -c.complexity,
                    c.expression,
                ),
                reverse=True,
            )
            # Remove exact textual duplicates while preserving semantically
            # distinct alternatives that fit the same current observations.
            seen_expr: set[str] = set()
            unique_ranked: list[ReasoningCandidate] = []
            for candidate in ranked:
                if candidate.expression in seen_expr:
                    continue
                seen_expr.add(candidate.expression)
                unique_ranked.append(candidate)
                if len(unique_ranked) >= max(1, max_candidates):
                    break
            ranked = unique_ranked

            best = ranked[0] if ranked else None
            ambiguity = False
            ambiguity_probes: list[dict[str, Any]] = []
            if best and len(ranked) > 1:
                second = ranked[1]
                # Minimum-description-length preference: a strictly more complex
                # explanation is not treated as equally plausible merely because
                # it interpolates the current samples.  Equal/shorter rivals are
                # considered genuinely ambiguous only when a bounded active probe
                # can make them predict different outputs.  Algebraically
                # equivalent forms such as a<b and b>a therefore do not create a
                # permanent false ambiguity.
                rival_close = (
                    abs(best.combined_score - second.combined_score) <= 0.01
                    and second.complexity <= best.complexity
                )
                if rival_close:
                    probe_names = symbol_trials[0].get("operand_names") or tuple(f"arg{i}" for i in range(arity))
                    ambiguity_probes = self._suggest_compositional_probes(
                        ranked, arity=arity, operand_names=tuple(probe_names)
                    )
                    ambiguity = bool(ambiguity_probes)
            evidence_factor = min(1.0, 0.45 + 0.09 * len(symbol_trials))
            uniqueness_factor = 0.6 if ambiguity else 1.0
            generalization = (
                best.holdout_score if best and best.holdout_score is not None
                else (best.train_score * 0.75 if best else 0.0)
            )
            confidence = round(float(generalization or 0.0) * evidence_factor * uniqueness_factor, 6)

            if best is None:
                status = "unresolved"
            elif ambiguity:
                status = "ambiguous"
            elif best.train_score == 1.0 and best.holdout_score == 1.0 and len(holdout_trials) >= 1:
                status = "holdout-supported"
            elif best.train_score == 1.0 and best.holdout_score is None:
                status = "training-fit-only"
            elif best.combined_score >= 0.85:
                status = "supported-hypothesis"
            else:
                status = "weak-hypothesis"

            names = symbol_trials[0].get("operand_names") or tuple(f"arg{i}" for i in range(arity))
            probes = ambiguity_probes or self._suggest_compositional_probes(
                ranked, arity=arity, operand_names=tuple(names)
            )
            key_name = symbol if symbol not in symbols else f"{form_name}:{symbol}"
            symbols[key_name] = ReasoningSymbol(
                symbol=symbol,
                form=form_name,
                arity=arity,
                observations=len(symbol_trials),
                status=status,
                confidence=confidence,
                candidates=ranked,
                suggested_probes=probes,
                diagnostics={
                    "train_observations": len(train_trials),
                    "holdout_observations": len(holdout_trials),
                    "generated_expression_count": len(expressions),
                    "ambiguity": ambiguity,
                    "best_depth": best.depth if best else None,
                    "best_complexity": best.complexity if best else None,
                    "generalization_score": round(float(generalization or 0.0), 6),
                },
            )

        profile = self._reasoning_profile(symbols)
        return CognitiveReasoningModel(
            observation_count=len(obs_list),
            symbols=symbols,
            profile=profile,
            unresolved=unresolved,
            metadata={
                "reader_version": self.VERSION,
                "safe_mode": "read-only/no-unknown-code-execution",
                "method": "bounded-compositional-program-induction-with-holdout",
                "max_depth": max(1, min(int(max_depth), 3)),
                "intelligence_claim": "none; profile measures only this bounded reasoning procedure",
            },
        )

    def cognitive_cycle(
        self,
        observations: Iterable[dict[str, Any]],
        *,
        program: bytes | bytearray | memoryview | str | None = None,
        max_depth: int = 2,
    ) -> dict[str, Any]:
        """Run direct + compositional induction and expose deficits and next goals."""
        obs_list = list(observations)
        direct = self.infer_semantics(obs_list, program=program)
        composed = self.infer_compositional_reasoning(obs_list, program=program, max_depth=max_depth)
        deficits: list[dict[str, Any]] = []
        next_goals: list[dict[str, Any]] = []
        for key, symbol in composed.symbols.items():
            if symbol.status in {"unresolved", "weak-hypothesis", "ambiguous", "training-fit-only"}:
                deficits.append({
                    "symbol": symbol.symbol,
                    "status": symbol.status,
                    "confidence": symbol.confidence,
                    "reason": "insufficient-generalization-or-ambiguity",
                })
            if symbol.suggested_probes:
                next_goals.append({
                    "type": "discriminating-experiment",
                    "symbol": symbol.symbol,
                    "probe": symbol.suggested_probes[0],
                    "purpose": "separate currently plausible semantic explanations",
                })
            elif symbol.status == "holdout-supported":
                next_goals.append({
                    "type": "harder-transfer-test",
                    "symbol": symbol.symbol,
                    "purpose": "test the learned composition outside the current value distribution",
                })
        return {
            "schema": "ucr.cognitive-cycle/1",
            "reader_version": self.VERSION,
            "direct_semantics": direct.to_dict(),
            "compositional_reasoning": composed.to_dict(),
            "deficits": deficits,
            "next_goals": next_goals,
            "profile": composed.profile,
            "safety": {
                "unknown_code_executed": False,
                "candidate_language": "trusted host primitives only",
            },
        }

    def benchmark_reasoning(self) -> dict[str, Any]:
        """
        Run a deterministic internal blind-holdout benchmark of the bounded
        reasoning layer.  This measures the implementation's ability to induce
        small trusted-primitive compositions; it is explicitly not an IQ or a
        claim of general intelligence.
        """
        tasks: list[dict[str, Any]] = [
            {
                "name": "direct_addition",
                "code": "r = ΩA(a,b)",
                "rows": [(-4, 7), (2, 3), (4, 5), (7, 2), (3, 6), (5, -2), (8, -1), (0, 9)],
                "function": lambda a, b: a + b,
                "expected_max_depth": 1,
            },
            {
                "name": "multiply_then_add",
                "code": "r = ΩB(a,b,c)",
                "rows": [(-2, 3, 4), (2, 3, 4), (4, 5, 2), (7, 2, 1), (3, 6, 5), (5, 4, -2), (8, -1, 3), (0, 9, 7)],
                "function": lambda a, b, c: a * b + c,
                "expected_max_depth": 2,
            },
            {
                "name": "add_then_multiply",
                "code": "r = ΩC(a,b,c)",
                "rows": [(-2, 3, 4), (2, 3, 4), (4, 5, 2), (7, 2, 1), (3, 6, 5), (5, 4, -2), (8, -1, 3), (0, 9, 7)],
                "function": lambda a, b, c: (a + b) * c,
                "expected_max_depth": 2,
            },
            {
                "name": "relational_chain",
                "code": "r = ΩD(a,b,c)",
                "rows": [
                    (1, 2, 3), (3, 2, 1), (1, 5, 3), (3, 1, 5),
                    (0, 1, 5), (5, 7, 9), (9, 7, 8), (-2, 0, 2),
                    (2, 4, 3), (3, 4, 8), (7, 8, 6), (1, 4, 10),
                ],
                "function": lambda a, b, c: (a < b) and (b < c),
                "expected_max_depth": 2,
            },
        ]
        observations: list[dict[str, Any]] = []
        symbol_by_task: dict[str, str] = {}
        for task in tasks:
            forms = self._extract_semantic_forms(task["code"], inputs={"a": 0, "b": 0, "c": 0})
            symbol = str(forms[0]["symbol"]) if forms else task["name"]
            symbol_by_task[task["name"]] = symbol
            for row in task["rows"]:
                inputs = {chr(ord("a") + i): value for i, value in enumerate(row)}
                observations.append({
                    "code": task["code"],
                    "inputs": inputs,
                    "output": task["function"](*row),
                })

        model = self.infer_compositional_reasoning(
            observations,
            max_depth=2,
            max_candidates=12,
            max_generated=12000,
        )
        results: list[dict[str, Any]] = []
        passed = 0
        for task in tasks:
            symbol = symbol_by_task[task["name"]]
            item = model.symbols.get(symbol)
            best = item.candidates[0] if item and item.candidates else None
            task_pass = bool(
                best
                and best.train_score == 1.0
                and best.holdout_score == 1.0
                and best.depth <= task["expected_max_depth"]
            )
            passed += int(task_pass)
            results.append({
                "task": task["name"],
                "pass": task_pass,
                "status": item.status if item else "missing",
                "confidence": item.confidence if item else 0.0,
                "recovered_expression": best.expression if best else None,
                "train_score": best.train_score if best else 0.0,
                "holdout_score": best.holdout_score if best else None,
                "depth": best.depth if best else None,
            })

        return {
            "schema": "ucr.reasoning-benchmark/1",
            "reader_version": self.VERSION,
            "task_count": len(tasks),
            "passed": passed,
            "pass_rate": round(passed / max(1, len(tasks)), 6),
            "results": results,
            "profile": model.profile,
            "interpretation": {
                "measures": "bounded compositional induction, holdout generalization, ambiguity handling",
                "does_not_measure": "general intelligence, consciousness, human IQ, unrestricted reasoning",
            },
        }

    def _infer_reasoning_with_policy(
        self,
        observations: Iterable[dict[str, Any]],
        *,
        policy: dict[str, Any],
        program: bytes | bytearray | memoryview | str | None = None,
    ) -> CognitiveReasoningModel:
        """
        Iterative-deepening induction under one accepted policy.

        Start with the shallowest hypothesis space and deepen only while at
        least one recovered symbol still lacks holdout support or remains
        observationally ambiguous.  This avoids spending depth-3 search on a
        relation already established at depth 1 or 2.
        """
        obs_list = list(observations)
        max_depth = max(1, min(int(policy.get("max_depth", 1)), 3))
        attempts: list[dict[str, Any]] = []
        model: CognitiveReasoningModel | None = None
        for depth in range(1, max_depth + 1):
            model = self.infer_compositional_reasoning(
                obs_list,
                program=program,
                max_depth=depth,
                max_candidates=int(policy.get("max_candidates", 12)),
                max_generated=int(policy.get("max_generated", 6000)),
            )
            unresolved_symbols = [
                key for key, item in model.symbols.items()
                if item.status != "holdout-supported" or bool(item.diagnostics.get("ambiguity"))
            ]
            attempts.append({
                "depth": depth,
                "symbol_count": len(model.symbols),
                "unresolved_symbols": unresolved_symbols,
            })
            if model.symbols and not unresolved_symbols:
                break
        if model is None:
            model = self.infer_compositional_reasoning(
                obs_list, program=program, max_depth=1,
                max_candidates=int(policy.get("max_candidates", 12)),
                max_generated=int(policy.get("max_generated", 6000)),
            )
        model.metadata["iterative_deepening"] = attempts
        model.metadata["policy"] = dict(policy)
        return model

    def infer_adaptive_reasoning(
        self,
        observations: Iterable[dict[str, Any]],
        *,
        program: bytes | bytearray | memoryview | str | None = None,
    ) -> CognitiveReasoningModel:
        """Run iterative compositional induction with the accepted curriculum policy."""
        return self._infer_reasoning_with_policy(
            observations, program=program, policy=dict(self.reasoning_policy)
        )

    def reasoning_curriculum_state(self) -> dict[str, Any]:
        """Return the accepted adaptive policy and its audit history."""
        return {
            "schema": "ucr.reasoning-curriculum-state/1",
            "reader_version": self.VERSION,
            "policy": dict(self.reasoning_policy),
            "history": copy.deepcopy(self.curriculum_history),
            "causal_evolution_history": copy.deepcopy(self.causal_evolution_history),
            "metacognitive_history": copy.deepcopy(self.metacognitive_history),
            "safety": {
                "unknown_code_executed": False,
                "self_source_rewritten": False,
                "adaptation_scope": "bounded-search-strategy-only",
            },
        }

    def run_reasoning_curriculum(self, *, rounds: int = 4) -> dict[str, Any]:
        """
        Adapt the bounded reasoning search policy using synthetic blind tasks.

        Each round evaluates the current policy, selects the weakest task family,
        proposes one conservative strategy mutation, and accepts it only when a
        fresh blind suite improves without regressing previously solved tasks.
        The target expressions are used only by the benchmark oracle to generate
        and score I/O; they are never supplied to the induction procedure.
        """
        rounds = max(1, min(int(rounds), 8))
        specs = self._curriculum_task_specs()
        baseline = self._evaluate_curriculum_suite(specs, policy=self.reasoning_policy, variant=0)
        start_score = float(baseline["aggregate_score"])
        accepted = 0
        round_reports: list[dict[str, Any]] = []
        skip_once: str | None = None

        for round_index in range(rounds):
            validation_variant = 1000 + round_index * 101
            current = self._evaluate_curriculum_suite(
                specs, policy=self.reasoning_policy, variant=validation_variant
            )
            # Stop once every canonical family passes the fresh blind suite.
            # Continuing to mutate an already perfect bounded benchmark only
            # burns search budget and risks overfitting without adding evidence.
            if (
                int(current.get("passed", 0)) == int(current.get("task_count", 0))
                and float(current.get("aggregate_score", 0.0)) >= 0.999999
            ):
                round_reports.append({
                    "round": round_index + 1,
                    "status": "converged-early-stop",
                    "score_before": current["aggregate_score"],
                    "policy": dict(self.reasoning_policy),
                    "accepted": False,
                })
                break
            eligible = [item for item in current["tasks"] if item["task"] != skip_once]
            if not eligible:
                eligible = list(current["tasks"])
            weakest = min(
                eligible,
                key=lambda x: (bool(x["pass"]), float(x["score"]), float(x.get("oracle_score", 0.0)), float(x["holdout_score"]), x["task"]),
            )
            skip_once = None
            proposal = dict(self.reasoning_policy)
            reason = "increase-evidence"

            # Detect a saturated reasoning frontier from observable diagnostics,
            # not from the hidden target tree.  If the best explanation still
            # fails and reaches the current depth bound, search one level deeper.
            if (
                float(weakest["score"]) < 0.999999
                and int(weakest.get("best_depth") or 0) >= int(proposal.get("max_depth", 1))
                and int(proposal.get("max_depth", 1)) < 3
            ):
                proposal["max_depth"] = int(proposal.get("max_depth", 1)) + 1
                proposal["max_generated"] = min(24000, max(int(proposal.get("max_generated", 6000)), 9000))
                # Deeper compositions create more observationally equivalent
                # rivals.  When entering depth 3, require a broader evidence
                # set at the same time so the extra expressivity does not trade
                # away identifiability.
                if int(proposal["max_depth"]) >= 3:
                    proposal["evidence_rows"] = max(12, int(proposal.get("evidence_rows", 8)))
                reason = "depth-frontier-saturated"
            elif bool(weakest.get("ambiguous")):
                proposal["evidence_rows"] = min(20, int(proposal.get("evidence_rows", 8)) + 4)
                proposal["max_candidates"] = min(24, int(proposal.get("max_candidates", 12)) + 4)
                proposal["counterexample_rounds"] = min(3, int(proposal.get("counterexample_rounds", 0)) + 1)
                reason = "ambiguity-needs-discriminating-evidence"
            elif float(weakest.get("oracle_score", 1.0)) < 1.0:
                proposal["counterexample_rounds"] = min(3, int(proposal.get("counterexample_rounds", 0)) + 1)
                if int(weakest.get("generated_expression_count") or 0) >= int(proposal.get("max_generated", 6000)) * 0.9:
                    proposal["max_generated"] = min(24000, int(proposal.get("max_generated", 6000)) + 3000)
                reason = "oracle-counterexample-required"
            elif int(weakest.get("generated_expression_count") or 0) >= int(proposal.get("max_generated", 6000)) * 0.9:
                proposal["max_generated"] = min(24000, int(proposal.get("max_generated", 6000)) + 4000)
                reason = "search-budget-saturated"
            else:
                proposal["evidence_rows"] = min(20, int(proposal.get("evidence_rows", 8)) + 2)
                if float(weakest["holdout_score"]) < 1.0:
                    proposal["max_generated"] = min(24000, int(proposal.get("max_generated", 6000)) + 2000)
                reason = "more-blind-evidence"

            before_policy = dict(self.reasoning_policy)
            candidate = self._evaluate_curriculum_suite(
                specs, policy=proposal, variant=validation_variant
            )
            previous_solved = {
                item["task"] for item in current["tasks"] if bool(item["pass"])
            }
            candidate_by_name = {item["task"]: item for item in candidate["tasks"]}
            regressions = sorted(
                name for name in previous_solved
                if not bool(candidate_by_name.get(name, {}).get("pass"))
            )
            improved = float(candidate["aggregate_score"]) > float(current["aggregate_score"]) + 1e-9
            no_regression = not regressions
            accept = bool(improved and no_regression)
            if accept:
                proposal["accepted_rounds"] = int(before_policy.get("accepted_rounds", 0)) + 1
                self.reasoning_policy = proposal
                accepted += 1
            else:
                # Avoid repeatedly spending every round on a mutation that just
                # failed to improve the same deficit.  The next round explores
                # the next weakest unsolved family, then the skipped task becomes
                # eligible again.
                skip_once = str(weakest["task"])

            report = {
                "round": round_index + 1,
                "weakest_task": weakest["task"],
                "weakest_family": weakest["family"],
                "weakest_score": weakest["score"],
                "diagnosed_deficit": reason,
                "policy_before": before_policy,
                "policy_proposed": proposal,
                "score_before": current["aggregate_score"],
                "score_candidate": candidate["aggregate_score"],
                "regressions": regressions,
                "accepted": accept,
            }
            self.curriculum_history.append(copy.deepcopy(report))
            round_reports.append(report)

        # Re-score the exact baseline audit distribution after adaptation so
        # the reported improvement is apples-to-apples.  Per-round acceptance
        # used separate validation variants above.
        final = self._evaluate_curriculum_suite(
            specs, policy=self.reasoning_policy, variant=0
        )
        return {
            "schema": "ucr.reasoning-curriculum/1",
            "reader_version": self.VERSION,
            "rounds_requested": rounds,
            "rounds_accepted": accepted,
            "start_score": round(start_score, 6),
            "final_score": final["aggregate_score"],
            "improvement": round(float(final["aggregate_score"]) - start_score, 6),
            "initial_suite": baseline,
            "rounds": round_reports,
            "final_suite": final,
            "final_policy": dict(self.reasoning_policy),
            "interpretation": {
                "learned": "bounded search strategy for compositional induction",
                "not_claimed": "general intelligence, consciousness, autonomous source-code self-rewrite",
                "blind_rule": "target expressions generate/score I/O but are never provided to the induction search",
            },
        }

    @staticmethod
    def _reasoning_tree_depth(tree: Any) -> int:
        """Return the operator depth of a bounded reasoning tree."""
        if not isinstance(tree, tuple) or not tree:
            return 0
        if tree[0] == "arg":
            return 0
        if tree[0] != "op" or len(tree) < 3:
            return 0
        children = tree[2] if isinstance(tree[2], tuple) else ()
        return 1 + max((UniversalCodeReader._reasoning_tree_depth(c) for c in children), default=0)

    @staticmethod
    def _reasoning_tree_digest(tree: Any) -> str:
        return hashlib.sha256(repr(tree).encode("utf-8")).hexdigest()[:16]

    def _generate_self_challenge_specs(
        self,
        *,
        weak_families: Iterable[str] | None = None,
        count: int = 6,
        seed: int = 13001,
    ) -> list[dict[str, Any]]:
        """
        Generate bounded *novel* reasoning challenges from the trusted primitive
        grammar.  The generator is deterministic but does not use fixed target
        expressions from the canonical curriculum.  Target trees are retained
        only by the scoring oracle; induction receives I/O examples, never the
        tree itself.

        This is task generation inside a deliberately small safe grammar, not
        unrestricted autonomous goal creation.
        """
        count = max(3, min(int(count), 12))
        weak = sorted(str(x) for x in (weak_families or []))
        seed_material = f"{int(seed)}|{'|'.join(weak)}|{self.VERSION}".encode("utf-8")
        state = int.from_bytes(hashlib.sha256(seed_material).digest()[:8], "big") or 1

        # Prefer compositions that remain identifiable on modest evidence.
        # Min/max/absolute-difference are valid primitives, but in synthetic
        # curricula they often collapse to a projection on a small sample and
        # create an artificial ambiguity unrelated to reasoning depth.
        numeric_inner = [
            "numeric.add", "numeric.subtract", "numeric.multiply",
        ]
        numeric_outer = [
            "numeric.add", "numeric.subtract",
        ]
        unary_outer = ["numeric.absolute", "numeric.negate"]
        relations = ["relation.less", "relation.greater", "relation.less_equal", "relation.greater_equal"]
        boolean_ops = ["boolean.and", "boolean.or"]
        bitwise_ops = ["integer.bit_xor", "integer.bit_or", "integer.bit_and"]

        canonical = {self._reasoning_tree_digest(s["tree"]) for s in self._curriculum_task_specs()}
        specs: list[dict[str, Any]] = []
        seen: set[str] = set(canonical)

        def next_index(n: int) -> int:
            nonlocal state
            state = (6364136223846793005 * state + 1442695040888963407) & ((1 << 64) - 1)
            # Use high bits: the low bits of an LCG have very short cycles
            # (mod 4 they can repeat a single pattern), which previously made
            # the self-challenge generator overproduce one task family.
            return int((state >> 29) % max(1, n))

        attempts = 0
        while len(specs) < count and attempts < count * 50:
            attempts += 1
            kind = next_index(4)
            arity = 3
            family = "self-generated"
            if kind == 0:
                inner = numeric_inner[next_index(len(numeric_inner))]
                outer = numeric_outer[next_index(len(numeric_outer))]
                # Rotate argument placement so structurally similar tasks still
                # require genuinely new binding/generalization.
                order = [0, 1, 2]
                rot = next_index(3)
                order = order[rot:] + order[:rot]
                tree = (
                    "op", outer,
                    (("op", inner, (("arg", order[0]), ("arg", order[1]))), ("arg", order[2])),
                )
                family = "self-depth2-arithmetic"
            elif kind == 1:
                inner = numeric_inner[next_index(len(numeric_inner))]
                outer = numeric_outer[next_index(len(numeric_outer))]
                unary = unary_outer[next_index(len(unary_outer))]
                tree = (
                    "op", unary,
                    (("op", outer, (("op", inner, (("arg", 0), ("arg", 1))), ("arg", 2))),),
                )
                family = "self-depth3-arithmetic"
            elif kind == 2:
                rel1 = relations[next_index(len(relations))]
                rel2 = relations[next_index(len(relations))]
                bop = boolean_ops[next_index(len(boolean_ops))]
                tree = (
                    "op", bop,
                    (("op", rel1, (("arg", 0), ("arg", 1))),
                     ("op", rel2, (("arg", 1), ("arg", 2)))),
                )
                family = "self-depth2-logic"
            else:
                op1 = bitwise_ops[next_index(len(bitwise_ops))]
                op2 = bitwise_ops[next_index(len(bitwise_ops))]
                tree = (
                    "op", op2,
                    (("op", op1, (("arg", 0), ("arg", 1))), ("arg", 2)),
                )
                family = "self-depth2-bitwise"

            digest = self._reasoning_tree_digest(tree)
            if digest in seen:
                continue
            seen.add(digest)
            specs.append({
                "name": f"self_{digest}",
                "family": family,
                "arity": arity,
                "tree": tree,
                "generated": True,
                "target_depth": self._reasoning_tree_depth(tree),
                "origin": "bounded-grammar-self-challenge",
            })
        return specs

    def _evaluate_suite_variants(
        self,
        specs: list[dict[str, Any]],
        *,
        policy: dict[str, Any],
        variants: Iterable[int],
    ) -> dict[str, Any]:
        """Evaluate one policy on several numerically fresh blind variants."""
        reports = [
            self._evaluate_curriculum_suite(specs, policy=policy, variant=int(v))
            for v in variants
        ]
        aggregates = [float(r["aggregate_score"]) for r in reports]
        pass_rates = [float(r["pass_rate"]) for r in reports]
        return {
            "policy": dict(policy),
            "variants": reports,
            "mean_score": round(statistics.fmean(aggregates), 6) if aggregates else 0.0,
            "min_score": round(min(aggregates), 6) if aggregates else 0.0,
            "mean_pass_rate": round(statistics.fmean(pass_rates), 6) if pass_rates else 0.0,
            "all_pass": bool(reports and all(int(r["passed"]) == int(r["task_count"]) for r in reports)),
        }

    def run_causal_reasoning_evolution(
        self,
        *,
        rounds: int = 4,
        challenge_count: int = 3,
    ) -> dict[str, Any]:
        """
        Run a stronger bounded development cycle with novel self-challenges,
        hidden oracle audit, counterexample-guided refinement, transfer and
        causal ablation.

        Unknown analyzed code is never executed and this routine never rewrites
        this source file. Adaptation is limited to bounded search strategy.
        """
        rounds = max(1, min(int(rounds), 8))
        challenge_count = max(3, min(int(challenge_count), 8))
        starting_policy = dict(self.reasoning_policy)
        canonical_specs = self._curriculum_task_specs()
        diagnostic = self._evaluate_curriculum_suite(
            canonical_specs, policy=starting_policy, variant=13001
        )
        weakest = sorted(
            diagnostic["tasks"],
            key=lambda x: (bool(x["pass"]), float(x["score"]), str(x["task"])),
        )[:3]
        weak_families = [str(x["family"]) for x in weakest]
        generated_specs = self._generate_self_challenge_specs(
            weak_families=weak_families,
            count=challenge_count,
            seed=13001,
        )

        pre_novel = self._evaluate_suite_variants(
            generated_specs, policy=starting_policy, variants=(13111,)
        )

        # Stage 1: canonical curriculum establishes the general depth frontier.
        curriculum = self.run_reasoning_curriculum(rounds=rounds)
        canonical_policy = dict(self.reasoning_policy)
        canonical_novel_blind = self._evaluate_suite_variants(
            generated_specs, policy=canonical_policy, variants=(19121,)
        )

        # Stage 2: generated tasks expose deficits absent from the canonical set.
        self_rounds: list[dict[str, Any]] = []
        for self_round in range(1):
            diagnosis_variant = 17011 + self_round * 211
            current_diag = self._evaluate_curriculum_suite(
                generated_specs, policy=self.reasoning_policy, variant=diagnosis_variant
            )
            weakest_new = min(
                current_diag["tasks"],
                key=lambda x: (
                    bool(x["pass"]), float(x["score"]),
                    float(x.get("oracle_score", 0.0)), str(x["task"]),
                ),
            )
            before = dict(self.reasoning_policy)
            proposal = dict(before)
            reasons: list[str] = []

            if int(weakest_new.get("generated_expression_count") or 0) >= int(proposal.get("max_generated", 6000)) * 0.9:
                proposal["max_generated"] = min(
                    24000, int(proposal.get("max_generated", 6000)) + 3000
                )
                reasons.append("search-budget-saturated")
            if float(weakest_new.get("oracle_score", 1.0)) < 1.0 or bool(weakest_new.get("ambiguous")):
                # Permit a small bounded CEGIS burst once hidden transfer
                # disproves the current explanation.  Three probes are enough
                # to resolve the equality-boundary cases in the generated suite
                # without unbounded interaction.
                proposal["counterexample_rounds"] = min(
                    4, max(4, int(proposal.get("counterexample_rounds", 0)))
                )
                reasons.append("counterexample-guided-discrimination")
            if proposal == before:
                proposal["evidence_rows"] = min(
                    20, int(proposal.get("evidence_rows", 8)) + 2
                )
                reasons.append("increase-independent-evidence")

            validation_variant = 18013 + self_round * 223
            current_validation = self._evaluate_curriculum_suite(
                generated_specs, policy=before, variant=validation_variant
            )
            candidate_validation = self._evaluate_curriculum_suite(
                generated_specs, policy=proposal, variant=validation_variant
            )
            previous_solved = {
                item["task"] for item in current_validation["tasks"] if bool(item["pass"])
            }
            candidate_map = {item["task"]: item for item in candidate_validation["tasks"]}
            regressions = sorted(
                name for name in previous_solved
                if not bool(candidate_map.get(name, {}).get("pass"))
            )
            improved = float(candidate_validation["aggregate_score"]) > float(current_validation["aggregate_score"]) + 1e-9
            accept = bool(improved and not regressions)
            if accept:
                proposal["accepted_rounds"] = int(before.get("accepted_rounds", 0)) + 1
                self.reasoning_policy = proposal
            self_rounds.append({
                "round": self_round + 1,
                "weakest_task": weakest_new["task"],
                "weakest_family": weakest_new["family"],
                "diagnosed_deficits": reasons,
                "policy_before": before,
                "policy_proposed": proposal,
                "score_before": current_validation["aggregate_score"],
                "score_candidate": candidate_validation["aggregate_score"],
                "regressions": regressions,
                "accepted": accept,
            })

        final_policy = dict(self.reasoning_policy)
        post_novel = self._evaluate_suite_variants(
            generated_specs,
            policy=final_policy,
            variants=(21127,),
        )
        core_transfer = self._evaluate_suite_variants(
            canonical_specs,
            policy=final_policy,
            variants=(20101,),
        )

        # Causally isolate only changes introduced by the *new* self-challenge
        # stage.  Depth/evidence changes admitted by the earlier canonical
        # curriculum are not re-attributed here.
        changed = [
            key for key in ("max_candidates", "max_generated", "evidence_rows", "counterexample_rounds")
            if final_policy.get(key) != canonical_policy.get(key)
        ]
        # Targeted causal ablation: test each newly changed mechanism on the
        # novel task where that mechanism was actually exercised.  This avoids
        # re-running the entire expensive CEGIS suite for every parameter while
        # preserving a concrete counterfactual measurement.
        final_tasks = post_novel["variants"][0]["tasks"] if post_novel.get("variants") else []
        spec_by_name = {spec["name"]: spec for spec in generated_specs}
        ablations: list[dict[str, Any]] = []
        for key in changed:
            if not final_tasks:
                break
            if key == "counterexample_rounds":
                chosen = max(
                    final_tasks,
                    key=lambda item: (len(item.get("counterexamples_used") or []), item.get("task", "")),
                )
            elif key == "max_generated":
                chosen = max(
                    final_tasks,
                    key=lambda item: (
                        int(item.get("generated_expression_count") or 0),
                        int(item.get("best_depth") or 0),
                        item.get("task", ""),
                    ),
                )
            else:
                chosen = min(final_tasks, key=lambda item: (float(item.get("score", 0.0)), item.get("task", "")))
            task_name = chosen["task"]
            spec = spec_by_name[task_name]
            task_index = next(i for i, s in enumerate(generated_specs) if s["name"] == task_name)
            task_variant = 21127 + task_index * 17
            ablated = dict(final_policy)
            ablated[key] = canonical_policy.get(key)
            ablated_result = self._evaluate_curriculum_task(
                spec, policy=ablated, variant=task_variant
            )
            reference_score = float(chosen.get("score", 0.0))
            effect = reference_score - float(ablated_result.get("score", 0.0))
            ablations.append({
                "parameter": key,
                "task": task_name,
                "final_value": final_policy.get(key),
                "reverted_value": canonical_policy.get(key),
                "reference_score": round(reference_score, 6),
                "ablated_score": ablated_result.get("score", 0.0),
                "causal_effect": round(effect, 6),
                "positive_effect": bool(effect > 1e-6),
                "ablated_pass": bool(ablated_result.get("pass")),
            })

        positive = [a for a in ablations if a["positive_effect"]]
        novel_gain = float(post_novel["mean_score"]) - float(canonical_novel_blind["mean_score"])
        admitted = bool(
            novel_gain > 1e-6
            and bool(post_novel["all_pass"])
            and bool(core_transfer["all_pass"])
            and bool(positive)
        )
        report = {
            "schema": "ucr.causal-reasoning-evolution/2",
            "reader_version": self.VERSION,
            "starting_policy": starting_policy,
            "diagnostic_suite": diagnostic,
            "weak_families": weak_families,
            "generated_challenges": [
                {
                    "name": s["name"],
                    "family": s["family"],
                    "arity": s["arity"],
                    "target_depth": s.get("target_depth"),
                    "target_digest": self._reasoning_tree_digest(s["tree"]),
                }
                for s in generated_specs
            ],
            "novel_before": pre_novel,
            "curriculum": curriculum,
            "canonical_policy": canonical_policy,
            "canonical_novel_blind": canonical_novel_blind,
            "self_challenge_rounds": self_rounds,
            "novel_after": post_novel,
            "novel_gain": round(novel_gain, 6),
            "core_transfer": core_transfer,
            "ablations": ablations,
            "causally_supported_changes": [a["parameter"] for a in positive],
            "admitted": admitted,
            "final_policy": final_policy,
            "safety": {
                "unknown_code_executed": False,
                "self_source_rewritten": False,
                "adaptation_scope": "bounded-search-strategy-only",
                "generated_tasks_scope": "trusted-primitive-grammar-only",
            },
            "interpretation": {
                "supported": "bounded strategy adaptation with generated blind tasks, CEGIS and parameter ablation",
                "not_claimed": "general intelligence, consciousness, unrestricted autonomous self-modification",
            },
        }
        self.causal_evolution_history.append(copy.deepcopy(report))
        return report

    def diagnose_reasoning_deficit(
        self,
        task_report: dict[str, Any],
        *,
        policy: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """
        Diagnose *why* one bounded induction task failed using only observable
        search/validation diagnostics.

        The hidden target tree is deliberately not consulted.  The diagnosis
        therefore distinguishes evidence shortage, search-budget saturation and
        model-capacity pressure from the same information a real caller sees.
        """
        policy = dict(policy or self.reasoning_policy)
        if bool(task_report.get("pass")):
            return {
                "deficit": "none",
                "confidence": 1.0,
                "evidence": ["task-pass"],
                "recommended_action": "keep-policy",
            }

        train = float(task_report.get("train_score") or 0.0)
        holdout = float(task_report.get("holdout_score") or 0.0)
        oracle = float(task_report.get("oracle_score") or 0.0)
        ambiguous = bool(task_report.get("ambiguous"))
        generated = int(task_report.get("generated_expression_count") or 0)
        max_generated = max(1, int(policy.get("max_generated", 6000)))
        best_depth = int(task_report.get("best_depth") or 0)
        max_depth = max(1, int(policy.get("max_depth", 1)))
        counterexamples = int(policy.get("counterexample_rounds", 0))

        evidence: list[str] = []

        # A perfect fit on visible train/holdout that breaks on the hidden audit
        # is evidence that the current observations do not discriminate rival
        # explanations.  Prefer more informative evidence over more brute force.
        if (train >= 0.999999 and holdout >= 0.999999 and oracle < 0.999999) or ambiguous:
            evidence.extend([
                "visible-fit-near-perfect" if train >= 0.999999 and holdout >= 0.999999 else "candidate-ambiguity",
                f"hidden-oracle={oracle:.6f}",
            ])
            return {
                "deficit": "evidence-gap",
                "confidence": round(min(1.0, 0.72 + max(0.0, 1.0 - oracle) * 0.28), 6),
                "evidence": evidence,
                "recommended_action": "seek-discriminating-counterexamples",
                "counterexample_rounds": counterexamples,
            }

        saturation = generated >= int(0.90 * max_generated)
        if saturation:
            evidence.extend([
                f"generated={generated}",
                f"budget={max_generated}",
                "search-frontier-saturated",
            ])
            return {
                "deficit": "search-budget-gap",
                "confidence": round(min(1.0, 0.75 + 0.25 * min(1.0, generated / max_generated)), 6),
                "evidence": evidence,
                "recommended_action": "increase-search-budget",
            }

        if max_depth < 3 and (best_depth >= max_depth or (best_depth == 0 and generated < int(0.90 * max_generated))):
            evidence.extend([
                f"best-depth={best_depth}",
                f"depth-limit={max_depth}",
                "no-expressive-candidate-at-current-depth" if best_depth == 0 else "best-candidate-reaches-depth-frontier",
            ])
            return {
                "deficit": "model-capacity-gap",
                "confidence": 0.9 if best_depth else 0.82,
                "evidence": evidence,
                "recommended_action": "deepen-composition-search",
            }

        # If the bounded grammar is already at its depth ceiling and neither
        # more evidence nor a saturated enumeration explains the miss, do not
        # blindly spend more compute.  Surface a representation/model mismatch.
        if max_depth >= 3 and oracle < 0.999999:
            evidence.extend([
                f"depth-limit={max_depth}",
                f"hidden-oracle={oracle:.6f}",
                "no-observed-budget-saturation",
            ])
            return {
                "deficit": "representation-gap",
                "confidence": 0.72,
                "evidence": evidence,
                "recommended_action": "request-new-trusted-primitive-or-model-family",
            }

        evidence.extend([
            f"train={train:.6f}",
            f"holdout={holdout:.6f}",
            f"oracle={oracle:.6f}",
        ])
        return {
            "deficit": "unresolved-model-mismatch",
            "confidence": 0.55,
            "evidence": evidence,
            "recommended_action": "collect-independent-evidence-before-mutation",
        }

    def propose_metacognitive_policy_change(
        self,
        diagnosis: dict[str, Any],
        *,
        policy: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Translate one deficit diagnosis into one conservative bounded action."""
        before = dict(policy or self.reasoning_policy)
        proposal = dict(before)
        deficit = str(diagnosis.get("deficit") or "unresolved-model-mismatch")
        action = "no-change"

        if deficit == "model-capacity-gap" and int(proposal.get("max_depth", 1)) < 3:
            proposal["max_depth"] = int(proposal.get("max_depth", 1)) + 1
            proposal["max_generated"] = max(int(proposal.get("max_generated", 6000)), 9000)
            action = "increase-depth"
        elif deficit == "search-budget-gap":
            proposal["max_generated"] = min(24000, int(proposal.get("max_generated", 6000)) + 4000)
            action = "increase-search-budget"
        elif deficit == "evidence-gap":
            # v13 ablation showed that four actively chosen counterexamples are
            # sufficient to break the equality-boundary ambiguities that plain
            # random holdout often misses.  Jump to that proven bounded floor
            # instead of spending multiple meta-rounds inching 0→2→4.
            proposal["counterexample_rounds"] = min(8, max(4, int(proposal.get("counterexample_rounds", 0)) + 2))
            proposal["evidence_rows"] = min(20, max(12, int(proposal.get("evidence_rows", 8)) + 2))
            action = "increase-discriminating-evidence"
        elif deficit in {"representation-gap", "unresolved-model-mismatch"}:
            # Intentional abstention: changing unrelated knobs is not learning.
            action = "abstain-and-escalate-model-class"

        return {
            "diagnosis": deficit,
            "action": action,
            "policy_before": before,
            "policy_proposed": proposal,
            "changed": proposal != before,
        }

    def _metacognitive_benchmark_cases(self) -> list[dict[str, Any]]:
        """Controlled cases whose *failure causes* differ while task syntax stays bounded."""
        canonical = {item["name"]: item for item in self._curriculum_task_specs()}
        novel = self._generate_self_challenge_specs(count=8, seed=14007)
        bitwise = next(item for item in novel if "bitwise" in str(item.get("family")))
        boundary_logic = {
            "name": "meta_logic_counterexample",
            "family": "meta-evidence",
            "arity": 3,
            "tree": (
                "op", "boolean.or",
                (
                    ("op", "relation.less", (("arg", 0), ("arg", 1))),
                    ("op", "relation.less_equal", (("arg", 1), ("arg", 2))),
                ),
            ),
        }
        return [
            {
                "name": "capacity_case",
                "expected_deficit": "model-capacity-gap",
                "spec": canonical["absolute_composition"],
                "policy": {
                    "max_depth": 1, "max_candidates": 12, "max_generated": 6000,
                    "evidence_rows": 8, "counterexample_rounds": 0, "accepted_rounds": 0,
                },
                "diagnosis_variant": 14501,
                "validation_variant": 24501,
            },
            {
                "name": "budget_case",
                "expected_deficit": "search-budget-gap",
                "spec": bitwise,
                "policy": {
                    "max_depth": 2, "max_candidates": 12, "max_generated": 256,
                    "evidence_rows": 12, "counterexample_rounds": 4, "accepted_rounds": 0,
                },
                "diagnosis_variant": 14519,
                "validation_variant": 24519,
            },
            {
                "name": "evidence_case",
                "expected_deficit": "evidence-gap",
                "spec": boundary_logic,
                "policy": {
                    "max_depth": 3, "max_candidates": 12, "max_generated": 12000,
                    "evidence_rows": 12, "counterexample_rounds": 0, "accepted_rounds": 0,
                },
                "diagnosis_variant": 21127,
                "validation_variant": 31127,
            },
        ]

    def benchmark_metacognitive_reasoning(self) -> dict[str, Any]:
        """
        Test whether the controller can identify *why* reasoning failed and pick
        a useful, cause-specific action on a numerically fresh validation split.
        """
        results: list[dict[str, Any]] = []
        correct_diagnoses = 0
        useful_actions = 0
        for case in self._metacognitive_benchmark_cases():
            spec = case["spec"]
            policy = dict(case["policy"])
            diagnostic = self._evaluate_curriculum_task(
                spec, policy=policy, variant=int(case["diagnosis_variant"])
            )
            diagnosis = self.diagnose_reasoning_deficit(diagnostic, policy=policy)
            proposal = self.propose_metacognitive_policy_change(diagnosis, policy=policy)
            proposed_policy = dict(proposal["policy_proposed"])

            # Evaluate the old and proposed policy on the *same fresh variant*;
            # the diagnostic variant is never reused for admission.
            before_validation = self._evaluate_curriculum_task(
                spec, policy=policy, variant=int(case["validation_variant"])
            )
            after_validation = self._evaluate_curriculum_task(
                spec, policy=proposed_policy, variant=int(case["validation_variant"])
            )
            diagnosis_ok = diagnosis.get("deficit") == case["expected_deficit"]
            improved = float(after_validation["score"]) > float(before_validation["score"]) + 1e-9
            pass_gain = bool(after_validation.get("pass")) and not bool(before_validation.get("pass"))
            useful = bool(proposal.get("changed") and (improved or pass_gain))
            correct_diagnoses += int(diagnosis_ok)
            useful_actions += int(useful)
            results.append({
                "case": case["name"],
                "expected_deficit": case["expected_deficit"],
                "diagnosis": diagnosis,
                "proposal": proposal,
                "diagnosis_correct": diagnosis_ok,
                "score_before_fresh": before_validation["score"],
                "score_after_fresh": after_validation["score"],
                "pass_before_fresh": before_validation["pass"],
                "pass_after_fresh": after_validation["pass"],
                "useful_action": useful,
                "recovered_expression_after": after_validation.get("best_expression"),
            })

        total = len(results)
        diagnosis_accuracy = correct_diagnoses / max(1, total)
        action_success = useful_actions / max(1, total)
        meta_index = 0.55 * diagnosis_accuracy + 0.45 * action_success
        return {
            "schema": "ucr.metacognitive-benchmark/1",
            "reader_version": self.VERSION,
            "case_count": total,
            "correct_diagnoses": correct_diagnoses,
            "useful_actions": useful_actions,
            "diagnosis_accuracy": round(diagnosis_accuracy, 6),
            "action_success_rate": round(action_success, 6),
            "bounded_metacognitive_index": round(meta_index, 6),
            "results": results,
            "interpretation": {
                "measures": "cause-specific diagnosis and bounded strategy selection on fresh validation data",
                "does_not_measure": "general intelligence, consciousness, human IQ, unrestricted self-modification",
            },
        }

    def bounded_intelligence_profile(self) -> dict[str, Any]:
        """
        Derive a bounded cognitive profile from independently checkable tests.

        This is intentionally *not* an IQ score and not a claim of general
        intelligence.  It summarizes only the reasoning mechanisms implemented
        in this file: compositional induction, deficit diagnosis, strategy
        selection, fresh validation and epistemic restraint.
        """
        reasoning = self.benchmark_reasoning()
        meta = self.benchmark_metacognitive_reasoning()

        # Test restraint on a fresh, already-solved task.  A metacognitive
        # controller should recognize success and avoid needless mutation.
        restraint_spec = next(
            item for item in self._curriculum_task_specs()
            if item["name"] == "direct_arithmetic"
        )
        restraint_task = self._evaluate_curriculum_task(
            restraint_spec, policy=dict(self.reasoning_policy), variant=314159
        )
        restraint_diag = self.diagnose_reasoning_deficit(
            restraint_task, policy=dict(self.reasoning_policy)
        )
        restraint_proposal = self.propose_metacognitive_policy_change(
            restraint_diag, policy=dict(self.reasoning_policy)
        )
        restraint = float(
            bool(restraint_task.get("pass"))
            and restraint_diag.get("deficit") == "none"
            and not bool(restraint_proposal.get("changed"))
        )

        compositional = float(reasoning.get("pass_rate") or 0.0)
        diagnosis = float(meta.get("diagnosis_accuracy") or 0.0)
        strategy = float(meta.get("action_success_rate") or 0.0)
        # Fresh validation is already built into every metacognitive case; use
        # the fraction whose selected action actually improved a fresh split.
        fresh_transfer = strategy
        index = (
            0.30 * compositional
            + 0.25 * diagnosis
            + 0.25 * strategy
            + 0.10 * fresh_transfer
            + 0.10 * restraint
        )
        return {
            "schema": "ucr.bounded-intelligence-profile/1",
            "reader_version": self.VERSION,
            "bounded_cognitive_index": round(index, 6),
            "dimensions": {
                "compositional_reasoning": round(compositional, 6),
                "deficit_diagnosis": round(diagnosis, 6),
                "strategy_selection": round(strategy, 6),
                "fresh_validation_transfer": round(fresh_transfer, 6),
                "epistemic_restraint": round(restraint, 6),
            },
            "evidence": {
                "reasoning_benchmark": reasoning,
                "metacognitive_benchmark": meta,
                "restraint_test": {
                    "task_pass": bool(restraint_task.get("pass")),
                    "diagnosis": restraint_diag,
                    "proposal": restraint_proposal,
                },
            },
            "interpretation": {
                "measures": "bounded implemented reasoning abilities under synthetic blind/fresh tests",
                "does_not_measure": "human IQ, consciousness, subjective experience, unrestricted general intelligence",
            },
        }

    def run_metacognitive_reasoning_evolution(self) -> dict[str, Any]:
        """
        Apply the meta-controller to fresh self-challenges while preserving a
        conservative admission rule: fresh improvement + no canonical regression.
        """
        starting_policy = dict(self.reasoning_policy)
        diagnostic_specs = self._generate_self_challenge_specs(count=4, seed=14101)
        diagnostic_suite = self._evaluate_curriculum_suite(
            diagnostic_specs, policy=starting_policy, variant=14131
        )
        weakest = min(
            diagnostic_suite["tasks"],
            key=lambda x: (bool(x.get("pass")), float(x.get("score", 0.0)), str(x.get("task"))),
        )
        diagnosis = self.diagnose_reasoning_deficit(weakest, policy=starting_policy)
        proposal_info = self.propose_metacognitive_policy_change(diagnosis, policy=starting_policy)
        proposal = dict(proposal_info["policy_proposed"])

        validation_variant = 24131
        current_validation = self._evaluate_curriculum_suite(
            diagnostic_specs, policy=starting_policy, variant=validation_variant
        )
        candidate_validation = self._evaluate_curriculum_suite(
            diagnostic_specs, policy=proposal, variant=validation_variant
        )
        canonical = self._curriculum_task_specs()
        current_core = self._evaluate_curriculum_suite(canonical, policy=starting_policy, variant=24197)
        candidate_core = self._evaluate_curriculum_suite(canonical, policy=proposal, variant=24197)

        gain = float(candidate_validation["aggregate_score"]) - float(current_validation["aggregate_score"])
        no_core_regression = float(candidate_core["aggregate_score"]) + 1e-12 >= float(current_core["aggregate_score"])
        accepted = bool(proposal_info.get("changed") and gain > 1e-9 and no_core_regression)
        if accepted:
            proposal["accepted_rounds"] = int(starting_policy.get("accepted_rounds", 0)) + 1
            self.reasoning_policy = proposal

        report = {
            "schema": "ucr.metacognitive-evolution/1",
            "reader_version": self.VERSION,
            "starting_policy": starting_policy,
            "diagnostic_suite": diagnostic_suite,
            "weakest_task": weakest,
            "diagnosis": diagnosis,
            "proposal": proposal_info,
            "fresh_validation_before": current_validation,
            "fresh_validation_after": candidate_validation,
            "fresh_gain": round(gain, 6),
            "core_before": current_core,
            "core_after": candidate_core,
            "no_core_regression": no_core_regression,
            "accepted": accepted,
            "final_policy": dict(self.reasoning_policy),
            "safety": {
                "unknown_code_executed": False,
                "self_source_rewritten": False,
                "adaptation_scope": "bounded-metacognitive-policy-selection-only",
            },
        }
        self.metacognitive_history.append(copy.deepcopy(report))
        return report


    # ---------------- v15 bounded autonomous primitive genesis ----------------

    def _grammar_rule_is_active(self, rule_id: str) -> bool:
        item = self.primitive_grammar_registry.get(str(rule_id), {})
        return bool(item.get("admitted"))

    def _compile_safe_primitive_blueprint(
        self,
        blueprint: dict[str, Any],
    ) -> Callable[..., Any]:
        """
        Compile one *trusted internal blueprint* into a tiny host-side function.

        This is intentionally not a source-code compiler.  The accepted grammar
        is a closed set of identifiers and small integer parameters.  No text
        from analyzed programs is eval/exec'd, imported or reflected into Python.
        """
        family = str(blueprint.get("family", ""))
        params = dict(blueprint.get("params") or {})

        def require_int(x: Any) -> int:
            if type(x) is not int:
                raise TypeError
            return x

        if family == "integer.mod_equal":
            modulus = int(params.get("modulus", 0))
            residue = int(params.get("residue", 0))
            if modulus < 2 or modulus > 8 or residue < 0 or residue >= modulus:
                raise ValueError("invalid bounded modular blueprint")
            def fn(a: Any, m: int = modulus, r: int = residue) -> bool:
                x = require_int(a)
                return x % m == r
            return fn

        if family == "integer.bit_test":
            bit = int(params.get("bit", -1))
            expected = int(params.get("expected", -1))
            if bit < 0 or bit > 7 or expected not in (0, 1):
                raise ValueError("invalid bounded bit-test blueprint")
            def fn(a: Any, b: int = bit, e: int = expected) -> bool:
                x = require_int(a)
                return ((x >> b) & 1) == e
            return fn

        if family == "integer.popcount_abs":
            def fn(a: Any) -> int:
                x = require_int(a)
                return abs(x).bit_count()
            return fn

        if family == "numeric.sign":
            def fn(a: Any) -> int:
                if type(a) not in (int, float):
                    raise TypeError
                return -1 if a < 0 else (1 if a > 0 else 0)
            return fn

        if family == "integer.digital_root_abs":
            def fn(a: Any) -> int:
                x = abs(require_int(a))
                return 0 if x == 0 else 1 + ((x - 1) % 9)
            return fn

        if family == "sequence.reverse":
            def fn(a: Any) -> Any:
                if type(a) not in (str, bytes, list, tuple):
                    raise TypeError
                return a[::-1]
            return fn

        if family == "meta.compose_unary2":
            if not self._grammar_rule_is_active("unary.compose2"):
                raise ValueError("compose_unary2 grammar rule is not admitted")
            inner = params.get("inner")
            outer = params.get("outer")
            if not isinstance(inner, dict) or not isinstance(outer, dict):
                raise ValueError("invalid composed blueprint")
            # v16 admits exactly one new grammar layer at a time.  Recursive
            # meta-composition remains disabled until a future separately tested
            # grammar rule is admitted.
            if str(inner.get("family", "")).startswith("meta.") or str(outer.get("family", "")).startswith("meta."):
                raise ValueError("nested meta composition is not admitted")
            inner_fn = self._compile_safe_primitive_blueprint(inner)
            outer_fn = self._compile_safe_primitive_blueprint(outer)
            def fn(a: Any) -> Any:
                mid = inner_fn(a)
                return outer_fn(mid)
            return fn

        raise ValueError(f"unsupported safe primitive blueprint: {family}")

    @staticmethod
    def _blueprint_complexity(blueprint: dict[str, Any]) -> int:
        family = str(blueprint.get("family", ""))
        if family == "meta.compose_unary2":
            params = dict(blueprint.get("params") or {})
            inner = params.get("inner") if isinstance(params.get("inner"), dict) else {}
            outer = params.get("outer") if isinstance(params.get("outer"), dict) else {}
            return 2 + UniversalCodeReader._blueprint_complexity(inner) + UniversalCodeReader._blueprint_complexity(outer)
        base = {
            "integer.mod_equal": 2,
            "integer.bit_test": 2,
            "numeric.sign": 3,
            "integer.popcount_abs": 4,
            "integer.digital_root_abs": 5,
            "sequence.reverse": 3,
        }.get(family, 99)
        return base + len(dict(blueprint.get("params") or {}))

    def _atomic_unary_blueprint_catalog(self, inputs: list[Any]) -> list[dict[str, Any]]:
        """Return atomic unary blueprints valid for the observed input type family."""
        out: list[dict[str, Any]] = []
        if inputs and all(type(x) is int for x in inputs):
            for modulus in range(2, 7):
                for residue in range(modulus):
                    out.append({
                        "family": "integer.mod_equal", "arity": 1, "category": "bitwise",
                        "params": {"modulus": modulus, "residue": residue},
                    })
            for bit in range(4):
                for expected in (0, 1):
                    out.append({
                        "family": "integer.bit_test", "arity": 1, "category": "bitwise",
                        "params": {"bit": bit, "expected": expected},
                    })
            out.extend([
                {"family": "numeric.sign", "arity": 1, "category": "arithmetic", "params": {}},
                {"family": "integer.popcount_abs", "arity": 1, "category": "bitwise", "params": {}},
                {"family": "integer.digital_root_abs", "arity": 1, "category": "arithmetic", "params": {}},
            ])
        if inputs and all(type(x) in (str, bytes, list, tuple) for x in inputs):
            out.append({"family": "sequence.reverse", "arity": 1, "category": "sequence", "params": {}})
        return out

    def _candidate_blueprints_from_examples(
        self,
        examples: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        """Generate safe candidate primitives from I/O *types*, not task names."""
        if not examples:
            return []
        arg_rows = [tuple(item.get("args") or ()) for item in examples]
        if not arg_rows or any(len(row) != 1 for row in arg_rows):
            return []
        inputs = [row[0] for row in arg_rows]
        outputs = [item.get("expected") for item in examples]
        out: list[dict[str, Any]] = []

        all_int = all(type(x) is int for x in inputs)
        all_bool_out = all(type(y) is bool for y in outputs)
        all_int_out = all(type(y) is int for y in outputs)
        all_seq = all(type(x) in (str, bytes, list, tuple) for x in inputs)

        if all_int and all_bool_out:
            for modulus in range(2, 7):
                for residue in range(modulus):
                    out.append({
                        "family": "integer.mod_equal",
                        "arity": 1,
                        "category": "bitwise",
                        "params": {"modulus": modulus, "residue": residue},
                    })
            for bit in range(4):
                for expected in (0, 1):
                    out.append({
                        "family": "integer.bit_test",
                        "arity": 1,
                        "category": "bitwise",
                        "params": {"bit": bit, "expected": expected},
                    })

        if all_int and all_int_out:
            out.extend([
                {"family": "numeric.sign", "arity": 1, "category": "arithmetic", "params": {}},
                {"family": "integer.popcount_abs", "arity": 1, "category": "bitwise", "params": {}},
                {"family": "integer.digital_root_abs", "arity": 1, "category": "arithmetic", "params": {}},
            ])

        if all_seq:
            out.append({"family": "sequence.reverse", "arity": 1, "category": "sequence", "params": {}})

        if self._grammar_rule_is_active("unary.compose2"):
            atoms = self._atomic_unary_blueprint_catalog(inputs)
            if all_int:
                int_outputs = [bp for bp in atoms if bp["family"] in {
                    "numeric.sign", "integer.popcount_abs", "integer.digital_root_abs"
                }]
                int_consumers = list(atoms)
                for inner in int_outputs:
                    for outer in int_consumers:
                        out.append({
                            "family": "meta.compose_unary2",
                            "arity": 1,
                            "category": "composed",
                            "params": {"inner": copy.deepcopy(inner), "outer": copy.deepcopy(outer)},
                        })
            elif all_seq:
                reverse = next((bp for bp in atoms if bp["family"] == "sequence.reverse"), None)
                if reverse is not None:
                    out.append({
                        "family": "meta.compose_unary2", "arity": 1, "category": "composed",
                        "params": {"inner": copy.deepcopy(reverse), "outer": copy.deepcopy(reverse)},
                    })

        # Deduplicate deterministically.
        seen: set[str] = set()
        unique: list[dict[str, Any]] = []
        for bp in out:
            key = json.dumps(bp, sort_keys=True, separators=(",", ":"), default=str)
            if key in seen:
                continue
            seen.add(key)
            unique.append(bp)
        unique.sort(key=lambda bp: (self._blueprint_complexity(bp), json.dumps(bp, sort_keys=True)))
        return unique

    def _score_safe_primitive(
        self,
        function: Callable[..., Any],
        examples: list[dict[str, Any]],
    ) -> dict[str, Any]:
        matched = 0
        outcomes: list[dict[str, Any]] = []
        for item in examples:
            args = tuple(item.get("args") or ())
            ok, value = self._apply_semantic_primitive(function, args)
            same = bool(ok and self._semantic_equal(value, item.get("expected")))
            matched += int(same)
            outcomes.append({
                "ok": bool(ok),
                "match": same,
                "value": self._canonical_semantic_value(value) if ok and self._is_safe_semantic_value(value) else None,
            })
        total = len(examples)
        material = json.dumps(outcomes, ensure_ascii=False, sort_keys=True, separators=(",", ":"), default=str)
        return {
            "matched": matched,
            "total": total,
            "score": matched / max(1, total),
            "behavioral_digest": hashlib.sha256(material.encode("utf-8")).hexdigest(),
        }

    def synthesize_safe_primitive(
        self,
        examples: Iterable[dict[str, Any]],
    ) -> dict[str, Any]:
        """
        Synthesize a primitive from the closed safe blueprint grammar.

        Selection uses only the supplied examples.  Hidden/fresh examples must
        be supplied by the caller later for admission; they are deliberately not
        consulted here.
        """
        rows = [dict(item) for item in examples if isinstance(item, dict)]
        candidates: list[dict[str, Any]] = []
        for blueprint in self._candidate_blueprints_from_examples(rows):
            try:
                function = self._compile_safe_primitive_blueprint(blueprint)
            except Exception:
                continue
            score = self._score_safe_primitive(function, rows)
            material = json.dumps(blueprint, sort_keys=True, separators=(",", ":"), default=str)
            machine_id = "evolved.p_" + hashlib.sha256(material.encode("utf-8")).hexdigest()[:16]
            candidates.append({
                "machine_id": machine_id,
                "blueprint": copy.deepcopy(blueprint),
                "complexity": self._blueprint_complexity(blueprint),
                "train_score": round(float(score["score"]), 6),
                "train_matched": score["matched"],
                "train_total": score["total"],
                "behavioral_digest": score["behavioral_digest"],
            })
        candidates.sort(key=lambda c: (-float(c["train_score"]), int(c["complexity"]), c["machine_id"]))
        best = candidates[0] if candidates else None
        return {
            "schema": "ucr.safe-primitive-synthesis/1",
            "reader_version": self.VERSION,
            "candidate_count": len(candidates),
            "best": copy.deepcopy(best),
            "candidates": copy.deepcopy(candidates[:16]),
            "safety": {
                "unknown_code_executed": False,
                "arbitrary_source_compilation": False,
                "candidate_language": "closed-safe-blueprint-grammar",
            },
        }

    def _primitive_genesis_challenge_pool(self) -> list[dict[str, Any]]:
        """Hidden-oracle task pool used to expose real representation gaps."""
        def even(a: Any) -> bool:
            if type(a) is not int: raise TypeError
            return a % 2 == 0
        def popcount(a: Any) -> int:
            if type(a) is not int: raise TypeError
            return abs(a).bit_count()
        def sign(a: Any) -> int:
            if type(a) not in (int, float): raise TypeError
            return -1 if a < 0 else (1 if a > 0 else 0)
        def digital_root(a: Any) -> int:
            if type(a) is not int: raise TypeError
            x = abs(a)
            return 0 if x == 0 else 1 + ((x - 1) % 9)

        grids = {
            "train": [-19, -14, -11, -8, -5, -3, -2, -1, 0, 1, 2, 3, 5, 8, 11, 14, 19, 23],
            "hidden": [-31, -24, -17, -10, -7, -4, 4, 6, 7, 9, 10, 13, 17, 24, 31],
            "fresh": [-47, -36, -29, -22, -15, -12, -6, 12, 15, 18, 21, 27, 29, 36, 47],
        }
        return [
            {"challenge_id": "rg-01", "oracle": even, "arity": 1, "grids": grids},
            {"challenge_id": "rg-02", "oracle": popcount, "arity": 1, "grids": grids},
            {"challenge_id": "rg-03", "oracle": sign, "arity": 1, "grids": grids},
            {"challenge_id": "rg-04", "oracle": digital_root, "arity": 1, "grids": grids},
        ]

    def _primitive_challenge_examples(
        self,
        challenge: dict[str, Any],
        split: str,
    ) -> list[dict[str, Any]]:
        oracle = challenge["oracle"]
        rows: list[dict[str, Any]] = []
        for value in list(challenge.get("grids", {}).get(split, [])):
            expected = oracle(value)
            rows.append({"args": (value,), "expected": expected})
        return rows

    def _reasoning_score_on_unary_oracle(
        self,
        challenge: dict[str, Any],
        *,
        train_split: str = "train",
        audit_split: str = "hidden",
        max_depth: int | None = None,
        max_generated: int | None = None,
    ) -> dict[str, Any]:
        train = self._primitive_challenge_examples(challenge, train_split)
        audit = self._primitive_challenge_examples(challenge, audit_split)
        observations = [
            {"code": "r ≔ Ω a", "inputs": {"a": row["args"][0]}, "output": row["expected"]}
            for row in train
        ]
        policy = self.reasoning_policy
        model = self.infer_compositional_reasoning(
            observations,
            max_depth=int(max_depth if max_depth is not None else policy.get("max_depth", 3)),
            max_candidates=int(policy.get("max_candidates", 12)),
            max_generated=int(max_generated if max_generated is not None else policy.get("max_generated", 12000)),
        )
        symbol = model.symbols.get("Ω")
        best = symbol.candidates[0] if symbol and symbol.candidates else None
        matched = 0
        if best is not None:
            for row in audit:
                ok, value = self._evaluate_reasoning_tree(best.tree, tuple(row["args"]))
                matched += int(ok and self._semantic_equal(value, row["expected"]))
        audit_score = matched / max(1, len(audit))
        return {
            "challenge_id": challenge["challenge_id"],
            "status": symbol.status if symbol else "no-hypothesis",
            "best_expression": best.expression if best else None,
            "train_score": float(best.train_score) if best else 0.0,
            "internal_holdout_score": float(best.holdout_score) if best and best.holdout_score is not None else 0.0,
            "external_audit_score": round(audit_score, 6),
            "pass": bool(best and float(best.train_score) >= 1.0 - 1e-12 and audit_score >= 1.0 - 1e-12),
        }

    def _admit_generated_primitive(
        self,
        candidate: dict[str, Any],
        *,
        challenge: dict[str, Any],
    ) -> dict[str, Any]:
        """Temporarily install, fresh-test, transfer-test, ablate, then commit/rollback."""
        label = str(candidate["machine_id"])
        blueprint = dict(candidate["blueprint"])
        function = self._compile_safe_primitive_blueprint(blueprint)
        train = self._primitive_challenge_examples(challenge, "train")
        hidden = self._primitive_challenge_examples(challenge, "hidden")
        fresh = self._primitive_challenge_examples(challenge, "fresh")
        hidden_score = self._score_safe_primitive(function, hidden)
        fresh_score = self._score_safe_primitive(function, fresh)

        core_before = self.benchmark_reasoning()
        baseline_reasoning = self._reasoning_score_on_unary_oracle(
            challenge, train_split="train", audit_split="fresh", max_depth=3, max_generated=12000
        )
        old_spec = self.semantic_primitives.get(label)
        self.register_semantic_primitive(
            label,
            function,
            arity=int(blueprint.get("arity", 1)),
            category=str(blueprint.get("category", "custom")),
            commutative=False,
            provenance={
                "origin": "ucr-v15-autonomous-safe-primitive-genesis",
                "blueprint": copy.deepcopy(blueprint),
                "challenge_id": challenge["challenge_id"],
            },
        )
        admitted_reasoning = self._reasoning_score_on_unary_oracle(
            challenge, train_split="train", audit_split="fresh", max_depth=2, max_generated=6000
        )
        core_after = self.benchmark_reasoning()

        # Transfer: require the new unary primitive to participate in a novel
        # composition with an old primitive on inputs not used for genesis.
        sample_output = train[0]["expected"] if train else None
        transfer_obs: list[dict[str, Any]] = []
        transfer_audit: list[dict[str, Any]] = []
        transfer_values = [-13, -9, -4, -1, 0, 2, 5, 9, 13, 18, 25, 33]
        for idx, a in enumerate(transfer_values):
            b = ((idx * 7) % 11) - 5
            base = challenge["oracle"](a)
            if type(sample_output) is bool:
                # A minimal but genuine composition test: the evolved boolean
                # primitive must combine with a pre-existing boolean primitive.
                expected = not bool(base)
                row = {"code": "r ≔ Ω a", "inputs": {"a": a}, "output": expected}
            else:
                expected = base + b
                row = {"code": "r ≔ Ω a b", "inputs": {"a": a, "b": b}, "output": expected}
            (transfer_obs if idx < 8 else transfer_audit).append(row)
        transfer_model = self.infer_compositional_reasoning(
            transfer_obs,
            max_depth=2,
            max_candidates=12,
            max_generated=9000,
        )
        transfer_symbol = transfer_model.symbols.get("Ω")
        transfer_best = transfer_symbol.candidates[0] if transfer_symbol and transfer_symbol.candidates else None
        transfer_matches = 0
        if transfer_best is not None:
            for obs in transfer_audit:
                if "b" in obs.get("inputs", {}):
                    args = (obs["inputs"]["a"], obs["inputs"]["b"])
                else:
                    args = (obs["inputs"]["a"],)
                ok, value = self._evaluate_reasoning_tree(transfer_best.tree, args)
                transfer_matches += int(ok and self._semantic_equal(value, obs["output"]))
        transfer_score = transfer_matches / max(1, len(transfer_audit))

        no_core_regression = float(core_after.get("pass_rate") or 0.0) + 1e-12 >= float(core_before.get("pass_rate") or 0.0)
        causal_gain = float(admitted_reasoning["external_audit_score"]) - float(baseline_reasoning["external_audit_score"])
        causal_pass_gain = bool(admitted_reasoning.get("pass") and not baseline_reasoning.get("pass"))
        candidate_exact = float(candidate.get("train_score", 0.0)) >= 1.0 - 1e-12
        hidden_exact = float(hidden_score["score"]) >= 1.0 - 1e-12
        fresh_exact = float(fresh_score["score"]) >= 1.0 - 1e-12
        transfer_pass = transfer_score >= 1.0 - 1e-12
        admission = bool(
            candidate_exact and hidden_exact and fresh_exact
            and admitted_reasoning.get("pass")
            and (causal_gain > 1e-9 or causal_pass_gain)
            and transfer_pass and no_core_regression
        )

        if admission:
            self.evolved_primitive_registry[label] = {
                "machine_id": label,
                "blueprint": copy.deepcopy(blueprint),
                "admitted_on": challenge["challenge_id"],
                "train_score": candidate.get("train_score"),
                "hidden_score": round(float(hidden_score["score"]), 6),
                "fresh_score": round(float(fresh_score["score"]), 6),
                "transfer_score": round(float(transfer_score), 6),
                "causal_gain": round(causal_gain, 6),
            }
        else:
            # Roll back only the temporary candidate.  Restore any previous spec
            # with the same deterministic label (normally impossible unless the
            # caller repeats an already-admitted blueprint).
            if old_spec is None:
                self.semantic_primitives.pop(label, None)
            else:
                self.semantic_primitives[label] = old_spec

        return {
            "machine_id": label,
            "blueprint": blueprint,
            "candidate_train_score": candidate.get("train_score"),
            "hidden_score": round(float(hidden_score["score"]), 6),
            "fresh_score": round(float(fresh_score["score"]), 6),
            "baseline_reasoning": baseline_reasoning,
            "admitted_reasoning": admitted_reasoning,
            "causal_gain": round(causal_gain, 6),
            "causal_pass_gain": causal_pass_gain,
            "causal_improvement": bool(causal_gain > 1e-9 or causal_pass_gain),
            "transfer": {
                "score": round(float(transfer_score), 6),
                "pass": transfer_pass,
                "best_expression": transfer_best.expression if transfer_best else None,
            },
            "core_before": {
                "pass_rate": core_before.get("pass_rate"),
                "bounded_reasoning_index": core_before.get("bounded_reasoning_index"),
            },
            "core_after": {
                "pass_rate": core_after.get("pass_rate"),
                "bounded_reasoning_index": core_after.get("bounded_reasoning_index"),
            },
            "no_core_regression": no_core_regression,
            "admitted": admission,
            "rollback": not admission,
        }

    def run_autonomous_self_development(self, *, max_generations: int = 2) -> dict[str, Any]:
        """
        Perform bounded autonomous capability growth.

        Each generation:
        1. evaluates several hidden-oracle challenges;
        2. chooses a failing representation gap without being told its meaning;
        3. synthesizes a primitive from the safe blueprint grammar using train I/O;
        4. requires hidden + fresh exactness, transfer, core regression, and causal ablation;
        5. admits or rolls back.

        The method mutates only ``semantic_primitives`` and the evolved registry
        of this Reader instance.  It never rewrites this file or executes unknown
        source code.
        """
        start_count = len(self.evolved_primitive_registry)
        generations: list[dict[str, Any]] = []
        blocked: set[str] = set()
        for generation in range(max(0, min(int(max_generations), 4))):
            pool = [c for c in self._primitive_genesis_challenge_pool() if c["challenge_id"] not in blocked]
            if not pool:
                break
            diagnoses = [
                self._reasoning_score_on_unary_oracle(
                    challenge,
                    train_split="train",
                    audit_split="hidden",
                    max_depth=2,
                    max_generated=6000,
                )
                for challenge in pool
            ]
            failing = [item for item in diagnoses if not item.get("pass")]
            if not failing:
                break
            weakest = min(failing, key=lambda item: (float(item.get("external_audit_score", 0.0)), item["challenge_id"]))
            challenge = next(c for c in pool if c["challenge_id"] == weakest["challenge_id"])
            train = self._primitive_challenge_examples(challenge, "train")
            synthesis = self.synthesize_safe_primitive(train)
            best = synthesis.get("best")
            if not best or float(best.get("train_score", 0.0)) < 1.0 - 1e-12:
                blocked.add(challenge["challenge_id"])
                generations.append({
                    "generation": generation + 1,
                    "diagnosis": weakest,
                    "synthesis": synthesis,
                    "admission": None,
                    "status": "WITHHOLD_NO_EXACT_SAFE_PRIMITIVE",
                })
                continue
            admission = self._admit_generated_primitive(best, challenge=challenge)
            generations.append({
                "generation": generation + 1,
                "diagnosis": weakest,
                "synthesis": synthesis,
                "admission": admission,
                "status": "ADMITTED" if admission.get("admitted") else "ROLLED_BACK",
            })
            blocked.add(challenge["challenge_id"])

        report = {
            "schema": "ucr.autonomous-self-development/1",
            "reader_version": self.VERSION,
            "starting_evolved_primitive_count": start_count,
            "ending_evolved_primitive_count": len(self.evolved_primitive_registry),
            "admitted_generation_count": sum(1 for g in generations if g.get("status") == "ADMITTED"),
            "generation_count": len(generations),
            "generations": generations,
            "evolved_registry": copy.deepcopy(self.evolved_primitive_registry),
            "final_reasoning_benchmark": self.benchmark_reasoning(),
            "safety": {
                "unknown_code_executed": False,
                "self_source_rewritten": False,
                "runtime_capability_mutation": True,
                "mutation_language": "closed-safe-blueprint-grammar",
                "admission_requires": [
                    "exact-train", "hidden-exact", "fresh-exact",
                    "causal-improvement", "novel-composition-transfer", "no-core-regression",
                ],
            },
            "interpretation": {
                "demonstrates": "bounded runtime self-improvement by admitted semantic primitive genesis",
                "does_not_demonstrate": "unrestricted recursive self-improvement, general intelligence, consciousness, arbitrary self-rewriting",
            },
        }
        self.self_development_history.append(copy.deepcopy(report))
        return report

    def export_evolved_state(self) -> dict[str, Any]:
        """Return a JSON-safe checkpoint containing only admitted safe blueprints/rules."""
        return {
            "schema": "ucr.evolved-state/2",
            "reader_version": self.VERSION,
            "grammar_rules": [
                copy.deepcopy(v) for k, v in sorted(self.primitive_grammar_registry.items())
                if k != "atomic.v1" and v.get("admitted")
            ],
            "primitives": [copy.deepcopy(v) for _, v in sorted(self.evolved_primitive_registry.items())],
        }

    def load_evolved_state(self, state: dict[str, Any]) -> dict[str, Any]:
        """Restore admitted blueprints/rules; no executable code is deserialized."""
        loaded = 0
        loaded_rules = 0
        rejected: list[dict[str, Any]] = []
        known_rules = {"unary.compose2"}
        for item in list((state or {}).get("grammar_rules") or []):
            if not isinstance(item, dict):
                rejected.append({"reason": "invalid-grammar-rule-entry"})
                continue
            rule_id = str(item.get("rule_id", ""))
            if rule_id not in known_rules or not item.get("admitted"):
                rejected.append({"rule_id": rule_id, "reason": "unknown-or-unadmitted-grammar-rule"})
                continue
            self.primitive_grammar_registry[rule_id] = {
                "rule_id": rule_id, "admitted": True, "origin": "loaded-admitted-evolved-state",
                "description": str(item.get("description", "admitted safe grammar rule")),
            }
            loaded_rules += 1
        for item in list((state or {}).get("primitives") or []):
            if not isinstance(item, dict) or not isinstance(item.get("blueprint"), dict):
                rejected.append({"reason": "invalid-entry"})
                continue
            blueprint = dict(item["blueprint"])
            material = json.dumps(blueprint, sort_keys=True, separators=(",", ":"), default=str)
            label = "evolved.p_" + hashlib.sha256(material.encode("utf-8")).hexdigest()[:16]
            if item.get("machine_id") not in (None, label):
                rejected.append({"machine_id": item.get("machine_id"), "reason": "digest-mismatch"})
                continue
            try:
                function = self._compile_safe_primitive_blueprint(blueprint)
                self.register_semantic_primitive(
                    label,
                    function,
                    arity=int(blueprint.get("arity", 1)),
                    category=str(blueprint.get("category", "custom")),
                    provenance={"origin": "loaded-admitted-evolved-state", "blueprint": copy.deepcopy(blueprint)},
                )
            except Exception as exc:
                rejected.append({"machine_id": label, "reason": type(exc).__name__})
                continue
            self.evolved_primitive_registry[label] = copy.deepcopy(item)
            self.evolved_primitive_registry[label]["machine_id"] = label
            loaded += 1
        return {
            "loaded": loaded,
            "loaded_grammar_rules": loaded_rules,
            "rejected": rejected,
            "registry_size": len(self.evolved_primitive_registry),
            "grammar_registry_size": len(self.primitive_grammar_registry),
        }

    # ---------------- v16 bounded grammar self-development ----------------

    def _grammar_gap_challenge_pool(self) -> list[dict[str, Any]]:
        def popcount_even(a: Any) -> bool:
            if type(a) is not int:
                raise TypeError
            return abs(a).bit_count() % 2 == 0

        def digital_root_even(a: Any) -> bool:
            if type(a) is not int:
                raise TypeError
            x = abs(a)
            root = 0 if x == 0 else 1 + ((x - 1) % 9)
            return root % 2 == 0

        grids = {
            "train": [-31,-27,-24,-19,-16,-15,-14,-12,-11,-10,-9,-8,-7,-6,-5,-4,-3,-2,-1,0,1,2,3,4,5,6,7,8,9,10,11,12,13,14,15,16,19,23,24,27,31],
            "hidden": [-47,-41,-36,-33,-29,-25,-22,-18,-17,-13,17,18,21,22,25,26,29,33,36,41,47],
            "fresh": [-63,-58,-52,-45,-39,-35,-30,-28,-21,-20,20,28,30,34,35,39,45,52,58,63],
        }
        return [
            {"challenge_id": "grammar-rg-01", "oracle": popcount_even, "arity": 1, "grids": grids},
            {"challenge_id": "grammar-rg-02", "oracle": digital_root_even, "arity": 1, "grids": grids},
        ]

    def _score_blueprint_synthesis_on_challenge(self, challenge: dict[str, Any]) -> dict[str, Any]:
        train = self._primitive_challenge_examples(challenge, "train")
        hidden = self._primitive_challenge_examples(challenge, "hidden")
        fresh = self._primitive_challenge_examples(challenge, "fresh")
        synthesis = self.synthesize_safe_primitive(train)
        best = synthesis.get("best")
        if not best:
            return {
                "challenge_id": challenge["challenge_id"], "best": None,
                "train_score": 0.0, "hidden_score": 0.0, "fresh_score": 0.0, "exact": False,
            }
        try:
            function = self._compile_safe_primitive_blueprint(best["blueprint"])
        except Exception:
            return {
                "challenge_id": challenge["challenge_id"], "best": copy.deepcopy(best),
                "train_score": float(best.get("train_score", 0.0)),
                "hidden_score": 0.0, "fresh_score": 0.0, "exact": False,
            }
        h = self._score_safe_primitive(function, hidden)["score"]
        f = self._score_safe_primitive(function, fresh)["score"]
        t = float(best.get("train_score", 0.0))
        return {
            "challenge_id": challenge["challenge_id"],
            "best": copy.deepcopy(best),
            "train_score": round(t, 6),
            "hidden_score": round(float(h), 6),
            "fresh_score": round(float(f), 6),
            "exact": bool(t >= 1.0 - 1e-12 and h >= 1.0 - 1e-12 and f >= 1.0 - 1e-12),
        }

    def _trial_grammar_rule(self, rule_id: str, *, primary: dict[str, Any], transfer: dict[str, Any]) -> dict[str, Any]:
        before_primary = self._score_blueprint_synthesis_on_challenge(primary)
        before_transfer = self._score_blueprint_synthesis_on_challenge(transfer)
        core_before = self.benchmark_reasoning()
        previous = copy.deepcopy(self.primitive_grammar_registry.get(rule_id))
        if rule_id == "unary.compose2":
            self.primitive_grammar_registry[rule_id] = {
                "rule_id": rule_id, "admitted": True, "origin": "v16-admission-probe",
                "description": "allow one bounded composition of two atomic unary blueprints",
            }
        elif rule_id == "atomic.redundancy":
            self.primitive_grammar_registry[rule_id] = {
                "rule_id": rule_id, "admitted": True, "origin": "v16-negative-control",
                "description": "negative control: does not add candidate forms",
            }
        else:
            raise ValueError("unknown bounded grammar-rule candidate")
        try:
            after_primary = self._score_blueprint_synthesis_on_challenge(primary)
            after_transfer = self._score_blueprint_synthesis_on_challenge(transfer)
            core_after = self.benchmark_reasoning()
        finally:
            if previous is None:
                self.primitive_grammar_registry.pop(rule_id, None)
            else:
                self.primitive_grammar_registry[rule_id] = previous
        no_core_regression = float(core_after.get("pass_rate") or 0.0) + 1e-12 >= float(core_before.get("pass_rate") or 0.0)
        gain = float(after_primary["fresh_score"]) - float(before_primary["fresh_score"])
        transfer_gain = float(after_transfer["fresh_score"]) - float(before_transfer["fresh_score"])
        causal = bool(after_primary["exact"] and not before_primary["exact"] and gain > 1e-9)
        transfer_pass = bool(after_transfer["exact"] and transfer_gain > 1e-9)
        return {
            "rule_id": rule_id,
            "primary_before": before_primary,
            "primary_after": after_primary,
            "transfer_before": before_transfer,
            "transfer_after": after_transfer,
            "fresh_gain": round(gain, 6),
            "transfer_gain": round(transfer_gain, 6),
            "causal_improvement": causal,
            "transfer_pass": transfer_pass,
            "no_core_regression": no_core_regression,
            "admissible": bool(causal and transfer_pass and no_core_regression),
        }

    def run_autonomous_grammar_evolution(self, *, max_generations: int = 1) -> dict[str, Any]:
        """
        Expand the *active safe primitive-generation grammar* under admission gates.

        A rule is admitted only when it closes a representation gap on one hidden
        challenge, transfers to a second unseen challenge, has a positive ablation
        effect versus the old grammar, and does not regress the core benchmark.
        The admitted rule still cannot execute arbitrary source code.
        """
        generations: list[dict[str, Any]] = []
        pool = self._grammar_gap_challenge_pool()
        dormant = [rule for rule in ("unary.compose2", "atomic.redundancy") if not self._grammar_rule_is_active(rule)]
        for generation in range(max(0, min(int(max_generations), 2))):
            if not dormant or len(pool) < 2:
                break
            baseline = [self._score_blueprint_synthesis_on_challenge(ch) for ch in pool]
            failing = [item for item in baseline if not item.get("exact")]
            if not failing:
                break
            weakest = min(failing, key=lambda x: (float(x.get("fresh_score", 0.0)), x["challenge_id"]))
            primary = next(ch for ch in pool if ch["challenge_id"] == weakest["challenge_id"])
            transfer = next(ch for ch in pool if ch["challenge_id"] != primary["challenge_id"])
            trials = [self._trial_grammar_rule(rule, primary=primary, transfer=transfer) for rule in dormant]
            trials.sort(key=lambda x: (bool(x["admissible"]), float(x["fresh_gain"]), float(x["transfer_gain"]), x["rule_id"]), reverse=True)
            best = trials[0] if trials else None
            if not best or not best.get("admissible"):
                generations.append({
                    "generation": generation + 1, "status": "WITHHOLD",
                    "diagnosis": weakest, "trials": trials,
                })
                break
            rule_id = str(best["rule_id"])
            self.primitive_grammar_registry[rule_id] = {
                "rule_id": rule_id, "admitted": True, "origin": "ucr-v16-autonomous-grammar-evolution",
                "description": "allow one bounded composition of two atomic unary blueprints",
                "admitted_on": primary["challenge_id"],
                "fresh_gain": best["fresh_gain"],
                "transfer_gain": best["transfer_gain"],
            }
            dormant = [rule for rule in dormant if rule != rule_id]

            # Materialize one capability enabled by the newly admitted grammar,
            # then apply the existing v15 hidden/fresh/transfer/rollback gate.
            synthesis = self.synthesize_safe_primitive(self._primitive_challenge_examples(primary, "train"))
            primitive_admission = None
            if synthesis.get("best") and float(synthesis["best"].get("train_score", 0.0)) >= 1.0 - 1e-12:
                primitive_admission = self._admit_generated_primitive(synthesis["best"], challenge=primary)
            generations.append({
                "generation": generation + 1,
                "status": "ADMITTED" if primitive_admission and primitive_admission.get("admitted") else "GRAMMAR_ADMITTED_PRIMITIVE_WITHHELD",
                "diagnosis": weakest,
                "selected_rule": copy.deepcopy(self.primitive_grammar_registry[rule_id]),
                "trials": trials,
                "primitive_synthesis": synthesis,
                "primitive_admission": primitive_admission,
            })
            break

        report = {
            "schema": "ucr.autonomous-grammar-evolution/1",
            "reader_version": self.VERSION,
            "generation_count": len(generations),
            "admitted_grammar_rules": [
                copy.deepcopy(v) for k, v in sorted(self.primitive_grammar_registry.items())
                if k != "atomic.v1" and v.get("admitted")
            ],
            "generations": generations,
            "evolved_primitive_count": len(self.evolved_primitive_registry),
            "final_reasoning_benchmark": self.benchmark_reasoning(),
            "safety": {
                "unknown_code_executed": False,
                "self_source_rewritten": False,
                "arbitrary_code_generation": False,
                "grammar_mutation_scope": "closed-host-defined-meta-catalog-only",
                "nested_meta_composition": False,
                "admission_requires": ["fresh-gain", "transfer-gain", "ablation", "no-core-regression"],
            },
            "interpretation": {
                "demonstrates": "bounded self-extension of the active safe primitive-generation grammar",
                "does_not_demonstrate": "unrestricted grammar invention, arbitrary recursive self-rewriting, or general intelligence",
            },
        }
        self.grammar_evolution_history.append(copy.deepcopy(report))
        return report

    def _curriculum_task_specs(self) -> list[dict[str, Any]]:
        """Trusted synthetic task families used only for blind curriculum scoring."""
        return [
            {
                "name": "direct_arithmetic",
                "family": "depth1-arithmetic",
                "arity": 2,
                "tree": ("op", "numeric.add", (("arg", 0), ("arg", 1))),
            },
            {
                "name": "direct_relation",
                "family": "depth1-relation",
                "arity": 2,
                "tree": ("op", "relation.less", (("arg", 0), ("arg", 1))),
            },
            {
                "name": "multiply_then_add",
                "family": "depth2-arithmetic",
                "arity": 3,
                "tree": (
                    "op", "numeric.add",
                    (("op", "numeric.multiply", (("arg", 0), ("arg", 1))), ("arg", 2)),
                ),
            },
            {
                "name": "relational_chain",
                "family": "depth2-logic",
                "arity": 3,
                "tree": (
                    "op", "boolean.and",
                    (
                        ("op", "relation.less", (("arg", 0), ("arg", 1))),
                        ("op", "relation.less", (("arg", 1), ("arg", 2))),
                    ),
                ),
            },
            {
                "name": "absolute_composition",
                "family": "depth3-arithmetic",
                "arity": 3,
                "tree": (
                    "op", "numeric.absolute",
                    (("op", "numeric.add", (("op", "numeric.multiply", (("arg", 0), ("arg", 1))), ("arg", 2))),),
                ),
            },
            {
                "name": "bitwise_transfer",
                "family": "depth1-bitwise",
                "arity": 2,
                "tree": ("op", "integer.bit_xor", (("arg", 0), ("arg", 1))),
            },
        ]

    @staticmethod
    def _curriculum_rows_for_spec(
        spec: dict[str, Any], *, variant: int, count: int
    ) -> list[tuple[int, ...]]:
        """Generate deterministic, label-diverse curriculum evidence."""
        name = str(spec.get("name"))
        arity = int(spec.get("arity", 2))
        curated: dict[str, list[tuple[int, ...]]] = {
            "direct_arithmetic": [
                (-7, 4), (-3, -2), (-1, 6), (0, 5), (2, 3), (4, -5), (7, 1), (9, -4),
                (11, 2), (-8, 3), (5, 5), (6, -9),
            ],
            "direct_relation": [
                (-4, -1), (-1, -4), (0, 0), (1, 2), (2, 1), (-3, 5), (5, -3), (7, 8),
                (8, 7), (3, 3), (-8, -2), (4, 9),
            ],
            "multiply_then_add": [
                (-4, 3, 2), (-2, -3, 5), (-1, 7, -4), (0, 6, 3), (2, 3, 4), (4, 5, -2),
                (7, 2, 1), (3, 6, 5), (5, -4, 2), (8, -1, 3), (6, 2, -9), (-5, 4, 7),
            ],
            "relational_chain": [
                (1, 2, 3), (3, 2, 1), (1, 5, 3), (3, 1, 5), (0, 1, 5), (5, 7, 9),
                (9, 7, 8), (-2, 0, 2), (2, 4, 3), (3, 4, 8), (7, 8, 6), (1, 4, 10),
            ],
            "absolute_composition": [
                (-4, 3, 2), (-3, 2, 8), (-2, -3, -1), (-1, 7, 10), (0, 6, -3), (2, 3, -10),
                (4, 5, -30), (7, 2, -20), (3, 6, 5), (5, -4, 2), (8, -1, 3), (-5, 4, 25),
            ],
            "bitwise_transfer": [
                (0, 0), (1, 2), (3, 5), (7, 1), (8, 3), (15, 6), (12, 10), (31, 7),
                (4, 9), (2, 14), (16, 5), (23, 11),
            ],
        }
        base = curated.get(name)
        if base is None:
            # Deterministic pseudo-random coverage for generated tasks.  The
            # previous Cartesian-prefix fallback could keep later arguments
            # nearly constant, which made some novel challenges artificially
            # easy or unidentifiable.
            state = int.from_bytes(
                hashlib.sha256(f"{name}|{variant}|{arity}".encode("utf-8")).digest()[:8],
                "big",
            ) or 1
            generated_rows: list[tuple[int, ...]] = []
            seen_rows: set[tuple[int, ...]] = set()
            while len(generated_rows) < 24:
                row: list[int] = []
                for _ in range(arity):
                    state = (2862933555777941757 * state + 3037000493) & ((1 << 64) - 1)
                    row.append(int((state >> 17) % 21) - 10)
                tup = tuple(row)
                if tup not in seen_rows:
                    seen_rows.add(tup)
                    generated_rows.append(tup)
            base = generated_rows
        # Positive affine transforms keep ordering tasks balanced while making
        # each validation variant numerically fresh.  Bitwise tasks keep their
        # curated integer domain and use rotation only.
        if name == "bitwise_transfer":
            transformed = list(base)
        else:
            scale = 1 + (abs(int(variant)) % 3)
            delta = (int(variant) % 7) - 3
            transformed = [tuple(scale * int(x) + delta for x in row) for row in base]
        shift = abs(int(variant)) % max(1, len(transformed))
        transformed = transformed[shift:] + transformed[:shift]
        if count > len(transformed):
            extra = []
            cycle = 1
            while len(transformed) + len(extra) < count:
                for row in transformed:
                    if len(transformed) + len(extra) >= count:
                        break
                    extra.append(tuple(int(x) + cycle for x in row))
                cycle += 1
            transformed.extend(extra)
        return transformed[: max(4, min(int(count), 24))]

    def _evaluate_curriculum_task(
        self,
        spec: dict[str, Any],
        *,
        policy: dict[str, Any],
        variant: int,
    ) -> dict[str, Any]:
        arity = int(spec["arity"])
        count = max(8, int(policy.get("evidence_rows", 8)))
        rows = self._curriculum_rows_for_spec(spec, variant=variant, count=count)
        symbol = "Ω" + hashlib.sha256(spec["name"].encode("utf-8")).hexdigest()[:5].upper()
        names = tuple(chr(ord("a") + i) for i in range(arity))
        code = f"r = {symbol}({','.join(names)})"
        observations: list[dict[str, Any]] = []
        for row in rows:
            ok, expected = self._evaluate_reasoning_tree(spec["tree"], tuple(row))
            if not ok:
                continue
            observations.append({
                "code": code,
                "inputs": {names[i]: row[i] for i in range(arity)},
                "output": expected,
            })

        # A hidden audit distribution is never passed to induction unless a
        # counterexample round explicitly promotes one failing row to new
        # experience.  This prevents a coincidentally perfect small holdout
        # from being mistaken for true transfer.
        audit_rows = self._curriculum_rows_for_spec(
            spec, variant=variant + 700001, count=24
        )
        # Add a compact boundary grid.  Purely pseudo-random audits can miss
        # the exact equalities that distinguish < from <= or > from >=.
        # These rows remain hidden from induction unless CEGIS promotes one
        # concrete failure to new experience.
        boundary_values = (-2, -1, 0, 1, 2)
        if arity <= 3:
            boundary_rows = list(itertools.product(boundary_values, repeat=arity))
            # Keep the audit bounded while retaining equality/sign boundaries.
            if len(boundary_rows) > 125:
                boundary_rows = boundary_rows[:125]
            merged_rows: list[tuple[int, ...]] = []
            seen_audit: set[tuple[int, ...]] = set()
            for row in list(boundary_rows) + list(audit_rows):
                tup = tuple(int(x) for x in row)
                if tup not in seen_audit:
                    seen_audit.add(tup)
                    merged_rows.append(tup)
            audit_rows = merged_rows

        def fit() -> tuple[CognitiveReasoningModel, ReasoningSymbol | None, ReasoningCandidate | None]:
            model_local = self._infer_reasoning_with_policy(observations, policy=policy)
            item_local = model_local.symbols.get(symbol)
            best_local = item_local.candidates[0] if item_local and item_local.candidates else None
            return model_local, item_local, best_local

        def oracle_audit(best_local: ReasoningCandidate | None) -> tuple[float, list[dict[str, Any]]]:
            if best_local is None or best_local.tree is None:
                return 0.0, []
            matched = 0
            total = 0
            failures: list[dict[str, Any]] = []
            for row in audit_rows:
                ok_target, expected = self._evaluate_reasoning_tree(spec["tree"], tuple(row))
                if not ok_target:
                    continue
                ok_pred, predicted = self._evaluate_reasoning_tree(best_local.tree, tuple(row))
                total += 1
                if ok_pred and self._semantic_equal(predicted, expected):
                    matched += 1
                elif len(failures) < 8:
                    failures.append({
                        "row": tuple(row),
                        "expected": expected,
                        "predicted": predicted if ok_pred else None,
                    })
            return (matched / max(1, total)), failures

        model, item, best = fit()
        oracle_score, oracle_failures = oracle_audit(best)
        counterexamples_used: list[dict[str, Any]] = []
        max_counterexamples = max(0, min(int(policy.get("counterexample_rounds", 0)), 8))

        def select_discriminating_oracle_probe(
            item_local: ReasoningSymbol | None,
            best_local: ReasoningCandidate | None,
        ) -> tuple[dict[str, Any], Any, str] | None:
            if item_local is None or best_local is None:
                return None
            existing_inputs = {
                tuple(existing.get("inputs", {}).get(name) for name in names)
                for existing in observations
                if isinstance(existing.get("inputs"), dict)
            }
            candidates = [c for c in item_local.candidates[:16] if c.tree is not None]
            ranked_rows: list[tuple[int, int, tuple[int, ...], Any]] = []
            for audit_row in audit_rows:
                row_tuple = tuple(audit_row)
                if row_tuple in existing_inputs:
                    continue
                ok_expected, expected = self._evaluate_reasoning_tree(spec["tree"], row_tuple)
                if not ok_expected:
                    continue
                best_ok, best_pred = self._evaluate_reasoning_tree(best_local.tree, row_tuple)
                best_wrong = int(not best_ok or not self._semantic_equal(best_pred, expected))
                disagreements = 0
                for candidate in candidates:
                    ok_pred, pred = self._evaluate_reasoning_tree(candidate.tree, row_tuple)
                    if not ok_pred or not self._semantic_equal(pred, expected):
                        disagreements += 1
                if best_wrong or (bool(item_local.diagnostics.get("ambiguity")) and disagreements):
                    ranked_rows.append((best_wrong, disagreements, row_tuple, expected))
            if not ranked_rows:
                return None
            # Prefer an actual counterexample to the current best; within that,
            # maximize how many rival hypotheses the observation eliminates.
            ranked_rows.sort(key=lambda x: (x[0], x[1], repr(x[2])), reverse=True)
            best_wrong, disagreements, row_tuple, expected = ranked_rows[0]
            inputs = {names[i]: row_tuple[i] for i in range(arity)}
            kind = "oracle-counterexample" if best_wrong else "oracle-disambiguation"
            return inputs, expected, kind

        for _ in range(max_counterexamples):
            selected = select_discriminating_oracle_probe(item, best)
            if selected is None:
                break
            inputs, expected, probe_kind = selected
            observation = {"code": code, "inputs": inputs, "output": expected}
            observations.append(observation)
            counterexamples_used.append({
                "kind": probe_kind,
                "inputs": inputs,
                "expected": self._canonical_semantic_value(expected),
            })
            model, item, best = fit()
            oracle_score, oracle_failures = oracle_audit(best)
            if (
                oracle_score >= 1.0 - 1e-12
                and item is not None
                and not bool(item.diagnostics.get("ambiguity"))
            ):
                break

        train_score = float(best.train_score) if best else 0.0
        holdout_score = float(best.holdout_score) if best and best.holdout_score is not None else 0.0
        ambiguous = bool(item.diagnostics.get("ambiguity")) if item else False
        # Hidden oracle transfer gets half the weight.  Training fit alone can
        # no longer dominate curriculum admission.
        score = (
            0.20 * train_score + 0.30 * holdout_score + 0.50 * oracle_score
        ) * (0.85 if ambiguous else 1.0)
        task_pass = bool(
            best and best.train_score == 1.0 and best.holdout_score == 1.0
            and oracle_score >= 1.0 - 1e-12
            and item and item.status == "holdout-supported"
            and not ambiguous
        )
        return {
            "task": spec["name"],
            "family": spec["family"],
            "pass": task_pass,
            "score": round(score, 6),
            "train_score": round(train_score, 6),
            "holdout_score": round(holdout_score, 6),
            "oracle_score": round(oracle_score, 6),
            "status": item.status if item else "missing",
            "confidence": item.confidence if item else 0.0,
            "best_expression": best.expression if best else None,
            "best_depth": best.depth if best else None,
            "generated_expression_count": (
                item.diagnostics.get("generated_expression_count") if item else 0
            ),
            "ambiguous": ambiguous,
            "observation_count": len(observations),
            "counterexamples_used": counterexamples_used,
            "remaining_oracle_failures": len(oracle_failures),
        }

    def _evaluate_curriculum_suite(
        self,
        specs: list[dict[str, Any]],
        *,
        policy: dict[str, Any],
        variant: int,
    ) -> dict[str, Any]:
        tasks = [
            self._evaluate_curriculum_task(spec, policy=policy, variant=variant + index * 17)
            for index, spec in enumerate(specs)
        ]
        aggregate = statistics.fmean(float(item["score"]) for item in tasks) if tasks else 0.0
        pass_rate = sum(bool(item["pass"]) for item in tasks) / max(1, len(tasks))
        return {
            "policy": dict(policy),
            "aggregate_score": round(aggregate, 6),
            "pass_rate": round(pass_rate, 6),
            "passed": sum(bool(item["pass"]) for item in tasks),
            "task_count": len(tasks),
            "tasks": tasks,
        }

    def read_with_cognitive_observations(
        self,
        payload: bytes | bytearray | memoryview | str,
        observations: Iterable[dict[str, Any]],
        filename: str | None = None,
        *,
        language_hint: str | None = None,
        max_depth: int = 2,
    ) -> tuple[ReadResult, dict[str, Any]]:
        """Attach the bounded cognitive-cycle evidence to a normal read result."""
        result = self.read(payload, filename=filename, language_hint=language_hint)
        cycle = self.cognitive_cycle(observations, program=payload, max_depth=max_depth)
        composed = cycle.get("compositional_reasoning", {})
        for key, item in composed.get("symbols", {}).items():
            candidates = item.get("candidates") or []
            best = candidates[0] if candidates else None
            nid = self._node_id("cognitive", key, item.get("status"), best.get("expression") if best else None)
            result.nodes.append(IRNode(
                nid,
                "cognitive.reasoning_hypothesis",
                item.get("symbol"),
                [],
                {
                    "status": item.get("status"),
                    "confidence": item.get("confidence"),
                    "best_expression": best.get("expression") if best else None,
                    "holdout_score": best.get("holdout_score") if best else None,
                    "suggested_probes": item.get("suggested_probes", [])[:3],
                },
            ))
        result.metadata["cognitive_profile"] = cycle.get("profile", {})
        result.metadata["cognitive_deficit_count"] = len(cycle.get("deficits", []))
        result.metadata["cognitive_next_goal_count"] = len(cycle.get("next_goals", []))
        result.metadata["node_count"] = len(result.nodes)
        return result, cycle

    def _synthesize_reasoning_trees(
        self,
        *,
        arity: int,
        train_trials: list[dict[str, Any]],
        max_depth: int,
        max_generated: int,
    ) -> list[Any]:
        leaves: list[Any] = [("arg", i) for i in range(arity)]
        generated: list[Any] = list(leaves)
        seen: set[str] = {repr(x) for x in leaves}
        active_limit = max_generated

        priority = {
            "arithmetic": 0, "selection": 1, "relation": 2, "boolean": 3,
            "projection": 4, "bitwise": 5, "sequence": 6, "mapping": 7,
            "construction": 8, "custom": 9,
        }
        unary = [
            (label, spec) for label, spec in self.semantic_primitives.items()
            if spec.get("arity") == 1
        ]
        binary = [
            (label, spec) for label, spec in self.semantic_primitives.items()
            if spec.get("arity") == 2
        ]
        unary.sort(key=lambda item: (priority.get(str(item[1].get("category")), 99), item[0]))
        binary.sort(key=lambda item: (priority.get(str(item[1].get("category")), 99), item[0]))

        def add(tree: Any) -> bool:
            if len(generated) >= active_limit:
                return False
            key = repr(tree)
            if key in seen:
                return True
            seen.add(key)
            generated.append(tree)
            return True

        depth1: list[Any] = []
        if max_depth >= 1:
            for label, _ in unary:
                for leaf in leaves:
                    tree = ("op", label, (leaf,))
                    if not add(tree):
                        break
                    depth1.append(tree)
            for label, spec in binary:
                for i, left in enumerate(leaves):
                    for j, right in enumerate(leaves):
                        if spec.get("commutative") and j < i:
                            continue
                        tree = ("op", label, (left, right))
                        if not add(tree):
                            break
                        depth1.append(tree)

        if max_depth >= 2:
            if max_depth >= 3:
                active_limit = max(len(generated) + 256, int(max_generated * 0.67))
            else:
                active_limit = max_generated
        if max_depth >= 2 and len(generated) < active_limit:
            # Prefer distinct behaviors on training evidence; this keeps the
            # synthesis bounded while preserving useful intermediate concepts.
            behavior_best: dict[str, Any] = {}
            for tree in depth1:
                _, _, signature = self._score_reasoning_tree(tree, train_trials)
                if signature not in behavior_best:
                    behavior_best[signature] = tree
            frontier = list(behavior_best.values())[:512]

            # Evidence-driven operator promotion.  A fixed global category
            # order can starve a relevant family (notably bitwise operations)
            # before the bounded search budget reaches it.  Estimate which
            # primitive categories already explain the training evidence best
            # at depth 1, then promote those categories for deeper expansion.
            category_scores: dict[str, float] = {}
            for tree in frontier:
                if not isinstance(tree, tuple) or not tree or tree[0] != "op":
                    continue
                spec = self.semantic_primitives.get(str(tree[1]), {})
                category = str(spec.get("category", "custom"))
                matched, total, _ = self._score_reasoning_tree(tree, train_trials)
                score = matched / max(1, total)
                category_scores[category] = max(category_scores.get(category, 0.0), score)
            adaptive_priority = {
                category: rank
                for rank, (category, _) in enumerate(
                    sorted(
                        category_scores.items(),
                        key=lambda item: (-item[1], priority.get(item[0], 99), item[0]),
                    )
                )
            }
            def deeper_sort_key(item: tuple[str, dict[str, Any]]) -> tuple[int, int, str]:
                category = str(item[1].get("category", "custom"))
                return (
                    adaptive_priority.get(category, len(adaptive_priority) + priority.get(category, 99)),
                    priority.get(category, 99),
                    item[0],
                )
            unary_deep = sorted(unary, key=deeper_sort_key)
            binary_deep = sorted(binary, key=deeper_sort_key)

            # Boolean compositions often need two independently inferred
            # relations, e.g. (a < b) AND (b < c).  Search this logically
            # important subspace *before* the broad arithmetic expansion so it
            # cannot be starved by the global candidate budget.
            relation_frontier = [
                tree for tree in frontier
                if tree[0] == "op" and self.semantic_primitives.get(tree[1], {}).get("category") in {"relation", "boolean"}
            ][:96]
            bool_ops = [(l, s) for l, s in binary if s.get("category") == "boolean"]
            for label, spec in bool_ops:
                for i, left in enumerate(relation_frontier):
                    for j, right in enumerate(relation_frontier):
                        if spec.get("commutative") and j < i:
                            continue
                        if not add(("op", label, (left, right))):
                            break
                    if len(generated) >= active_limit:
                        break
                if len(generated) >= active_limit:
                    break

            if len(generated) < active_limit:
                for label, _ in unary_deep:
                    for inner in frontier:
                        if not add(("op", label, (inner,))):
                            break
                    if len(generated) >= active_limit:
                        break
            if len(generated) < active_limit:
                for label, spec in binary_deep:
                    for inner in frontier:
                        for leaf in leaves:
                            if not add(("op", label, (inner, leaf))):
                                break
                            if not spec.get("commutative"):
                                if not add(("op", label, (leaf, inner))):
                                    break
                        if len(generated) >= active_limit:
                            break
                    if len(generated) >= active_limit:
                        break

        if max_depth >= 3:
            active_limit = max_generated
        if max_depth >= 3 and len(generated) < active_limit:
            # A narrow third layer: take the best-scoring depth<=2 expressions
            # and compose them with raw arguments.  This avoids combinatorial
            # explosion while permitting structures such as abs(a-b)+c.
            scored: list[tuple[float, int, Any]] = []
            for tree in generated:
                matched, total, _ = self._score_reasoning_tree(tree, train_trials)
                score = matched / max(1, total)
                complexity, depth = self._reasoning_tree_complexity(tree)
                if depth >= 1:
                    scored.append((score, -complexity, tree))
            scored.sort(key=lambda x: (x[0], x[1], repr(x[2])), reverse=True)
            frontier3 = [tree for _, _, tree in scored[:96]]
            for label, _ in unary_deep:
                for inner in frontier3:
                    if not add(("op", label, (inner,))):
                        break
            for label, spec in binary_deep:
                for inner in frontier3:
                    for leaf in leaves:
                        if not add(("op", label, (inner, leaf))):
                            break
                        if not spec.get("commutative") and not add(("op", label, (leaf, inner))):
                            break
                    if len(generated) >= active_limit:
                        break
                if len(generated) >= active_limit:
                    break

        return generated

    def _evaluate_reasoning_tree(self, tree: Any, args: tuple[Any, ...]) -> tuple[bool, Any]:
        if not isinstance(tree, tuple) or not tree:
            return False, None
        if tree[0] == "arg":
            index = int(tree[1])
            if index < 0 or index >= len(args):
                return False, None
            return True, args[index]
        if tree[0] != "op" or len(tree) != 3:
            return False, None
        label = str(tree[1])
        spec = self.semantic_primitives.get(label)
        if not spec:
            return False, None
        child_values: list[Any] = []
        for child in tree[2]:
            ok, value = self._evaluate_reasoning_tree(child, args)
            if not ok:
                return False, None
            child_values.append(value)
        ok, value = self._apply_semantic_primitive(spec["function"], tuple(child_values))
        if not ok or not self._is_safe_semantic_value(value):
            return False, None
        return True, value

    def _score_reasoning_tree(
        self,
        tree: Any,
        trials: list[dict[str, Any]],
    ) -> tuple[int, int, str]:
        matched = 0
        outcomes: list[Any] = []
        for trial in trials:
            ok, value = self._evaluate_reasoning_tree(tree, tuple(trial["args"]))
            if ok:
                is_match = self._semantic_equal(value, trial["expected"])
                matched += int(is_match)
                outcomes.append({"ok": True, "value": self._canonical_semantic_value(value), "match": is_match})
            else:
                outcomes.append({"ok": False})
        material = json.dumps(outcomes, ensure_ascii=False, sort_keys=True, separators=(",", ":"), default=str)
        return matched, len(trials), hashlib.sha256(material.encode("utf-8")).hexdigest()

    def _reasoning_tree_complexity(self, tree: Any) -> tuple[int, int]:
        if tree[0] == "arg":
            return 1, 0
        child_stats = [self._reasoning_tree_complexity(child) for child in tree[2]]
        return 1 + sum(c for c, _ in child_stats), 1 + max((d for _, d in child_stats), default=0)

    def _reasoning_tree_text(self, tree: Any, operand_names: tuple[str, ...]) -> str:
        if tree[0] == "arg":
            index = int(tree[1])
            return operand_names[index] if index < len(operand_names) and operand_names[index] else f"arg{index}"
        label = str(tree[1])
        children = ", ".join(self._reasoning_tree_text(child, operand_names) for child in tree[2])
        return f"{label}({children})"

    def _reasoning_behavioral_digest(self, tree: Any, trials: list[dict[str, Any]]) -> str:
        behavior: list[Any] = []
        for trial in trials:
            ok, value = self._evaluate_reasoning_tree(tree, tuple(trial["args"]))
            behavior.append(
                {"ok": ok, "value": self._canonical_semantic_value(value) if ok else None}
            )
        material = json.dumps(behavior, ensure_ascii=False, sort_keys=True, separators=(",", ":"), default=str)
        return hashlib.sha256(material.encode("utf-8")).hexdigest()

    def _suggest_compositional_probes(
        self,
        ranked: list[ReasoningCandidate],
        *,
        arity: int,
        operand_names: tuple[str, ...],
        max_probes: int = 5,
    ) -> list[dict[str, Any]]:
        if len(ranked) < 2 or not 1 <= arity <= 4:
            return []
        plausible = [c for c in ranked[:6] if c.combined_score >= max(0.5, ranked[0].combined_score - 0.1)]
        if len(plausible) < 2:
            return []
        values: tuple[Any, ...] = (-3, -1, 0, 1, 2, 3, 5)
        candidates: list[tuple[int, tuple[Any, ...], dict[str, Any]]] = []
        checked = 0
        for args in itertools.product(values, repeat=arity):
            checked += 1
            if checked > 768:
                break
            predictions: dict[str, Any] = {}
            distinct: set[str] = set()
            for candidate in plausible:
                ok, value = self._evaluate_reasoning_tree(candidate.tree, tuple(args))
                if not ok:
                    continue
                canonical = self._canonical_semantic_value(value)
                token = json.dumps(canonical, sort_keys=True, ensure_ascii=False, separators=(",", ":"), default=str)
                predictions[candidate.expression] = canonical
                distinct.add(token)
            if len(distinct) >= 2:
                input_map = {
                    (operand_names[i] if i < len(operand_names) and operand_names[i] else f"arg{i}"): args[i]
                    for i in range(arity)
                }
                candidates.append((len(distinct), args, {"inputs": input_map, "predictions": predictions}))
        candidates.sort(key=lambda item: (item[0], repr(item[1])), reverse=True)
        return [item[2] for item in candidates[:max_probes]]

    @staticmethod
    def _reasoning_profile(symbols: dict[str, ReasoningSymbol]) -> dict[str, Any]:
        if not symbols:
            return {
                "bounded_reasoning_index": 0.0,
                "status": "insufficient-evidence",
                "claim": "not a measure of general intelligence or IQ",
            }
        vals = list(symbols.values())
        confidence = statistics.fmean(s.confidence for s in vals)
        generalization_values = [
            float(s.diagnostics.get("generalization_score", 0.0) or 0.0) for s in vals
        ]
        generalization = statistics.fmean(generalization_values) if generalization_values else 0.0
        supported = sum(s.status == "holdout-supported" for s in vals) / len(vals)
        ambiguity_rate = sum(s.status == "ambiguous" for s in vals) / len(vals)
        compositional = sum(
            bool(s.candidates) and s.candidates[0].depth >= 2 and float(s.diagnostics.get("generalization_score", 0.0) or 0.0) >= 0.9
            for s in vals
        ) / len(vals)
        active_learning = sum(bool(s.suggested_probes) for s in vals) / len(vals)
        index = (
            0.35 * generalization +
            0.20 * confidence +
            0.20 * supported +
            0.15 * compositional +
            0.10 * (1.0 - ambiguity_rate)
        )
        return {
            "bounded_reasoning_index": round(max(0.0, min(1.0, index)), 6),
            "generalization": round(generalization, 6),
            "mean_confidence": round(confidence, 6),
            "holdout_supported_fraction": round(supported, 6),
            "compositional_success_fraction": round(compositional, 6),
            "ambiguity_rate": round(ambiguity_rate, 6),
            "active_learning_probe_fraction": round(active_learning, 6),
            "status": "bounded-evidence-profile",
            "claim": "not a measure of general intelligence or IQ",
        }

    def read_with_observations(
        self,
        payload: bytes | bytearray | memoryview | str,
        observations: Iterable[dict[str, Any]],
        filename: str | None = None,
        *,
        language_hint: str | None = None,
    ) -> tuple[ReadResult, SemanticModel]:
        """Read code and attach behavioral semantic hypotheses to its AI-IR."""
        result = self.read(payload, filename=filename, language_hint=language_hint)
        obs_list = []
        for observation in observations:
            if isinstance(observation, dict):
                item = dict(observation)
                item.setdefault("code", payload)
                obs_list.append(item)
            else:
                obs_list.append(observation)
        model = self.infer_semantics(obs_list)

        for key, semantic in model.symbols.items():
            parent_id = self._node_id("semantic-symbol", key, semantic.form, semantic.arity)
            candidate_ids: list[str] = []
            for rank, candidate in enumerate(semantic.candidates, 1):
                cid = self._node_id("semantic-candidate", key, candidate.semantic_id, rank)
                candidate_ids.append(cid)
                result.nodes.append(IRNode(
                    cid,
                    "semantic.candidate",
                    candidate.semantic_id,
                    [],
                    {
                        "rank": rank,
                        "label": candidate.label,
                        "score": candidate.score,
                        "matched": candidate.matched,
                        "total": candidate.total,
                        "behavioral_digest": candidate.behavioral_digest,
                        **candidate.meta,
                    },
                ))
            result.nodes.append(IRNode(
                parent_id,
                "semantic.symbol_hypothesis",
                semantic.symbol,
                candidate_ids,
                {
                    "form": semantic.form,
                    "arity": semantic.arity,
                    "observations": semantic.observations,
                    "confidence": semantic.confidence,
                    "status": semantic.status,
                    "suggested_probes": semantic.suggested_probes,
                },
            ))

        result.metadata["semantic_model"] = {
            "symbol_count": len(model.symbols),
            "unresolved_observations": len(model.unresolved),
            "semantic_status": model.metadata.get("semantic_status"),
        }
        result.metadata["node_count"] = len(result.nodes)
        return result, model

    def infer_stateful_semantics(
        self,
        observations: Iterable[dict[str, Any]],
        *,
        program: bytes | bytearray | memoryview | str | None = None,
        max_program_candidates: int = 16,
        max_combinations: int = 4096,
    ) -> StatefulSemanticModel:
        """
        Infer stateful semantics and a bounded VM model from external traces.

        Unknown code is never executed.  UCR combines three evidence channels:
        parsed data-flow (when a line resembles an expression), observed state
        transitions, and observed control locations such as pc/ip/state/mode.
        This means jump/branch/loop instructions can still be reconstructed even
        when their syntax is completely unknown to the reader.

        Trace steps may contain ``before``/``after`` plus optional ``pc``,
        ``next_pc``, ``opcode``/``symbol``, ``reads`` and ``instruction`` fields.
        Nested dictionaries/lists in state snapshots are treated as candidate
        register banks, stacks or memory spaces and are diffed by leaf path.
        """
        obs_list = list(observations)
        unresolved: list[dict[str, Any]] = []
        transitions: list[StateTransition] = []
        semantic_observations: list[dict[str, Any]] = []
        control_counts: Counter[tuple[str, str]] = Counter()
        control_samples: list[dict[str, Any]] = []
        state_samples: list[dict[str, Any]] = []
        trace_sequences: list[list[str]] = []
        instruction_samples: list[dict[str, Any]] = []
        protocol_events: list[dict[str, Any]] = []

        default_code: str | None = None
        if program is not None:
            raw = program.encode("utf-8") if isinstance(program, str) else bytes(program)
            default_code, _, binary = self._decode_lossless(raw)
            if binary:
                default_code = None
                unresolved.append({
                    "reason": "binary-program-needs-external-decoder-or-trace-instructions",
                })

        all_program_forms: list[dict[str, Any]] = []

        for obs_index, obs in enumerate(obs_list):
            if not isinstance(obs, dict):
                unresolved.append({"observation": obs_index, "reason": "observation-not-a-mapping"})
                continue

            for event_key in ("events", "io_events", "messages", "protocol_events"):
                raw_events = obs.get(event_key)
                if isinstance(raw_events, list):
                    for event_index, raw_event in enumerate(raw_events):
                        if isinstance(raw_event, dict):
                            normalized = self._normalize_protocol_event(
                                raw_event, observation=obs_index, step=None, event_index=event_index
                            )
                            if normalized is not None:
                                protocol_events.append(normalized)

            trace = obs.get("trace")
            code = self._observation_code(obs, default_code)
            if code is None and isinstance(trace, list):
                # A trace can be sufficient to reconstruct a VM even when there
                # is no textual program.  Instruction strings are evidence only.
                parts = [
                    str(step.get("instruction"))
                    for step in trace
                    if isinstance(step, dict) and isinstance(step.get("instruction"), str)
                ]
                code = "\n".join(parts)
            if code is None:
                unresolved.append({"observation": obs_index, "reason": "missing-or-binary-code"})
                continue

            inputs = obs.get("inputs", {})
            if not self._valid_state_mapping(inputs):
                unresolved.append({"observation": obs_index, "reason": "invalid-input-state"})
                inputs = {}

            known_names = self._semantic_known_names(code, inputs)
            forms = self._extract_semantic_forms(code, inputs=known_names)
            if forms and not all_program_forms:
                all_program_forms = forms

            # Normalize either explicit trace entries or compact state snapshots.
            if trace is None and isinstance(obs.get("states"), list):
                states = obs["states"]
                if len(states) >= 2:
                    trace = []
                    for i in range(len(states) - 1):
                        item: dict[str, Any] = {"before": states[i], "after": states[i + 1]}
                        if i < len(forms):
                            item["line"] = forms[i].get("line")
                        trace.append(item)
                else:
                    unresolved.append({
                        "observation": obs_index,
                        "reason": "too-few-state-snapshots",
                    })

            if not isinstance(trace, list):
                # Final-output-only evidence can still feed bounded straight-line
                # composition below; it simply cannot reveal control flow.
                continue

            previous_control: str | None = None
            sequence: list[str] = []
            for step_index, step in enumerate(trace):
                if not isinstance(step, dict):
                    unresolved.append({"observation": obs_index, "step": step_index, "reason": "trace-step-not-a-mapping"})
                    continue
                before = step.get("before")
                after = step.get("after")
                if not self._valid_state_mapping(before) or not self._valid_state_mapping(after):
                    unresolved.append({"observation": obs_index, "step": step_index, "reason": "invalid-trace-state"})
                    continue

                state_samples.append({"observation": obs_index, "step": step_index, "before": before, "after": after})
                form = self._match_trace_form(step, forms, step_index)
                reads = self._form_read_names(form) if form else []
                explicit_reads = step.get("reads")
                if isinstance(explicit_reads, list):
                    for name in explicit_reads:
                        if isinstance(name, (str, int)) and str(name) not in reads:
                            reads.append(str(name))
                target = str(form.get("target")) if form and form.get("target") is not None else None
                symbol = str(form.get("symbol")) if form else self._trace_step_symbol(step)
                writes, deletes = self._state_delta_paths(before, after)
                side_effects = [k for k in writes if target is None or k != target]
                line = self._coerce_optional_int(step.get("line"))
                if line is None and form:
                    line = self._coerce_optional_int(form.get("line"))
                instruction = step.get("instruction")
                if not isinstance(instruction, str):
                    instruction = self._line_at(code, line) if line else None

                expected_target = target is not None and target in after
                target_changed = target in writes if target is not None else False
                confidence = 0.4
                if form is not None:
                    confidence += 0.18
                if symbol is not None:
                    confidence += 0.08
                if expected_target:
                    confidence += 0.15
                if target_changed:
                    confidence += 0.08
                if writes or deletes:
                    confidence += 0.06
                if self._trace_control_pair(step, before, after, form, step_index)[0] is not None:
                    confidence += 0.05
                confidence = round(min(1.0, confidence), 6)

                transitions.append(StateTransition(
                    observation=obs_index,
                    step=step_index,
                    line=line,
                    instruction=instruction,
                    symbol=symbol,
                    target=target,
                    reads=reads,
                    writes=writes,
                    deletes=deletes,
                    side_effect_writes=side_effects,
                    before_digest=self._state_digest(before),
                    after_digest=self._state_digest(after),
                    confidence=confidence,
                ))

                if form and target is not None and target in after:
                    snippet = instruction or self._line_at(code, form.get("line")) or code
                    semantic_observations.append({
                        "code": snippet,
                        "inputs": dict(before),
                        "outputs": {target: after[target]},
                    })

                source_control, destination_control = self._trace_control_pair(
                    step, before, after, form, step_index
                )
                safe_raw_step = {
                    key: value for key, value in step.items()
                    if key not in {"before", "after"}
                    and self._is_safe_semantic_value(value)
                }
                instruction_samples.append({
                    "observation": obs_index,
                    "step": step_index,
                    "symbol": symbol,
                    "instruction": instruction,
                    "before": before,
                    "after": after,
                    "writes": writes,
                    "deletes": deletes,
                    "reads": reads,
                    "from": source_control,
                    "to": destination_control,
                    "raw_step": safe_raw_step,
                })
                normalized_event = self._normalize_protocol_event(
                    safe_raw_step, observation=obs_index, step=step_index, event_index=None
                )
                if normalized_event is not None:
                    protocol_events.append(normalized_event)
                if source_control is not None:
                    sequence.append(source_control)
                if source_control is not None and destination_control is not None:
                    control_counts[(source_control, destination_control)] += 1
                    control_samples.append({
                        "observation": obs_index,
                        "step": step_index,
                        "from": source_control,
                        "to": destination_control,
                        "before": before,
                        "after": after,
                        "symbol": symbol,
                        "instruction": instruction,
                    })
                    previous_control = destination_control
                else:
                    current = self._trace_control_id(step, form, step_index)
                    if previous_control is not None:
                        control_counts[(previous_control, current)] += 1
                    previous_control = current
                    if not sequence or sequence[-1] != current:
                        sequence.append(current)

            if sequence:
                trace_sequences.append(sequence)

        local_model = self.infer_semantics(semantic_observations) if semantic_observations else SemanticModel(0)
        dependencies = self._infer_data_dependencies(all_program_forms)

        source_totals: Counter[str] = Counter()
        for (source, _), count in control_counts.items():
            source_totals[source] += count
        control_edges = [
            {
                "from": a,
                "to": b,
                "observations": count,
                "probability": round(count / max(1, source_totals[a]), 6),
            }
            for (a, b), count in sorted(control_counts.items())
        ]

        branch_hypotheses = self._infer_branch_hypotheses(control_samples)
        loop_hypotheses = self._infer_loop_hypotheses(control_edges, trace_sequences)
        memory_model = self._infer_memory_model(state_samples, transitions)
        isa_profile = self._infer_instruction_set(
            instruction_samples,
            memory_model=memory_model,
            branch_hypotheses=branch_hypotheses,
        )
        instruction_set = isa_profile.get("instructions", [])
        addressing_modes = isa_profile.get("addressing_modes", [])
        calling_convention = isa_profile.get("calling_convention", {})
        function_model = self._infer_function_model(
            instruction_samples,
            control_edges=control_edges,
            calling_convention=calling_convention,
            memory_model=memory_model,
        )
        abi_profile = self._infer_abi_profile(
            instruction_samples,
            function_model=function_model,
            calling_convention=calling_convention,
            memory_model=memory_model,
        )
        protocol_model = self._infer_protocol_model(protocol_events)
        emulator_model = self._build_behavioral_emulator_model(
            instruction_samples,
            memory_model=memory_model,
            instruction_set=instruction_set,
            addressing_modes=addressing_modes,
            calling_convention=calling_convention,
            branch_hypotheses=branch_hypotheses,
        )

        program_candidates: list[ProgramSemanticCandidate] = []
        if all_program_forms:
            program_candidates = self._infer_program_candidates(
                all_program_forms,
                obs_list,
                local_model=local_model,
                max_candidates=max_program_candidates,
                max_combinations=max_combinations,
            )

        vm_profile = self._build_vm_profile(
            transitions=transitions,
            control_edges=control_edges,
            branch_hypotheses=branch_hypotheses,
            loop_hypotheses=loop_hypotheses,
            memory_model=memory_model,
            instruction_set=instruction_set,
            addressing_modes=addressing_modes,
            calling_convention=calling_convention,
            function_model=function_model,
            abi_profile=abi_profile,
            protocol_model=protocol_model,
            emulator_model=emulator_model,
        )

        return StatefulSemanticModel(
            observation_count=len(obs_list),
            symbols=local_model.symbols,
            transitions=transitions,
            dependencies=dependencies,
            control_flow_edges=control_edges,
            branch_hypotheses=branch_hypotheses,
            loop_hypotheses=loop_hypotheses,
            memory_model=memory_model,
            instruction_set=instruction_set,
            addressing_modes=addressing_modes,
            calling_convention=calling_convention,
            function_model=function_model,
            abi_profile=abi_profile,
            protocol_model=protocol_model,
            emulator_model=emulator_model,
            vm_profile=vm_profile,
            program_candidates=program_candidates,
            unresolved=unresolved + local_model.unresolved,
            metadata={
                "reader_version": self.VERSION,
                "safe_mode": "read-only/no-execution",
                "method": "observed-state-control-memory-and-bounded-composition-induction",
                "semantic_status": "hypotheses-from-observed-state-not-proof",
                "trace_transition_count": len(transitions),
                "dependency_count": len(dependencies),
                "program_form_count": len(all_program_forms),
                "branch_hypothesis_count": len(branch_hypotheses),
                "loop_hypothesis_count": len(loop_hypotheses),
                "isa_instruction_count": len(instruction_set),
                "addressing_mode_count": len(addressing_modes),
                "call_return_model": bool(calling_convention.get("call_symbols") or calling_convention.get("return_symbols")),
                "function_count": int(function_model.get("function_count", 0) or 0),
                "completed_invocation_count": int(function_model.get("completed_invocation_count", 0) or 0),
                "abi_status": abi_profile.get("status"),
                "protocol_event_count": int(protocol_model.get("event_count", 0) or 0),
                "protocol_status": protocol_model.get("status"),
                "emulator_status": emulator_model.status,
                "emulator_rule_count": sum(len(v) for v in emulator_model.rules.values()),
                "emulator_executable_rule_count": int(emulator_model.metadata.get("executable_rule_count", 0) or 0),
                "candidate_search_limit": max_combinations,
            },
        )

    def read_with_state_observations(
        self,
        payload: bytes | bytearray | memoryview | str,
        observations: Iterable[dict[str, Any]],
        filename: str | None = None,
        *,
        language_hint: str | None = None,
        max_program_candidates: int = 16,
        max_combinations: int = 4096,
    ) -> tuple[ReadResult, StatefulSemanticModel]:
        """Read code and attach stateful chain-semantic evidence to AI-IR."""
        result = self.read(payload, filename=filename, language_hint=language_hint)
        obs_list = list(observations)
        model = self.infer_stateful_semantics(
            obs_list,
            program=payload,
            max_program_candidates=max_program_candidates,
            max_combinations=max_combinations,
        )

        transition_ids: list[str] = []
        for transition in model.transitions:
            tid = self._node_id(
                "state-transition",
                transition.observation,
                transition.step,
                transition.before_digest,
                transition.after_digest,
            )
            transition_ids.append(tid)
            result.nodes.append(IRNode(
                tid,
                "semantic.state_transition",
                transition.symbol,
                [],
                transition.to_dict(),
            ))

        dependency_ids: list[str] = []
        for dep in model.dependencies:
            did = self._node_id("data-dependency", dep)
            dependency_ids.append(did)
            result.nodes.append(IRNode(did, "semantic.data_dependency", dep.get("variable"), [], dep))

        candidate_ids: list[str] = []
        for rank, candidate in enumerate(model.program_candidates, 1):
            cid = self._node_id("program-semantic-candidate", rank, candidate.behavioral_digest)
            candidate_ids.append(cid)
            result.nodes.append(IRNode(
                cid,
                "semantic.program_candidate",
                candidate.mapping,
                [],
                {
                    "rank": rank,
                    "score": candidate.score,
                    "matched_checks": candidate.matched_checks,
                    "total_checks": candidate.total_checks,
                    "successful_runs": candidate.successful_runs,
                    "total_runs": candidate.total_runs,
                    "behavioral_digest": candidate.behavioral_digest,
                    **candidate.meta,
                },
            ))

        branch_ids: list[str] = []
        for branch in model.branch_hypotheses:
            bid = self._node_id("vm-branch", branch)
            branch_ids.append(bid)
            result.nodes.append(IRNode(bid, "semantic.control_branch", branch.get("source"), [], branch))

        loop_ids: list[str] = []
        for loop in model.loop_hypotheses:
            lid = self._node_id("vm-loop", loop)
            loop_ids.append(lid)
            result.nodes.append(IRNode(lid, "semantic.control_loop", loop.get("nodes"), [], loop))

        memory_id = self._node_id("vm-memory-model", model.memory_model)
        result.nodes.append(IRNode(memory_id, "semantic.memory_model", None, [], model.memory_model))

        isa_ids: list[str] = []
        for item in model.instruction_set:
            iid = self._node_id("isa-instruction", item.get("symbol"), item)
            isa_ids.append(iid)
            result.nodes.append(IRNode(iid, "semantic.isa_instruction", item.get("symbol"), [], item))

        addressing_ids: list[str] = []
        for mode in model.addressing_modes:
            aid = self._node_id("isa-addressing", mode)
            addressing_ids.append(aid)
            result.nodes.append(IRNode(aid, "semantic.addressing_mode", mode.get("mode"), [], mode))

        calling_id = self._node_id("isa-calling-convention", model.calling_convention)
        result.nodes.append(IRNode(
            calling_id,
            "semantic.calling_convention",
            None,
            [],
            model.calling_convention,
        ))

        function_id = self._node_id("function-model", model.function_model)
        result.nodes.append(IRNode(
            function_id,
            "semantic.function_model",
            None,
            [],
            model.function_model,
        ))
        abi_id = self._node_id("abi-profile", model.abi_profile)
        result.nodes.append(IRNode(abi_id, "semantic.abi_profile", None, [function_id, calling_id], model.abi_profile))
        protocol_id = self._node_id("protocol-model", model.protocol_model)
        result.nodes.append(IRNode(protocol_id, "semantic.protocol_model", None, [], model.protocol_model))
        emulator_payload = model.emulator_model.to_dict() if model.emulator_model is not None else {}
        emulator_id = self._node_id("behavioral-emulator-model", emulator_payload)
        result.nodes.append(IRNode(emulator_id, "semantic.behavioral_emulator", None, [], emulator_payload))

        vm_id = self._node_id("vm-profile", model.vm_profile)
        result.nodes.append(IRNode(
            vm_id,
            "semantic.vm_profile",
            None,
            branch_ids + loop_ids + [memory_id] + isa_ids + addressing_ids + [calling_id, function_id, abi_id, protocol_id, emulator_id],
            model.vm_profile,
        ))

        root_id = self._node_id("stateful-semantic-root", result.sha256, len(obs_list))
        result.nodes.append(IRNode(
            root_id,
            "semantic.stateful_model",
            None,
            transition_ids + dependency_ids + candidate_ids + branch_ids + loop_ids + [memory_id] + isa_ids + addressing_ids + [calling_id, function_id, abi_id, protocol_id, emulator_id, vm_id],
            {
                "observation_count": model.observation_count,
                "transition_count": len(model.transitions),
                "dependency_count": len(model.dependencies),
                "control_flow_edge_count": len(model.control_flow_edges),
                "branch_hypothesis_count": len(model.branch_hypotheses),
                "loop_hypothesis_count": len(model.loop_hypotheses),
                "isa_instruction_count": len(model.instruction_set),
                "addressing_mode_count": len(model.addressing_modes),
                "function_count": int(model.function_model.get("function_count", 0) or 0),
                "completed_invocation_count": int(model.function_model.get("completed_invocation_count", 0) or 0),
                "protocol_event_count": int(model.protocol_model.get("event_count", 0) or 0),
                "emulator_status": model.emulator_model.status if model.emulator_model is not None else "unavailable",
                "emulator_rule_count": sum(len(v) for v in model.emulator_model.rules.values()) if model.emulator_model is not None else 0,
                "program_candidate_count": len(model.program_candidates),
                "control_flow_edges": model.control_flow_edges,
                "semantic_status": model.metadata.get("semantic_status"),
            },
        ))
        result.metadata["stateful_semantics"] = {
            "transition_count": len(model.transitions),
            "dependency_count": len(model.dependencies),
            "control_flow_edge_count": len(model.control_flow_edges),
            "branch_hypothesis_count": len(model.branch_hypotheses),
            "loop_hypothesis_count": len(model.loop_hypotheses),
            "isa_instruction_count": len(model.instruction_set),
            "addressing_mode_count": len(model.addressing_modes),
            "call_symbol_count": len(model.calling_convention.get("call_symbols", [])),
            "return_symbol_count": len(model.calling_convention.get("return_symbols", [])),
            "function_count": int(model.function_model.get("function_count", 0) or 0),
            "completed_invocation_count": int(model.function_model.get("completed_invocation_count", 0) or 0),
            "abi_status": model.abi_profile.get("status"),
            "protocol_event_count": int(model.protocol_model.get("event_count", 0) or 0),
            "protocol_status": model.protocol_model.get("status"),
            "emulator_status": model.emulator_model.status if model.emulator_model is not None else "unavailable",
            "emulator_executable_rule_count": int(model.emulator_model.metadata.get("executable_rule_count", 0) or 0) if model.emulator_model is not None else 0,
            "program_candidate_count": len(model.program_candidates),
            "best_program_score": model.program_candidates[0].score if model.program_candidates else None,
            "semantic_status": model.metadata.get("semantic_status"),
        }
        result.metadata["vm_profile"] = model.vm_profile
        result.metadata["function_model"] = model.function_model
        result.metadata["abi_profile"] = model.abi_profile
        result.metadata["protocol_model"] = model.protocol_model
        result.metadata["emulator_model"] = model.emulator_model.to_dict() if model.emulator_model is not None else None
        result.metadata["node_count"] = len(result.nodes)
        return result, model

    @staticmethod
    def _coerce_optional_int(value: Any) -> int | None:
        if type(value) is int:
            return value
        if isinstance(value, str) and value.strip().isdigit():
            return int(value.strip())
        return None

    def _observation_code(self, obs: dict[str, Any], default_code: str | None) -> str | None:
        value = obs.get("code", default_code)
        if isinstance(value, str):
            return value
        if isinstance(value, (bytes, bytearray, memoryview)):
            text, _, binary = self._decode_lossless(bytes(value))
            return None if binary else text
        return None

    def _valid_state_mapping(self, value: Any) -> bool:
        return isinstance(value, dict) and all(
            isinstance(k, str) and self._is_safe_semantic_value(v)
            for k, v in value.items()
        )

    def _semantic_known_names(self, code: str, inputs: dict[str, Any]) -> dict[str, Any]:
        names = dict(inputs)
        for raw_line in code.splitlines():
            tokens = [
                t for t in self._tokenize(raw_line)
                if t["kind"] not in {"line_comment", "block_comment", "directive"}
            ]
            for i, tok in enumerate(tokens):
                if str(tok["value"]) in self.ASSIGN_SYMBOLS and i > 0 and tokens[i - 1]["kind"] == "identifier":
                    names.setdefault(str(tokens[i - 1]["value"]), None)
                    break
        return names

    @staticmethod
    def _line_at(code: str, line: Any) -> str | None:
        if type(line) is not int or line < 1:
            return None
        lines = code.splitlines()
        return lines[line - 1].strip() if line <= len(lines) else None

    def _match_trace_form(
        self,
        step: dict[str, Any],
        forms: list[dict[str, Any]],
        step_index: int,
    ) -> dict[str, Any] | None:
        line = self._coerce_optional_int(step.get("line"))
        if line is not None:
            for form in forms:
                if form.get("line") == line:
                    return form
        instruction = step.get("instruction")
        if isinstance(instruction, str):
            before = step.get("before") if isinstance(step.get("before"), dict) else {}
            known = self._semantic_known_names(instruction, before)
            parsed = self._extract_semantic_forms(instruction, inputs=known)
            if parsed:
                return parsed[0]
        if 0 <= step_index < len(forms):
            return forms[step_index]
        return None

    @staticmethod
    def _form_read_names(form: dict[str, Any] | None) -> list[str]:
        if not form:
            return []
        names: list[str] = []
        for tok in form.get("operands", []):
            if tok.get("kind") == "identifier":
                value = str(tok.get("value"))
                if value not in names:
                    names.append(value)
        return names

    def _state_delta(self, before: dict[str, Any], after: dict[str, Any]) -> tuple[list[str], list[str]]:
        writes: list[str] = []
        for key in sorted(after):
            if key not in before or not self._semantic_equal(before[key], after[key]):
                writes.append(key)
        deletes = [key for key in sorted(before) if key not in after]
        return writes, deletes

    def _state_digest(self, state: dict[str, Any]) -> str:
        canonical = {
            key: self._canonical_semantic_value(value)
            for key, value in sorted(state.items())
        }
        material = json.dumps(canonical, ensure_ascii=False, sort_keys=True, separators=(",", ":"), default=str)
        return hashlib.sha256(material.encode("utf-8")).hexdigest()

    @staticmethod
    def _trace_control_id(step: dict[str, Any], form: dict[str, Any] | None, step_index: int) -> str:
        for key in ("pc", "ip", "instruction_pointer", "state", "mode"):
            if key in step and type(step[key]) in (str, int):
                return f"{key}:{step[key]}"
        if form and form.get("line") is not None:
            return f"line:{form['line']}"
        return f"step:{step_index}"

    @staticmethod
    def _trace_step_symbol(step: dict[str, Any]) -> str | None:
        for key in ("symbol", "opcode", "op", "mnemonic", "instruction_id"):
            value = step.get(key)
            if type(value) in (str, int):
                return str(value)
        instruction = step.get("instruction")
        if isinstance(instruction, str):
            stripped = instruction.strip()
            if stripped:
                match = re.match(r"([^\s,;:\[\](){}]+)", stripped)
                if match:
                    return match.group(1)
        return None

    @staticmethod
    def _control_value(mapping: dict[str, Any], keys: tuple[str, ...]) -> tuple[str, Any] | None:
        for key in keys:
            value = mapping.get(key)
            if type(value) in (str, int):
                return key, value
        return None

    def _trace_control_pair(
        self,
        step: dict[str, Any],
        before: dict[str, Any],
        after: dict[str, Any],
        form: dict[str, Any] | None,
        step_index: int,
    ) -> tuple[str | None, str | None]:
        source = self._control_value(step, ("pc", "ip", "instruction_pointer", "from_pc", "address", "state", "mode"))
        if source is None:
            source = self._control_value(before, ("pc", "ip", "instruction_pointer", "address", "state", "mode"))

        destination = self._control_value(step, ("next_pc", "to_pc", "next_ip", "target_pc", "next_state", "to_state"))
        if destination is None:
            destination = self._control_value(after, ("pc", "ip", "instruction_pointer", "address", "state", "mode"))

        if source is None and form and form.get("line") is not None:
            source = ("line", form.get("line"))
        if source is None:
            line = self._coerce_optional_int(step.get("line"))
            if line is not None:
                source = ("line", line)

        def normalize(item: tuple[str, Any] | None, *, fallback_kind: str | None = None) -> str | None:
            if item is None:
                return None
            key, value = item
            canonical_key = key
            if key in {"from_pc", "next_pc", "to_pc", "target_pc"}:
                canonical_key = "pc"
            elif key in {"next_ip", "to_ip"}:
                canonical_key = "ip"
            elif key in {"next_state", "to_state"}:
                canonical_key = "state"
            elif key == "address" and fallback_kind:
                canonical_key = fallback_kind
            return f"{canonical_key}:{value}"

        source_id = normalize(source)
        source_kind = source[0] if source else None
        destination_id = normalize(destination, fallback_kind=source_kind)
        return source_id, destination_id

    @classmethod
    def _flatten_state_leaves(cls, value: Any, prefix: str = "") -> dict[str, Any]:
        out: dict[str, Any] = {}
        if type(value) is dict:
            if not value and prefix:
                out[prefix] = {}
            for key, child in value.items():
                key_text = str(key)
                path = f"{prefix}.{key_text}" if prefix else key_text
                out.update(cls._flatten_state_leaves(child, path))
            return out
        if type(value) in (list, tuple):
            if not value and prefix:
                out[prefix] = [] if type(value) is list else ()
            for index, child in enumerate(value):
                path = f"{prefix}[{index}]" if prefix else f"[{index}]"
                out.update(cls._flatten_state_leaves(child, path))
            return out
        if prefix:
            out[prefix] = value
        return out

    def _state_delta_paths(self, before: dict[str, Any], after: dict[str, Any]) -> tuple[list[str], list[str]]:
        flat_before = self._flatten_state_leaves(before)
        flat_after = self._flatten_state_leaves(after)
        writes = [
            key for key in sorted(flat_after)
            if key not in flat_before or not self._semantic_equal(flat_before[key], flat_after[key])
        ]
        deletes = [key for key in sorted(flat_before) if key not in flat_after]
        return writes, deletes

    @staticmethod
    def _is_control_path(path: str) -> bool:
        root = path.split(".", 1)[0].split("[", 1)[0].lower()
        return root in {"pc", "ip", "instruction_pointer", "address", "state", "mode"}

    def _infer_branch_hypotheses(self, samples: list[dict[str, Any]]) -> list[dict[str, Any]]:
        by_source: dict[str, list[dict[str, Any]]] = defaultdict(list)
        for sample in samples:
            if isinstance(sample.get("from"), str) and isinstance(sample.get("to"), str):
                by_source[sample["from"]].append(sample)

        hypotheses: list[dict[str, Any]] = []
        for source, group in sorted(by_source.items()):
            destinations = sorted({str(x["to"]) for x in group})
            if len(destinations) < 2:
                continue

            flattened = [self._flatten_state_leaves(x.get("before", {})) for x in group]
            common = set(flattened[0]) if flattened else set()
            for state in flattened[1:]:
                common.intersection_update(state)
            common = {k for k in common if not self._is_control_path(k)}

            predicates: list[tuple[str, Callable[[dict[str, Any]], bool | None]]] = []
            for path in sorted(common)[:32]:
                values = [state.get(path) for state in flattened]
                if all(type(v) is bool for v in values):
                    predicates.append((f"{path} is true", lambda st, p=path: bool(st[p]) if p in st and type(st[p]) is bool else None))
                if all(type(v) in (int, float) and type(v) is not bool for v in values):
                    predicates.extend([
                        (f"{path} == 0", lambda st, p=path: st[p] == 0 if p in st and type(st[p]) in (int, float) and type(st[p]) is not bool else None),
                        (f"{path} > 0", lambda st, p=path: st[p] > 0 if p in st and type(st[p]) in (int, float) and type(st[p]) is not bool else None),
                        (f"{path} < 0", lambda st, p=path: st[p] < 0 if p in st and type(st[p]) in (int, float) and type(st[p]) is not bool else None),
                    ])
                if all(type(v) in (str, bytes, list, tuple, dict) for v in values):
                    predicates.append((f"len({path}) == 0", lambda st, p=path: len(st[p]) == 0 if p in st and type(st[p]) in (str, bytes, list, tuple, dict) else None))

            numeric_paths = [
                p for p in sorted(common)[:16]
                if all(type(st.get(p)) in (int, float) and type(st.get(p)) is not bool for st in flattened)
            ]
            for left_index in range(len(numeric_paths)):
                for right_index in range(left_index + 1, min(len(numeric_paths), left_index + 6)):
                    a, b = numeric_paths[left_index], numeric_paths[right_index]
                    predicates.extend([
                        (f"{a} == {b}", lambda st, x=a, y=b: st[x] == st[y] if x in st and y in st else None),
                        (f"{a} < {b}", lambda st, x=a, y=b: st[x] < st[y] if x in st and y in st else None),
                        (f"{a} > {b}", lambda st, x=a, y=b: st[x] > st[y] if x in st and y in st else None),
                    ])

            ranked: list[dict[str, Any]] = []
            for label, predicate in predicates[:256]:
                rows: list[tuple[bool, str]] = []
                for state, sample in zip(flattened, group):
                    try:
                        outcome = predicate(state)
                    except Exception:
                        outcome = None
                    if type(outcome) is bool:
                        rows.append((outcome, str(sample["to"])))
                if len(rows) < 2 or len({outcome for outcome, _ in rows}) < 2:
                    continue
                mapping: dict[bool, str] = {}
                correct = 0
                for outcome in (False, True):
                    counts = Counter(dest for flag, dest in rows if flag is outcome)
                    if counts:
                        mapping[outcome] = counts.most_common(1)[0][0]
                for outcome, dest in rows:
                    if mapping.get(outcome) == dest:
                        correct += 1
                accuracy = correct / len(rows)
                ranked.append({
                    "predicate": label,
                    "accuracy": round(accuracy, 6),
                    "samples": len(rows),
                    "true_target": mapping.get(True),
                    "false_target": mapping.get(False),
                })

            ranked.sort(key=lambda x: (x["accuracy"], x["samples"], x["predicate"]), reverse=True)
            best = ranked[:5]
            symbol_counts = Counter(str(x.get("symbol")) for x in group if x.get("symbol") is not None)
            confidence = 0.0
            if best:
                confidence = best[0]["accuracy"] * min(1.0, 0.35 + 0.12 * len(group))
            hypotheses.append({
                "source": source,
                "destinations": destinations,
                "observations": len(group),
                "instruction_symbols": [name for name, _ in symbol_counts.most_common(4)],
                "status": "supported-hypothesis" if best and best[0]["accuracy"] >= 0.95 and len(group) >= 4 else "tentative",
                "confidence": round(confidence, 6),
                "candidate_conditions": best,
            })
        return hypotheses

    def _infer_loop_hypotheses(
        self,
        control_edges: list[dict[str, Any]],
        trace_sequences: list[list[str]],
    ) -> list[dict[str, Any]]:
        adjacency: dict[str, set[str]] = defaultdict(set)
        nodes: set[str] = set()
        edge_count: dict[tuple[str, str], int] = {}
        for edge in control_edges:
            source, target = edge.get("from"), edge.get("to")
            if isinstance(source, str) and isinstance(target, str):
                adjacency[source].add(target)
                nodes.update((source, target))
                edge_count[(source, target)] = int(edge.get("observations", 0) or 0)

        index = 0
        stack: list[str] = []
        on_stack: set[str] = set()
        indices: dict[str, int] = {}
        lowlink: dict[str, int] = {}
        components: list[list[str]] = []

        def strongconnect(node: str) -> None:
            nonlocal index
            indices[node] = index
            lowlink[node] = index
            index += 1
            stack.append(node)
            on_stack.add(node)
            for nxt in adjacency.get(node, set()):
                if nxt not in indices:
                    strongconnect(nxt)
                    lowlink[node] = min(lowlink[node], lowlink[nxt])
                elif nxt in on_stack:
                    lowlink[node] = min(lowlink[node], indices[nxt])
            if lowlink[node] == indices[node]:
                component: list[str] = []
                while stack:
                    item = stack.pop()
                    on_stack.remove(item)
                    component.append(item)
                    if item == node:
                        break
                components.append(sorted(component))

        for node in sorted(nodes):
            if node not in indices:
                strongconnect(node)

        loops: list[dict[str, Any]] = []
        for component in components:
            internal_edges = [
                (a, b, count)
                for (a, b), count in edge_count.items()
                if a in component and b in component
            ]
            cyclic = len(component) > 1 or any(a == b for a, b, _ in internal_edges)
            if not cyclic:
                continue
            entries = sorted({
                b for (a, b), _count in edge_count.items()
                if a not in component and b in component
            })
            exits = sorted({
                b for (a, b), _count in edge_count.items()
                if a in component and b not in component
            })
            visits: list[int] = []
            for sequence in trace_sequences:
                count = sum(1 for item in sequence if item in component)
                if count:
                    visits.append(count)
            evidence = sum(count for _, _, count in internal_edges)
            loops.append({
                "nodes": component,
                "entry_nodes": entries,
                "exit_nodes": exits,
                "internal_edges": [
                    {"from": a, "to": b, "observations": count}
                    for a, b, count in sorted(internal_edges)
                ],
                "observations": evidence,
                "trace_visit_counts": visits[:64],
                "status": "observed-cycle",
            })
        loops.sort(key=lambda item: (item["observations"], len(item["nodes"])), reverse=True)
        return loops

    def _infer_memory_model(
        self,
        state_samples: list[dict[str, Any]],
        transitions: list[StateTransition],
    ) -> dict[str, Any]:
        root_shapes: dict[str, Counter[str]] = defaultdict(Counter)
        scalar_roots: Counter[str] = Counter()
        observed_roots: Counter[str] = Counter()
        changed_paths: Counter[str] = Counter()
        deleted_paths: Counter[str] = Counter()

        for sample in state_samples:
            for state_name in ("before", "after"):
                state = sample.get(state_name)
                if not isinstance(state, dict):
                    continue
                for key, value in state.items():
                    root = str(key)
                    observed_roots[root] += 1
                    if type(value) is dict:
                        root_shapes[root]["mapping"] += 1
                    elif type(value) is list:
                        root_shapes[root]["list"] += 1
                    elif type(value) is tuple:
                        root_shapes[root]["tuple"] += 1
                    else:
                        root_shapes[root]["scalar"] += 1
                        scalar_roots[root] += 1
        for transition in transitions:
            changed_paths.update(transition.writes)
            deleted_paths.update(transition.deletes)

        spaces: list[dict[str, Any]] = []
        control_registers: list[str] = []
        registers: list[str] = []
        for root in sorted(observed_roots):
            lower = root.lower()
            shapes = root_shapes[root]
            dominant = shapes.most_common(1)[0][0] if shapes else "unknown"
            if lower in {"pc", "ip", "instruction_pointer"}:
                control_registers.append(root)
                continue
            if dominant == "scalar":
                registers.append(root)
                continue
            role = "structured-state"
            if "stack" in lower:
                role = "stack"
            elif lower in {"mem", "memory", "ram"} or "memory" in lower:
                role = "linear-memory" if dominant in {"list", "tuple"} else "addressed-memory"
            elif "heap" in lower:
                role = "heap"
            elif "reg" in lower:
                role = "register-bank"
            paths = [
                {"path": path, "writes": count}
                for path, count in changed_paths.most_common()
                if path == root or path.startswith(root + ".") or path.startswith(root + "[")
            ][:64]
            spaces.append({
                "name": root,
                "role_hypothesis": role,
                "shape": dominant,
                "observations": observed_roots[root],
                "changed_locations": paths,
            })

        memory_writes = [
            {"path": path, "count": count}
            for path, count in changed_paths.most_common(128)
            if any(token in path.lower() for token in ("mem", "heap", "stack", "ram"))
        ]
        register_writes = [
            {"path": path, "count": count}
            for path, count in changed_paths.most_common(128)
            if path.split(".", 1)[0].split("[", 1)[0] in registers
            or "reg" in path.lower()
        ]

        return {
            "status": "observed-layout-hypothesis" if state_samples else "no-state-evidence",
            "control_registers": control_registers,
            "scalar_registers": registers[:128],
            "address_spaces": spaces,
            "frequent_memory_writes": memory_writes[:64],
            "frequent_register_writes": register_writes[:64],
            "deleted_locations": [
                {"path": path, "count": count} for path, count in deleted_paths.most_common(64)
            ],
            "state_samples": len(state_samples),
        }


    @staticmethod
    def _path_root(path: str) -> str:
        return path.split(".", 1)[0].split("[", 1)[0]

    @staticmethod
    def _path_numeric_address(path: str) -> int | None:
        match = re.search(r"\[(-?(?:0[xX][0-9A-Fa-f]+|\d+))\]$", path)
        if match is None:
            match = re.search(r"\.(-?(?:0[xX][0-9A-Fa-f]+|\d+))$", path)
        if match is None:
            return None
        try:
            return int(match.group(1), 0)
        except ValueError:
            return None

    @staticmethod
    def _control_numeric(control_id: str | None) -> int | None:
        if not isinstance(control_id, str) or ":" not in control_id:
            return None
        value = control_id.split(":", 1)[1].strip()
        try:
            return int(value, 0)
        except ValueError:
            return None

    @staticmethod
    def _control_payload(control_id: str | None) -> Any:
        if not isinstance(control_id, str) or ":" not in control_id:
            return None
        value = control_id.split(":", 1)[1]
        try:
            return int(value, 0)
        except ValueError:
            return value

    @classmethod
    def _state_path_is_control(cls, path: str) -> bool:
        return cls._is_control_path(path)

    def _infer_instruction_set(
        self,
        samples: list[dict[str, Any]],
        *,
        memory_model: dict[str, Any],
        branch_hypotheses: list[dict[str, Any]],
    ) -> dict[str, Any]:
        """
        Infer bounded ISA roles from externally supplied traces.

        The inference is deliberately behavioral: opcode spelling is never used
        to decide that an instruction is LOAD/STORE/CALL/RET.  Roles are derived
        from state deltas, value provenance, stack shape and observed control
        transfers.  These are hypotheses, not a disassembler and not proof of
        the hidden machine's specification.
        """
        memory_roots: set[str] = set()
        stack_roots: set[str] = set()
        register_roots: set[str] = set(memory_model.get("scalar_registers", []))
        for space in memory_model.get("address_spaces", []):
            if not isinstance(space, dict) or not isinstance(space.get("name"), str):
                continue
            name = space["name"]
            role = str(space.get("role_hypothesis", ""))
            if role in {"linear-memory", "addressed-memory", "heap"}:
                memory_roots.add(name)
            elif role == "stack":
                stack_roots.add(name)
            elif role == "register-bank":
                register_roots.add(name)

        # Include conventional-looking structured roots only as layout evidence;
        # opcode names are still ignored for semantic classification.
        for sample in samples:
            before = sample.get("before", {})
            if not isinstance(before, dict):
                continue
            for root, value in before.items():
                low = str(root).lower()
                if type(value) in (list, tuple) and "stack" in low:
                    stack_roots.add(str(root))
                if type(value) in (list, tuple, dict) and any(x in low for x in ("mem", "ram", "heap")):
                    memory_roots.add(str(root))
                if type(value) is dict and "reg" in low:
                    register_roots.add(str(root))

        delta_counts: Counter[int] = Counter()
        for sample in samples:
            src = self._control_numeric(sample.get("from"))
            dst = self._control_numeric(sample.get("to"))
            if src is not None and dst is not None and src != dst:
                delta = dst - src
                # Small positive deltas are the most plausible observed
                # fall-through widths. Large jumps remain control evidence.
                if 0 < delta <= 32:
                    delta_counts[delta] += 1
        fallthrough_delta = delta_counts.most_common(1)[0][0] if delta_counts else None
        fallthrough_evidence = delta_counts.get(fallthrough_delta, 0) if fallthrough_delta is not None else 0

        grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
        for sample in samples:
            symbol = sample.get("symbol")
            if symbol is not None:
                grouped[str(symbol)].append(sample)

        # Addressing inference is accumulated as per-access observations rather
        # than one-off coincidences.  A numeric register is not accepted as an
        # address source merely because `address - register` happens to be a
        # small constant in one trace.
        addressing_observations: dict[str, list[dict[str, Any]]] = defaultdict(list)
        direct_address_evidence: Counter[tuple[str, int]] = Counter()
        call_stack_evidence: Counter[str] = Counter()
        call_symbols: set[str] = set()
        return_symbols: set[str] = set()
        return_rule_evidence = 0
        instructions: list[dict[str, Any]] = []

        for symbol, group in sorted(grouped.items()):
            counts: Counter[str] = Counter()
            details: dict[str, list[dict[str, Any]]] = defaultdict(list)
            destinations: Counter[str] = Counter()
            total = len(group)

            for sample in group:
                before = sample.get("before", {})
                after = sample.get("after", {})
                if not isinstance(before, dict) or not isinstance(after, dict):
                    continue
                flat_before = self._flatten_state_leaves(before)
                flat_after = self._flatten_state_leaves(after)
                writes = [str(x) for x in sample.get("writes", []) if isinstance(x, str)]
                source_control = sample.get("from")
                dest_control = sample.get("to")
                if isinstance(dest_control, str):
                    destinations[dest_control] += 1

                src_num = self._control_numeric(source_control)
                dst_num = self._control_numeric(dest_control)
                dst_payload = self._control_payload(dest_control)
                raw_step = sample.get("raw_step", {}) if isinstance(sample.get("raw_step"), dict) else {}
                is_fallthrough = (
                    fallthrough_delta is not None
                    and src_num is not None
                    and dst_num is not None
                    and dst_num - src_num == fallthrough_delta
                )
                non_fallthrough = (
                    src_num is not None and dst_num is not None
                    and fallthrough_delta is not None and not is_fallthrough
                )

                memory_writes = [p for p in writes if self._path_root(p) in memory_roots]
                non_memory_writes = [
                    p for p in writes
                    if self._path_root(p) not in memory_roots
                    and self._path_root(p) not in stack_roots
                    and not self._state_path_is_control(p)
                ]

                memory_reads_this_step: set[str] = set()
                for dest_path in non_memory_writes:
                    if dest_path not in flat_after:
                        continue
                    value = flat_after[dest_path]
                    matches = [
                        path for path, candidate in flat_before.items()
                        if self._path_root(path) in memory_roots
                        and self._semantic_equal(value, candidate)
                    ]
                    if matches:
                        counts["memory.load"] += 1
                        chosen = matches[0]
                        memory_reads_this_step.add(chosen)
                        details["memory.load"].append({"destination": dest_path, "source": chosen})

                for mem_path in memory_writes:
                    if mem_path not in flat_after:
                        continue
                    value = flat_after[mem_path]
                    matches = [
                        path for path, candidate in flat_before.items()
                        if self._path_root(path) not in memory_roots
                        and self._path_root(path) not in stack_roots
                        and not self._state_path_is_control(path)
                        and self._semantic_equal(value, candidate)
                    ]
                    if matches:
                        counts["memory.store"] += 1
                        details["memory.store"].append({"destination": mem_path, "source": matches[0]})

                accessed_memory = set(memory_writes) | memory_reads_this_step
                for mem_path in accessed_memory:
                    address = self._path_numeric_address(mem_path)
                    root = self._path_root(mem_path)
                    if address is None:
                        continue

                    # Record every concrete address.  Later we decide whether
                    # the trace supports register-indirect/base+offset or only
                    # an absolute-address observation.
                    direct_address_evidence[(root, address)] += 1
                    candidates: dict[str, int] = {}
                    for path, value in flat_before.items():
                        path_root = self._path_root(path)
                        if path_root in memory_roots | stack_roots:
                            continue
                        if self._state_path_is_control(path):
                            continue
                        # Restrict address-source candidates to state already
                        # identified as a register/register-bank.  Arbitrary
                        # integer data values are too easy to correlate by
                        # accident.
                        if path_root not in register_roots:
                            continue
                        if type(value) is int and type(value) is not bool:
                            candidates[path] = value
                    addressing_observations[root].append({
                        "address": address,
                        "candidates": candidates,
                        "symbol": symbol,
                        "source": source_control,
                    })

                for root in stack_roots:
                    bstack = before.get(root)
                    astack = after.get(root)
                    if type(bstack) not in (list, tuple) or type(astack) not in (list, tuple):
                        continue
                    if len(astack) == len(bstack) + 1 and list(astack[:-1]) == list(bstack):
                        pushed = astack[-1]
                        counts["stack.push"] += 1
                        details["stack.push"].append({"stack": root, "value": pushed})
                        call_rule: str | None = None
                        if non_fallthrough and src_num is not None and fallthrough_delta is not None:
                            expected_return = src_num + fallthrough_delta
                            if self._semantic_equal(pushed, expected_return):
                                call_rule = f"source+{fallthrough_delta}"
                        explicit_return = raw_step.get("return_address")
                        if explicit_return is not None and self._is_safe_semantic_value(explicit_return):
                            if self._semantic_equal(pushed, explicit_return):
                                call_rule = "trace.return_address"
                        if call_rule is not None:
                            counts["control.call"] += 1
                            call_symbols.add(symbol)
                            call_stack_evidence[root] += 1
                            return_rule_evidence += 1
                            details["control.call"].append({
                                "stack": root,
                                "pushed_return": pushed,
                                "target": dest_control,
                                "return_rule": call_rule,
                            })
                    elif len(bstack) == len(astack) + 1 and list(bstack[:-1]) == list(astack):
                        popped = bstack[-1]
                        counts["stack.pop"] += 1
                        details["stack.pop"].append({"stack": root, "value": popped})
                        if dst_payload is not None and self._semantic_equal(popped, dst_payload):
                            counts["control.return"] += 1
                            return_symbols.add(symbol)
                            call_stack_evidence[root] += 1
                            details["control.return"].append({"stack": root, "return_target": dest_control})

                if non_fallthrough and dst_num is not None:
                    candidate_paths = [
                        path for path, value in flat_before.items()
                        if not self._state_path_is_control(path)
                        and self._path_root(path) not in memory_roots | stack_roots
                        and type(value) is int and type(value) is not bool
                        and value == dst_num
                    ]
                    if candidate_paths:
                        counts["control.jump.indirect"] += 1
                        details["control.jump.indirect"].append({
                            "target_source": candidate_paths[0],
                            "target": dest_control,
                        })
                    else:
                        counts["control.jump.direct"] += 1
                        details["control.jump.direct"].append({"target": dest_control})

            # A symbol is a branch only when the *same control source* has
            # actually been observed reaching multiple destinations.  The same
            # opcode appearing at different addresses with ordinary fallthrough
            # targets is not branch evidence.
            by_source_destinations: dict[str, Counter[str]] = defaultdict(Counter)
            for sample in group:
                src = sample.get("from")
                dst = sample.get("to")
                if isinstance(src, str) and isinstance(dst, str):
                    by_source_destinations[src][dst] += 1
            branch_points = [
                (src, dests) for src, dests in by_source_destinations.items()
                if len(dests) >= 2
            ]
            if branch_points:
                branch_evidence = sum(sum(dests.values()) for _src, dests in branch_points)
                counts["control.branch"] = max(counts["control.branch"], branch_evidence)
                details["control.branch"].append({
                    "branch_points": [
                        {
                            "source": src,
                            "destinations": [
                                {"target": target, "observations": count}
                                for target, count in dests.most_common(16)
                            ],
                        }
                        for src, dests in sorted(branch_points)
                    ]
                })

            hypotheses: list[dict[str, Any]] = []
            for kind, evidence_count in counts.most_common():
                if evidence_count <= 0:
                    continue
                confidence = min(1.0, evidence_count / max(1, total))
                # CALL/RET have compound evidence (stack + control transfer) and
                # are intentionally slightly stronger than a value coincidence.
                if kind in {"control.call", "control.return"}:
                    confidence = min(1.0, 0.2 + confidence)
                hypotheses.append({
                    "kind": kind,
                    "confidence": round(confidence, 6),
                    "evidence": evidence_count,
                    "observations": total,
                    "examples": details[kind][:8],
                    "status": "trace-derived-hypothesis",
                })

            role_priority = {
                "control.call": 100,
                "control.return": 100,
                "memory.load": 90,
                "memory.store": 90,
                "control.branch": 85,
                "control.jump.indirect": 80,
                "control.jump.direct": 75,
                "stack.push": 60,
                "stack.pop": 60,
            }
            primary = None
            if hypotheses:
                primary = max(
                    hypotheses,
                    key=lambda h: (role_priority.get(str(h.get("kind")), 0), h.get("confidence", 0.0)),
                ).get("kind")

            instructions.append({
                "symbol": symbol,
                "observations": total,
                "primary_role": primary,
                "destinations": [
                    {"target": target, "observations": count}
                    for target, count in destinations.most_common(16)
                ],
                "hypotheses": hypotheses,
                "semantic_status": "behavioral-hypothesis-not-proof",
            })

        addressing_modes: list[dict[str, Any]] = []
        validated_memory_roots: set[str] = set()

        for memory_root, observations in sorted(addressing_observations.items()):
            # Evaluate each register path across *all* relevant accesses.  A
            # usable base register needs repeated, stable evidence and actual
            # variation; a single lucky arithmetic coincidence is insufficient.
            path_offsets: dict[str, Counter[int]] = defaultdict(Counter)
            path_values: dict[str, set[int]] = defaultdict(set)
            path_addresses: dict[str, set[int]] = defaultdict(set)
            path_opportunities: Counter[str] = Counter()

            for obs in observations:
                address = obs.get("address")
                candidates = obs.get("candidates", {})
                if type(address) is not int or not isinstance(candidates, dict):
                    continue
                for source_path, value in candidates.items():
                    if type(value) is not int or type(value) is bool:
                        continue
                    offset = address - value
                    path_opportunities[source_path] += 1
                    path_values[source_path].add(value)
                    path_addresses[source_path].add(address)
                    if abs(offset) <= 4096:
                        path_offsets[source_path][offset] += 1

            candidates_ranked: list[dict[str, Any]] = []
            for source_path, offsets in path_offsets.items():
                if not offsets:
                    continue
                offset, evidence = offsets.most_common(1)[0]
                opportunities = path_opportunities[source_path]
                support = evidence / max(1, opportunities)
                varied = min(len(path_values[source_path]), len(path_addresses[source_path]))
                if evidence < 2 or opportunities < 2 or support < 0.8 or varied < 2:
                    continue
                # Prefer the simplest equally-supported explanation (direct
                # register-indirect before base+offset) but keep confidence
                # evidence-based and below certainty when alternatives compete.
                simplicity = 1 if offset == 0 else 0
                candidates_ranked.append({
                    "source_path": source_path,
                    "offset": offset,
                    "evidence": evidence,
                    "opportunities": opportunities,
                    "support": support,
                    "varied": varied,
                    "simplicity": simplicity,
                })

            candidates_ranked.sort(
                key=lambda c: (
                    c["support"], c["evidence"], c["varied"], c["simplicity"],
                    -abs(c["offset"]), c["source_path"],
                ),
                reverse=True,
            )

            if candidates_ranked:
                best = candidates_ranked[0]
                competitors = [
                    c for c in candidates_ranked[1:]
                    if c["support"] == best["support"]
                    and c["evidence"] == best["evidence"]
                    and c["varied"] == best["varied"]
                    and c["simplicity"] == best["simplicity"]
                    and abs(c["offset"]) == abs(best["offset"])
                ]
                ambiguous = bool(competitors)
                confidence = best["support"]
                if ambiguous:
                    confidence *= 0.6
                elif best["evidence"] < 4:
                    confidence *= 0.9
                mode = "register-indirect" if best["offset"] == 0 else "base-plus-offset"
                addressing_modes.append({
                    "mode": mode,
                    "memory_space": memory_root,
                    "address_source": best["source_path"],
                    "offset": best["offset"],
                    "evidence": best["evidence"],
                    "observations": best["opportunities"],
                    "confidence": round(min(1.0, confidence), 6),
                    "status": "ambiguous-trace-hypothesis" if ambiguous else "trace-derived-hypothesis",
                    "alternative_count": len(competitors),
                })
                validated_memory_roots.add(memory_root)

        # Absolute addressing is reported only where no repeated register-based
        # explanation was validated.  Repeated use of the same concrete address
        # is required; one observation is merely an access, not an addressing
        # mode.
        for (memory_root, address), count in direct_address_evidence.most_common(32):
            if memory_root in validated_memory_roots or count < 2:
                continue
            addressing_modes.append({
                "mode": "absolute-address",
                "memory_space": memory_root,
                "address": address,
                "evidence": count,
                "confidence": round(min(0.95, 0.45 + 0.1 * count), 6),
                "status": "trace-derived-hypothesis",
            })
        addressing_modes.sort(key=lambda x: (x.get("evidence", 0), x.get("confidence", 0.0)), reverse=True)

        stack_name = call_stack_evidence.most_common(1)[0][0] if call_stack_evidence else None
        calling_convention = {
            "status": "trace-derived-hypothesis" if call_symbols or return_symbols else "insufficient-evidence",
            "call_symbols": sorted(call_symbols),
            "return_symbols": sorted(return_symbols),
            "return_address_stack": stack_name,
            "fallthrough_delta": fallthrough_delta,
            "fallthrough_evidence": fallthrough_evidence,
            "return_address_rule": (
                f"push(source+{fallthrough_delta})"
                if return_rule_evidence and fallthrough_delta is not None
                else ("push(trace.return_address)" if return_rule_evidence else None)
            ),
            "return_rule_evidence": return_rule_evidence,
            "unknown_code_executed": False,
        }

        return {
            "schema": "ucr.isa-profile/1",
            "status": "trace-derived-hypothesis" if instructions else "insufficient-trace-evidence",
            "fallthrough_delta": fallthrough_delta,
            "fallthrough_evidence": fallthrough_evidence,
            "instructions": instructions,
            "addressing_modes": addressing_modes[:128],
            "calling_convention": calling_convention,
            "branch_evidence_count": len(branch_hypotheses),
            "unknown_code_executed": False,
            "completeness_claim": "none; only roles evidenced by supplied traces are represented",
        }


    @staticmethod
    def _layout_role_roots(memory_model: dict[str, Any]) -> tuple[set[str], set[str], set[str]]:
        memory_roots: set[str] = set()
        stack_roots: set[str] = set()
        register_roots: set[str] = set(str(x) for x in memory_model.get("scalar_registers", []) if isinstance(x, str))
        for space in memory_model.get("address_spaces", []):
            if not isinstance(space, dict) or not isinstance(space.get("name"), str):
                continue
            name = str(space["name"])
            role = str(space.get("role_hypothesis", ""))
            if role in {"linear-memory", "addressed-memory", "heap"}:
                memory_roots.add(name)
            elif role == "stack":
                stack_roots.add(name)
            elif role == "register-bank":
                register_roots.add(name)
        return memory_roots, stack_roots, register_roots

    @classmethod
    def _path_is_abi_candidate(cls, path: str, memory_roots: set[str], stack_roots: set[str]) -> bool:
        root = cls._path_root(path)
        return root not in memory_roots and root not in stack_roots and not cls._state_path_is_control(path)

    @classmethod
    def _read_mentions_path(cls, reads: Iterable[Any], path: str) -> bool:
        root = cls._path_root(path)
        tail = path.rsplit(".", 1)[-1]
        for item in reads:
            text = str(item)
            if text == path or text == root or text == tail:
                return True
            if path.endswith("." + text) or path.endswith("[" + text + "]"):
                return True
        return False

    def _infer_function_model(
        self,
        samples: list[dict[str, Any]],
        *,
        control_edges: list[dict[str, Any]],
        calling_convention: dict[str, Any],
        memory_model: dict[str, Any],
    ) -> dict[str, Any]:
        """Reconstruct observed function entries and dynamic invocations.

        Function boundaries are inferred only from CALL/RETURN behavior already
        supported by trace evidence.  No name, address range, symbol spelling or
        executable behavior is trusted as a function declaration.
        """
        call_symbols = {str(x) for x in calling_convention.get("call_symbols", [])}
        return_symbols = {str(x) for x in calling_convention.get("return_symbols", [])}
        if not call_symbols and not return_symbols:
            return {
                "schema": "ucr.function-model/1",
                "status": "insufficient-evidence",
                "function_count": 0,
                "completed_invocation_count": 0,
                "incomplete_invocation_count": 0,
                "functions": [],
                "unknown_code_executed": False,
            }

        memory_roots, stack_roots, _register_roots = self._layout_role_roots(memory_model)
        by_observation: dict[int, list[dict[str, Any]]] = defaultdict(list)
        for sample in samples:
            obs = sample.get("observation")
            if type(obs) is int:
                by_observation[obs].append(sample)
        for group in by_observation.values():
            group.sort(key=lambda item: int(item.get("step", 0) or 0))

        completed: list[dict[str, Any]] = []
        incomplete: list[dict[str, Any]] = []
        entry_counts: Counter[str] = Counter()
        call_site_counts: dict[str, Counter[str]] = defaultdict(Counter)

        for obs, group in sorted(by_observation.items()):
            frames: list[dict[str, Any]] = []
            for sample in group:
                symbol = str(sample.get("symbol")) if sample.get("symbol") is not None else None
                source = sample.get("from") if isinstance(sample.get("from"), str) else None
                target = sample.get("to") if isinstance(sample.get("to"), str) else None

                if frames:
                    frame = frames[-1]
                    frame["body"].append(sample)
                    if isinstance(source, str):
                        frame["nodes"].add(source)
                    # A CALL target belongs to the child function and a RETURN
                    # target belongs to the caller, so neither is part of the
                    # current function's observed body.
                    if symbol not in call_symbols and symbol not in return_symbols and isinstance(target, str):
                        frame["nodes"].add(target)

                if symbol in call_symbols and target is not None:
                    entry_counts[target] += 1
                    if source is not None:
                        call_site_counts[target][source] += 1
                    frames.append({
                        "observation": obs,
                        "entry": target,
                        "call_site": source,
                        "call_symbol": symbol,
                        "call_before": sample.get("before", {}),
                        "after_call": sample.get("after", {}),
                        "body": [],
                        "nodes": {target},
                        "depth": len(frames),
                    })
                    continue

                if symbol in return_symbols and frames:
                    frame = frames.pop()
                    frame["exit"] = source
                    frame["return_to"] = target
                    frame["return_symbol"] = symbol
                    frame["after_return"] = sample.get("after", {})
                    completed.append(frame)

            for frame in frames:
                incomplete.append(frame)

        # Collect per-invocation ABI-like carrier evidence without retaining raw values.
        invocation_summaries: list[dict[str, Any]] = []
        for frame in completed:
            call_before = frame.get("call_before") if isinstance(frame.get("call_before"), dict) else {}
            after_call = frame.get("after_call") if isinstance(frame.get("after_call"), dict) else {}
            after_return = frame.get("after_return") if isinstance(frame.get("after_return"), dict) else {}
            flat_before = self._flatten_state_leaves(call_before)
            flat_after_call = self._flatten_state_leaves(after_call)
            flat_after_return = self._flatten_state_leaves(after_return)
            body = [x for x in frame.get("body", []) if isinstance(x, dict)]

            stable_entry: list[str] = []
            argument_carriers: list[str] = []
            common_entry = sorted(set(flat_before) & set(flat_after_call))
            for path in common_entry:
                if not self._path_is_abi_candidate(path, memory_roots, stack_roots):
                    continue
                if not self._semantic_equal(flat_before[path], flat_after_call[path]):
                    continue
                if type(flat_before[path]) not in (str, int, float, bool, bytes, type(None)):
                    continue
                stable_entry.append(path)
                written = False
                read_before_write = False
                for body_sample in body[:8]:
                    reads = body_sample.get("reads", []) if isinstance(body_sample.get("reads"), list) else []
                    writes = body_sample.get("writes", []) if isinstance(body_sample.get("writes"), list) else []
                    if not written and self._read_mentions_path(reads, path):
                        read_before_write = True
                        break
                    if any(str(w) == path for w in writes):
                        written = True
                if read_before_write:
                    argument_carriers.append(path)

            preserved: list[str] = []
            clobbered: list[str] = []
            return_carriers: list[str] = []
            common_return = sorted(set(flat_before) & set(flat_after_return))
            recent_writes: set[str] = set()
            for body_sample in body[-4:]:
                for item in body_sample.get("writes", []) if isinstance(body_sample.get("writes"), list) else []:
                    recent_writes.add(str(item))
            for path in common_return:
                if not self._path_is_abi_candidate(path, memory_roots, stack_roots):
                    continue
                before_value = flat_before[path]
                after_value = flat_after_return[path]
                if self._semantic_equal(before_value, after_value):
                    preserved.append(path)
                else:
                    clobbered.append(path)
                    if path in recent_writes:
                        return_carriers.append(path)

            invocation_summaries.append({
                "observation": frame.get("observation"),
                "entry": frame.get("entry"),
                "call_site": frame.get("call_site"),
                "exit": frame.get("exit"),
                "return_to": frame.get("return_to"),
                "depth": frame.get("depth"),
                "observed_nodes": sorted(str(x) for x in frame.get("nodes", set()))[:256],
                "stable_entry_carriers": stable_entry[:128],
                "argument_carriers": argument_carriers[:128],
                "return_carriers": return_carriers[:128],
                "preserved_carriers": preserved[:128],
                "clobbered_carriers": clobbered[:128],
                "body_step_count": len(body),
            })

        per_entry: dict[str, dict[str, Any]] = {}
        all_entries = set(entry_counts)
        all_entries.update(str(x.get("entry")) for x in invocation_summaries if isinstance(x.get("entry"), str))
        all_entries.update(str(x.get("entry")) for x in incomplete if isinstance(x.get("entry"), str))
        for entry in sorted(all_entries):
            invocations = [x for x in invocation_summaries if x.get("entry") == entry]
            arg_counts: Counter[str] = Counter()
            ret_counts: Counter[str] = Counter()
            preserved_counts: Counter[str] = Counter()
            clobbered_counts: Counter[str] = Counter()
            exit_counts: Counter[str] = Counter()
            return_to_counts: Counter[str] = Counter()
            nodes: Counter[str] = Counter()
            for inv in invocations:
                arg_counts.update(inv.get("argument_carriers", []))
                ret_counts.update(inv.get("return_carriers", []))
                preserved_counts.update(inv.get("preserved_carriers", []))
                clobbered_counts.update(inv.get("clobbered_carriers", []))
                if isinstance(inv.get("exit"), str):
                    exit_counts[str(inv["exit"])] += 1
                if isinstance(inv.get("return_to"), str):
                    return_to_counts[str(inv["return_to"])] += 1
                nodes.update(str(x) for x in inv.get("observed_nodes", []))

            total = max(1, len(invocations))
            def ranked(counter: Counter[str], limit: int = 32) -> list[dict[str, Any]]:
                return [
                    {
                        "path": path,
                        "evidence": count,
                        "observations": len(invocations),
                        "confidence": round(count / total, 6),
                    }
                    for path, count in counter.most_common(limit)
                ]

            per_entry[entry] = {
                "entry": entry,
                "observed_calls": entry_counts.get(entry, 0),
                "completed_invocations": len(invocations),
                "call_sites": [
                    {"node": node, "observations": count}
                    for node, count in call_site_counts.get(entry, Counter()).most_common(32)
                ],
                "exit_nodes": [
                    {"node": node, "observations": count}
                    for node, count in exit_counts.most_common(32)
                ],
                "return_targets": [
                    {"node": node, "observations": count}
                    for node, count in return_to_counts.most_common(32)
                ],
                "observed_nodes": [node for node, _ in nodes.most_common(256)],
                "candidate_argument_carriers": ranked(arg_counts),
                "candidate_return_carriers": ranked(ret_counts),
                "preserved_carriers": ranked(preserved_counts),
                "clobbered_carriers": ranked(clobbered_counts),
                "status": "trace-derived-hypothesis",
            }

        return {
            "schema": "ucr.function-model/1",
            "status": "trace-derived-hypothesis" if per_entry else "insufficient-evidence",
            "function_count": len(per_entry),
            "completed_invocation_count": len(completed),
            "incomplete_invocation_count": len(incomplete),
            "functions": list(per_entry.values()),
            "invocations": invocation_summaries[:512],
            "boundary_basis": "observed-call-targets-and-return-transfers",
            "control_edge_count": len(control_edges),
            "unknown_code_executed": False,
            "completeness_claim": "none; tail calls, exceptions and unobserved entries may be missing",
        }

    def _infer_abi_profile(
        self,
        samples: list[dict[str, Any]],
        *,
        function_model: dict[str, Any],
        calling_convention: dict[str, Any],
        memory_model: dict[str, Any],
    ) -> dict[str, Any]:
        functions = [x for x in function_model.get("functions", []) if isinstance(x, dict)]
        if not functions or int(function_model.get("completed_invocation_count", 0) or 0) == 0:
            return {
                "schema": "ucr.abi-profile/1",
                "status": "insufficient-evidence",
                "argument_carriers": [],
                "return_carriers": [],
                "preserved_carriers": [],
                "clobbered_carriers": [],
                "calling_convention": calling_convention,
                "unknown_code_executed": False,
            }

        arg_counts: Counter[str] = Counter()
        ret_counts: Counter[str] = Counter()
        preserved_counts: Counter[str] = Counter()
        clobbered_counts: Counter[str] = Counter()
        function_support: dict[str, set[str]] = defaultdict(set)
        totals = Counter()
        for fn in functions:
            entry = str(fn.get("entry"))
            completed = int(fn.get("completed_invocations", 0) or 0)
            if completed <= 0:
                continue
            totals[entry] = completed
            for field_name, counter in (
                ("candidate_argument_carriers", arg_counts),
                ("candidate_return_carriers", ret_counts),
                ("preserved_carriers", preserved_counts),
                ("clobbered_carriers", clobbered_counts),
            ):
                for item in fn.get(field_name, []):
                    if not isinstance(item, dict) or not isinstance(item.get("path"), str):
                        continue
                    path = str(item["path"])
                    evidence = int(item.get("evidence", 0) or 0)
                    counter[path] += evidence
                    if evidence:
                        function_support[path].add(entry)

        total_invocations = int(function_model.get("completed_invocation_count", 0) or 0)
        function_count = max(1, len([f for f in functions if int(f.get("completed_invocations", 0) or 0) > 0]))

        def summarize(counter: Counter[str], limit: int = 64) -> list[dict[str, Any]]:
            return [
                {
                    "path": path,
                    "evidence": count,
                    "completed_invocations": total_invocations,
                    "function_support": len(function_support.get(path, set())),
                    "confidence": round(min(1.0, count / max(1, total_invocations)), 6),
                }
                for path, count in counter.most_common(limit)
            ]

        return {
            "schema": "ucr.abi-profile/1",
            "status": "trace-derived-hypothesis",
            "argument_carriers": summarize(arg_counts),
            "return_carriers": summarize(ret_counts),
            "preserved_carriers": summarize(preserved_counts),
            "clobbered_carriers": summarize(clobbered_counts),
            "return_address_stack": calling_convention.get("return_address_stack"),
            "return_address_rule": calling_convention.get("return_address_rule"),
            "call_symbols": calling_convention.get("call_symbols", []),
            "return_symbols": calling_convention.get("return_symbols", []),
            "function_count": function_count,
            "completed_invocation_count": total_invocations,
            "evidence_basis": "entry-stable/read-before-write and post-return preservation deltas",
            "unknown_code_executed": False,
            "semantic_status": "carrier hypotheses, not a proven ABI specification",
        }

    @staticmethod
    def _pick_protocol_field(mapping: dict[str, Any], keys: tuple[str, ...]) -> Any:
        for key in keys:
            if key in mapping and mapping[key] is not None:
                return mapping[key]
        return None

    @classmethod
    def _protocol_shape(cls, value: Any, depth: int = 0) -> Any:
        if depth >= 6:
            return "..."
        if value is None:
            return "null"
        if type(value) is bool:
            return "bool"
        if type(value) is int:
            return "int"
        if type(value) is float:
            return "float"
        if type(value) is str:
            return "str"
        if type(value) is bytes:
            return "bytes"
        if type(value) is dict:
            return {
                str(k): cls._protocol_shape(v, depth + 1)
                for k, v in sorted(value.items(), key=lambda kv: str(kv[0]))[:64]
            }
        if type(value) in (list, tuple):
            shapes: list[Any] = []
            seen: set[str] = set()
            for item in list(value)[:32]:
                shape = cls._protocol_shape(item, depth + 1)
                key = json.dumps(shape, ensure_ascii=False, sort_keys=True, default=str)
                if key not in seen:
                    seen.add(key)
                    shapes.append(shape)
                if len(shapes) >= 8:
                    break
            return {"sequence": shapes}
        return type(value).__name__

    def _normalize_protocol_event(
        self,
        raw: dict[str, Any],
        *,
        observation: int,
        step: int | None,
        event_index: int | None,
    ) -> dict[str, Any] | None:
        component = self._pick_protocol_field(raw, ("component", "actor", "agent", "process", "module", "node", "service"))
        peer = self._pick_protocol_field(raw, ("peer", "remote", "counterparty"))
        source = self._pick_protocol_field(raw, ("source", "src", "from_component", "sender"))
        destination = self._pick_protocol_field(raw, ("destination", "dst", "to_component", "receiver"))
        channel = self._pick_protocol_field(raw, ("channel", "topic", "mailbox", "stream", "port", "queue", "bus"))
        action = self._pick_protocol_field(raw, ("action", "event", "io", "operation", "kind", "type"))
        if action is None:
            action = raw.get("direction")

        action_text = str(action).strip().lower() if type(action) in (str, int) else ""
        send_terms = {"send", "sent", "tx", "transmit", "write", "publish", "emit", "request", "req"}
        recv_terms = {"recv", "receive", "received", "rx", "read", "consume", "response", "reply", "resp"}
        direction: str | None = None
        if action_text in send_terms or any(term in action_text for term in ("send", "transmit", "publish", "request")):
            direction = "send"
        elif action_text in recv_terms or any(term in action_text for term in ("recv", "receive", "consume")):
            direction = "receive"
        explicit_direction = raw.get("direction")
        if isinstance(explicit_direction, str):
            d = explicit_direction.strip().lower()
            if d in {"out", "outbound", "send", "sent", "tx", "write", "publish"}:
                direction = "send"
            elif d in {"in", "inbound", "recv", "receive", "received", "rx", "read", "consume"}:
                direction = "receive"

        event_kind = "message"
        if "request" in action_text or action_text == "req":
            event_kind = "request"
        elif "response" in action_text or "reply" in action_text or action_text == "resp":
            event_kind = "response"
        elif direction is not None:
            event_kind = direction

        if component is None:
            if direction == "send" and source is not None:
                component = source
            elif direction == "receive" and destination is not None:
                component = destination
        if peer is None:
            if direction == "send" and destination is not None:
                peer = destination
            elif direction == "receive" and source is not None:
                peer = source

        has_protocol_signal = any(x is not None for x in (component, peer, source, destination, channel)) or direction is not None or event_kind in {"request", "response"}
        if not has_protocol_signal:
            return None

        payload = self._pick_protocol_field(raw, ("message", "payload", "packet", "body", "data"))
        if payload is None and "value" in raw and has_protocol_signal:
            payload = raw.get("value")
        if payload is not None and not self._is_safe_semantic_value(payload):
            payload = None

        correlation = self._pick_protocol_field(raw, ("correlation_id", "request_id", "conversation_id", "session_id", "trace_id"))
        message_id = self._pick_protocol_field(raw, ("message_id", "msg_id", "id"))
        reply_to = self._pick_protocol_field(raw, ("reply_to", "in_reply_to", "response_to"))
        payload_shape = self._protocol_shape(payload) if payload is not None else None
        payload_material = json.dumps(
            self._canonical_semantic_value(payload),
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
            default=str,
        ) if payload is not None else "<none>"
        payload_digest = hashlib.sha256(payload_material.encode("utf-8")).hexdigest()
        shape_material = json.dumps(payload_shape, ensure_ascii=False, sort_keys=True, separators=(",", ":"), default=str)
        shape_digest = hashlib.sha256(shape_material.encode("utf-8")).hexdigest()

        return {
            "observation": observation,
            "step": step,
            "event_index": event_index,
            "component": str(component) if type(component) in (str, int) else None,
            "peer": str(peer) if type(peer) in (str, int) else None,
            "source": str(source) if type(source) in (str, int) else None,
            "destination": str(destination) if type(destination) in (str, int) else None,
            "channel": str(channel) if type(channel) in (str, int) else None,
            "direction": direction,
            "event_kind": event_kind,
            "correlation_id": str(correlation) if type(correlation) in (str, int) else None,
            "message_id": str(message_id) if type(message_id) in (str, int) else None,
            "reply_to": str(reply_to) if type(reply_to) in (str, int) else None,
            "payload_digest": payload_digest,
            "payload_shape": payload_shape,
            "shape_digest": shape_digest,
        }

    def _infer_protocol_model(self, events: list[dict[str, Any]]) -> dict[str, Any]:
        if not events:
            return {
                "schema": "ucr.protocol-model/1",
                "status": "insufficient-evidence",
                "event_count": 0,
                "components": [],
                "channels": [],
                "message_schemas": [],
                "links": [],
                "request_response_pairs": [],
                "unknown_code_executed": False,
            }

        ordered = sorted(
            events,
            key=lambda e: (
                int(e.get("observation", 0) or 0),
                -1 if e.get("step") is None else int(e.get("step", 0) or 0),
                -1 if e.get("event_index") is None else int(e.get("event_index", 0) or 0),
            ),
        )
        component_counts: Counter[str] = Counter()
        channel_counts: Counter[str] = Counter()
        edge_counts: Counter[tuple[str, str, str, str]] = Counter()
        schema_counts: Counter[tuple[str, str, str]] = Counter()
        schema_shapes: dict[tuple[str, str, str], Any] = {}
        for event in ordered:
            component = event.get("component")
            peer = event.get("peer")
            channel = event.get("channel") or "<unspecified>"
            direction = event.get("direction") or event.get("event_kind") or "message"
            kind = event.get("event_kind") or "message"
            if isinstance(component, str):
                component_counts[component] += 1
            if isinstance(peer, str):
                component_counts[peer] += 0
            channel_counts[str(channel)] += 1
            if isinstance(component, str) and isinstance(peer, str):
                if direction == "receive":
                    edge_counts[(peer, component, str(channel), str(kind))] += 1
                else:
                    edge_counts[(component, peer, str(channel), str(kind))] += 1
            key = (str(channel), str(kind), str(event.get("shape_digest")))
            schema_counts[key] += 1
            schema_shapes[key] = event.get("payload_shape")

        # Pair mirrored send/receive observations without exposing payloads.
        links: list[dict[str, Any]] = []
        used_receives: set[int] = set()
        for i, send in enumerate(ordered):
            if send.get("direction") != "send":
                continue
            for j in range(i + 1, len(ordered)):
                recv = ordered[j]
                if j in used_receives or recv.get("direction") != "receive":
                    continue
                same_channel = (send.get("channel") or "<unspecified>") == (recv.get("channel") or "<unspecified>")
                same_payload = send.get("payload_digest") == recv.get("payload_digest")
                corr_send, corr_recv = send.get("correlation_id"), recv.get("correlation_id")
                correlation_ok = corr_send is None or corr_recv is None or corr_send == corr_recv
                endpoints_ok = True
                if send.get("component") and recv.get("peer"):
                    endpoints_ok = endpoints_ok and send.get("component") == recv.get("peer")
                if send.get("peer") and recv.get("component"):
                    endpoints_ok = endpoints_ok and send.get("peer") == recv.get("component")
                if same_channel and same_payload and correlation_ok and endpoints_ok:
                    used_receives.add(j)
                    links.append({
                        "send_event": i,
                        "receive_event": j,
                        "channel": send.get("channel"),
                        "source": send.get("component") or send.get("source"),
                        "destination": send.get("peer") or send.get("destination"),
                        "correlation_id": corr_send or corr_recv,
                        "shape_digest": send.get("shape_digest"),
                        "status": "observed-mirror-match",
                    })
                    break

        request_response_pairs: list[dict[str, Any]] = []
        for i, req in enumerate(ordered):
            if req.get("event_kind") != "request":
                continue
            # If direction is known, pair the logical sender-side request and
            # sender-side response instead of duplicating the mirrored receive
            # observations as separate transactions.
            if req.get("direction") is not None and req.get("direction") != "send":
                continue
            corr = req.get("correlation_id") or req.get("message_id")
            for j in range(i + 1, len(ordered)):
                resp = ordered[j]
                if resp.get("event_kind") != "response":
                    continue
                if resp.get("direction") is not None and resp.get("direction") != "send":
                    continue
                response_corr = resp.get("correlation_id") or resp.get("reply_to")
                if corr is not None and response_corr is not None and str(corr) != str(response_corr):
                    continue
                endpoints_reverse = True
                if req.get("component") and resp.get("peer"):
                    endpoints_reverse = endpoints_reverse and req.get("component") == resp.get("peer")
                if req.get("peer") and resp.get("component"):
                    endpoints_reverse = endpoints_reverse and req.get("peer") == resp.get("component")
                if endpoints_reverse:
                    request_response_pairs.append({
                        "request_event": i,
                        "response_event": j,
                        "correlation_id": corr or response_corr,
                        "request_shape": req.get("shape_digest"),
                        "response_shape": resp.get("shape_digest"),
                        "channel": req.get("channel") or resp.get("channel"),
                        "status": "observed-pair",
                    })
                    break

        transition_counts: Counter[tuple[str, str, str]] = Counter()
        sequences: dict[tuple[int, str], list[str]] = defaultdict(list)
        for event in ordered:
            comp = event.get("component")
            if not isinstance(comp, str):
                continue
            label = f"{event.get('event_kind') or 'message'}@{event.get('channel') or '<unspecified>'}"
            sequences[(int(event.get("observation", 0) or 0), comp)].append(label)
        for (_obs, comp), seq in sequences.items():
            for a, b in zip(seq, seq[1:]):
                transition_counts[(comp, a, b)] += 1

        return {
            "schema": "ucr.protocol-model/1",
            "status": "trace-derived-hypothesis",
            "event_count": len(ordered),
            "components": [
                {"component": name, "events": count}
                for name, count in component_counts.most_common(128)
            ],
            "channels": [
                {"channel": name, "events": count}
                for name, count in channel_counts.most_common(128)
            ],
            "message_schemas": [
                {
                    "channel": channel,
                    "event_kind": kind,
                    "shape_digest": shape_digest,
                    "shape": schema_shapes[(channel, kind, shape_digest)],
                    "observations": count,
                }
                for (channel, kind, shape_digest), count in schema_counts.most_common(256)
            ],
            "communication_edges": [
                {
                    "source": source,
                    "destination": destination,
                    "channel": channel,
                    "event_kind": kind,
                    "observations": count,
                }
                for (source, destination, channel, kind), count in edge_counts.most_common(256)
            ],
            "links": links[:512],
            "request_response_pairs": request_response_pairs[:512],
            "component_state_transitions": [
                {
                    "component": component,
                    "from": source,
                    "to": destination,
                    "observations": count,
                }
                for (component, source, destination), count in transition_counts.most_common(256)
            ],
            "semantic_status": "observed protocol structure, not proof of hidden message meaning",
            "unknown_code_executed": False,
        }

    @staticmethod
    def _build_vm_profile(
        *,
        transitions: list[StateTransition],
        control_edges: list[dict[str, Any]],
        branch_hypotheses: list[dict[str, Any]],
        loop_hypotheses: list[dict[str, Any]],
        memory_model: dict[str, Any],
        instruction_set: list[dict[str, Any]],
        addressing_modes: list[dict[str, Any]],
        calling_convention: dict[str, Any],
        function_model: dict[str, Any],
        abi_profile: dict[str, Any],
        protocol_model: dict[str, Any],
        emulator_model: BehavioralEmulatorModel | None = None,
    ) -> dict[str, Any]:
        symbols = Counter(t.symbol for t in transitions if t.symbol)
        control_nodes = sorted({
            endpoint
            for edge in control_edges
            for endpoint in (edge.get("from"), edge.get("to"))
            if isinstance(endpoint, str)
        })
        capabilities: list[str] = []
        if symbols:
            capabilities.append("observed-instruction-alphabet")
        if control_edges:
            capabilities.append("observed-control-flow")
        if branch_hypotheses:
            capabilities.append("conditional-branch-hypotheses")
        if loop_hypotheses:
            capabilities.append("loop/cycle-reconstruction")
        if memory_model.get("address_spaces") or memory_model.get("scalar_registers"):
            capabilities.append("state-layout-reconstruction")
        if instruction_set:
            capabilities.append("trace-derived-isa-role-reconstruction")
        if addressing_modes:
            capabilities.append("addressing-mode-hypotheses")
        if calling_convention.get("call_symbols") or calling_convention.get("return_symbols"):
            capabilities.append("call-return-reconstruction")
        if function_model.get("function_count"):
            capabilities.append("function-boundary-and-invocation-reconstruction")
        if abi_profile.get("status") == "trace-derived-hypothesis":
            capabilities.append("abi-carrier-and-preservation-hypotheses")
        if protocol_model.get("status") == "trace-derived-hypothesis":
            capabilities.append("inter-component-protocol-reconstruction")
        if emulator_model is not None and emulator_model.metadata.get("executable_rule_count", 0):
            capabilities.append("bounded-behavioral-emulation")
        if any(
            any(h.get("kind") == "control.jump.indirect" for h in item.get("hypotheses", []))
            for item in instruction_set
        ):
            capabilities.append("indirect-control-transfer-reconstruction")
        return {
            "schema": "ucr.vm-profile/4",
            "status": "trace-derived-hypothesis" if transitions else "insufficient-trace-evidence",
            "observed_instruction_symbols": [
                {"symbol": symbol, "count": count} for symbol, count in symbols.most_common(128)
            ],
            "control_node_count": len(control_nodes),
            "control_nodes": control_nodes[:256],
            "branch_point_count": len(branch_hypotheses),
            "loop_count": len(loop_hypotheses),
            "memory_model": memory_model,
            "instruction_set": instruction_set,
            "addressing_modes": addressing_modes,
            "calling_convention": calling_convention,
            "function_model": function_model,
            "abi_profile": abi_profile,
            "protocol_model": protocol_model,
            "behavioral_emulator": emulator_model.to_dict() if emulator_model is not None else None,
            "capabilities": capabilities,
            "unknown_code_executed": False,
            "completeness_claim": "none; model covers only behavior present in supplied traces",
        }

    @staticmethod
    def _emulator_path_tokens(path: str) -> list[Any]:
        """Parse the leaf-path syntax produced by ``_flatten_state_leaves``."""
        if not isinstance(path, str) or not path:
            return []
        parts: list[Any] = []
        for dot_part in path.split("."):
            if not dot_part:
                continue
            head = re.match(r"^[^\[]+", dot_part)
            if head:
                parts.append(head.group(0))
            for match in re.finditer(r"\[(-?\d+)\]", dot_part):
                parts.append(int(match.group(1)))
        return parts

    @classmethod
    def _emulator_get_path(cls, state: dict[str, Any], path: str) -> tuple[bool, Any]:
        tokens = cls._emulator_path_tokens(path)
        if not tokens:
            return False, None
        current: Any = state
        for token in tokens:
            if type(token) is int:
                if type(current) not in (list, tuple) or token < 0 or token >= len(current):
                    return False, None
                current = current[token]
            else:
                if not isinstance(current, dict) or token not in current:
                    return False, None
                current = current[token]
        return True, current

    @classmethod
    def _emulator_set_path(cls, state: dict[str, Any], path: str, value: Any) -> bool:
        tokens = cls._emulator_path_tokens(path)
        if not tokens:
            return False
        current: Any = state
        for index, token in enumerate(tokens[:-1]):
            nxt = tokens[index + 1]
            if type(token) is int:
                if type(current) is not list or token < 0:
                    return False
                while token >= len(current):
                    current.append({} if type(nxt) is str else [])
                if current[token] is None:
                    current[token] = {} if type(nxt) is str else []
                current = current[token]
            else:
                if not isinstance(current, dict):
                    return False
                if token not in current or current[token] is None:
                    current[token] = {} if type(nxt) is str else []
                current = current[token]
        leaf = tokens[-1]
        if type(leaf) is int:
            if type(current) is not list or leaf < 0:
                return False
            while leaf >= len(current):
                current.append(None)
            current[leaf] = copy.deepcopy(value)
        else:
            if not isinstance(current, dict):
                return False
            current[leaf] = copy.deepcopy(value)
        return True

    @classmethod
    def _emulator_memory_get(cls, state: dict[str, Any], root: str, address: Any) -> tuple[bool, Any]:
        if root not in state:
            return False, None
        memory = state[root]
        if type(memory) in (list, tuple):
            if type(address) is not int or type(address) is bool or address < 0 or address >= len(memory):
                return False, None
            return True, memory[address]
        if isinstance(memory, dict):
            if address in memory:
                return True, memory[address]
            text = str(address)
            if text in memory:
                return True, memory[text]
        return False, None

    @classmethod
    def _emulator_memory_set(cls, state: dict[str, Any], root: str, address: Any, value: Any) -> bool:
        if root not in state:
            return False
        memory = state[root]
        if type(memory) is list:
            if type(address) is not int or type(address) is bool or address < 0:
                return False
            while address >= len(memory):
                memory.append(None)
            memory[address] = copy.deepcopy(value)
            return True
        if isinstance(memory, dict):
            key = address if address in memory else str(address) if str(address) in memory else address
            memory[key] = copy.deepcopy(value)
            return True
        return False

    @staticmethod
    def _emulator_parse_predicate(label: Any) -> dict[str, Any] | None:
        if not isinstance(label, str):
            return None
        patterns = [
            (r"^(.+) is true$", "truthy", 1),
            (r"^(.+) == 0$", "eq_zero", 1),
            (r"^(.+) > 0$", "gt_zero", 1),
            (r"^(.+) < 0$", "lt_zero", 1),
            (r"^len\((.+)\) == 0$", "len_zero", 1),
            (r"^(.+) == (.+)$", "eq_path", 2),
            (r"^(.+) < (.+)$", "lt_path", 2),
            (r"^(.+) > (.+)$", "gt_path", 2),
        ]
        for pattern, kind, arity in patterns:
            match = re.match(pattern, label)
            if not match:
                continue
            if arity == 1:
                return {"kind": kind, "path": match.group(1).strip(), "label": label}
            return {"kind": kind, "left": match.group(1).strip(), "right": match.group(2).strip(), "label": label}
        return None

    @classmethod
    def _emulator_eval_predicate(cls, predicate: dict[str, Any], state: dict[str, Any]) -> tuple[bool, bool | None]:
        kind = predicate.get("kind")
        if kind in {"truthy", "eq_zero", "gt_zero", "lt_zero", "len_zero"}:
            ok, value = cls._emulator_get_path(state, str(predicate.get("path", "")))
            if not ok:
                return False, None
            try:
                if kind == "truthy" and type(value) is bool:
                    return True, value
                if kind == "eq_zero" and type(value) in (int, float) and type(value) is not bool:
                    return True, value == 0
                if kind == "gt_zero" and type(value) in (int, float) and type(value) is not bool:
                    return True, value > 0
                if kind == "lt_zero" and type(value) in (int, float) and type(value) is not bool:
                    return True, value < 0
                if kind == "len_zero" and type(value) in (str, bytes, list, tuple, dict):
                    return True, len(value) == 0
            except Exception:
                return False, None
            return False, None
        if kind in {"eq_path", "lt_path", "gt_path"}:
            ok_l, left = cls._emulator_get_path(state, str(predicate.get("left", "")))
            ok_r, right = cls._emulator_get_path(state, str(predicate.get("right", "")))
            if not ok_l or not ok_r:
                return False, None
            try:
                if kind == "eq_path":
                    return True, left == right
                if kind == "lt_path":
                    return True, left < right
                return True, left > right
            except Exception:
                return False, None
        return False, None

    def _infer_emulator_value_rule(
        self,
        symbol: str,
        destination: str,
        samples: list[dict[str, Any]],
        *,
        excluded_roots: set[str],
    ) -> tuple[EmulatorRule | None, list[dict[str, Any]]]:
        """Infer one conservative state-write rule from repeated transitions."""
        rows: list[tuple[dict[str, Any], Any]] = []
        for sample in samples:
            before = sample.get("before")
            after = sample.get("after")
            writes = sample.get("writes", [])
            if not isinstance(before, dict) or not isinstance(after, dict) or destination not in writes:
                continue
            flat_before = self._flatten_state_leaves(before)
            flat_after = self._flatten_state_leaves(after)
            if destination in flat_after:
                rows.append((flat_before, flat_after[destination]))
        if len(rows) < 2:
            return None, []

        candidates: list[dict[str, Any]] = []
        common_sources = set(rows[0][0])
        for before, _ in rows[1:]:
            common_sources.intersection_update(before)
        source_paths = [
            p for p in sorted(common_sources)
            if not self._state_path_is_control(p)
            and self._path_root(p) not in excluded_roots
            and all(self._is_safe_semantic_value(before.get(p)) for before, _ in rows)
        ][:24]

        # Exact copy has the strongest simplicity prior.
        for source in source_paths:
            matches = sum(self._semantic_equal(before[source], expected) for before, expected in rows)
            if matches == len(rows) and len({repr(before[source]) for before, _ in rows}) >= 2:
                candidates.append({"kind": "state.copy", "sources": [source], "score": 1.0, "priority": 100})

        outputs = [expected for _, expected in rows]
        if len(rows) >= 3 and all(self._semantic_equal(outputs[0], item) for item in outputs[1:]):
            candidates.append({"kind": "state.constant", "value": outputs[0], "score": 1.0, "priority": 50})

        if len(rows) >= 3:
            for label, spec in sorted(self.semantic_primitives.items()):
                arity = int(spec.get("arity", 0) or 0)
                if arity not in {1, 2}:
                    continue
                if label in {"unary.identity", "projection.left", "projection.right"}:
                    continue
                if arity == 1:
                    combos = ((p,) for p in source_paths)
                else:
                    combos = itertools.product(source_paths, repeat=2)
                seen_commutative: set[tuple[str, str]] = set()
                for combo in combos:
                    if arity == 2 and spec.get("commutative"):
                        canonical = tuple(sorted(combo))
                        if canonical in seen_commutative:
                            continue
                        seen_commutative.add(canonical)
                    matched = 0
                    applicable = 0
                    for before, expected in rows:
                        args = tuple(before[p] for p in combo)
                        ok, predicted = self._apply_semantic_primitive(spec["function"], args)
                        if not ok or not self._is_safe_semantic_value(predicted):
                            continue
                        applicable += 1
                        if self._semantic_equal(predicted, expected):
                            matched += 1
                    if applicable != len(rows):
                        continue
                    score = matched / len(rows)
                    if score >= 0.999999:
                        # Require variation in at least one source so constants do not
                        # masquerade as arithmetic behavior.
                        if not any(len({repr(before[p]) for before, _ in rows}) >= 2 for p in combo):
                            continue
                        candidates.append({
                            "kind": "semantic.unary" if arity == 1 else "semantic.binary",
                            "semantic": label,
                            "sources": list(combo),
                            "score": score,
                            "priority": 90 if arity == 1 else 80,
                        })

        if not candidates:
            return None, []
        candidates.sort(key=lambda c: (c["score"], c["priority"], c.get("semantic", ""), c.get("sources", [])), reverse=True)
        best = candidates[0]
        # Different perfect behavioral explanations remain ambiguous.  A copy
        # rule may safely dominate a semantically equivalent identity rule, but
        # distinct arithmetic meanings are not silently collapsed.
        best_behavior = (best.get("kind"), tuple(best.get("sources", [])), best.get("semantic"), repr(best.get("value")))
        alternatives = []
        for candidate in candidates[1:]:
            if candidate["score"] < best["score"]:
                continue
            behavior = (candidate.get("kind"), tuple(candidate.get("sources", [])), candidate.get("semantic"), repr(candidate.get("value")))
            if behavior != best_behavior:
                alternatives.append(candidate)
        ambiguous = bool(alternatives) and best["kind"] not in {"state.copy", "state.constant"}
        evidence = len(rows)
        confidence = min(0.99, 0.55 + 0.09 * evidence)
        if ambiguous:
            confidence *= 0.55
        executable = (not ambiguous and evidence >= 3) or (best["kind"] == "state.copy" and evidence >= 2)
        rule = EmulatorRule(
            symbol=symbol,
            kind=best["kind"],
            confidence=round(confidence, 6),
            evidence=evidence,
            executable=executable,
            destination=destination,
            sources=list(best.get("sources", [])),
            semantic=best.get("semantic"),
            value=copy.deepcopy(best.get("value")),
            meta={
                "status": "trace-derived-rule" if executable else "ambiguous-trace-hypothesis",
                "alternative_count": len(alternatives),
                "alternatives": alternatives[:8],
                "unknown_code_executed": False,
            },
        )
        return rule, candidates[:12]

    def _build_behavioral_emulator_model(
        self,
        samples: list[dict[str, Any]],
        *,
        memory_model: dict[str, Any],
        instruction_set: list[dict[str, Any]],
        addressing_modes: list[dict[str, Any]],
        calling_convention: dict[str, Any],
        branch_hypotheses: list[dict[str, Any]],
    ) -> BehavioralEmulatorModel:
        """Build a bounded executable model from repeated, trace-supported rules.

        This never turns unknown source/binary code into host executable code.
        Only host-side primitives already registered in ``semantic_primitives``
        and structural memory/control rules supported by traces can execute.
        """
        memory_roots, stack_roots, _register_roots = self._layout_role_roots(memory_model)
        control_registers = [str(x) for x in memory_model.get("control_registers", []) if isinstance(x, str)]
        control_register = control_registers[0] if control_registers else None
        fallthrough_delta = calling_convention.get("fallthrough_delta")
        if type(fallthrough_delta) is not int:
            fallthrough_delta = None

        grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
        for sample in samples:
            symbol = sample.get("symbol")
            if symbol is not None:
                grouped[str(symbol)].append(sample)
        isa_by_symbol = {str(item.get("symbol")): item for item in instruction_set if item.get("symbol") is not None}
        address_by_root = {
            str(item.get("memory_space")): item
            for item in addressing_modes
            if isinstance(item, dict) and isinstance(item.get("memory_space"), str)
        }
        rules_by_symbol: dict[str, list[EmulatorRule]] = {}
        unresolved_symbols: list[str] = []

        for symbol, group in sorted(grouped.items()):
            rules: list[EmulatorRule] = []
            item = isa_by_symbol.get(symbol, {})
            hypotheses = item.get("hypotheses", []) if isinstance(item, dict) else []
            hyp_by_kind = {
                str(h.get("kind")): h for h in hypotheses
                if isinstance(h, dict) and isinstance(h.get("kind"), str)
            }
            handled_destinations: set[str] = set()

            for kind in ("memory.load", "memory.store"):
                hypothesis = hyp_by_kind.get(kind)
                if not isinstance(hypothesis, dict):
                    continue
                examples = [e for e in hypothesis.get("examples", []) if isinstance(e, dict)]
                if not examples:
                    continue
                if kind == "memory.load":
                    dests = Counter(str(e.get("destination")) for e in examples if isinstance(e.get("destination"), str))
                    sources = [str(e.get("source")) for e in examples if isinstance(e.get("source"), str)]
                    if not dests or not sources:
                        continue
                    destination = dests.most_common(1)[0][0]
                    memory_space = self._path_root(sources[0])
                    if any(self._path_root(p) != memory_space for p in sources):
                        continue
                    mode = address_by_root.get(memory_space, {})
                    concrete_paths = Counter(sources)
                    source_path = concrete_paths.most_common(1)[0][0] if len(concrete_paths) == 1 else None
                    executable = bool(mode.get("address_source")) or source_path is not None
                    confidence = min(float(hypothesis.get("confidence", 0.0) or 0.0), float(mode.get("confidence", 1.0) or 1.0))
                    rules.append(EmulatorRule(
                        symbol=symbol, kind=kind, confidence=round(confidence, 6),
                        evidence=int(hypothesis.get("evidence", 0) or 0), executable=executable,
                        destination=destination, memory_space=memory_space,
                        address_source=mode.get("address_source") if isinstance(mode.get("address_source"), str) else None,
                        offset=int(mode.get("offset", 0) or 0),
                        sources=[source_path] if source_path else [],
                        meta={"addressing_mode": mode.get("mode") or ("concrete" if source_path else None), "unknown_code_executed": False},
                    ))
                    handled_destinations.add(destination)
                else:
                    dests = [str(e.get("destination")) for e in examples if isinstance(e.get("destination"), str)]
                    source_counts = Counter(str(e.get("source")) for e in examples if isinstance(e.get("source"), str))
                    if not dests or not source_counts:
                        continue
                    memory_space = self._path_root(dests[0])
                    if any(self._path_root(p) != memory_space for p in dests):
                        continue
                    source_path = source_counts.most_common(1)[0][0]
                    mode = address_by_root.get(memory_space, {})
                    concrete_paths = Counter(dests)
                    concrete_path = concrete_paths.most_common(1)[0][0] if len(concrete_paths) == 1 else None
                    executable = bool(mode.get("address_source")) or concrete_path is not None
                    confidence = min(float(hypothesis.get("confidence", 0.0) or 0.0), float(mode.get("confidence", 1.0) or 1.0))
                    rules.append(EmulatorRule(
                        symbol=symbol, kind=kind, confidence=round(confidence, 6),
                        evidence=int(hypothesis.get("evidence", 0) or 0), executable=executable,
                        sources=[source_path], memory_space=memory_space,
                        address_source=mode.get("address_source") if isinstance(mode.get("address_source"), str) else None,
                        offset=int(mode.get("offset", 0) or 0),
                        destination=concrete_path,
                        meta={"addressing_mode": mode.get("mode") or ("concrete" if concrete_path else None), "unknown_code_executed": False},
                    ))

            write_counts: Counter[str] = Counter()
            for sample in group:
                for path in sample.get("writes", []):
                    if not isinstance(path, str):
                        continue
                    if self._state_path_is_control(path) or self._path_root(path) in memory_roots | stack_roots:
                        continue
                    if path in handled_destinations:
                        continue
                    write_counts[path] += 1
            for destination, evidence in write_counts.most_common(16):
                if evidence < 2:
                    continue
                rule, _candidates = self._infer_emulator_value_rule(
                    symbol, destination, group, excluded_roots=memory_roots | stack_roots,
                )
                if rule is not None:
                    rules.append(rule)

            # Branch rules are source-specific; this prevents one opcode used at
            # multiple addresses from becoming a universal branch instruction.
            for branch in branch_hypotheses:
                if symbol not in [str(x) for x in branch.get("instruction_symbols", [])]:
                    continue
                if branch.get("status") != "supported-hypothesis" or float(branch.get("confidence", 0.0) or 0.0) < 0.7:
                    continue
                candidates = branch.get("candidate_conditions", [])
                if not candidates:
                    continue
                best = candidates[0]
                if float(best.get("accuracy", 0.0) or 0.0) < 0.95:
                    continue
                predicate = self._emulator_parse_predicate(best.get("predicate"))
                if predicate is None:
                    continue
                rules.append(EmulatorRule(
                    symbol=symbol, kind="control.branch",
                    confidence=round(min(float(branch.get("confidence", 0.0)), float(best.get("accuracy", 0.0))), 6),
                    evidence=int(best.get("samples", 0) or 0), executable=True,
                    source_control=self._control_payload(branch.get("source")), predicate=predicate,
                    true_target=self._control_payload(best.get("true_target")),
                    false_target=self._control_payload(best.get("false_target")),
                    meta={"status": "trace-derived-rule", "unknown_code_executed": False},
                ))

            primary = item.get("primary_role") if isinstance(item, dict) else None
            if "control.call" in hyp_by_kind or primary == "control.call":
                hyp = hyp_by_kind.get("control.call", {})
                examples = [e for e in hyp.get("examples", []) if isinstance(e, dict)] if isinstance(hyp, dict) else []
                targets = Counter(self._control_payload(e.get("target")) for e in examples if e.get("target") is not None)
                stable_target = targets.most_common(1)[0][0] if len(targets) == 1 and targets else None
                rules.append(EmulatorRule(
                    symbol=symbol, kind="control.call", confidence=float(hyp.get("confidence", 0.0) or 0.0),
                    evidence=int(hyp.get("evidence", 0) or 0), executable=bool(calling_convention.get("return_address_stack")),
                    target_control=stable_target, stack=calling_convention.get("return_address_stack"),
                    meta={"return_address_rule": calling_convention.get("return_address_rule"), "unknown_code_executed": False},
                ))
            elif "control.return" in hyp_by_kind or primary == "control.return":
                hyp = hyp_by_kind.get("control.return", {})
                rules.append(EmulatorRule(
                    symbol=symbol, kind="control.return", confidence=float(hyp.get("confidence", 0.0) or 0.0),
                    evidence=int(hyp.get("evidence", 0) or 0), executable=bool(calling_convention.get("return_address_stack")),
                    stack=calling_convention.get("return_address_stack"),
                    meta={"unknown_code_executed": False},
                ))
            else:
                # A varying register-sourced target is an indirect jump even if
                # the same source address consequently also looks like a generic
                # multi-destination branch. Keep both rules; runtime selection
                # prefers a supported source-specific predicate when present.
                hyp = hyp_by_kind.get("control.jump.indirect")
                if isinstance(hyp, dict):
                    examples = [e for e in hyp.get("examples", []) if isinstance(e, dict)]
                    sources = Counter(str(e.get("target_source")) for e in examples if isinstance(e.get("target_source"), str))
                    source_path = sources.most_common(1)[0][0] if sources else None
                    rules.append(EmulatorRule(
                        symbol=symbol, kind="control.jump.indirect", confidence=float(hyp.get("confidence", 0.0) or 0.0),
                        evidence=int(hyp.get("evidence", 0) or 0), executable=source_path is not None,
                        sources=[source_path] if source_path else [], meta={"unknown_code_executed": False},
                    ))
                hyp = hyp_by_kind.get("control.jump.direct")
                if isinstance(hyp, dict) and "control.jump.indirect" not in hyp_by_kind:
                    examples = [e for e in hyp.get("examples", []) if isinstance(e, dict)]
                    targets = Counter(self._control_payload(e.get("target")) for e in examples if e.get("target") is not None)
                    stable_target = targets.most_common(1)[0][0] if len(targets) == 1 and targets else None
                    rules.append(EmulatorRule(
                        symbol=symbol, kind="control.jump.direct", confidence=float(hyp.get("confidence", 0.0) or 0.0),
                        evidence=int(hyp.get("evidence", 0) or 0), executable=stable_target is not None,
                        target_control=stable_target, meta={"unknown_code_executed": False},
                    ))

            # A plain fall-through rule is useful for instructions whose state
            # effects were reconstructed but which have no special control role.
            if not any(r.kind.startswith("control.") for r in rules) and fallthrough_delta is not None:
                fallthrough_matches = 0
                control_rows = 0
                for sample in group:
                    src = self._control_numeric(sample.get("from"))
                    dst = self._control_numeric(sample.get("to"))
                    if src is None or dst is None:
                        continue
                    control_rows += 1
                    if dst - src == fallthrough_delta:
                        fallthrough_matches += 1
                if control_rows >= 2 and fallthrough_matches == control_rows:
                    rules.append(EmulatorRule(
                        symbol=symbol, kind="control.fallthrough",
                        confidence=round(min(0.99, 0.6 + 0.08 * control_rows), 6), evidence=control_rows,
                        executable=True, meta={"unknown_code_executed": False},
                    ))

            if rules:
                rules_by_symbol[symbol] = rules
            if not any(rule.executable for rule in rules):
                unresolved_symbols.append(symbol)

        executable_count = sum(rule.executable for rules in rules_by_symbol.values() for rule in rules)
        total_rules = sum(len(rules) for rules in rules_by_symbol.values())
        return BehavioralEmulatorModel(
            status="trace-derived-bounded-emulator" if executable_count else "insufficient-evidence",
            control_register=control_register,
            fallthrough_delta=fallthrough_delta,
            rules=rules_by_symbol,
            unresolved_symbols=sorted(unresolved_symbols),
            metadata={
                "reader_version": self.VERSION,
                "rule_count": total_rules,
                "executable_rule_count": executable_count,
                "instruction_symbol_count": len(rules_by_symbol),
                "unknown_code_executed": False,
                "execution_basis": "trusted-host-primitives-and-trace-derived-structural-rules-only",
                "completeness_claim": "none; unresolved or ambiguous instructions halt emulation",
            },
        )

    @staticmethod
    def _emulator_normalize_address(value: Any) -> Any:
        if type(value) is int:
            return value
        if isinstance(value, str):
            stripped = value.strip()
            try:
                return int(stripped, 0)
            except ValueError:
                return stripped
        return value

    def _normalize_emulator_program(
        self,
        program: Any,
        *,
        fallthrough_delta: int | None,
    ) -> tuple[dict[Any, dict[str, Any]], list[Any]]:
        normalized: dict[Any, dict[str, Any]] = {}
        order: list[Any] = []
        if isinstance(program, dict):
            items = list(program.items())
        elif isinstance(program, (list, tuple)):
            delta = fallthrough_delta or 1
            items = []
            for index, spec in enumerate(program):
                address = spec.get("address") if isinstance(spec, dict) and "address" in spec else index * delta
                items.append((address, spec))
        else:
            return {}, []
        for raw_address, raw_spec in items:
            address = self._emulator_normalize_address(raw_address)
            if isinstance(raw_spec, str):
                spec = {"symbol": raw_spec}
            elif isinstance(raw_spec, dict):
                spec = dict(raw_spec)
            else:
                continue
            symbol = self._trace_step_symbol(spec)
            if symbol is None and isinstance(spec.get("symbol"), str):
                symbol = spec["symbol"]
            if symbol is None:
                continue
            spec["symbol"] = symbol
            normalized[address] = spec
            order.append(address)
        return normalized, order

    @staticmethod
    def _emulator_next_address(order: list[Any], current: Any, delta: int | None) -> Any:
        if type(current) is int and type(delta) is int:
            return current + delta
        try:
            index = order.index(current)
        except ValueError:
            return None
        return order[index + 1] if index + 1 < len(order) else None

    def emulate_reconstructed(
        self,
        model: StatefulSemanticModel | BehavioralEmulatorModel,
        program: Any,
        initial_state: dict[str, Any],
        *,
        entry: Any = None,
        max_steps: int = 256,
        min_rule_confidence: float = 0.6,
    ) -> EmulationResult:
        """Predict behavior using only the reconstructed bounded emulator.

        ``program`` is a decoded instruction map/list (symbol per address), not
        arbitrary source to be executed.  Unknown source/binary code is never
        passed to Python ``eval``/``exec`` or dynamically imported.  Emulation
        stops at the first unsupported or ambiguous instruction.
        """
        emulator = model.emulator_model if isinstance(model, StatefulSemanticModel) else model
        if emulator is None:
            return EmulationResult("unavailable", "missing-emulator-model", 0, copy.deepcopy(initial_state))
        if not self._valid_state_mapping(initial_state):
            return EmulationResult("invalid-input", "unsafe-or-invalid-initial-state", 0, {})
        if type(max_steps) is not int or max_steps < 1 or max_steps > 100000:
            return EmulationResult("invalid-input", "max-steps-out-of-range", 0, copy.deepcopy(initial_state))

        decoded, order = self._normalize_emulator_program(program, fallthrough_delta=emulator.fallthrough_delta)
        if not decoded:
            return EmulationResult("invalid-input", "empty-or-undecodable-program-map", 0, copy.deepcopy(initial_state))
        state = copy.deepcopy(initial_state)
        if entry is None and emulator.control_register:
            ok, control_value = self._emulator_get_path(state, emulator.control_register)
            if ok:
                entry = control_value
        if entry is None:
            entry = order[0]
        pc = self._emulator_normalize_address(entry)
        if emulator.control_register:
            self._emulator_set_path(state, emulator.control_register, pc)

        trace: list[dict[str, Any]] = []
        unresolved: list[dict[str, Any]] = []
        confidences: list[float] = []
        halt_reason = "step-limit"
        status = "step-limit"

        for step_index in range(max_steps):
            spec = decoded.get(pc)
            if spec is None:
                halt_reason = "no-instruction-at-control"
                status = "halted"
                break
            symbol = str(spec.get("symbol"))
            all_rules = emulator.rules.get(symbol, [])
            rules = [r for r in all_rules if r.executable and r.confidence >= min_rule_confidence]
            if not rules:
                unresolved.append({"step": step_index, "control": pc, "symbol": symbol, "reason": "no-executable-rule"})
                halt_reason = "unresolved-instruction"
                status = "partial"
                break

            before_digest = self._state_digest(state)
            applied: list[str] = []
            step_conf: list[float] = []
            failed = False
            control_rules = [r for r in rules if r.kind.startswith("control.") and r.kind != "control.fallthrough"]
            fallthrough_rules = [r for r in rules if r.kind == "control.fallthrough"]
            state_rules = [r for r in rules if not r.kind.startswith("control.")]

            for rule in state_rules:
                ok = False
                value: Any = None
                if rule.kind == "state.copy" and rule.destination and rule.sources:
                    got, value = self._emulator_get_path(state, rule.sources[0])
                    ok = got and self._emulator_set_path(state, rule.destination, value)
                elif rule.kind == "state.constant" and rule.destination:
                    ok = self._emulator_set_path(state, rule.destination, rule.value)
                elif rule.kind in {"semantic.unary", "semantic.binary"} and rule.destination and rule.semantic:
                    primitive = self.semantic_primitives.get(rule.semantic)
                    args: list[Any] = []
                    if primitive is not None:
                        for source in rule.sources:
                            got, item = self._emulator_get_path(state, source)
                            if not got:
                                args = []
                                break
                            args.append(item)
                    if primitive is not None and len(args) == int(primitive.get("arity", 0) or 0):
                        success, value = self._apply_semantic_primitive(primitive["function"], tuple(args))
                        ok = success and self._is_safe_semantic_value(value) and self._emulator_set_path(state, rule.destination, value)
                elif rule.kind in {"memory.load", "memory.store"} and rule.memory_space:
                    address: Any = None
                    if rule.address_source:
                        got, base = self._emulator_get_path(state, rule.address_source)
                        if got and type(base) is int and type(base) is not bool:
                            address = base + int(rule.offset or 0)
                    elif rule.destination and rule.kind == "memory.store":
                        address = self._path_numeric_address(rule.destination)
                    elif rule.sources and rule.kind == "memory.load":
                        address = self._path_numeric_address(rule.sources[0])
                    if rule.kind == "memory.load" and rule.destination is not None and address is not None:
                        got, value = self._emulator_memory_get(state, rule.memory_space, address)
                        ok = got and self._emulator_set_path(state, rule.destination, value)
                    elif rule.kind == "memory.store" and rule.sources and address is not None:
                        got, value = self._emulator_get_path(state, rule.sources[0])
                        ok = got and self._emulator_memory_set(state, rule.memory_space, address, value)
                if not ok:
                    unresolved.append({"step": step_index, "control": pc, "symbol": symbol, "rule": rule.kind, "reason": "rule-application-failed"})
                    failed = True
                    break
                applied.append(rule.kind)
                step_conf.append(rule.confidence)
            if failed:
                halt_reason = "rule-application-failed"
                status = "partial"
                break

            next_pc: Any = None
            if control_rules:
                # Source-specific branches take precedence over generic control rules.
                branch_rules = [r for r in control_rules if r.kind == "control.branch" and (r.source_control is None or self._emulator_normalize_address(r.source_control) == pc)]
                generic_control_rules = [r for r in control_rules if r.kind != "control.branch"]
                if branch_rules:
                    rule = branch_rules[0]
                elif generic_control_rules:
                    rule = generic_control_rules[0]
                else:
                    unresolved.append({"step": step_index, "control": pc, "symbol": symbol, "reason": "branch-rule-not-applicable-at-this-control"})
                    halt_reason = "control-rule-not-applicable"
                    status = "partial"
                    break
                if rule.kind == "control.branch" and rule.predicate:
                    ok, outcome = self._emulator_eval_predicate(rule.predicate, state)
                    if ok and type(outcome) is bool:
                        next_pc = rule.true_target if outcome else rule.false_target
                elif rule.kind == "control.jump.indirect" and rule.sources:
                    ok, next_pc = self._emulator_get_path(state, rule.sources[0])
                    if not ok:
                        next_pc = None
                elif rule.kind == "control.jump.direct":
                    next_pc = spec.get("target", rule.target_control)
                elif rule.kind == "control.call":
                    target = spec.get("target", rule.target_control)
                    stack_path = rule.stack
                    if stack_path:
                        ok, stack_value = self._emulator_get_path(state, stack_path)
                        if ok and type(stack_value) in (list, tuple):
                            return_address = spec.get("return_address")
                            if return_address is None:
                                return_address = self._emulator_next_address(order, pc, emulator.fallthrough_delta)
                            updated = list(stack_value) + [return_address]
                            if type(stack_value) is tuple:
                                updated_value: Any = tuple(updated)
                            else:
                                updated_value = updated
                            if self._emulator_set_path(state, stack_path, updated_value):
                                next_pc = target
                elif rule.kind == "control.return" and rule.stack:
                    ok, stack_value = self._emulator_get_path(state, rule.stack)
                    if ok and type(stack_value) in (list, tuple) and stack_value:
                        next_pc = stack_value[-1]
                        updated = list(stack_value[:-1])
                        updated_value = tuple(updated) if type(stack_value) is tuple else updated
                        self._emulator_set_path(state, rule.stack, updated_value)
                if next_pc is None:
                    unresolved.append({"step": step_index, "control": pc, "symbol": symbol, "rule": rule.kind, "reason": "control-target-unresolved"})
                    halt_reason = "control-target-unresolved"
                    status = "partial"
                    break
                applied.append(rule.kind)
                step_conf.append(rule.confidence)
            else:
                next_pc = self._emulator_next_address(order, pc, emulator.fallthrough_delta)
                if fallthrough_rules:
                    best_fallthrough = max(fallthrough_rules, key=lambda r: (r.confidence, r.evidence))
                    applied.append("control.fallthrough")
                    step_conf.append(best_fallthrough.confidence)

            next_pc = self._emulator_normalize_address(next_pc)
            if emulator.control_register and next_pc is not None:
                self._emulator_set_path(state, emulator.control_register, next_pc)
            after_digest = self._state_digest(state)
            step_confidence = min(step_conf) if step_conf else 0.5
            confidences.append(step_confidence)
            trace.append({
                "step": step_index,
                "control": pc,
                "next_control": next_pc,
                "symbol": symbol,
                "applied_rules": applied,
                "confidence": round(step_confidence, 6),
                "before_digest": before_digest,
                "after_digest": after_digest,
            })
            if next_pc is None:
                halt_reason = "program-end"
                status = "halted"
                break
            pc = next_pc
        else:
            halt_reason = "step-limit"
            status = "step-limit"

        confidence = min(confidences) if confidences else 0.0
        return EmulationResult(
            status=status,
            halted_reason=halt_reason,
            steps=len(trace),
            final_state=state,
            trace=trace,
            unresolved=unresolved,
            confidence=round(confidence, 6),
            metadata={
                "reader_version": self.VERSION,
                "unknown_code_executed": False,
                "program_representation": "decoded-symbol-map",
                "model_status": emulator.status,
                "rule_confidence_floor": min_rule_confidence,
            },
        )

    def _infer_data_dependencies(self, forms: list[dict[str, Any]]) -> list[dict[str, Any]]:
        last_writer: dict[str, int] = {}
        dependencies: list[dict[str, Any]] = []
        for index, form in enumerate(forms):
            reads = self._form_read_names(form)
            for variable in reads:
                if variable in last_writer:
                    source_index = last_writer[variable]
                    dependencies.append({
                        "variable": variable,
                        "from_instruction": source_index,
                        "to_instruction": index,
                        "from_line": forms[source_index].get("line"),
                        "to_line": form.get("line"),
                        "kind": "read-after-write",
                    })
                else:
                    dependencies.append({
                        "variable": variable,
                        "from_instruction": None,
                        "to_instruction": index,
                        "from_line": None,
                        "to_line": form.get("line"),
                        "kind": "external-input",
                    })
            target = form.get("target")
            if isinstance(target, str):
                if target in last_writer:
                    dependencies.append({
                        "variable": target,
                        "from_instruction": last_writer[target],
                        "to_instruction": index,
                        "from_line": forms[last_writer[target]].get("line"),
                        "to_line": form.get("line"),
                        "kind": "write-after-write",
                    })
                last_writer[target] = index
        return dependencies

    @staticmethod
    def _form_semantic_key(form: dict[str, Any]) -> str:
        return f"{form.get('form')}|{form.get('symbol')}|{len(form.get('operands', []))}"

    def _candidate_labels_for_form(
        self,
        form: dict[str, Any],
        local_model: SemanticModel,
        *,
        per_symbol_limit: int = 32,
    ) -> list[str]:
        symbol = str(form.get("symbol"))
        arity = len(form.get("operands", []))
        preferred: list[str] = []
        for semantic in local_model.symbols.values():
            if semantic.symbol == symbol and semantic.arity == arity:
                preferred.extend(c.label for c in semantic.candidates if c.score > 0)
        ordered = []
        for label in preferred:
            if label not in ordered:
                ordered.append(label)
        for label, spec in sorted(self.semantic_primitives.items()):
            if spec["arity"] == arity and label not in ordered:
                ordered.append(label)
        return ordered[:max(1, per_symbol_limit)]

    def _infer_program_candidates(
        self,
        forms: list[dict[str, Any]],
        observations: list[Any],
        *,
        local_model: SemanticModel,
        max_candidates: int,
        max_combinations: int,
    ) -> list[ProgramSemanticCandidate]:
        unique_forms: dict[str, dict[str, Any]] = {}
        for form in forms:
            if form.get("target") is None:
                continue
            unique_forms.setdefault(self._form_semantic_key(form), form)
        if not unique_forms:
            return []

        keys = sorted(unique_forms)
        domains = [self._candidate_labels_for_form(unique_forms[key], local_model) for key in keys]
        if any(not domain for domain in domains):
            return []

        ranked: list[ProgramSemanticCandidate] = []
        searched = 0
        for choice in itertools.product(*domains):
            searched += 1
            if searched > max_combinations:
                break
            mapping = dict(zip(keys, choice))
            matched = 0
            checks = 0
            successful_runs = 0
            total_runs = 0
            for obs in observations:
                if not isinstance(obs, dict) or not self._valid_state_mapping(obs.get("inputs", {})):
                    continue
                expected = self._observation_expected_outputs(obs, forms)
                if not expected:
                    continue
                total_runs += 1
                ok, final_state, _ = self._simulate_trusted_candidate_chain(forms, mapping, obs.get("inputs", {}))
                if not ok:
                    checks += len(expected)
                    continue
                run_ok = True
                for key, value in expected.items():
                    checks += 1
                    if key in final_state and self._semantic_equal(final_state[key], value):
                        matched += 1
                    else:
                        run_ok = False
                if run_ok:
                    successful_runs += 1
            if checks == 0:
                continue
            score = matched / checks
            material = json.dumps(mapping, sort_keys=True, ensure_ascii=False, separators=(",", ":"))
            digest = hashlib.sha256(material.encode("utf-8")).hexdigest()
            ranked.append(ProgramSemanticCandidate(
                mapping=mapping,
                score=round(score, 6),
                matched_checks=matched,
                total_checks=checks,
                successful_runs=successful_runs,
                total_runs=total_runs,
                behavioral_digest=digest,
                meta={
                    "search_rank_material": "trusted-primitive-composition",
                    "unknown_code_executed": False,
                },
            ))

        ranked.sort(
            key=lambda c: (c.score, c.successful_runs, c.matched_checks, c.behavioral_digest),
            reverse=True,
        )
        if not ranked:
            return []
        best = ranked[0].score
        # Keep the strongest candidates first, including ties that reveal ambiguity.
        useful = [c for c in ranked if c.score >= max(0.5, best - 0.2)]
        return useful[:max(1, max_candidates)]

    def _simulate_trusted_candidate_chain(
        self,
        forms: list[dict[str, Any]],
        mapping: dict[str, str],
        inputs: dict[str, Any],
    ) -> tuple[bool, dict[str, Any], list[dict[str, Any]]]:
        state = dict(inputs)
        trace: list[dict[str, Any]] = []
        for index, form in enumerate(forms):
            target = form.get("target")
            if not isinstance(target, str):
                return False, state, trace
            label = mapping.get(self._form_semantic_key(form))
            spec = self.semantic_primitives.get(label or "")
            if spec is None:
                return False, state, trace
            args: list[Any] = []
            for operand in form.get("operands", []):
                ok, value = self._resolve_semantic_operand(operand, state)
                if not ok:
                    return False, state, trace
                args.append(value)
            ok, value = self._apply_semantic_primitive(spec["function"], tuple(args))
            if not ok or not self._is_safe_semantic_value(value):
                return False, state, trace
            before_digest = self._state_digest(state)
            state[target] = value
            trace.append({
                "instruction": index,
                "line": form.get("line"),
                "symbol": form.get("symbol"),
                "semantic": label,
                "target": target,
                "after_value": self._canonical_semantic_value(value),
                "before_digest": before_digest,
                "after_digest": self._state_digest(state),
            })
        return True, state, trace

    def _observation_expected_outputs(
        self,
        observation: dict[str, Any],
        forms: list[dict[str, Any]],
    ) -> dict[str, Any]:
        outputs = observation.get("outputs")
        if isinstance(outputs, dict):
            return {
                str(k): v for k, v in outputs.items()
                if isinstance(k, str) and self._is_safe_semantic_value(v)
            }
        for key in ("output", "expected"):
            if key in observation and self._is_safe_semantic_value(observation[key]):
                last_target = next(
                    (f.get("target") for f in reversed(forms) if isinstance(f.get("target"), str)),
                    None,
                )
                return {last_target: observation[key]} if isinstance(last_target, str) else {}
        return {}

    def _install_builtin_semantic_primitives(self) -> None:
        def numeric_pair(a: Any, b: Any) -> tuple[float | int, float | int]:
            if type(a) not in (int, float) or type(b) not in (int, float):
                raise TypeError
            return a, b

        def ints(a: Any, b: Any) -> tuple[int, int]:
            if type(a) is not int or type(b) is not int:
                raise TypeError
            return a, b

        def add(a: Any, b: Any) -> Any:
            x, y = numeric_pair(a, b); return x + y
        def sub(a: Any, b: Any) -> Any:
            x, y = numeric_pair(a, b); return x - y
        def mul(a: Any, b: Any) -> Any:
            x, y = numeric_pair(a, b); return x * y
        def div(a: Any, b: Any) -> Any:
            x, y = numeric_pair(a, b)
            if y == 0: raise ZeroDivisionError
            return x / y
        def floordiv(a: Any, b: Any) -> Any:
            x, y = numeric_pair(a, b)
            if y == 0: raise ZeroDivisionError
            return x // y
        def mod(a: Any, b: Any) -> Any:
            x, y = numeric_pair(a, b)
            if y == 0: raise ZeroDivisionError
            return x % y
        def power(a: Any, b: Any) -> Any:
            x, y = numeric_pair(a, b)
            if abs(float(x)) > 1e6 or abs(float(y)) > 16: raise ValueError
            value = x ** y
            if isinstance(value, complex) or (isinstance(value, float) and not math.isfinite(value)):
                raise ValueError
            return value
        def absolute_difference(a: Any, b: Any) -> Any:
            x, y = numeric_pair(a, b); return abs(x - y)
        def minimum(a: Any, b: Any) -> Any:
            x, y = numeric_pair(a, b); return min(x, y)
        def maximum(a: Any, b: Any) -> Any:
            x, y = numeric_pair(a, b); return max(x, y)
        def bit_and(a: Any, b: Any) -> Any:
            x, y = ints(a, b); return x & y
        def bit_or(a: Any, b: Any) -> Any:
            x, y = ints(a, b); return x | y
        def bit_xor(a: Any, b: Any) -> Any:
            x, y = ints(a, b); return x ^ y
        def shift_left(a: Any, b: Any) -> Any:
            x, y = ints(a, b)
            if y < 0 or y > 63: raise ValueError
            return x << y
        def shift_right(a: Any, b: Any) -> Any:
            x, y = ints(a, b)
            if y < 0 or y > 63: raise ValueError
            return x >> y
        def equal(a: Any, b: Any) -> Any:
            return self._semantic_equal(a, b)
        def not_equal(a: Any, b: Any) -> Any:
            return not self._semantic_equal(a, b)
        def less(a: Any, b: Any) -> Any:
            x, y = numeric_pair(a, b); return x < y
        def less_equal(a: Any, b: Any) -> Any:
            x, y = numeric_pair(a, b); return x <= y
        def greater(a: Any, b: Any) -> Any:
            x, y = numeric_pair(a, b); return x > y
        def greater_equal(a: Any, b: Any) -> Any:
            x, y = numeric_pair(a, b); return x >= y
        def bool_and(a: Any, b: Any) -> Any:
            if type(a) is not bool or type(b) is not bool: raise TypeError
            return a and b
        def bool_or(a: Any, b: Any) -> Any:
            if type(a) is not bool or type(b) is not bool: raise TypeError
            return a or b
        def bool_xor(a: Any, b: Any) -> Any:
            if type(a) is not bool or type(b) is not bool: raise TypeError
            return bool(a) ^ bool(b)
        def concatenate(a: Any, b: Any) -> Any:
            if type(a) is not type(b) or type(a) not in (str, bytes, list, tuple):
                raise TypeError
            return a + b
        def merge_dict(a: Any, b: Any) -> Any:
            if type(a) is not dict or type(b) is not dict: raise TypeError
            out = dict(a); out.update(b); return out
        def left(a: Any, b: Any) -> Any:
            return a
        def right(a: Any, b: Any) -> Any:
            return b
        def pair_list(a: Any, b: Any) -> Any:
            return [a, b]
        def pair_tuple(a: Any, b: Any) -> Any:
            return (a, b)
        def unary_identity(a: Any) -> Any:
            return a
        def unary_negate(a: Any) -> Any:
            if type(a) not in (int, float): raise TypeError
            return -a
        def unary_abs(a: Any) -> Any:
            if type(a) not in (int, float): raise TypeError
            return abs(a)
        def unary_increment(a: Any) -> Any:
            if type(a) not in (int, float): raise TypeError
            return a + 1
        def unary_decrement(a: Any) -> Any:
            if type(a) not in (int, float): raise TypeError
            return a - 1
        def unary_bool_not(a: Any) -> Any:
            if type(a) is not bool: raise TypeError
            return not a
        def unary_bit_not(a: Any) -> Any:
            if type(a) is not int: raise TypeError
            return ~a
        def unary_length(a: Any) -> Any:
            if type(a) not in (str, bytes, list, tuple, dict): raise TypeError
            return len(a)

        builtins = [
            ("numeric.add", add, "arithmetic", True),
            ("numeric.subtract", sub, "arithmetic", False),
            ("numeric.multiply", mul, "arithmetic", True),
            ("numeric.divide", div, "arithmetic", False),
            ("numeric.floor_divide", floordiv, "arithmetic", False),
            ("numeric.modulo", mod, "arithmetic", False),
            ("numeric.power", power, "arithmetic", False),
            ("numeric.absolute_difference", absolute_difference, "arithmetic", True),
            ("numeric.minimum", minimum, "selection", True),
            ("numeric.maximum", maximum, "selection", True),
            ("integer.bit_and", bit_and, "bitwise", True),
            ("integer.bit_or", bit_or, "bitwise", True),
            ("integer.bit_xor", bit_xor, "bitwise", True),
            ("integer.shift_left", shift_left, "bitwise", False),
            ("integer.shift_right", shift_right, "bitwise", False),
            ("relation.equal", equal, "relation", True),
            ("relation.not_equal", not_equal, "relation", True),
            ("relation.less", less, "relation", False),
            ("relation.less_equal", less_equal, "relation", False),
            ("relation.greater", greater, "relation", False),
            ("relation.greater_equal", greater_equal, "relation", False),
            ("boolean.and", bool_and, "boolean", True),
            ("boolean.or", bool_or, "boolean", True),
            ("boolean.xor", bool_xor, "boolean", True),
            ("sequence.concatenate", concatenate, "sequence", False),
            ("mapping.merge_right", merge_dict, "mapping", False),
            ("projection.left", left, "projection", False),
            ("projection.right", right, "projection", False),
            ("construction.list_pair", pair_list, "construction", False),
            ("construction.tuple_pair", pair_tuple, "construction", False),
        ]
        for label, function, category, commutative in builtins:
            self.register_semantic_primitive(
                label,
                function,
                arity=2,
                category=category,
                commutative=commutative,
            )

        unary_builtins = [
            ("unary.identity", unary_identity, "projection"),
            ("numeric.negate", unary_negate, "arithmetic"),
            ("numeric.absolute", unary_abs, "arithmetic"),
            ("numeric.increment", unary_increment, "arithmetic"),
            ("numeric.decrement", unary_decrement, "arithmetic"),
            ("boolean.not", unary_bool_not, "boolean"),
            ("integer.bit_not", unary_bit_not, "bitwise"),
            ("sequence.length", unary_length, "sequence"),
        ]
        for label, function, category in unary_builtins:
            self.register_semantic_primitive(label, function, arity=1, category=category)

    @classmethod
    def _is_safe_semantic_value(cls, value: Any, *, depth: int = 0) -> bool:
        if depth > 8:
            return False
        if type(value) in cls.SAFE_SCALAR_TYPES:
            return not (type(value) is float and (math.isnan(value) or math.isinf(value)))
        if type(value) in (list, tuple):
            return len(value) <= 1024 and all(cls._is_safe_semantic_value(v, depth=depth + 1) for v in value)
        if type(value) is dict:
            return len(value) <= 1024 and all(
                type(k) in (str, int, float, bool, type(None))
                and cls._is_safe_semantic_value(v, depth=depth + 1)
                for k, v in value.items()
            )
        return False

    @classmethod
    def _canonical_semantic_value(cls, value: Any) -> Any:
        if type(value) is bytes:
            return {"type": "bytes", "base64": base64.b64encode(value).decode("ascii")}
        if type(value) is tuple:
            return {"type": "tuple", "items": [cls._canonical_semantic_value(v) for v in value]}
        if type(value) is list:
            return {"type": "list", "items": [cls._canonical_semantic_value(v) for v in value]}
        if type(value) is dict:
            return {
                "type": "dict",
                "items": [
                    [cls._canonical_semantic_value(k), cls._canonical_semantic_value(v)]
                    for k, v in sorted(value.items(), key=lambda kv: repr(kv[0]))
                ],
            }
        return {"type": type(value).__name__, "value": value}

    @classmethod
    def _semantic_equal(cls, left: Any, right: Any) -> bool:
        if type(left) is float or type(right) is float:
            if type(left) not in (int, float) or type(right) not in (int, float):
                return False
            if type(left) is bool or type(right) is bool:
                return False
            if not (math.isfinite(float(left)) and math.isfinite(float(right))):
                return False
            return math.isclose(float(left), float(right), rel_tol=1e-9, abs_tol=1e-12)
        return cls._canonical_semantic_value(left) == cls._canonical_semantic_value(right)

    @staticmethod
    def _apply_semantic_primitive(function: Callable[..., Any], args: tuple[Any, ...]) -> tuple[bool, Any]:
        try:
            value = function(*args)
        except (ArithmeticError, LookupError, TypeError, ValueError, OverflowError):
            return False, None
        except Exception:
            # Third-party registered host primitives are contained as hypotheses;
            # an unexpected failure never aborts reading the unknown code.
            return False, None
        return True, value

    def _primitive_behavioral_digest(self, function: Callable[..., Any], arity: int) -> str:
        if arity == 1:
            probes: list[tuple[Any, ...]] = [
                (-3,), (0,), (2,), (7,), (True,), (False,),
                ("",), ("abc",), ([1, 2],), ([],), ({"a": 1},),
            ]
        elif arity == 2:
            probes = [
                (-2, 3), (0, 5), (2, 2), (7, 3), (9, 1),
                (True, False), (False, True),
                ("a", "b"), ("xy", "z"),
                ([1], [2, 3]), ((1,), (2,)),
                ({"a": 1}, {"b": 2}),
            ]
        else:
            # Custom higher-arity semantics can still participate in scoring.
            # A digest cannot be meaningfully sampled without a domain, so it
            # records only arity until the host adds a richer primitive set.
            return hashlib.sha256(f"unsampled-arity:{arity}".encode("utf-8")).hexdigest()

        behavior: list[Any] = []
        for args in probes:
            ok, value = self._apply_semantic_primitive(function, args)
            behavior.append(
                {"ok": ok, "value": self._canonical_semantic_value(value) if ok and self._is_safe_semantic_value(value) else None}
            )
        material = json.dumps(behavior, sort_keys=True, ensure_ascii=False, separators=(",", ":"), default=str)
        return hashlib.sha256(material.encode("utf-8")).hexdigest()

    def _extract_semantic_forms(
        self,
        code: str,
        *,
        inputs: dict[str, Any] | None = None,
    ) -> list[dict[str, Any]]:
        forms: list[dict[str, Any]] = []
        input_names = set((inputs or {}).keys())
        for line_no, raw_line in enumerate(code.splitlines(), 1):
            tokens = [
                t for t in self._tokenize(raw_line)
                if t["kind"] not in {"line_comment", "block_comment", "directive"}
            ]
            while tokens and tokens[-1]["kind"] == "punct" and tokens[-1]["value"] == ";":
                tokens.pop()
            if not tokens:
                continue

            target: str | None = None
            expr = tokens
            for i, tok in enumerate(tokens):
                if str(tok["value"]) in self.ASSIGN_SYMBOLS and i > 0 and i + 1 < len(tokens):
                    if tokens[i - 1]["kind"] == "identifier":
                        target = str(tokens[i - 1]["value"])
                    expr = tokens[i + 1:]
                    break

            if not expr:
                continue

            # NAME(a,b), opcode(a,b), or machine-symbol(a,b)
            if len(expr) >= 4 and expr[1]["value"] == "(" and expr[-1]["value"] == ")":
                args = self._split_simple_arguments(expr[2:-1])
                if len(args) >= 1 and all(len(part) == 1 for part in args):
                    forms.append({
                        "symbol": str(expr[0]["value"]),
                        "form": "call",
                        "operands": [part[0] for part in args],
                        "operand_names": [str(part[0]["value"]) for part in args],
                        "target": target,
                        "line": line_no,
                        "source": raw_line.strip(),
                    })
                    continue

            # [OPCODE, a, b] is common in compact machine-native encodings.
            if len(expr) >= 5 and expr[0]["value"] == "[" and expr[-1]["value"] == "]":
                parts = self._split_simple_arguments(expr[1:-1])
                if len(parts) >= 2 and len(parts[0]) == 1 and all(len(part) == 1 for part in parts[1:]):
                    forms.append({
                        "symbol": str(parts[0][0]["value"]),
                        "form": "vector-opcode",
                        "operands": [part[0] for part in parts[1:]],
                        "operand_names": [str(part[0]["value"]) for part in parts[1:]],
                        "target": target,
                        "line": line_no,
                        "source": raw_line.strip(),
                    })
                    continue

            # Unary machine forms: ⊗ a or K7 a.
            if len(expr) == 2:
                first, second = expr
                first_value = str(first["value"])
                second_value = str(second["value"])
                if first["kind"] in {"operator", "symbol"} or (
                    first["kind"] in {"identifier", "number"}
                    and first_value not in input_names
                    and second_value in input_names
                ):
                    forms.append({
                        "symbol": first_value,
                        "form": "prefix-unary",
                        "operands": [second],
                        "operand_names": [second_value],
                        "target": target,
                        "line": line_no,
                        "source": raw_line.strip(),
                    })
                    continue

            # a ⊗ b.  For word-like machine operators, use known input names to
            # distinguish ``a K7 b`` from the prefix form ``K7 a b``.
            if len(expr) == 3:
                first, middle, last = expr
                first_value = str(first["value"])
                middle_value = str(middle["value"])
                last_value = str(last["value"])
                infix = middle["kind"] in {"operator", "symbol"} or (
                    middle["kind"] in {"identifier", "number"}
                    and first_value in input_names
                    and last_value in input_names
                    and middle_value not in input_names
                )
                if infix:
                    forms.append({
                        "symbol": middle_value,
                        "form": "infix",
                        "operands": [first, last],
                        "operand_names": [first_value, last_value],
                        "target": target,
                        "line": line_no,
                        "source": raw_line.strip(),
                    })
                    continue

                prefix = (
                    first["kind"] in {"identifier", "number", "symbol", "operator"}
                    and first_value not in input_names
                    and middle_value in input_names
                    and last_value in input_names
                )
                if prefix:
                    forms.append({
                        "symbol": first_value,
                        "form": "prefix",
                        "operands": [middle, last],
                        "operand_names": [middle_value, last_value],
                        "target": target,
                        "line": line_no,
                        "source": raw_line.strip(),
                    })
        return forms

    @staticmethod
    def _split_simple_arguments(tokens: list[dict[str, Any]]) -> list[list[dict[str, Any]]]:
        parts: list[list[dict[str, Any]]] = []
        current: list[dict[str, Any]] = []
        depth = 0
        pairs = {"(": ")", "[": "]", "{": "}"}
        opens = set(pairs)
        closes = set(pairs.values())
        for tok in tokens:
            value = tok["value"]
            if value in opens:
                depth += 1
            elif value in closes:
                depth = max(0, depth - 1)
            if value == "," and depth == 0:
                parts.append(current)
                current = []
            else:
                current.append(tok)
        if current:
            parts.append(current)
        return parts

    def _resolve_semantic_operand(self, token: dict[str, Any], inputs: dict[str, Any]) -> tuple[bool, Any]:
        kind = token.get("kind")
        raw = str(token.get("value", ""))
        if kind == "identifier":
            if raw in inputs:
                return True, inputs[raw]
            low = raw.lower()
            if low in {"true", "false"}:
                return True, low == "true"
            if low in {"none", "null", "nil"}:
                return True, None
            return False, None
        if kind == "number":
            cleaned = raw.replace("_", "")
            try:
                if any(c in cleaned.lower() for c in (".", "e")) and not cleaned.lower().startswith(("0x", "0b", "0o")):
                    return True, float(cleaned)
                return True, int(cleaned, 0)
            except ValueError:
                return False, None
        if kind in {"string", "triple_string"}:
            try:
                value = ast.literal_eval(raw)
            except (ValueError, SyntaxError):
                return False, None
            return (True, value) if self._is_safe_semantic_value(value) else (False, None)
        return False, None

    @staticmethod
    def _expected_for_semantic_form(
        observation: dict[str, Any],
        form: dict[str, Any],
        form_count: int,
    ) -> tuple[bool, Any]:
        target = form.get("target")
        outputs = observation.get("outputs")
        if isinstance(outputs, dict) and target is not None and target in outputs:
            return True, outputs[target]

        if "output" in observation:
            value = observation["output"]
            if form_count == 1:
                return True, value
            if isinstance(value, dict) and target is not None and target in value:
                return True, value[target]

        if "expected" in observation:
            value = observation["expected"]
            if form_count == 1:
                return True, value
            if isinstance(value, dict) and target is not None and target in value:
                return True, value[target]

        return False, None

    def _suggest_discriminating_probes(
        self,
        ranked: list[SemanticCandidate],
        *,
        arity: int,
        operand_names: tuple[str, ...] = (),
        max_probes: int = 5,
    ) -> list[dict[str, Any]]:
        if arity != 2 or not ranked:
            return []
        best = ranked[0].score
        plausible = [c for c in ranked if c.score > 0 and c.score >= max(0.5, best - 0.15)][:5]
        if len(plausible) < 2:
            return []

        name_a = operand_names[0] if len(operand_names) > 0 else "arg0"
        name_b = operand_names[1] if len(operand_names) > 1 else "arg1"
        probe_pairs: list[tuple[Any, Any]] = [
            (-3, 2), (2, -3), (0, 4), (1, 5), (2, 3), (3, 2),
            (4, 4), (7, 2), (8, 3), (9, 4),
            (True, False), (False, True),
            ("a", "b"), ("ab", "c"),
            ([1], [2]), ([1, 2], [3]),
        ]
        output: list[dict[str, Any]] = []
        seen: set[str] = set()
        for pair in probe_pairs:
            predictions: dict[str, Any] = {}
            distinct: set[str] = set()
            for candidate in plausible:
                spec = self.semantic_primitives.get(candidate.label)
                if not spec:
                    continue
                ok, value = self._apply_semantic_primitive(spec["function"], pair)
                if not ok or not self._is_safe_semantic_value(value):
                    continue
                canonical = self._canonical_semantic_value(value)
                encoded = json.dumps(canonical, sort_keys=True, ensure_ascii=False, default=str)
                distinct.add(encoded)
                predictions[candidate.semantic_id] = canonical
            if len(distinct) < 2:
                continue
            key = json.dumps([self._canonical_semantic_value(x) for x in pair], sort_keys=True, ensure_ascii=False)
            if key in seen:
                continue
            seen.add(key)
            output.append({
                "inputs": {name_a: self._canonical_semantic_value(pair[0]), name_b: self._canonical_semantic_value(pair[1])},
                "predictions": predictions,
                "purpose": "distinguish-current-semantic-candidates",
            })
            if len(output) >= max_probes:
                break
        return output

    def read_file(self, path: str | Path) -> ReadResult:
        p = Path(path)
        return self.read(p.read_bytes(), filename=p.name)

    def read_many(
        self,
        samples: Iterable[bytes | bytearray | memoryview | str],
        *,
        language_hint: str | None = None,
    ) -> list[ReadResult]:
        """Read a corpus without executing any member of it."""
        return [self.read(sample, language_hint=language_hint) for sample in samples]

    def learn_grammar(
        self,
        samples: Iterable[bytes | bytearray | memoryview | str],
        *,
        language_hint: str | None = None,
        max_rules: int = 128,
    ) -> GrammarModel:
        """
        Infer a surface grammar from multiple samples.

        This learns recurring token-shape statements and operator contexts.
        It deliberately does not claim meaning that cannot be established from
        syntax alone. The result is useful for machine-created/unknown languages.
        """
        texts: list[str] = []
        detected: Counter[str] = Counter()
        all_tokens: list[list[dict[str, Any]]] = []

        for sample in samples:
            raw = sample.encode("utf-8") if isinstance(sample, str) else bytes(sample)
            text, _, is_binary = self._decode_lossless(raw)
            lang, _, _ = self._detect_language(raw, text, None, is_binary, language_hint)
            detected[lang] += 1
            if is_binary:
                continue
            texts.append(text)
            all_tokens.append(self._tokenize(text))

        language = detected.most_common(1)[0][0] if detected else (language_hint or "unknown-text")
        rule_counts: Counter[tuple[str, ...]] = Counter()
        examples: dict[tuple[str, ...], list[str]] = defaultdict(list)
        vocab: Counter[str] = Counter()
        op_contexts: dict[str, Counter[tuple[str, str]]] = defaultdict(Counter)
        op_positions: dict[str, list[float]] = defaultdict(list)
        total_statements = 0
        token_count = 0

        for text, tokens in zip(texts, all_tokens):
            token_count += len(tokens)
            for tok in tokens:
                if tok["kind"] == "identifier":
                    vocab[str(tok["value"])] += 1

            for stmt in self._statement_index_groups(tokens):
                if not stmt:
                    continue
                pattern = tuple(self._token_shape(tokens[i]) for i in stmt)
                rule_counts[pattern] += 1
                total_statements += 1
                if len(examples[pattern]) < 4:
                    examples[pattern].append(" ".join(str(tokens[i]["value"]) for i in stmt)[:300])

            for i, tok in enumerate(tokens):
                if tok["kind"] not in {"operator", "symbol"}:
                    continue
                op = str(tok["value"])
                left = self._token_shape(tokens[i - 1]) if i > 0 else "<START>"
                right = self._token_shape(tokens[i + 1]) if i + 1 < len(tokens) else "<END>"
                op_contexts[op][(left, right)] += 1
                op_positions[op].append(i / max(1, len(tokens) - 1))

        rules: list[GrammarRule] = []
        for pattern, count in rule_counts.most_common(max_rules):
            rules.append(GrammarRule(
                pattern=pattern,
                count=count,
                probability=count / max(1, total_statements),
                examples=examples[pattern],
            ))

        profiles: dict[str, dict[str, Any]] = {}
        for op, contexts in sorted(op_contexts.items()):
            positions = op_positions[op]
            profiles[op] = {
                "count": sum(contexts.values()),
                "top_contexts": [
                    {"left": a, "right": b, "count": c}
                    for (a, b), c in contexts.most_common(12)
                ],
                "mean_relative_position": round(statistics.fmean(positions), 6) if positions else None,
                "role_hypothesis": self._operator_role_hypothesis(contexts),
            }

        return GrammarModel(
            language=language,
            sample_count=len(texts),
            token_count=token_count,
            rules=rules,
            operator_profiles=profiles,
            vocabulary=dict(vocab.most_common(256)),
            metadata={
                "reader_version": self.VERSION,
                "semantic_status": "surface-grammar-only",
                "detected_languages": dict(detected),
                "statement_count": total_statements,
            },
        )

    def compare(
        self,
        left: bytes | bytearray | memoryview | str,
        right: bytes | bytearray | memoryview | str,
    ) -> dict[str, Any]:
        """Compare two programs by normalized structure rather than spelling."""
        lraw = left.encode("utf-8") if isinstance(left, str) else bytes(left)
        rraw = right.encode("utf-8") if isinstance(right, str) else bytes(right)
        lt, _, lb = self._decode_lossless(lraw)
        rt, _, rb = self._decode_lossless(rraw)
        if lb or rb:
            return {
                "comparable": False,
                "reason": "binary-input",
                "left_binary": lb,
                "right_binary": rb,
            }

        ls = self._structural_fingerprint(lt)
        rs = self._structural_fingerprint(rt)
        lset, rset = set(ls), set(rs)
        jaccard = len(lset & rset) / max(1, len(lset | rset))
        seq = self._lcs_ratio(ls, rs)
        return {
            "comparable": True,
            "structural_jaccard": round(jaccard, 6),
            "ordered_similarity": round(seq, 6),
            "similarity": round((jaccard + seq) / 2.0, 6),
            "left_fingerprint": ls[:256],
            "right_fingerprint": rs[:256],
        }

    def read(
        self,
        payload: bytes | bytearray | memoryview | str,
        filename: str | None = None,
        *,
        language_hint: str | None = None,
    ) -> ReadResult:
        raw = payload.encode("utf-8") if isinstance(payload, str) else bytes(payload)
        digest = hashlib.sha256(raw).hexdigest()

        text, encoding, is_binary = self._decode_lossless(raw)
        detected, confidence, evidence = self._detect_language(
            raw, text, filename, is_binary, language_hint
        )

        parser_error: dict[str, str] | None = None
        if is_binary or detected in {"wasm", "jvm-bytecode", "android-dex", "llvm-bitcode", "elf-binary", "pe-binary", "mach-o", "binary", "zip-container"}:
            is_binary = True
            nodes = self._parse_binary(raw, detected)
            parse_level = "bytes"
        else:
            parser = self.parsers.get(detected)
            parse_level = {"python": "ast", "json": "json_tree", "jsonl": "json_lines",
                           "xml": "xml_tree", "ai-native": "graph_syntax"}.get(
                               detected, "custom_syntax" if parser else "tokens")
            if parser is not None:
                try:
                    nodes = parser(text)
                except Exception as exc:  # preserve input even when a specialist fails
                    parser_error = {"type": type(exc).__name__, "message": str(exc)}
                    nodes = self._parse_generic(text)
                    parse_level = "tokens"
                    nodes.insert(0, IRNode("parser-error", "parser_error", type(exc).__name__,
                                           [], {"message": str(exc)}))
            else:
                nodes = self._parse_generic(text)

            # Add language-independent structural evidence even for specialist
            # parsers, but do not duplicate every token unless useful.
            # Generic and AI-native parsers already emit this layer. Appending
            # it twice produces duplicate IDs for JS and failed specialists.
            if parser is not None and parser_error is None and detected != "ai-native":
                nodes.extend(self._cross_language_analysis_nodes(text, detected))
            elif parse_level == "tokens":
                for node in nodes:
                    if node.kind == "canonical.statement":
                        node.meta["language"] = detected

        ids = Counter(n.id for n in nodes)
        metadata = {
            "reader_version": self.VERSION,
            "size_bytes": len(raw),
            "filename": filename,
            "binary": bool(is_binary),
            "node_count": len(nodes),
            "language_confidence": round(confidence, 4),
            "language_evidence": evidence,
            "byte_entropy": round(self._entropy(raw), 6),
            "safe_mode": "read-only/no-execution",
            "executes_source": False,
            "parse_level": parse_level,
            "unresolved_links": sorted({link for n in nodes for link in n.links if link not in ids}),
            "duplicate_node_ids": sorted(nid for nid, count in ids.items() if count > 1),
            "implicit_symbols": sorted(n.value for n in nodes if n.kind == "ai.atom" and n.meta.get("implicit")),
        }
        if parser_error:
            metadata["parser_error"] = parser_error

        return ReadResult(
            sha256=digest,
            language=detected,
            encoding=encoding,
            lossless_source=text,
            nodes=nodes,
            metadata=metadata,
            source_base64=base64.b64encode(raw).decode("ascii"),
        )

    # ---------------------------- ingestion -----------------------------

    def _decode_lossless(self, raw: bytes) -> tuple[str, str, bool]:
        if not raw:
            return "", "utf-8", False

        # BOM-first decoding.
        bom_decoders = (
            (b"\xef\xbb\xbf", "utf-8-sig"),
            (b"\xff\xfe\x00\x00", "utf-32"),
            (b"\x00\x00\xfe\xff", "utf-32"),
            (b"\xff\xfe", "utf-16"),
            (b"\xfe\xff", "utf-16"),
        )
        for bom, enc in bom_decoders:
            if raw.startswith(bom):
                try:
                    return raw.decode(enc), enc, False
                except UnicodeDecodeError:
                    break

        magic = self._magic_language(raw)
        if magic in {"wasm", "jvm-bytecode", "android-dex", "llvm-bitcode", "elf-binary", "pe-binary", "mach-o", "zip-container"}:
            return base64.b64encode(raw).decode("ascii"), "base64", True

        # UTF-8 is by far the most useful default.
        try:
            text = raw.decode("utf-8")
            if not self._looks_binary_text(text):
                return text, "utf-8", False
        except UnicodeDecodeError:
            pass

        # UTF-16 without BOM: infer from alternating NUL layout.
        if len(raw) >= 4:
            even_nul = sum(raw[i] == 0 for i in range(0, len(raw), 2))
            odd_nul = sum(raw[i] == 0 for i in range(1, len(raw), 2))
            half = max(1, len(raw) // 2)
            guesses: list[str] = []
            if odd_nul / half > 0.30:
                guesses.append("utf-16-le")
            if even_nul / half > 0.30:
                guesses.append("utf-16-be")
            for enc in guesses:
                try:
                    text = raw.decode(enc)
                    if not self._looks_binary_text(text):
                        return text, enc, False
                except UnicodeDecodeError:
                    pass

        # latin-1 gives a reversible 1:1 byte mapping. Decide binary after it.
        text = raw.decode("latin-1")
        if self._looks_binary_text(text):
            return base64.b64encode(raw).decode("ascii"), "base64", True
        return text, "latin-1", False

    @staticmethod
    def _looks_binary_text(text: str) -> bool:
        if not text:
            return False
        nul_ratio = text.count("\x00") / len(text)
        controls = sum((ord(ch) < 32 and ch not in "\n\r\t\f\b") for ch in text)
        replacement = text.count("\ufffd")
        return nul_ratio > 0.01 or controls / len(text) > 0.05 or replacement / len(text) > 0.01

    # ------------------------- language detection ------------------------

    def _detect_language(
        self,
        raw: bytes,
        text: str,
        filename: str | None,
        is_binary: bool,
        language_hint: str | None,
    ) -> tuple[str, float, list[str]]:
        evidence: list[str] = []

        if language_hint:
            hint = language_hint.lower().strip()
            evidence.append("explicit-language-hint")
            return hint, 0.99, evidence

        magic = self._magic_language(raw)
        if magic:
            evidence.append(f"magic:{magic}")
            return magic, 1.0, evidence

        ext_lang: str | None = None
        if filename:
            ext = Path(filename).suffix.lower()
            ext_lang = self.EXTENSIONS.get(ext)
            if ext_lang:
                evidence.append(f"extension:{ext}")
                if is_binary:
                    return ext_lang, 0.97, evidence

        if is_binary:
            return ext_lang or "binary", 0.85 if ext_lang else 0.70, evidence or ["binary-profile"]

        s = text.lstrip()

        # Shebang has stronger evidence than extension.
        first = text.splitlines()[0] if text.splitlines() else ""
        shebang_map = {
            "python": "python", "node": "javascript", "deno": "javascript",
            "bash": "shell", "sh": "shell", "zsh": "shell", "ruby": "ruby",
            "perl": "perl", "php": "php",
        }
        if first.startswith("#!"):
            low = first.lower()
            for needle, lang in shebang_map.items():
                if needle in low:
                    evidence.append(f"shebang:{needle}")
                    return lang, 0.99, evidence

        if s.startswith(("{", "[")):
            try:
                json.loads(text)
                evidence.append("valid-json")
                return "json", 0.995, evidence
            except Exception:
                pass

        # XML/HTML distinction.
        if re.match(r"^\s*<\?xml\b", text, re.I):
            evidence.append("xml-declaration")
            return "xml", 0.99, evidence
        # Treat HTML root markers as strong evidence only when they occur at
        # the document root. Searching the entire source can self-match regex
        # literals or string constants inside non-HTML programs.
        if re.match(r"^\s*(?:<!doctype\s+html[^>]*>\s*)?<html\b", text, re.I | re.S):
            evidence.append("html-root")
            return "html", 0.98, evidence

        scores: dict[str, float] = defaultdict(float)
        if ext_lang:
            scores[ext_lang] += 4.0

        signatures = {
            "python": [
                (r"^\s*(?:async\s+)?def\s+\w+\s*\(", 5),
                (r"^\s*class\s+\w+\s*(?:\([^\n]*\))?\s*:", 5),
                (r"^\s*(?:from\s+\S+\s+import|import\s+\S+)", 2),
            ],
            "javascript": [
                (r"\b(?:function|const|let|var)\b", 2),
                (r"=>", 2), (r"\bconsole\.log\s*\(", 2),
            ],
            "typescript": [(r"\binterface\s+\w+\b", 4), (r"\btype\s+\w+\s*=", 3)],
            "c": [(r"^\s*#\s*include\s*[<\"]", 5), (r"\b(?:int|char|void|double)\s+\w+\s*\(", 2)],
            "cpp": [(r"\bstd::", 4), (r"\btemplate\s*<", 4), (r"\bnamespace\s+\w+", 2)],
            "rust": [(r"\bfn\s+\w+\s*\(", 3), (r"\blet\s+mut\b", 3), (r"\bimpl\b", 2)],
            "go": [(r"^\s*package\s+\w+", 5), (r"\bfunc\s+\w+\s*\(", 4)],
            "java": [(r"\bpublic\s+(?:static\s+)?(?:class|interface|enum)\b", 4), (r"\bSystem\.out\.print", 3)],
            "sql": [(r"\bSELECT\b.+\bFROM\b", 4), (r"\bCREATE\s+TABLE\b", 4)],
            "shell": [(r"\b(?:fi|then|elif|esac)\b", 3), (r"\$\{?[A-Za-z_]", 2)],
            "ai-native": [
                (r"^\s*[A-Za-z0-9_.-]+\s*:\s*$", 2),
                (r"^\s*[A-Za-z0-9_.-]+\s*(?:->|=>)\s*[A-Za-z0-9_.-]+\s*$", 4),
                (r"^\s*\[[^\n\]]+(?:,[^\n\]]+)+\]\s*$", 2),
            ],
        }
        for lang, rules in signatures.items():
            for pattern, weight in rules:
                if re.search(pattern, text, re.I | re.M | re.S):
                    scores[lang] += weight

        if scores:
            ranked = sorted(scores.items(), key=lambda kv: (-kv[1], kv[0]))
            lang, score = ranked[0]
            # Extension alone should not force a false certainty.
            confidence = min(0.98, 0.45 + score / 12.0)
            evidence.append("signature-score:" + ",".join(f"{k}={v:g}" for k, v in ranked[:4]))
            return lang, confidence, evidence

        if ext_lang:
            evidence.append("extension-only")
            return ext_lang, 0.58, evidence

        return "unknown-text", 0.25, ["no-known-signature"]

    def _magic_language(self, raw: bytes) -> str | None:
        for magic, lang in self.MAGIC:
            if raw.startswith(magic):
                return lang
        return None

    # -------------------------- node utilities ---------------------------

    @staticmethod
    def _jsonable(value: Any) -> Any:
        if isinstance(value, float) and not math.isfinite(value):
            return {"nonfinite_float": repr(value)}
        if value is None or isinstance(value, (str, int, float, bool)):
            return value
        if isinstance(value, bytes):
            return {"base64": base64.b64encode(value).decode("ascii")}
        if isinstance(value, complex):
            return {"real": UniversalCodeReader._jsonable(value.real),
                    "imag": UniversalCodeReader._jsonable(value.imag)}
        if isinstance(value, (list, tuple)):
            return [UniversalCodeReader._jsonable(v) for v in value]
        if isinstance(value, dict):
            return {str(k): UniversalCodeReader._jsonable(v) for k, v in value.items()}
        return repr(value)

    @staticmethod
    def _node_id(*parts: Any) -> str:
        data = "\x1f".join(map(str, parts)).encode("utf-8", "surrogatepass")
        return hashlib.sha256(data).hexdigest()[:20]

    # ------------------------- specialist parsers ------------------------

    def _parse_python(self, text: str) -> list[IRNode]:
        tree = ast.parse(text)
        nodes: list[IRNode] = []
        # Context and operator objects are AST singletons. Each occurrence
        # needs its own path, including the exact ID used by the parent edge.
        pending = [(tree, "$")]
        while pending:
            item, path = pending.pop()
            nid = self._node_id("py", path, type(item).__name__)
            value: Any = None
            if isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                value = item.name
            elif isinstance(item, ast.Name):
                value = item.id
            elif isinstance(item, ast.Attribute):
                value = item.attr
            elif isinstance(item, ast.Constant):
                value = self._jsonable(item.value)

            occurrences = [(child, f"{path}/{index}")
                           for index, child in enumerate(ast.iter_child_nodes(item))]
            children = [self._node_id("py", child_path, type(child).__name__)
                        for child, child_path in occurrences]
            pending.extend(reversed(occurrences))
            meta = {
                "path": path,
                "line": getattr(item, "lineno", None),
                "column": getattr(item, "col_offset", None),
                "end_line": getattr(item, "end_lineno", None),
                "end_column": getattr(item, "end_col_offset", None),
            }
            nodes.append(IRNode(nid, f"python.{type(item).__name__}", value, children, meta))
        return nodes

    def _parse_json(self, text: str) -> list[IRNode]:
        return self._json_object_to_nodes(self._strict_json(text), root="$", family="json")

    @staticmethod
    def _strict_json(text: str) -> Any:
        def pairs(items):
            result = {}
            for key, value in items:
                if key in result:
                    raise ValueError("duplicate JSON key: " + key)
                result[key] = value
            return result

        def reject(value):
            raise ValueError("nonstandard JSON constant: " + value)

        return json.loads(text, object_pairs_hook=pairs, parse_constant=reject)

    def _parse_jsonl(self, text: str) -> list[IRNode]:
        nodes: list[IRNode] = []
        for lineno, line in enumerate(text.splitlines(), 1):
            if not line.strip():
                continue
            value = self._strict_json(line)
            part = self._json_object_to_nodes(value, root=f"$/{lineno}", family="jsonl")
            for node in part:
                node.meta.setdefault("line", lineno)
            nodes.extend(part)
        return nodes

    def _json_object_to_nodes(self, obj: Any, *, root: str, family: str) -> list[IRNode]:
        nodes: list[IRNode] = []

        def walk(value: Any, path: str) -> str:
            nid = self._node_id(family, path)
            links: list[str] = []
            meta: dict[str, Any] = {"path": path}
            if isinstance(value, dict):
                kind = f"{family}.object"
                node_value = None
                meta["keys"] = [str(k) for k in value.keys()]
                for key, child in value.items():
                    segment = str(key).replace("~", "~0").replace("/", "~1")
                    links.append(walk(child, f"{path}/{segment}"))
            elif isinstance(value, list):
                kind = f"{family}.array"
                node_value = None
                for i, child in enumerate(value):
                    links.append(walk(child, f"{path}/{i}"))
            else:
                if isinstance(value, float) and not math.isfinite(value):
                    raise ValueError("JSON number exceeds finite representation")
                kind = f"{family}.{type(value).__name__}"
                node_value = self._jsonable(value)
            nodes.append(IRNode(nid, kind, node_value, links, meta))
            return nid

        walk(obj, root)
        return nodes

    def _parse_xml(self, text: str) -> list[IRNode]:
        root = ET.fromstring(text)
        nodes: list[IRNode] = []
        counter = 0

        def walk(elem: ET.Element, path: str) -> str:
            nonlocal counter
            counter += 1
            nid = self._node_id("xml", counter, path, elem.tag)
            links: list[str] = []
            child_counts: Counter[str] = Counter()
            for child in list(elem):
                child_counts[str(child.tag)] += 1
                links.append(walk(child, f"{path}/{child.tag}[{child_counts[str(child.tag)]}]") )
            value = (elem.text or "").strip() or None
            nodes.append(IRNode(
                nid, "xml.element", value, links,
                {"path": path, "tag": str(elem.tag), "attributes": dict(elem.attrib)},
            ))
            return nid

        walk(root, f"/{root.tag}[1]")
        return nodes

    def _parse_ai_native(self, text: str) -> list[IRNode]:
        """Parse a deliberately loose machine-native graph syntax."""
        nodes: list[IRNode] = []
        current: str | None = None
        known_atoms: dict[str, IRNode] = {}

        def ensure_atom(name: str, lineno: int, implicit: bool = False) -> str:
            nonlocal nodes
            if name not in known_atoms:
                atom = IRNode(
                    id=self._node_id("ai.atom", name),
                    kind="ai.atom",
                    value=name,
                    meta={"line": lineno, "implicit": implicit},
                )
                known_atoms[name] = atom
                nodes.append(atom)
            elif not implicit:
                known_atoms[name].meta["implicit"] = False
            return self._node_id("ai.atom", name)

        for lineno, raw_line in enumerate(text.splitlines(), 1):
            line = raw_line.strip()
            if not line or line.startswith(("#", "//")):
                continue

            m_head = re.fullmatch(r"([\w.$-]+)\s*:\s*", line, re.UNICODE)
            if m_head:
                current = m_head.group(1)
                ensure_atom(current, lineno)
                continue

            # relation -> target OR source relation -> target
            m_edge = re.fullmatch(
                r"(?:(?P<src>[\w.$-]+)\s+)?(?P<rel>[\w.$@:-]+)\s*(?:->|=>)\s*(?P<dst>[\w.$@:-]+)",
                line,
                re.UNICODE,
            )
            if m_edge:
                src = m_edge.group("src") or current
                rel = m_edge.group("rel")
                dst = m_edge.group("dst")
                if src:
                    src_id = ensure_atom(src, lineno, implicit=src != current)
                    dst_id = ensure_atom(dst, lineno, implicit=True)
                    nodes.append(IRNode(
                        id=self._node_id("ai.edge", src, rel, dst, lineno),
                        kind="ai.edge",
                        value=rel,
                        links=[src_id, dst_id],
                        meta={"line": lineno, "source": src, "target": dst},
                    ))
                    continue

            # Vector/tuple-like machine operation: [14, 011F, 27]
            m_vec = re.fullmatch(r"\[(.*)\]", line)
            if m_vec:
                parts = [p.strip() for p in m_vec.group(1).split(",") if p.strip()]
                links: list[str] = []
                if current:
                    links.append(ensure_atom(current, lineno))
                nodes.append(IRNode(
                    id=self._node_id("ai.vector", lineno, *parts),
                    kind="ai.vector",
                    value=parts,
                    links=links,
                    meta={"line": lineno, "arity": len(parts)},
                ))
                continue

            nodes.append(IRNode(
                id=self._node_id("ai.raw", lineno, line),
                kind="ai.raw",
                value=line,
                links=[ensure_atom(current, lineno)] if current else [],
                meta={"line": lineno},
            ))

        # Add learned surface patterns so a receiver can infer new operators.
        nodes.extend(self._cross_language_analysis_nodes(text, "ai-native"))
        return nodes

    # -------------------------- generic parser ---------------------------

    def _tokenize(self, text: str) -> list[dict[str, Any]]:
        """Tokenize permissively, including unfamiliar Unicode operators."""
        line_starts = [0]
        for m in re.finditer("\n", text):
            line_starts.append(m.end())

        raw_tokens: list[dict[str, Any]] = []
        for raw_index, match in enumerate(self.TOKEN_RE.finditer(text)):
            kind = match.lastgroup or "other"
            value = match.group(0)
            if kind == "ws":
                continue
            start, end = match.start(), match.end()
            line_idx = bisect.bisect_right(line_starts, start) - 1
            line = line_idx + 1
            column = start - line_starts[line_idx]

            # Unknown punctuation/symbols are still potentially meaningful
            # machine operators. Preserve them as symbols rather than noise.
            if kind == "other" and value:
                cat = unicodedata.category(value[0])
                if cat.startswith(("S", "P")):
                    kind = "symbol"

            raw_tokens.append({
                "raw_index": raw_index,
                "kind": kind,
                "value": value,
                "start": start,
                "end": end,
                "line": line,
                "column": column,
            })

        # Coalesce adjacent unfamiliar symbols, e.g. ⊗≔ or ⟹⟹.
        merged: list[dict[str, Any]] = []
        for tok in raw_tokens:
            if (
                merged
                and tok["kind"] == "symbol"
                and merged[-1]["kind"] == "symbol"
                and tok["start"] == merged[-1]["end"]
                and tok["line"] == merged[-1]["line"]
            ):
                merged[-1]["value"] += tok["value"]
                merged[-1]["end"] = tok["end"]
                continue
            merged.append(tok)

        for index, tok in enumerate(merged):
            tok["index"] = index
        return merged

    def _parse_generic(self, text: str) -> list[IRNode]:
        """
        Language-independent structural parser.

        Unknown syntax is not discarded. The reader emits token sequence,
        bracket/group relations, statement boundaries, weak call/assignment
        hypotheses, and recurring token-shape patterns. These are evidence, not
        claims of semantic understanding.
        """
        tokens = self._tokenize(text)
        nodes: list[IRNode] = []
        token_ids: list[str] = []

        for tok in tokens:
            nid = self._node_id("token", tok["index"], tok["kind"], tok["value"], tok["start"])
            token_ids.append(nid)
            links = [token_ids[-2]] if len(token_ids) > 1 else []
            meta = {
                "index": tok["index"], "start": tok["start"], "end": tok["end"],
                "line": tok["line"], "column": tok["column"],
            }
            nodes.append(IRNode(nid, f"token.{tok['kind']}", tok["value"], links, meta))

        # Pair nested delimiters and emit explicit group nodes.
        stack: list[tuple[str, int]] = []
        for i, tok in enumerate(tokens):
            val = tok["value"]
            if tok["kind"] == "punct" and val in self.OPEN_TO_CLOSE:
                stack.append((val, i))
            elif tok["kind"] == "punct" and val in self.CLOSE_TO_OPEN:
                expected = self.CLOSE_TO_OPEN[val]
                if stack and stack[-1][0] == expected:
                    opener, j = stack.pop()
                    inner = token_ids[j + 1:i]
                    gid = self._node_id("group", j, i, opener, val)
                    nodes.append(IRNode(
                        gid, "structure.group", f"{opener}{val}",
                        [token_ids[j], *inner, token_ids[i]],
                        {"open_index": j, "close_index": i, "depth_hint": len(stack), "balanced": True},
                    ))
                else:
                    nodes.append(IRNode(
                        self._node_id("unmatched-close", i, val),
                        "structure.unmatched_close", val, [token_ids[i]],
                        {"index": i, "line": tok["line"]},
                    ))
        for opener, j in stack:
            nodes.append(IRNode(
                self._node_id("unmatched-open", j, opener),
                "structure.unmatched_open", opener, [token_ids[j]],
                {"index": j, "line": tokens[j]["line"]},
            ))

        # Statement-ish spans: split on ; and physical newlines indirectly by line.
        by_line: dict[int, list[int]] = defaultdict(list)
        for i, tok in enumerate(tokens):
            by_line[tok["line"]].append(i)
        for line, indexes in sorted(by_line.items()):
            if not indexes:
                continue
            # Skip pure comments.
            semantic = [i for i in indexes if not tokens[i]["kind"].endswith("comment")]
            if not semantic:
                continue
            values = [tokens[i]["value"] for i in semantic]
            sid = self._node_id("line", line, *values)
            nodes.append(IRNode(
                sid, "structure.line", None,
                [token_ids[i] for i in semantic],
                {"line": line, "shape": self._shape_for_indexes(tokens, semantic)},
            ))

        # Weak relation hypotheses that work across many syntaxes.
        nodes.extend(self._infer_surface_relations(tokens, token_ids))
        nodes.extend(self._pattern_nodes(tokens, token_ids))
        nodes.extend(self._cross_language_analysis_nodes(text, "unknown-text"))
        return nodes

    def _infer_surface_relations(self, tokens: list[dict[str, Any]], token_ids: list[str]) -> list[IRNode]:
        out: list[IRNode] = []
        for i, tok in enumerate(tokens):
            val = tok["value"]

            # identifier followed by '(' often denotes invocation/declaration.
            if tok["kind"] == "identifier" and i + 1 < len(tokens) and tokens[i + 1]["value"] == "(":
                role = "declaration-or-call" if i > 0 and str(tokens[i - 1]["value"]).lower() in self.DECL_WORDS else "call-like"
                out.append(IRNode(
                    self._node_id("relation", role, i),
                    f"relation.{role}", val,
                    [token_ids[i], token_ids[i + 1]],
                    {"confidence": 0.72 if role == "call-like" else 0.88, "line": tok["line"]},
                ))

            # assignment-like binary relation.
            if tok["kind"] == "operator" and val in {"=", ":=", "<-", "=>", "->"} and 0 < i < len(tokens) - 1:
                out.append(IRNode(
                    self._node_id("relation", "binary-op", i, val),
                    "relation.binary_operator", val,
                    [token_ids[i - 1], token_ids[i], token_ids[i + 1]],
                    {"confidence": 0.80, "line": tok["line"]},
                ))

            if tok["kind"] == "identifier":
                low = str(val).lower()
                if low in self.CONTROL_WORDS:
                    out.append(IRNode(
                        self._node_id("role", "control", i, low),
                        "role.control_marker", low, [token_ids[i]],
                        {"confidence": 0.83, "line": tok["line"]},
                    ))
                elif low in self.DECL_WORDS:
                    out.append(IRNode(
                        self._node_id("role", "declaration", i, low),
                        "role.declaration_marker", low, [token_ids[i]],
                        {"confidence": 0.83, "line": tok["line"]},
                    ))
        return out

    def _pattern_nodes(self, tokens: list[dict[str, Any]], token_ids: list[str]) -> list[IRNode]:
        """Infer repeated token-shape n-grams; useful for unknown grammars."""
        out: list[IRNode] = []
        shapes = [self._token_shape(t) for t in tokens]
        if not shapes:
            return out

        for n in (2, 3, 4, 5):
            if len(shapes) < n:
                continue
            buckets: dict[tuple[str, ...], list[int]] = defaultdict(list)
            for i in range(0, len(shapes) - n + 1):
                # Don't learn across comments.
                if any(tokens[j]["kind"].endswith("comment") for j in range(i, i + n)):
                    continue
                buckets[tuple(shapes[i:i+n])].append(i)
            ranked = sorted(
                ((pat, starts) for pat, starts in buckets.items() if len(starts) >= 2),
                key=lambda x: (-len(x[1]), -n, x[0]),
            )[:12]
            for pat, starts in ranked:
                links: list[str] = []
                for s in starts[:8]:
                    links.extend(token_ids[s:s+n])
                out.append(IRNode(
                    self._node_id("pattern", n, pat, tuple(starts)),
                    "learned.repeated_pattern",
                    list(pat),
                    list(dict.fromkeys(links)),
                    {"ngram": n, "occurrences": len(starts), "starts": starts[:32], "semantic_status": "unknown"},
                ))
        return out

    def _statement_index_groups(self, tokens: list[dict[str, Any]]) -> list[list[int]]:
        """Split tokens into statement-like spans while respecting nesting."""
        if not tokens:
            return []
        groups: list[list[int]] = []
        current: list[int] = []
        depth = 0
        prev_line = tokens[0]["line"]

        for i, tok in enumerate(tokens):
            val = str(tok["value"])
            kind = tok["kind"]

            # A physical newline at top level is useful evidence of a boundary.
            if current and tok["line"] != prev_line and depth == 0:
                groups.append(current)
                current = []

            if not kind.endswith("comment"):
                current.append(i)

            if kind == "punct" and val in self.OPEN_TO_CLOSE:
                depth += 1
            elif kind == "punct" and val in self.CLOSE_TO_OPEN:
                depth = max(0, depth - 1)

            if val == ";" and depth == 0 and current:
                groups.append(current)
                current = []

            prev_line = tok["line"]

        if current:
            groups.append(current)
        return groups

    def _normalized_token_shape(self, tok: dict[str, Any]) -> str:
        """Map surface tokens to a spelling-independent structural alphabet."""
        kind = tok["kind"]
        value = str(tok["value"])
        low = value.lower()

        if kind == "identifier":
            if low in self.DECL_WORDS:
                return "KW:DECL"
            if low in {"return", "yield", "throw", "raise", "break", "continue"}:
                return "KW:TRANSFER"
            if low in self.CONTROL_WORDS:
                return "KW:CONTROL"
            if low in {"true", "false", "none", "null", "nil"}:
                return "LITERAL:SPECIAL"
            return "ID"
        if kind == "number":
            return "LITERAL:NUM"
        if kind in {"string", "triple_string"}:
            return "LITERAL:STR"
        if kind.endswith("comment"):
            return "COMMENT"
        if kind == "directive":
            return "DIRECTIVE"
        if kind in {"operator", "symbol"}:
            if value in {"=", ":=", "<-", "≔", "←"}:
                return "OP:ASSIGN"
            if value in {"->", "=>", "→", "⇒", "⟶", "⟹"}:
                return "OP:FLOW"
            if value in {"==", "!=", "<", ">", "<=", ">=", "===", "!==", "≤", "≥", "≠", "∈", "∉"}:
                return "OP:COMPARE"
            if value in {"+", "-", "*", "/", "%", "**", "⊕", "⊗", "÷", "×"}:
                return "OP:ARITH"
            if value in {"&&", "||", "!", "&", "|", "^", "¬", "∧", "∨"}:
                return "OP:LOGIC"
            if value in {".", "?.", "::"}:
                return "OP:ACCESS"
            return "OP:UNKNOWN"
        if kind == "punct":
            if value in "([{":
                return "GROUP:OPEN"
            if value in ")]}" :
                return "GROUP:CLOSE"
            if value in {",", ";"}:
                return "SEP"
            return f"P:{value}"
        return kind.upper()

    @staticmethod
    def _operator_role_hypothesis(contexts: Counter[tuple[str, str]]) -> dict[str, Any]:
        """Infer only a syntactic role; never pretend this proves semantics."""
        total = sum(contexts.values())
        if total <= 0:
            return {"role": "unknown", "confidence": 0.0}

        prefix = sum(c for (left, _), c in contexts.items() if left == "<START>" or left.startswith("GROUP:OPEN"))
        postfix = sum(c for (_, right), c in contexts.items() if right == "<END>" or right.startswith("GROUP:CLOSE"))
        infix = total - min(total, prefix + postfix)

        scores = {
            "prefix-like": prefix / total,
            "postfix-like": postfix / total,
            "infix-like": infix / total,
        }
        role, confidence = max(scores.items(), key=lambda kv: kv[1])
        return {"role": role, "confidence": round(confidence, 6), "evidence_count": total}

    def _structural_fingerprint(self, text: str) -> list[str]:
        tokens = self._tokenize(text)
        fp = [self._normalized_token_shape(t) for t in tokens if not t["kind"].endswith("comment")]
        # Bound comparison cost while preserving both beginning and end.
        if len(fp) > 2048:
            fp = fp[:1024] + ["<TRUNCATED>"] + fp[-1024:]
        return fp

    @staticmethod
    def _lcs_ratio(left: list[str], right: list[str]) -> float:
        if not left and not right:
            return 1.0
        if not left or not right:
            return 0.0
        return difflib.SequenceMatcher(None, left, right, autojunk=False).ratio()

    def _indentation_nodes(self, text: str) -> list[IRNode]:
        """Infer indentation scopes as evidence, useful for unknown languages."""
        nodes: list[IRNode] = []
        stack: list[tuple[int, int]] = [(0, 1)]  # indent, starting line
        lines = text.splitlines()

        for lineno, raw in enumerate(lines, 1):
            if not raw.strip() or raw.lstrip().startswith(("#", "//", "--")):
                continue
            expanded = raw.expandtabs(4)
            indent = len(expanded) - len(expanded.lstrip(" "))
            current = stack[-1][0]

            if indent > current:
                stack.append((indent, lineno))
            elif indent < current:
                while len(stack) > 1 and indent < stack[-1][0]:
                    old_indent, start_line = stack.pop()
                    nodes.append(IRNode(
                        self._node_id("indent-scope", old_indent, start_line, lineno - 1),
                        "structure.indent_scope",
                        None,
                        [],
                        {
                            "indent": old_indent,
                            "start_line": start_line,
                            "end_line": max(start_line, lineno - 1),
                            "depth": len(stack),
                            "semantic_status": "structural-evidence",
                        },
                    ))
                if indent > stack[-1][0]:
                    stack.append((indent, lineno))

        end_line = max(1, len(lines))
        while len(stack) > 1:
            old_indent, start_line = stack.pop()
            nodes.append(IRNode(
                self._node_id("indent-scope", old_indent, start_line, end_line),
                "structure.indent_scope",
                None,
                [],
                {
                    "indent": old_indent,
                    "start_line": start_line,
                    "end_line": end_line,
                    "depth": len(stack),
                    "semantic_status": "structural-evidence",
                },
            ))
        return nodes

    def _cross_language_analysis_nodes(self, text: str, language: str) -> list[IRNode]:
        """Emit canonical evidence that is comparable across source languages."""
        tokens = self._tokenize(text)
        if not tokens:
            return []
        out: list[IRNode] = []

        # Canonical statement fingerprints.
        pattern_counts: Counter[tuple[str, ...]] = Counter()
        for stmt_no, indexes in enumerate(self._statement_index_groups(tokens)):
            if not indexes:
                continue
            pattern = tuple(self._normalized_token_shape(tokens[i]) for i in indexes)
            pattern_counts[pattern] += 1
            first, last = tokens[indexes[0]], tokens[indexes[-1]]
            excerpt = text[first["start"]:last["end"]]
            out.append(IRNode(
                self._node_id("canonical-statement", stmt_no, pattern, first["start"]),
                "canonical.statement",
                list(pattern),
                [],
                {
                    "language": language,
                    "line_start": first["line"],
                    "line_end": last["line"],
                    "source_excerpt": excerpt[:300],
                    "semantic_status": "normalized-structure",
                },
            ))

        # Canonical role candidates independent of identifier spelling.
        for i, tok in enumerate(tokens):
            value = str(tok["value"])
            low = value.lower()
            if tok["kind"] == "identifier" and low in self.DECL_WORDS:
                target = None
                for j in range(i + 1, min(len(tokens), i + 5)):
                    if tokens[j]["kind"] == "identifier":
                        target = str(tokens[j]["value"])
                        break
                out.append(IRNode(
                    self._node_id("canonical-decl", i, target),
                    "canonical.declaration",
                    target,
                    [],
                    {"marker": value, "line": tok["line"], "confidence": 0.86},
                ))
            elif tok["kind"] == "identifier" and low in self.CONTROL_WORDS:
                out.append(IRNode(
                    self._node_id("canonical-control", i, low),
                    "canonical.control",
                    low,
                    [],
                    {"line": tok["line"], "confidence": 0.84},
                ))

            if tok["kind"] == "identifier" and i + 1 < len(tokens) and tokens[i + 1]["value"] == "(":
                prior = str(tokens[i - 1]["value"]).lower() if i else ""
                role = "declaration" if prior in self.DECL_WORDS else "invocation"
                out.append(IRNode(
                    self._node_id("canonical-call", i, role),
                    f"canonical.{role}",
                    value,
                    [],
                    {"line": tok["line"], "confidence": 0.9 if role == "declaration" else 0.74},
                ))

            if tok["kind"] in {"operator", "symbol"}:
                nshape = self._normalized_token_shape(tok)
                if nshape == "OP:ASSIGN" and i > 0:
                    out.append(IRNode(
                        self._node_id("canonical-assign", i, value),
                        "canonical.assignment",
                        value,
                        [],
                        {"line": tok["line"], "confidence": 0.87},
                    ))
                elif nshape == "OP:FLOW":
                    out.append(IRNode(
                        self._node_id("canonical-flow", i, value),
                        "canonical.flow",
                        value,
                        [],
                        {"line": tok["line"], "confidence": 0.78},
                    ))

        # Unknown operators get distributional syntactic profiles.
        op_contexts: dict[str, Counter[tuple[str, str]]] = defaultdict(Counter)
        for i, tok in enumerate(tokens):
            if tok["kind"] not in {"operator", "symbol"}:
                continue
            op = str(tok["value"])
            left = self._normalized_token_shape(tokens[i - 1]) if i > 0 else "<START>"
            right = self._normalized_token_shape(tokens[i + 1]) if i + 1 < len(tokens) else "<END>"
            op_contexts[op][(left, right)] += 1

        for op, contexts in sorted(op_contexts.items()):
            out.append(IRNode(
                self._node_id("operator-profile", op, tuple(contexts.items())),
                "learned.operator_profile",
                op,
                [],
                {
                    "contexts": [
                        {"left": a, "right": b, "count": c}
                        for (a, b), c in contexts.most_common(16)
                    ],
                    "role_hypothesis": self._operator_role_hypothesis(contexts),
                    "semantic_status": "hypothesis-not-meaning",
                },
            ))

        # Repeated full-statement patterns are stronger than token n-grams.
        for pattern, count in pattern_counts.most_common(32):
            if count < 2:
                continue
            out.append(IRNode(
                self._node_id("grammar-rule", pattern, count),
                "learned.grammar_rule",
                list(pattern),
                [],
                {"occurrences": count, "semantic_status": "surface-grammar"},
            ))

        out.extend(self._indentation_nodes(text))
        out.extend(self._surface_summary_nodes(text))
        return out

    def _surface_summary_nodes(self, text: str) -> list[IRNode]:
        tokens = self._tokenize(text)
        if not tokens:
            return []
        kinds = Counter(t["kind"] for t in tokens)
        operators = Counter(t["value"] for t in tokens if t["kind"] in {"operator", "symbol"})
        identifiers = Counter(t["value"] for t in tokens if t["kind"] == "identifier")
        shapes_by_line: Counter[str] = Counter()
        grouped: dict[int, list[int]] = defaultdict(list)
        for i, tok in enumerate(tokens):
            grouped[tok["line"]].append(i)
        for indexes in grouped.values():
            semantic = [i for i in indexes if not tokens[i]["kind"].endswith("comment")]
            if semantic:
                shapes_by_line[self._shape_for_indexes(tokens, semantic)] += 1

        return [
            IRNode(
                self._node_id("summary", "surface", len(text), len(tokens)),
                "summary.surface",
                None,
                [],
                {
                    "characters": len(text),
                    "lines": text.count("\n") + (1 if text else 0),
                    "tokens": len(tokens),
                    "token_kinds": dict(kinds),
                    "top_operators": operators.most_common(20),
                    "top_identifiers": identifiers.most_common(20),
                    "repeated_line_shapes": [(shape, count) for shape, count in shapes_by_line.most_common(20) if count >= 2],
                    "lexical_diversity": round(len(set(t["value"] for t in tokens)) / max(1, len(tokens)), 6),
                },
            )
        ]

    def _shape_for_indexes(self, tokens: list[dict[str, Any]], indexes: Iterable[int]) -> str:
        return " ".join(self._token_shape(tokens[i]) for i in indexes)

    @staticmethod
    def _token_shape(tok: dict[str, Any]) -> str:
        kind, value = tok["kind"], str(tok["value"])
        if kind == "identifier":
            return "ID"
        if kind == "number":
            return "NUM"
        if kind in {"string", "triple_string"}:
            return "STR"
        if kind.endswith("comment"):
            return "COMMENT"
        if kind in {"operator", "symbol"}:
            return f"OP:{value}"
        if kind == "directive":
            return "DIRECTIVE"
        if kind == "punct":
            return f"P:{value}"
        return f"{kind.upper()}:{value[:12]}"

    # --------------------------- binary parser ---------------------------

    def _parse_binary(self, raw: bytes, detected: str = "binary") -> list[IRNode]:
        """Analyze arbitrary binary code as structure, never by executing it."""
        nodes: list[IRNode] = []
        chunk_size = 64
        previous: str | None = None

        for offset in range(0, len(raw), chunk_size):
            chunk = raw[offset:offset + chunk_size]
            nid = self._node_id("binary", offset, chunk.hex())
            links = [previous] if previous else []
            nodes.append(IRNode(
                nid,
                "binary.chunk",
                base64.b64encode(chunk).decode("ascii"),
                links,
                {
                    "offset": offset,
                    "length": len(chunk),
                    "hex_prefix": chunk[:16].hex(),
                    "entropy": round(self._entropy(chunk), 6),
                },
            ))
            previous = nid

        # Extract printable evidence only; do not disassemble/execute.
        string_count = 0
        for match in re.finditer(rb"[\x20-\x7e]{4,}", raw):
            if string_count >= 256:
                break
            value = match.group(0).decode("ascii", "replace")
            nodes.append(IRNode(
                self._node_id("binary-string", match.start(), value),
                "binary.printable_string",
                value,
                [],
                {"offset": match.start(), "length": len(match.group(0))},
            ))
            string_count += 1

        # Repeated byte motifs often expose instruction/data regularity even
        # when the binary format is completely unknown. Bound work to 1 MiB.
        probe = raw[: 1024 * 1024]
        repeated_motifs = 0
        for width in (2, 4, 8, 16):
            if len(probe) < width * 3:
                continue
            counts: Counter[bytes] = Counter(
                probe[i:i + width] for i in range(0, len(probe) - width + 1, width)
            )
            for motif, count in counts.most_common(12):
                if count < 3:
                    continue
                nodes.append(IRNode(
                    self._node_id("binary-motif", width, motif.hex(), count),
                    "binary.repeated_motif",
                    motif.hex(),
                    [],
                    {
                        "width": width,
                        "occurrences": count,
                        "sampling": "aligned",
                        "semantic_status": "pattern-only",
                    },
                ))
                repeated_motifs += 1

        byte_counts = Counter(raw)
        top_bytes = [(f"{b:02x}", c) for b, c in byte_counts.most_common(16)]
        zero_runs = [len(m.group(0)) for m in re.finditer(rb"\x00{4,}", raw)]

        nodes.append(IRNode(
            self._node_id("binary-summary", detected, len(raw)),
            "summary.binary",
            detected,
            [],
            {
                "size_bytes": len(raw),
                "entropy": round(self._entropy(raw), 6),
                "printable_ascii_strings": string_count,
                "repeated_motifs": repeated_motifs,
                "top_bytes": top_bytes,
                "zero_run_count": len(zero_runs),
                "max_zero_run": max(zero_runs, default=0),
                "magic": raw[:16].hex(),
                "analysis_limit_bytes": min(len(raw), 1024 * 1024),
            },
        ))
        return nodes

    @staticmethod
    def _entropy(data: bytes) -> float:
        if not data:
            return 0.0
        counts = Counter(data)
        n = len(data)
        return -sum((c / n) * math.log2(c / n) for c in counts.values())


# ---------------------------------------------------------------------------
# Minimal CLI / self-test
# ---------------------------------------------------------------------------

def _demo() -> None:
    reader = UniversalCodeReader()
    sample = b"""
A7:
    01 -> 011F
    02 -> 77C2
    [14, 011F, 27]
"""
    result = reader.read(sample, "sample.aic")
    print(result.to_json(pretty=True))


if __name__ == "__main__":
    _demo()

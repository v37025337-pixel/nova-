# Architecture and evidence contract

## One state, one loop

`Kernel` is the only runtime. CODE, LOGIC, THINKING and INTELLIGENCE share its
one event-sourced state, task queue, causal memory and active genome. There are
no independently booted faculties, separate per-faculty stores or integration
bridges. Modules contain stateless functions or the single journal connection.
The journal stores genesis, immutable task registrations, complete learning
receipts and rollback events. Active programs, attempted contexts, consumed
datasets, lineage and the next deficit are projections of these events.

Each step has one `workspace.context` and mandatory evidence for all four
faculties. THINKING chooses a queue item; INTELLIGENCE selects inherited genes
that execute on its training inputs; CODE freezes a natively synthesized gene;
LOGIC evaluates it and its proposed genome before the single atomic admission.
Both code and cognition depend on the same prior events.

| Responsibility | Implementation | Observable evidence |
|---|---|---|
| JSON semantics and input boundary | `contracts.py` | Object-order invariance, bool/number distinction, overlap rejection |
| Durable memory | `memory.py` | Transaction/CAS tests, SQLite online backup and restore |
| Goal selection and self-model | `kernel.py` | Recorded training baseline, memory context, selected task, outcome counts |
| Program construction | `synthesis.py` | Exact training-only candidate and finite search count |
| Code execution | `language.py` | Validated IR, generated Python AST, exact source identity, measured outputs |
| Admission | `evaluation.py` | Held-out improvement, full active-task regression, dependency removal |
| Inheritance and rollback | `kernel.py` | Parent generation, immutable source IDs, branch ancestry |
| Genetics | `genetics.py` | Hashed parent/child genomes, inherited genes, expression parents, checked variation |
| Replay | `Kernel._load` | All decisions, programs, outputs and verdicts recomputed |

## Boundaries

Training labels guide search. Holdout labels are used only after a candidate is
fixed. Both are stored in the journal for reproducibility; this is a separation
of function arguments and control flow, not a cryptographic secret from the
process or its operator. Removing a parent proves that this compiled program
calls that parent; it does not prove that no alternative program exists.

Search exhaustion may retry in a new program-memory context. Any attempt that
reached held-out evaluation consumes the canonical dataset identity, regardless
of its admission result. The identity ignores task names, source labels and row
ordering. The operator remains responsible for genuinely fresh future datasets;
cross-task statistical leakage is not automatically eliminated.

The causal memory projection records task submission, earlier attempts, gene
admission events and each outcome. A task is retried after memory changes only
when its set of executable genes changes. Incompatible genes do not count as a
new search context. Queue states and outcomes survive restart without a second
queue database or a mutable status cache.

Memory stores verified programs and all failed receipts. A rollback selects a
strict ancestor without deleting history, resetting holdout consumption, or
reusing generation numbers. There is no automatic roll-forward into an archived
descendant. Concurrent writers use a compare-and-swap check under BEGIN IMMEDIATE.
The active genome and the queue verdict change through that same journal event.
Program-gene evolution is implemented; mutation of the host grammar/controller
is a separate future extension and is not implied by the word genetics.

Generated code has no arbitrary source input, imports, attributes, loops or
filesystem/network calls. Execution compiles source regenerated from validated
IR, checks its exact identity and uses reviewed bounded primitives. This is a
restricted expression executor, not a sandbox for arbitrary supplied Python.

Full semantic replay deliberately repeats synthesis. This favors correctness
and reproducibility for a small kernel; large histories need verified incremental
checkpoints in a future version. No scalability or general-intelligence result
is inferred from this release's small tests.

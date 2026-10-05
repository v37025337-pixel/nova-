# DM08 bounded genesis: first local increment

This is a **synthetic shadow implementation**, not M0020 production admission,
arbitrary algorithm invention, or evidence of consciousness. DM08 remains ACTIVE.
It extends the cloud runtime's existing bounded-artifact and independent-admission
approach; it does not replace the Python kernels.

## Reproduce without services or dependencies

Use Node 24.19.0 or a compatible Node 24 release with native TypeScript execution:

```sh
node --test mind-core-cloud/tests/*.test.ts
node mind-core-cloud/scripts/run_genesis_shadow.ts
for file in mind-core-cloud/edge/*.ts; do node --check "$file" || exit; done
```

No database, credentials, package install, model calls, API spend, or internet
requests are needed. The new GitHub workflow runs these same commands. Syntax
checking does not type-check imports or validate the Deno/Supabase deployment.

## Observable result

The example specification is: accept a relation only if both consistency and
coverage are at least 0.5.

1. The always-reject incumbent gets 1/2 public examples right: a measured gap.
2. Train-only search produces a one-condition rule with 2/2 training accuracy.
3. Independent suite `relation-v1` rejects that shortcut: 5/7 correct.
4. A predeclared, separate public training batch drives a two-condition redesign.
5. The old artifact and rejection are retained; its hash becomes the parent hash.
6. Distinct suite `relation-v2` gives 11/11; status becomes `shadow_admitted`.
7. A separate 81-point specification-derived grid verifies the final rule.

The repair batch is supplied by this demonstration harness. Autonomous evidence
acquisition or research is not implemented here. The synthesizer is not given
held-out features, labels, or failed case IDs, and does not construct its evaluator.

## Components and trust boundary

- `edge/genesis.ts`: finite numeric conjunction DSL, train-only enumeration,
  SHA-256 content commitments, immutable snapshots, bounded session and lineage.
- `edge/genesis_evaluator.ts`: separately implemented trusted evaluator. It freezes
  all suite data before awaiting, rejects overlap with the entire public training
  pool, evaluates a named suite at most once, and returns aggregate counts only.
- `edge/genesis_shadow_suites.ts`: independently authored synthetic policy cases.
  These are transparent reproducibility fixtures, not secret production benchmarks.
- `edge/genesis_shadow.ts`: integration exercise using the real synthesizer and
  evaluator, not mocked verdicts.
- `edge/index.ts`: explicit `mechanism_genesis_shadow` dispatch. Existing cycle
  logging stores the returned report if this source is separately deployed and an
  authorized goal is created. No goal is auto-created, registry admission is not
  changed, and production source is not auto-mutated. The M0019/M0020 inventory
  target typo is corrected.

A trusted caller must own the evaluator capability and its test data. This is
in-process data-flow separation, not process isolation, a cryptographically signed
remote judge, or protection against a host that edits both learner and evaluator.
A caller-provided receipt or goal-provided answer key is not an admission authority.
Each new session can replay these public demo suites; repeated demos add no novel
production evidence. Durable one-use benchmark tracking across restarts is future
work.

## Bounds and failure behavior

- 2–32 public training examples, both classes, no duplicate feature rows
- 1–6 training features; finite values between -1,000,000 and 1,000,000
- 1–3 conjunction conditions; `>=` / `<=` numeric comparisons only
- At most 50,000 candidate rules searched per proposal and three revisions/session
- Missing/nonfinite features, unsupported fields/operators, or executable payloads
  are errors; no arbitrary code evaluation, shell, network, or source mutation
- Artifact must be frozen before a suite is consumed; rejected suites cannot be
  reused by another candidate in the same evaluator, including concurrent requests
- A redesign must change the artifact and can only use committed public inputs
- Invalid/mismatched receipts and evaluator failures reject without exposing
  evaluator exception text; every hidden test must pass for shadow admission

## Remaining work before DM08 admission

1. Demonstrate at least three genuinely new mechanisms across appropriate deficit
   types; this increment demonstrates one rule-learning task in a fixed grammar.
2. Use independently owned, non-public real-task suites with fresh evaluator data
   per revision. Preserve the original exclusion boundary for training acquisition.
3. Add durable artifact/session/evaluator receipts and restart/recovery tests with
   the actual database schema. The current session is in-memory; the CLI emits JSON.
4. Run a full Deno type check and Supabase integration test, including cycle failure
   persistence and deployment packaging. Local Node tests do not prove this layer.
5. Review production admission separately. Do not flip `safe_to_auto_pursue` or
   mark M0020 admitted based on these synthetic scores.

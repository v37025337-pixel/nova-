# Mind Core Cloud Runtime

Real read-only internet runtime for Mind Core.

## Live infrastructure

- Supabase Postgres persistent state
- Supabase Edge Function runtime
- Supabase Cron hourly scheduler
- Direct outbound HTTP to public sources
- RLS-protected `mind_core_*` tables
- No credentials committed to GitHub

The project had reached its Edge Function count limit, so a retired function
slug, `noesis-internet-channel`, was safely extended. Its legacy behavior is
preserved: requests that do not POST `{"mode":"mind-core"}` still return the
old `410 NOESIS_REMOVED` response.

## Verified live cycles

1. `stable_release`
   - fetched https://www.python.org/downloads/
   - detected Python 3.14.8
   - stored evidence and state in Postgres

2. `release_blockers`
   - queried the public GitHub Search API
   - found the then-current open CPython release-blocker issue #158629
   - stored evidence and state in Postgres

## Scheduler

Cron job: `mind-core-research-hourly`

Schedule: `17 * * * *` (UTC)

The runtime alternates between stable-release verification and release-blocker
inspection. It is read-only with respect to external websites.

## Files

- `edge/index.ts` — exact deployed Edge Function source
- `schema.sql` — persistent state/evidence tables
- `cron.sql` — scheduler definition using Vault secret names only


## Goal Genesis v0.2

The runtime no longer alternates between two hard-coded checks.

It now stores a persistent research frontier in `mind_core_goals` and selects
the highest-priority eligible goal. New goals are generated from live evidence.

Example verified chain:

```
release-blocker scan
  -> discovers CPython #158629
  -> creates inspect_github_issue goal (priority 0.95)
  -> inspects issue body/state/labels
  -> creates recurring recheck goal while blocker remains open
```

Goal classes currently supported:

- `verify_stable_release`
- `scan_release_blockers`
- `inspect_github_issue`
- `inspect_github_pull`
- `inspect_web_reference`

References are treated as data. Only a small allowlist of public Python domains
can be followed automatically.


## Mechanism #1 — Real Internet Read

Mind Core now has a formal mechanism registry.

The first admitted mechanism is:

`M0001:real-internet-read`

Capabilities:
- HTTPS GET to public resources
- public web reading
- GitHub public API reading
- provenance/event logging

Constraints:
- read-only
- HTTPS only
- local/private targets blocked
- redirects revalidated hop-by-hop
- no credentials accepted from web content
- no remote mutation

Admission test:
- independent target: https://www.iana.org/domains/reserved
- HTTP status: 200
- bytes: 10497
- expected phrase found: `IANA-managed Reserved Domains`
- result: PASS
- status transition: `probation -> admitted`

All runtime web reads now call this mechanism rather than calling `fetch()`
directly from individual research actions.


## Mechanism #2 — Curiosity Pressure

Mind Core now has a source-grounded question-generation mechanism:

`M0002:curiosity-pressure`

It consumes real evidence already stored by M0001 and computes an interest
pressure from:

- uncertainty
- impact
- causal gap
- novelty
- temporal relevance

A question is persisted only when it can point back to a concrete evidence row.

Verified chain:

1. Autonomous evidence #6 contained:
   `have 9.0.4, need exactly 9.0.3`
2. M0002 generated:
   "What caused the mismatch, and do the latest comments identify a fix?"
3. It created an executable `inspect_issue_comments` goal.
4. M0001 fetched the live GitHub comments.
5. The comments referenced prior issue #150836.
6. M0002 generated a second causal question linking #158629 -> #150836.
7. M0001 fetched #150836 and answered that question.

This demonstrates a real loop:
`evidence -> interest -> question -> internet -> answer -> new evidence`.

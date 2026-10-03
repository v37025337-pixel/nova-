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

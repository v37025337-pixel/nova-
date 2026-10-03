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

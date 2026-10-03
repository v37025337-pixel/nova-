# Mind Core Mechanisms

## M0001 — Real Internet Read

**Key:** `M0001:real-internet-read`  
**Ordinal:** 1  
**Kind:** environment_io  
**Status:** admitted

Purpose: give Mind Core a real, read-only sensory channel to the public
internet.

### Admission evidence

Independent target:

`https://www.iana.org/domains/reserved`

Observed during cloud cycle 4:

- HTTP 200
- 10,497 bytes
- no redirect
- expected phrase present: `IANA-managed Reserved Domains`
- event persisted to Postgres
- final verdict: PASS

### Safety boundary

The mechanism accepts HTTPS only, blocks local/private targets and credential
URLs, manually validates every redirect target, and performs no remote
mutation.

Every successful or failed network read is recorded in
`mind_core_mechanism_events` with the purpose, target and result.

### Architectural rule

Research modules must not perform raw outbound fetches themselves. They call
M0001. Future mechanisms should follow the same registry -> probation -> real
test -> admission path.

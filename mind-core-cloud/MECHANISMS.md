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


## M0002 — Curiosity Pressure

**Key:** `M0002:curiosity-pressure`  
**Ordinal:** 2  
**Kind:** goal_genesis  
**Status:** admitted

Purpose: turn unresolved structure in real evidence into an explicit question
and an executable research goal.

Pressure vector:

```
P = (
  uncertainty,
  impact,
  causal_gap,
  novelty,
  temporal
)
```

Current interest score:

```
I = 0.30*uncertainty
  + 0.25*impact
  + 0.20*causal_gap
  + 0.15*novelty
  + 0.10*temporal
```

Admission evidence:
- source: genuine autonomous evidence #6
- generated question key:
  `mismatch:python/cpython#158629:9.0.4->9.0.3`
- interest: 1.000
- created executable goal: `inspect_issue_comments`
- result: question was answered through M0001

Chain test:
- answer evidence #8 referenced prior issue #150836
- M0002 generated:
  `causal-link:python/cpython#158629->150836`
- interest: 0.7425
- generated goal fetched real issue #150836
- second question status: answered

Constraint: no question without source evidence.


## M0003 — Domain Birth

**Key:** `M0003:domain-birth`  
**Ordinal:** 3  
**Kind:** research_frontier_expansion  
**Status:** admitted

Purpose: detect when accumulated real evidence points to an autonomous subject
outside the current research topic, verify that subject independently, and
open a new research frontier.

Admission evidence:
- source evidence: #9
- parent domain: `python/cpython`
- detected external domain: `tcl-tk-runtime`
- name: Tcl/Tk Runtime Ecosystem
- repeated mentions: 24
- dependency signals: 10
- birth pressure: 1.000
- verification host: `www.tcl-lang.org`
- verification HTTP: 200
- independent terms matched: `Tcl Developer Xchange`, `Tcl/Tk`
- domain status: admitted

Derived cross-domain goal:
- `domain-seed:tcl-tk-runtime`
- researched official Tcl/Tk downloads
- left GitHub/CPython and fetched `tcl-lang.org`

Current limitation: v0.1 domain inference uses a small external-entity resolver.
It is real domain birth, but not yet arbitrary open-world ontology induction.

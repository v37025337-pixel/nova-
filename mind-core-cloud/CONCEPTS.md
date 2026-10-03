# Mind Core Concepts

## Versioned Runtime Interface Contract

**Key:** `versioned-runtime-interface-contract:tcl-tk-runtime`  
**Status:** admitted  
**Kind:** cross_runtime_compatibility  
**Domain:** tcl-tk-runtime

### Definition

A compatibility boundary where a host or extension interacts with another
runtime through an interface that declares acceptable runtime versions.
Multiple release lines may coexist, but integration succeeds only when the
declared version contract is satisfied.

### Birth evidence

Evidence #14:
- official Tcl/Tk download page
- simultaneous release lines: 9.1, 9.0, 8.6

Evidence #12:
- real CPython/Tcl runtime failure
- installed: 9.0.4
- required: exactly 9.0.3

### Verification

Official Tcl 9.1 `Tcl_InitStubs` documentation confirmed:
- explicit version requirement
- `exact` matching behavior
- acceptance of newer versions under defined conditions
- major-version compatibility boundary
- dynamic API binding through function tables

Second official application source:
`https://www.tcl-lang.org/about/stubs.html`

Observed:
- cross-version extensions are supported
- function tables implement the boundary
- compatibility across major versions is not guaranteed

### Relations

```
python/cpython
  --depends_on_versioned_interface_of-->
tcl-tk-runtime
```

```
tcl-tk-runtime
  --exhibits-->
Versioned Runtime Interface Contract
```

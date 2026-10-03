# Mind Core Concept Transfers

## Versioned Runtime Interface Contract -> Node.js Node-API

**Status:** admitted  
**Mechanism:** M0005:concept-transfer  
**Transfer score:** 1.000  
**Official source:** https://nodejs.org/api/n-api.html

Structural matches:
- ABI stability
- cross-version behavior
- no recompilation for supported later Node.js versions
- explicit interface version
- version matrix
- insulation from underlying JavaScript engine

Source-technology contamination checks:
- Tcl/Tk: false
- CPython identifier: false

Relation:

```
nodejs-node-api
  --exhibits_analogue_of-->
versioned-runtime-interface-contract:tcl-tk-runtime
```

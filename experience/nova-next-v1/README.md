# Retained failed network experiment

The first frozen successor runtime performed local DNS validation before urllib
could use the configured HTTPS proxy. All eight requests failed with
`Temporary failure in name resolution`. No external source was observed, no
candidate was generated, and no mechanism was admitted.

`protocol.json`, `result.json`, `journal.json.gz` and `actions.json.gz` retain
the actual failure. `frozen-runtime.tar.gz` preserves the source hashes from
this protocol, before the proxy-aware transport correction. The archive is
historical evidence and does not replace the current package.

The next independent run is `../nova-next-v2`. Its journal has a different
runtime manifest. The failed journal cannot be silently restored into that
changed runtime.

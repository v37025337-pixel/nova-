# Runtime and deployment policy

NOVA is a Python CLI/kernel repository. Its supported entry points are declared
in `pyproject.toml`; it is not the production HTTP/browser runtime.

## Active cloud components

The current Mind Core cloud stack is intentionally split:

- `nova-` — source/kernel repository and `mind-core-cloud/` source mirror.
- Supabase — persistent state, Edge Function runtime, cron, Resource Fabric,
  mechanisms, beliefs, evidence, and private bridge functions.
- `v37025337-pixel/fastapi` — separate Vercel project used only for the
  verified browser runtime.
- Vercel Sandbox — ephemeral Firecracker microVM that runs the SHA-256-pinned
  Ungoogled Chromium browser snapshot.

The browser runtime is therefore **not** deployed from this repository.

## Vercel Git deployments for nova-

The root `vercel.json` intentionally sets:

```json
{
  "git": {
    "deploymentEnabled": false
  }
}
```

This prevents the historical false Vercel deployments of the NOVA CLI
repository from producing misleading production failures.

The earlier failures such as `PYTHON_ENTRYPOINT_NOT_FOUND` were caused by
binding this CLI repository to a web deployment target. They are historical
records and are not the active Mind Core runtime.

## Browser runtime

The active browser service is deployed from the separate repository/project:

`v37025337-pixel/fastapi`

It exposes a private HMAC-authenticated bridge to a Vercel Sandbox snapshot
containing verified Ungoogled Chromium. Mind Core reaches it through private
Supabase functions; user browser cookies/passwords are not imported.

## Branch consolidation

On 2026-10-05 all historical NOVA development branches were reviewed against
`main`. Every branch except
`fix/disable-vercel-auto-deploy-20261004` had no commits ahead of main. The
useful deployment-policy content from that remaining branch was reconciled into
main before branch refs were synchronized.

This keeps `main` as the canonical kernel source while preserving the separate
cloud/browser deployment boundaries.

# Mind Core Browser Runtime

Dedicated browser runtime for Mind Core using Vercel Sandbox microVMs.

Browser source:
- ungoogled-software/ungoogled-chromium-portablelinux
- pinned version: 154.0.8037.97-1
- x86_64 tarball SHA-256:
  9529d5829ee58b22d97d0f4d6d5f9afaa4ce6cb34e591ac324be0cf3fa51f8e6
- release uploader: github-actions[bot]

Endpoints:
- GET /api/health
- POST /api/bootstrap — authenticated; prepares a verified browser snapshot
- POST /api/browser — authenticated; runs an ephemeral headless browser session

No user cookies, saved passwords, or browser profiles are imported.

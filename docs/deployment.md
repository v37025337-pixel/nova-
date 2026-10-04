# Runtime and deployment policy

NOVA is a Python CLI package. Its supported entry points are declared in
`pyproject.toml` under `[project.scripts]`; persistent local state and subprocess
execution are part of the kernel runtime. The repository does not provide a
WSGI/ASGI application for Vercel Functions.

The separate cloud runtime in `mind-core-cloud/` uses Supabase Postgres,
Supabase Edge Functions and Supabase Cron. See
[its runtime documentation](../mind-core-cloud/README.md).

## Vercel Git deployments

The root `vercel.json` sets `git.deploymentEnabled` to `false` for all
branches. This prevents automatic production and preview deployments for every
Vercel project connected to this repository, including `nova-` and
`nova--fqt5`. It does not disable the GitHub Actions kernel verification workflow.

Both Vercel production deployments of commit
`5080b2b9df433be38cde75f34d5f5fa6654a56fb` selected the Python framework and
failed during the build with `PYTHON_ENTRYPOINT_NOT_FOUND`. The root
`pyproject.toml` describes an installable CLI package, not a Python HTTP
entry point. A missing `package.json` was not the cause.

Historical failed deployments remain failed; disabling future deployments does
not convert those records into successful builds. Vercel deployment status
contexts are not required checks on the main branch as inspected on
2026-10-04: main was unprotected and the repository ruleset list was empty.

If a Vercel web application is introduced later, define and validate its actual
HTTP runtime and project root before re-enabling Git deployments.

Official configuration reference:
https://vercel.com/docs/project-configuration/git-configuration#turning-off-all-automatic-deployments

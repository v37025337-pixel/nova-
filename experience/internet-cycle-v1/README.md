# Internet cycle v1

This experiment gives the existing NOVA 0.4 runtime live HTTPS data without
changing any `nova_core` source file or its deterministic replay contract.

The adapter fetches fresh public metadata from the GitHub REST API and builds two
disjoint tasks:

- `140-live-stars-plus-forks`: derive a numeric result from two fields in a live
  repository JSON snapshot.
- `150-live-owner-uppercase`: traverse a nested live JSON object and normalize
  the owner login.

NOVA receives both tasks together. The experiment does not tell the kernel which
one to run first. Selection is made by the existing queue policy
`largest_training_deficit_then_previous_cost_then_task_id`. Program synthesis
uses training rows only; the existing gate evaluates the pre-registered holdout.
After development, additional repositories are fetched and used only as fresh
post-admission queries.

The network adapter and reference-output construction are environment code, not a
new kernel faculty. This intentionally preserves the G14 runtime and journal
replay. A PASS therefore means: live internet ingestion succeeded, NOVA selected
a task with its own policy, synthesized at least one admitted program, answered
all fresh live queries correctly, and the resulting journal replayed in a
separate process. It does **not** claim unrestricted web browsing, autonomous
research-goal invention, or arbitrary self-rewrite.

Run:

```bash
python scripts/run_internet_cycle.py \
  --state /tmp/nova-internet-cycle-v1/state.sqlite \
  --output /tmp/nova-internet-cycle-v1/result
```

The CI workflow `.github/workflows/internet-cycle-v1.yml` runs this against the
live GitHub API on Python 3.12 after the full existing unit test and release
verification suite.

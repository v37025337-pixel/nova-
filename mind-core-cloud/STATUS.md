# Live Status

Runtime:
- version: 0.3-cloud-mechanism-registry
- Edge Function: noesis-internet-channel
- Supabase function version: 16
- deployed source SHA-256: e7c191f3260c7d2aef6a3b481c8aa18caaf4d962c11b387957aa928640875d03
- cron: mind-core-research-hourly
- schedule: 17 * * * *
- cron active: true
- external mode: read-only

Mechanism registry:
- #1: M0001:real-internet-read
- name: Real Internet Read
- status: admitted
- admitted after independent IANA self-test
- self-test HTTP: 200
- self-test bytes: 10497
- expected text: PASS
- mechanism events are persisted in mind_core_mechanism_events

Verified cloud cycles:
- cycle 1: stable_release — completed
- cycle 2: release_blockers — completed
- cycle 3: self-selected inspect_github_issue — completed
- cycle 4: mechanism_self_test — completed

Goal Genesis remains active.

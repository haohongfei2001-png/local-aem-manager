# R6 Local Certification Harness Receipt

Disposition: HARNESS_CERTIFIED / LIVE_RUN_PENDING

## Certified harness runtime

Runtime/test SHA:
`6dd4f16e10861a3a9a730473819e39cb232b02ec`

Implementation PR:
- PR #9 — R6: local Chrome certification harness
- candidate SHA: `705e562590f8295e49b3f4137627e198076812df`

PR CI:
- run `35598069115`
- all six required jobs: SUCCESS

Exact-main CI:
- run `35598153437`
- head: `6dd4f16e10861a3a9a730473819e39cb232b02ec`
- unit: SUCCESS
- policy-replay: SUCCESS
- executor-sandbox: SUCCESS
- portfolio-events: SUCCESS
- browser-thread-control: SUCCESS
- real-readonly-shadow: SUCCESS

## Harness delivered

- generic configured Playwright/CDP transport;
- current-page thread observation;
- composer preparation and guarded send click;
- positive user-message confirmation by normalized digest;
- refresh/rebind probe;
- dedicated certification command:
  `local-aem-r6-cert`;
- local config template:
  `config/r6-cert.example.yaml`;
- normal-send, pre-send retry, post-send uncertainty/no-retry probes;
- controlled stale writer-lease replacement path.

## Required live run

The harness has NOT been run against the user's real Mac/Chrome session in this execution.

A dedicated harmless certification ChatGPT thread must be used for the three send probes. Real engineering threads are observation-only during certification.

R6 remains BLOCKED_LIVE_CERTIFICATION and R7 remains LOCKED until the live run passes.

# R0 — Architecture Freeze

Mode: DESIGN_ONLY
Managed-project writes: FORBIDDEN
Legacy worker start: FORBIDDEN

## Goal

Create a clean v4 architecture based on AEM v0.2 management policy and lessons from the legacy supervisor without inheriting its rule-first coupling.

## Inputs verified

- new repository remote main exists;
- AEM v0.2.0 current policy files were re-read from remote;
- AEM case 007 and manager decision evals were re-read;
- legacy supervisor has no GitHub mirror discoverable in the connected GitHub account;
- fresh local source audit is unavailable in the current session.

## Decisions frozen

- Python 3.12+ local runtime;
- SQLite operational state + append-only JSONL audit;
- provider-agnostic Manager Brain;
- schema-bound model decisions;
- deterministic policy gate before privileged action;
- one-writer lease;
- executor abstraction;
- browser is optional;
- event-driven internal loop with health tick fallback;
- AEM validate-then-activate policy sync;
- restart reconciliation;
- no secrets in persistent state/logs.

## Non-decisions deferred

- exact Python libraries/frameworks beyond the technology baseline;
- exact DeepSeek model name / reasoning parameter;
- exact Codex integration mechanism until capability probe;
- v3 file/module reuse map pending fresh source audit;
- production polling intervals;
- production canary repository.

## Exit condition

R0 is architecture-complete when:
- all frozen docs/schemas/config/status are on remote main;
- remote readback matches;
- R1 is marked READY but not started.

The donor source audit remains a tracked prerequisite for claiming reuse, not for R1 read-only implementation.

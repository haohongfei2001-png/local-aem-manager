# R1 — Read-only Shadow Foundation

Mode: IMPLEMENTATION / READ_ONLY
Managed-project writes: FORBIDDEN
Executor actions: FORBIDDEN

## Goal

Implement the first runnable Local AEM foundation without any ability to modify managed repositories or send instructions to developer agents.

## Deliverables

- Python package and CLI;
- YAML config loader with R1 safety validation;
- SQLite portfolio state;
- append-only JSONL audit log with sensitive-field redaction;
- GET-only GitHub REST client;
- AEM policy loader with required-file/version validation and last-known-good fallback;
- portfolio observation and canonical YAML status extraction;
- CLI commands: status, observe, shadow-once;
- unit tests;
- real GitHub read-only integration run in CI.

## Security boundary

R1 exposes no mutation method in its GitHub client and requires all executor flags disabled.

It does not:
- modify managed repositories;
- send messages to GPT/developer threads;
- execute shell/Codex work;
- acquire active writer leases;
- start legacy v3 workers.

## Policy activation in R1

R1 validates policy presence and minimum version before caching/activating a last-known-good bundle.

Full manager-decision eval/replay validation is added in R2. No manager brain exists in R1, so no policy-driven privileged decision can occur yet.

## Verification

Required:
- package compiles;
- unit tests pass;
- GET-only surface test passes;
- real read-only shadow run successfully reads the AEM policy repository and local-aem-manager remote main/status;
- persisted status exactly matches the newly recorded snapshot.

## Exit

If all required checks pass on the implementation head:
- merge the R1 PR;
- verify exact main CI;
- update canonical status to R1 COMPLETE and R2 READY;
- stop. Do not start R2 in the same execution.

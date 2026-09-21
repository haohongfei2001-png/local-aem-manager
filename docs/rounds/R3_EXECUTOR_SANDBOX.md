# R3 — Executor Layer in Dry-run / Sandbox

Mode: IMPLEMENTATION / SANDBOX
Managed-product writes: FORBIDDEN
Live GitHub mutations: FORBIDDEN
Live Codex execution: FORBIDDEN

## Goal

Implement the executor abstraction and verification lifecycle without depending on browser automation and without granting production write authority.

## Deliverables

- ActionPlan JSON Schema and validation;
- Executor protocol and job/result lifecycle;
- ShellExecutor with bounded sandbox root and program allowlist;
- GitHubExecutor dry-run adapter;
- CodexExecutor capability probe + dry-run adapter;
- SQLite execution/idempotency ledger;
- ExecutionCoordinator that requires an APPROVE gate result;
- independent verifier framework;
- sandbox self-test;
- CI executor-sandbox job.

## Safety model

### Shell

R3 may execute a real local command only inside a temporary sandbox and only when:
- operation is RUN_SHELL;
- cwd resolves inside sandbox_root;
- executable basename is explicitly allowlisted;
- subprocess uses argv directly, not shell=true;
- HOME and TMPDIR point to the sandbox;
- timeout is bounded.

### GitHub

GitHubExecutor accepts only dry_run=true in R3. It performs no mutation API request.

### Codex

CodexExecutor may probe whether a Codex binary is installed, but accepts only dry_run=true in R3 and starts no Codex process.

## Idempotency

ExecutionLedger keys completed/failed attempts by idempotency_key. Replaying the same key returns the durable prior result rather than executing again.

A failed attempt is not silently retried under the same idempotency key.

## Verification

Executor success is not enough.

ExecutionCoordinator runs independent verification specs:
- JOB_SUCCEEDED;
- FILE_EXISTS;
- FILE_TEXT_EQUALS.

The R3 sandbox self-test:
1. runs one allowlisted Python command in a temporary sandbox;
2. verifies its output file;
3. repeats the same action and confirms idempotent replay;
4. simulates a GitHub mutation without writing;
5. simulates a Codex task without starting Codex.

## Exit

R3 completes when:
- unit tests pass;
- policy replay remains green;
- executor sandbox self-test passes;
- R1 real-readonly integration remains green;
- PR is merged;
- exact-main CI passes.

Then set R3 COMPLETE / R4 READY. R4 is the first round allowed to define a real canary repository/scope.

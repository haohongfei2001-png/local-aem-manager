# R2 — Manager Brain + Deterministic Gate

Mode: IMPLEMENTATION / DECISION_ONLY
Managed-project writes: FORBIDDEN
Executor actions: FORBIDDEN

## Goal

Implement the reasoning layer that can turn a verified portfolio snapshot plus AEM policy into one schema-bound manager decision, then pass that decision through deterministic authority/safety gates before any future executor can act.

## Deliverables

- provider-agnostic ManagerProvider contract;
- OpenAI-compatible transport adapter;
- DeepSeek adapter through the common transport contract;
- ManagerBrain prompt construction from activated AEM policy + portfolio snapshot;
- strict ManagerDecision JSON Schema validation;
- stale/foreign evidence-snapshot rejection;
- deterministic Policy Gate;
- explicit requested_operations declaration;
- offline replay harness;
- AEM v0.2 18-case replay translation plus fail-closed unsafe cases;
- CI policy-replay job.

## Deterministic gate coverage

The R2 gate must fail closed on:
- project/repository mismatch;
- owner-gated canonical states;
- force push / destructive data / new credentials / permission expansion;
- blocked scope write/advance;
- unauthorized next-scope start;
- unauthorized merge/write;
- active-writer takeover;
- ambiguous SUSPECT writer takeover.

It may approve ordinary bounded technical decisions when current authority permits them.

## Provider boundary

Provider adapters may generate decisions but cannot execute them.

R2 does not expose any command that sends the resulting decision to a managed repository, shell, Codex, browser, or developer thread.

Provider credentials are resolved only from configured environment-variable names and are not persisted in Local AEM state or audit logs.

## Evaluation boundary

CI does not require a real DeepSeek/OpenAI credential.

ManagerBrain is tested with a deterministic fake provider; the transport is tested with a fake HTTP opener.

The AEM v0.2 manager evals are translated to replay fixtures so schema/gate behavior is regression-tested deterministically. Live-model quality/cost benchmarking is deferred until a credentialed shadow/canary round.

## Exit

R2 is complete when:
- unit tests pass;
- the replay suite passes all translated AEM v0.2 cases;
- unsafe replay cases fail closed with the expected gate disposition;
- existing R1 real-readonly-shadow integration remains green;
- PR is merged;
- exact-main CI succeeds.

Then set R2 COMPLETE / R3 READY and stop the R2 execution.

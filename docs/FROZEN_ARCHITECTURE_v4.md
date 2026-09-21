# Local AEM Manager v4 — Frozen Architecture

Status: FROZEN FOR IMPLEMENTATION
Architecture version: 4.0
Policy baseline: AEM v0.2.0

## 1. Purpose

Local AEM Manager is a long-running local engineering-management runtime. It converts heterogeneous evidence from GitHub, local processes, developer agents, and browser state into a verified portfolio state, asks a strong model to propose the next engineering action, applies deterministic authority/safety checks, dispatches an executor, and verifies durable progress.

It is deliberately not a fixed IF/ELSE round scheduler.

## 2. Core pipeline

```
Evidence Collectors
      ↓
Evidence Normalizer
      ↓
Portfolio State Store
      ↓
Manager Brain
      ↓ structured ManagerDecision
Deterministic Policy Gate
      ↓ approved ActionPlan
Executor Router
      ↓
Executor(s)
      ↓
Verification Engine
      ↓
Portfolio State + Audit Log
      ↓
Re-prioritize
```

The LLM may propose decisions. It cannot bypass Policy Gate or call privileged executors directly.

## 3. Runtime modules

### 3.1 policy/

Responsibilities:
- fetch/pin AEM policy bundle;
- validate policy version and files;
- run AEM manager decision evals before activating a new bundle;
- expose normalized charter/escalation/takeover constraints.

Policy sync mode is **validate_then_activate**.

A newly observed AEM main is not immediately authoritative for the running process. The last-known-good activated bundle remains active until validation succeeds.

### 3.2 evidence/

Collectors provide observations, not conclusions.

Required collector interfaces:
- GitHub evidence: refs, commits, PRs, checks/actions, changed files, canonical docs.
- Local Git evidence: worktree/branch/dirty state when available.
- Process evidence: PID/liveness/exit/output heartbeat.
- Executor evidence: Codex/shell/browser job lifecycle.
- Browser/thread evidence: visible agent state and message/output freshness.
- Timer evidence: health ticks and timeout windows.

Each observation has:
- source;
- observed_at;
- freshness key;
- subject;
- payload digest;
- confidence/provenance;
- optional exact SHA/run binding.

Cached or repeated observations must not be treated as fresh merely because they were re-read.

### 3.3 portfolio/

Persistent operational state uses SQLite.

Primary entities:
- projects;
- scopes/rounds;
- evidence snapshots;
- writer leases;
- executor jobs;
- manager decisions;
- action plans;
- verification records;
- owner escalations.

SQLite is the operational database. An append-only JSONL audit stream is maintained for human/replay inspection.

### 3.4 manager/

Manager Brain is provider-agnostic.

Supported architecture:
- OpenAI-compatible provider adapter;
- DeepSeek adapter/configuration through the common provider contract;
- additional providers without changing manager logic.

Inputs:
- activated AEM policy digest/version;
- project authority summary;
- current portfolio snapshot;
- relevant fresh evidence;
- recent decisions/actions;
- current writer leases.

Output:
- one schema-valid ManagerDecision;
- no free-form executor calls.

The model is responsible for:
- state interpretation;
- portfolio prioritization;
- ordinary engineering judgment;
- executor selection recommendation;
- escalation recommendation;
- verification requirements.

### 3.5 gate/

The deterministic Policy Gate evaluates a proposed ManagerDecision against:
- AEM escalation rules;
- project authority;
- writer leases;
- branch/scope restrictions;
- forbidden operations;
- credential/permission boundaries;
- current authorization envelope;
- replay/idempotency constraints.

Possible results:
- APPROVE;
- NARROW_AND_RETRY;
- REJECT;
- OWNER_ESCALATION_REQUIRED.

The gate is fail-closed.

### 3.6 leases/

WriterLease key:
`repo + branch + scope_overlap_key`.

States:
ACTIVE, SUSPECT, STALE, RELEASED, BLOCKED.

Lease state is not derived from UI labels alone.

Progress signals include:
- branch/head movement;
- commit creation;
- CI transition;
- durable process output;
- developer-agent output;
- executor heartbeat.

Takeover uses independent worktree/snapshot/manager branch when practical.

### 3.7 executors/

Executor interface:
- capability_probe();
- prepare(action);
- execute(action);
- observe(job);
- cancel(job);
- collect_result(job).

Planned adapters:
- GitHubExecutor;
- ShellExecutor;
- CodexExecutor;
- BrowserExecutor;
- DeveloperThreadExecutor.

Browser/ChatGPT thread execution is optional, not the sole actuator.

A stuck browser composer must not block the portfolio if another authorized executor can safely take over.

### 3.8 verification/

Verification is independent from executor prose.

It can require:
- exact-head commit verification;
- targeted tests;
- full suite/certification;
- PR state;
- CI/action run;
- deployed product/browser evidence;
- canonical closure docs.

The engine distinguishes:
- runtime/test SHA;
- later documentation-only closure SHA.

### 3.9 events/

Internal event bus drives fast re-evaluation.

Event sources:
- GitHub changes/check transitions;
- local process/job transitions;
- executor completion;
- browser/thread output changes;
- lease timeout;
- periodic health tick.

Initial implementation may poll external systems, but must publish normalized internal events.

A configurable health tick remains as a fallback even when event-driven sources exist.

### 3.10 audit/

All manager decisions and privileged actions produce durable records.

Audit logs must include:
- evidence refs/digests;
- decision;
- policy version;
- gate result;
- action;
- executor;
- verification result;
- state transition.

Secrets and raw credentials are never logged.

## 4. State model

Project state is descriptive, not a rigid global state machine.

Recommended high-level values:
UNKNOWN, IDLE, ACTIVE, WAITING_EXTERNAL, BLOCKED, NEEDS_OWNER, COMPLETE.

Scope state remains project-specific and may include READY, IN_PROGRESS, COMPLETE, FAIL, BLOCKED, NOT_STARTED, etc.

Local AEM must preserve project terminology rather than coercing every repository into one lifecycle.

## 5. Decision model

The ManagerDecision schema contains:
- decision_id;
- project_id;
- evidence_snapshot_id;
- assessment;
- priority;
- owner_required;
- action_type;
- executor;
- target;
- rationale;
- instructions;
- verification requirements;
- expected state transition;
- idempotency key.

The runtime does not depend on natural-language parsing of the model response.

## 6. Autonomy boundary

Autonomous:
- ordinary engineering debugging;
- tests;
- bounded refactors;
- CI diagnosis;
- PR hygiene allowed by project rules;
- executor replacement;
- stale-worker takeover;
- portfolio reprioritization;
- closure after real gates pass.

Owner-gated:
- product direction/frozen invariant changes;
- material UX fork without authority;
- expanded permissions/privacy/data access;
- new credentials/accounts/paid services;
- destructive or irreversible high-risk actions;
- explicit OWNER_DECISION / NO_GO;
- genuine dead ends after reasonable attempts.

## 7. Credentials

Credentials are resolved at runtime from approved local mechanisms such as:
- existing CLI auth;
- OS keychain;
- environment/session injection.

They are referenced by logical credential IDs, never serialized into project state or logs.

No round may add a new credential requirement without explicit authorization.

## 8. Recovery

On restart:
1. load last-known-good policy bundle;
2. open SQLite state;
3. mark previously running jobs UNKNOWN_PENDING_RECONCILIATION;
4. re-observe GitHub/process/browser truth;
5. reconcile writer leases;
6. resume only actions that are proven idempotent and authorized;
7. otherwise create a new manager decision.

Never assume an interrupted write succeeded.

## 9. Non-goals for v4 foundation

- autonomous product strategy generation;
- bypassing project canonical authority;
- self-modifying safety policy;
- mandatory cloud infrastructure;
- direct dependence on one LLM vendor;
- uncontrolled multi-agent shared-branch writing.

## 10. Technology baseline

Implementation baseline:
- Python 3.12+;
- asyncio-based runtime;
- SQLite for operational state;
- JSON Schema for model/runtime contracts;
- YAML for operator configuration;
- JSONL for append-only audit/replay;
- subprocess-based local executors;
- GitHub API/CLI adapter behind a common interface;
- Playwright/CDP only behind BrowserExecutor.

The architecture may add libraries without changing these boundaries.

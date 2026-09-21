# Local AEM v4 Roadmap

## R0 — Architecture freeze

Status: COMPLETE_FOR_ARCHITECTURE

Deliverables:
- frozen v4 architecture;
- execution protocol;
- legacy donor audit boundary;
- decision/state schemas;
- config baseline;
- canonical status.

No runtime execution against managed repositories.

## R1 — Read-only shadow foundation

Build:
- package skeleton;
- config loader;
- SQLite + audit log;
- AEM policy loader with pinned last-known-good bundle;
- GitHub/local evidence interfaces;
- portfolio state reconstruction;
- CLI: status / observe / shadow-once.

Hard rule: no managed-repo writes, no executor actions.

Exit: reproduce portfolio state from fixtures and one real read-only repository set without changing anything.

## R2 — Manager Brain + deterministic gate

Build:
- provider interface;
- DeepSeek/OpenAI-compatible adapters;
- structured ManagerDecision;
- policy gate;
- AEM decision-eval runner;
- replay harness.

Exit: AEM eval suite passes; unsafe fixtures fail closed; still no real writes.

## R3 — Executor layer in dry-run/sandbox

Build:
- ShellExecutor;
- GitHubExecutor;
- CodexExecutor capability probe/adapter;
- job lifecycle and idempotency;
- verifier framework.

Use sandbox/test repositories or no-op actions.

Exit: action plans can execute and verify without browser dependence.

## R4 — Single-repository canary

Authorize one low-risk repo/scope.

Test:
- one writer lease;
- bounded code/test/PR cycle;
- restart/reconciliation;
- kill switch;
- owner escalation.

Exit: canary completes without unauthorized scope expansion.

## R5 — Portfolio + event-driven scheduling

Build:
- multiple projects;
- dynamic prioritization;
- normalized event bus;
- GitHub/process events;
- health tick;
- waiting-project switching.

Exit: manager handles concurrent waiting/running projects without global WAIT.

## R6 — Browser/developer-thread executor + stale takeover

Port or rewrite:
- CDP/Playwright browser adapter;
- thread freshness;
- pre-send/post-send uncertainty;
- stale-active detection;
- safe executor takeover.

Browser is optional, not the sole actuator.

## R7 — Production certification

Shadow Local AEM against Work/human manager decisions, then staged authority:
1. read-only;
2. one repo;
3. two repos;
4. portfolio.

Require replay/eval evidence, no duplicate writers, clean escalation behavior, restart safety, and audited secrets handling before unattended production.

# AGENTS.md

## Authority

For this repository, use the following order:

1. explicit owner instruction for the current Local AEM development round;
2. status/LOCAL_AEM_STATUS.yaml;
3. docs/rounds/<current round>;
4. docs/FROZEN_ARCHITECTURE_v4.md;
5. docs/EXECUTION_PROTOCOL.md;
6. upstream AEM policy bundle from haohongfei2001-png/ai-engineering-manager;
7. implementation notes and tests.

## Hard boundaries

- Never modify managed product repositories while developing Local AEM unless the current round explicitly authorizes a canary.
- Never start legacy AI-Supervisor workers merely to test Local AEM.
- Never delete or rewrite the legacy /Users/hhf/AI-Supervisor/v3 tree.
- Never force push.
- Never persist API keys, OAuth tokens, cookies, or secrets in repo files, SQLite state, JSONL audit logs, fixtures, or CI output.
- A language model never receives direct write authority. Every proposed action must pass the deterministic policy/authority gate.
- One active writer per repo + branch + overlapping scope.
- Project-specific frozen design and canonical authority outrank generic AEM policy.
- AEM policy updates use validate-then-activate; do not silently run an unvalidated new policy version.

## Round discipline

Implement only the current authorized round.

A completed round may mark the next round READY, but does not itself authorize starting it in the same execution unless the owner or package authorization explicitly says so.

## Testing

Every material manager rule needs:
- deterministic unit tests where possible;
- at least one decision/replay eval;
- evidence that unsafe actions fail closed.

No test may be weakened solely to obtain green status.

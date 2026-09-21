# Local AEM v4 Execution Protocol

## Source of truth

Local AEM's own development uses:
- GitHub remote main;
- status/LOCAL_AEM_STATUS.yaml;
- the current round contract;
- required tests/CI once configured.

Local clones are workspaces, not authority.

## Development round rules

1. Re-read remote main and status before work.
2. Execute only the authorized round.
3. Preserve previous correct work.
4. Use bounded branches/PRs for implementation rounds.
5. Run the round's required verification.
6. Update canonical status and evidence.
7. Re-read remote after push/merge.
8. Stop at the round boundary unless the authorization explicitly covers the next round.

## Runtime safety gates

Before any privileged action, runtime must confirm:
- policy bundle activated and valid;
- project authority loaded;
- action schema valid;
- owner escalation not required;
- writer lease available;
- target repo/branch/scope matches authorization;
- idempotency key not already completed;
- required credential capability exists without exposing secret material.

## Managed-repository writes

Shadow rounds: forbidden.

Canary rounds: only repositories/scopes explicitly listed in the round contract.

Production manager: use one-writer rule and project-specific protocols.

Force push is disabled by default and is not part of normal autonomous authority.

## Executor lifecycle

PREPARED → RUNNING → SUCCEEDED / FAILED / CANCELLED / UNKNOWN

A successful executor job is not necessarily a successful engineering task. Verification must independently close the action.

## Long-running jobs

Do not mark stale solely by elapsed time.

Use heartbeats and durable progress evidence. While one project waits on a real job, the portfolio manager should inspect other projects.

## Takeover

Takeover requires:
- stale/released writer determination;
- remote reconstruction;
- no credible concurrent write;
- authorized scope;
- isolated recovery workspace when practical.

Old worktree/uncommitted files are preserved.

## Policy updates

AEM policy updates:
1. fetch candidate bundle;
2. validate required files/version;
3. run decision eval suite/replay;
4. compare material policy changes;
5. activate only on success;
6. retain rollback to prior bundle.

Policy update failure does not stop current management if the last-known-good bundle remains valid.

## Kill switch

The runtime must support:
- graceful pause: stop issuing new actions; allow safe observation;
- hard stop: stop new actions and cancel cancel-safe jobs;
- status: show current leases/jobs/actions;
- resume: reconcile before new writes.

A stop must not delete state or silently release uncertain writers.

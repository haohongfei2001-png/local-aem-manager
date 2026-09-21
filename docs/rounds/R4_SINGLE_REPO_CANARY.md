# R4 — Single-repository Canary

Mode: LIVE_CANARY / SELF_REPOSITORY_ONLY

## Canary authority

The only live write target in R4 is this repository:

- repo: `haohongfei2001-png/local-aem-manager`
- implementation base: `r4/single-repo-canary`
- canary branch prefix: `canary/r4-proof-`
- canary path prefix: `canary/`
- scope: `R4_CANARY`

The canary may create one proof branch, one proof file, one pull request, verify them, and close the PR without merging.

It may not:
- write to main;
- merge the canary PR;
- force push;
- delete history/data;
- touch any product repository;
- expand credentials or permissions outside the workflow token already scoped to this repository.

## Runtime controls under test

- one-writer lease;
- persistent kill switch;
- execution reservation/idempotency;
- restart reconciliation to UNKNOWN/SUSPECT rather than blind replay;
- deterministic gate before execution;
- exact canary target/path constraints.

## Canary trigger

The canary workflow triggers only on a push to `r4/single-repo-canary`.

Its token permissions are bounded to:
- contents: write
- pull-requests: write

The runtime action is still further restricted by GitHubCanaryPolicy.

## Success criteria

1. normal unit/replay/shadow/sandbox CI remains green;
2. R4 canary creates only an allowed proof branch/file;
3. proof content is read back exactly;
4. a PR back to the R4 implementation branch is created;
5. the PR is closed and never merged;
6. writer lease returns RELEASED;
7. kill switch prevents a subsequent action;
8. restart reconciliation tests pass;
9. R4 implementation PR merges;
10. exact-main CI passes.

No product repository is a canary in R4.

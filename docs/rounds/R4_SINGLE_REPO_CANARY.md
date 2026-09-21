# R4 — Single-repository Canary

Mode: LIVE_CANARY / SELF_REPOSITORY_ONLY

## Canary authority

The only live write target in R4 is this repository:

- repo: `haohongfei2001-png/local-aem-manager`
- implementation base: `r4/single-repo-canary`
- canary branch prefix: `canary/r4-proof-`
- canary path prefix: `canary/`
- scope: `R4_CANARY`

The runtime may create one proof branch and one proof file and must read the file back exactly.

It may not:
- write to main;
- merge a canary PR;
- force push;
- delete history/data;
- touch any product repository;
- expand credentials or permissions outside the existing workflow token.

## PR capability split discovered by the first canary

The first real canary proved that the GitHub Actions token had:
- Contents: write
- PullRequests: write

The runtime successfully created the bounded proof branch/file and read it back, but GitHub returned HTTP 403 when that Actions token attempted to create a pull request. This is a repository/platform policy restriction, not evidence that branch/file writes failed.

R4 does not expand that repository permission setting.

Therefore R4 certification is split:

1. runtime credential proves bounded branch/file live write + exact read-back;
2. the already-authorized manager GitHub connector creates and closes the proof PR;
3. the PR is verified unmerged;
4. future local-production credential certification must separately prove whether runtime-native PR creation is available.

This limitation is explicit and must not be represented as runtime-native PR capability.

## Runtime controls under test

- one-writer lease;
- persistent kill switch;
- execution reservation/idempotency;
- restart reconciliation to UNKNOWN/SUSPECT rather than blind replay;
- deterministic gate before execution;
- exact canary repo/branch/path constraints.

## Canary trigger

The canary workflow triggers only on a push to `r4/single-repo-canary`.

Its workflow token remains bounded to:
- contents: write
- pull-requests: write

The runtime executor is further restricted by GitHubCanaryPolicy.

## Success criteria

1. normal unit/replay/shadow/sandbox CI remains green;
2. runtime canary creates only an allowed proof branch/file;
3. proof content is read back exactly;
4. if Actions-native PR creation is blocked with HTTP 403, the result explicitly requests external PR verification instead of weakening scope;
5. manager GitHub connector creates/closes the exact proof PR, and it is never merged;
6. writer lease returns RELEASED;
7. kill switch prevents a subsequent action;
8. restart reconciliation tests pass;
9. R4 implementation PR merges;
10. exact-main CI passes.

No product repository is a canary in R4.

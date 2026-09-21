# Legacy AI-Supervisor v3 Donor Audit

Status: SOURCE_REAUDIT_PENDING
Legacy path: /Users/hhf/AI-Supervisor/v3

## Provenance

At Round 0, the local filesystem could not be re-opened because the available Desktop Commander channel had reached its usage limit.

Therefore this file deliberately does **not** claim a fresh source-code audit.

The capability inventory below is based on previously observed and verified runtime behavior from the legacy supervisor and is used only to identify likely donor areas. No v4 architecture decision depends on exact v3 implementation details.

## Previously observed donor capabilities

Likely reusable concepts/components:
- manager + worker process separation;
- browser/CDP connection and page rebinding;
- worker runtime state persistence;
- execution leases / duplicate-send protection concepts;
- GitHub/canonical/CI observation;
- browser degradation handling;
- stop-all / disarm behavior;
- local model enable/disable controls;
- logging and worker status;
- package manifests and current-round bindings;
- browser idle/sleep/wake behavior;
- composer pre-send vs post-send uncertainty distinction.

## Known legacy architectural limitations

The v4 design intentionally removes these assumptions:
- browser ChatGPT tab as the primary/only actuator;
- rule-first WAIT/CONTINUE state machine as the manager brain;
- model/provider-specific manager coupling;
- worker identity permanently tied to one project;
- UI “active/responding” as sufficient progress evidence;
- hard-coded round semantics that compete with project authority.

## Fresh source audit checklist

When local access is available, inspect without modifying or starting v3:

1. directory/module map;
2. process model and launcher;
3. state persistence format;
4. package manifest/parser implementation;
5. GitHub observation code;
6. browser/CDP adapter;
7. composer send/retry semantics;
8. execution lease implementation;
9. stop/disarm/restart semantics;
10. logging/audit format;
11. secrets/config handling;
12. tests/self-test coverage;
13. portability of each component into v4.

Classify each donor item:
- REUSE_AS_IS;
- PORT_WITH_ADAPTER;
- REWRITE;
- RETIRE.

## Safety

Do not:
- start old manager/workers during the audit;
- mutate v3 runtime state;
- delete old backups/logs;
- migrate secrets into the new repo;
- import v3 code before its license/provenance and dependency behavior are understood.

## Round 0 interpretation

The missing source re-audit is a reuse-efficiency gap, not a blocker to the frozen v4 architecture.

Implementation rounds must not claim a specific v3 module was reused until this audit is completed.

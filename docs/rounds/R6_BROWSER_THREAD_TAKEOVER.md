# R6 — Browser / Developer Thread Executor + Stale Takeover

Mode: IMPLEMENTATION + LOCAL_CAPABILITY_CERTIFICATION

## Goal

Implement the control semantics needed for Local AEM to observe and direct developer threads through a browser transport without making browser state the source of truth.

## CI-certifiable deliverables

- ThreadObservation model;
- thread freshness classifier;
- durable delivery ledger;
- pre-send vs post-send uncertainty semantics;
- BrowserTransport contract;
- DeveloperThreadExecutor;
- optional Playwright/CDP capability adapter;
- stale-active takeover assessment;
- ActionPlan support for SEND_THREAD_MESSAGE;
- deterministic tests for retry/no-retry and takeover conditions.

## Send safety

A send attempt has three durable outcomes:

- PRE_SEND_FAILED — no irreversible send is known to have occurred; retry is allowed.
- SENT_CONFIRMED — positive confirmation exists; automatic duplicate send is forbidden.
- POST_SEND_UNKNOWN — the irreversible send may have occurred but confirmation is missing; automatic retry is forbidden.

A browser disconnect, selector loss, or exception after the send commit is treated as POST_SEND_UNKNOWN unless there is positive evidence that commit did not occur.

## Freshness and stale-active

UI labels such as generating/responding are only sensors.

Verified progress includes:
- new developer output;
- remote repository movement;
- CI transition;
- durable local process heartbeat.

A known long-running durable process prevents stale classification even when the developer thread is quiet.

Takeover is allowed only when:
- freshness is STALE;
- the old writer lease is STALE/RELEASED/BLOCKED;
- no credible concurrent process remains;
- remote truth is reconstructable;
- no product/permission boundary is crossed.

ACTIVE becomes SUSPECT before takeover; it is not silently stolen.

## Browser adapter boundary

R6 includes a Playwright/CDP capability adapter but does not hard-code live ChatGPT selectors into the certified runtime.

Live browser behavior must be certified against the user's current Chrome/profile/thread environment before browser_executor_enabled can become true.

CI/fake-transport success is not live-browser certification.

## Local capability certification still required

A real local R6 certification must verify at least:

1. attach/rebind to the intended Chrome profile/session;
2. map configured project IDs to the correct developer threads;
3. read latest assistant output and generating/idle state;
4. confirm a normal send exactly once;
5. prove a pre-send failure can retry;
6. prove a post-send uncertain result does not duplicate;
7. survive tab refresh/rebind;
8. distinguish ghost-active UI from durable progress;
9. perform one safe stale-worker takeover/release sequence;
10. preserve one-writer safety.

Until that evidence exists, R6 remains implementation-complete but live-certification-blocked.

## Exit

Code/CI completion alone is insufficient for full R6 COMPLETE.

R6 becomes COMPLETE only after current local browser capability evidence passes. R7 remains locked until then.

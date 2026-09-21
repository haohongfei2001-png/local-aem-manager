# R5 — Portfolio + Event-driven Scheduling

Mode: IMPLEMENTATION / MULTI_PROJECT_SHADOW

## Goal

Make Local AEM manage a portfolio rather than one permanently bound worker.

The scheduler must react to normalized changes, ask the manager brain for the next portfolio action, and avoid global WAIT when one project is legitimately waiting.

## Delivered design

### Event bus

Normalized events have:
- type;
- source;
- subject;
- observed_at;
- payload;
- freshness_key.

The event bus deduplicates identical freshness keys.

### Event sources

R5 implements polling adapters that publish normalized events:
- GitHub branch/workflow changes;
- registered process-state changes;
- periodic health ticks.

External polling remains an implementation detail. The internal manager loop receives normalized events.

### Portfolio scheduling

For every fresh event:
1. rebuild/read a current portfolio snapshot;
2. ask ManagerBrain for the highest-value next action;
3. pass it through the deterministic gate;
4. if the chosen project only needs WAIT/OBSERVE/NO_ACTION and other projects exist, remove that project from the current selection pass and ask the manager again;
5. dispatch the first approved actionable decision to an injected action sink.

The action sink is not a production executor in R5.

## Safety

R5 does not expand canary write authority and does not enable browser/developer-thread execution.

Project authority and writer-lease rules remain unchanged.

## Verification

Required:
- event freshness dedupe;
- GitHub change events only when state changes;
- process events only when state changes;
- health tick processing;
- a synthetic two-project case where project A is waiting and project B is selected and dispatched;
- all earlier R1-R4 gates remain green.

## Exit

When PR and exact-main CI pass:
- R5 COMPLETE;
- R6 READY;
- do not weaken any previous execution boundary.

# Local AEM Manager v4

Local AEM Manager is the local runtime for the Autonomous Engineering Manager (AEM) playbook.

It runs on the user's Mac, observes GitHub and local execution state, asks a pluggable reasoning model to make engineering-management decisions, enforces deterministic safety/authority gates, and dispatches work to executors such as Codex, shell, GitHub, and browser agents.

## Separation of concerns

- **ai-engineering-manager** = policy / charter / cases / manager evals.
- **local-aem-manager** = local runtime / evidence / state / leases / executors / verification.
- **project repositories** = product truth and project-specific authority.

AEM policy does not replace project authority. Local AEM does not invent product direction.

## v4 design goal

Replace the legacy rule-first supervisor with:

Evidence → Portfolio State → Manager Brain → Policy Gate → Executor → Verification → Re-prioritization

The manager brain may be DeepSeek or another provider. No single model is a permanent dependency.

## Current status

Round 0 architecture is frozen for implementation.

No workers are started by this repository yet. No managed project is modified by Round 0.

See:
- docs/FROZEN_ARCHITECTURE_v4.md
- docs/EXECUTION_PROTOCOL.md
- docs/LEGACY_V3_DONOR_AUDIT.md
- docs/ROADMAP.md
- status/LOCAL_AEM_STATUS.yaml

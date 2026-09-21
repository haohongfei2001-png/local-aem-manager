from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any, Callable

from .gate import GateDisposition, evaluate_decision
from .policy import PolicyBundle


PASSIVE_ACTIONS = {"WAIT_THIS_PROJECT", "NO_ACTION", "OBSERVE"}


@dataclass(frozen=True)
class ScheduleResult:
    event: dict[str, Any]
    decision: dict[str, Any] | None
    gate: dict[str, Any] | None
    skipped_projects: list[str]
    dispatched: bool

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class PortfolioScheduler:
    def __init__(
        self,
        *,
        brain: Any,
        policy: PolicyBundle,
        authorization_for: Callable[[str], dict[str, Any]] | None = None,
        action_sink: Callable[[dict[str, Any], dict[str, Any]], None] | None = None,
    ):
        self.brain = brain
        self.policy = policy
        self.authorization_for = authorization_for or (lambda _project_id: {})
        self.action_sink = action_sink

    def handle(
        self,
        *,
        snapshot: dict[str, Any],
        event: dict[str, Any],
    ) -> ScheduleResult:
        remaining = list(snapshot.get("projects", []))
        skipped: list[str] = []
        last_decision = None
        last_gate = None

        while remaining:
            working = dict(snapshot)
            working["projects"] = remaining
            decision = self.brain.decide(
                policy=self.policy,
                portfolio_snapshot=working,
                recent_context=[
                    {"event": event},
                    {"skipped_projects": list(skipped)},
                ],
            )
            last_decision = decision
            project = next(
                item
                for item in remaining
                if item["project_id"] == decision["project_id"]
            )
            gate = evaluate_decision(
                decision,
                project,
                self.authorization_for(decision["project_id"]),
            )
            last_gate = gate.to_dict()

            if (
                gate.disposition == GateDisposition.APPROVE
                and decision["action_type"] in PASSIVE_ACTIONS
                and len(remaining) > 1
            ):
                skipped.append(decision["project_id"])
                remaining = [
                    item
                    for item in remaining
                    if item["project_id"] != decision["project_id"]
                ]
                continue

            dispatched = False
            if (
                gate.disposition == GateDisposition.APPROVE
                and decision["action_type"] not in PASSIVE_ACTIONS
                and self.action_sink is not None
            ):
                self.action_sink(decision, last_gate)
                dispatched = True

            return ScheduleResult(
                event=event,
                decision=decision,
                gate=last_gate,
                skipped_projects=skipped,
                dispatched=dispatched,
            )

        return ScheduleResult(
            event=event,
            decision=last_decision,
            gate=last_gate,
            skipped_projects=skipped,
            dispatched=False,
        )

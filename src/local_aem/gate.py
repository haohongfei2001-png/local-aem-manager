from __future__ import annotations

from dataclasses import asdict, dataclass
from enum import Enum
from typing import Any


class GateDisposition(str, Enum):
    APPROVE = "APPROVE"
    NARROW_AND_RETRY = "NARROW_AND_RETRY"
    REJECT = "REJECT"
    OWNER_ESCALATION_REQUIRED = "OWNER_ESCALATION_REQUIRED"


@dataclass(frozen=True)
class GateResult:
    disposition: GateDisposition
    reasons: list[str]

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["disposition"] = self.disposition.value
        return payload


OWNER_CANONICAL = {"OWNER_DECISION", "NEEDS_OWNER"}
BLOCKED_CANONICAL = {
    "BLOCKED",
    "NO_GO",
    "DESIGN_ONLY_NOT_AUTHORIZED",
}
HIGH_RISK_OPS = {
    "FORCE_PUSH",
    "DELETE_DATA",
    "ADD_CREDENTIAL",
    "EXPAND_PERMISSION",
}
WRITE_OPS = {"WRITE_BRANCH", "CREATE_PR", "MERGE_PR"}
BLOCKED_SCOPE_WRITE_OPS = WRITE_OPS | {"START_NEXT_SCOPE"}
WRITE_ACTIONS = {"START_EXECUTOR", "TAKEOVER", "FIX_AND_VERIFY"}


def evaluate_decision(
    decision: dict[str, Any],
    project_state: dict[str, Any],
    authorization: dict[str, Any] | None = None,
) -> GateResult:
    authorization = authorization or {}
    reasons: list[str] = []

    if decision["project_id"] != project_state.get("project_id"):
        return GateResult(
            GateDisposition.REJECT,
            ["decision project_id does not match selected project state"],
        )

    if decision["target"].get("repo") != project_state.get("repo"):
        return GateResult(
            GateDisposition.REJECT,
            ["decision target repository does not match project repository"],
        )

    canonical = project_state.get("canonical_status")
    requested = set(decision.get("requested_operations", []))

    if decision.get("owner_required") or decision["action_type"] == "OWNER_ESCALATION":
        return GateResult(
            GateDisposition.OWNER_ESCALATION_REQUIRED,
            [decision.get("owner_reason") or "manager requested owner escalation"],
        )

    if canonical in OWNER_CANONICAL:
        return GateResult(
            GateDisposition.OWNER_ESCALATION_REQUIRED,
            [f"project canonical requires owner decision: {canonical}"],
        )

    risky = sorted(requested & HIGH_RISK_OPS)
    if risky:
        return GateResult(
            GateDisposition.OWNER_ESCALATION_REQUIRED,
            [f"high-risk/owner-gated operations requested: {', '.join(risky)}"],
        )

    if canonical in BLOCKED_CANONICAL and requested & BLOCKED_SCOPE_WRITE_OPS:
        return GateResult(
            GateDisposition.REJECT,
            [
                f"canonical state {canonical} forbids scope-advancing/write operations",
            ],
        )

    if "START_NEXT_SCOPE" in requested:
        if canonical != "READY":
            return GateResult(
                GateDisposition.REJECT,
                [
                    "START_NEXT_SCOPE requested while canonical status is not READY"
                ],
            )
        if not authorization.get("allow_start_ready_scope", False):
            return GateResult(
                GateDisposition.REJECT,
                ["current authorization does not permit starting a READY scope"],
            )

    if "MERGE_PR" in requested and not authorization.get("allow_merge", False):
        return GateResult(
            GateDisposition.REJECT,
            ["current authorization does not permit PR merge"],
        )

    if requested & WRITE_OPS and not authorization.get(
        "allow_repo_writes", False
    ):
        return GateResult(
            GateDisposition.REJECT,
            ["current authorization does not permit repository writes"],
        )

    lease = project_state.get("writer_lease") or {}
    lease_state = lease.get("state")
    if lease_state == "ACTIVE" and decision["action_type"] in WRITE_ACTIONS:
        return GateResult(
            GateDisposition.REJECT,
            ["an ACTIVE writer lease prevents a second writer/takeover"],
        )
    if lease_state == "SUSPECT" and decision["action_type"] == "TAKEOVER":
        return GateResult(
            GateDisposition.NARROW_AND_RETRY,
            ["writer is only SUSPECT; re-observe before declaring it STALE"],
        )

    reasons.append("decision stays within current deterministic authority")
    return GateResult(GateDisposition.APPROVE, reasons)

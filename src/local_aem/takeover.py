from __future__ import annotations

from dataclasses import asdict, dataclass
from enum import Enum
from typing import Any

from .freshness import FreshnessClass


class TakeoverDecision(str, Enum):
    KEEP_CURRENT_WRITER = "KEEP_CURRENT_WRITER"
    MARK_SUSPECT = "MARK_SUSPECT"
    TAKEOVER_ALLOWED = "TAKEOVER_ALLOWED"
    BLOCKED = "BLOCKED"


@dataclass(frozen=True)
class TakeoverAssessment:
    decision: TakeoverDecision
    reason: str

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["decision"] = self.decision.value
        return payload


def assess_takeover(
    *,
    freshness: FreshnessClass,
    writer_state: str,
    remote_reconstructable: bool,
    concurrent_process_credible: bool,
    product_or_permission_boundary: bool,
) -> TakeoverAssessment:
    if product_or_permission_boundary:
        return TakeoverAssessment(
            TakeoverDecision.BLOCKED,
            "takeover would cross a product/permission boundary",
        )

    if concurrent_process_credible:
        return TakeoverAssessment(
            TakeoverDecision.KEEP_CURRENT_WRITER,
            "credible concurrent process evidence exists",
        )

    if freshness == FreshnessClass.PROGRESSING:
        return TakeoverAssessment(
            TakeoverDecision.KEEP_CURRENT_WRITER,
            "verified progress exists",
        )

    if freshness == FreshnessClass.QUIET_BUT_CREDIBLE:
        return TakeoverAssessment(
            TakeoverDecision.KEEP_CURRENT_WRITER,
            "quiet state still has credible non-stale evidence",
        )

    if freshness == FreshnessClass.SUSPECT:
        return TakeoverAssessment(
            TakeoverDecision.MARK_SUSPECT,
            "evidence is ambiguous; re-observe before takeover",
        )

    if writer_state == "ACTIVE":
        return TakeoverAssessment(
            TakeoverDecision.MARK_SUSPECT,
            "writer is still ACTIVE; reconcile lease before takeover",
        )

    if not remote_reconstructable:
        return TakeoverAssessment(
            TakeoverDecision.BLOCKED,
            "remote state cannot be safely reconstructed",
        )

    if freshness == FreshnessClass.STALE and writer_state in {
        "STALE",
        "RELEASED",
        "BLOCKED",
    }:
        return TakeoverAssessment(
            TakeoverDecision.TAKEOVER_ALLOWED,
            "writer is stale/released and remote truth is reconstructable",
        )

    return TakeoverAssessment(
        TakeoverDecision.MARK_SUSPECT,
        "takeover preconditions are not yet fully proven",
    )

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Any


class FreshnessClass(str, Enum):
    PROGRESSING = "PROGRESSING"
    QUIET_BUT_CREDIBLE = "QUIET_BUT_CREDIBLE"
    SUSPECT = "SUSPECT"
    STALE = "STALE"


@dataclass(frozen=True)
class FreshnessEvidence:
    ui_generating: bool = False
    message_changed: bool = False
    repo_changed: bool = False
    ci_changed: bool = False
    process_heartbeat: bool = False
    durable_job_running: bool = False
    transport_connected: bool = True
    elapsed_seconds_without_progress: int = 0


def classify_freshness(
    evidence: FreshnessEvidence,
    *,
    suspect_after_seconds: int = 900,
    stale_after_seconds: int = 1800,
) -> FreshnessClass:
    if (
        evidence.message_changed
        or evidence.repo_changed
        or evidence.ci_changed
        or evidence.process_heartbeat
    ):
        return FreshnessClass.PROGRESSING

    if evidence.durable_job_running:
        return FreshnessClass.QUIET_BUT_CREDIBLE

    if evidence.elapsed_seconds_without_progress >= stale_after_seconds:
        return FreshnessClass.STALE

    if (
        not evidence.transport_connected
        or evidence.elapsed_seconds_without_progress >= suspect_after_seconds
    ):
        return FreshnessClass.SUSPECT

    # UI generating/responding alone is only a sensor and never proves progress.
    return FreshnessClass.QUIET_BUT_CREDIBLE


def freshness_payload(
    evidence: FreshnessEvidence,
    classification: FreshnessClass,
) -> dict[str, Any]:
    return {
        "classification": classification.value,
        "evidence": {
            "ui_generating": evidence.ui_generating,
            "message_changed": evidence.message_changed,
            "repo_changed": evidence.repo_changed,
            "ci_changed": evidence.ci_changed,
            "process_heartbeat": evidence.process_heartbeat,
            "durable_job_running": evidence.durable_job_running,
            "transport_connected": evidence.transport_connected,
            "elapsed_seconds_without_progress": (
                evidence.elapsed_seconds_without_progress
            ),
        },
    }

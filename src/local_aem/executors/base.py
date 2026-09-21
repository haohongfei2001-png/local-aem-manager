from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Protocol


class ExecutorState(str, Enum):
    PREPARED = "PREPARED"
    RUNNING = "RUNNING"
    SUCCEEDED = "SUCCEEDED"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"
    UNKNOWN = "UNKNOWN"


@dataclass
class ExecutorResult:
    job_id: str
    executor: str
    state: ExecutorState
    detail: str
    outputs: dict[str, Any] = field(default_factory=dict)
    started_at: str | None = None
    ended_at: str | None = None
    replayed: bool = False

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["state"] = self.state.value
        return payload


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


class Executor(Protocol):
    name: str

    def capability_probe(self) -> dict[str, Any]:
        ...

    def prepare(self, plan: dict[str, Any]) -> None:
        ...

    def execute(self, plan: dict[str, Any]) -> ExecutorResult:
        ...

    def observe(self, job_id: str) -> ExecutorResult | None:
        ...

    def cancel(self, job_id: str) -> bool:
        ...

    def collect_result(self, job_id: str) -> ExecutorResult | None:
        ...

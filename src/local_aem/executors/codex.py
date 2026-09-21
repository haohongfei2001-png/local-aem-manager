from __future__ import annotations

import shutil
import uuid

from .base import ExecutorResult, ExecutorState, utc_now
from .shell import ExecutorSafetyError


class CodexExecutor:
    name = "CODEX"

    def __init__(self, binary: str = "codex"):
        self.binary = binary
        self._jobs: dict[str, ExecutorResult] = {}

    def capability_probe(self) -> dict:
        path = shutil.which(self.binary)
        return {
            "executor": self.name,
            "binary": self.binary,
            "binary_path": path,
            "available": path is not None,
            "dry_run_supported": True,
            "live_execution_enabled": False,
        }

    def prepare(self, plan: dict) -> None:
        if plan["operation"] != "CODEX_TASK":
            raise ExecutorSafetyError("CodexExecutor only accepts CODEX_TASK")
        if not plan["dry_run"]:
            raise ExecutorSafetyError("R3 forbids live Codex execution")

    def execute(self, plan: dict) -> ExecutorResult:
        self.prepare(plan)
        job_id = f"codex-{uuid.uuid4().hex[:16]}"
        now = utc_now()
        result = ExecutorResult(
            job_id=job_id,
            executor=self.name,
            state=ExecutorState.SUCCEEDED,
            detail="Codex task simulated; no Codex process was started",
            outputs={
                "simulated": True,
                "capability": self.capability_probe(),
                "task": plan["params"].get("task"),
            },
            started_at=now,
            ended_at=utc_now(),
        )
        self._jobs[job_id] = result
        return result

    def observe(self, job_id: str) -> ExecutorResult | None:
        return self._jobs.get(job_id)

    def cancel(self, job_id: str) -> bool:
        return False

    def collect_result(self, job_id: str) -> ExecutorResult | None:
        return self._jobs.get(job_id)

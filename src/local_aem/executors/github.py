from __future__ import annotations

import uuid

from .base import ExecutorResult, ExecutorState, utc_now
from .shell import ExecutorSafetyError


class GitHubExecutor:
    name = "GITHUB"

    def __init__(self):
        self._jobs: dict[str, ExecutorResult] = {}

    def capability_probe(self) -> dict:
        return {
            "executor": self.name,
            "dry_run_supported": True,
            "live_mutations_enabled": False,
        }

    def prepare(self, plan: dict) -> None:
        if plan["operation"] != "GITHUB_MUTATION":
            raise ExecutorSafetyError(
                "GitHubExecutor only accepts GITHUB_MUTATION"
            )
        if not plan["dry_run"]:
            raise ExecutorSafetyError(
                "R3 forbids live GitHub mutations"
            )

    def execute(self, plan: dict) -> ExecutorResult:
        self.prepare(plan)
        job_id = f"github-{uuid.uuid4().hex[:16]}"
        now = utc_now()
        result = ExecutorResult(
            job_id=job_id,
            executor=self.name,
            state=ExecutorState.SUCCEEDED,
            detail="GitHub mutation simulated; no network write was performed",
            outputs={
                "simulated": True,
                "target": plan["target"],
                "params": plan["params"],
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

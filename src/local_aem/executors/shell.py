from __future__ import annotations

import os
import subprocess
import uuid
from pathlib import Path

from .base import ExecutorResult, ExecutorState, utc_now


class ExecutorSafetyError(RuntimeError):
    pass


class ShellExecutor:
    name = "SHELL"

    def __init__(
        self,
        *,
        sandbox_root: str | Path,
        allowed_programs: set[str],
        timeout_seconds: int = 60,
    ):
        self.sandbox_root = Path(sandbox_root).resolve()
        self.sandbox_root.mkdir(parents=True, exist_ok=True)
        self.allowed_programs = set(allowed_programs)
        self.timeout_seconds = timeout_seconds
        self._jobs: dict[str, ExecutorResult] = {}

    def capability_probe(self) -> dict:
        return {
            "executor": self.name,
            "sandbox_root": str(self.sandbox_root),
            "allowed_programs": sorted(self.allowed_programs),
            "live_sandbox_execution": True,
        }

    def _cwd(self, value: str | None) -> Path:
        candidate = (
            self.sandbox_root
            if not value
            else (self.sandbox_root / value).resolve()
        )
        try:
            candidate.relative_to(self.sandbox_root)
        except ValueError as exc:
            raise ExecutorSafetyError("cwd escapes sandbox root") from exc
        candidate.mkdir(parents=True, exist_ok=True)
        return candidate

    def prepare(self, plan: dict) -> None:
        if plan["operation"] != "RUN_SHELL":
            raise ExecutorSafetyError("ShellExecutor only accepts RUN_SHELL")
        argv = plan["params"].get("argv")
        if not isinstance(argv, list) or not argv or not all(
            isinstance(item, str) for item in argv
        ):
            raise ExecutorSafetyError("RUN_SHELL params.argv must be a string list")
        program = Path(argv[0]).name
        if program not in self.allowed_programs:
            raise ExecutorSafetyError(
                f"program {program!r} is not allowed in the R3 sandbox"
            )
        self._cwd(plan["params"].get("cwd"))

    def execute(self, plan: dict) -> ExecutorResult:
        self.prepare(plan)
        job_id = f"shell-{uuid.uuid4().hex[:16]}"
        started = utc_now()
        if plan["dry_run"]:
            result = ExecutorResult(
                job_id=job_id,
                executor=self.name,
                state=ExecutorState.SUCCEEDED,
                detail="dry-run shell action accepted without execution",
                outputs={"simulated": True, "argv": plan["params"]["argv"]},
                started_at=started,
                ended_at=utc_now(),
            )
            self._jobs[job_id] = result
            return result

        cwd = self._cwd(plan["params"].get("cwd"))
        env = {
            "PATH": os.environ.get("PATH", ""),
            "HOME": str(self.sandbox_root),
            "TMPDIR": str(self.sandbox_root),
            "LANG": os.environ.get("LANG", "C.UTF-8"),
        }
        try:
            completed = subprocess.run(
                plan["params"]["argv"],
                cwd=cwd,
                env=env,
                capture_output=True,
                text=True,
                timeout=min(
                    int(plan["params"].get("timeout_seconds", self.timeout_seconds)),
                    self.timeout_seconds,
                ),
                check=False,
            )
            state = (
                ExecutorState.SUCCEEDED
                if completed.returncode == 0
                else ExecutorState.FAILED
            )
            result = ExecutorResult(
                job_id=job_id,
                executor=self.name,
                state=state,
                detail=f"process exited with code {completed.returncode}",
                outputs={
                    "returncode": completed.returncode,
                    "stdout": completed.stdout,
                    "stderr": completed.stderr,
                    "cwd": str(cwd),
                },
                started_at=started,
                ended_at=utc_now(),
            )
        except subprocess.TimeoutExpired as exc:
            result = ExecutorResult(
                job_id=job_id,
                executor=self.name,
                state=ExecutorState.FAILED,
                detail="sandbox command timed out",
                outputs={
                    "stdout": exc.stdout or "",
                    "stderr": exc.stderr or "",
                },
                started_at=started,
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

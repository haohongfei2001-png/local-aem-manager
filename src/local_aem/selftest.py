from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path

from .coordinator import ExecutionCoordinator
from .executors import CodexExecutor, GitHubExecutor, ShellExecutor
from .gate import GateDisposition, GateResult
from .jobs import ExecutionLedger


def _plan(
    *,
    action_id: str,
    executor: str,
    operation: str,
    params: dict,
    verification: list[dict],
    idempotency_key: str,
    dry_run: bool,
) -> dict:
    return {
        "action_id": action_id,
        "decision_id": f"decision-{action_id}",
        "project_id": "r3-sandbox",
        "executor": executor,
        "operation": operation,
        "target": {
            "repo": "sandbox/local",
            "branch": "sandbox",
            "scope": "R3",
        },
        "params": params,
        "verification": verification,
        "idempotency_key": idempotency_key,
        "dry_run": dry_run,
    }


def run_executor_selftest() -> dict:
    approved = GateResult(
        GateDisposition.APPROVE,
        ["R3 sandbox self-test"],
    )
    with tempfile.TemporaryDirectory(prefix="local-aem-r3-") as tmp:
        root = Path(tmp)
        python_program = Path(sys.executable).name
        shell = ShellExecutor(
            sandbox_root=root / "shell",
            allowed_programs={python_program},
        )
        github = GitHubExecutor()
        codex = CodexExecutor()
        with ExecutionLedger(root / "execution.db") as ledger:
            coordinator = ExecutionCoordinator(
                ledger=ledger,
                executors={
                    "SHELL": shell,
                    "GITHUB": github,
                    "CODEX": codex,
                },
            )

            shell_plan = _plan(
                action_id="shell-selftest",
                executor="SHELL",
                operation="RUN_SHELL",
                params={
                    "argv": [
                        sys.executable,
                        "-c",
                        (
                            "from pathlib import Path; "
                            "Path('out.txt').write_text('ok', encoding='utf-8')"
                        ),
                    ],
                    "cwd": ".",
                },
                verification=[
                    {"type": "JOB_SUCCEEDED"},
                    {"type": "FILE_EXISTS", "path": "out.txt"},
                    {
                        "type": "FILE_TEXT_EQUALS",
                        "path": "out.txt",
                        "expected": "ok",
                    },
                ],
                idempotency_key="r3-shell-once",
                dry_run=False,
            )
            shell_first = coordinator.run(
                shell_plan,
                gate_result=approved,
            )
            shell_replay = coordinator.run(
                shell_plan,
                gate_result=approved,
            )

            github_plan = _plan(
                action_id="github-dry-run",
                executor="GITHUB",
                operation="GITHUB_MUTATION",
                params={"intent": "create sandbox pull request"},
                verification=[{"type": "JOB_SUCCEEDED"}],
                idempotency_key="r3-github-dry",
                dry_run=True,
            )
            github_result = coordinator.run(
                github_plan,
                gate_result=approved,
            )

            codex_plan = _plan(
                action_id="codex-dry-run",
                executor="CODEX",
                operation="CODEX_TASK",
                params={"task": "sandbox-only coding task"},
                verification=[{"type": "JOB_SUCCEEDED"}],
                idempotency_key="r3-codex-dry",
                dry_run=True,
            )
            codex_result = coordinator.run(
                codex_plan,
                gate_result=approved,
            )

        summary = {
            "shell": shell_first,
            "shell_replay": shell_replay,
            "github": github_result,
            "codex": codex_result,
            "codex_capability": codex.capability_probe(),
        }
        summary["passed"] = bool(
            shell_first["verification"]["passed"]
            and shell_replay["replayed"]
            and github_result["verification"]["passed"]
            and github_result["outputs"]["simulated"]
            and codex_result["verification"]["passed"]
            and codex_result["outputs"]["simulated"]
        )
        return summary


def main() -> int:
    summary = run_executor_selftest()
    print(json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True))
    return 0 if summary["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())

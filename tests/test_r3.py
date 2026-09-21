import json
import sys
from pathlib import Path

import pytest

from local_aem.action import load_action_schema
from local_aem.coordinator import CoordinatorError, ExecutionCoordinator
from local_aem.executors import (
    CodexExecutor,
    ExecutorSafetyError,
    GitHubExecutor,
    ShellExecutor,
)
from local_aem.gate import GateDisposition, GateResult
from local_aem.jobs import ExecutionLedger
from local_aem.selftest import run_executor_selftest


def test_packaged_action_schema_matches_repository_schema():
    packaged = load_action_schema()
    root = json.loads(
        (Path(__file__).resolve().parents[1]
         / "schemas"
         / "action-plan.schema.json").read_text(encoding="utf-8")
    )
    assert packaged == root


def test_executor_selftest_runs_and_replays_idempotently():
    summary = run_executor_selftest()
    assert summary["passed"] is True
    assert summary["shell"]["replayed"] is False
    assert summary["shell_replay"]["replayed"] is True
    assert summary["github"]["outputs"]["simulated"] is True
    assert summary["codex"]["outputs"]["simulated"] is True


def test_shell_rejects_escape_and_unapproved_program(tmp_path: Path):
    shell = ShellExecutor(
        sandbox_root=tmp_path / "sandbox",
        allowed_programs={Path(sys.executable).name},
    )
    base = {
        "operation": "RUN_SHELL",
        "dry_run": False,
        "params": {"argv": [sys.executable, "-c", "print('ok')"]},
    }

    escaping = dict(base)
    escaping["params"] = {
        "argv": [sys.executable, "-c", "print('ok')"],
        "cwd": "../outside",
    }
    with pytest.raises(ExecutorSafetyError):
        shell.prepare(escaping)

    forbidden = dict(base)
    forbidden["params"] = {"argv": ["sh", "-c", "echo no"]}
    with pytest.raises(ExecutorSafetyError):
        shell.prepare(forbidden)


def test_live_github_and_codex_are_disabled_in_r3():
    github = GitHubExecutor()
    with pytest.raises(ExecutorSafetyError):
        github.prepare(
            {
                "operation": "GITHUB_MUTATION",
                "dry_run": False,
            }
        )

    codex = CodexExecutor()
    with pytest.raises(ExecutorSafetyError):
        codex.prepare(
            {
                "operation": "CODEX_TASK",
                "dry_run": False,
            }
        )


def test_coordinator_refuses_nonapproved_gate(tmp_path: Path):
    plan = {
        "action_id": "a",
        "decision_id": "d",
        "project_id": "p",
        "executor": "GITHUB",
        "operation": "GITHUB_MUTATION",
        "target": {"repo": "sandbox/repo", "branch": "main", "scope": "R3"},
        "params": {"intent": "dry-run"},
        "verification": [{"type": "JOB_SUCCEEDED"}],
        "idempotency_key": "k",
        "dry_run": True,
    }
    with ExecutionLedger(tmp_path / "jobs.db") as ledger:
        coordinator = ExecutionCoordinator(
            ledger=ledger,
            executors={"GITHUB": GitHubExecutor()},
        )
        with pytest.raises(CoordinatorError):
            coordinator.run(
                plan,
                gate_result=GateResult(
                    GateDisposition.REJECT,
                    ["test rejection"],
                ),
            )

import base64
from pathlib import Path

import pytest

from local_aem.control import RuntimeControl, RuntimePaused
from local_aem.executors import (
    ExecutorSafetyError,
    GitHubCanaryError,
    GitHubCanaryExecutor,
    GitHubCanaryPolicy,
)
from local_aem.jobs import ExecutionLedger
from local_aem.leases import LeaseConflict, WriterLeaseStore


def test_one_writer_lease_and_restart_reconciliation(tmp_path: Path):
    path = tmp_path / "runtime.db"
    with WriterLeaseStore(path) as store:
        lease = store.acquire(
            repo="owner/repo",
            branch="canary/r4-proof-1",
            scope="R4",
            holder="writer-a",
        )
        assert lease.state == "ACTIVE"
        with pytest.raises(LeaseConflict):
            store.acquire(
                repo="owner/repo",
                branch="canary/r4-proof-1",
                scope="R4",
                holder="writer-b",
            )

    with WriterLeaseStore(path) as restarted:
        assert restarted.reconcile_restart() == 1
        lease = restarted.get("owner/repo", "canary/r4-proof-1", "R4")
        assert lease is not None
        assert lease.state == "SUSPECT"


def test_execution_reservation_becomes_unknown_after_restart(tmp_path: Path):
    path = tmp_path / "jobs.db"
    with ExecutionLedger(path) as ledger:
        ledger.reserve(
            idempotency_key="same-key",
            action_id="a1",
            executor="GITHUB",
        )

    with ExecutionLedger(path) as restarted:
        assert restarted.reconcile_restart() == 1
        reservation = restarted.reservation("same-key")
        assert reservation is not None
        assert reservation["state"] == "UNKNOWN_PENDING_RECONCILIATION"


def test_kill_switch_defaults_paused_and_requires_resume(tmp_path: Path):
    with RuntimeControl(tmp_path / "control.db") as control:
        assert control.mode() == "PAUSED"
        with pytest.raises(RuntimePaused):
            control.assert_new_actions_allowed()
        control.resume()
        control.assert_new_actions_allowed()
        control.pause()
        with pytest.raises(RuntimePaused):
            control.assert_new_actions_allowed()
        control.hard_stop()
        assert control.mode() == "STOPPED"
        with pytest.raises(RuntimePaused):
            control.assert_new_actions_allowed()


def _plan(
    repo="owner/repo",
    branch="canary/r4-proof-1",
    path="canary/proof.json",
):
    return {
        "operation": "GITHUB_MUTATION",
        "dry_run": False,
        "target": {"repo": repo},
        "params": {
            "kind": "CANARY_PR_CYCLE",
            "branch": branch,
            "base_branch": "r4/single-repo-canary",
            "path": path,
            "content": "{}\n",
        },
    }


def test_canary_executor_scope_is_fail_closed():
    executor = GitHubCanaryExecutor(
        policy=GitHubCanaryPolicy(
            repo="owner/repo",
            base_branch="r4/single-repo-canary",
            branch_prefix="canary/r4-proof-",
            path_prefix="canary/",
        )
    )
    executor.prepare(_plan())

    with pytest.raises(ExecutorSafetyError):
        executor.prepare(_plan(repo="owner/other"))
    with pytest.raises(ExecutorSafetyError):
        executor.prepare(_plan(branch="main"))
    with pytest.raises(ExecutorSafetyError):
        executor.prepare(_plan(path="../escape"))

    dry = _plan()
    dry["dry_run"] = True
    with pytest.raises(ExecutorSafetyError):
        executor.prepare(dry)


def test_actions_pr_403_becomes_external_pr_verification(monkeypatch):
    executor = GitHubCanaryExecutor(
        policy=GitHubCanaryPolicy(
            repo="owner/repo",
            base_branch="r4/single-repo-canary",
            branch_prefix="canary/r4-proof-",
            path_prefix="canary/",
        )
    )
    plan = {
        "operation": "GITHUB_MUTATION",
        "dry_run": False,
        "target": {"repo": "owner/repo"},
        "params": {
            "kind": "CANARY_PR_CYCLE",
            "branch": "canary/r4-proof-1",
            "base_branch": "r4/single-repo-canary",
            "path": "canary/proof.json",
            "content": "{}\n",
        },
    }

    def fake_request(method, path, payload=None, query=None):
        if method == "GET" and "/branches/" in path:
            return {"commit": {"sha": "base"}}
        if method == "POST" and path.endswith("/git/refs"):
            return {"ref": "refs/heads/canary/r4-proof-1"}
        if method == "PUT" and "/contents/" in path:
            return {"commit": {"sha": "proof-sha"}}
        if method == "GET" and "/contents/" in path:
            return {
                "content": base64.b64encode(b"{}\n").decode("ascii")
            }
        if method == "POST" and path.endswith("/pulls"):
            raise GitHubCanaryError("PR creation blocked", status=403)
        raise AssertionError((method, path))

    monkeypatch.setattr(executor, "_request", fake_request)
    result = executor.execute(plan)
    assert result.state.value == "SUCCEEDED"
    assert result.outputs["external_pr_required"] is True
    assert result.outputs["commit_sha"] == "proof-sha"
    assert result.outputs["merged"] is False

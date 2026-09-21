from __future__ import annotations

import json
import os
from pathlib import Path

from .control import RuntimeControl, RuntimePaused
from .coordinator import ExecutionCoordinator
from .executors import GitHubCanaryExecutor, GitHubCanaryPolicy
from .gate import GateDisposition, GateResult
from .jobs import ExecutionLedger
from .leases import WriterLeaseStore


def run_canary() -> dict:
    repo = os.environ.get(
        "AEM_CANARY_REPO", "haohongfei2001-png/local-aem-manager"
    )
    base_branch = os.environ.get(
        "AEM_CANARY_BASE_BRANCH", "r4/single-repo-canary"
    )
    nonce = os.environ.get("AEM_CANARY_NONCE")
    if not nonce:
        raise RuntimeError("AEM_CANARY_NONCE is required")

    branch = f"canary/r4-proof-{nonce}"
    path = f"canary/r4-proof-{nonce}.json"
    holder = f"r4-canary-{nonce}"
    runtime_root = Path(
        os.environ.get("RUNNER_TEMP", "/tmp")
    ) / f"local-aem-r4-{nonce}"
    runtime_root.mkdir(parents=True, exist_ok=True)

    proof = json.dumps(
        {
            "round": "R4",
            "nonce": nonce,
            "repo": repo,
            "base_branch": base_branch,
            "intent": "bounded-single-repository-canary",
        },
        sort_keys=True,
        indent=2,
    ) + "\n"

    policy = GitHubCanaryPolicy(
        repo=repo,
        base_branch=base_branch,
        branch_prefix="canary/r4-proof-",
        path_prefix="canary/",
    )
    executor = GitHubCanaryExecutor(policy=policy)
    approved = GateResult(
        GateDisposition.APPROVE,
        ["R4 canary scope pre-authorized by round contract"],
    )

    plan = {
        "action_id": f"r4-canary-{nonce}",
        "decision_id": f"r4-canary-decision-{nonce}",
        "project_id": "local-aem-r4-canary",
        "executor": "GITHUB",
        "operation": "GITHUB_MUTATION",
        "target": {
            "repo": repo,
            "branch": branch,
            "scope": "R4_CANARY",
        },
        "params": {
            "kind": "CANARY_PR_CYCLE",
            "branch": branch,
            "base_branch": base_branch,
            "path": path,
            "content": proof,
            "title": f"R4 canary proof {nonce}",
        },
        "verification": [{"type": "JOB_SUCCEEDED"}],
        "idempotency_key": f"r4-canary-{nonce}",
        "dry_run": False,
    }

    db_path = runtime_root / "runtime.db"
    with (
        RuntimeControl(db_path) as control,
        WriterLeaseStore(db_path) as leases,
        ExecutionLedger(db_path) as ledger,
    ):
        control.resume()
        lease = leases.acquire(
            repo=repo,
            branch=branch,
            scope="R4_CANARY",
            holder=holder,
        )
        coordinator = ExecutionCoordinator(
            ledger=ledger,
            executors={"GITHUB": executor},
            control=control,
        )
        try:
            result = coordinator.run(plan, gate_result=approved)
        finally:
            leases.release(
                repo=repo,
                branch=branch,
                scope="R4_CANARY",
                holder=holder,
            )
            control.pause()

        kill_switch_verified = False
        try:
            coordinator.run(plan, gate_result=approved)
        except RuntimePaused:
            kill_switch_verified = True

        final_lease = leases.get(repo, branch, "R4_CANARY")

    return {
        "passed": bool(
            result["verification"]["passed"]
            and result["state"] == "SUCCEEDED"
            and result["outputs"].get("merged") is False
            and kill_switch_verified
            and final_lease is not None
            and final_lease.state == "RELEASED"
        ),
        "result": result,
        "writer_lease": final_lease.to_dict() if final_lease else None,
        "kill_switch_verified": kill_switch_verified,
        "capability": executor.capability_probe(),
    }


def main() -> int:
    summary = run_canary()
    print(json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True))
    return 0 if summary["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())

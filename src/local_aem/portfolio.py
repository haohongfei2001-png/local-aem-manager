from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

import yaml

from .github_read import GitHubReadClient


def _canonical_from_yaml(
    text: str,
) -> tuple[str | None, str | None, str | None]:
    try:
        payload = yaml.safe_load(text)
    except yaml.YAMLError:
        return None, None, None
    if not isinstance(payload, dict):
        return None, None, None
    package_status = payload.get("package_status")
    current = payload.get("current_round")
    if isinstance(current, dict):
        scope = current.get("id")
        current_status = current.get("status")
    else:
        scope = None
        current_status = None
    canonical = current_status or payload.get("status") or package_status
    return (
        str(canonical) if canonical is not None else None,
        str(scope) if scope is not None else None,
        str(package_status) if package_status is not None else None,
    )


def observe_project(
    client: GitHubReadClient, project: dict[str, Any]
) -> dict[str, Any]:
    project_id = str(project["id"])
    repo = str(project["repo"])
    branch_name = str(project.get("default_branch", "main"))

    repo_meta = client.repo(repo)
    branch = client.branch(repo, branch_name)
    sha = branch["commit"]["sha"]
    combined = client.combined_status(repo, sha)
    workflows = client.workflow_runs(repo, sha)
    runs = workflows.get("workflow_runs", [])

    running = [
        run
        for run in runs
        if run.get("status")
        in {"queued", "in_progress", "waiting", "requested"}
    ]
    failures = [
        run
        for run in runs
        if run.get("status") == "completed"
        and run.get("conclusion")
        in {"failure", "cancelled", "timed_out", "action_required"}
    ]

    canonical_status = None
    current_scope = None
    package_status = None
    status_path = project.get("status_path")
    status_digest = None
    if status_path:
        import hashlib

        status_text = client.file_text(repo, str(status_path), branch_name)
        canonical_status, current_scope, package_status = _canonical_from_yaml(
            status_text
        )
        status_digest = hashlib.sha256(
            status_text.encode("utf-8")
        ).hexdigest()

    if canonical_status in {"OWNER_DECISION", "NEEDS_OWNER"}:
        portfolio_state = "NEEDS_OWNER"
        blocker_type = "AUTHORITY"
        owner_required = True
    elif canonical_status in {
        "BLOCKED",
        "NO_GO",
        "DESIGN_ONLY_NOT_AUTHORIZED",
    }:
        portfolio_state = "BLOCKED"
        blocker_type = "AUTHORITY"
        owner_required = False
    elif package_status == "COMPLETE":
        portfolio_state = "COMPLETE"
        blocker_type = "NONE"
        owner_required = False
    elif running:
        portfolio_state = "ACTIVE"
        blocker_type = "NONE"
        owner_required = False
    else:
        portfolio_state = "IDLE"
        blocker_type = "NONE"
        owner_required = False

    observed_at = datetime.now(timezone.utc).isoformat()
    return {
        "project_id": project_id,
        "repo": repo,
        "default_branch": branch_name,
        "current_scope": current_scope,
        "canonical_status": canonical_status,
        "remote_head": sha,
        "portfolio_state": portfolio_state,
        "observed_at": observed_at,
        "last_verified_progress_at": None,
        "writer_lease": {
            "state": "RELEASED",
            "holder": None,
            "branch": branch_name,
            "scope": current_scope,
            "last_verified_activity_at": None,
        },
        "checks": {
            "combined_status": combined.get("state"),
            "status_count": len(combined.get("statuses", [])),
            "workflow_run_count": len(runs),
            "running_workflows": [
                {
                    "id": run.get("id"),
                    "name": run.get("name"),
                    "status": run.get("status"),
                    "head_sha": run.get("head_sha"),
                }
                for run in running
            ],
            "failed_workflows": [
                {
                    "id": run.get("id"),
                    "name": run.get("name"),
                    "conclusion": run.get("conclusion"),
                    "head_sha": run.get("head_sha"),
                }
                for run in failures
            ],
        },
        "blocker": {
            "type": blocker_type,
            "description": canonical_status
            if blocker_type != "NONE"
            else None,
            "owner_required": owner_required,
        },
        "next_action_summary": None,
        "evidence": {
            "repo_private": bool(repo_meta.get("private", False)),
            "branch_protected": bool(branch.get("protected", False)),
            "status_path": status_path,
            "status_digest": status_digest,
        },
    }


def observe_portfolio(
    client: GitHubReadClient, projects: list[dict[str, Any]]
) -> list[dict[str, Any]]:
    return [observe_project(client, project) for project in projects]

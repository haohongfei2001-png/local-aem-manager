from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Callable

from .events import Event
from .github_read import GitHubReadClient


def _stamp() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass
class GitHubPollSource:
    client: GitHubReadClient
    projects: list[dict[str, Any]]

    def __post_init__(self) -> None:
        self._last: dict[str, str] = {}

    def poll(self) -> list[Event]:
        events: list[Event] = []
        for project in self.projects:
            project_id = str(project["id"])
            repo = str(project["repo"])
            branch_name = str(project.get("default_branch", "main"))
            branch = self.client.branch(repo, branch_name)
            sha = branch["commit"]["sha"]
            workflows = self.client.workflow_runs(repo, sha).get(
                "workflow_runs", []
            )
            summary = {
                "head": sha,
                "workflows": [
                    {
                        "id": run.get("id"),
                        "status": run.get("status"),
                        "conclusion": run.get("conclusion"),
                    }
                    for run in workflows
                ],
            }
            signature = json.dumps(summary, sort_keys=True)
            if self._last.get(project_id) == signature:
                continue
            self._last[project_id] = signature
            events.append(
                Event(
                    type="GITHUB_CHANGED",
                    source="github",
                    subject=project_id,
                    observed_at=_stamp(),
                    payload={"repo": repo, **summary},
                    freshness_key=f"github:{project_id}:{signature}",
                )
            )
        return events


class ProcessPollSource:
    def __init__(self, probes: dict[str, Callable[[], dict[str, Any]]]):
        self.probes = probes
        self._last: dict[str, str] = {}

    def poll(self) -> list[Event]:
        events: list[Event] = []
        for name, probe in self.probes.items():
            payload = probe()
            signature = json.dumps(payload, sort_keys=True)
            if self._last.get(name) == signature:
                continue
            self._last[name] = signature
            events.append(
                Event(
                    type="PROCESS_CHANGED",
                    source="process",
                    subject=name,
                    observed_at=_stamp(),
                    payload=payload,
                    freshness_key=f"process:{name}:{signature}",
                )
            )
        return events


class HealthTickSource:
    def __init__(self):
        self.sequence = 0

    def poll(self) -> list[Event]:
        self.sequence += 1
        stamp = _stamp()
        return [
            Event(
                type="HEALTH_TICK",
                source="timer",
                subject="portfolio",
                observed_at=stamp,
                payload={"sequence": self.sequence},
                freshness_key=f"health:{self.sequence}:{stamp}",
            )
        ]

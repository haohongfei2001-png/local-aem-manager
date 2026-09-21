import asyncio

from local_aem.event_sources import GitHubPollSource, HealthTickSource, ProcessPollSource
from local_aem.events import Event, EventBus
from local_aem.policy import PolicyBundle
from local_aem.scheduler import PortfolioScheduler
from local_aem.service import PortfolioService


def _policy():
    return PolicyBundle(
        repo="owner/aem",
        version="0.2.0",
        digest="d",
        files={},
        source="test",
    )


def _project(project_id, state="IDLE"):
    return {
        "project_id": project_id,
        "repo": f"owner/{project_id.lower()}",
        "canonical_status": "IN_PROGRESS",
        "portfolio_state": state,
        "writer_lease": {"state": "RELEASED"},
    }


def _decision(project_id, action_type, *, executor="NONE", operations=None):
    return {
        "decision_id": f"d-{project_id}-{action_type}",
        "project_id": project_id,
        "evidence_snapshot_id": "s1",
        "assessment": (
            "WAITING_REAL_PROCESS"
            if action_type == "WAIT_THIS_PROJECT"
            else "VERIFYING"
        ),
        "priority": 80,
        "owner_required": False,
        "owner_reason": None,
        "action_type": action_type,
        "executor": executor,
        "target": {
            "repo": f"owner/{project_id.lower()}",
            "branch": "main",
            "scope": "R5",
        },
        "rationale": "test decision",
        "instructions": "test instruction",
        "requested_operations": operations or ["READ_REPO"],
        "verification": ["remote truth"],
        "expected_state": None,
        "idempotency_key": f"k-{project_id}-{action_type}",
    }


class SwitchingBrain:
    def decide(self, *, policy, portfolio_snapshot, recent_context=None):
        ids = [p["project_id"] for p in portfolio_snapshot["projects"]]
        if "A" in ids:
            return _decision("A", "WAIT_THIS_PROJECT")
        return _decision("B", "VERIFY")


def test_waiting_project_does_not_global_wait():
    dispatched = []
    scheduler = PortfolioScheduler(
        brain=SwitchingBrain(),
        policy=_policy(),
        action_sink=lambda decision, gate: dispatched.append(decision["project_id"]),
    )
    snapshot = {
        "snapshot_id": "s1",
        "projects": [_project("A", "WAITING_EXTERNAL"), _project("B")],
    }
    result = scheduler.handle(
        snapshot=snapshot,
        event={"type": "HEALTH_TICK"},
    )
    assert result.skipped_projects == ["A"]
    assert result.decision["project_id"] == "B"
    assert result.dispatched is True
    assert dispatched == ["B"]


def test_event_bus_deduplicates_freshness_key():
    async def scenario():
        bus = EventBus()
        event = Event(
            type="GITHUB_CHANGED",
            source="github",
            subject="p",
            observed_at="2026-09-21T00:00:00+00:00",
            payload={"head": "abc"},
            freshness_key="same",
        )
        assert await bus.publish(event) is True
        assert await bus.publish(event) is False
        received = await bus.next()
        assert received.freshness_key == "same"
        assert bus.empty()

    asyncio.run(scenario())


class FakeGitHub:
    def __init__(self):
        self.sha = "a"

    def branch(self, repo, branch):
        return {"commit": {"sha": self.sha}}

    def workflow_runs(self, repo, sha):
        return {
            "workflow_runs": [
                {"id": 1, "status": "completed", "conclusion": "success"}
            ]
        }


def test_github_source_emits_only_on_change():
    client = FakeGitHub()
    source = GitHubPollSource(
        client=client,
        projects=[{"id": "p", "repo": "owner/p", "default_branch": "main"}],
    )
    assert len(source.poll()) == 1
    assert source.poll() == []
    client.sha = "b"
    events = source.poll()
    assert len(events) == 1
    assert events[0].payload["head"] == "b"


def test_process_source_emits_on_state_change():
    state = {"value": "running"}
    source = ProcessPollSource({"job": lambda: dict(state)})
    assert len(source.poll()) == 1
    assert source.poll() == []
    state["value"] = "done"
    assert len(source.poll()) == 1


def test_service_processes_health_tick_and_switches_project():
    dispatched = []
    scheduler = PortfolioScheduler(
        brain=SwitchingBrain(),
        policy=_policy(),
        action_sink=lambda decision, gate: dispatched.append(decision["project_id"]),
    )
    snapshot = {
        "snapshot_id": "s1",
        "projects": [_project("A", "WAITING_EXTERNAL"), _project("B")],
    }

    async def scenario():
        service = PortfolioService(
            bus=EventBus(),
            sources=[HealthTickSource()],
            observer=lambda: snapshot,
            scheduler=scheduler,
        )
        results = await service.run_cycle()
        assert len(results) == 1
        assert results[0]["skipped_projects"] == ["A"]

    asyncio.run(scenario())
    assert dispatched == ["B"]

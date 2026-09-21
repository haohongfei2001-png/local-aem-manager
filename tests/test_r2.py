import io
import json
from pathlib import Path

import pytest

from local_aem.decision import (
    DecisionValidationError,
    load_decision_schema,
)
from local_aem.manager import ManagerBrain
from local_aem.policy import PolicyBundle, REQUIRED_POLICY_FILES
from local_aem.providers.openai_compat import OpenAICompatibleProvider
from local_aem.replay import replay_summary, run_replay_file


class FakeProvider:
    def __init__(self, content):
        self.content = content
        self.system_prompt = None
        self.user_prompt = None

    def complete(self, *, system_prompt, user_prompt):
        self.system_prompt = system_prompt
        self.user_prompt = user_prompt
        return self.content


def policy_bundle():
    files = {path: f"# {path}\npolicy\n" for path in REQUIRED_POLICY_FILES}
    return PolicyBundle(
        repo="owner/aem",
        version="0.2.0",
        digest="digest",
        files=files,
        source="test",
    )


def snapshot():
    return {
        "snapshot_id": "s1",
        "projects": [
            {
                "project_id": "p",
                "repo": "owner/repo",
                "canonical_status": "IN_PROGRESS",
                "writer_lease": {"state": "RELEASED"},
            }
        ],
    }


def valid_decision():
    return {
        "decision_id": "d1",
        "project_id": "p",
        "evidence_snapshot_id": "s1",
        "assessment": "VERIFYING",
        "priority": 50,
        "owner_required": False,
        "owner_reason": None,
        "action_type": "VERIFY",
        "executor": "NONE",
        "target": {"repo": "owner/repo", "branch": "main", "scope": "R1"},
        "rationale": "verify remote truth",
        "instructions": "read exact remote state",
        "requested_operations": ["READ_REPO"],
        "verification": ["remote truth"],
        "expected_state": None,
        "idempotency_key": "d1-key",
    }


def test_packaged_schema_matches_repository_schema():
    packaged = load_decision_schema()
    root = json.loads(
        (Path(__file__).resolve().parents[1]
         / "schemas"
         / "manager-decision.schema.json").read_text(encoding="utf-8")
    )
    assert packaged == root


def test_manager_brain_returns_schema_valid_decision():
    provider = FakeProvider(json.dumps(valid_decision()))
    decision = ManagerBrain(provider).decide(
        policy=policy_bundle(),
        portfolio_snapshot=snapshot(),
    )
    assert decision["decision_id"] == "d1"
    assert "ManagerDecision JSON Schema" in provider.system_prompt
    assert '"snapshot_id": "s1"' in provider.user_prompt


def test_manager_brain_rejects_stale_snapshot_reference():
    payload = valid_decision()
    payload["evidence_snapshot_id"] = "old"
    provider = FakeProvider(json.dumps(payload))
    with pytest.raises(DecisionValidationError):
        ManagerBrain(provider).decide(
            policy=policy_bundle(),
            portfolio_snapshot=snapshot(),
        )


class Response(io.BytesIO):
    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.close()


def test_openai_compatible_transport_uses_post_without_logging_key(monkeypatch):
    seen = {}

    def opener(request, timeout):
        seen["method"] = request.get_method()
        seen["url"] = request.full_url
        seen["authorization"] = request.headers.get("Authorization")
        body = json.dumps(
            {
                "choices": [
                    {"message": {"content": json.dumps(valid_decision())}}
                ]
            }
        ).encode("utf-8")
        return Response(body)

    monkeypatch.setenv("FAKE_MANAGER_KEY", "not-a-real-secret")
    provider = OpenAICompatibleProvider(
        base_url="https://provider.invalid/v1",
        model="manager-model",
        api_key_env="FAKE_MANAGER_KEY",
        opener=opener,
    )
    content = provider.complete(system_prompt="system", user_prompt="user")
    assert json.loads(content)["decision_id"] == "d1"
    assert seen["method"] == "POST"
    assert seen["url"].endswith("/chat/completions")
    assert seen["authorization"] == "Bearer not-a-real-secret"


def test_aem_v02_replay_suite_passes():
    path = (
        Path(__file__).resolve().parent
        / "fixtures"
        / "aem-v0.2-replays.yaml"
    )
    summary = replay_summary(run_replay_file(path))
    assert summary["total"] >= 22
    assert summary["failed"] == 0, summary

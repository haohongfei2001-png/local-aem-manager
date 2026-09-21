import base64
import io
import json
from pathlib import Path

import pytest

from local_aem.audit import AuditLog
from local_aem.config import ConfigError, assert_r1_shadow_safe, load_config
from local_aem.db import StateDB
from local_aem.github_read import GitHubReadClient
from local_aem.policy import REQUIRED_POLICY_FILES, PolicyError, sync_policy
from local_aem.portfolio import observe_project


class Response(io.BytesIO):
    def __enter__(self):
        return self
    def __exit__(self, *args):
        self.close()


def test_shadow_config_accepts_read_only_and_rejects_writes(tmp_path: Path):
    good = tmp_path / "good.yaml"
    good.write_text(
        """
runtime:
  mode: shadow
safety:
  allow_managed_repo_writes: false
executors:
  github:
    enabled: false
portfolio:
  projects: []
""",
        encoding="utf-8",
    )
    assert_r1_shadow_safe(load_config(good))

    bad = tmp_path / "bad.yaml"
    bad.write_text(
        """
runtime:
  mode: active
safety:
  allow_managed_repo_writes: true
""",
        encoding="utf-8",
    )
    with pytest.raises(ConfigError):
        assert_r1_shadow_safe(load_config(bad))


def test_audit_redacts_sensitive_fields(tmp_path: Path):
    path = tmp_path / "audit.jsonl"
    AuditLog(path).append(
        {
            "event": "test",
            "api_key": "super-secret",
            "nested": {"Authorization": "Bearer secret", "safe": "ok"},
        }
    )
    raw = path.read_text(encoding="utf-8")
    payload = json.loads(raw)
    assert payload["api_key"] == "[REDACTED]"
    assert payload["nested"]["Authorization"] == "[REDACTED]"
    assert payload["nested"]["safe"] == "ok"
    assert "super-secret" not in raw


def test_snapshot_round_trip(tmp_path: Path):
    project = {
        "project_id": "p1",
        "repo": "owner/repo",
        "portfolio_state": "IDLE",
    }
    with StateDB(tmp_path / "state.db") as db:
        db.save_snapshot(
            snapshot_id="s1",
            observed_at="2026-09-21T00:00:00+00:00",
            policy_version="0.2.0",
            policy_digest="abc",
            projects=[project],
        )
        latest = db.latest_snapshot()
    assert latest["snapshot_id"] == "s1"
    assert latest["projects"][0]["project_id"] == "p1"


def test_github_client_uses_get_only_and_decodes_file():
    seen = []

    def opener(request, timeout):
        seen.append((request.get_method(), request.full_url))
        if "/contents/" in request.full_url:
            payload = {
                "type": "file",
                "content": base64.b64encode(b"hello").decode("ascii"),
            }
        else:
            payload = {"ok": True}
        return Response(json.dumps(payload).encode("utf-8"))

    client = GitHubReadClient(
        api_base="https://example.invalid", opener=opener
    )
    assert client.repo("o/r") == {"ok": True}
    assert client.file_text("o/r", "README.md") == "hello"
    assert all(method == "GET" for method, _ in seen)

    forbidden = {"create", "update", "delete", "post", "put", "patch", "merge"}
    assert not forbidden.intersection(
        {name.lower() for name in dir(GitHubReadClient)}
    )


class FakePolicyClient:
    def __init__(self, fail=False, version="0.2.0"):
        self.fail = fail
        self.version = version

    def file_text(self, repo, path, ref="main"):
        if self.fail:
            raise RuntimeError("offline")
        if path == "VERSION":
            return self.version + "\n"
        if path in REQUIRED_POLICY_FILES:
            return f"# {path}\ncontent\n"
        raise KeyError(path)


def test_policy_sync_fallback_and_minimum_version(tmp_path: Path):
    first = sync_policy(
        FakePolicyClient(),
        repo="owner/aem",
        required_version=">=0.2.0",
        data_dir=tmp_path,
    )
    assert first.source == "remote-validated"

    fallback = sync_policy(
        FakePolicyClient(fail=True),
        repo="owner/aem",
        required_version=">=0.2.0",
        data_dir=tmp_path,
    )
    assert fallback.digest == first.digest
    assert fallback.source == "last-known-good"

    with pytest.raises(PolicyError):
        sync_policy(
            FakePolicyClient(version="0.1.0"),
            repo="owner/aem",
            required_version=">=0.2.0",
            data_dir=tmp_path / "old",
        )


class FakeProjectClient:
    def repo(self, repo):
        return {"private": False}
    def branch(self, repo, branch):
        return {"commit": {"sha": "abc123"}, "protected": False}
    def combined_status(self, repo, sha):
        return {"state": "success", "statuses": []}
    def workflow_runs(self, repo, sha):
        return {"workflow_runs": []}
    def file_text(self, repo, path, ref="main"):
        return """
package_status: IN_PROGRESS
current_round:
  id: SCA04
  status: BLOCKED
"""


def test_portfolio_preserves_canonical_blocked():
    state = observe_project(
        FakeProjectClient(),
        {
            "id": "sem",
            "repo": "owner/sem",
            "default_branch": "main",
            "status_path": "status.yaml",
        },
    )
    assert state["current_scope"] == "SCA04"
    assert state["canonical_status"] == "BLOCKED"
    assert state["portfolio_state"] == "BLOCKED"
    assert state["blocker"]["owner_required"] is False

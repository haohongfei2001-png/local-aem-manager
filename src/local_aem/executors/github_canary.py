from __future__ import annotations

import base64
import json
import os
import uuid
from dataclasses import dataclass
from typing import Any
from urllib.parse import quote, urlencode
from urllib.request import Request, urlopen

from .base import ExecutorResult, ExecutorState, utc_now
from .shell import ExecutorSafetyError


class GitHubCanaryError(RuntimeError):
    pass


@dataclass(frozen=True)
class GitHubCanaryPolicy:
    repo: str
    base_branch: str
    branch_prefix: str
    path_prefix: str


class GitHubCanaryExecutor:
    name = "GITHUB"

    def __init__(
        self,
        *,
        policy: GitHubCanaryPolicy,
        token_env: str = "GITHUB_TOKEN",
        api_base: str = "https://api.github.com",
        opener=urlopen,
        timeout: int = 30,
    ):
        self.policy = policy
        self.token_env = token_env
        self.api_base = api_base.rstrip("/")
        self.opener = opener
        self.timeout = timeout
        self._jobs: dict[str, ExecutorResult] = {}

    def capability_probe(self) -> dict[str, Any]:
        return {
            "executor": self.name,
            "live_canary_enabled": True,
            "repo": self.policy.repo,
            "base_branch": self.policy.base_branch,
            "branch_prefix": self.policy.branch_prefix,
            "path_prefix": self.policy.path_prefix,
            "merge_enabled": False,
            "delete_enabled": False,
            "force_enabled": False,
        }

    def _headers(self) -> dict[str, str]:
        token = os.environ.get(self.token_env)
        if not token:
            raise GitHubCanaryError(
                f"missing canary credential environment variable: {self.token_env}"
            )
        return {
            "Authorization": f"Bearer {token}",
            "Accept": "application/vnd.github+json",
            "Content-Type": "application/json",
            "X-GitHub-Api-Version": "2022-11-28",
            "User-Agent": "local-aem-manager-r4-canary",
        }

    def _request(
        self,
        method: str,
        path: str,
        payload: dict[str, Any] | None = None,
        query: dict[str, Any] | None = None,
    ) -> Any:
        url = f"{self.api_base}{path}"
        if query:
            url += "?" + urlencode(query)
        data = None if payload is None else json.dumps(payload).encode("utf-8")
        request = Request(
            url,
            data=data,
            headers=self._headers(),
            method=method,
        )
        try:
            with self.opener(request, timeout=self.timeout) as response:
                body = response.read().decode("utf-8")
        except Exception as exc:
            raise GitHubCanaryError(
                f"GitHub canary {method} failed for {path}: {exc}"
            ) from exc
        return json.loads(body) if body else {}

    def prepare(self, plan: dict[str, Any]) -> None:
        if plan["operation"] != "GITHUB_MUTATION":
            raise ExecutorSafetyError(
                "GitHubCanaryExecutor only accepts GITHUB_MUTATION"
            )
        if plan["dry_run"]:
            raise ExecutorSafetyError("R4 canary requires dry_run=false")
        if plan["target"]["repo"] != self.policy.repo:
            raise ExecutorSafetyError("canary repo does not match allowlist")

        params = plan["params"]
        if params.get("kind") != "CANARY_PR_CYCLE":
            raise ExecutorSafetyError("only CANARY_PR_CYCLE is allowed")
        branch = str(params.get("branch") or "")
        base_branch = str(params.get("base_branch") or "")
        path = str(params.get("path") or "")
        if not branch.startswith(self.policy.branch_prefix):
            raise ExecutorSafetyError("canary branch is outside allowed prefix")
        if base_branch != self.policy.base_branch:
            raise ExecutorSafetyError("canary base branch is not allowlisted")
        if not path.startswith(self.policy.path_prefix):
            raise ExecutorSafetyError("canary path is outside allowed prefix")
        if path.startswith("/") or ".." in path.split("/"):
            raise ExecutorSafetyError("canary path is unsafe")

    def execute(self, plan: dict[str, Any]) -> ExecutorResult:
        self.prepare(plan)
        job_id = f"github-canary-{uuid.uuid4().hex[:16]}"
        started = utc_now()
        params = plan["params"]
        branch = params["branch"]
        base_branch = params["base_branch"]
        path = params["path"]
        content = str(params["content"])
        title = str(params.get("title") or "Local AEM R4 canary proof")

        owner, repo_name = self.policy.repo.split("/", 1)
        root = f"/repos/{quote(owner, safe='')}/{quote(repo_name, safe='')}"
        pr_number = None
        try:
            base = self._request(
                "GET",
                f"{root}/branches/{quote(base_branch, safe='')}",
            )
            base_sha = base["commit"]["sha"]

            self._request(
                "POST",
                f"{root}/git/refs",
                {
                    "ref": f"refs/heads/{branch}",
                    "sha": base_sha,
                },
            )

            safe_path = "/".join(
                quote(part, safe="") for part in path.split("/")
            )
            created = self._request(
                "PUT",
                f"{root}/contents/{safe_path}",
                {
                    "message": "test(r4): write canary proof",
                    "content": base64.b64encode(
                        content.encode("utf-8")
                    ).decode("ascii"),
                    "branch": branch,
                },
            )
            commit_sha = created["commit"]["sha"]

            remote = self._request(
                "GET",
                f"{root}/contents/{safe_path}",
                query={"ref": branch},
            )
            remote_text = base64.b64decode(remote["content"]).decode("utf-8")
            if remote_text != content:
                raise GitHubCanaryError("remote canary file content mismatch")

            pr = self._request(
                "POST",
                f"{root}/pulls",
                {
                    "title": title,
                    "head": branch,
                    "base": base_branch,
                    "body": (
                        "R4 single-repository canary. "
                        "This PR is verification-only and must not be merged."
                    ),
                },
            )
            pr_number = int(pr["number"])
            if pr["head"]["ref"] != branch or pr["base"]["ref"] != base_branch:
                raise GitHubCanaryError("created PR does not match canary scope")

            closed = self._request(
                "PATCH",
                f"{root}/pulls/{pr_number}",
                {"state": "closed"},
            )
            if closed.get("state") != "closed":
                raise GitHubCanaryError("canary PR did not close cleanly")

            result = ExecutorResult(
                job_id=job_id,
                executor=self.name,
                state=ExecutorState.SUCCEEDED,
                detail="bounded GitHub canary branch/file/PR cycle succeeded",
                outputs={
                    "repo": self.policy.repo,
                    "base_branch": base_branch,
                    "branch": branch,
                    "path": path,
                    "commit_sha": commit_sha,
                    "pr_number": pr_number,
                    "pr_state": "closed",
                    "merged": False,
                },
                started_at=started,
                ended_at=utc_now(),
            )
        except Exception as exc:
            result = ExecutorResult(
                job_id=job_id,
                executor=self.name,
                state=ExecutorState.FAILED,
                detail=str(exc),
                outputs={
                    "repo": self.policy.repo,
                    "branch": branch,
                    "path": path,
                    "pr_number": pr_number,
                    "merged": False,
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

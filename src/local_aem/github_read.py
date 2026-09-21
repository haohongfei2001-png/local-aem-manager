from __future__ import annotations

import base64
import json
import os
from typing import Any
from urllib.parse import quote, urlencode
from urllib.request import Request, urlopen


class GitHubReadError(RuntimeError):
    pass


class GitHubReadClient:
    """GET-only GitHub REST client.

    R1 intentionally exposes no mutation method.
    """

    def __init__(
        self,
        *,
        token_env: str = "GITHUB_TOKEN",
        api_base: str = "https://api.github.com",
        opener=urlopen,
        timeout: int = 30,
    ):
        self.api_base = api_base.rstrip("/")
        self.timeout = timeout
        self.opener = opener
        self.token_env = token_env

    def _headers(self) -> dict[str, str]:
        headers = {
            "Accept": "application/vnd.github+json",
            "User-Agent": "local-aem-manager-r1-readonly",
            "X-GitHub-Api-Version": "2022-11-28",
        }
        token = os.environ.get(self.token_env)
        if token:
            headers["Authorization"] = f"Bearer {token}"
        return headers

    def _get(self, path: str, query: dict[str, Any] | None = None) -> Any:
        url = f"{self.api_base}{path}"
        if query:
            url += "?" + urlencode(query)
        request = Request(url, headers=self._headers(), method="GET")
        try:
            with self.opener(request, timeout=self.timeout) as response:
                body = response.read().decode("utf-8")
        except Exception as exc:
            raise GitHubReadError(f"GitHub GET failed for {path}: {exc}") from exc
        try:
            return json.loads(body)
        except json.JSONDecodeError as exc:
            raise GitHubReadError(f"GitHub returned non-JSON for {path}") from exc

    @staticmethod
    def _repo_path(repo: str) -> str:
        if "/" not in repo:
            raise GitHubReadError(f"invalid repository name: {repo}")
        owner, name = repo.split("/", 1)
        return f"/repos/{quote(owner, safe='')}/{quote(name, safe='')}"

    def repo(self, repo: str) -> dict[str, Any]:
        return self._get(self._repo_path(repo))

    def branch(self, repo: str, branch: str) -> dict[str, Any]:
        return self._get(
            f"{self._repo_path(repo)}/branches/{quote(branch, safe='')}"
        )

    def combined_status(self, repo: str, sha: str) -> dict[str, Any]:
        return self._get(
            f"{self._repo_path(repo)}/commits/{quote(sha, safe='')}/status"
        )

    def workflow_runs(
        self, repo: str, sha: str, per_page: int = 20
    ) -> dict[str, Any]:
        return self._get(
            f"{self._repo_path(repo)}/actions/runs",
            {"head_sha": sha, "per_page": max(1, min(per_page, 100))},
        )

    def file_text(self, repo: str, path: str, ref: str = "main") -> str:
        safe_path = "/".join(quote(part, safe="") for part in path.split("/"))
        payload = self._get(
            f"{self._repo_path(repo)}/contents/{safe_path}", {"ref": ref}
        )
        if payload.get("type") != "file" or "content" not in payload:
            raise GitHubReadError(f"not a file: {repo}:{path}@{ref}")
        try:
            return base64.b64decode(payload["content"]).decode("utf-8")
        except Exception as exc:
            raise GitHubReadError(
                f"cannot decode UTF-8 file: {repo}:{path}@{ref}"
            ) from exc

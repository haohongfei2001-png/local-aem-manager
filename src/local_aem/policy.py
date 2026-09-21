from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from pathlib import Path

from .github_read import GitHubReadClient

REQUIRED_POLICY_FILES = (
    "MANAGER_CHARTER.md",
    "OPERATING_PLAYBOOK.md",
    "DECISION_POLICY.md",
    "ESCALATION_POLICY.md",
    "EXECUTION_AND_TAKEOVER.md",
    "evals/MANAGER_DECISION_EVALS.md",
)


class PolicyError(RuntimeError):
    pass


@dataclass(frozen=True)
class PolicyBundle:
    repo: str
    version: str
    digest: str
    files: dict[str, str]
    source: str


def _version_tuple(value: str) -> tuple[int, ...]:
    value = value.strip()
    if value.startswith(">="):
        value = value[2:]
    if value.startswith("v"):
        value = value[1:]
    try:
        return tuple(int(part) for part in value.split("."))
    except ValueError as exc:
        raise PolicyError(f"unsupported semantic version: {value}") from exc


def _digest(files: dict[str, str]) -> str:
    hasher = hashlib.sha256()
    for path in sorted(files):
        hasher.update(path.encode("utf-8"))
        hasher.update(b"\0")
        hasher.update(files[path].encode("utf-8"))
        hasher.update(b"\0")
    return hasher.hexdigest()


def _write_bundle(data_dir: Path, bundle: PolicyBundle) -> None:
    root = data_dir / "policy"
    bundles = root / "bundles"
    bundles.mkdir(parents=True, exist_ok=True)
    payload = {
        "repo": bundle.repo,
        "version": bundle.version,
        "digest": bundle.digest,
        "files": bundle.files,
    }
    (bundles / f"{bundle.digest}.json").write_text(
        json.dumps(payload, ensure_ascii=False, sort_keys=True, indent=2),
        encoding="utf-8",
    )
    (root / "active.json").write_text(
        json.dumps(
            {
                "repo": bundle.repo,
                "version": bundle.version,
                "digest": bundle.digest,
            },
            sort_keys=True,
            indent=2,
        ),
        encoding="utf-8",
    )


def load_last_known_good(data_dir: Path) -> PolicyBundle:
    root = data_dir / "policy"
    active = root / "active.json"
    if not active.exists():
        raise PolicyError("no last-known-good policy bundle exists")
    meta = json.loads(active.read_text(encoding="utf-8"))
    payload = json.loads(
        (root / "bundles" / f"{meta['digest']}.json").read_text(encoding="utf-8")
    )
    return PolicyBundle(
        repo=payload["repo"],
        version=payload["version"],
        digest=payload["digest"],
        files=payload["files"],
        source="last-known-good",
    )


def sync_policy(
    client: GitHubReadClient,
    *,
    repo: str,
    required_version: str,
    data_dir: Path,
) -> PolicyBundle:
    try:
        version = client.file_text(repo, "VERSION", "main").strip()
        if _version_tuple(version) < _version_tuple(required_version):
            raise PolicyError(
                f"policy {version} is older than required {required_version}"
            )
        files = {
            path: client.file_text(repo, path, "main")
            for path in REQUIRED_POLICY_FILES
        }
        bundle = PolicyBundle(
            repo=repo,
            version=version,
            digest=_digest(files),
            files=files,
            source="remote-validated",
        )
        _write_bundle(data_dir, bundle)
        return bundle
    except Exception as exc:
        try:
            return load_last_known_good(data_dir)
        except Exception:
            if isinstance(exc, PolicyError):
                raise
            raise PolicyError(
                f"policy sync failed and no fallback exists: {exc}"
            ) from exc

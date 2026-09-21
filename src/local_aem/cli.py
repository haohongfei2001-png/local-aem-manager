from __future__ import annotations

import argparse
import hashlib
import json
import os
from datetime import datetime, timezone
from pathlib import Path

from .audit import AuditLog
from .config import assert_r1_shadow_safe, load_config
from .db import StateDB
from .github_read import GitHubReadClient
from .policy import sync_policy
from .portfolio import observe_portfolio
from .replay import replay_summary, run_replay_file


def _data_dir(config, override: str | None) -> Path:
    return Path(override).expanduser() if override else config.data_dir


def _client(config) -> GitHubReadClient:
    github = config.github
    return GitHubReadClient(
        token_env=str(github.get("token_env", "GITHUB_TOKEN")),
        api_base=str(github.get("api_base", "https://api.github.com")),
        timeout=int(github.get("timeout_seconds", 30)),
    )


def _snapshot_id(observed_at: str, projects: list[dict]) -> str:
    material = observed_at + "\n" + "\n".join(
        f"{p['project_id']}:{p.get('remote_head')}" for p in projects
    )
    return hashlib.sha256(material.encode("utf-8")).hexdigest()[:24]


def _print_summary(snapshot: dict) -> None:
    print(
        f"snapshot={snapshot['snapshot_id']} "
        f"observed_at={snapshot['observed_at']} "
        f"policy={snapshot.get('policy_version') or '-'}"
    )
    for project in snapshot.get("projects", []):
        print(
            f"{project['project_id']}: {project['portfolio_state']} "
            f"scope={project.get('current_scope') or '-'} "
            f"canonical={project.get('canonical_status') or '-'} "
            f"head={project.get('remote_head') or '-'}"
        )


def command_status(args: argparse.Namespace) -> int:
    config = load_config(args.config)
    assert_r1_shadow_safe(config)
    data_dir = _data_dir(config, args.data_dir)
    with StateDB(data_dir / "state.db") as db:
        snapshot = db.latest_snapshot()
    if snapshot is None:
        print("No portfolio snapshot has been recorded.")
        return 0
    if args.json:
        print(json.dumps(snapshot, ensure_ascii=False, indent=2, sort_keys=True))
    else:
        _print_summary(snapshot)
    return 0


def _observe(args: argparse.Namespace, *, sync: bool) -> dict:
    config = load_config(args.config)
    assert_r1_shadow_safe(config)
    data_dir = _data_dir(config, args.data_dir)
    data_dir.mkdir(parents=True, exist_ok=True)
    client = _client(config)

    policy_version = None
    policy_digest = None
    if sync:
        policy_cfg = config.policy
        bundle = sync_policy(
            client,
            repo=str(
                policy_cfg.get(
                    "repo", "haohongfei2001-png/ai-engineering-manager"
                )
            ),
            required_version=str(
                policy_cfg.get("required_version", ">=0.2.0")
            ),
            data_dir=data_dir,
        )
        policy_version = bundle.version
        policy_digest = bundle.digest

    projects = observe_portfolio(client, config.projects)
    observed_at = datetime.now(timezone.utc).isoformat()
    snapshot_id = _snapshot_id(observed_at, projects)
    snapshot = {
        "snapshot_id": snapshot_id,
        "observed_at": observed_at,
        "policy_version": policy_version,
        "policy_digest": policy_digest,
        "projects": projects,
    }

    with StateDB(data_dir / "state.db") as db:
        db.save_snapshot(
            snapshot_id=snapshot_id,
            observed_at=observed_at,
            policy_version=policy_version,
            policy_digest=policy_digest,
            projects=projects,
        )
    AuditLog(data_dir / "audit.jsonl").append(
        {
            "event": "portfolio_observed",
            "snapshot_id": snapshot_id,
            "observed_at": observed_at,
            "policy_version": policy_version,
            "policy_digest": policy_digest,
            "project_count": len(projects),
        }
    )
    return snapshot


def command_observe(args: argparse.Namespace) -> int:
    snapshot = _observe(args, sync=False)
    if args.json:
        print(json.dumps(snapshot, ensure_ascii=False, indent=2, sort_keys=True))
    else:
        _print_summary(snapshot)
    return 0


def command_shadow_once(args: argparse.Namespace) -> int:
    snapshot = _observe(args, sync=True)
    if args.json:
        print(json.dumps(snapshot, ensure_ascii=False, indent=2, sort_keys=True))
    else:
        _print_summary(snapshot)
    return 0


def command_replay(args: argparse.Namespace) -> int:
    summary = replay_summary(run_replay_file(args.fixture))
    print(json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True))
    return 0 if summary["failed"] == 0 else 1


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="local-aem")
    parser.add_argument(
        "--config",
        default=os.environ.get(
            "LOCAL_AEM_CONFIG",
            "~/.config/local-aem-manager/config.yaml",
        ),
    )
    parser.add_argument("--data-dir", default=None)
    sub = parser.add_subparsers(dest="command", required=True)

    status = sub.add_parser("status")
    status.add_argument("--json", action="store_true")
    status.set_defaults(func=command_status)

    observe = sub.add_parser("observe")
    observe.add_argument("--json", action="store_true")
    observe.set_defaults(func=command_observe)

    shadow = sub.add_parser("shadow-once")
    shadow.add_argument("--json", action="store_true")
    shadow.set_defaults(func=command_shadow_once)

    replay = sub.add_parser("replay")
    replay.add_argument("fixture")
    replay.set_defaults(func=command_replay)
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return int(args.func(args))


if __name__ == "__main__":
    raise SystemExit(main())

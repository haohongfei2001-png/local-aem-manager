from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from typing import Any

SCHEMA = """
PRAGMA journal_mode=WAL;
CREATE TABLE IF NOT EXISTS portfolio_snapshots (
    snapshot_id TEXT PRIMARY KEY,
    observed_at TEXT NOT NULL,
    policy_version TEXT,
    policy_digest TEXT,
    payload_json TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS project_states (
    snapshot_id TEXT NOT NULL,
    project_id TEXT NOT NULL,
    repo TEXT NOT NULL,
    payload_json TEXT NOT NULL,
    PRIMARY KEY (snapshot_id, project_id)
);
CREATE INDEX IF NOT EXISTS idx_snapshots_observed
    ON portfolio_snapshots(observed_at DESC);
"""


class StateDB:
    def __init__(self, path: str | Path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.conn = sqlite3.connect(self.path)
        self.conn.row_factory = sqlite3.Row
        self.conn.executescript(SCHEMA)

    def close(self) -> None:
        self.conn.close()

    def __enter__(self) -> "StateDB":
        return self

    def __exit__(self, *_: object) -> None:
        self.close()

    def save_snapshot(
        self,
        *,
        snapshot_id: str,
        observed_at: str,
        policy_version: str | None,
        policy_digest: str | None,
        projects: list[dict[str, Any]],
    ) -> None:
        payload = {
            "snapshot_id": snapshot_id,
            "observed_at": observed_at,
            "policy_version": policy_version,
            "policy_digest": policy_digest,
            "projects": projects,
        }
        with self.conn:
            self.conn.execute(
                """
                INSERT OR REPLACE INTO portfolio_snapshots
                (snapshot_id, observed_at, policy_version, policy_digest, payload_json)
                VALUES (?, ?, ?, ?, ?)
                """,
                (
                    snapshot_id,
                    observed_at,
                    policy_version,
                    policy_digest,
                    json.dumps(payload, ensure_ascii=False, sort_keys=True),
                ),
            )
            self.conn.execute(
                "DELETE FROM project_states WHERE snapshot_id = ?", (snapshot_id,)
            )
            for project in projects:
                self.conn.execute(
                    """
                    INSERT INTO project_states
                    (snapshot_id, project_id, repo, payload_json)
                    VALUES (?, ?, ?, ?)
                    """,
                    (
                        snapshot_id,
                        project["project_id"],
                        project["repo"],
                        json.dumps(project, ensure_ascii=False, sort_keys=True),
                    ),
                )

    def latest_snapshot(self) -> dict[str, Any] | None:
        row = self.conn.execute(
            """
            SELECT payload_json
            FROM portfolio_snapshots
            ORDER BY observed_at DESC
            LIMIT 1
            """
        ).fetchone()
        if row is None:
            return None
        return json.loads(row["payload_json"])

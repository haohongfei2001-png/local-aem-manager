from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from typing import Any


SCHEMA = """
CREATE TABLE IF NOT EXISTS executor_jobs (
    idempotency_key TEXT PRIMARY KEY,
    action_id TEXT NOT NULL,
    job_id TEXT NOT NULL,
    executor TEXT NOT NULL,
    state TEXT NOT NULL,
    result_json TEXT NOT NULL,
    created_at TEXT NOT NULL
);
"""


class ExecutionLedger:
    def __init__(self, path: str | Path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.conn = sqlite3.connect(self.path)
        self.conn.row_factory = sqlite3.Row
        self.conn.executescript(SCHEMA)

    def close(self) -> None:
        self.conn.close()

    def __enter__(self) -> "ExecutionLedger":
        return self

    def __exit__(self, *_: object) -> None:
        self.close()

    def get(self, idempotency_key: str) -> dict[str, Any] | None:
        row = self.conn.execute(
            """
            SELECT result_json
            FROM executor_jobs
            WHERE idempotency_key = ?
            """,
            (idempotency_key,),
        ).fetchone()
        if row is None:
            return None
        return json.loads(row["result_json"])

    def save(
        self,
        *,
        idempotency_key: str,
        action_id: str,
        result: dict[str, Any],
        created_at: str,
    ) -> None:
        with self.conn:
            self.conn.execute(
                """
                INSERT INTO executor_jobs
                (idempotency_key, action_id, job_id, executor, state, result_json, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    idempotency_key,
                    action_id,
                    result["job_id"],
                    result["executor"],
                    result["state"],
                    json.dumps(result, ensure_ascii=False, sort_keys=True),
                    created_at,
                ),
            )

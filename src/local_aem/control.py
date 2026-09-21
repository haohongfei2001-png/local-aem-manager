from __future__ import annotations

import sqlite3
from pathlib import Path


class RuntimePaused(RuntimeError):
    pass


SCHEMA = """
CREATE TABLE IF NOT EXISTS runtime_control (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL
);
"""


class RuntimeControl:
    def __init__(self, path: str | Path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.conn = sqlite3.connect(self.path)
        self.conn.executescript(SCHEMA)
        with self.conn:
            self.conn.execute(
                """
                INSERT OR IGNORE INTO runtime_control(key, value)
                VALUES ('mode', 'PAUSED')
                """
            )

    def close(self) -> None:
        self.conn.close()

    def __enter__(self) -> "RuntimeControl":
        return self

    def __exit__(self, *_: object) -> None:
        self.close()

    def mode(self) -> str:
        row = self.conn.execute(
            "SELECT value FROM runtime_control WHERE key='mode'"
        ).fetchone()
        return str(row[0])

    def _set(self, value: str) -> None:
        with self.conn:
            self.conn.execute(
                """
                INSERT INTO runtime_control(key, value)
                VALUES ('mode', ?)
                ON CONFLICT(key) DO UPDATE SET value=excluded.value
                """,
                (value,),
            )

    def resume(self) -> None:
        self._set("RUNNING")

    def pause(self) -> None:
        self._set("PAUSED")

    def hard_stop(self) -> None:
        self._set("STOPPED")

    def assert_new_actions_allowed(self) -> None:
        current = self.mode()
        if current != "RUNNING":
            raise RuntimePaused(f"runtime mode {current} forbids new actions")

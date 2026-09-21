from __future__ import annotations

import sqlite3
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


class LeaseConflict(RuntimeError):
    pass


@dataclass(frozen=True)
class WriterLease:
    repo: str
    branch: str
    scope: str
    holder: str | None
    state: str
    acquired_at: str | None
    last_activity_at: str | None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


SCHEMA = """
CREATE TABLE IF NOT EXISTS writer_leases (
    repo TEXT NOT NULL,
    branch TEXT NOT NULL,
    scope TEXT NOT NULL,
    holder TEXT,
    state TEXT NOT NULL,
    acquired_at TEXT,
    last_activity_at TEXT,
    PRIMARY KEY (repo, branch, scope)
);
"""


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


class WriterLeaseStore:
    def __init__(self, path: str | Path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.conn = sqlite3.connect(self.path)
        self.conn.row_factory = sqlite3.Row
        self.conn.executescript(SCHEMA)

    def close(self) -> None:
        self.conn.close()

    def __enter__(self) -> "WriterLeaseStore":
        return self

    def __exit__(self, *_: object) -> None:
        self.close()

    def get(self, repo: str, branch: str, scope: str) -> WriterLease | None:
        row = self.conn.execute(
            """
            SELECT repo, branch, scope, holder, state, acquired_at, last_activity_at
            FROM writer_leases
            WHERE repo=? AND branch=? AND scope=?
            """,
            (repo, branch, scope),
        ).fetchone()
        if row is None:
            return None
        return WriterLease(**dict(row))

    def acquire(
        self,
        *,
        repo: str,
        branch: str,
        scope: str,
        holder: str,
    ) -> WriterLease:
        now = _now()
        with self.conn:
            row = self.conn.execute(
                """
                SELECT holder, state
                FROM writer_leases
                WHERE repo=? AND branch=? AND scope=?
                """,
                (repo, branch, scope),
            ).fetchone()
            if row is not None and row["state"] in {"ACTIVE", "SUSPECT"}:
                if row["holder"] != holder:
                    raise LeaseConflict(
                        f"writer lease held by {row['holder']} in state {row['state']}"
                    )
            self.conn.execute(
                """
                INSERT INTO writer_leases
                (repo, branch, scope, holder, state, acquired_at, last_activity_at)
                VALUES (?, ?, ?, ?, 'ACTIVE', ?, ?)
                ON CONFLICT(repo, branch, scope) DO UPDATE SET
                  holder=excluded.holder,
                  state='ACTIVE',
                  acquired_at=excluded.acquired_at,
                  last_activity_at=excluded.last_activity_at
                """,
                (repo, branch, scope, holder, now, now),
            )
        lease = self.get(repo, branch, scope)
        assert lease is not None
        return lease

    def heartbeat(
        self, *, repo: str, branch: str, scope: str, holder: str
    ) -> WriterLease:
        now = _now()
        with self.conn:
            row = self.conn.execute(
                """
                SELECT holder, state FROM writer_leases
                WHERE repo=? AND branch=? AND scope=?
                """,
                (repo, branch, scope),
            ).fetchone()
            if row is None or row["holder"] != holder or row["state"] != "ACTIVE":
                raise LeaseConflict("cannot heartbeat a lease not actively held")
            self.conn.execute(
                """
                UPDATE writer_leases SET last_activity_at=?
                WHERE repo=? AND branch=? AND scope=?
                """,
                (now, repo, branch, scope),
            )
        lease = self.get(repo, branch, scope)
        assert lease is not None
        return lease

    def release(
        self, *, repo: str, branch: str, scope: str, holder: str
    ) -> WriterLease:
        with self.conn:
            row = self.conn.execute(
                """
                SELECT holder FROM writer_leases
                WHERE repo=? AND branch=? AND scope=?
                """,
                (repo, branch, scope),
            ).fetchone()
            if row is None or row["holder"] != holder:
                raise LeaseConflict("cannot release a lease held by another writer")
            self.conn.execute(
                """
                UPDATE writer_leases
                SET state='RELEASED', holder=NULL
                WHERE repo=? AND branch=? AND scope=?
                """,
                (repo, branch, scope),
            )
        lease = self.get(repo, branch, scope)
        assert lease is not None
        return lease

    def reconcile_restart(self) -> int:
        with self.conn:
            cursor = self.conn.execute(
                """
                UPDATE writer_leases
                SET state='SUSPECT'
                WHERE state='ACTIVE'
                """
            )
        return int(cursor.rowcount)

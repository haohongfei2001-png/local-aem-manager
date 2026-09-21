from __future__ import annotations

import json
import sqlite3
from dataclasses import asdict, dataclass
from enum import Enum
from pathlib import Path
from typing import Any


class DeliveryState(str, Enum):
    PRE_SEND_FAILED = "PRE_SEND_FAILED"
    SENT_CONFIRMED = "SENT_CONFIRMED"
    POST_SEND_UNKNOWN = "POST_SEND_UNKNOWN"


@dataclass(frozen=True)
class DeliveryRecord:
    idempotency_key: str
    thread_id: str
    message_digest: str
    state: DeliveryState
    detail: str

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["state"] = self.state.value
        return payload


SCHEMA = """
CREATE TABLE IF NOT EXISTS thread_deliveries (
    idempotency_key TEXT PRIMARY KEY,
    thread_id TEXT NOT NULL,
    message_digest TEXT NOT NULL,
    state TEXT NOT NULL,
    detail TEXT NOT NULL,
    payload_json TEXT NOT NULL
);
"""


class DeliveryLedger:
    def __init__(self, path: str | Path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.conn = sqlite3.connect(self.path)
        self.conn.row_factory = sqlite3.Row
        self.conn.executescript(SCHEMA)

    def close(self) -> None:
        self.conn.close()

    def __enter__(self) -> "DeliveryLedger":
        return self

    def __exit__(self, *_: object) -> None:
        self.close()

    def get(self, idempotency_key: str) -> DeliveryRecord | None:
        row = self.conn.execute(
            """
            SELECT payload_json
            FROM thread_deliveries
            WHERE idempotency_key=?
            """,
            (idempotency_key,),
        ).fetchone()
        if row is None:
            return None
        payload = json.loads(row["payload_json"])
        return DeliveryRecord(
            idempotency_key=payload["idempotency_key"],
            thread_id=payload["thread_id"],
            message_digest=payload["message_digest"],
            state=DeliveryState(payload["state"]),
            detail=payload["detail"],
        )

    def save(self, record: DeliveryRecord) -> None:
        payload = record.to_dict()
        with self.conn:
            self.conn.execute(
                """
                INSERT INTO thread_deliveries
                (idempotency_key, thread_id, message_digest, state, detail, payload_json)
                VALUES (?, ?, ?, ?, ?, ?)
                ON CONFLICT(idempotency_key) DO UPDATE SET
                  thread_id=excluded.thread_id,
                  message_digest=excluded.message_digest,
                  state=excluded.state,
                  detail=excluded.detail,
                  payload_json=excluded.payload_json
                """,
                (
                    record.idempotency_key,
                    record.thread_id,
                    record.message_digest,
                    record.state.value,
                    record.detail,
                    json.dumps(payload, ensure_ascii=False, sort_keys=True),
                ),
            )


def may_retry(record: DeliveryRecord | None) -> bool:
    if record is None:
        return True
    return record.state == DeliveryState.PRE_SEND_FAILED

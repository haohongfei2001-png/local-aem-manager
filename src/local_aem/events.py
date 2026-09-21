from __future__ import annotations

import asyncio
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from typing import Any


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass(frozen=True)
class Event:
    type: str
    source: str
    subject: str
    observed_at: str
    payload: dict[str, Any]
    freshness_key: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class EventBus:
    def __init__(self):
        self._queue: asyncio.Queue[Event] = asyncio.Queue()
        self._seen: set[str] = set()

    async def publish(self, event: Event) -> bool:
        if event.freshness_key in self._seen:
            return False
        self._seen.add(event.freshness_key)
        await self._queue.put(event)
        return True

    async def next(self, timeout: float | None = None) -> Event:
        if timeout is None:
            return await self._queue.get()
        return await asyncio.wait_for(self._queue.get(), timeout=timeout)

    def empty(self) -> bool:
        return self._queue.empty()

from __future__ import annotations

from typing import Any, Callable

from .events import EventBus
from .scheduler import PortfolioScheduler


class PortfolioService:
    def __init__(
        self,
        *,
        bus: EventBus,
        sources: list[Any],
        observer: Callable[[], dict[str, Any]],
        scheduler: PortfolioScheduler,
    ):
        self.bus = bus
        self.sources = sources
        self.observer = observer
        self.scheduler = scheduler

    async def collect(self) -> int:
        published = 0
        for source in self.sources:
            for event in source.poll():
                if await self.bus.publish(event):
                    published += 1
        return published

    async def run_cycle(self) -> list[dict[str, Any]]:
        await self.collect()
        results: list[dict[str, Any]] = []
        while not self.bus.empty():
            event = await self.bus.next()
            snapshot = self.observer()
            result = self.scheduler.handle(
                snapshot=snapshot,
                event=event.to_dict(),
            )
            results.append(result.to_dict())
        return results

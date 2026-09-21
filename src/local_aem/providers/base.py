from __future__ import annotations

from typing import Protocol


class ManagerProvider(Protocol):
    def complete(self, *, system_prompt: str, user_prompt: str) -> str:
        ...

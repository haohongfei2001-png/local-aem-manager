from __future__ import annotations

from dataclasses import asdict, dataclass
from enum import Enum
from typing import Any


class ThreadUiState(str, Enum):
    IDLE = "IDLE"
    GENERATING = "GENERATING"
    ERROR = "ERROR"
    UNKNOWN = "UNKNOWN"


@dataclass(frozen=True)
class ThreadObservation:
    thread_id: str
    project_id: str
    ui_state: ThreadUiState
    latest_message_id: str | None
    latest_message_digest: str | None
    observed_at: str
    composer_available: bool
    send_button_available: bool
    transport_connected: bool
    error: str | None = None

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["ui_state"] = self.ui_state.value
        return payload

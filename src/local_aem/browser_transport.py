from __future__ import annotations

from typing import Protocol

from .thread_state import ThreadObservation


class BrowserTransportError(RuntimeError):
    pass


class PreSendError(BrowserTransportError):
    pass


class PostSendUnknown(BrowserTransportError):
    pass


class BrowserTransport(Protocol):
    def capability_probe(self) -> dict:
        ...

    def observe_thread(self, thread_id: str, project_id: str) -> ThreadObservation:
        ...

    def prepare_message(self, thread_id: str, text: str) -> None:
        """Fill/prepare a composer without committing the send."""
        ...

    def commit_send(self, thread_id: str) -> None:
        """Trigger the irreversible send action."""
        ...

    def confirm_send(
        self,
        thread_id: str,
        *,
        previous_message_id: str | None,
        expected_digest: str,
    ) -> bool:
        """Return True only when send confirmation is positively observed."""
        ...

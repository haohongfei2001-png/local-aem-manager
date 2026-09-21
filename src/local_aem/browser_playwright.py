from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .browser_transport import BrowserTransportError
from .thread_state import ThreadObservation


@dataclass(frozen=True)
class PlaywrightSelectors:
    conversation_root: str
    composer: str
    send_button: str
    assistant_messages: str


class PlaywrightCdpTransport:
    """Capability adapter for an already-running Chrome CDP endpoint.

    R6 does not certify this adapter against the user's real Chrome. The
    optional Playwright dependency and live selectors are intentionally
    provided through runtime configuration rather than hard-coded product
    assumptions.
    """

    def __init__(
        self,
        *,
        cdp_endpoint: str,
        selectors: PlaywrightSelectors,
        thread_url_for: dict[str, str],
    ):
        self.cdp_endpoint = cdp_endpoint
        self.selectors = selectors
        self.thread_url_for = dict(thread_url_for)

    def capability_probe(self) -> dict[str, Any]:
        try:
            import playwright.sync_api  # noqa: F401
        except Exception:
            return {
                "transport": "playwright-cdp",
                "available": False,
                "reason": "playwright package is not installed",
                "live_certified": False,
            }
        return {
            "transport": "playwright-cdp",
            "available": True,
            "cdp_endpoint_configured": bool(self.cdp_endpoint),
            "thread_count": len(self.thread_url_for),
            "live_certified": False,
        }

    def _unsupported(self) -> None:
        raise BrowserTransportError(
            "PlaywrightCdpTransport requires R6 local capability certification "
            "before live use"
        )

    def observe_thread(
        self, thread_id: str, project_id: str
    ) -> ThreadObservation:
        self._unsupported()

    def prepare_message(self, thread_id: str, text: str) -> None:
        self._unsupported()

    def commit_send(self, thread_id: str) -> None:
        self._unsupported()

    def confirm_send(
        self,
        thread_id: str,
        *,
        previous_message_id: str | None,
        expected_digest: str,
    ) -> bool:
        self._unsupported()

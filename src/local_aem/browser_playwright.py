from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Any
from urllib.parse import urlsplit, urlunsplit

from .browser_transport import (
    BrowserTransportError,
    PostSendUnknown,
    PreSendError,
)
from .message_text import message_digest
from .thread_state import ThreadObservation, ThreadUiState


@dataclass(frozen=True)
class PlaywrightSelectors:
    conversation_root: str
    composer: str
    send_button: str
    assistant_messages: str
    user_messages: str
    generating_indicator: str | None = None
    message_id_attribute: str | None = "data-message-id"


class PlaywrightCdpTransport:
    """Playwright/CDP transport for an already-running Chrome session.

    The adapter is generic: selectors and thread URLs are runtime configuration.
    It is not considered live-certified until the R6 local capability harness
    passes against the user's current browser/profile.
    """

    def __init__(
        self,
        *,
        cdp_endpoint: str,
        selectors: PlaywrightSelectors,
        thread_url_for: dict[str, str],
        confirmation_timeout_seconds: float = 20.0,
    ):
        self.cdp_endpoint = cdp_endpoint
        self.selectors = selectors
        self.thread_url_for = dict(thread_url_for)
        self.confirmation_timeout_seconds = confirmation_timeout_seconds
        self._playwright = None
        self._browser = None
        self._prepared_user_counts: dict[str, int] = {}

    def capability_probe(self) -> dict[str, Any]:
        try:
            import playwright.sync_api  # noqa: F401
        except Exception:
            return {
                "transport": "playwright-cdp",
                "available": False,
                "reason": "playwright package is not installed",
                "cdp_endpoint_configured": bool(self.cdp_endpoint),
                "thread_count": len(self.thread_url_for),
                "live_certified": False,
            }
        return {
            "transport": "playwright-cdp",
            "available": True,
            "cdp_endpoint_configured": bool(self.cdp_endpoint),
            "thread_count": len(self.thread_url_for),
            "live_certified": False,
        }

    @staticmethod
    def _canonical_url(value: str) -> str:
        parts = urlsplit(value)
        path = parts.path.rstrip("/") or "/"
        return urlunsplit(
            (parts.scheme, parts.netloc, path, parts.query, "")
        )

    def _ensure_browser(self):
        if self._browser is not None:
            return self._browser
        try:
            from playwright.sync_api import sync_playwright
        except Exception as exc:
            raise BrowserTransportError(
                "playwright is not installed; install the browser extra"
            ) from exc
        try:
            self._playwright = sync_playwright().start()
            self._browser = self._playwright.chromium.connect_over_cdp(
                self.cdp_endpoint
            )
        except Exception as exc:
            self.close()
            raise BrowserTransportError(
                f"cannot connect to Chrome CDP endpoint: {exc}"
            ) from exc
        return self._browser

    def close(self) -> None:
        browser = self._browser
        playwright = self._playwright
        self._browser = None
        self._playwright = None
        if browser is not None:
            try:
                browser.close()
            except Exception:
                pass
        if playwright is not None:
            try:
                playwright.stop()
            except Exception:
                pass

    def _target_url(self, thread_id: str) -> str:
        try:
            return self.thread_url_for[thread_id]
        except KeyError as exc:
            raise BrowserTransportError(
                f"thread {thread_id!r} has no configured URL"
            ) from exc

    def _page_for_thread(self, thread_id: str):
        browser = self._ensure_browser()
        target = self._canonical_url(self._target_url(thread_id))
        pages = []
        for context in browser.contexts:
            pages.extend(context.pages)

        for page in pages:
            if self._canonical_url(page.url) == target:
                return page

        raise BrowserTransportError(
            f"configured thread page is not open: {thread_id}"
        )

    def _message_id(self, locator, fallback: str) -> str:
        attr = self.selectors.message_id_attribute
        if attr:
            try:
                value = locator.get_attribute(attr)
                if value:
                    return value
            except Exception:
                pass
        return fallback

    def observe_thread(
        self, thread_id: str, project_id: str
    ) -> ThreadObservation:
        try:
            page = self._page_for_thread(thread_id)
            root = page.locator(self.selectors.conversation_root)
            if root.count() == 0:
                raise BrowserTransportError("conversation root not found")

            assistant = root.locator(self.selectors.assistant_messages)
            count = assistant.count()
            latest_id = None
            latest_digest = None
            if count:
                last = assistant.nth(count - 1)
                text = last.inner_text(timeout=3000)
                latest_digest = message_digest(text)
                latest_id = self._message_id(
                    last,
                    f"assistant:{count - 1}:{latest_digest[:12]}",
                )

            composer = page.locator(self.selectors.composer)
            send = page.locator(self.selectors.send_button)

            generating = False
            if self.selectors.generating_indicator:
                indicator = page.locator(
                    self.selectors.generating_indicator
                )
                generating = bool(
                    indicator.count() and indicator.first.is_visible()
                )

            return ThreadObservation(
                thread_id=thread_id,
                project_id=project_id,
                ui_state=(
                    ThreadUiState.GENERATING
                    if generating
                    else ThreadUiState.IDLE
                ),
                latest_message_id=latest_id,
                latest_message_digest=latest_digest,
                observed_at=time.strftime(
                    "%Y-%m-%dT%H:%M:%SZ", time.gmtime()
                ),
                composer_available=bool(
                    composer.count() and composer.first.is_visible()
                ),
                send_button_available=bool(
                    send.count() and send.first.is_visible()
                ),
                transport_connected=True,
            )
        except Exception as exc:
            if isinstance(exc, BrowserTransportError):
                raise
            raise BrowserTransportError(
                f"thread observation failed: {exc}"
            ) from exc

    def prepare_message(self, thread_id: str, text: str) -> None:
        page = self._page_for_thread(thread_id)
        composer = page.locator(self.selectors.composer)
        if composer.count() == 0 or not composer.first.is_visible():
            raise PreSendError("composer is not visible")

        user_messages = page.locator(self.selectors.user_messages)
        self._prepared_user_counts[thread_id] = user_messages.count()

        try:
            composer.first.fill(text, timeout=5000)
        except Exception as exc:
            raise PreSendError(
                f"composer fill failed before send: {exc}"
            ) from exc

    def commit_send(self, thread_id: str) -> None:
        page = self._page_for_thread(thread_id)
        send = page.locator(self.selectors.send_button)
        if send.count() == 0:
            raise PreSendError("send button is absent before click")
        button = send.first
        try:
            if not button.is_visible() or not button.is_enabled():
                raise PreSendError(
                    "send button is not visible/enabled before click"
                )
        except PreSendError:
            raise
        except Exception as exc:
            raise PreSendError(
                f"send button state unavailable before click: {exc}"
            ) from exc

        try:
            button.click(timeout=5000)
        except Exception as exc:
            # Once click has been attempted, delivery is uncertain.
            raise PostSendUnknown(
                f"send click produced an uncertain result: {exc}"
            ) from exc

    def confirm_send(
        self,
        thread_id: str,
        *,
        previous_message_id: str | None,
        expected_digest: str,
    ) -> bool:
        page = self._page_for_thread(thread_id)
        baseline = self._prepared_user_counts.get(thread_id, 0)
        deadline = time.monotonic() + self.confirmation_timeout_seconds

        while time.monotonic() < deadline:
            messages = page.locator(self.selectors.user_messages)
            count = messages.count()
            if count > baseline:
                for index in range(baseline, count):
                    try:
                        text = messages.nth(index).inner_text(
                            timeout=2000
                        )
                    except Exception:
                        continue
                    if message_digest(text) == expected_digest:
                        return True
            time.sleep(0.25)

        raise PostSendUnknown(
            "send was triggered but matching user message was not "
            "positively confirmed before timeout"
        )

    def refresh_thread(self, thread_id: str) -> None:
        page = self._page_for_thread(thread_id)
        try:
            page.reload(wait_until="domcontentloaded", timeout=15000)
        except Exception as exc:
            raise BrowserTransportError(
                f"thread refresh failed: {exc}"
            ) from exc

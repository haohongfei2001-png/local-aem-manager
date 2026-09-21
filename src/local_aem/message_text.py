from __future__ import annotations

import hashlib


def normalize_message_text(text: str) -> str:
    return text.replace("\r\n", "\n").replace("\r", "\n").strip()


def message_digest(text: str) -> str:
    return hashlib.sha256(
        normalize_message_text(text).encode("utf-8")
    ).hexdigest()

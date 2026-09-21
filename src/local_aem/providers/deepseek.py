from __future__ import annotations

from .openai_compat import OpenAICompatibleProvider


class DeepSeekProvider(OpenAICompatibleProvider):
    """DeepSeek adapter using the OpenAI-compatible transport.

    base_url and model remain configuration, not hard-coded policy.
    """

    pass

from __future__ import annotations

import json
import os
from urllib.request import Request, urlopen


class ProviderError(RuntimeError):
    pass


class OpenAICompatibleProvider:
    def __init__(
        self,
        *,
        base_url: str,
        model: str,
        api_key_env: str,
        timeout: int = 180,
        opener=urlopen,
        json_mode: bool = False,
    ):
        if not base_url:
            raise ProviderError("provider base_url is required")
        if not model:
            raise ProviderError("provider model is required")
        self.base_url = base_url.rstrip("/")
        self.model = model
        self.api_key_env = api_key_env
        self.timeout = timeout
        self.opener = opener
        self.json_mode = json_mode

    def complete(self, *, system_prompt: str, user_prompt: str) -> str:
        key = os.environ.get(self.api_key_env)
        if not key:
            raise ProviderError(
                f"missing provider credential environment variable: {self.api_key_env}"
            )

        payload = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            "temperature": 0,
        }
        if self.json_mode:
            payload["response_format"] = {"type": "json_object"}

        body = json.dumps(payload).encode("utf-8")
        request = Request(
            f"{self.base_url}/chat/completions",
            data=body,
            headers={
                "Authorization": f"Bearer {key}",
                "Content-Type": "application/json",
                "Accept": "application/json",
                "User-Agent": "local-aem-manager-r2",
            },
            method="POST",
        )
        try:
            with self.opener(request, timeout=self.timeout) as response:
                raw = response.read().decode("utf-8")
        except Exception as exc:
            raise ProviderError(f"manager provider request failed: {exc}") from exc

        try:
            parsed = json.loads(raw)
            content = parsed["choices"][0]["message"]["content"]
        except Exception as exc:
            raise ProviderError(
                "manager provider returned an unexpected response shape"
            ) from exc

        if not isinstance(content, str) or not content.strip():
            raise ProviderError("manager provider returned empty content")
        return content

from __future__ import annotations

from typing import Any

from .base import ManagerProvider
from .deepseek import DeepSeekProvider
from .openai_compat import OpenAICompatibleProvider, ProviderError


def build_provider(config: dict[str, Any]) -> ManagerProvider:
    manager = config.get("manager", {})
    providers = config.get("providers", {})
    provider_name = str(manager.get("provider", "")).strip()
    model = manager.get("model")

    if provider_name == "deepseek":
        p = providers.get("deepseek", {})
        return DeepSeekProvider(
            base_url=str(p.get("base_url") or ""),
            model=str(model or p.get("model") or ""),
            api_key_env=str(p.get("api_key_ref") or "DEEPSEEK_API_KEY"),
            timeout=int(manager.get("timeout_seconds", 180)),
            json_mode=bool(p.get("json_mode", False)),
        )

    if provider_name in {"openai_compatible", "openai-compatible"}:
        p = providers.get("openai_compatible", {})
        return OpenAICompatibleProvider(
            base_url=str(p.get("base_url") or ""),
            model=str(model or p.get("model") or ""),
            api_key_env=str(p.get("api_key_ref") or "OPENAI_API_KEY"),
            timeout=int(manager.get("timeout_seconds", 180)),
            json_mode=bool(p.get("json_mode", False)),
        )

    raise ProviderError(f"unsupported manager provider: {provider_name!r}")


__all__ = [
    "ManagerProvider",
    "DeepSeekProvider",
    "OpenAICompatibleProvider",
    "ProviderError",
    "build_provider",
]

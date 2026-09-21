from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml


class ConfigError(ValueError):
    pass


@dataclass(frozen=True)
class RuntimeConfig:
    raw: dict[str, Any]
    source: Path

    @property
    def data_dir(self) -> Path:
        value = self.raw.get("runtime", {}).get("data_dir", "~/.local/share/local-aem-manager")
        return Path(value).expanduser()

    @property
    def mode(self) -> str:
        return str(self.raw.get("runtime", {}).get("mode", "shadow"))

    @property
    def projects(self) -> list[dict[str, Any]]:
        projects = self.raw.get("portfolio", {}).get("projects", [])
        if projects is None:
            return []
        if not isinstance(projects, list):
            raise ConfigError("portfolio.projects must be a list")
        return projects

    @property
    def policy(self) -> dict[str, Any]:
        return dict(self.raw.get("policy", {}))

    @property
    def github(self) -> dict[str, Any]:
        return dict(self.raw.get("github", {}))

    @property
    def safety(self) -> dict[str, Any]:
        return dict(self.raw.get("safety", {}))


def load_config(path: str | Path) -> RuntimeConfig:
    source = Path(path).expanduser()
    if not source.exists():
        raise ConfigError(f"config not found: {source}")
    payload = yaml.safe_load(source.read_text(encoding="utf-8")) or {}
    if not isinstance(payload, dict):
        raise ConfigError("config root must be a mapping")
    return RuntimeConfig(raw=payload, source=source)


def assert_r1_shadow_safe(config: RuntimeConfig) -> None:
    if config.mode != "shadow":
        raise ConfigError("R1 only permits runtime.mode=shadow")
    if config.safety.get("allow_managed_repo_writes", False):
        raise ConfigError("R1 forbids managed-repo writes")
    executors = config.raw.get("executors", {})
    enabled = [
        name
        for name, value in executors.items()
        if isinstance(value, dict) and value.get("enabled", False)
    ]
    if enabled:
        raise ConfigError(f"R1 forbids enabled executors: {', '.join(enabled)}")

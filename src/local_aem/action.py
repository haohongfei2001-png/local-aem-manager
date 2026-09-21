from __future__ import annotations

import json
from importlib import resources
from typing import Any

from jsonschema import Draft202012Validator


class ActionValidationError(ValueError):
    pass


def load_action_schema() -> dict[str, Any]:
    resource = resources.files("local_aem").joinpath(
        "schemas/action-plan.schema.json"
    )
    return json.loads(resource.read_text(encoding="utf-8"))


def validate_action_plan(payload: Any) -> dict[str, Any]:
    if not isinstance(payload, dict):
        raise ActionValidationError("action plan must be a JSON object")
    validator = Draft202012Validator(load_action_schema())
    errors = sorted(validator.iter_errors(payload), key=lambda e: list(e.path))
    if errors:
        joined = "; ".join(
            f"{'.'.join(map(str, err.path)) or '<root>'}: {err.message}"
            for err in errors
        )
        raise ActionValidationError(joined)

    expected = {
        "RUN_SHELL": "SHELL",
        "GITHUB_MUTATION": "GITHUB",
        "CODEX_TASK": "CODEX",
    }[payload["operation"]]
    if payload["executor"] != expected:
        raise ActionValidationError(
            f"operation {payload['operation']} requires executor {expected}"
        )
    return payload

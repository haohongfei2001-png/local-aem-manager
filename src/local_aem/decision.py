from __future__ import annotations

import json
from importlib import resources
from typing import Any

from jsonschema import Draft202012Validator


class DecisionValidationError(ValueError):
    pass


def load_decision_schema() -> dict[str, Any]:
    resource = resources.files("local_aem").joinpath(
        "schemas/manager-decision.schema.json"
    )
    return json.loads(resource.read_text(encoding="utf-8"))


def validate_decision(payload: Any) -> dict[str, Any]:
    if not isinstance(payload, dict):
        raise DecisionValidationError("manager decision must be a JSON object")
    validator = Draft202012Validator(load_decision_schema())
    errors = sorted(validator.iter_errors(payload), key=lambda e: list(e.path))
    if errors:
        joined = "; ".join(
            f"{'.'.join(map(str, err.path)) or '<root>'}: {err.message}"
            for err in errors
        )
        raise DecisionValidationError(joined)

    if payload["owner_required"] and not payload.get("owner_reason"):
        raise DecisionValidationError(
            "owner_reason is required when owner_required=true"
        )
    if (
        payload["action_type"] == "OWNER_ESCALATION"
        and not payload["owner_required"]
    ):
        raise DecisionValidationError(
            "OWNER_ESCALATION requires owner_required=true"
        )
    return payload

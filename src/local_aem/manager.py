from __future__ import annotations

import json
from typing import Any

from .decision import DecisionValidationError, load_decision_schema, validate_decision
from .policy import PolicyBundle
from .providers.base import ManagerProvider


POLICY_PROMPT_FILES = (
    "MANAGER_CHARTER.md",
    "OPERATING_PLAYBOOK.md",
    "DECISION_POLICY.md",
    "ESCALATION_POLICY.md",
    "EXECUTION_AND_TAKEOVER.md",
)


def _strip_code_fence(text: str) -> str:
    value = text.strip()
    if value.startswith("```"):
        lines = value.splitlines()
        if lines and lines[0].startswith("```"):
            lines = lines[1:]
        if lines and lines[-1].strip() == "```":
            lines = lines[:-1]
        value = "\n".join(lines).strip()
    return value


class ManagerBrain:
    def __init__(self, provider: ManagerProvider):
        self.provider = provider

    def _system_prompt(self, policy: PolicyBundle) -> str:
        sections = []
        for path in POLICY_PROMPT_FILES:
            sections.append(f"## {path}\n{policy.files[path]}")
        schema = json.dumps(
            load_decision_schema(), ensure_ascii=False, sort_keys=True
        )
        return (
            "You are the Autonomous Engineering Manager. "
            "Use the policy below as management authority, while project-specific "
            "canonical authority remains higher for that project. "
            "Return exactly one JSON object and no prose. "
            "The JSON must satisfy the supplied ManagerDecision schema. "
            "Do not invent evidence. Ordinary engineering decisions should be "
            "made autonomously; product/privacy/permission/credential/high-risk "
            "boundaries require owner escalation.\n\n"
            f"Policy version: {policy.version}\n"
            f"Policy digest: {policy.digest}\n\n"
            + "\n\n".join(sections)
            + "\n\n## ManagerDecision JSON Schema\n"
            + schema
        )

    def decide(
        self,
        *,
        policy: PolicyBundle,
        portfolio_snapshot: dict[str, Any],
        recent_context: list[dict[str, Any]] | None = None,
    ) -> dict[str, Any]:
        user_prompt = json.dumps(
            {
                "task": (
                    "Choose the single highest-value next management action for "
                    "this portfolio snapshot. Use requested_operations to declare "
                    "all capabilities the action would need."
                ),
                "portfolio_snapshot": portfolio_snapshot,
                "recent_context": recent_context or [],
            },
            ensure_ascii=False,
            sort_keys=True,
        )
        raw = self.provider.complete(
            system_prompt=self._system_prompt(policy),
            user_prompt=user_prompt,
        )
        try:
            payload = json.loads(_strip_code_fence(raw))
        except json.JSONDecodeError as exc:
            raise DecisionValidationError(
                "manager provider did not return valid JSON"
            ) from exc

        decision = validate_decision(payload)
        if decision["evidence_snapshot_id"] != portfolio_snapshot["snapshot_id"]:
            raise DecisionValidationError(
                "manager decision references a stale/foreign evidence snapshot"
            )
        projects = {
            item["project_id"]: item
            for item in portfolio_snapshot.get("projects", [])
        }
        if decision["project_id"] not in projects:
            raise DecisionValidationError(
                "manager decision targets a project absent from the snapshot"
            )
        return decision

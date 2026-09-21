from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

from .decision import DecisionValidationError, validate_decision
from .gate import evaluate_decision


@dataclass(frozen=True)
class ReplayCaseResult:
    name: str
    expected: str
    actual: str
    passed: bool
    detail: str


def load_replay_cases(path: str | Path) -> list[dict[str, Any]]:
    payload = yaml.safe_load(Path(path).read_text(encoding="utf-8")) or {}
    cases = payload.get("cases", [])
    if not isinstance(cases, list):
        raise ValueError("replay fixture cases must be a list")
    return cases


def run_replay_file(path: str | Path) -> list[ReplayCaseResult]:
    results: list[ReplayCaseResult] = []
    for case in load_replay_cases(path):
        name = str(case["name"])
        expected = str(case["expected_disposition"])
        try:
            decision = validate_decision(case["decision"])
            gate = evaluate_decision(
                decision,
                case["project_state"],
                case.get("authorization") or {},
            )
            actual = gate.disposition.value
            detail = "; ".join(gate.reasons)
        except DecisionValidationError as exc:
            actual = "DECISION_INVALID"
            detail = str(exc)
        passed = actual == expected
        results.append(
            ReplayCaseResult(
                name=name,
                expected=expected,
                actual=actual,
                passed=passed,
                detail=detail,
            )
        )
    return results


def replay_summary(results: list[ReplayCaseResult]) -> dict[str, Any]:
    passed = sum(1 for item in results if item.passed)
    return {
        "total": len(results),
        "passed": passed,
        "failed": len(results) - passed,
        "cases": [
            {
                "name": item.name,
                "expected": item.expected,
                "actual": item.actual,
                "passed": item.passed,
                "detail": item.detail,
            }
            for item in results
        ],
    }

from __future__ import annotations

from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class VerificationItem:
    type: str
    passed: bool
    detail: str


@dataclass(frozen=True)
class VerificationReport:
    passed: bool
    items: list[VerificationItem]

    def to_dict(self) -> dict[str, Any]:
        return {
            "passed": self.passed,
            "items": [asdict(item) for item in self.items],
        }


def _sandbox_path(root: Path, relative: str) -> Path:
    candidate = (root / relative).resolve()
    try:
        candidate.relative_to(root)
    except ValueError as exc:
        raise ValueError("verification path escapes sandbox root") from exc
    return candidate


def verify_action(
    plan: dict[str, Any],
    result: dict[str, Any],
    *,
    sandbox_root: str | Path | None = None,
) -> VerificationReport:
    root = Path(sandbox_root).resolve() if sandbox_root is not None else None
    items: list[VerificationItem] = []

    for spec in plan["verification"]:
        kind = spec["type"]
        if kind == "JOB_SUCCEEDED":
            passed = result.get("state") == "SUCCEEDED"
            items.append(
                VerificationItem(
                    kind,
                    passed,
                    f"executor state={result.get('state')}",
                )
            )
            continue

        if root is None:
            items.append(
                VerificationItem(
                    kind,
                    False,
                    "filesystem verification requires sandbox_root",
                )
            )
            continue

        raw_path = spec.get("path")
        if not raw_path:
            items.append(
                VerificationItem(kind, False, "verification path is missing")
            )
            continue

        path = _sandbox_path(root, raw_path)
        if kind == "FILE_EXISTS":
            items.append(
                VerificationItem(
                    kind,
                    path.exists(),
                    f"path={path}",
                )
            )
        elif kind == "FILE_TEXT_EQUALS":
            if not path.exists():
                items.append(
                    VerificationItem(
                        kind,
                        False,
                        f"path does not exist: {path}",
                    )
                )
            else:
                actual = path.read_text(encoding="utf-8")
                expected = spec.get("expected") or ""
                items.append(
                    VerificationItem(
                        kind,
                        actual == expected,
                        f"path={path}",
                    )
                )
        else:
            items.append(
                VerificationItem(kind, False, f"unsupported verifier: {kind}")
            )

    return VerificationReport(
        passed=bool(items) and all(item.passed for item in items),
        items=items,
    )

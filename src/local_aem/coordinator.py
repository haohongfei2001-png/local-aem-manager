from __future__ import annotations

from typing import Any

from .action import validate_action_plan
from .control import RuntimeControl
from .gate import GateDisposition, GateResult
from .jobs import ExecutionConflict, ExecutionLedger
from .executors.base import utc_now
from .verifier import verify_action


class CoordinatorError(RuntimeError):
    pass


class ExecutionCoordinator:
    def __init__(
        self,
        *,
        ledger: ExecutionLedger,
        executors: dict[str, Any],
        control: RuntimeControl | None = None,
    ):
        self.ledger = ledger
        self.executors = executors
        self.control = control

    def run(
        self,
        plan: dict[str, Any],
        *,
        gate_result: GateResult,
    ) -> dict[str, Any]:
        plan = validate_action_plan(plan)
        if gate_result.disposition != GateDisposition.APPROVE:
            raise CoordinatorError(
                f"gate disposition {gate_result.disposition.value} forbids execution"
            )
        if self.control is not None:
            self.control.assert_new_actions_allowed()

        previous = self.ledger.get(plan["idempotency_key"])
        if previous is not None:
            replay = dict(previous)
            replay["replayed"] = True
            return replay

        reservation = self.ledger.reservation(plan["idempotency_key"])
        if reservation is not None:
            raise CoordinatorError(
                "action has an unfinished/uncertain reservation; reconcile before retry"
            )

        executor = self.executors.get(plan["executor"])
        if executor is None:
            raise CoordinatorError(
                f"executor {plan['executor']} is not registered"
            )

        executor.prepare(plan)
        try:
            self.ledger.reserve(
                idempotency_key=plan["idempotency_key"],
                action_id=plan["action_id"],
                executor=plan["executor"],
            )
        except ExecutionConflict as exc:
            raise CoordinatorError(str(exc)) from exc

        result = executor.execute(plan)
        result_payload = result.to_dict()
        sandbox_root = getattr(executor, "sandbox_root", None)
        verification = verify_action(
            plan,
            result_payload,
            sandbox_root=sandbox_root,
        )
        record = {
            **result_payload,
            "action_id": plan["action_id"],
            "idempotency_key": plan["idempotency_key"],
            "verification": verification.to_dict(),
            "replayed": False,
        }
        self.ledger.save(
            idempotency_key=plan["idempotency_key"],
            action_id=plan["action_id"],
            result=record,
            created_at=utc_now(),
        )
        return record

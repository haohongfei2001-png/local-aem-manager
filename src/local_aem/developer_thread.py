from __future__ import annotations

import uuid
from typing import Any

from .browser_transport import (
    BrowserTransport,
    PostSendUnknown,
    PreSendError,
)
from .delivery import (
    DeliveryLedger,
    DeliveryRecord,
    DeliveryState,
    may_retry,
)
from .executors.base import ExecutorResult, ExecutorState, utc_now
from .message_text import message_digest


class ThreadExecutorError(RuntimeError):
    pass


class DeveloperThreadExecutor:
    name = "DEVELOPER_THREAD"

    def __init__(
        self,
        *,
        transport: BrowserTransport,
        delivery_ledger: DeliveryLedger,
    ):
        self.transport = transport
        self.delivery_ledger = delivery_ledger
        self._jobs: dict[str, ExecutorResult] = {}

    def capability_probe(self) -> dict[str, Any]:
        return {
            "executor": self.name,
            "transport": self.transport.capability_probe(),
        }

    def prepare(self, plan: dict[str, Any]) -> None:
        if plan["operation"] != "SEND_THREAD_MESSAGE":
            raise ThreadExecutorError(
                "DeveloperThreadExecutor only accepts SEND_THREAD_MESSAGE"
            )
        params = plan["params"]
        thread_id = str(params.get("thread_id") or "")
        message = str(params.get("message") or "")
        if not thread_id:
            raise ThreadExecutorError("thread_id is required")
        if not message.strip():
            raise ThreadExecutorError("message must not be empty")

        existing = self.delivery_ledger.get(plan["idempotency_key"])
        if not may_retry(existing):
            raise ThreadExecutorError(
                f"delivery state {existing.state.value} forbids automatic retry"
            )

    def execute(self, plan: dict[str, Any]) -> ExecutorResult:
        self.prepare(plan)
        params = plan["params"]
        thread_id = str(params["thread_id"])
        project_id = str(params.get("project_id") or plan["project_id"])
        message = str(params["message"])
        digest = message_digest(message)
        job_id = f"thread-{uuid.uuid4().hex[:16]}"
        started = utc_now()

        before = self.transport.observe_thread(thread_id, project_id)
        try:
            self.transport.prepare_message(thread_id, message)
        except Exception as exc:
            record = DeliveryRecord(
                idempotency_key=plan["idempotency_key"],
                thread_id=thread_id,
                message_digest=digest,
                state=DeliveryState.PRE_SEND_FAILED,
                detail=str(exc),
            )
            self.delivery_ledger.save(record)
            result = ExecutorResult(
                job_id=job_id,
                executor=self.name,
                state=ExecutorState.FAILED,
                detail="message preparation failed before send",
                outputs={"delivery": record.to_dict()},
                started_at=started,
                ended_at=utc_now(),
            )
            self._jobs[job_id] = result
            return result

        try:
            self.transport.commit_send(thread_id)
        except PreSendError as exc:
            record = DeliveryRecord(
                idempotency_key=plan["idempotency_key"],
                thread_id=thread_id,
                message_digest=digest,
                state=DeliveryState.PRE_SEND_FAILED,
                detail=str(exc),
            )
            self.delivery_ledger.save(record)
            result = ExecutorResult(
                job_id=job_id,
                executor=self.name,
                state=ExecutorState.FAILED,
                detail="send failed before irreversible commit",
                outputs={"delivery": record.to_dict()},
                started_at=started,
                ended_at=utc_now(),
            )
            self._jobs[job_id] = result
            return result
        except Exception as exc:
            record = DeliveryRecord(
                idempotency_key=plan["idempotency_key"],
                thread_id=thread_id,
                message_digest=digest,
                state=DeliveryState.POST_SEND_UNKNOWN,
                detail=str(exc),
            )
            self.delivery_ledger.save(record)
            result = ExecutorResult(
                job_id=job_id,
                executor=self.name,
                state=ExecutorState.UNKNOWN,
                detail="send may have committed; automatic retry is forbidden",
                outputs={"delivery": record.to_dict()},
                started_at=started,
                ended_at=utc_now(),
            )
            self._jobs[job_id] = result
            return result

        try:
            confirmed = self.transport.confirm_send(
                thread_id,
                previous_message_id=before.latest_message_id,
                expected_digest=digest,
            )
        except PostSendUnknown as exc:
            confirmed = False
            confirm_detail = str(exc)
        except Exception as exc:
            confirmed = False
            confirm_detail = str(exc)
        else:
            confirm_detail = "positive send confirmation observed"

        state = (
            DeliveryState.SENT_CONFIRMED
            if confirmed
            else DeliveryState.POST_SEND_UNKNOWN
        )
        record = DeliveryRecord(
            idempotency_key=plan["idempotency_key"],
            thread_id=thread_id,
            message_digest=digest,
            state=state,
            detail=confirm_detail,
        )
        self.delivery_ledger.save(record)

        result = ExecutorResult(
            job_id=job_id,
            executor=self.name,
            state=(
                ExecutorState.SUCCEEDED
                if confirmed
                else ExecutorState.UNKNOWN
            ),
            detail=(
                "thread message send confirmed"
                if confirmed
                else "send triggered but confirmation is uncertain"
            ),
            outputs={
                "delivery": record.to_dict(),
                "thread_id": thread_id,
            },
            started_at=started,
            ended_at=utc_now(),
        )
        self._jobs[job_id] = result
        return result

    def observe(self, job_id: str) -> ExecutorResult | None:
        return self._jobs.get(job_id)

    def cancel(self, job_id: str) -> bool:
        return False

    def collect_result(self, job_id: str) -> ExecutorResult | None:
        return self._jobs.get(job_id)

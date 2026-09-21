from __future__ import annotations

import argparse
import json
import tempfile
import time
from pathlib import Path
from typing import Any

import yaml

from .browser_playwright import (
    PlaywrightCdpTransport,
    PlaywrightSelectors,
)
from .browser_transport import PostSendUnknown, PreSendError
from .delivery import DeliveryLedger, DeliveryState
from .developer_thread import (
    DeveloperThreadExecutor,
    ThreadExecutorError,
)
from .freshness import (
    FreshnessClass,
    FreshnessEvidence,
    classify_freshness,
)
from .leases import WriterLeaseStore
from .takeover import TakeoverDecision, assess_takeover


class CertificationConfigError(ValueError):
    pass


class _DelegatingTransport:
    def __init__(self, inner):
        self.inner = inner

    def capability_probe(self):
        return self.inner.capability_probe()

    def observe_thread(self, thread_id, project_id):
        return self.inner.observe_thread(thread_id, project_id)

    def prepare_message(self, thread_id, text):
        return self.inner.prepare_message(thread_id, text)

    def commit_send(self, thread_id):
        return self.inner.commit_send(thread_id)

    def confirm_send(
        self,
        thread_id,
        *,
        previous_message_id,
        expected_digest,
    ):
        return self.inner.confirm_send(
            thread_id,
            previous_message_id=previous_message_id,
            expected_digest=expected_digest,
        )


class _PreSendFaultTransport(_DelegatingTransport):
    def __init__(self, inner):
        super().__init__(inner)
        self.failed = False

    def prepare_message(self, thread_id, text):
        if not self.failed:
            self.failed = True
            raise PreSendError(
                "R6 certification injected a fault before composer commit"
            )
        return self.inner.prepare_message(thread_id, text)


class _PostSendFaultTransport(_DelegatingTransport):
    def commit_send(self, thread_id):
        self.inner.commit_send(thread_id)
        raise PostSendUnknown(
            "R6 certification injected uncertainty after real send click"
        )


def _load(path: str | Path) -> dict[str, Any]:
    source = Path(path).expanduser()
    payload = yaml.safe_load(source.read_text(encoding="utf-8")) or {}
    cert = payload.get("r6_certification")
    if not isinstance(cert, dict):
        raise CertificationConfigError(
            "r6_certification mapping is required"
        )
    return cert


def _selectors(payload: dict[str, Any]) -> PlaywrightSelectors:
    required = (
        "conversation_root",
        "composer",
        "send_button",
        "assistant_messages",
        "user_messages",
    )
    missing = [key for key in required if not payload.get(key)]
    if missing:
        raise CertificationConfigError(
            f"missing selector fields: {', '.join(missing)}"
        )
    return PlaywrightSelectors(
        conversation_root=str(payload["conversation_root"]),
        composer=str(payload["composer"]),
        send_button=str(payload["send_button"]),
        assistant_messages=str(payload["assistant_messages"]),
        user_messages=str(payload["user_messages"]),
        generating_indicator=(
            str(payload["generating_indicator"])
            if payload.get("generating_indicator")
            else None
        ),
        message_id_attribute=(
            str(payload["message_id_attribute"])
            if payload.get("message_id_attribute")
            else None
        ),
    )


def _send_plan(
    *,
    key: str,
    thread_id: str,
    project_id: str,
    message: str,
) -> dict[str, Any]:
    return {
        "action_id": key,
        "decision_id": f"decision-{key}",
        "project_id": project_id,
        "executor": "DEVELOPER_THREAD",
        "operation": "SEND_THREAD_MESSAGE",
        "target": {
            "repo": "local/r6-certification",
            "branch": "none",
            "scope": "R6_LOCAL_CERT",
        },
        "params": {
            "thread_id": thread_id,
            "project_id": project_id,
            "message": message,
        },
        "verification": [{"type": "JOB_SUCCEEDED"}],
        "idempotency_key": key,
        "dry_run": False,
    }


def run_certification(config_path: str | Path) -> dict[str, Any]:
    cert = _load(config_path)
    cdp_endpoint = str(cert.get("cdp_endpoint") or "")
    if not cdp_endpoint:
        raise CertificationConfigError("cdp_endpoint is required")

    threads = cert.get("threads")
    if not isinstance(threads, dict) or not threads:
        raise CertificationConfigError("threads mapping is required")

    certification_thread = str(cert.get("certification_thread") or "")
    if certification_thread not in threads:
        raise CertificationConfigError(
            "certification_thread must name a configured thread"
        )

    thread_urls = {
        str(thread_id): str(info["url"])
        for thread_id, info in threads.items()
    }
    project_ids = {
        str(thread_id): str(info["project_id"])
        for thread_id, info in threads.items()
    }
    selectors = _selectors(dict(cert.get("selectors") or {}))
    transport = PlaywrightCdpTransport(
        cdp_endpoint=cdp_endpoint,
        selectors=selectors,
        thread_url_for=thread_urls,
        confirmation_timeout_seconds=float(
            cert.get("confirmation_timeout_seconds", 20.0)
        ),
    )

    prefix = str(
        cert.get("send_message_prefix")
        or "LOCAL_AEM_R6_CERTIFICATION"
    )
    nonce = str(int(time.time()))
    results: dict[str, Any] = {
        "capability": transport.capability_probe(),
        "observations": {},
        "refresh_rebind": False,
        "normal_send": None,
        "pre_send_retry": None,
        "post_send_unknown": None,
        "post_send_retry_blocked": False,
        "controlled_stale_takeover": False,
    }

    try:
        if not results["capability"].get("available"):
            results["passed"] = False
            return results

        for thread_id in threads:
            observation = transport.observe_thread(
                str(thread_id), project_ids[str(thread_id)]
            )
            results["observations"][str(thread_id)] = (
                observation.to_dict()
            )

        transport.refresh_thread(certification_thread)
        refreshed = transport.observe_thread(
            certification_thread,
            project_ids[certification_thread],
        )
        results["refresh_rebind"] = refreshed.transport_connected

        with tempfile.TemporaryDirectory(
            prefix="local-aem-r6-cert-"
        ) as tmp:
            state_db = Path(tmp) / "cert.db"

            with DeliveryLedger(state_db) as ledger:
                normal_message = (
                    f"{prefix} normal-send {nonce}"
                )
                normal_plan = _send_plan(
                    key=f"r6-normal-{nonce}",
                    thread_id=certification_thread,
                    project_id=project_ids[certification_thread],
                    message=normal_message,
                )
                normal = DeveloperThreadExecutor(
                    transport=transport,
                    delivery_ledger=ledger,
                ).execute(normal_plan)
                results["normal_send"] = normal.to_dict()

                pre_message = (
                    f"{prefix} pre-send-retry {nonce}"
                )
                pre_plan = _send_plan(
                    key=f"r6-pre-{nonce}",
                    thread_id=certification_thread,
                    project_id=project_ids[certification_thread],
                    message=pre_message,
                )
                pre_fault = DeveloperThreadExecutor(
                    transport=_PreSendFaultTransport(transport),
                    delivery_ledger=ledger,
                ).execute(pre_plan)
                pre_retry = DeveloperThreadExecutor(
                    transport=transport,
                    delivery_ledger=ledger,
                ).execute(pre_plan)
                results["pre_send_retry"] = {
                    "fault": pre_fault.to_dict(),
                    "retry": pre_retry.to_dict(),
                }

                post_message = (
                    f"{prefix} post-send-unknown {nonce}"
                )
                post_plan = _send_plan(
                    key=f"r6-post-{nonce}",
                    thread_id=certification_thread,
                    project_id=project_ids[certification_thread],
                    message=post_message,
                )
                post_executor = DeveloperThreadExecutor(
                    transport=_PostSendFaultTransport(transport),
                    delivery_ledger=ledger,
                )
                post = post_executor.execute(post_plan)
                results["post_send_unknown"] = post.to_dict()

                try:
                    DeveloperThreadExecutor(
                        transport=transport,
                        delivery_ledger=ledger,
                    ).prepare(post_plan)
                except ThreadExecutorError:
                    results["post_send_retry_blocked"] = True

                normal_record = ledger.get(normal_plan["idempotency_key"])
                pre_record = ledger.get(pre_plan["idempotency_key"])
                post_record = ledger.get(post_plan["idempotency_key"])

            takeover_cfg = dict(cert.get("takeover") or {})
            repo = str(
                takeover_cfg.get("repo")
                or "local/r6-certification"
            )
            branch = str(
                takeover_cfg.get("branch")
                or "r6-certification"
            )
            scope = str(
                takeover_cfg.get("scope")
                or "R6_LOCAL_CERT"
            )

            with WriterLeaseStore(state_db) as leases:
                leases.acquire(
                    repo=repo,
                    branch=branch,
                    scope=scope,
                    holder="old-thread-writer",
                )
                leases.reconcile_restart()
                stale_evidence = FreshnessEvidence(
                    ui_generating=True,
                    transport_connected=True,
                    elapsed_seconds_without_progress=1900,
                )
                freshness = classify_freshness(
                    stale_evidence,
                    suspect_after_seconds=900,
                    stale_after_seconds=1800,
                )
                if freshness == FreshnessClass.STALE:
                    leases.mark_stale(
                        repo=repo,
                        branch=branch,
                        scope=scope,
                        holder="old-thread-writer",
                    )
                assessment = assess_takeover(
                    freshness=freshness,
                    writer_state="STALE",
                    remote_reconstructable=True,
                    concurrent_process_credible=False,
                    product_or_permission_boundary=False,
                )
                if assessment.decision == TakeoverDecision.TAKEOVER_ALLOWED:
                    new_lease = leases.acquire(
                        repo=repo,
                        branch=branch,
                        scope=scope,
                        holder="replacement-writer",
                    )
                    results["controlled_stale_takeover"] = (
                        new_lease.state == "ACTIVE"
                        and new_lease.holder == "replacement-writer"
                    )

            results["passed"] = bool(
                results["refresh_rebind"]
                and normal_record is not None
                and normal_record.state == DeliveryState.SENT_CONFIRMED
                and pre_record is not None
                and pre_record.state == DeliveryState.SENT_CONFIRMED
                and post_record is not None
                and post_record.state == DeliveryState.POST_SEND_UNKNOWN
                and results["post_send_retry_blocked"]
                and results["controlled_stale_takeover"]
            )
            return results
    finally:
        transport.close()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="local-aem-r6-cert")
    parser.add_argument("--config", required=True)
    args = parser.parse_args(argv)
    result = run_certification(args.config)
    print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))
    return 0 if result.get("passed") else 1


if __name__ == "__main__":
    raise SystemExit(main())

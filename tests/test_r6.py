from pathlib import Path

import pytest

from local_aem.browser_playwright import (
    PlaywrightCdpTransport,
    PlaywrightSelectors,
)
from local_aem.browser_transport import PreSendError
from local_aem.delivery import DeliveryLedger, DeliveryState
from local_aem.developer_thread import (
    DeveloperThreadExecutor,
    ThreadExecutorError,
)
from local_aem.freshness import (
    FreshnessClass,
    FreshnessEvidence,
    classify_freshness,
)
from local_aem.leases import LeaseConflict, WriterLeaseStore
from local_aem.message_text import message_digest
from local_aem.takeover import (
    TakeoverDecision,
    assess_takeover,
)
from local_aem.thread_state import ThreadObservation, ThreadUiState


class FakeTransport:
    def __init__(
        self,
        *,
        prepare_error=None,
        commit_error=None,
        confirm=True,
    ):
        self.prepare_error = prepare_error
        self.commit_error = commit_error
        self.confirm = confirm
        self.prepare_calls = 0
        self.commit_calls = 0
        self.confirm_calls = 0

    def capability_probe(self):
        return {"transport": "fake", "available": True}

    def observe_thread(self, thread_id, project_id):
        return ThreadObservation(
            thread_id=thread_id,
            project_id=project_id,
            ui_state=ThreadUiState.IDLE,
            latest_message_id="m1",
            latest_message_digest="old",
            observed_at="2026-09-21T00:00:00+00:00",
            composer_available=True,
            send_button_available=True,
            transport_connected=True,
        )

    def prepare_message(self, thread_id, text):
        self.prepare_calls += 1
        if self.prepare_error:
            raise self.prepare_error

    def commit_send(self, thread_id):
        self.commit_calls += 1
        if self.commit_error:
            raise self.commit_error

    def confirm_send(
        self,
        thread_id,
        *,
        previous_message_id,
        expected_digest,
    ):
        self.confirm_calls += 1
        return self.confirm


def _plan(key="k1"):
    return {
        "action_id": "a1",
        "decision_id": "d1",
        "project_id": "p1",
        "executor": "DEVELOPER_THREAD",
        "operation": "SEND_THREAD_MESSAGE",
        "target": {
            "repo": "owner/repo",
            "branch": "main",
            "scope": "R6",
        },
        "params": {
            "thread_id": "thread-1",
            "project_id": "p1",
            "message": "continue the bounded repair",
        },
        "verification": [{"type": "JOB_SUCCEEDED"}],
        "idempotency_key": key,
        "dry_run": False,
    }


def test_message_digest_normalizes_line_endings():
    assert message_digest("a\r\nb\n") == message_digest("a\nb")


def test_confirmed_send_is_durable_and_not_retryable(tmp_path: Path):
    transport = FakeTransport(confirm=True)
    with DeliveryLedger(tmp_path / "delivery.db") as ledger:
        executor = DeveloperThreadExecutor(
            transport=transport,
            delivery_ledger=ledger,
        )
        result = executor.execute(_plan())
        assert result.state.value == "SUCCEEDED"
        record = ledger.get("k1")
        assert record is not None
        assert record.state == DeliveryState.SENT_CONFIRMED
        with pytest.raises(ThreadExecutorError):
            executor.prepare(_plan())


def test_pre_send_failure_can_retry(tmp_path: Path):
    transport = FakeTransport(prepare_error=RuntimeError("composer missing"))
    with DeliveryLedger(tmp_path / "delivery.db") as ledger:
        executor = DeveloperThreadExecutor(
            transport=transport,
            delivery_ledger=ledger,
        )
        result = executor.execute(_plan())
        assert result.state.value == "FAILED"
        record = ledger.get("k1")
        assert record is not None
        assert record.state == DeliveryState.PRE_SEND_FAILED

        transport.prepare_error = None
        retry = executor.execute(_plan())
        assert retry.state.value == "SUCCEEDED"


def test_pre_commit_failure_can_retry(tmp_path: Path):
    transport = FakeTransport(
        commit_error=PreSendError("button unavailable before click")
    )
    with DeliveryLedger(tmp_path / "delivery.db") as ledger:
        executor = DeveloperThreadExecutor(
            transport=transport,
            delivery_ledger=ledger,
        )
        result = executor.execute(_plan())
        assert result.state.value == "FAILED"
        assert ledger.get("k1").state == DeliveryState.PRE_SEND_FAILED


def test_post_send_unknown_forbids_automatic_retry(tmp_path: Path):
    transport = FakeTransport(
        commit_error=RuntimeError("connection lost after click")
    )
    with DeliveryLedger(tmp_path / "delivery.db") as ledger:
        executor = DeveloperThreadExecutor(
            transport=transport,
            delivery_ledger=ledger,
        )
        result = executor.execute(_plan())
        assert result.state.value == "UNKNOWN"
        record = ledger.get("k1")
        assert record is not None
        assert record.state == DeliveryState.POST_SEND_UNKNOWN
        with pytest.raises(ThreadExecutorError):
            executor.prepare(_plan())


def test_unconfirmed_send_forbids_retry(tmp_path: Path):
    transport = FakeTransport(confirm=False)
    with DeliveryLedger(tmp_path / "delivery.db") as ledger:
        executor = DeveloperThreadExecutor(
            transport=transport,
            delivery_ledger=ledger,
        )
        result = executor.execute(_plan())
        assert result.state.value == "UNKNOWN"
        assert ledger.get("k1").state == DeliveryState.POST_SEND_UNKNOWN


def test_ui_generating_alone_does_not_prove_progress():
    evidence = FreshnessEvidence(
        ui_generating=True,
        elapsed_seconds_without_progress=1900,
        transport_connected=True,
    )
    assert classify_freshness(evidence) == FreshnessClass.STALE


def test_real_progress_wins_over_elapsed_time():
    evidence = FreshnessEvidence(
        ui_generating=False,
        repo_changed=True,
        elapsed_seconds_without_progress=9999,
    )
    assert classify_freshness(evidence) == FreshnessClass.PROGRESSING


def test_durable_long_running_process_prevents_stale():
    evidence = FreshnessEvidence(
        durable_job_running=True,
        elapsed_seconds_without_progress=9999,
    )
    assert (
        classify_freshness(evidence)
        == FreshnessClass.QUIET_BUT_CREDIBLE
    )


def test_takeover_requires_stale_release_and_remote_truth():
    allowed = assess_takeover(
        freshness=FreshnessClass.STALE,
        writer_state="STALE",
        remote_reconstructable=True,
        concurrent_process_credible=False,
        product_or_permission_boundary=False,
    )
    assert allowed.decision == TakeoverDecision.TAKEOVER_ALLOWED

    active = assess_takeover(
        freshness=FreshnessClass.STALE,
        writer_state="ACTIVE",
        remote_reconstructable=True,
        concurrent_process_credible=False,
        product_or_permission_boundary=False,
    )
    assert active.decision == TakeoverDecision.MARK_SUSPECT

    process = assess_takeover(
        freshness=FreshnessClass.STALE,
        writer_state="STALE",
        remote_reconstructable=True,
        concurrent_process_credible=True,
        product_or_permission_boundary=False,
    )
    assert process.decision == TakeoverDecision.KEEP_CURRENT_WRITER

    boundary = assess_takeover(
        freshness=FreshnessClass.STALE,
        writer_state="STALE",
        remote_reconstructable=True,
        concurrent_process_credible=False,
        product_or_permission_boundary=True,
    )
    assert boundary.decision == TakeoverDecision.BLOCKED


def test_writer_must_be_suspect_before_mark_stale(tmp_path: Path):
    path = tmp_path / "runtime.db"
    with WriterLeaseStore(path) as leases:
        leases.acquire(
            repo="owner/repo",
            branch="main",
            scope="R6",
            holder="old",
        )
        with pytest.raises(LeaseConflict):
            leases.mark_stale(
                repo="owner/repo",
                branch="main",
                scope="R6",
                holder="old",
            )
        assert leases.reconcile_restart() == 1
        stale = leases.mark_stale(
            repo="owner/repo",
            branch="main",
            scope="R6",
            holder="old",
        )
        assert stale.state == "STALE"
        replacement = leases.acquire(
            repo="owner/repo",
            branch="main",
            scope="R6",
            holder="new",
        )
        assert replacement.state == "ACTIVE"
        assert replacement.holder == "new"


def test_playwright_transport_is_not_live_certified():
    transport = PlaywrightCdpTransport(
        cdp_endpoint="http://127.0.0.1:9222",
        selectors=PlaywrightSelectors(
            conversation_root="main",
            composer="textarea",
            send_button="button",
            assistant_messages="[data-message-author-role=assistant]",
            user_messages="[data-message-author-role=user]",
        ),
        thread_url_for={"thread-1": "https://example.invalid/thread-1"},
    )
    probe = transport.capability_probe()
    assert probe["live_certified"] is False

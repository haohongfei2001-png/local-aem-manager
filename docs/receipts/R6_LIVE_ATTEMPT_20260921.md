# R6 Live Local Certification Attempt — 2026-09-21

Disposition: **BLOCKED_LIVE_CERTIFICATION** (owner authorization required for the
transport fix). R7 remains LOCKED.

This receipt records a real attempt to run the certified R6 local harness
(`local-aem-r6-cert`) against the owner's current Mac/Chrome session. No mock,
CI, or synthetic browser evidence is used to substitute for the live run.

## 1. Environment

| Item | Value |
| --- | --- |
| Repository HEAD at run time | `0deb86e0a4055f4a932a6a725e8ed9c029f5697c` (== `origin/main`, verified with `git ls-remote`) |
| Certified harness runtime | `6dd4f16e10861a3a9a730473819e39cb232b02ec` (`docs/receipts/R6_LOCAL_HARNESS.md`) |
| Harness command | `local-aem-r6-cert --config <local>/r6-cert.yaml` |
| Python / Playwright | CPython 3.12.14 / playwright 1.63.0 (browser extra) |
| Chrome | 153.0.8010.48 (stable), already running, intended logged-in ChatGPT account |
| CDP endpoint | `http://127.0.0.1:9222`, launched with `--remote-debugging-address=127.0.0.1` (local-only) |
| Chrome profile | isolated certification profile, `user-data-dir=<home>/.config/local-aem-manager/chrome-r6-cert-profile` |
| Local config | `<home>/.config/local-aem-manager/r6-cert.yaml` (outside the repository, never committed, no credentials) |

CDP reachability was confirmed (`/json/version` returns the browser WebSocket
endpoint) and every configured thread page was open in that same Chrome session
before the run.

## 2. Live DOM confirmation (selectors are observations, not guesses)

Confirmed against the live conversation page on 2026-09-21:

| Config key | Confirmed selector | Live evidence |
| --- | --- | --- |
| `conversation_root` | `#thread` | count 1 on conversation pages |
| `composer` | `#prompt-textarea[contenteditable="true"]` | count 1, ProseMirror node, editable |
| `send_button` | `#composer-submit-button` | idle state: `data-testid="send-button"`, `aria-label="发送提示词"` |
| `assistant_messages` | `[data-message-author-role="assistant"]` | count equals assistant replies |
| `user_messages` | `[data-message-author-role="user"]` | count equals user sends; `inner_text` equals the sent text with no label prefix |
| `generating_indicator` | `[data-testid="stop-button"]` | visible exactly while a response streams |
| `message_id_attribute` | `data-message-id` | present on message elements (8 ids on a 4-user/4-assistant thread) |

Confirmed message text contract: the `[data-message-author-role="user"]`
`inner_text` for a sent message equals the sent text after
`message_text.normalize_message_text`, so the harness digest comparison is
usable on this build.

## 3. Thread mapping (observe-only developer threads)

Conversation ids are truncated; full URLs stay in the local config only.

| Config key | Project id | Thread title | Conversation | Observed state |
| --- | --- | --- | --- | --- |
| `paia` | PAIA | PAIA开发1.2 (project `g-p-6aaf5170…`) | `6ab0f948…` | GENERATING |
| `pjsdas` | PJSDAS | 查看开发情况 (project `g-p-6aaf8274…`) | `6ab1029f…` | IDLE |
| `hcl` | HCL | HCL1.1 (project `g-p-6aafd5cb…`) | `6aafd5d9…` | GENERATING |
| `certification` | R6_CERTIFICATION | dedicated harmless thread | `6ab13f1e…` | IDLE |

No message was sent to PAIA, PJSDAS, or HCL. They were opened and observed only.

The dedicated certification thread was created for this certification and
seeded once with a harmless bootstrap message
(`LOCAL_AEM_R6_CERTIFICATION bootstrap … reply with ACK`) so that a stable
`/c/<id>` URL and at least one real assistant output existed before the harness
ran. That bootstrap is not one of the three harness probes.

## 4. Harness result (two independent runs, identical outcome)

```
capability.available              = true   (playwright-cdp, thread_count 4)
observations[paia/pjsdas/hcl/cert] = transport_connected true, ui_state as in §3
refresh_rebind                    = true
controlled_stale_takeover         = true
normal_send                       = PRE_SEND_FAILED   "composer is not visible"
pre_send_retry.fault              = PRE_SEND_FAILED   "R6 certification injected a fault before composer commit"
pre_send_retry.retry              = PRE_SEND_FAILED   "composer is not visible"
post_send_unknown                 = PRE_SEND_FAILED   "composer is not visible"
post_send_retry_blocked           = false
passed                            = false
```

Both runs ended ~2 s after start. **No harness send reached a real send click**;
the only messages in the certification thread are the bootstrap message and the
manual diagnostic messages described in §6.

### Behaviours demonstrated live

1. CDP attach/rebind — yes (`refresh_rebind` true; every observation reports `transport_connected`).
2. Configured project id → correct developer thread mapping — yes.
3. Latest assistant output digest and generating/idle state per thread — yes.
4. Normal send exactly once — **not exercised** (failed closed before send).
5. Pre-send failure followed by a permitted retry — **not exercised** (the injected pre-send fault was recorded, but the retry could not prepare).
6. Post-send unknown followed by no duplicate — **not exercised**.
7. Survive tab refresh/rebind — yes (`refresh_thread` + re-observe).
8. Ghost-active UI vs durable progress — the harness pipeline reports UI state as a sensor only; the freshness/takeover classification inside the harness run is driven by configured evidence, so this row is only partially covered by live data.
9. Controlled stale writer takeover — yes (`controlled_stale_takeover` true).
10. One-writer invariant — yes (lease store refuses a second ACTIVE holder until the previous holder is STALE/RELEASED/BLOCKED).

## 5. Blocker 1 — deterministic post-refresh readiness race

`PlaywrightCdpTransport.refresh_thread()` performs
`page.reload(wait_until="domcontentloaded")` and the harness immediately
continues to `prepare_message()`, whose first check is composer visibility.

Measured on the live certification thread immediately after that reload:

```
domcontentloaded returned at +0.64 s
#prompt-textarea[contenteditable="true"] visible at +2.37 s
post-refresh observation: composer_available true, send_button_available false
```

The ~2 s hydration gap is longer than the harness's zero wait, so every probe
fails closed with `PRE_SEND_FAILED` ("composer is not visible") and no send is
attempted. Reproduced in two consecutive runs.

Required fix: after refresh/rebind, wait for the composer to be visible and
editable (and for a send-capable submit control) before `prepare_message`.

## 6. Blocker 2 — commit-by-click is not a send while the thread is generating

On this ChatGPT build the submit control is a single element whose identity
flips with thread state:

```
idle thread, text present : id=composer-submit-button  data-testid=send-button   aria-label=发送提示词
streaming thread          : id=composer-submit-button  data-testid=stop-button   aria-label=停止回答
```

Two live experiments on the certification thread (manual, not part of the
harness):

* streaming + text in composer + **click** the submit control → user message
  count did not increase; the draft stayed in the composer; the response was not
  the intended message delivery.
* streaming + text in composer + **press Enter** → user message count did not
  increase; the draft stayed in the composer.

Consequence: even with blocker 1 fixed, the harness issues probes 2 and 3 within
~1–2 s of the preceding probe's confirmed send, i.e. while the assistant is
still streaming. Their commit click would land on the stop control rather than a
send control, so `pre_send_retry.retry` cannot reach `SENT_CONFIRMED`, and probe
3's "real send click" would not actually deliver a message. The harness would
still fail closed, but with misleading intermediate evidence.

Required fix (owner decision, transport level): only commit when the submit
control is genuinely send-capable (for example `data-testid="send-button"`), or
wait for the thread to leave GENERATING before commit, and treat a stop-state
control as `PRE_SEND_FAILED` instead of a send attempt.

Both fixes are inside the previously certified harness runtime, so they need a
new authorized R6 change (PR + CI + a fresh live run); this receipt does not
change R6 code.

## 7. Environment incident (recorded for completeness)

To obtain a usable local CDP channel, Chrome was launched once against the
legacy `AI-Supervisor/chrome-profile` using the same parameters as the legacy
`scripts/ensure_chrome.sh` (no supervisor or worker was started, and no v3
runtime state file was modified). In that launch Chrome could not use the macOS
keychain encryption key, so it dropped that profile's cookie jar, including its
ChatGPT session; that profile is now logged out. Certification then moved to the
isolated certification profile listed in §1.

Related observation: for Chrome launched from this shell context, cookies do not
survive a browser restart, so the certification must run inside a single
continuous Chrome session. Firefox-free, local-only CDP was used throughout; no
browser permission was widened and no account was changed.

## 8. What is needed to unblock R6

1. Owner authorization for the two transport fixes in §5 and §6.
2. Implement the fixes, re-certify the harness with exact-main CI.
3. Re-run `local-aem-r6-cert` against the owner's live Chrome session and write
   a passing receipt before R6 can become COMPLETE and R7 READY.

# AI Wrapper Migration Report — Onlenco

> **Phase:** Prompt 12A. Migrating direct provider calls onto
> `ai_usage.services.ai_client`. Migration is **incremental and tested** —
> this report tracks what is migrated, what remains, and why.

## 1. Wrapper

`ai_usage/services/ai_client.py` is the single egress. Public methods:
`chat`, `complete_text`, `stream_chat`, `transcribe_audio`,
`synthesize_speech`, `explain`, `generate_content`, `roleplay`,
`generic_call`, plus `log_realtime_session_start`. Every method logs one
`AIUsageLog` (success/failed), prices via `AIModelPricing`, scrubs the API
key from errors, and returns the provider response unchanged.

## 2. Migrated in this phase (Batch B — clean, low-risk wins)

| Feature | File | Before | After |
|---|---|---|---|
| motivation | `motivation/services/ai_message_generator.py` | `requests.post(/chat/completions)` + inline `core.log_usage` | `ai_client.chat(..., feature=motivation, user=user)`; inline metering removed |
| library | `library/services/summarizer.py` | `requests.post(/chat/completions)` | `ai_client.chat(..., feature=library, response_format=json_object)` |
| vocabulary (dictionary) | `dictionary/services.py` | `requests.post(/chat/completions)` + tools + inline `core.log_usage` | `ai_client.chat(..., feature=vocabulary, tools=…)`; inline metering removed |

All three preserve existing behaviour (heuristic/template fallback on any
failure). Their existing test suites pass unchanged because the tests patch
`requests.post` on the shared `requests` module, which the wrapper also uses.

## 3. Already abstracted — wrap at the funnel (no per-site change needed)

These route through `factory/services/llm_router._post_chat`; metering them
is a single future change at that funnel (Batch A-funnel), which transitively
covers `ai_engine` providers, `quality_router`, `question_factory`, and the
`ai_training` evaluator:

* `ai_engine/services/providers.py` (`_llm_chat`, `local_llm`, `openai`)
* `factory/services/quality_router.py`
* `question_factory/services/ai_generator.py`
* `ai_training/services/evaluator.py`

## 4. Staged (not yet migrated) — with reasons

| Feature | File | Reason staged |
|---|---|---|
| ai_tutor text + stream | `tutor/services/_chat.py` | High-traffic, has streaming + a large test suite (`test_chat_stream*`, `test_api_chat`). Migrate via `ai_client.chat` / `ai_client.stream_chat` next, with its tests run each step. |
| challenge (explanation/roleplay/end-advice) | `tutor/services/challenge_tutor_service.py` | Uses `urllib` (not `requests`) + `ai_usage_guard` quotas; migrate to `ai_client.roleplay`/`chat` and reconcile with the guard. |
| placement written | `placement/services/_assessor.py` | Function-calling (`tools`); migrate via `ai_client.chat(extra_payload=tools)` (pattern proven on dictionary). |
| placement speaking (STT) | `placement/services/stt.py` | Migrate to `ai_client.transcribe_audio` (pattern implemented + tested in `ai_usage`). |
| tutor TTS | `tutor/services/tts.py` | Migrate to `ai_client.synthesize_speech`. |
| realtime voice | `tutor/services/realtime_session.py`, `tutor/api/views.py` (`voice_call_session`, `voice_call_sdp_relay`) | Server only mints/relays; no token usage visible. Use `ai_client.log_realtime_session_start` at authorisation and keep minute accounting in `subscriptions.session_service`. |
| lesson assistant / error analysis | `learning_core/services/error_analyzer.py` | Migrate via `ai_client.chat`; keep heuristic fallback. |
| content generation | `learning_core/services/exercise_generator.py`, `exams/services/ai_question_generator.py`, `library/services/extractors.py` | Role=`teacher`/`system`; migrate via `ai_client.generate_content`. |
| media generation | `courses/services/onlenco_media_clients.py`, `daily_learning/.../generate_a0_audio.py` | Image + TTS with **hardcoded** pricing; migrating also moves pricing into `AIModelPricing`. Offline batch — lower urgency. |

## 5. Remaining direct calls

All sites in §3 and §4 still call the provider directly. §3 are covered by a
single funnel change; §4 are scheduled per the table above. The
pre-existing `core/services/ai_usage.py` logger remains in place for
un-migrated sites and is retired in a later phase once §4 completes
(tracked as risk **R4** in the audit report).

## 6. Acceptance status

Criterion #18 ("no direct OpenAI calls remain outside the wrapper, or
exceptions documented") is met in the **documented-exception** form: 3 sites
migrated as a proven template; the remainder are enumerated here with reasons
and a concrete per-site method mapping.

---

# Prompt 12A.1 — Migration Completion

## Call sites migrated in 12A.1

| Group | Feature(s) | Files | Wrapper method |
|---|---|---|---|
| A — Challenge | challenge_explanation / roleplay / end_advice | `tutor/services/challenge_tutor_service.py` (`_call_llm`) | `ai_client.chat` |
| B — Tutor | ai_tutor (text + stream) | `tutor/services/_chat.py` (`chat`, `chat_stream_tokens`) | `ai_client.chat`, `ai_client.stream_chat` |
| C — Placement | placement_written, placement_speaking | `placement/services/_assessor.py`, `placement/services/stt.py` | `ai_client.chat` (tools), `ai_client.transcribe_audio` |
| D — Audio/Realtime | tts, ai_tutor (realtime) | `tutor/services/tts.py`, `tutor/api/views.py` (`voice_call_session`) | `ai_client.synthesize_speech`, `ai_client.log_realtime_session_start` |
| E — Content gen | lesson_assistant, content_generation | `learning_core/services/error_analyzer.py`, `learning_core/services/exercise_generator.py`, `exams/services/ai_question_generator.py`, `library/services/extractors.py` | `ai_client.chat` |
| E — Media | media_generation | `courses/services/onlenco_media_clients.py` (image+audio), `daily_learning/.../generate_a0_audio.py` | `ai_client.generate_image`, `ai_client.synthesize_speech` |
| F — Funnel | content_generation (system) | `factory/services/llm_router.py` (`chat`) | self-meters via `usage_logger` |

Migrated in 12A (prior): motivation, library/summarizer, dictionary.

## Features now fully tracked

ai_tutor (text/stream/realtime-session), challenge_explanation, challenge_roleplay,
challenge_end_advice, placement_written, placement_speaking, lesson_assistant,
content_generation, media_generation, tts, stt, library, motivation, vocabulary.

## Features partially tracked

* **realtime ai_tutor** — session START is logged (request count + reconcile flag);
  token cost is server-invisible (billed browser↔OpenAI). Minutes are charged on
  hang-up via `subscriptions.session_service.end_session`.
* **media image** — request + model logged; **per-image USD cost is not modelled**
  in `AIModelPricing` yet, so cost logs as 0 (the historical hardcoded estimate is
  preserved on `GenerationResult.cost_estimate_usd` for backward-compat).

## Remaining direct calls (allowed, documented)

| File | Why allowed |
|---|---|
| `ai_usage/services/ai_client.py` | The wrapper itself (the single egress). |
| `factory/services/llm_router.py` | Local-first router transport; **self-logs** usage at the funnel (`chat()`), covering ai_engine providers + quality_router + question_factory + ai_training. |
| `tutor/services/realtime_session.py` (`request_ephemeral_session`) | Realtime control-plane: mints an ephemeral key. No token usage; session logged separately. |
| `tutor/api/views.py` (`voice_call_sdp_relay`) | WebRTC SDP relay using the browser's ephemeral token. Pure handshake passthrough — no AI usage. |

Enforced by `ai_usage/tests/test_no_direct_calls.py` (fails on any new bypass).

## AI Tutor Plan Minutes Mismatch

**Business requirement:** base 5 / upgrades 10 / **20** / 30 minutes per day.
**What exists in the DB** (`subscriptions/migrations/0002_seed_initial_plans.py`):
plans seeded at **5, 5, 10, 15, 30** `ai_tutor_daily_minutes` (a free + base 5,
then 10 / **15** / 30). So the **15-minute** upgrade tier does not match the
requested **20-minute** tier.

* **Currently enforced:** whatever `SubscriptionPlan.ai_tutor_daily_minutes`
  holds per active subscription — i.e. **15**, not 20, for that tier. `limit_service`
  reads the plan value verbatim (admin-editable), so it reflects reality.
* **What the UI exposes:** the public pricing page renders plans from the DB, so
  it currently shows 15.
* **Decision required (business owner):** confirm whether the upgrade tier should
  be **15 or 20** minutes. This is a pricing/packaging decision, intentionally
  **not** changed here.
  * If **20** is correct: update the existing plan's `ai_tutor_daily_minutes`
    (admin edit or a new data migration) — do **not** delete the plan (existing
    subscribers reference it; changing the field value is safe and immediate).
  * If **15** is correct: update the business spec to say 5 / 10 / 15 / 30.
* **TODO flag:** `# TODO(business): confirm 15 vs 20-minute upgrade tier` — tracked
  here; tests assert the *actual* current values (5/10/15/30), not the aspirational ones.

No existing subscriber is broken: minute allowance is read live from the plan row.

## Legacy AI Usage Logger Retirement Plan

`core/services/ai_usage.py` + `core.models.AIUsageLog` (the lightweight
per-feature daily-count logger).

* **Where still used:** after 12A.1, the migrated services no longer call it
  (the inline `core.services.ai_usage.log_usage` calls were removed in each
  migrated file). It is still referenced by:
  * `core/services/ai_usage.is_within_limit(...)` — the legacy per-feature daily
    *request* cap, still consulted by `tutor/services/_chat._is_within_limit` and
    `learning_core/services/error_analyzer` (a separate concern from cost metering).
  * its own tests (`core/tests/test_ai_usage.py`) and `notifications` tests.
* **Duplication:** none for cost — migrated sites now log only to
  `ai_usage.AIUsageLog`. The legacy table no longer receives writes from migrated
  paths, so the two tables do not double-count.
* **Status now:** **deprecated for writing** from migrated call sites. The
  `log_usage` function remains (for any un-migrated/legacy caller + its tests) but
  is no longer invoked by the AI egress paths.
* **Retirement strategy (next phase):**
  1. Move the daily-request-cap logic (`is_within_limit`) into `ai_usage`
     (a small `request_limit_service`) reading `ai_usage.AIUsageLog`.
  2. Repoint `_chat._is_within_limit` and `error_analyzer` to it.
  3. Mark `core.services.ai_usage.log_usage` `@deprecated`; keep as a no-op-safe shim for one release.
  4. Optional data migration to backfill historical `core.AIUsageLog` rows into
     `ai_usage.AIUsageLog` if historical continuity is needed (usually not — keep
     the old table read-only for audit).
  5. Remove after a deprecation window once no caller/test references remain.
* **Tests needed before removal:** parity test (request-cap behaviour identical
  after repoint), and a grep test that `core.services.ai_usage.log_usage` has no
  non-test callers.
* **Risk if left:** low — it is inert for cost; only the request-cap helper is live.

# AI Calls Audit Report — Onlenco

> **Phase:** Prompt 12A — AI Daily Usage Tracking & Cost Control (FinOps)
> **Scope:** Audit only. No call was replaced as part of producing this report.
> **Method:** Repo‑wide `git grep` for provider endpoints + `Authorization: Bearer` headers,
> cross‑checked by a 6‑way parallel reader sweep (one reader per app group).
> **Date:** 2026‑05‑31

---

## 1. Executive Summary

Onlenco does **not** use the `openai` Python SDK. Every paid AI call is a **raw
`requests.post` (or `urllib`) to an OpenAI‑compatible HTTP endpoint**, built from
two settings: `settings.AI_API_BASE` (default `https://api.openai.com/v1`) and
`settings.AI_API_KEY`. The endpoints in use are:

| Endpoint | Purpose | Token usage in response? | Audio duration in response? |
|---|---|---|---|
| `/chat/completions` | text generation, function‑calling, streaming | **yes** (`usage.{prompt,completion,total}_tokens`) | n/a |
| `/audio/speech` | TTS | no | no (must be derived from text length / output bytes) |
| `/audio/transcriptions` | STT (Whisper) | no | **yes** (`duration` seconds) |
| `/images/generations` | image content generation | no | n/a |
| `/realtime/client_secrets` | mint ephemeral key for live voice tutor | no (usage happens browser↔OpenAI) | no — duration comes from session lifecycle |
| `/realtime/calls` | SDP relay for the WebRTC voice session | no | no |

**Two pieces of infrastructure already exist and must be respected (not duplicated):**

1. **`core/services/ai_usage.py` + `core.models.AIUsageLog`** — a *lightweight*
   per‑user/feature daily‑count logger. Several call sites already call its
   `log_usage(...)` / `is_within_limit(...)`. It tracks token counts and a flat
   `estimated_cost` but has **no pricing table, no per‑model cost, no audio
   minutes, no organization/role dimension, no daily summary**. The new
   `ai_usage` app **supersedes** it functionally; the old module is kept intact
   for backward compatibility (its tests must stay green) and is bridged, not
   deleted, in this phase.

2. **`subscriptions` app — a full AI‑Tutor minutes system already exists:**
   `SubscriptionPlan.ai_tutor_daily_minutes` (admin‑editable; seeded 5/10/15/30),
   `UserSubscription`, `FreeTrialUsage` (one‑shot 5‑minute trial, in seconds),
   `AITutorSession` (DB session lifecycle with `duration_seconds`/`consumed_seconds`),
   `UserDailyQuota` (per user/day seconds), and services
   `subscriptions.services.quota_service` + `session_service`. **The spec's
   `StudentDailyAILimit` / `limit_service` is therefore implemented as a thin
   adapter / daily projection over this system — not a reimplementation** (the
   spec explicitly says "read from subscription system if it exists").

**Counts:** 22 distinct provider egress + relay sites were catalogued (19 direct
HTTP egress points + 3 indirect view wrappers). Of the direct egress points,
**1 is the shared abstraction** (`factory/services/llm_router._post_chat`) through
which the `ai_engine` model‑router pipeline funnels; the other ~18 are
feature‑specific raw calls that bypass the abstraction.

**Key risk:** AI Tutor *minutes* cannot be derived from tokens — the realtime
voice session's usage is never seen by the server. Minute enforcement must stay
attached to the **session lifecycle** (`AITutorSession` duration), which is
already wired. Token/cost metering and minute enforcement are **two separate
axes** and the wrapper must treat them as such.

---

## 2. Direct AI Calls Found

Legend — **Repl.**: `now` = wrap in this phase · `later` = wrap after core lands ·
`leave` = leave temporarily (with reason). **Min?**: impacts student daily AI‑Tutor minutes.

| # | File:line | Symbol | Feature | Endpoint | Model | Stream | Tokens? | Audio dur? | Min? | Admin/content? | Risk | Repl. |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 1 | `factory/services/llm_router.py:62` | `_post_chat` | (shared) ai_tutor/content | `/chat/completions` | `AI_MODEL` | no | yes | n/a | — | — | **high** | **now** (the wrap point) |
| 2 | `ai_engine/services/providers.py:351` | `_llm_chat` | via #1 | (delegates) | — | no | yes | n/a | — | — | med | leave (routes through #1) |
| 3 | `ai_engine/services/providers.py:422` | `local_llm` | via #1 | (delegates) | local/`AI_MODEL` | no | yes | n/a | — | — | med | leave (routes through #1) |
| 4 | `ai_engine/services/providers.py:539` | `openai` | via #1 | (delegates) | `AI_MODEL` | no | yes | n/a | — | — | med | leave (routes through #1) |
| 5 | `factory/services/quality_router.py:67` | `_ai_validate` | content_generation | via #1 | `AI_MODEL` | no | yes | n/a | — | ✓ | med | leave (routes through #1) |
| 6 | `tutor/services/_chat.py:355` | `chat` | ai_tutor | `/chat/completions` | `AI_MODEL` | no | yes | no | ✓* | — | **high** | **now** |
| 7 | `tutor/services/_chat.py:438` | `chat_stream_tokens` | ai_tutor | `/chat/completions` | `AI_MODEL` | **yes** | yes (not extracted from stream) | no | ✓* | — | **high** | **now** |
| 8 | `tutor/services/tts.py:48` | `synthesize` | ai_tutor (TTS) | `/audio/speech` | `AI_TTS_MODEL` | no | no | no | — | — | med | **now** |
| 9 | `tutor/services/realtime_session.py:317` | `request_ephemeral_session` | ai_tutor (speaking) | `/realtime/client_secrets` | `AI_REALTIME_MODEL` | no | no | no | **✓** | — | **high** | **now** (log session start; minutes via lifecycle) |
| 10 | `tutor/services/challenge_tutor_service.py:64` | `_call_llm` | challenge_explanation / roleplay / end_advice | `/chat/completions` (urllib) | `TUTOR_TEXT_MODEL` | no | yes | n/a | — | — | **high** | **now** |
| 11 | `tutor/api/views.py:272` | `voice_transcribe` | placement_speaking (indirect) | →`placement.stt` | `AI_STT_MODEL` | no | no | yes | ✓ | — | high | covered by #14 |
| 12 | `tutor/api/views.py:782` | `voice_tts` | ai_tutor (indirect) | →`tutor.tts` | `AI_TTS_MODEL` | no | no | no | — | — | med | covered by #8 |
| 13 | `tutor/api/views.py:907` | `voice_call_session` | ai_tutor (indirect) | →`realtime_session` | `AI_REALTIME_MODEL` | no | no | no | **✓** | — | high | covered by #9 |
| 14 | `tutor/api/views.py:1144` | `voice_call_sdp_relay` | ai_tutor (speaking relay) | `/realtime/calls` | `AI_REALTIME_MODEL` | no | no | no | ✓ | — | high | later (relay only; no usage) |
| 15 | `placement/services/_assessor.py:201` | `assess` | placement_written | `/chat/completions` | `AI_MODEL` | no | yes | n/a | — | — | med | **now** |
| 16 | `placement/services/stt.py:39` | `transcribe` | placement_speaking | `/audio/transcriptions` | `AI_STT_MODEL` | no | no | **yes** | ✓ | — | **high** | **now** |
| 17 | `learning_core/services/error_analyzer.py:103` | `_call_ai` | lesson_assistant / error analysis | `/chat/completions` | `AI_MODEL` | no | yes | n/a | — | — | med | **now** |
| 18 | `learning_core/services/exercise_generator.py:219` | `_call_ai` | content_generation | `/chat/completions` | `AI_MODEL` | no | yes | n/a | — | ✓ | med | now |
| 19 | `question_factory/services/ai_generator.py:104` | `generate_for_blueprint` | content_generation | via #1 | `AI_MODEL` | no | yes | n/a | — | ✓ | med | leave (routes through #1) |
| 20 | `motivation/services/ai_message_generator.py:52` | `_call_llm` | motivation | `/chat/completions` | `AI_MODEL` | no | yes (not extracted) | n/a | — | — | low | **now** |
| 21 | `library/services/summarizer.py:73` | `_call_ai` | library | `/chat/completions` | `AI_MODEL` | no | yes (not extracted) | n/a | — | — | low | now |
| 22 | `library/services/extractors.py:149` | `_call_ai` | library | `/chat/completions` | `AI_MODEL` | no | yes (not extracted) | n/a | — | ✓ | med | now |
| 23 | `dictionary/services.py:100` | `ai_lookup` | vocabulary (dictionary) | `/chat/completions` | `AI_MODEL` | no | yes (not extracted) | n/a | — | — | low | now |
| 24 | `exams/services/ai_question_generator.py:63` | `_call_llm` | content_generation | `/chat/completions` | `AI_MODEL` | no | yes (not extracted) | n/a | — | ✓ | med | now |
| 25 | `courses/services/onlenco_media_clients.py:80` | `generate_image` | content_generation | `/images/generations` | `gpt-image-1-mini` | no | no | n/a | — | ✓ | **high** | now (hardcoded $ today) |
| 26 | `courses/services/onlenco_media_clients.py:125` | `generate_audio` | content_generation | `/audio/speech` | `tts-1` | no | no | no | — | ✓ | **high** | now (hardcoded $ today) |
| 27 | `daily_learning/management/commands/generate_a0_audio.py:72` | `_synth_bytes` | content_generation | `/audio/speech` | `tts-1` | no | no | no | — | ✓ | high | later (offline batch) |
| 28 | `ai_training/services/evaluator.py:180` | `evaluate_build` | content_generation (eval) | via #1 (router) | router | no | partial | n/a | — | ✓ | med | leave (routes through #1) |

\* `_chat.py` is the **text** tutor chat; it counts toward the legacy per‑feature
daily *request* cap, not the *minutes* quota. Minutes belong to the **voice**
path (#9/#13/#14) via `AITutorSession`.

> `core/services/reading_prep.py` references `/audio/speech` only in comments; the
> actual synthesis is delegated to the TTS helpers above, so it is **not** a
> separate egress point.

---

## 3. Calls by Feature

| Feature (12A taxonomy) | Call sites |
|---|---|
| `ai_tutor` (text) | #6, #7 |
| `ai_tutor` (speaking / realtime) | #9, #13, #14 (relay) |
| `ai_tutor` (TTS) | #8, #12 |
| `placement_written` | #15 |
| `placement_speaking` (STT) | #16, #11 |
| `lesson_assistant` | #17 |
| `vocabulary` | #23 |
| `library` | #21, #22 |
| `motivation` | #20 |
| `content_generation` (teacher/admin/system) | #5, #18, #19, #24, #25, #26, #27, #28 |
| `challenge_explanation` / `challenge_roleplay` / `challenge_end_advice` | #10 |
| shared abstraction (multi‑feature) | #1 (+#2‑#4 delegate to it) |

---

## 4. Calls by Risk Level

**High** — student‑facing, money‑burning, or currently mis‑metered:
#1 (funnel), #6, #7 (tutor text), #9/#13/#14 (realtime minutes), #10 (challenge),
#16 (STT), #25, #26 (image/audio with **hardcoded** pricing today).

**Medium** — metered‑able, lower volume or admin/content:
#2‑#5, #8, #11, #12, #15, #17, #18, #19, #22, #24, #27, #28.

**Low** — small payloads, easy wins:
#20 (motivation), #21 (library summary), #23 (dictionary).

---

## 5. Streaming Calls

Only **one** true streaming call: **#7 `tutor/services/_chat.py:chat_stream_tokens`**
(SSE, `stream=True`, `iter_lines`). Token usage is *available in principle* but the
current code never extracts the trailing `usage` chunk. The wrapper's
`stream_chat(...)` must: yield tokens unchanged, accumulate the assembled text,
and read the final `usage` frame (request OpenAI's `stream_options={"include_usage": true}`)
to log tokens after the stream closes — logging a `success` row at end‑of‑stream
and a `failed` row if the stream errors before first byte.

---

## 6. Audio / Speaking Calls

| Site | Kind | Duration source | Minute impact |
|---|---|---|---|
| #16 placement STT | `/audio/transcriptions` | response `duration` (sec) — **authoritative** | counts to speaking |
| #9/#13 realtime | `/realtime/client_secrets` | **session lifecycle** (`AITutorSession.duration_seconds` on hang‑up) — *not* the API response | **drives AI‑Tutor minutes** |
| #8/#12/#26/#27 TTS | `/audio/speech` | none in response → estimate from input chars or output bytes | none (output audio, not student speaking) |

**Design rule confirmed:** AI‑Tutor minutes = **actual session duration**, charged
by `subscriptions.session_service.end_session(actual_seconds=…)`, never tokens.

---

## 7. Teacher/Admin Content Generation Calls

Sites flagged `is_admin_teacher_content_gen`: #5, #18, #19, #24, #25, #26, #27, #28.
These should log with `role=teacher`/`admin`/`system` and `feature=content_generation`
so the dashboard can separate **platform content cost** from **student usage cost**.
None of these consume student minutes.

---

## 8. Calls That Need Daily Minute Enforcement

Only the **speaking / voice** path:
- #9 `request_ephemeral_session` (gate **before** minting the key)
- #13 `voice_call_session` (the view that calls #9 — already opens an `AITutorSession`)
- #14 SDP relay (no separate gate; the session is already authorized)
- #16 placement STT counts speaking seconds but is part of the **placement test**, which is exempt from the paid daily tutor quota (one‑time onboarding) — log usage, do **not** decrement tutor minutes.

Text tutor chat (#6/#7) and all other features are gated by *request/token* caps,
not *minutes*.

---

## 9. Replacement Plan

**Wrap point strategy — two layers:**

1. **The shared funnel (#1).** Add token+cost logging *inside*
   `factory/services/llm_router._post_chat` (or have it delegate to
   `ai_usage.services.ai_client`). This instantly meters #2‑#5, #19, #28 with one
   change — they all flow through it. Feature attribution is passed down via a
   `context`/`meta` arg.

2. **The bypass calls (raw `requests.post`).** Migrate each to
   `ai_usage.services.ai_client.*` incrementally, in risk order:
   - **Batch A (now, high‑value):** #6, #7 (tutor text+stream), #10 (challenge),
     #15 (placement written), #16 (placement STT), #9 (realtime start log).
   - **Batch B (now, easy wins):** #20 (motivation), #21 (library summary),
     #23 (dictionary), #17 (error analyzer), #8 (tutor TTS).
   - **Batch C (later):** #18, #22, #24 (content gen), #25, #26 (media — also
     removes hardcoded pricing), #27 (offline batch command), #14 (relay — log only).

3. **Leave temporarily (documented):** #2‑#5, #19, #28 stay as‑is because they
   already route through #1; wrapping #1 covers them. The low‑level relay #14
   carries no usable usage signal (pure SDP passthrough) and is logged as a
   session event only.

**Pre‑existing logger bridge:** `core/services/ai_usage.log_usage` is kept; new
wrapper writes to `ai_usage.AIUsageLog`. To avoid double counting, migrated sites
drop their inline `core.services.ai_usage.log_usage` call (the wrapper logs once).
Un‑migrated sites keep theirs until migrated.

---

## 10. Remaining Risks

| ID | Risk | Severity | Mitigation |
|---|---|---|---|
| R1 | Realtime token cost invisible server‑side; only minutes are known | P1 | Price realtime per‑minute in `AIModelPricing.audio_*`; reconcile against OpenAI dashboard monthly |
| R2 | Streaming token usage requires `stream_options.include_usage` | P2 | Wrapper sets it; fall back to `len`-based estimate if absent |
| R3 | Hardcoded image/TTS pricing in `onlenco_media_clients.py` | P2 | Replaced by `AIModelPricing` rows on migration (Batch C) |
| R4 | Two parallel usage tables (`core.AIUsageLog` + `ai_usage.AIUsageLog`) during transition | P2 | Migrate incrementally; only one logs per migrated site; reconcile + retire `core` logger in a later phase |
| R5 | `request_id` not emitted by all endpoints → dedup relies on caller‑supplied id | P3 | Wrapper synthesizes a uuid when provider gives none; dedup only when id present |
| R6 | Offline management commands run outside request scope (no `user`) | P3 | Log with `role=system`, `user=None` |

---

## Prompt 12A.1 Re-Audit

Re-ran the direct-call sweep (`requests.post` / `urllib` / `httpx` + provider
endpoints). The sweep is now enforced by an automated guardrail test:
`ai_usage/tests/test_no_direct_calls.py::test_no_direct_ai_provider_calls_outside_wrapper`.

**Result: 0 un-migrated AI egress points remain.** Every chat / audio / image
call routes through `ai_usage.services.ai_client`. Three files are documented
allowed exceptions (control-plane / self-logging transport).

| ID | File | Function | Feature | Provider | Model | Current Status | Migration Target | Risk | Action |
|---|---|---|---|---|---|---|---|---|---|
| AI-001 | `tutor/services/_chat.py` | `chat` | ai_tutor | openai | AI_MODEL | migrated | `ai_client.chat` | high | done |
| AI-002 | `tutor/services/_chat.py` | `chat_stream_tokens` | ai_tutor | openai | AI_MODEL | migrated | `ai_client.stream_chat` | high | done |
| AI-003 | `tutor/services/challenge_tutor_service.py` | `_call_llm` | challenge_explanation/roleplay/end_advice | openai | TUTOR_TEXT_MODEL | migrated | `ai_client.chat` | high | done |
| AI-004 | `placement/services/_assessor.py` | `assess` | placement_written | openai | AI_MODEL | migrated | `ai_client.chat` (tools) | medium | done |
| AI-005 | `placement/services/stt.py` | `transcribe` | placement_speaking | openai | AI_STT_MODEL | migrated | `ai_client.transcribe_audio` | high | done |
| AI-006 | `tutor/services/tts.py` | `synthesize` | tts | openai | AI_TTS_MODEL | migrated | `ai_client.synthesize_speech` | medium | done |
| AI-007 | `tutor/api/views.py` | `voice_call_session` | ai_tutor (realtime) | openai | AI_REALTIME_MODEL | migrated (session-start logged) | `ai_client.log_realtime_session_start` | high | done |
| AI-008 | `tutor/services/realtime_session.py` | `request_ephemeral_session` | ai_tutor (realtime) | openai | AI_REALTIME_MODEL | allowed_provider_adapter | control-plane mint (no usage) | high | document |
| AI-009 | `tutor/api/views.py` | `voice_call_sdp_relay` | ai_tutor (realtime) | openai | AI_REALTIME_MODEL | allowed_provider_adapter | SDP relay (no usage) | high | document |
| AI-010 | `learning_core/services/error_analyzer.py` | `_call_ai` | lesson_assistant | openai | AI_MODEL | migrated | `ai_client.chat` (tools) | medium | done |
| AI-011 | `learning_core/services/exercise_generator.py` | `_call_ai` | content_generation | openai | AI_MODEL | migrated | `ai_client.chat` (tools) | medium | done |
| AI-012 | `exams/services/ai_question_generator.py` | `_call_llm` | content_generation | openai | AI_MODEL | migrated | `ai_client.chat` | medium | done |
| AI-013 | `library/services/extractors.py` | `_call_ai` | content_generation | openai | AI_MODEL | migrated | `ai_client.chat` (tools) | medium | done |
| AI-014 | `library/services/summarizer.py` | `_call_ai` | library | openai | AI_MODEL | migrated (12A) | `ai_client.chat` | low | done |
| AI-015 | `motivation/services/ai_message_generator.py` | `_call_llm` | motivation | openai | AI_MODEL | migrated (12A) | `ai_client.chat` | low | done |
| AI-016 | `dictionary/services.py` | `ai_lookup` | vocabulary | openai | AI_MODEL | migrated (12A) | `ai_client.chat` (tools) | low | done |
| AI-017 | `courses/services/onlenco_media_clients.py` | `generate_image` | media_generation | openai | gpt-image-1-mini | migrated | `ai_client.generate_image` | high | done |
| AI-018 | `courses/services/onlenco_media_clients.py` | `generate_audio` | media_generation | openai | tts-1 | migrated | `ai_client.synthesize_speech` | high | done |
| AI-019 | `daily_learning/management/commands/generate_a0_audio.py` | `_synth_bytes` | media_generation | openai | tts-1 | migrated | `ai_client.synthesize_speech` | high | done |
| AI-020 | `factory/services/llm_router.py` | `_post_chat`/`chat` | content_generation (funnel) | openai/local | AI_MODEL/local | allowed_provider_adapter (self-logs) | funnel meter in `chat()` | medium | document |
| AI-021 | `ai_engine/services/providers.py` | `_llm_chat`/`local_llm`/`openai` | (via funnel) | — | — | covered by AI-020 | metered at funnel | medium | covered |
| AI-022 | `factory/services/quality_router.py` / `question_factory/services/ai_generator.py` / `ai_training/services/evaluator.py` | (via funnel) | content_generation | — | — | covered by AI-020 | metered at funnel | medium | covered |

**Classification summary:** migrated = 16 egress sites + funnel meter; covered
(via funnel) = ai_engine providers, quality_router, question_factory, ai_training;
allowed_provider_adapter = `llm_router` (self-logs), realtime mint + SDP relay
(control-plane, no token usage); false_positive = `core/services/reading_prep.py`
(endpoint only in comments — delegates to TTS helper).

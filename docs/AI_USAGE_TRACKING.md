# AI Usage Tracking & Cost Control (`ai_usage`)

Prompt 12A. This document explains how the platform meters and controls its
own AI spend — independent of any provider dashboard.

## 1. Architecture

```
caller (view / service / task)
        │  (after migration: never calls the provider directly)
        ▼
ai_usage.services.ai_client      ← single egress
        ├── limit_service         enforce AI-Tutor minutes (speaking)
        ├── usage_logger          write AIUsageLog (success/failed/cancelled)
        │       └── cost_calculator   price via AIModelPricing (Decimal)
        └── provider HTTP (OpenAI-compatible: AI_API_BASE + Bearer AI_API_KEY)

nightly / hourly jobs
        ├── aggregate_ai_usage_daily      AIUsageLog → AIDailyUsageSummary
        ├── update_student_daily_limits   refresh StudentDailyAILimit
        └── ai_usage_alerts               budget / failure thresholds
```

**Models** (`ai_usage/models.py`):
* `AIModelPricing` — admin-editable price book (provider + model + effective window).
* `AIUsageLog` — one row per request (tokens, audio seconds, minutes, cost, status, latency, minimal metadata).
* `AIDailyUsageSummary` — nightly rollup per (date, user, organization, role).
* `StudentDailyAILimit` — per-student/day minute projection over `subscriptions`.

> The legacy `core.models.AIUsageLog` / `core.services.ai_usage` still exist for
> un-migrated call sites; the new app supersedes them and they are retired once
> migration completes.

## 2. How usage is calculated

The wrapper captures, per call:
* **chat** — `usage.prompt_tokens` / `completion_tokens` from the response.
* **streaming chat** — sets `stream_options.include_usage`; reads the trailing usage frame.
* **STT** — `duration` seconds from the transcription response.
* **TTS** — estimated spoken seconds (≈14 chars/sec) since the endpoint returns no usage.
* **realtime voice** — no server-visible tokens; only the session event is logged. Minutes come from the session lifecycle.

## 3. How cost is estimated

`cost_calculator` reads the active `AIModelPricing` row and computes, in `Decimal`:
`tokens/1e6 × token_price + audio_seconds/60 × per-minute_price`. Missing price ⇒
cost `0` + a logged warning (never an error). Money is `Decimal` end-to-end.

## 4. How pricing is configured

Edit `AIModelPricing` in Django Admin (`/django-admin/`). Choose the row by
`provider` + `model_name`, with an `effective_from`/`effective_to` window and
`is_active`. A data migration seeds public list prices as a starting point;
**verify them against your invoice**. Never hardcode prices in code.

## 5. Daily AI-Tutor minutes

Authoritative state lives in `subscriptions` (plans, `FreeTrialUsage`,
`UserDailyQuota`, `AITutorSession`). `ai_usage.limit_service` is a thin adapter:

* **Free first day** — a new student (no subscription) gets a one-shot
  `AI_TUTOR_FREE_FIRST_DAY_MINUTES` (5) trial, granted once and never reset.
* **Base plan** — `SubscriptionPlan.ai_tutor_daily_minutes` (5).
* **Upgrades** — 10 / 20 / 30 minutes/day (plan-driven, admin-editable).
* **Minutes are charged from actual session duration**, via
  `subscriptions.session_service.end_session(actual_seconds=…)` /
  `limit_service.finalize_ai_tutor_minutes`.
* **Block** — when no minutes remain, `check_can_start_ai_tutor` returns
  `(False, {reason, message:{ar,en}})`:
  * ar: «لقد انتهى رصيدك اليومي من دقائق المعلم الذكي…»
  * en: "Your daily AI Tutor minutes are finished…"
* `remaining_minutes` is bucket-consistent and never negative.

`StudentDailyAILimit` is a per-plan projection; the start gate uses the true
effective startability (which may include a one-shot trial cushion the
`subscriptions` layer grants).

## 6. Admin monitoring

Control-center pages (admin only) under `/control/ai-usage/`:
* **Overview** — today/yesterday/month spend, requests, tokens, tutor minutes,
  failed requests, top users/features/models, budget %.
* **Daily report** — filter by date/user/role/feature/model/status.
* **Student usage** — plan, allowed/used/remaining minutes, month cost, last session.
* **Export** — CSV (Excel/PDF are TODO).

## 7. Student visibility

Students see remaining minutes (`GET /api/ai-usage/limits/me/`) but **never**
internal USD cost unless `AI_USAGE_STUDENT_CAN_VIEW_COST=True`.

## 8. API

| Endpoint | Who |
|---|---|
| `GET /api/ai-usage/summary/today/` · `…/month/` | self-scoped; admin = all |
| `GET /api/ai-usage/daily/` | self/teacher = own rows; admin = all (paginated, filters) |
| `GET /api/ai-usage/users/{id}/` | self or admin |
| `GET /api/ai-usage/features/` · `…/models/` | admin only |
| `GET /api/ai-usage/limits/me/` | any authenticated user |
| `POST /api/ai-usage/recalculate/` | admin only |

## 9. Scheduled aggregation & jobs

Celery is an optional stub, so **management commands** are the supported path
(`ai_usage/tasks.py` mirrors them for when Celery is enabled):

```
python manage.py aggregate_ai_usage_daily --date=YYYY-MM-DD [--from-date --to-date --force]
python manage.py update_student_daily_limits [--user ID]
python manage.py ai_usage_alerts
```

## 10. Alerts

`alert_service.evaluate_alerts()` fires on: daily budget, monthly budget,
abnormal per-user spend, and a failed-request spike (last hour). Emails
`AI_USAGE_ALERT_EMAILS`; logs a warning + TODO when none configured.

## 11. Settings

`AI_USAGE_TRACKING_ENABLED`, `AI_USAGE_DEFAULT_CURRENCY`,
`AI_USAGE_ALERT_EMAILS`, `AI_USAGE_DAILY_BUDGET_USD`,
`AI_USAGE_MONTHLY_BUDGET_USD`, `AI_TUTOR_FREE_FIRST_DAY_MINUTES`,
`AI_TUTOR_BASE_DAILY_MINUTES`, `AI_USAGE_STUDENT_CAN_VIEW_COST`,
`AI_USAGE_LOG_PROMPTS`, `AI_USAGE_LOG_RESPONSES`, `AI_USAGE_REDACT_METADATA`,
`AI_USAGE_USER_DAILY_ALERT_USD`, `AI_USAGE_FAILED_REQUESTS_ALERT`.

## 12. Privacy & security

* No full conversations stored. Only metrics, feature, tokens, duration,
  model, cost, status, latency, minimal metadata.
* Prompt/response logging is **off by default**; metadata is redacted
  (sensitive keys dropped, long strings truncated).
* API keys are never stored or logged — the wrapper scrubs the key from any
  error string before logging.

## 13. Troubleshooting missing usage logs

* `AI_USAGE_TRACKING_ENABLED=False` → wrapper skips logging.
* Call site not migrated → still logs via legacy `core` logger (see migration report).
* `request_id` reused → row is updated, not duplicated (intentional dedup).
* No `AIModelPricing` row → cost logs as 0 with a warning; add a pricing row.

## 14. Migrating direct OpenAI calls

See `docs/AI_WRAPPER_MIGRATION_REPORT.md`. Pattern: replace the raw
`requests.post(...)` with the matching `ai_client` method, pass
`feature`/`user`/`role`/ids, and drop any inline `core.services.ai_usage`
logging (the wrapper logs once).

---

## 15. Adding a new AI feature safely (12A.1)

1. **Never call the provider directly.** Call a method on
   `ai_usage.services.ai_client` (`chat`, `stream_chat`, `complete_text`,
   `transcribe_audio`, `synthesize_speech`, `generate_image`,
   `generate_content`, `roleplay`, `generic_call`,
   `log_realtime_session_start`).
2. **Pass attribution:** `feature=` (a constant from
   `ai_usage.services.feature_mapping`), `user=`, `role=` (or let it derive),
   and any of `model/session_id/lesson_id/unit_id/course_id/organization/
   request_id/metadata`. Function-calling / response_format / temperature go in
   `extra_payload=`.
3. **Pick the feature code** from `ai_usage/constants.py::FEATURE_CHOICES`. Add a
   new one there (+ a no-op `AlterField` migration) if none fits, and map it in
   `feature_mapping.py`.
4. **Roles:** student-facing → `student` (default); teacher/admin content →
   `teacher`/`admin`; scheduled/offline → `system`. Content/media generation must
   **not** use a minute-bearing feature (only `ai_tutor` consumes daily minutes).
5. **Minutes:** for a live student *speaking* session, gate with
   `limit_service.check_can_start_ai_tutor` (or pass `enforce_minutes=True` to
   `chat`/`stream_chat`) and charge actual duration via
   `limit_service.finalize_ai_tutor_minutes` / `session_service.end_session`.

### Required wrapper parameters

All `ai_client` methods accept the `AICallContext` fields via kwargs:
`user, role, feature, provider, model, session_id, lesson_id, unit_id,
course_id, organization, request_id, metadata` (+ method-specific
`extra_payload`, `voice`, `response_format`, `enforce_minutes`).

### How to test logging

Mock the shared transport and assert an `AIUsageLog` row:

```python
from unittest import mock
from ai_usage.services import ai_client
from ai_usage.models import AIUsageLog
from ai_usage.tests.helpers import FakeResponse, chat_json

with mock.patch.object(ai_client.requests, "post",
                       return_value=FakeResponse(json_data=chat_json())):
    my_service.do_ai_thing()
log = AIUsageLog.objects.latest("id")
assert log.feature == "my_feature" and log.status == "success"
```

### How to verify no direct calls remain

Run the guardrail:

```
DJANGO_SETTINGS_MODULE=config.settings.test python manage.py test \
  ai_usage.tests.test_no_direct_calls
```

It walks the source tree and fails if any non-allowlisted file makes an HTTP
POST to a provider endpoint. Allowed: the wrapper, the `llm_router` funnel
(self-logs), and the realtime mint / SDP relay (control-plane, no token usage).

---

## 16. Image generation pricing (Prompt 16.5)

`AIModelPricing` now also prices **image generation** (in addition to tokens +
audio):

* `image_price_per_generation` — USD per image, used when
  `image_pricing_unit = "per_image"` (default).
* `image_price_per_1k_images` — USD per 1,000 images, used when
  `image_pricing_unit = "per_1k_images"`.

`cost_calculator.calculate_image_cost(provider, model, n_images)` reads the
active row; `ai_client.generate_image` computes the cost and passes it to the
usage log (so `feature=media_generation` rows get a non-zero
`estimated_cost_usd` when a price exists). Missing image price ⇒ cost 0 + a
logged warning (never a crash). All money is `Decimal`; never hardcode prices
in services — edit the row in Django Admin.

> ⚠️ The seeded default for `gpt-image-1-mini` is **$0.02/image — a public
> list-price approximation and a starting point only**. Verify it against the
> real provider invoice and update the row before relying on the figure.

### Reconciling historical $0 image logs

Image usage logged before pricing existed (e.g. the Prompt 16 smoke image) can
be recomputed:

```
python manage.py reconcile_image_ai_usage_costs --dry-run
python manage.py reconcile_image_ai_usage_costs --confirm
```

Only `feature=media_generation` rows with `estimated_cost_usd = 0` are updated
(using `metadata.image_count`); text/audio logs are never touched, and a
`metadata.image_cost_recalculated_after_prompt_16_5` flag is set.

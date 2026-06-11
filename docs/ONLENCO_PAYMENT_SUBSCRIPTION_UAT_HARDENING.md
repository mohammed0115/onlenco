# Onlenco — Payment & Subscription UAT Hardening (18.5B)

> Hardening pass on the existing manual payment + subscription system.
> No payment gateway built, no external gateway called, no real money, no
> production deploy. Builds on `docs/ONLENCO_PAYMENT_SUBSCRIPTION_UAT_AUDIT.md`.
> Branch: `feat/beginner-media-and-tutor-usage`.

---

## 1. What Was Hardened

1. **Single server-side source of truth for amount + duration** — documented and locked: `payments.models.PLAN_DETAILS` is the only place the base-subscription price (`monthly`=30,000 / `quarterly`=50,000) and duration (30 / 90 days) live. Both the HTML form and the API read from it; `amount_sdg` is read-only in the API serializer and is **not** a form field, so the client can never set it.
2. **Added the missing 20-minute tier** — `pro_20m` = 20 AI-Tutor min/day @ **100,000 SDG**, completing the product upgrade grid (10→50k, 20→100k, 30→150k). Additive, idempotent seed migration; admin-editable.
3. **Admin-editable per-plan caps + feature gates** (additive fields): per-session caps for AI Tutor and Library, plus `course_access_enabled` / `daily_quiz_enabled` / `placement_enabled`.
4. **Plan-driven AI-Tutor session cap** — the realtime call now reads the active plan's `ai_tutor_session_cap_minutes`, falling back to the global `AI_REALTIME_MAX_SESSION_SECONDS` when unset (so existing behaviour is unchanged unless an admin opts in).
5. **Library minute fields wired for read** — daily + session caps are stored on and read from the plan now; enforcement lands in 19.0.
6. **Focused test coverage** for amount integrity, durations, the 20-min tier, live plan edits, and the full access lifecycle.

No AI-Tutor accounting logic was rewritten — the `subscriptions` quota/session services remain the single source of truth.

---

## 2. Plan Catalog Source of Truth

| Concern | Authoritative location | Read by |
|---------|------------------------|---------|
| Base-subscription **price** (monthly/quarterly) | `payments.models.PLAN_DETAILS[plan]["price_sdg"]` | `PaymentSubmissionForm.save`, `PaymentSubmissionListCreateView.perform_create` |
| Base-subscription **duration** | `payments.models.PLAN_DETAILS[plan]["duration_days"]` | `PaymentSubmission.approve()` |
| AI-Tutor **daily minutes / daily cap** | `SubscriptionPlan.ai_tutor_daily_minutes` (DB) | `quota_service.daily_ai_tutor_limit_seconds` |
| AI-Tutor **session cap** | `SubscriptionPlan.ai_tutor_session_cap_minutes` (DB) → global setting fallback | `quota_service.ai_tutor_session_cap_seconds` → tutor realtime start |
| Library **daily / session minutes** | `SubscriptionPlan.library_audio_daily_minutes` / `library_session_cap_minutes` (DB) | `quota_service.daily_library_limit_seconds` / `library_session_cap_seconds` |
| Minute-tier prices (upgrades) | `SubscriptionPlan.price_sdg` (DB) | upgrade page / admin |

The client never supplies amount, duration, or minutes — all are server/DB-driven. No price is hardcoded in templates, views, or serializers.

> **Note on the two price lists.** `PLAN_DETAILS` (base subscription, monthly/quarterly) and `SubscriptionPlan.price_sdg` (minute-tier upgrades) are *different products*, not duplicates. They are intentionally separate. The remaining structural item — letting students *purchase a specific minute tier directly* through the manual flow — is deferred (see §9).

---

## 3. Admin Editable Fields (`SubscriptionPlan`, no code change needed)

Grouped into clear fieldsets in `/admin/subscriptions/subscriptionplan/`:

- **Identity:** `code`, `name_en`/`name_ar`, descriptions
- **Billing:** `price_sdg`, `currency`, `billing_cycle` (monthly/quarterly), `is_active`, `is_free_trial`, `is_featured`, `sort_order`
- **AI Tutor:** `ai_tutor_daily_minutes` (allowance = daily cap), `ai_tutor_session_cap_minutes`
- **Library (19.0):** `library_audio_daily_minutes`, `library_session_cap_minutes`
- **Feature gates:** `course_access_enabled`, `daily_quiz_enabled`, `placement_enabled`

`price_sdg`, `ai_tutor_daily_minutes`, `library_audio_daily_minutes`, `is_active`, and `sort_order` are also inline-editable from the list view. Naming-parity read-only aliases `ai_tutor_daily_cap_minutes` and `library_daily_minutes` exist on the model for spec/report references.

---

## 4. Manual Payment UAT Flow

1. Student chooses a plan (`monthly` / `quarterly`) + method (Bankak/Fawry/O-Cash).
2. **Server** computes `amount_sdg` from `PLAN_DETAILS` (client value ignored).
3. `PaymentSubmission` created → `status=pending`, `Profile.subscription_status=pending`.
4. Admin reviews in `/admin/` → approve / reject / refund.
5. On **approve**: profile → `active` + `subscription_expires_at` extended (server-side from `duration_days`), a `UserSubscription` is activated, revenue split recorded.
6. Course access + AI-Tutor minutes unlock from the active plan.
7. **Refund / cancel** reverses both layers (profile `expired` + `UserSubscription` expired) → minutes drop to 0.
8. Expiry enforced three ways: `is_subscribed`, lazy-expiry middleware, `expire_overdue_subscriptions` sweep.

States: `pending` → `approved` / `rejected` / `refunded`; subscription: `pending`/`active`/`expired`/`cancelled`.

---

## 5. Access Control Rules (test-locked)

| State | Paid course | AI Tutor |
|-------|-------------|----------|
| No active subscription | ❌ blocked | trial only |
| Pending payment | ❌ blocked | trial only |
| Active subscription | ✅ granted | plan minutes |
| Expired subscription | ❌ blocked | 0 |
| Refunded payment | ❌ blocked | 0 |
| Free course | ✅ always | — |

Frontend cannot override the **amount** (read-only / not a form field) nor the **minutes** (computed from the active plan, no client input).

---

## 6. AI Tutor Plan Linkage

- Daily allowance = `active_plan_for(user).ai_tutor_daily_minutes × 60`; **0 with no active plan**.
- Session cap = plan's `ai_tutor_session_cap_minutes` (if >0) else `AI_REALTIME_MAX_SESSION_SECONDS`.
- Editing the plan's minutes is read **live** on the next request — no constants, no cache to invalidate (quota reads hit the DB plan each call).
- Bucket priority unchanged: subscription first, one-shot free trial fallback.

---

## 7. Library Minutes Readiness for 19.0

- `library_audio_daily_minutes` (daily) and `library_session_cap_minutes` (per-session) are **stored on and read from the plan today** via `quota_service.daily_library_limit_seconds` / `library_session_cap_seconds`.
- `UserDailyQuota.library_seconds_used` + `consume_library_seconds` already exist.
- **19.0 wiring point:** the Library reader (and Sudanese-school-novels reader) must open a `LibraryAudioSession`, cap each session at `library_session_cap_seconds(user)`, and deduct via `consume_library_seconds`. The plan limits and counters are ready; only the reader-side call sites are pending.

---

## 8. Tests Added

`subscriptions/tests/test_uat_hardening_18_5b.py` (18 tests):
- Catalog source of truth: frontend cannot override amount (monthly/quarterly).
- Durations: monthly → ~30-day sub, quarterly → ~90-day sub.
- 20-min tier seeded @ 100,000 SDG; upgrade grid (10/20/30 → 50k/100k/150k); new fields exist + safe defaults + aliases.
- Live plan edits: AI minutes 10→2 reflected; library minutes read from plan; session cap fallback vs plan value; inactive plan not offered.
- Access lifecycle: no-sub / pending / approved / refunded / expired / free-course.

Updated `subscriptions/tests/test_models.py` seed-set assertion to include `pro_20m`.

---

## 9. Remaining Production Blockers

1. **Direct purchase of a specific minute tier** through the manual flow is still indirect — the base flow sells `monthly`/`quarterly` (both map to `basic_10m`). The upgrade page lists all tiers but the buy path needs a product decision on the two-axis (period × minute-tier) model. **Deferred to a future phase**, not a UAT blocker.
2. **No electronic gateway / automated reconciliation** — by design (manual business model).
3. **Library minute enforcement** is read-ready but not enforced until 19.0.

No dangerous bypass: amount is server-set, approve is idempotent, refund revokes minutes, expiry is server-enforced.

---

## 10. Notes for Novel Reader Integration (19.0)

- Reuse `LibraryAudioSession` + `consume_library_seconds` + `library_session_cap_seconds(user)`; do **not** add a parallel counter.
- Gate novel access on `SubscriptionPlan.course_access_enabled` (or a dedicated flag if novels become a separate entitlement) — the feature-gate fields are in place.
- Keep placement/Daily-Quiz free of the Library bucket, mirroring how placement speaking is kept free of the AI-Tutor bucket.

---

> **18.5B hardened payment and subscription UAT readiness with admin-editable plan limits for AI Tutor and Library.**

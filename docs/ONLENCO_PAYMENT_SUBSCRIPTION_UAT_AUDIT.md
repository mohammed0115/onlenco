# Onlenco — Payment & Subscription UAT Audit (18.5A)

> Audit-only document. No real payment was performed, no production price or
> access rule was changed, no migration was run.
> Branch: `feat/beginner-media-and-tutor-usage` · Base commit: `488212a`

---

## 1. Current Architecture

Onlenco currently runs **two parallel layers** that are bridged on payment approval:

| Layer | App | Purpose |
|-------|-----|---------|
| **Legacy / billing** | `payments` | Manual bank-transfer + screenshot proof + admin approval. Drives `Profile.subscription_status` / `subscription_expires_at`. |
| **Quota / catalogue** | `subscriptions` | Plan catalogue (minutes), `UserSubscription`, daily quota counters, free trial, AI-Tutor session lifecycle. |
| **Bridge** | `payments.PaymentSubmission.approve()` | On approval, sets the profile fields **and** activates a `subscriptions.UserSubscription` via `LEGACY_PLAN_TO_NEW_CODE`. |
| **Enforcement adapters** | `ai_usage`, `tutor.services.usage_limits` | Thin facades that read the `subscriptions` quota — they do not re-implement accounting. |

There is **no electronic gateway**. All payment is **manual offline transfer** (Bankak / Fawry / O-Cash) verified by a human admin.

---

## 2. Existing Models / Views / Services

### Models
- `payments.PaymentMethodAccount` — admin-editable destination accounts (bank/wallet).
- `payments.PaymentSubmission` — the payment proof + status machine + `approve/reject/refund` + marketplace revenue split.
- `subscriptions.SubscriptionPlan` — plan catalogue (price, daily AI-Tutor minutes, library minutes, free-trial flag).
- `subscriptions.UserSubscription` — which plan is active for which user/window (FK → `PaymentSubmission`).
- `subscriptions.FreeTrialUsage` — one-shot 5-minute AI-Tutor trial (never resets).
- `subscriptions.UserDailyQuota` — per-(user, date) seconds counter.
- `subscriptions.AITutorSession` / `LibraryAudioSession` — DB-backed session lifecycle with a "one in-progress per user" constraint.
- `accounts.Profile` — `subscription_status`, `subscription_expires_at`, `is_subscribed`, `is_in_free_tier`.

### Views
- `payments.views.subscribe` — pick plan + method, show account, upload screenshot → `pending`.
- `payments.views.payment_history`, `payments.views.choose_teacher`.
- `subscriptions.views.upgrade_page` — lists paid plans + quota snapshot.
- `subscriptions.views.quota_snapshot_api` / `preferences_page` / `preference_api`.

### Services
- `subscriptions.services.subscription_service` — `active_plan_for`, `activate_subscription` (top-up semantics), `cancel`, `expire_overdue_subscriptions`, `revoke_subscription_for_payment`.
- `subscriptions.services.quota_service` — daily limits, `effective_ai_tutor_remaining`, `deduct_session_seconds`, free-trial accounting.
- `subscriptions.services.session_service` — session open/close + concurrency guard.
- `payments.services` — `approve_submission` / `reject_submission` wrappers.
- `accounts.decorators.subscription_required` — central paywall decorator.
- `accounts.middleware` — lazy request-time subscription expiry.

### Templates
- `templates/payments/subscribe.html`, `.../history.html`, `.../choose_teacher.html`.
- `subscriptions/templates/subscriptions/upgrade.html`, `preferences.html`.

---

## 3. Current Payment Flow

1. Student opens `/payments/` (`subscribe`).
2. Picks **plan** (`monthly` / `quarterly`) + **method** (Bankak/Fawry/O-Cash).
3. Transfers money offline to the shown account.
4. Uploads a **screenshot** (required, ≤5 MB, image MIME enforced) + optional transaction reference.
5. `PaymentSubmission` is created with `status=pending`; `Profile.subscription_status=pending`; admin + student notified.
6. Admin reviews in `/admin/` → `approve()` / `reject()` / `refund()`.
7. On **approve**: `amount_sdg` is **server-set** from `PLAN_DETAILS` (tamper-proof), profile flips to `active` with `subscription_expires_at` extended, revenue split recorded, and a `UserSubscription` is activated (best-effort, non-blocking).

> **Amount integrity:** the form never trusts a client-supplied amount — `obj.amount_sdg = PLAN_DETAILS[obj.plan]["price_sdg"]`.

---

## 4. Current Subscription Flow

- `activate_subscription` creates/extends a `UserSubscription` (top-up stacks the end date; a different plan expires the old row).
- Expiry is enforced three ways: (a) `Profile.is_subscribed` checks `subscription_expires_at`; (b) `accounts.middleware` lazily flips `active → expired` at request time; (c) `expire_overdue_subscriptions` sweep + `accounts` management command.
- **Refund** reverses both layers: profile → `expired` **and** `revoke_subscription_for_payment` expires the linked `UserSubscription` (closes the "refunded user keeps minutes" gap).
- Double-approve is guarded (idempotent — no accidental free extra month).

---

## 5. Access Control Findings

| Scenario | Result | Mechanism |
|----------|--------|-----------|
| Paid course, no active subscription | **Blocked** (403 / redirect to subscribe) | `can_access_course` → `is_subscribed` |
| Free course, no subscription | Open | `course.is_free` short-circuit |
| First 7 days after onboarding | **Allowed** (free tier) | `Profile.is_in_free_tier` (by design, time-boxed) |
| Pending payment | Treated as not-subscribed (trial/free-tier only) | `is_subscribed` requires `status=active` |
| Expired subscription | **Blocked** | lazy-expiry middleware + sweep |
| Active subscription | Allowed | `is_subscribed` |
| Payment but no enrollment | Auto-enrolled on entry | `ensure_course_enrollment` |
| AI Tutor without plan | 5-min one-shot trial, then **blocked** | `effective_ai_tutor_remaining` |
| Exceed AI minutes | Hard-stopped | quota clamp + `AI_REALTIME_MAX_SESSION_SECONDS` (900s) session cap + `killed_quota_exceeded` |
| Locked (drip) lessons | Sequential unlock | `can_open_lesson` / `is_unlocked_for` (independent of subscription) |

**Session vs daily caps:** per-session hard cap = `AI_REALTIME_MAX_SESSION_SECONDS` (default **900s / 15 min**); browser is told `min(session_cap, remaining_today)`. Daily cap = `plan.ai_tutor_daily_minutes`. Both enforced **server-side**.

---

## 6. AI Tutor Minutes / Plan Linkage

- `daily_ai_tutor_limit_seconds(user) = active_plan_for(user).ai_tutor_daily_minutes * 60` → **0 when no active plan**.
- **Voice calls** and **voice messages** consume the daily allowance; **placement speaking** never does (explicit `MODE_PLACEMENT_SPEAKING_CALL`); **text chat** is gated by `is_subscribed` but does not burn voice minutes.
- Bucket priority: **subscription first, free trial fallback** (`effective_ai_tutor_remaining`) — paid users never accidentally burn the trial.
- Free trial = 5 minutes (300s), one-shot, never resets.

---

## 7. Product Rule Comparison

| Product rule | Code state | Match? |
|--------------|-----------|--------|
| Monthly = 30,000 SDG | `PLAN_DETAILS.monthly = 30000 / 30d` | ✅ |
| 3 months = 50,000 SDG | `PLAN_DETAILS.quarterly = 50000 / 90d` | ✅ |
| First day free 5 min | `FreeTrialUsage` 300s | ✅ |
| Base daily minutes per plan | `SubscriptionPlan.ai_tutor_daily_minutes` | ✅ |
| Upgrade 10 min = 50,000 | `basic_10m = 50000 / 10 min` | ✅ |
| Upgrade 20 min = 100,000 | **No 20-min plan** (catalogue has `plus_15m = 75000 / 15 min`) | ❌ |
| Upgrade 30 min = 150,000 | `pro_30m = 150000 / 30 min` | ✅ |
| Session cap + daily cap enforced | server-side, yes | ✅ |

### ⚠️ Critical disconnect — catalogue vs purchasable
The payment form only sells `monthly` / `quarterly`, and **both map to `basic_10m` (10 min/day)** via `LEGACY_PLAN_TO_NEW_CODE`. The richer catalogue plans (`starter_5m`, `plus_15m`, `pro_30m`) are listed on the upgrade page and its "Subscribe" buttons pass `?plan=<code>`, **but the subscribe form's `plan` field only accepts `monthly`/`quarterly`** — so those upgrade tiers are **not actually purchasable** through the real flow. Effectively, the only thing a paying student can obtain today is **10 min/day**, regardless of price paid (30k monthly or 50k quarterly both → 10 min/day).

Additionally, there are **two price sources of truth** (`payments.PLAN_DETAILS` vs `SubscriptionPlan.price_sdg`) that can drift — e.g. `basic_10m.price_sdg = 50000` while `monthly = 30000`.

---

## 8. Tests Found / Missing

### Found
- `subscriptions/tests/`: `test_models`, `test_services`, `test_payments_integration`, `test_free_trial_and_sessions`, `test_admin_pages`, `test_voice_avatar_preferences`, `test_library_natural_reader`.
- `payments/tests/`: `test_payments`, `test_marketplace`.
- `ai_usage/tests/`: `test_limits`, `test_approval_gate` (+ migration/cost suites).
- `courses/tests/`: `test_student_flow` and others touch paywall/forbidden paths.
- ✅ `subscriptions + payments` suite = **167 tests OK**.

### Missing / thin
- No dedicated end-to-end test for the **upgrade-tier purchase path** (because it does not exist).
- No test asserting **catalogue ↔ payment price parity** (would catch the disconnect).
- Course-paywall assertions exist but are scattered; no single focused access-control matrix test for the 9 scenarios in §5.
- No explicit test for the **20-min tier** product rule (tier absent).

---

## 9. UAT Readiness

**Ready for limited internal UAT (manual flow): YES.**
- Manual submit → admin approve → access granted → quota assigned → expiry respected all work and are tested.
- Amount is tamper-proof; refund reverses both layers; expiry is enforced three ways.

**Caveat:** UAT should exercise only `monthly` / `quarterly` (both yield 10 min/day). Do **not** advertise starter/plus/pro tiers to UAT students — they cannot be bought yet.

---

## 10. Production Blockers

1. **Catalogue ↔ payment disconnect** — only `basic_10m` (10 min/day) is purchasable; `starter_5m`/`plus_15m`/`pro_30m` upgrade buttons lead to a form that rejects them.
2. **Missing 20-min / 100,000 SDG tier** required by product rules (catalogue has 15-min instead).
3. **Dual price source of truth** (`PLAN_DETAILS` vs `SubscriptionPlan.price_sdg`) — drift risk.
4. **No electronic gateway** — acceptable for a manual business model, but there is no automated reconciliation and no env/feature separation between a future gateway and the manual path.
5. Thin focused test coverage for the access-control matrix and price parity.

> No **dangerous free-access bypass** was found: amount is server-set, double-approve is idempotent, refund revokes minutes, expiry is enforced server-side. The 7-day free tier is intentional and time-boxed.

---

## 11. Recommended 18.5B Implementation Plan

The base architecture **exists and is solid** — it needs hardening/wiring, not a rebuild. Recommend **18.5B — Payment Subscription UAT Hardening**:

1. **Unify the purchase path** — let the subscribe form accept any active `SubscriptionPlan.code`, map `plan → duration_days` from the plan's billing cycle, and set `amount` from `SubscriptionPlan.price_sdg`. Retire `LEGACY_PLAN_TO_NEW_CODE` or make it 1:1.
2. **Single price source of truth** — drive `PLAN_DETAILS` from `SubscriptionPlan` (or delete the duplicate) so 30k/50k vs 50k cannot drift.
3. **Reconcile product price grid** — add the **20-min = 100,000 SDG** tier (or confirm 15-min replaces it as a product decision); align monthly/quarterly price→minutes with the product spec.
4. **Access-control matrix test** — one test covering all 9 §5 scenarios + a price-parity test.
5. **Admin approval UX** — confirm the bank-transfer-proof review actions (approve/reject/refund) are first-class in `/admin/` with audit notes (already present; add coverage).
6. (Optional, later) electronic gateway behind a feature flag, kept separate from the manual path.

Any migration (e.g. new 20-min plan / price realignment) is to be **planned in 18.5B**, not run in 18.5A.

---

## 12. Commands Run (18.5A)

```
python manage.py check                         → System check identified no issues (0 silenced).
python manage.py test subscriptions payments   → Ran 167 tests … OK
python manage.py test tutor daily_learning courses → (see Report §14)
```
(No `billing` app exists; `payments` + `subscriptions` cover that scope.)

---

## 13. Final Note

**18.5A audited payment and subscription readiness without performing real payments or changing production access.**

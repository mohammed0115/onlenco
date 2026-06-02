# Student Registration Approval Gate + Anti-Bot

Prevents bot/unapproved accounts from reaching student features (dashboard,
courses, lessons, challenges, AI Tutor, placement, library, student APIs) or
consuming AI minutes until an admin approves them.

## Registration flow

```
register  →  email verification (OTP)  →  pending admin approval  →  (admin approves)  →  dashboard
            pending_email_verification     pending_admin_approval        approved
```

* New students are created **pending** and are **never** sent straight to the
  dashboard. They see the waiting page at `/account/pending-approval/`.
* Staff / teacher / admin accounts are **auto-approved and exempt** — the gate
  never blocks them.
* Feature flag: `ONLENCO_STUDENT_APPROVAL_REQUIRED` (default **True**). When
  False the gate is inert (used in the test suite; production keeps it True).

## Approval statuses (`Profile.approval_status`)

| Status | Meaning | Student access |
|---|---|---|
| `pending_email_verification` | registered, email not verified | blocked (→ verify page) |
| `pending_admin_approval` | email verified, awaiting admin | blocked (→ waiting page) |
| `approved` | admin approved | full access |
| `rejected` | admin rejected (note required) | blocked |
| `suspended` | admin suspended an approved account (note required) | blocked |

`is_active` (email/account active) and `email_verified` are **separate** and
untouched — approval is its own axis.

## Admin approval steps

Control panel → **Student Approvals** (`/control/student-approvals/` and
`/admin/student-approvals/`), gated by capability `students.view` (list) /
`students.manage` (actions):

* **Approve** → `approved`, sets `admin_approved_by/at`, audit `approved`.
* **Reject** (note required) → `rejected`, audit `rejected`.
* **Suspend** (note required) → `suspended`, audit `suspended`.
* **Add note** → audit `note_added`.
* **Bulk approve / reject** selected.

All actions go through `accounts.approval` so a `StudentApprovalEvent` audit row
is always written. Users are **never deleted**.

## Pending student behaviour

* HTML requests to gated pages → 302 redirect to `/account/pending-approval/`.
* API/JSON requests → `403 {"code": "account_pending_approval", "message": …}`.
* Allowed while pending: login/logout, email verification, password reset/change,
  the waiting page, language toggle, static/media.
* NOT allowed: dashboard, courses, lessons, challenges, AI Tutor, onboarding/
  placement, library, student APIs.

## Anti-bot protections

* **Honeypot** — a hidden, off-screen `ol_contact_url` field (deliberately not
  `website`/`url`/`nickname`, which browser autofill fills — the reason the old
  honeypot was removed). If filled → generic error, no account created.
* **Rate limits** — registration / login (django-axes) / password-reset are
  throttled per IP. `ONLENCO_REGISTRATION_RATE_LIMIT_PER_HOUR` (default 10).
* **CAPTCHA readiness** — `ONLENCO_REGISTRATION_CAPTCHA_ENABLED` (False),
  `ONLENCO_CAPTCHA_PROVIDER`; hCaptcha already supported via `HCAPTCHA_SITE_KEY`/
  `HCAPTCHA_SECRET` (auto-skips when keys absent — never blocks real signups).
* **Disposable email** — `ONLENCO_BLOCK_DISPOSABLE_EMAILS` (False) +
  `ONLENCO_DISPOSABLE_EMAIL_DOMAINS`. When enabled, blocks listed domains.
* **Suspicious flags** (recorded on the profile, surfaced in the queue, never
  auto-approved): `suspicious_user_agent`, `disposable_email`, `repeated_ip`,
  `honeypot_filled`, `too_many_attempts`, `duplicate_email_attempt`.

## AI access blocking

`ai_usage.services.ai_client` calls `_enforce_student_approval(ctx)` at the start
of every student-facing method (`chat`, `stream_chat`, `transcribe_audio`,
`synthesize_speech`). For a not-yet-approved student it:

* raises `AccountPendingApproval` **before** any provider HTTP call,
* consumes **no** daily AI-Tutor minutes,
* logs a `cancelled` `AIUsageLog` (cost 0, `blocked_reason=account_pending_approval`)
  so denied attempts are auditable without paid cost.

Teacher/admin/system calls are never gated.

## Migration for existing users

Schema migration `accounts/0009_initialize_approval_status` runs at deploy and
sets existing rows safely:

* staff / superuser / admin-role / Teacher-group → `approved`
* email-verified students → `approved`
* unverified → `pending_email_verification`

Re-runnable command with reporting:

```
python manage.py initialize_student_approval_status --dry-run
python manage.py initialize_student_approval_status --confirm
```

It never flips a manually `rejected`/`suspended` account.

## Troubleshooting locked users

* **A real student is stuck on the waiting page** → Student Approvals → Approve
  (or run `initialize_student_approval_status --confirm` to re-approve verified
  students in bulk).
* **A teacher/admin is blocked** → ensure they are staff, role `admin`, or in the
  `Teacher` group; `is_staff_or_privileged` exempts them. Re-run the init command.
* **Disable the gate entirely (emergency)** → set
  `ONLENCO_STUDENT_APPROVAL_REQUIRED=0` in the environment and restart.
* **A student can't reach AI** but is approved → confirm
  `profile.approval_status == "approved"`; the AI gate reads it live.

## App names note

The dashboard lives in the `lessons` app (`/dashboard/`); there is no `users` or
`student_portal` app. Run tests with: `accounts`, `ai_usage`, `tutor`,
`courses`, `teacher_portal`.

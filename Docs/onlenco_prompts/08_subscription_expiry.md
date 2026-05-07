# 08 — Subscription Expiry

## Context

The **Onlenco** Django project has a `Profile.subscription_status` field
that flips to `"active"` and a `subscription_expires_at` datetime that gets
set when an admin approves a `PaymentSubmission`. **But nothing ever expires
a subscription** — once active, it stays active forever even after
`subscription_expires_at` passes.

This is a small but important gap. This prompt fixes it three ways:

1. A management command admins can run on a schedule (cron/Celery beat/etc.)
2. A request-time check that lazily expires subscriptions when the user
   shows up
3. A property + admin field that always reflects ground truth

## Goal

Make the `is_subscribed` check correct: it returns `True` only when the
subscription is `active` AND `subscription_expires_at` is in the future
(or null, treated as "no expiry set yet"). Add a management command and a
small middleware-equivalent check.

## Spec

### Model property change — `accounts/models.py`

Update `Profile.is_subscribed`:

```python
@property
def is_subscribed(self):
    """True if the subscription is currently active and not expired."""
    if self.subscription_status != "active":
        return False
    if self.subscription_expires_at is None:
        # No expiry set means trial / lifetime — treat as active.
        return True
    from django.utils import timezone
    return self.subscription_expires_at > timezone.now()
```

This change alone fixes the gate everywhere — the dashboard, lesson detail,
library, club, tutor, etc. all consult `request.user.profile.is_subscribed`.

### Management command — `accounts/management/commands/expire_subscriptions.py`

Create the directory + `__init__.py` files if needed.

The command should:

- Find profiles where `subscription_status == "active"` AND
  `subscription_expires_at__lt = now`.
- Update them to `subscription_status = "expired"` in a single
  `.update(subscription_status="expired")` call (no per-row save).
- Print: `"Expired N subscription(s)."`
- Support `--dry-run` flag to print the IDs without modifying.

```bash
python manage.py expire_subscriptions
python manage.py expire_subscriptions --dry-run
```

### Middleware — `accounts/middleware.py`

Add a second middleware class (the file already has `LanguagePreferenceMiddleware`).

**`ExpireSubscriptionMiddleware`**

For authenticated users only, on each request:
- If `profile.subscription_status == "active"` AND
  `profile.subscription_expires_at` is in the past → set status to
  `"expired"` and save the field.
- Use `update_fields=["subscription_status"]` to keep the write minimal.
- Wrap in `try/except` to never crash the request — log a warning if anything
  unexpected happens.

This means a user landing on any page after their subscription expires sees
the unsubscribed UI immediately, even if no cron job ran. The middleware
runs once per request, so it's fine on a small site; a larger one would
move this to a periodic task.

Register the middleware in `onlenco/settings.py` MIDDLEWARE list, **after**
`AuthenticationMiddleware` (so `request.user` is available) and after
`LanguagePreferenceMiddleware` (which already exists there).

### Admin display — `accounts/admin.py`

Update `ProfileAdmin`:

- Add `expires_in_days` as a computed `list_display` column. Returns
  "Expired N days ago" / "Expires in N days" / "—" (when no expiry set).
- Add a `subscription_state` column that shows: "✓ Active",
  "⚠ Expiring soon" (if < 7 days left), "✗ Expired", "Pending", "Inactive".
- Add `subscription_expires_at` to the `list_filter` via Django's
  `RelatedDateTimeListFilter` or a custom one — or skip if it's getting
  too elaborate. A simple "filter by status" is fine.

### Tests (optional)

If practical, add a single test in `accounts/tests.py` that:
- Creates a profile with `subscription_status="active"` and
  `subscription_expires_at` in the past
- Calls the management command
- Asserts the status is now `"expired"`

Use Django's `TestCase` and `freezegun` is **not** allowed — we don't add
deps. Use `timezone.now() - timedelta(days=1)` directly.

## Acceptance criteria

A reviewer should be able to:

1. Open the Django shell and create a test profile with
   `subscription_status="active"` and `subscription_expires_at = timezone.now() - timedelta(days=2)`.
2. Run `python manage.py expire_subscriptions --dry-run` → see the profile
   ID printed but the DB unchanged.
3. Run `python manage.py expire_subscriptions` → see "Expired 1 subscription(s)."
4. Re-check the profile → `subscription_status == "expired"`.
5. Create another expired-but-still-active profile, log in as that user,
   visit `/dashboard/` → middleware flips them to expired and the
   "Subscribe" CTA appears immediately.
6. Look at `/admin/accounts/profile/` → see the new `expires_in_days` and
   `subscription_state` columns showing the right text.
7. Approve a fresh `PaymentSubmission` → the subscription's
   `subscription_expires_at` is correctly set 30 / 90 days out, AND
   `is_subscribed` returns `True`.

`python manage.py check` clean. No new dependencies in `requirements.txt`.

## Out of scope

- No grace period (e.g. "still works for 3 days after expiry").
- No reminder emails before expiry (covered separately).
- No auto-renewal — payments are still manual.
- No cancel-mid-cycle flow. Users keep what they paid for; admin can
  manually edit the date in `/admin/` if needed.

## Style guide

- Management commands: short, single `Command` class, `help` string,
  `add_arguments` for `--dry-run`. Use `self.stdout.write(self.style.SUCCESS(...))`
  for success output.
- Admin custom columns should be methods on the `ModelAdmin` class with
  `@admin.display(description="...")` decorators where the label needs
  customization.

## What to deliver

A patched `onlenco_django.zip` with:

- `Profile.is_subscribed` property updated
- `accounts/management/commands/expire_subscriptions.py` added
- `accounts/middleware.py` extended with `ExpireSubscriptionMiddleware`
- `onlenco/settings.py` updated to register the middleware
- `accounts/admin.py` updated with the new columns
- (Optional) one test in `accounts/tests.py`

`python manage.py check`, `python manage.py migrate`, and
`python manage.py expire_subscriptions --dry-run` all run clean.

# 10 — Payment Rejection UI for Users

## Context

The **Onlenco** payment flow lets admins approve or reject `PaymentSubmission`
rows from `/admin/`. Approval works fine. Rejection technically works too —
the row gets `status="rejected"` and an `admin_note` — **but the user has no
clear way to see the rejection or do something about it.** The history page
shows the status but doesn't surface the note prominently or invite a retry.

Project conventions:
- `{% load i18n_dict %}` plus `{% t "key" %}` and `{% t_either "en" "ar" %}`.
- Component classes: `.btn`, `.btn-hero`, `.btn-outline`, `.card`, `.badge`.
- Lucide icons.
- Existing payment views: `payments/views.py`, templates in
  `templates/payments/{subscribe,history}.html`.

## Goal

When a user has a `rejected` payment submission, give them clear, friendly
feedback explaining why and an obvious path to retry. Specifically:

1. Show a prominent rejection banner on the dashboard (and on the history
   page) for any user whose latest submission is rejected.
2. Show the admin's `admin_note` reason inline.
3. Include a "Try again" CTA that links to `/payments/` (the subscribe
   form) with the previous plan/method pre-selected via querystring.
4. Reset the user's `subscription_status` to `"inactive"` (not `"pending"`)
   when the latest submission is rejected and there are no other pending
   submissions.

## Spec

### Model behavior change — `payments/models.py`

The `PaymentSubmission.reject()` method already partially handles this.
Audit and tighten:

```python
def reject(self, reviewer, note=""):
    self.status = "rejected"
    self.reviewed_by = reviewer
    self.reviewed_at = timezone.now()
    if note:
        self.admin_note = note
    self.save(update_fields=["status", "reviewed_by", "reviewed_at", "admin_note"])

    # If this user has no other pending submissions, drop their profile
    # status back to "inactive" so the dashboard banners are correct.
    profile = self.user.profile
    has_pending = self.user.payment_submissions.filter(status="pending").exists()
    if profile.subscription_status == "pending" and not has_pending:
        profile.subscription_status = "inactive"
        profile.save(update_fields=["subscription_status"])
```

If this is already what the code does, leave it.

Add an admin-side helper: when an admin sets status to "rejected" via the
**form** (not the bulk action), the `admin_note` should be required. Add a
form-level validation in `payments/admin.py` to enforce this.

### Subscribe view changes — `payments/views.py`

Update `subscribe(request)`:

- Check whether the user has a `rejected` latest submission. If yes, set a
  context var `last_rejected = <that submission>`.
- Honor querystring `?plan=monthly&method=bankak` for pre-selection: pass
  these values to the template as `prefill_plan` and `prefill_method`.
- Pass `last_rejected` to the template.

### Template changes — `templates/payments/subscribe.html`

At the top of the page (above the plan picker), render a rejection card if
`last_rejected` is set:

```html
{% if last_rejected %}
<div class="card p-5 mb-6" style="border-color: hsl(var(--destructive)); background: hsl(0 75% 97%);">
  <div class="flex items-start gap-3">
    <i data-lucide="alert-circle" class="h-5 w-5 mt-0.5" style="color: hsl(var(--destructive))"></i>
    <div class="flex-1">
      <h3 class="font-semibold mb-1" style="color: hsl(var(--destructive))">
        {% t "pay.rejected_title" %}
      </h3>
      <p class="text-sm">
        {% t_either "Your previous submission on" "تم رفض دفعتك السابقة بتاريخ" %}
        {{ last_rejected.created_at|date:"Y-m-d" }}
        {% t_either "was rejected." "" %}
      </p>
      {% if last_rejected.admin_note %}
      <p class="text-sm mt-2 italic">"{{ last_rejected.admin_note }}"</p>
      {% endif %}
      <p class="text-sm mt-2">{% t "pay.rejected_retry" %}</p>
    </div>
  </div>
</div>
{% endif %}
```

Pre-select plan and method in the radio inputs via `prefill_plan` /
`prefill_method`:

```html
<input type="radio" name="plan" value="monthly" required class="sr-only"
       {% if prefill_plan == "monthly" %}checked{% endif %}>
```

(Apply to all four plan/method radios.)

Trigger the JS card-highlighting on page load when there's a prefill so the
selection is visually obvious — fire `radio.dispatchEvent(new Event('change'))`
on the checked one in a `DOMContentLoaded` handler.

### Dashboard banner — `templates/lessons/dashboard.html`

Add a banner near the top (just below the welcome heading) when the user's
latest submission is rejected:

```html
{% if last_rejected %}
<div class="card p-5" style="border-color: hsl(var(--destructive)); background: hsl(0 75% 97%);">
  <div class="flex items-start justify-between gap-3">
    <div class="flex items-start gap-3 flex-1">
      <i data-lucide="alert-circle" class="h-5 w-5 mt-0.5" style="color: hsl(var(--destructive))"></i>
      <div>
        <h3 class="font-semibold mb-1">{% t "pay.rejected_title" %}</h3>
        {% if last_rejected.admin_note %}
        <p class="text-sm italic mb-2">"{{ last_rejected.admin_note }}"</p>
        {% endif %}
        <p class="text-sm text-muted-foreground">{% t "pay.rejected_retry" %}</p>
      </div>
    </div>
    <a href="{% url 'subscribe' %}?plan={{ last_rejected.plan }}&method={{ last_rejected.method }}"
       class="btn btn-hero shrink-0">
      {% t "pay.try_again" %}
    </a>
  </div>
</div>
{% endif %}
```

### Dashboard view changes — `lessons/views.py`

Update `dashboard(request)` to compute `last_rejected`: the user's most
recent `PaymentSubmission` if its status is `"rejected"`, otherwise `None`.

```python
last_rejected = (request.user.payment_submissions
                 .filter(status="rejected")
                 .order_by("-created_at")
                 .first())
# Only show the banner if the rejected one is also the very latest
latest = request.user.payment_submissions.order_by("-created_at").first()
if latest and latest.status != "rejected":
    last_rejected = None
```

Pass `last_rejected` to the template context.

### Same for history page — `templates/payments/history.html`

The history page already lists rejection rows with their status badge.
Tweak to also surface the `admin_note` in italic underneath each rejected
row. (The existing "if s.admin_note" branch likely covers it — confirm and
make sure the italic styling is decent.)

### i18n strings — add to `core/translations.py`

```python
"pay.rejected_title":  {"en": "Your last payment was rejected",
                        "ar": "تم رفض دفعتك الأخيرة"},
"pay.rejected_retry":  {"en": "Please review the note above and submit a new transfer screenshot.",
                        "ar": "يرجى مراجعة الملاحظة أعلاه وإرسال لقطة شاشة جديدة للتحويل."},
"pay.try_again":       {"en": "Try again",   "ar": "حاول مرة أخرى"},
```

## Acceptance criteria

A reviewer should be able to:

1. Sign in as a student, submit a payment, then sign in as admin.
2. As admin, open the submission in `/admin/payments/`, set status to
   "rejected", fill in `admin_note` ("Wrong amount — you sent 5,000 SDG
   but the plan is 8,000 SDG"), and save. The form requires the note.
3. Sign back in as the student, visit `/dashboard/` → see a red rejection
   banner with the note and a "Try again" button.
4. Click "Try again" → land on `/payments/?plan=monthly&method=bankak`
   with the rejection card up top, the monthly + bankak radios already
   selected, and the visual selection highlight on those cards.
5. Submit a new screenshot → the dashboard banner disappears (status moves
   to "pending" again).
6. As admin, approve the new submission → user is "active" with no banner.
7. Visit `/payments/history/` → see both rows: the rejected one with the
   admin_note shown in italic, and the approved one with the green badge.
8. Verify `Profile.subscription_status` is `"inactive"` after the rejection
   (because no other submissions are pending).

`python manage.py check` clean.

## Out of scope

- No email notification when a payment is rejected (separate prompt).
- No in-app inbox / messages system.
- No refund flow — these are pre-payment rejections, nothing to refund.
- No appeal / dispute tooling.

## Style guide

- The destructive (red) accent uses inline styles because we don't have a
  pre-made `.card-destructive` class. Stick with inline `hsl(var(--destructive))`
  to keep it consistent. If you'd rather, add a `.card-destructive` class
  to `static/css/onlenco.css` and use that.
- Lucide icon: `alert-circle` for rejection. Reuse `clock` for pending and
  `check-circle-2` for approved (already used elsewhere in the project).
- The rejection card in `subscribe.html` should NOT visually compete with
  the plan picker below it — use lighter typography and don't overuse bold.

## What to deliver

A patched `onlenco_django.zip` with:

- `payments/models.py` `reject()` audited (or unchanged if already correct)
- `payments/admin.py` enforcing `admin_note` required when rejecting via form
- `payments/views.py` updated `subscribe` view (last_rejected + prefill)
- `lessons/views.py` updated `dashboard` view (last_rejected)
- Templates updated: `subscribe.html` (rejection card + prefill),
  `dashboard.html` (rejection banner), `history.html` (admin_note styling)
- New i18n strings

`python manage.py check` clean. The 8 acceptance criteria pass.

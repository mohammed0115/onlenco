# 07 — Admin Analytics Dashboard

## Context

The original Onlenco technical doc says admin should "manage users, content,
payments, and analytics". The Django port shipped users / content / payments
admin via Django's built-in `/admin/`, but **analytics** is missing. This
prompt adds a custom analytics page with the metrics that matter for an
early-stage learning platform.

Project conventions:
- Tailwind via Play CDN + `static/css/onlenco.css`.
- Component classes available: `.btn`, `.btn-hero`, `.btn-outline`, `.card`,
  `.badge`, `.badge-secondary`, `.badge-outline`, `.badge-popular`.
- Lucide icons via `<i data-lucide="..."></i>`.
- Profile.is_admin check available; admins are users with `profile.role == "admin"`
  or `is_staff=True`.

## Goal

Add an `analytics` Django app with a single dashboard page at
`/admin-analytics/` accessible only to admin users. It should show
live-computed metrics from the database — no caching needed at this scale —
broken into four sections: Acquisition, Activation, Retention, Revenue.

Use Chart.js via CDN for the charts. No backend chart libraries.

## Spec

### Permissions decorator — `analytics/decorators.py`

A `@admin_required` decorator that:
- 302 redirects to `LOGIN_URL` if anonymous
- Returns a 403 if logged in but not admin (`profile.is_admin` is False)
- Otherwise calls the view

### View — `analytics/views.py`

**`analytics_dashboard(request)`** — `GET /admin-analytics/`
- `@admin_required`
- Compute these metrics (all from DB queries — keep them simple, no caching):

**Acquisition**
- Total users
- New users today / this week / this month (use `created_at` on Profile or
  `date_joined` on User — pick whichever exists; the project uses Profile)
- New users daily for the last 30 days → time series for a Chart.js line
  chart

**Activation**
- Users who completed placement (`placement_completed=True`)
- Activation rate (% completed of total)
- Distribution of CEFR levels among placement-completed users (pie chart)

**Retention** (light version since we don't have lots of activity yet)
- DAU / WAU / MAU based on `last_login` on User
- Returning users (logged in more than 1 day apart) — count

**Revenue**
- Total revenue this month: SUM `amount_sdg` from approved `PaymentSubmission`
  rows whose `reviewed_at >= start_of_month`
- Total revenue all-time
- Pending payments awaiting verification (count + total SDG)
- Approval rate (% approved of all reviewed)
- Most popular plan (monthly vs quarterly) and method (bankak/fawry/ocash)

Pass these to the template as a single `metrics` dict.

For the line chart data, build a list of `{date, count}` for the last 30
days, filling in zeros for days with no signups.

### URLs — `analytics/urls.py`

```python
urlpatterns = [
    path("", views.analytics_dashboard, name="analytics"),
]
```

Mount in `onlenco/urls.py`: `path("admin-analytics/", include("analytics.urls"))`.

### Template — `templates/analytics/dashboard.html`

A single big page. Layout:

1. **Top header** — "Analytics" title, last-updated timestamp, "Open Django
   admin" link in the corner (`/admin/`).
2. **KPI strip** — 6 stat cards across the top: Total users, Placement done,
   MAU, Active subs, Revenue this month, Pending payments. Each card shows
   the number large, label small, and a Lucide icon in the corner.
3. **Charts row** — 2-column grid:
   - Left: "New users (last 30 days)" — Chart.js `line` chart
   - Right: "CEFR level distribution" — Chart.js `doughnut` chart
4. **Tables row** — 2-column grid:
   - Left: "Top plans" — small bar chart or simple table
   - Right: "Top payment methods" — small bar chart or simple table
5. **Recent payments** — 10 most recent `PaymentSubmission` rows with status
   badges, linking to the admin change page for each.

Include Chart.js via CDN: `<script src="https://cdn.jsdelivr.net/npm/chart.js"></script>`.

Initialize charts inline in a `<script>` block. Use the project's color
tokens — read `getComputedStyle(document.documentElement).getPropertyValue('--secondary')`
etc. so charts pick up the design system.

### i18n strings — add to `core/translations.py`

Admin pages can stay English-only since admins are likely fluent — but for
consistency, add a few keys you'll use prominently:

```python
"analytics.title":      {"en": "Analytics",            "ar": "التحليلات"},
"analytics.users":      {"en": "Total users",          "ar": "إجمالي المستخدمين"},
"analytics.placement":  {"en": "Placement done",       "ar": "اختبارات منجزة"},
"analytics.mau":        {"en": "Monthly active",       "ar": "نشطون شهرياً"},
"analytics.active_subs":{"en": "Active subscriptions", "ar": "اشتراكات نشطة"},
"analytics.revenue":    {"en": "Revenue this month",   "ar": "الإيرادات هذا الشهر"},
"analytics.pending":    {"en": "Pending payments",     "ar": "مدفوعات قيد المراجعة"},
"analytics.signups_30d":{"en": "New users (last 30 days)",
                         "ar": "المستخدمون الجدد (آخر 30 يوماً)"},
"analytics.cefr_dist":  {"en": "CEFR level distribution",
                         "ar": "توزيع المستويات"},
"analytics.recent_pay": {"en": "Recent payments",      "ar": "المدفوعات الأخيرة"},
```

### Header link

Add a small "📊 Analytics" link in `_app_header.html`, **shown only to admins**:

```html
{% if request.user.profile.is_admin %}
  <a href="{% url 'analytics' %}" class="btn btn-ghost" style="height:2.25rem;font-size:0.8125rem">
    <i data-lucide="bar-chart-3" class="h-4 w-4"></i>
    Analytics
  </a>
{% endif %}
```

### Optional: management command

Add `analytics/management/commands/print_metrics.py` that prints the same
KPIs to stdout. Useful for cron/email reports later. Keep it short.

## Acceptance criteria

A reviewer should be able to:

1. Sign in as the seeded admin (`admin@onlenco.local`).
2. See the new "📊 Analytics" link in the app header.
3. Click it → land on `/admin-analytics/` with all 6 KPI cards populated.
4. See the 30-day line chart rendering even on a fresh DB (will mostly be
   zeros, but renders correctly).
5. See the CEFR doughnut chart populated if any users have completed
   placement; if none, show an empty-state message.
6. See recent payments table with status badges.
7. Sign out and try `/admin-analytics/` anonymously → redirect to login.
8. Sign in as a non-admin student and visit `/admin-analytics/` → 403.
9. Run `python manage.py print_metrics` → see the same numbers in the
   terminal.

`python manage.py check` clean.

## Out of scope

- No date-range picker — fixed windows (today / 7d / 30d / all-time).
- No CSV export.
- No realtime updates / websockets.
- No A/B test tracking.
- No funnel charts (signup → placement → first lesson → first payment).
- No cohort analysis.

## Style guide

- KPI card: `.card`, `p-5`, big number in `font-display text-4xl font-bold`,
  small label in `text-sm text-muted-foreground` below, Lucide icon in the
  top-right corner in a `gradient-sunset` rounded square.
- Chart cards: same `.card` shell, `p-6`, `h-64` chart container.
- Use Chart.js defaults but override colors with the project tokens. Disable
  the legend on the line chart (it's a single series), keep it on the
  doughnut.
- Table: zebra striping with `.bg-muted/50` on alternate rows, no borders.

## What to deliver

A patched `onlenco_django.zip` with:

- New `analytics` app added to `INSTALLED_APPS`
- `decorators.py`, `views.py`, `urls.py`, template
- Admin-only header link
- Optional `print_metrics` command
- New i18n strings

`python manage.py check` passes. Visiting as admin shows real numbers from
the seeded DB.

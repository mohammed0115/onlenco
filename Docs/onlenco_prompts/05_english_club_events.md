# 05 — Weekly English Club Events

## Context

This task adds the **Weekly English Club** to the **Onlenco** Django project —
listed as a feature on the marketing page but not yet built. Subscribed
students see upcoming live sessions over Google Meet, RSVP, and admins
record attendance after each session.

Project conventions:
- `{% load i18n_dict %}` plus `{% t "key" %}` and `{% t_either "en" "ar" %}`.
- Tailwind via Play CDN + `static/css/onlenco.css`.
- Component classes: `.btn`, `.btn-hero`, `.btn-outline`, `.card`, `.badge`.
- Lucide icons via `<i data-lucide="..."></i>`.
- Subscription gate: `request.user.profile.is_subscribed`.

## Goal

Add a `club` Django app with `ClubEvent` and `ClubRSVP` models, a public
events list, a per-event detail page with the Google Meet link revealed
only to subscribed RSVPs, and an admin attendance recording action.

## Spec

### Models — `club/models.py`

Use the existing CEFR enum: `from accounts.models import CEFR_CHOICES`.

**`ClubEvent`**
- `title = CharField(max_length=200)`
- `topic = CharField(max_length=200)` — short topic blurb
- `description = TextField(blank=True)`
- `host_name = CharField(max_length=120, blank=True)`
- `level_min = CharField(max_length=2, choices=CEFR_CHOICES, default="A2")` —
  recommended minimum CEFR level
- `level_max = CharField(max_length=2, choices=CEFR_CHOICES, default="C1")`
- `starts_at = DateTimeField()`
- `duration_minutes = PositiveSmallIntegerField(default=60)`
- `meet_url = URLField(blank=True)` — Google Meet link, revealed close to start
- `capacity = PositiveSmallIntegerField(default=20)` — soft cap for RSVPs
- `is_published = BooleanField(default=True)`
- `created_at = DateTimeField(auto_now_add=True)`
- Meta `ordering = ["starts_at"]`
- Property `is_past`: `starts_at < timezone.now()`
- Property `is_full`: `rsvps.filter(status="going").count() >= capacity`
- Property `ends_at`: `starts_at + timedelta(minutes=duration_minutes)`

**`ClubRSVP`**
- `event = ForeignKey(ClubEvent, on_delete=CASCADE, related_name="rsvps")`
- `user = ForeignKey(settings.AUTH_USER_MODEL, on_delete=CASCADE,
    related_name="club_rsvps")`
- `status = CharField(max_length=10, choices=[
    ("going","Going"), ("maybe","Maybe"), ("cancelled","Cancelled")],
    default="going")`
- `attended = BooleanField(default=False)` — set by admin after the session
- `created_at = DateTimeField(auto_now_add=True)`
- `updated_at = DateTimeField(auto_now=True)`
- Meta `unique_together = [("event","user")]`, `ordering = ["-created_at"]`

### Views & URLs — `club/views.py`, `club/urls.py`

**`event_list(request)`** — `GET /club/`
- `@login_required`. Subscription required → otherwise show preview cards
  (titles + dates) with a subscribe CTA and no RSVP buttons.
- Default: upcoming events (where `starts_at >= now`), ordered by `starts_at`.
- Tab nav: "Upcoming" / "Past" — `?tab=past` shows past events.
- Show RSVP status on each card if the user has one.

**`event_detail(request, pk)`** — `GET /club/<pk>/`
- `@login_required`, subscription required → otherwise redirect to
  `subscribe` with a `messages.warning`.
- 404 if not published.
- Show full info: title, topic, description, host, level range, when (in
  the user's local time — render in UTC and let the browser format), how
  long, capacity used / total.
- Reveal `meet_url` only when:
  - the user has a "going" RSVP, AND
  - the event starts within the next 24 hours.
- If outside that window, show "The Meet link will appear here 24 hours
  before the session."

**`rsvp(request, pk)`** — `POST /club/<pk>/rsvp/`
- `@login_required`, `@require_POST`, subscription required.
- Read `status` from POST: "going", "maybe", or "cancelled".
- Reject "going" if the event is already at capacity AND the user doesn't
  already have a "going" RSVP (so they can switch from maybe→going only if
  there's room).
- Upsert the `ClubRSVP` row.
- Redirect back to the event detail with a success message.

URLs:
```python
urlpatterns = [
    path("", views.event_list, name="club"),
    path("<int:pk>/", views.event_detail, name="club_event"),
    path("<int:pk>/rsvp/", views.rsvp, name="club_rsvp"),
]
```
Mount in `onlenco/urls.py`: `path("club/", include("club.urls"))`.

### Templates

**`templates/club/list.html`**
- Header: "Weekly English Club", subtitle.
- Tab nav: Upcoming / Past (active tab styling).
- Grid of event cards, 1 col mobile, 2 desktop. Each card:
  - Big date pill (e.g. "Sat 12 Apr · 7:00 PM")
  - Title, topic, host
  - Level range chip ("A2 – B2")
  - Capacity bar ("12/20 going") with a Tailwind bg progress bar
  - Action button: "RSVP" if no RSVP yet, "Going ✓" / "Maybe" / "Cancelled"
    badges if they already have one
  - Link to the detail page

**`templates/club/detail.html`**
- Big header card with title, topic, host avatar/name, level range, time
  + duration.
- A countdown component (small, JS-driven) that updates every minute showing
  "Starts in 2h 14m" — once it hits zero, swap to "Live now" with a pulse
  animation. Pure vanilla JS.
- RSVP form: three buttons (Going / Maybe / Cancel). Submit via POST to
  `club_rsvp` with `status` hidden.
- Capacity bar.
- "Join the Meet" button — visible only when meet_url is revealed (per
  the rule above). Big primary button. Opens in a new tab.
- Description below.
- "Back to club" link top-left.

**Use `_app_header.html`** on both.

### Admin — `club/admin.py`

- `ClubEvent` admin: `list_display = ("title", "starts_at", "level_min",
  "level_max", "capacity", "rsvp_count", "is_published")`,
  `list_filter = ("is_published", "level_min")`,
  `search_fields = ("title", "topic", "host_name")`. Add a `rsvp_count`
  method on the admin class.
- Add `ClubRSVP` as `TabularInline` on `ClubEvent` (read-mostly: only
  `attended` is editable).
- Admin action **"Mark all 'going' RSVPs as attended"** on `ClubEvent`:
  bulk update `attended=True` for every `going` RSVP for the selected
  events. Display a success message with the count.

### Seed data

In `seed_demo.py`, create 4 sample events:
- 2 upcoming (one tomorrow, one next week)
- 1 in 3 hours (so the Meet link reveals immediately for testing)
- 1 in the past (for the "Past" tab)

Use a placeholder `meet_url = "https://meet.google.com/example-abc-def"`.

### Dashboard integration

Add a "Next club event" widget on `templates/lessons/dashboard.html` that
shows the soonest upcoming `ClubEvent` (if any) the user has access to.
Include the title, when it is, an RSVP status, and a link to the detail page.

### i18n strings — add to `core/translations.py`

```python
"club.title":       {"en": "Weekly English Club",         "ar": "نادي الإنجليزية الأسبوعي"},
"club.subtitle":    {"en": "Live discussions over Google Meet on real topics.",
                     "ar": "نقاشات حية عبر Google Meet حول مواضيع واقعية."},
"club.upcoming":    {"en": "Upcoming",                    "ar": "القادمة"},
"club.past":        {"en": "Past",                        "ar": "السابقة"},
"club.empty_up":    {"en": "No upcoming events yet — check back soon.",
                     "ar": "لا توجد جلسات قادمة بعد — تابع لاحقاً."},
"club.empty_past":  {"en": "No past events yet.",         "ar": "لا توجد جلسات سابقة بعد."},
"club.host":        {"en": "Hosted by",                   "ar": "يستضيفها"},
"club.starts":      {"en": "Starts in",                   "ar": "تبدأ خلال"},
"club.live":        {"en": "Live now",                    "ar": "البث مباشر الآن"},
"club.join":        {"en": "Join the Meet",               "ar": "انضم إلى الجلسة"},
"club.rsvp.going":  {"en": "Going",                       "ar": "حضور"},
"club.rsvp.maybe":  {"en": "Maybe",                       "ar": "ربما"},
"club.rsvp.cancel": {"en": "Cancel RSVP",                 "ar": "إلغاء"},
"club.full":        {"en": "Full",                        "ar": "ممتلئ"},
"club.capacity":    {"en": "going",                       "ar": "مسجل"},
"club.link_later":  {"en": "The Meet link will appear here 24 hours before the session.",
                     "ar": "سيظهر رابط الجلسة هنا قبل 24 ساعة من بدئها."},
"club.locked":      {"en": "Subscribe to join the English Club.",
                     "ar": "اشترك للانضمام إلى نادي الإنجليزية."},
```

## Acceptance criteria

A reviewer should be able to:

1. As a subscribed user, click the "Next club event" widget on the dashboard.
2. Land on `/club/` with the upcoming-events tab active and 3 events listed.
3. Click "Past" → see the past-events tab with 1 event.
4. Click into an upcoming event → see the detail page with countdown.
5. RSVP "going" → button updates, capacity bar increments.
6. RSVP "maybe" → status updates, capacity decrements.
7. For the event 3 hours away, see the Meet link button visible.
8. For the event next week, see "The Meet link will appear here 24 hours
   before the session." instead.
9. As an unsubscribed user, hitting `/club/` shows preview cards with no
   RSVP button.
10. In `/admin/`, select a past event, run the "Mark all 'going' RSVPs as
    attended" bulk action → all those RSVPs flip to attended=True.

`python manage.py check` and `python manage.py migrate` clean.

## Out of scope

- No automated reminder emails (separate prompt).
- No calendar export (.ics files).
- No video recording / replay storage.
- No Google Meet API integration — `meet_url` is a plain URL field that
  admins paste in.
- No discussion threads or chat per event.

## Style guide

- Date pill: gradient-sunset background, white text, 0.75rem padding,
  rounded-xl. Show day-of-week + date + time stacked.
- Capacity bar: thin (4px tall), rounded, `bg-secondary` filled portion on
  `bg-muted` track.
- Live badge: red dot + "Live now" — use `bg-red-500` directly with a CSS
  `@keyframes pulse` already in the codebase, or define one.
- "Join the Meet" button: full-width on mobile, inline on desktop, prominent
  `.btn-hero` style with a Lucide `video` icon.

## What to deliver

A patched `onlenco_django.zip` with:

- New `club` app added to `INSTALLED_APPS`
- `ClubEvent` and `ClubRSVP` models with one migration
- Views, URLs, templates, admin
- "Next club event" widget added to the dashboard
- Seeded 4 sample events via `seed_demo`
- New i18n strings

`python manage.py check` passes. The dashboard shows the upcoming event
widget; `/club/` lists 3 upcoming events.

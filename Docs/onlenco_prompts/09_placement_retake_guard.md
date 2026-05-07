# 09 — Placement Test "Already Taken" Guard

## Context

The **Onlenco** placement test currently lets a user re-take the test as
many times as they want, and each new submission overwrites their
`Profile.cefr_level`. There's no friction. This prompt adds a sensible
guard: once a user has taken the test, they see their existing result
instead of the form, and have to explicitly click "Retake" to start over.

Project conventions:
- `{% load i18n_dict %}` plus `{% t "key" %}` and `{% t_either "en" "ar" %}`.
- Tailwind via Play CDN + `static/css/onlenco.css`.
- Component classes available: `.btn`, `.btn-hero`, `.btn-outline`, `.card`,
  `.badge`.
- The placement view is at `placement/views.py` — `placement(request)`.
- The model `PlacementResult` already exists with `created_at`, `level`,
  `feedback`, etc.

## Goal

When a user with `placement_completed=True` visits `/placement/`, show
their most recent result and history (not the form). Add a "Retake" button
that, when clicked, sets a session flag and shows the form. Only after
submitting the new attempt does the result actually update.

## Spec

### View changes — `placement/views.py`

Restructure `placement(request)` like this:

1. If `request.method == "POST"` → existing behaviour: validate, score,
   save the new `PlacementResult`, update the profile, render the result.
   Also clear any `placement_retake` session flag.
2. Otherwise (GET):
   - If `profile.placement_completed` is False → render the form (current
     behaviour for first-time users).
   - If completed AND `request.session.get("placement_retake")` is True →
     render the form (so the retake flow works).
   - Otherwise → render the new "your result" page showing:
     - The user's current CEFR level (big hero number, same style as the
       current result page)
     - The most recent feedback string
     - A small history table: date · level · scores
     - A "Retake the test" button

When the user clicks "Retake the test", it should be a `POST` form to a
new view `start_retake` that sets `request.session["placement_retake"] = True`
and redirects back to `/placement/`. (Using POST + redirect avoids letting
crawlers / pre-fetchers trigger a retake state.)

Add a route:
```python
path("retake/", views.start_retake, name="placement_retake"),
```

`start_retake(request)`:
- `@login_required`
- `@require_POST`
- Set the session flag, redirect to `placement`.

### Template changes

**Update `templates/placement/placement.html`** so the existing two states
(form and result-just-now) become three states:

1. **No previous result + no retake flag** → render form (current behavior).
2. **Form just submitted (POST)** → render the "result" hero card (current
   behavior, with a "back to dashboard" link).
3. **Has a saved result + no retake flag** → new template
   `templates/placement/already_taken.html`:

```html
{% extends "base.html" %}
{% load i18n_dict %}
{% block body %}
<div class="min-h-screen bg-muted/20">
  {% include "_app_header.html" %}
  <main class="container py-10" style="max-width:42rem">

    <div class="card gradient-hero text-primary-foreground border-0 shadow-elegant p-10 text-center mb-6">
      <p class="mb-2" style="opacity:0.9">{% t "pl.your_level" %}</p>
      <div class="font-display text-7xl font-bold mb-4">{{ profile.cefr_level }}</div>
      {% if latest %}
      <p class="max-w-md mx-auto leading-relaxed mb-6" style="opacity:0.9">
        {{ latest.feedback }}
      </p>
      <p class="text-xs" style="opacity:0.7">
        {% t_either "Last taken" "آخر اختبار" %}: {{ latest.created_at|date:"Y-m-d" }}
      </p>
      {% endif %}
    </div>

    <div class="flex flex-wrap gap-3 justify-center mb-10">
      <a href="{% url 'dashboard' %}" class="btn btn-hero btn-lg">
        {% t "pl.continue" %} <i data-lucide="arrow-right" class="h-4 w-4 rtl-flip"></i>
      </a>
      <form method="post" action="{% url 'placement_retake' %}">
        {% csrf_token %}
        <button type="submit" class="btn btn-outline btn-lg">
          <i data-lucide="rotate-ccw" class="h-4 w-4"></i>
          {% t "pl.retake" %}
        </button>
      </form>
    </div>

    {% if history %}
    <h2 class="font-display text-2xl font-bold mb-4">{% t "pl.history" %}</h2>
    <div class="card divide-y divide-border">
      {% for r in history %}
      <div class="p-4 flex items-center justify-between gap-4">
        <div>
          <div class="font-semibold">{{ r.level }}</div>
          <div class="text-xs text-muted-foreground">{{ r.created_at|date:"Y-m-d H:i" }}</div>
        </div>
        <div class="text-sm text-muted-foreground">
          {% t_either "Written" "كتابي" %}: {{ r.written_score|default:"—" }} ·
          {% t_either "Speaking" "شفهي" %}: {{ r.speaking_score|default:"—" }}
        </div>
      </div>
      {% endfor %}
    </div>
    {% endif %}

  </main>
</div>
{% endblock %}
```

Pass `latest` (the most recent `PlacementResult`) and `history` (up to 10
prior results, newest first) from the view.

### Retake-warning UI tweak

When a user has been redirected back into the form via the retake flag, add
a small banner at the top of the placement form: "You're retaking the test.
Your level will only update if you submit." Use a soft `.card` with a
Lucide `info` icon. Add an i18n key for it.

### i18n strings — add to `core/translations.py`

```python
"pl.your_level": {"en": "Your CEFR level is",  "ar": "مستواك في CEFR هو"},
"pl.retake":     {"en": "Retake the test",     "ar": "إعادة الاختبار"},
"pl.history":    {"en": "Past attempts",       "ar": "المحاولات السابقة"},
"pl.retaking":   {"en": "You're retaking the test. Your level will only update if you submit.",
                  "ar": "أنت تعيد الاختبار. مستواك سيتحدث فقط عند الإرسال."},
```

## Acceptance criteria

A reviewer should be able to:

1. Sign in as a fresh user, complete the placement test → land on the
   result page (current behavior).
2. Click "Continue to lessons" or navigate to `/dashboard/`, then click
   "Take placement test" again or navigate to `/placement/` →
   **see the new "your level" page** with their CEFR level, feedback, and
   history (just the 1 entry).
3. Click "Retake the test" (which POSTs to `/placement/retake/`) → land on
   the form with a "You're retaking the test…" banner.
4. Refresh the page on the form → still on the form (session flag persists).
5. Submit the new attempt with worse answers → the new attempt is saved AND
   the profile's `cefr_level` is updated to the new level. The session
   flag is cleared.
6. Visit `/placement/` again → see the updated level on the "your level"
   page, AND a 2-row history.
7. Try to navigate to `/placement/retake/` via GET → 405 Method Not Allowed.

`python manage.py check` clean.

## Out of scope

- No "you can only retake once per N days" rate limit.
- No payment gate on retakes.
- No comparison view ("you went from B1 → B2!").
- No emailed result.

## Style guide

- The "your level" page mirrors the current "just submitted" hero card so
  users feel like they're seeing the same component, just persisted.
- Buttons: primary "Continue to lessons" (`.btn-hero`), secondary
  "Retake the test" (`.btn-outline`) with a `rotate-ccw` Lucide icon.
- History table: minimal, no styling chrome — just rows.

## What to deliver

A patched `onlenco_django.zip` with:

- Updated `placement/views.py` (3 states + new `start_retake` view)
- Updated `placement/urls.py` with the `placement_retake` route
- New template `templates/placement/already_taken.html`
- Small banner addition to `templates/placement/placement.html` for the
  retaking state
- New i18n strings in `core/translations.py`

`python manage.py check` clean. The 7 acceptance criteria all pass on a
fresh DB after `seed_demo`.

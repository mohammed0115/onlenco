# 01 — Lesson Detail Page + Quizzes

## Context

This task extends the **Onlenco** Django project (a port of a React+Supabase
English learning platform aimed at Sudanese learners). The project already
has a `lessons` app with a `Lesson` model (`title`, `description`, `skill`,
`level`, `video_url`, `duration_minutes`, `sort_order`) and a dashboard at
`/dashboard/` that shows lesson cards. **Right now the cards are decorative —
clicking one does nothing.** This prompt fixes that and adds quizzes.

The project follows specific patterns:

- Templates use `{% load i18n_dict %}` plus `{% t "key" %}` and
  `{% t_either "en" "ar" %}` helpers.
- Styling uses Tailwind via Play CDN plus `static/css/onlenco.css` design
  tokens. Component classes: `.btn`, `.btn-hero`, `.btn-outline`, `.btn-ghost`,
  `.btn-glass`, `.btn-lg`, `.card`, `.badge`, `.badge-secondary`,
  `.badge-outline`, `.badge-popular`, `.input`, `.label`, `.radio-card`.
- Lucide icons via `<i data-lucide="..."></i>`.
- Auth: `@login_required` from `django.contrib.auth.decorators`.
- Subscription gate: `request.user.profile.is_subscribed` returns True/False.

## Goal

Make lesson cards clickable, render a per-lesson detail page with the
embedded video and an optional multi-question quiz, and track which lessons
each user has completed.

## Spec

### Models — `lessons/models.py`

Add three models:

**`Quiz`** — one quiz per lesson (1-1)
- `lesson = OneToOneField(Lesson, on_delete=CASCADE, related_name="quiz")`
- `pass_score = PositiveSmallIntegerField(default=70)` — % required to pass

**`Question`** — multiple choice
- `quiz = ForeignKey(Quiz, on_delete=CASCADE, related_name="questions")`
- `prompt = TextField()` — the question text
- `choice_a = CharField(max_length=200)`
- `choice_b = CharField(max_length=200)`
- `choice_c = CharField(max_length=200, blank=True)`
- `choice_d = CharField(max_length=200, blank=True)`
- `correct = CharField(max_length=1, choices=[("a","A"),("b","B"),("c","C"),("d","D")])`
- `sort_order = PositiveSmallIntegerField(default=0)`
- Meta `ordering = ["sort_order", "id"]`

**`LessonProgress`** — per-user tracking
- `user = ForeignKey(settings.AUTH_USER_MODEL, on_delete=CASCADE, related_name="lesson_progress")`
- `lesson = ForeignKey(Lesson, on_delete=CASCADE, related_name="progress_entries")`
- `video_completed = BooleanField(default=False)`
- `quiz_score = PositiveSmallIntegerField(null=True, blank=True)` — 0..100
- `quiz_passed = BooleanField(default=False)`
- `last_attempt_at = DateTimeField(auto_now=True)`
- `completed_at = DateTimeField(null=True, blank=True)`
- Meta `unique_together = [("user", "lesson")]`
- Property `is_complete`: returns True iff `video_completed and (no quiz OR quiz_passed)`

### Views & URLs — `lessons/views.py`, `lessons/urls.py`

Add three views:

**`lesson_detail(request, pk)`** — `GET /dashboard/lessons/<pk>/`
- `@login_required`
- 404 if lesson doesn't exist
- If user is not subscribed → render the detail page in "preview" mode:
  description visible, video and quiz hidden behind a subscribe CTA
- If subscribed → render full detail with embedded video and a "Start quiz"
  button when `lesson.quiz` exists
- Get-or-create the user's `LessonProgress` row so we can show completion
  state in the template

**`mark_video_complete(request, pk)`** — `POST /dashboard/lessons/<pk>/video-done/`
- `@login_required`, `@require_POST`
- 403 if not subscribed
- Set `progress.video_completed = True` and update `completed_at` if
  `is_complete`. Redirect back to the lesson detail with a success message.

**`quiz_attempt(request, pk)`** — `GET/POST /dashboard/lessons/<pk>/quiz/`
- `@login_required`
- 403 if not subscribed
- 404 if lesson has no quiz
- GET: render the quiz form (radio buttons per question)
- POST: grade the answers. Compute `score = correct_count * 100 / total`.
  Update `LessonProgress.quiz_score`, `quiz_passed = score >= pass_score`,
  and `completed_at` if now `is_complete`. Redirect to a result page
  showing score + pass/fail + per-question feedback.

Add to `lessons/urls.py`:
```python
path("lessons/<int:pk>/", views.lesson_detail, name="lesson_detail"),
path("lessons/<int:pk>/video-done/", views.mark_video_complete, name="lesson_video_done"),
path("lessons/<int:pk>/quiz/", views.quiz_attempt, name="lesson_quiz"),
```

### Templates

**`templates/lessons/detail.html`** — embeds an iframe for `video_url`
(YouTube/Vimeo direct embed; if the URL is a YouTube watch link, convert it
to `/embed/`), shows lesson title/level/skill/duration, a "Mark video as
watched" button (POSTs to `lesson_video_done`), and (if quiz exists) a
"Start the quiz" button to `lesson_quiz`. Use `_app_header.html`.

If the user isn't subscribed: hide video and quiz, show a "Subscribe to
unlock this lesson" card with a button to `subscribe`.

**`templates/lessons/quiz.html`** — renders questions with radio inputs.
Uses `.radio-card` styling for choices (already defined in `onlenco.css`).
On submit, POSTs the answers as form fields named `q_<question_id>`.

**`templates/lessons/quiz_result.html`** — big score display, pass/fail badge,
list of questions with a green check or red X next to each, the correct
answer highlighted on incorrect ones. Buttons: "Retake the quiz" (back to
`lesson_quiz`) and "Back to lesson" (back to `lesson_detail`).

**Update `templates/lessons/dashboard.html`** so each lesson card becomes
an `<a href="{% url 'lesson_detail' l.pk %}">` instead of a `<div>`. If
`LessonProgress` exists for that lesson and `is_complete`, show a small
green "Completed" badge in the corner.

### Admin — `lessons/admin.py`

- Register `Quiz` with `list_display = ("lesson", "pass_score", "question_count")`.
  Add a custom `question_count` method.
- Register `Question` inline under `Quiz` (use `admin.TabularInline`).
- Register `LessonProgress` with `list_display = ("user", "lesson",
  "video_completed", "quiz_score", "quiz_passed", "completed_at")`,
  `list_filter = ("video_completed", "quiz_passed")`,
  `search_fields = ("user__email", "lesson__title")`,
  `readonly_fields` for everything (admins shouldn't edit student progress
  by hand).

### Seed data

Update `lessons/management/commands/seed_demo.py` to add a 3-question quiz
to the first 4 lessons. Keep questions short (one per skill area):
- A grammar MCQ
- A vocabulary MCQ
- A reading-comprehension MCQ
Don't bother adding quizzes to all 12; 4 is enough to demo.

### i18n strings — add to `core/translations.py`

```python
"lesson.start":         {"en": "Start lesson",          "ar": "ابدأ الدرس"},
"lesson.video_done":    {"en": "Mark video as watched", "ar": "تم مشاهدة الفيديو"},
"lesson.quiz_start":    {"en": "Start the quiz",        "ar": "ابدأ الاختبار"},
"lesson.quiz_retake":   {"en": "Retake quiz",           "ar": "إعادة الاختبار"},
"lesson.back":          {"en": "Back to lesson",        "ar": "العودة للدرس"},
"lesson.completed":     {"en": "Completed",             "ar": "مكتمل"},
"lesson.locked":        {"en": "Subscribe to unlock this lesson", "ar": "اشترك لفتح هذا الدرس"},
"quiz.score":           {"en": "Your score",            "ar": "نتيجتك"},
"quiz.passed":          {"en": "Passed",                "ar": "ناجح"},
"quiz.failed":          {"en": "Try again",             "ar": "حاول مرة أخرى"},
"quiz.correct_answer":  {"en": "Correct answer",        "ar": "الإجابة الصحيحة"},
"quiz.q":               {"en": "Question",              "ar": "سؤال"},
```

## Acceptance criteria

A reviewer running the project should be able to:

1. Click a lesson card on the dashboard → land on a detail page with the
   embedded video.
2. As a non-subscribed user, see a "subscribe to unlock" card instead of the
   video.
3. Click "Mark video as watched" → page reloads, button disappears or is
   replaced with a "✓ Watched" indicator.
4. Click "Start the quiz" on a lesson that has a quiz → see 3 MCQ questions.
5. Submit the quiz → see a result page showing the score (e.g. "67%"),
   pass/fail status, and the correct answer for each question they got
   wrong.
6. Retake the quiz → score updates on `LessonProgress`.
7. Return to the dashboard → completed lessons show a green "Completed"
   badge.
8. In `/admin/`, create a Quiz with 5 inline Questions on a Lesson without
   leaving the page.

## Out of scope

- No video upload — `video_url` is a URL field; embed YouTube/Vimeo only.
- No timed quizzes, no question shuffling, no partial credit.
- No "next lesson" recommender.
- No certificates.

## Style guide

- Match the existing dashboard card style for lesson detail (gradient-card,
  shadow-elegant on hover, etc.).
- Use the `.btn-hero` style for primary actions, `.btn-outline` for secondary.
- Use Lucide icons: `play-circle`, `check-circle-2`, `circle-x`, `award`,
  `lock`.
- Quiz pass/fail: green for pass (`text-secondary` is the warm amber, use
  `text-emerald-600` from Tailwind directly, or a green inline color).
- Detail page width: `max-w-3xl mx-auto` — narrower than the dashboard.

## What to deliver

A patched `onlenco_django.zip` that:
- Adds `Quiz`, `Question`, `LessonProgress` models with a single new migration
- Adds the 3 new views and URL routes
- Adds the 3 new templates (detail, quiz, quiz_result) and updates dashboard
- Updates `lessons/admin.py` and `seed_demo.py`
- Adds the i18n strings to `core/translations.py`
- Passes `python manage.py check` and `python manage.py migrate` cleanly

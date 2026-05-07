# Onlenco Prompts (00 ? 12)
This file concatenates the prompts in `onlenco_prompts/` in numeric order for easy copy/paste.

---

<!-- BEGIN: 00_PROJECT_CONTEXT.md -->
# 00 — Project Context (shared)

> **Note:** Every numbered prompt in this directory inlines the essential bits
> of this context, so you usually don't need to paste this file separately.
> It exists as a single source of truth.

## What Onlenco is

Onlenco is an AI-powered English learning platform aimed at Sudanese learners.
It was originally prototyped as a React/Vite + Supabase app, then ported to
Django. The marketing page promises:

- AI placement test (CEFR A0–C2)
- AI voice tutor
- Structured video lessons across reading / writing / listening / speaking
- Weekly English Club over Google Meet
- Digital library
- Arabic–English dictionary
- Local payment via Bankak / Fawry / O-Cash

## Existing Django apps

| App | What it does |
|-----|--------------|
| `accounts` | `Profile` model (CEFR level, subscription, role), email-based signup/login, language-preference middleware |
| `core` | Public landing page, EN/AR translation dict, language switcher, 404 |
| `lessons` | `Lesson` model (`title`, `description`, `skill`, `level`, `video_url`, `duration_minutes`, `sort_order`), student dashboard at `/dashboard/` |
| `placement` | `PlacementResult` model + AI scoring service that calls any OpenAI-compatible endpoint, deterministic fallback when no key |
| `payments` | `PaymentSubmission` model, screenshot upload, admin approve/reject actions, subscription activation/extension |

## Existing patterns to match

- **Templates** use a `{% load i18n_dict %}` helper that gives `{% t "key" %}`
  (looks up an EN/AR pair from `core/translations.py`) and
  `{% t_either "english" "عربي" %}` for one-off labels.
- **Styling** uses Tailwind via the Play CDN (config in `templates/base.html`)
  plus `static/css/onlenco.css` for design tokens — HSL color vars, gradients,
  and component classes (`.btn`, `.btn-hero`, `.btn-outline`, `.btn-ghost`,
  `.btn-glass`, `.btn-lg`, `.card`, `.badge`, `.badge-secondary`,
  `.badge-outline`, `.badge-popular`, `.input`, `.label`, `.radio-card`).
- **Icons** are Lucide via UMD bundle: `<i data-lucide="check"></i>`.
- **Auth** uses Django's built-in User model with email as username; the
  `Profile` is auto-created via a `post_save` signal.
- **Login required** is a function decorator: `@login_required` from
  `django.contrib.auth.decorators`.
- **Admin** is registered with `@admin.register(Model)` and uses concise
  `list_display` + `list_filter` + `search_fields`.
- **Models** use `models.BigAutoField` for IDs (set by `DEFAULT_AUTO_FIELD`).
- **Migrations** are committed to git — every prompt that adds a model must
  also include the new migration file.

## Code style

- Type hints are used sparingly — match the existing style (none in views,
  some in pure-Python service modules).
- Docstrings on classes and public functions, none on obvious one-liners.
- Comments explain *why*, not *what*. Keep them short and well-placed.
- No bullet lists in docstrings; prefer prose.
- Keep imports grouped: stdlib, Django, third-party, local. Each group
  separated by a blank line.

## What NOT to add

- No new dependencies unless absolutely necessary. The current `requirements.txt`
  is `Django + Pillow + requests` — keep it that way.
- No HTMX, Alpine, React, or other frontend frameworks. Server-rendered HTML
  with vanilla JS for interactions, matching what's already there.
- No DRF / GraphQL. Plain Django views.
- No new auth backends. Use the existing email-as-username pattern.

## i18n

Add new translation keys to `core/translations.py` in the `DICT` dict.
Always include both `en` and `ar` entries. Use the same naming convention
as existing keys: `area.subarea.detail`, e.g. `tutor.title`, `library.book.read`.
<!-- END: 00_PROJECT_CONTEXT.md -->

---

<!-- BEGIN: 01_lesson_detail_and_quizzes.md -->
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
<!-- END: 01_lesson_detail_and_quizzes.md -->

---

<!-- BEGIN: 02_ai_voice_tutor.md -->
# 02 — AI Voice Tutor

## Context

This task adds the **AI Voice Tutor** to the **Onlenco** Django project — the
headline feature on the marketing page that the current build doesn't deliver.
The existing project already has an OpenAI-compatible chat client in
`placement/services.py` (called `assess()`); reuse the same pattern.

Project conventions:

- Templates use `{% load i18n_dict %}` plus `{% t "key" %}` and
  `{% t_either "en" "ar" %}` helpers.
- Tailwind via Play CDN + `static/css/onlenco.css` design tokens.
- Component classes available: `.btn`, `.btn-hero`, `.btn-outline`, `.card`, `.badge`.
- Lucide icons via `<i data-lucide="..."></i>`.
- AI config lives in `settings.py`: `AI_API_KEY`, `AI_API_BASE`, `AI_MODEL`.
- Subscription gate: `request.user.profile.is_subscribed`.

## Goal

Add a new `tutor` Django app that gives subscribed students a chat-style
conversation with an AI English coach. The student types (and optionally
records voice — see "Phase 2" below) in English; the tutor responds in
English with corrections, feedback, and follow-up questions tailored to the
student's CEFR level. Conversations persist so students can resume them.

## Spec

This prompt is split into two phases. **Phase 1 must be delivered.** Phase 2
is a stretch goal — implement only if straightforward.

### Phase 1 — text chat (required)

#### Models — `tutor/models.py`

**`TutorConversation`**
- `user = ForeignKey(settings.AUTH_USER_MODEL, on_delete=CASCADE, related_name="tutor_conversations")`
- `title = CharField(max_length=200, blank=True)` — auto-set from first message
- `topic = CharField(max_length=50, blank=True)` — optional ("travel",
  "job-interview", "small-talk", etc.) for prompt steering
- `created_at = DateTimeField(auto_now_add=True)`
- `updated_at = DateTimeField(auto_now=True)`
- Meta `ordering = ["-updated_at"]`

**`TutorMessage`**
- `conversation = ForeignKey(TutorConversation, on_delete=CASCADE, related_name="messages")`
- `role = CharField(max_length=10, choices=[("user","user"),("assistant","assistant")])`
- `content = TextField()`
- `created_at = DateTimeField(auto_now_add=True)`
- Meta `ordering = ["created_at"]`

#### Service — `tutor/services.py`

A `chat(conversation, user_message)` function that:

1. Looks up the user's CEFR level from `conversation.user.profile.cefr_level`
   (default to "B1" if not set).
2. Builds a system prompt that pins the tutor's behaviour:
   - Respond at or just slightly above the student's CEFR level
   - Always end with a short follow-up question
   - When the student makes a grammar error, gently correct it in a
     dedicated "Quick fix:" line, then continue the conversation
   - Stay in English unless the student writes in Arabic, in which case
     translate their question and answer in English
3. Constructs the message list: system prompt + the last 20 messages from
   `conversation.messages` + the new user message.
4. Calls the same OpenAI-compatible endpoint pattern that `placement/services.py`
   already uses (re-read it for the exact shape).
5. Returns the assistant's reply text.

If `AI_API_KEY` is not set, return a deterministic stub reply that's still
useful for testing — e.g. the student's message echoed with `"(stub: AI not
configured)"` and a fixed follow-up question. Don't crash.

#### Views & URLs — `tutor/views.py`, `tutor/urls.py`

All views are `@login_required`. All views also require `request.user.profile.is_subscribed`
— if not subscribed, redirect to `subscribe` with a `messages.warning`.

**`conversation_list(request)`** — `GET /tutor/`
- Lists the user's past conversations as cards. Empty state with a "Start a
  new conversation" button if there are none.

**`new_conversation(request)`** — `POST /tutor/new/`
- Creates an empty `TutorConversation` (optional `topic` from POST), redirects
  to its detail page.

**`conversation_detail(request, pk)`** — `GET /tutor/<pk>/`
- 404 if the conversation isn't owned by the user.
- Renders the chat UI: existing messages + a textarea for the next message.

**`send_message(request, pk)`** — `POST /tutor/<pk>/send/`
- 404 if not owned by user. Reject empty messages.
- Save the user message, call `services.chat()`, save the assistant message,
  redirect back to `conversation_detail`. (No JS streaming required for
  Phase 1.)

URLs:
```python
urlpatterns = [
    path("", views.conversation_list, name="tutor"),
    path("new/", views.new_conversation, name="tutor_new"),
    path("<int:pk>/", views.conversation_detail, name="tutor_detail"),
    path("<int:pk>/send/", views.send_message, name="tutor_send"),
]
```

Add to `onlenco/urls.py`: `path("tutor/", include("tutor.urls"))`.

#### Templates

**`templates/tutor/list.html`** — list of conversation cards. Each shows
title, topic badge, last-updated time ("3 hours ago"), and links to the detail
page. A prominent "Start new conversation" button at the top with a topic
picker (dropdown or pill buttons): travel, job interview, small talk, news,
free chat.

**`templates/tutor/detail.html`** — chat UI:
- Sticky header with conversation title and a "New conversation" button.
- Message list: user messages right-aligned with a teal/primary background;
  assistant messages left-aligned with a card background. RTL flips alignment.
- Sticky footer with a textarea (auto-grow, Enter to submit, Shift+Enter for
  newline) and a send button.
- After the user submits, the page reloads with the new messages. Auto-scroll
  to bottom on load.

Both templates use `_app_header.html` and the standard layout.

#### Admin — `tutor/admin.py`

- `TutorConversation` with `list_display = ("user", "title", "topic", "updated_at")`,
  `list_filter = ("topic",)`, `search_fields = ("user__email", "title")`.
- `TutorMessage` shown as `TabularInline` on `TutorConversation`.

#### Dashboard integration

Update `templates/lessons/dashboard.html`: add a prominent "AI Tutor" card
at the top of the page (alongside the placement banner / subscription CTA)
that links to `/tutor/`. Use the `mic` Lucide icon and the gradient-sunset
style.

#### i18n strings — add to `core/translations.py`

```python
"tutor.title":      {"en": "AI English Tutor",  "ar": "المدرس الذكي"},
"tutor.intro":      {"en": "Practice English with an AI coach who adapts to your level.",
                     "ar": "تدرب على الإنجليزية مع مدرس ذكي يتكيف مع مستواك."},
"tutor.new":        {"en": "New conversation",  "ar": "محادثة جديدة"},
"tutor.empty":      {"en": "No conversations yet — start your first one!",
                     "ar": "لا توجد محادثات بعد — ابدأ محادثتك الأولى!"},
"tutor.send":       {"en": "Send",              "ar": "إرسال"},
"tutor.placeholder":{"en": "Type your message in English…",
                     "ar": "اكتب رسالتك بالإنجليزية…"},
"tutor.topic.travel":     {"en": "Travel",         "ar": "السفر"},
"tutor.topic.interview":  {"en": "Job interview",  "ar": "مقابلة عمل"},
"tutor.topic.smalltalk":  {"en": "Small talk",     "ar": "حديث عابر"},
"tutor.topic.news":       {"en": "News",           "ar": "أخبار"},
"tutor.topic.free":       {"en": "Free chat",      "ar": "حوار حر"},
"tutor.locked":     {"en": "Subscribe to chat with the AI tutor.",
                     "ar": "اشترك للتحدث مع المدرس الذكي."},
```

### Phase 2 — voice (stretch, optional)

If time permits, add browser-based voice input (no server-side audio storage):

- Use the Web Speech API (`SpeechRecognition`) to transcribe student speech
  into the textarea. Show a microphone button next to the send button.
- Use the Web Speech API (`speechSynthesis`) to read assistant replies aloud
  with a "Play" button on each assistant message.
- Both are pure-frontend JS — no new Django routes needed.
- Gracefully degrade when the browser doesn't support these APIs (hide the
  buttons).

Do NOT attempt server-side TTS or file uploads for audio in this prompt —
those need a separate prompt with a real provider integration.

## Acceptance criteria

A reviewer should be able to:

1. As a subscribed user, click "AI Tutor" from the dashboard.
2. Land on the conversation list, see the empty state, click "New conversation".
3. Pick a topic from the picker, get a fresh conversation page.
4. Type a message ("Hi, I want to practise English for travel.") and submit.
5. See their message appear, then the AI's reply (or stub if no API key)
   directly under it.
6. Send another message; the conversation persists across page reloads.
7. Click "New conversation" to start fresh; the old one shows up in the list
   with the right title/topic/timestamp.
8. As an unsubscribed user, hitting `/tutor/` redirects to subscribe.
9. (Phase 2 only) Click the mic button → browser asks for microphone
   permission → speak → text appears in the textarea.

Run `python manage.py check` and `python manage.py migrate` — both clean.

## Out of scope

- No real-time streaming (token-by-token) responses.
- No conversation export, sharing, or deletion.
- No file/image attachments.
- No server-stored audio files. (Phase 2 is browser-side only.)
- No usage limits / rate limiting per user — assume the subscription is the
  rate limit.

## Style guide

- Chat bubbles: 85% max-width, rounded corners, 0.75rem padding.
- User bubbles: `bg-primary text-primary-foreground`, right-aligned (LTR) /
  left-aligned (RTL).
- Assistant bubbles: `card bg-card border-border`, prose-friendly typography.
- Use the same gradient-hero CTA style as the dashboard's "Subscribe" button
  for "Start new conversation".
- Topic pill buttons: `.badge` style, clickable, with a checked state showing
  `bg-primary text-primary-foreground`.

## What to deliver

A patched `onlenco_django.zip` with:

- New `tutor` app added to `INSTALLED_APPS`
- Models + migrations
- Views, URLs, templates, admin
- A new "AI Tutor" card on the dashboard
- New i18n strings
- Phase 2 (voice) only if it can be done cleanly with the Web Speech API

`python manage.py check` passes. Existing pages still render.
<!-- END: 02_ai_voice_tutor.md -->

---

<!-- BEGIN: 03_digital_library.md -->
# 03 — Digital Library

## Context

This task adds the **Digital Library** to the **Onlenco** Django project —
listed as a feature on the marketing page but not yet built. Subscribed
students browse books/short stories/grammar references by CEFR level and
read them inline.

Project conventions to follow:

- Templates: `{% load i18n_dict %}` plus `{% t "key" %}` and
  `{% t_either "en" "ar" %}` helpers.
- Tailwind via Play CDN + `static/css/onlenco.css`.
- Component classes: `.btn`, `.btn-hero`, `.btn-outline`, `.btn-ghost`,
  `.card`, `.badge`, `.badge-secondary`, `.badge-outline`, `.input`, `.label`.
- Lucide icons via `<i data-lucide="..."></i>`.
- Subscription gate: `request.user.profile.is_subscribed`.

## Goal

Add a `library` app with a `Book` model, a list page with filtering by CEFR
level and category, and a per-book reader page. Books either hold their text
inline (one or many chapters) or link out to a PDF.

## Spec

### Models — `library/models.py`

Use the existing CEFR choices: `from accounts.models import CEFR_CHOICES`.

**`Book`**
- `title = CharField(max_length=200)`
- `author = CharField(max_length=120, blank=True)`
- `category = CharField(max_length=20, choices=[
    ("novel","Novel"),
    ("short","Short story"),
    ("grammar","Grammar reference"),
    ("article","Article")])`
- `level = CharField(max_length=2, choices=CEFR_CHOICES)`
- `summary = TextField(blank=True)` — 1-3 sentences, shown on the list page
- `cover = ImageField(upload_to="library/covers/", blank=True, null=True)`
- `pdf = FileField(upload_to="library/pdfs/", blank=True, null=True)`
- `published_at = DateField(blank=True, null=True)`
- `is_published = BooleanField(default=True)`
- `created_at = DateTimeField(auto_now_add=True)`
- Meta `ordering = ["-published_at", "title"]`
- `__str__` returns `f"{title} ({level})"`

**`Chapter`** — for inline-text books (when there's no PDF)
- `book = ForeignKey(Book, on_delete=CASCADE, related_name="chapters")`
- `title = CharField(max_length=200)`
- `body = TextField()` — markdown or plain text
- `sort_order = PositiveSmallIntegerField(default=0)`
- Meta `ordering = ["sort_order", "id"]`
- `__str__` returns `f"{book.title} — Chapter {sort_order}: {title}"`

A book has either chapters OR a pdf, not both. The reader picks between them.

### Views & URLs — `library/views.py`, `library/urls.py`

**`book_list(request)`** — `GET /library/`
- `@login_required`
- If not subscribed → render the page in preview mode: cover + title visible,
  "Read" buttons replaced with a "Subscribe to unlock" CTA on each card.
- Pull filters from querystring: `?level=B1&category=novel`. Both optional.
- Default sort: newest first (`-published_at`).
- Pagination: 12 per page using Django's `Paginator`.
- Pass available levels and categories to the template for the filter UI.

**`book_detail(request, pk)`** — `GET /library/<pk>/`
- `@login_required`. 403/redirect to subscribe if not subscribed.
- 404 if `is_published=False`.
- If the book has a `pdf`, render an `<iframe src="{{ book.pdf.url }}">` reader.
- If the book has chapters, render a chapter selector (sidebar or top tabs)
  and the selected chapter's body in a typography-tuned column. Use Django's
  `linebreaks` filter on `body` to handle paragraph breaks.

URLs:
```python
urlpatterns = [
    path("", views.book_list, name="library"),
    path("<int:pk>/", views.book_detail, name="library_book"),
]
```
Mount in `onlenco/urls.py`: `path("library/", include("library.urls"))`.

### Templates

**`templates/library/list.html`**
- Page header: title, intro paragraph, filter form (level + category as
  pill buttons that link to the same page with the right querystring).
- Grid of book cards: 2 cols mobile, 3 tablets, 4 desktop. Each card shows
  cover image (or a gradient placeholder if no cover), title, author, level
  badge, category badge.
- Pagination controls at the bottom.
- Empty state when no books match the filter.

**`templates/library/detail.html`**
- Header: cover thumbnail, title, author, level + category badges,
  short summary.
- Reader: PDF iframe or chapter view.
- For chapter view: `aside` with the chapter list (highlight the active
  one), main column with the chapter body. Smooth scroll between chapters.
- "Back to library" link top-left.

Use `_app_header.html` on both.

Place the cover-placeholder gradient inline:
```html
<div class="aspect-[3/4] gradient-sunset rounded-xl flex items-center justify-center">
  <i data-lucide="book-open" class="h-12 w-12 text-primary-foreground"></i>
</div>
```

### Admin — `library/admin.py`

- `Book` admin: `list_display = ("title", "author", "category", "level",
  "is_published", "published_at")`, `list_filter = ("category", "level",
  "is_published")`, `search_fields = ("title", "author", "summary")`,
  `prepopulated_fields = {}`. Add `Chapter` as a `TabularInline`.

### Dashboard integration

Update `templates/lessons/dashboard.html`: add a "Library" card to the row
of secondary CTAs (alongside AI Tutor, etc.) that links to `/library/`.
Use the `library` Lucide icon (or `book-marked`).

### Seed data

Update `lessons/management/commands/seed_demo.py` (or create
`library/management/commands/seed_books.py` and call it from `seed_demo`)
to add 6 sample books spanning A0–C2:

1. *First English Words* (grammar, A0) — 2 inline chapters
2. *A Day in the Market* (short story, A1) — 1 inline chapter
3. *Letters from a Friend* (short story, A2) — 3 inline chapters
4. *News from Khartoum* (article, B1) — 1 inline chapter
5. *Beginner's Grammar Pocketbook* (grammar, B2) — 4 inline chapters
6. *The Long Road* (novel, C1) — 5 inline chapters with placeholder Lorem-ipsum-style text

No real cover images or PDFs are needed; leave those fields blank and rely
on the gradient placeholder.

### i18n strings — add to `core/translations.py`

```python
"library.title":     {"en": "Digital Library",            "ar": "المكتبة الرقمية"},
"library.subtitle":  {"en": "Read at your level — novels, short stories, grammar references.",
                      "ar": "اقرأ على مستواك — روايات وقصص قصيرة ومراجع قواعد."},
"library.read":      {"en": "Read",                       "ar": "اقرأ"},
"library.continue":  {"en": "Continue reading",           "ar": "متابعة القراءة"},
"library.back":      {"en": "Back to library",            "ar": "العودة للمكتبة"},
"library.empty":     {"en": "No books match these filters.","ar": "لا توجد كتب تطابق هذه الفلاتر."},
"library.filter":    {"en": "Filter",                     "ar": "تصفية"},
"library.all":       {"en": "All",                        "ar": "الكل"},
"library.locked":    {"en": "Subscribe to read",          "ar": "اشترك للقراءة"},
"library.cat.novel":   {"en": "Novel",                    "ar": "رواية"},
"library.cat.short":   {"en": "Short story",              "ar": "قصة قصيرة"},
"library.cat.grammar": {"en": "Grammar",                  "ar": "قواعد"},
"library.cat.article": {"en": "Article",                  "ar": "مقال"},
```

## Acceptance criteria

A reviewer should be able to:

1. Click "Library" from the dashboard → land on `/library/` with a grid of
   sample books.
2. Click a level pill ("B1") → see only B1 books. Same for category.
3. Click "All" → reset the filter.
4. As a subscribed user, click a book → land on the detail page with the
   chapter list sidebar and the first chapter body.
5. Click a different chapter in the sidebar → main column updates.
6. As an unsubscribed user, every "Read" button is replaced with "Subscribe
   to unlock".
7. Hitting `/library/<pk>/` directly without a subscription redirects to
   `subscribe`.
8. In `/admin/`, create a new book with 3 chapters inline without leaving
   the page.

`python manage.py check` and `python manage.py migrate` both clean.

## Out of scope

- No bookmarks, highlights, or reading-position memory.
- No search box (filters only — search is its own prompt if needed later).
- No book purchasing, downloads, or DRM.
- No comments or ratings.
- No PDF text extraction or in-iframe annotation tools.

## Style guide

- Cover aspect ratio: 3:4. Real covers cover the whole card; the placeholder
  gradient fills the same space.
- Filter pills use `.badge` styling; the active filter uses `bg-primary
  text-primary-foreground`.
- Reader main column: `max-w-3xl mx-auto`, `prose` line-height, `text-lg`
  font size, generous line height (~1.7).
- Chapter body uses Django's `{{ chapter.body|linebreaks }}` to render
  paragraph breaks.

## What to deliver

A patched `onlenco_django.zip` with:

- New `library` app added to `INSTALLED_APPS`
- `Book` and `Chapter` models with one migration
- Views, URLs, templates, admin
- "Library" card added to the dashboard
- Seeded sample books (via `seed_demo` or a dedicated command)
- New i18n strings

`python manage.py check` passes. Hitting `/library/` while logged in and
subscribed shows 6 books.
<!-- END: 03_digital_library.md -->

---

<!-- BEGIN: 04_arabic_english_dictionary.md -->
# 04 — Arabic ↔ English Dictionary

## Context

This task adds the **Arabic–English dictionary** to the **Onlenco** Django
project — listed as a feature on the marketing page but not yet built.

Project conventions:
- `{% load i18n_dict %}` plus `{% t "key" %}` and `{% t_either "en" "ar" %}`.
- Tailwind via Play CDN + `static/css/onlenco.css`.
- Component classes: `.btn`, `.btn-hero`, `.btn-outline`, `.card`, `.badge`,
  `.input`, `.label`.
- Lucide icons: `<i data-lucide="..."></i>`.
- AI client pattern in `placement/services.py` (OpenAI-compatible).

## Goal

Add a `dictionary` app with a `DictionaryEntry` model and a search page
that lets logged-in users look up an English or Arabic word and see the
translation, part of speech, example sentences, and a small list of related
words.

The dictionary has a curated DB-stored set of common words, plus an optional
AI fallback for words that aren't in the DB. The AI fallback is cached so we
don't pay for the same word twice.

## Spec

### Models — `dictionary/models.py`

**`DictionaryEntry`**
- `english = CharField(max_length=80, db_index=True)`
- `arabic = CharField(max_length=80, db_index=True)`
- `pos = CharField(max_length=20, blank=True,
    choices=[
      ("noun","Noun"), ("verb","Verb"), ("adj","Adjective"),
      ("adv","Adverb"), ("prep","Preposition"), ("phrase","Phrase"),
      ("other","Other")])` — part of speech
- `example_en = CharField(max_length=300, blank=True)`
- `example_ar = CharField(max_length=300, blank=True)`
- `notes = TextField(blank=True)` — admin-only style/usage notes
- `source = CharField(max_length=20, default="curated",
    choices=[("curated","Curated"),("ai","AI-generated")])`
- `lookup_count = PositiveIntegerField(default=0)` — bump on each lookup,
  useful for "popular searches"
- `created_at = DateTimeField(auto_now_add=True)`
- Meta `ordering = ["english"]`, `unique_together = [("english","arabic")]`
- `__str__` returns `f"{english} ↔ {arabic}"`

### Service — `dictionary/services.py`

Two helpers:

**`search(query: str, lang_hint: str = "auto") -> List[DictionaryEntry]`**
- Normalize whitespace + lowercase the query.
- If `lang_hint == "auto"`, detect: if the query contains any character in
  the U+0600–U+06FF range, treat as Arabic; otherwise English.
- Query the DB:
  - English query → `Q(english__icontains=q)`, ordered by exact-match first,
    then prefix, then contains, then `-lookup_count`.
  - Arabic query → `Q(arabic__icontains=q)` with the same ordering rules.
- Return up to 20 entries.
- Bump `lookup_count` for the entries returned (single bulk `.update()` —
  don't loop).

**`ai_lookup(query: str, lang_hint: str) -> Optional[DictionaryEntry]`**
- Used only when `search()` returns nothing.
- If `AI_API_KEY` is empty → return `None` (no crash, no fallback fabrication).
- Call the same OpenAI-compatible endpoint pattern that `placement/services.py`
  uses, with a system prompt asking the model to return a single JSON object
  via function calling: `{english, arabic, pos, example_en, example_ar}`.
- On success, save a new `DictionaryEntry(source="ai")` and return it.
- On any error (API down, missing fields, bad JSON), log the error and return
  `None` — never crash.

Use Python's `logging` module (`logger = logging.getLogger(__name__)`).

### Views & URLs — `dictionary/views.py`, `dictionary/urls.py`

**`dictionary_view(request)`** — `GET /dictionary/?q=hello`
- `@login_required`. Subscription is **not** required (this is a free
  utility — the marketing page lists it without "subscribe to unlock").
- Read `q` from querystring. If empty: render the page with a search box
  and a "Popular lookups" section showing the top 12 entries by `lookup_count`.
- If `q` is present:
  1. Call `services.search(q)`.
  2. If empty, call `services.ai_lookup(q)`. If that returns an entry, show
     it with a small "AI-generated" badge so users know it isn't curated.
  3. If still empty, show a "No results found" empty state with a "Try a
     different spelling" hint.

URL:
```python
urlpatterns = [
    path("", views.dictionary_view, name="dictionary"),
]
```
Mount in `onlenco/urls.py`: `path("dictionary/", include("dictionary.urls"))`.

### Template — `templates/dictionary/dictionary.html`

- Standard `_app_header.html` shell.
- Big centred search box at the top with a search icon, autofocus.
  Form GETs to `?q=`. Bilingual placeholder: in EN show "Search English or
  Arabic…", in AR show "ابحث بالإنجليزية أو العربية…".
- Recent / popular lookups shown as pill links below the box when `q`
  is empty.
- Results list: each entry as a card with:
  - Big `english` and `arabic` next to each other (both in the appropriate
    direction)
  - Part-of-speech badge
  - Example sentences (en + ar) below in smaller text
  - A small "🤖 AI-generated" badge in the corner if `source == "ai"`
- Empty state with a friendly icon (Lucide `search-x`) and a tip.

### Admin — `dictionary/admin.py`

- `list_display = ("english", "arabic", "pos", "source", "lookup_count")`
- `list_filter = ("pos", "source")`
- `search_fields = ("english", "arabic")`
- `readonly_fields = ("lookup_count", "created_at")`

### Seed data — `dictionary/management/commands/seed_dictionary.py`

Create a `seed_dictionary` management command that loads ~60 high-frequency
words across parts of speech: hello/مرحبا, water/ماء, book/كتاب,
to read/يقرأ, fast/سريع, slowly/ببطء, on/على, etc. Include short example
sentences in both languages. Categorize each by `pos`.

Update `seed_demo.py` to call `call_command("seed_dictionary")`.

### i18n strings — add to `core/translations.py`

```python
"dict.title":         {"en": "Arabic ↔ English Dictionary",
                       "ar": "قاموس عربي ↔ إنجليزي"},
"dict.subtitle":      {"en": "Look up any word, see examples, learn faster.",
                       "ar": "ابحث عن أي كلمة، شاهد الأمثلة، تعلم بسرعة."},
"dict.search":        {"en": "Search",                  "ar": "بحث"},
"dict.search_hint":   {"en": "Search English or Arabic…",
                       "ar": "ابحث بالإنجليزية أو العربية…"},
"dict.popular":       {"en": "Popular lookups",         "ar": "الكلمات الشائعة"},
"dict.no_results":    {"en": "No results found.",       "ar": "لم يتم العثور على نتائج."},
"dict.ai_generated":  {"en": "AI-generated",            "ar": "مولّد بالذكاء الاصطناعي"},
"dict.example":       {"en": "Example",                 "ar": "مثال"},
"dict.pos.noun":      {"en": "noun",                    "ar": "اسم"},
"dict.pos.verb":      {"en": "verb",                    "ar": "فعل"},
"dict.pos.adj":       {"en": "adjective",               "ar": "صفة"},
"dict.pos.adv":       {"en": "adverb",                  "ar": "ظرف"},
"dict.pos.prep":      {"en": "preposition",             "ar": "حرف جر"},
"dict.pos.phrase":    {"en": "phrase",                  "ar": "عبارة"},
```

### Header / dashboard integration

- Add a "Dictionary" link in `_site_header.html`'s nav (visible to everyone)
  — between Curriculum and Pricing on the public site, leading to
  `/dictionary/` (will redirect to login for anonymous users).
- Add a "Dictionary" card in the dashboard secondary CTAs row alongside
  AI Tutor / Library. Use Lucide icon `book-a` or `languages`.

## Acceptance criteria

A reviewer should be able to:

1. Click "Dictionary" from the dashboard → land on `/dictionary/`.
2. See popular lookups when no query.
3. Search "hello" → see the curated entry with English, Arabic, examples.
4. Search "مرحبا" → see the same entry from the Arabic side.
5. Search a word that's not in the DB (e.g. "serendipity") → either get an
   AI-generated entry with the AI badge (if `AI_API_KEY` is set) or the
   "No results" empty state (if not).
6. The AI-generated entry is saved to the DB so the next search for the
   same word is instant.
7. Click a "Popular lookups" pill → it pre-fills the search box and runs
   the query.
8. In `/admin/`, edit an existing entry's translation or example.

`python manage.py check` and `python manage.py migrate` clean.

## Out of scope

- No verb conjugations, no diacritics handling beyond basic normalization,
  no morphological root mapping.
- No audio pronunciation.
- No flashcard / spaced-repetition saving.
- No bulk import from external dictionary files (CSV / dictionary APIs).
- No favorites or per-user history.

## Style guide

- The two big words (English + Arabic) on each result card should each be
  in their natural script direction. Use inline `dir="ltr"` and `dir="rtl"`
  on those spans regardless of the page direction.
- Results should feel close to a printed dictionary: serif display font for
  the headwords (Fraunces / Cairo), generous spacing, examples italicised.
- Search input: `.input` class, full width, with a Lucide `search` icon
  inside-left and a Lucide `arrow-right` submit hint inside-right.
- AI-generated badge: subtle, `badge-outline` with a small bot emoji or icon.

## What to deliver

A patched `onlenco_django.zip` with:

- New `dictionary` app added to `INSTALLED_APPS`
- `DictionaryEntry` model + migration
- `services.py` with `search()` and `ai_lookup()`
- `dictionary_view`, URL, template
- Admin
- `seed_dictionary` command + integration into `seed_demo`
- Header nav link + dashboard card
- New i18n strings

`python manage.py check` passes; `seed_demo` populates ~60 entries.
<!-- END: 04_arabic_english_dictionary.md -->

---

<!-- BEGIN: 05_english_club_events.md -->
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
<!-- END: 05_english_club_events.md -->

---

<!-- BEGIN: 06_placement_speaking.md -->
# 06 — Speaking Part of the Placement Test

## Context

The **Onlenco** placement test currently asks 4 written questions (2 MCQs + 2
free-text). The original technical document specified "AI Placement Test
(written + speaking)" — the speaking half is missing. This prompt adds it.

Project conventions:
- `{% load i18n_dict %}` plus `{% t "key" %}` and `{% t_either "en" "ar" %}`.
- Tailwind via Play CDN + `static/css/onlenco.css`.
- Component classes: `.btn`, `.btn-hero`, `.btn-outline`, `.card`, `.badge`.
- Lucide icons.
- AI service: see `placement/services.py` — uses an OpenAI-compatible endpoint
  with function calling, falls back to a deterministic heuristic when no key.
- The existing placement view: `placement/views.py` `placement(request)`,
  template `templates/placement/placement.html`.

## Goal

Add a 5th task to the placement test: a 30-60 second spoken response. The
user records audio in the browser using `MediaRecorder`, the audio is
auto-transcribed with the Web Speech API client-side (no upload), and the
transcript is fed into the existing AI assessor along with the written
answers. The model gets both `written_score` and `speaking_score`.

The audio file itself is **not** uploaded to the server — only the
transcript is sent. This keeps storage and privacy concerns simple.

## Spec

### View changes — `placement/views.py`

The current view collects `q1`, `q2`, `q3`, `q4`. Add a `q5_transcript`
field that comes from the form as a hidden `<input>` populated by JS.

Validation rules:
- `q5_transcript` must be ≥ 30 characters (about 6-8 words). If shorter,
  return the form with an error message: "Please record a longer spoken
  answer (at least 5 sentences)."
- All other validation rules unchanged.

Pass `q5` to `assess()` alongside the other answers.

### Service changes — `placement/services.py`

Update `_build_user_prompt()` to include the new question:

```python
def _build_user_prompt(answers: dict) -> str:
    return (
        "Learner answers:\n"
        f"1. Grammar MCQ ('She ___ to school every day'): {answers.get('q1','')}\n"
        f"2. Grammar MCQ (which is correct): {answers.get('q2','')}\n"
        f"3. Free writing about hobbies: {answers.get('q3','')}\n"
        f"4. Past tense description (yesterday): {answers.get('q4','')}\n"
        f"5. Spoken response transcript (talked for ~45 seconds about their daily routine): "
        f"{answers.get('q5','')}\n\n"
        "Use answers 1-4 to score 'written_score' and answer 5 to score "
        "'speaking_score'. Each is 0-100. Return CEFR level and short feedback."
    )
```

Update `_heuristic_fallback()` to score `speaking_score` from `q5` length and
sentence variety (mirror the q4 logic). Currently it just returns
`written_score - 10` — replace with a real (heuristic) calculation.

### Template changes — `templates/placement/placement.html`

After Q4, add **Q5: Speaking task**:

```html
<div class="space-y-3">
  <p class="text-base font-semibold">5. {% t "pl.q5" %}</p>
  <p class="text-sm text-muted-foreground">{% t "pl.q5_intro" %}</p>

  <div class="card p-5 bg-muted/30">
    <div class="flex items-center justify-between mb-3">
      <div class="flex items-center gap-3">
        <button type="button" id="rec-toggle" class="btn btn-hero">
          <i data-lucide="mic" class="h-4 w-4"></i>
          <span id="rec-label">{% t "pl.q5_record" %}</span>
        </button>
        <span id="rec-timer" class="text-sm text-muted-foreground" hidden>0:00</span>
      </div>
      <span id="rec-status" class="text-sm text-muted-foreground"></span>
    </div>
    <textarea id="q5-transcript-display" rows="5" readonly
              dir="ltr" class="font-mono text-sm"
              placeholder="{% t 'pl.q5_transcript_hint' %}"></textarea>
    <input type="hidden" name="q5_transcript" id="q5-transcript">
  </div>
  <p class="text-xs text-muted-foreground">{% t "pl.q5_note" %}</p>
</div>
```

Add a JS block that wires up the speech recognition. It must:

1. Feature-detect `window.SpeechRecognition || window.webkitSpeechRecognition`.
   If unsupported, hide the record button and show: "Your browser doesn't
   support voice recording. Please type your answer instead." with a
   fallback `<textarea name="q5_transcript">`.
2. On record start: change button to "Stop", show timer ticking up,
   `recognition.lang = 'en-US'`, `recognition.continuous = true`,
   `recognition.interimResults = true`.
3. As partial results arrive, append to the transcript display (and to the
   hidden input).
4. Stop after either:
   - User clicks "Stop"
   - 60 seconds elapsed (auto-stop with a "Time's up!" status)
5. After stop, button label becomes "Re-record" and clicking it clears the
   transcript and starts fresh.

Keep the script self-contained in the template — no new files. About 60
lines of vanilla JS.

### i18n strings — add to `core/translations.py`

```python
"pl.q5":              {"en": "Speaking task — record yourself in English",
                       "ar": "مهمة تحدث — سجّل نفسك بالإنجليزية"},
"pl.q5_intro":        {"en": "Talk for about 45 seconds about your typical day. "
                              "What time do you wake up? What do you usually eat? "
                              "What do you do in the evenings?",
                       "ar": "تحدث لمدة 45 ثانية تقريباً عن يومك المعتاد. متى تستيقظ؟ "
                              "ماذا تأكل عادةً؟ ماذا تفعل في المساء؟"},
"pl.q5_record":       {"en": "Start recording",        "ar": "ابدأ التسجيل"},
"pl.q5_stop":         {"en": "Stop",                   "ar": "إيقاف"},
"pl.q5_rerecord":     {"en": "Record again",           "ar": "إعادة التسجيل"},
"pl.q5_transcript_hint": {"en": "Your speech will appear here as you talk.",
                          "ar": "سيظهر كلامك هنا أثناء التحدث."},
"pl.q5_note":         {"en": "Audio is processed in your browser. We only store the transcript.",
                       "ar": "تتم معالجة الصوت في متصفحك. نحن نخزن النص فقط."},
"pl.q5_unsupported":  {"en": "Your browser doesn't support voice recording. "
                              "Please type your answer below instead.",
                       "ar": "متصفحك لا يدعم تسجيل الصوت. يرجى كتابة إجابتك أدناه بدلاً من ذلك."},
"pl.q5_too_short":    {"en": "Please record a longer spoken answer (at least 5 sentences).",
                       "ar": "يرجى تسجيل إجابة شفهية أطول (5 جمل على الأقل)."},
"pl.q5_recording":    {"en": "Recording…",             "ar": "جاري التسجيل…"},
"pl.q5_done":         {"en": "Recording complete",     "ar": "اكتمل التسجيل"},
```

## Acceptance criteria

A reviewer should be able to:

1. Open `/placement/` while logged in.
2. Fill in Q1–Q4.
3. See Q5 with a "Start recording" button and a placeholder textarea.
4. Click "Start recording" → browser asks for mic permission → granted.
5. Speak for ~30 seconds → see live transcription appear in the textarea.
6. Click "Stop" → button becomes "Record again" and transcript is preserved.
7. Submit the form → AI returns a CEFR level whose `speaking_score` reflects
   the recorded answer (try recording very little — score should be lower).
8. Open the page in a browser without speech-recognition support (Firefox
   on Linux is one) → see the fallback message and a textarea instead of
   the record button.
9. Submit with a too-short transcript → see the validation error.
10. Submit successfully → land on the result page with the CEFR level.

In `/admin/`, the new placement result row's `transcript` JSON should now
include a `q5` field with the spoken transcript.

## Out of scope

- No server-side audio upload, transcription, or storage.
- No multi-language support for speech recognition (English only).
- No accent grading, prosody analysis, or pronunciation scoring beyond what
  the LLM can infer from the transcript.
- No ability to upload pre-recorded audio.

## Style guide

- Mic button: `.btn-hero` with the Lucide `mic` icon. When recording, swap
  to a "stop" state with `mic-off` icon and a subtle red pulse on the
  button background.
- Timer format: `M:SS`, monospace.
- Transcript textarea: monospace font, `dir="ltr"`, read-only-ish (the user
  doesn't type — the JS fills it).

## What to deliver

A patched `onlenco_django.zip` with:

- Updated `placement/views.py` to handle q5
- Updated `placement/services.py` for the new prompt and improved fallback
- Updated `templates/placement/placement.html` with the recording UI + JS
- New i18n strings in `core/translations.py`

`python manage.py check` clean. The placement flow still works in browsers
without speech-recognition support (graceful fallback to typing).
<!-- END: 06_placement_speaking.md -->

---

<!-- BEGIN: 07_admin_analytics.md -->
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
<!-- END: 07_admin_analytics.md -->

---

<!-- BEGIN: 08_subscription_expiry.md -->
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
<!-- END: 08_subscription_expiry.md -->

---

<!-- BEGIN: 09_placement_retake_guard.md -->
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
<!-- END: 09_placement_retake_guard.md -->

---

<!-- BEGIN: 10_payment_reject_ui.md -->
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
<!-- END: 10_payment_reject_ui.md -->

---

<!-- BEGIN: 11_editable_payment_accounts.md -->
# 11 — Editable Payment Method Accounts

## Context

The **Onlenco** payment flow currently shows three hardcoded payment methods
(Bankak / Fawry / O-Cash) with hardcoded account numbers. The data lives in
`payments/views.py`:

```python
ACCOUNT_INFO = {
    "bankak": {"label": "Bankak", "account": "1234 5678 9012", "name": "Onlenco Sudan"},
    "fawry":  {"label": "Fawry",  "account": "+249 91 234 5678", "name": "Onlenco Sudan"},
    "ocash":  {"label": "O-Cash", "account": "+249 92 876 5432", "name": "Onlenco Sudan"},
}
```

This means changing an account number requires a code deploy. This prompt
moves it into a model so admins can edit account details from `/admin/`
without redeploying.

Project conventions:
- Use Django's built-in `/admin/`. No custom admin pages.
- The existing `PAYMENT_METHODS` choices list lives in `payments/models.py`
  — reuse it.

## Goal

Replace the hardcoded `ACCOUNT_INFO` dict with a `PaymentMethodAccount`
model. Migrate seed data into it. Update the subscribe view to read from
the DB.

## Spec

### Model — `payments/models.py`

Add to the existing models file:

```python
class PaymentMethodAccount(models.Model):
    """Bank/wallet account details shown to students for offline transfer.

    Editable by admins via /admin/ so account numbers can change without
    a code deploy. Each method (Bankak/Fawry/O-Cash) has at most one
    active row at a time.
    """
    method = models.CharField(max_length=10, choices=PAYMENT_METHODS, unique=True)
    label = models.CharField(max_length=80, help_text="Display name, e.g. 'Bankak'")
    account_number = models.CharField(max_length=80,
        help_text="Account number, IBAN, or phone number to send to.")
    account_holder = models.CharField(max_length=120, default="Onlenco Sudan",
        help_text="Name on the account.")
    instructions = models.TextField(blank=True,
        help_text="Optional extra instructions shown under the account info.")
    is_active = models.BooleanField(default=True)
    sort_order = models.PositiveSmallIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["sort_order", "method"]
        verbose_name = "Payment method account"
        verbose_name_plural = "Payment method accounts"

    def __str__(self):
        return f"{self.label} — {self.account_number}"
```

### Migration — data migration

Generate a migration with `python manage.py makemigrations payments`. Then
add a **data migration** in the same migration file (or a follow-up one)
that seeds the three existing methods:

```python
def seed_methods(apps, schema_editor):
    PMA = apps.get_model("payments", "PaymentMethodAccount")
    PMA.objects.get_or_create(
        method="bankak",
        defaults=dict(label="Bankak", account_number="1234 5678 9012",
                      account_holder="Onlenco Sudan", sort_order=10),
    )
    PMA.objects.get_or_create(
        method="fawry",
        defaults=dict(label="Fawry", account_number="+249 91 234 5678",
                      account_holder="Onlenco Sudan", sort_order=20),
    )
    PMA.objects.get_or_create(
        method="ocash",
        defaults=dict(label="O-Cash", account_number="+249 92 876 5432",
                      account_holder="Onlenco Sudan", sort_order=30),
    )

operations = [
    # ... model creation ...
    migrations.RunPython(seed_methods, reverse_code=migrations.RunPython.noop),
]
```

This way, anyone running the migration on a fresh DB gets the same default
data the old hardcoded dict provided.

### View changes — `payments/views.py`

Remove the `ACCOUNT_INFO` dict at the top of the file. Update `subscribe(request)`:

```python
from .models import PaymentMethodAccount

def subscribe(request):
    profile = request.user.profile
    accounts_qs = PaymentMethodAccount.objects.filter(is_active=True)
    # Build the dict shape the template expects: {code: {label, account, name}}
    accounts = {
        a.method: {
            "label": a.label,
            "account": a.account_number,
            "name": a.account_holder,
            "instructions": a.instructions,
        }
        for a in accounts_qs
    }
    # ... rest of the existing view, passing `accounts` to the template
```

The template already iterates `accounts.items` so this drop-in works. The
extra `instructions` key gives admins a place to add per-method notes —
update the template to show it under the account number when present.

### Template changes — `templates/payments/subscribe.html`

Two small additions:

1. In the method picker, only render methods that exist in `accounts` (the
   current `{% for code, info in accounts.items %}` already does this if
   the dict comes from the DB).

2. In the "Payment instructions" card, show each method's `instructions`
   field if non-empty:

```html
<ul class="text-sm mt-3 space-y-2">
  {% for code, info in accounts.items %}
  <li>
    <strong>{{ info.label }}:</strong> {{ info.name }} — <code>{{ info.account }}</code>
    {% if info.instructions %}
      <div class="text-xs text-muted-foreground mt-1">{{ info.instructions }}</div>
    {% endif %}
  </li>
  {% endfor %}
</ul>
```

### Admin — `payments/admin.py`

Register the new model:

```python
from .models import PaymentMethodAccount

@admin.register(PaymentMethodAccount)
class PaymentMethodAccountAdmin(admin.ModelAdmin):
    list_display = ("method", "label", "account_number", "account_holder",
                    "is_active", "sort_order")
    list_filter = ("is_active",)
    list_editable = ("is_active", "sort_order")
    search_fields = ("label", "account_number", "account_holder")
    ordering = ("sort_order", "method")
```

### Form-side validation — `payments/forms.py`

The form already has a `method` field driven by the `PAYMENT_METHODS`
choices tuple. Add a small validation step: reject submissions whose
chosen method has no active `PaymentMethodAccount` row. This prevents a
race where an admin deactivates a method between a user loading the form
and submitting:

```python
def clean_method(self):
    method = self.cleaned_data["method"]
    if not PaymentMethodAccount.objects.filter(method=method, is_active=True).exists():
        raise forms.ValidationError("This payment method is not currently available.")
    return method
```

### Tests (optional)

In `payments/tests.py`, a quick sanity test:

```python
from django.test import TestCase
from payments.models import PaymentMethodAccount

class PaymentMethodAccountSeedTest(TestCase):
    def test_three_methods_seeded(self):
        # data migration should have created 3 rows
        codes = set(PaymentMethodAccount.objects.values_list("method", flat=True))
        self.assertEqual(codes, {"bankak", "fawry", "ocash"})
```

## Acceptance criteria

A reviewer should be able to:

1. Run `python manage.py migrate` on a fresh DB → 3 `PaymentMethodAccount`
   rows are seeded (Bankak / Fawry / O-Cash) with the same numbers as before.
2. Visit `/payments/` while logged in → see the same three method cards as
   before, with the same account numbers.
3. In `/admin/payments/paymentmethodaccount/`, edit the Bankak row's
   `account_number` to "9999 8888 7777" and save.
4. Refresh `/payments/` → see "9999 8888 7777" displayed without restarting
   the server.
5. In `/admin/`, set the Fawry row's `is_active` to False.
6. Refresh `/payments/` → only Bankak and O-Cash now appear in the method
   picker. The "Payment instructions" list also drops Fawry.
7. Try to submit the form with `method=fawry` (e.g. via a stale browser tab)
   → form rejects it with the "not currently available" error.
8. Add an `instructions` value to the O-Cash row ("Send via the merchant
   tab, not personal transfer.") → see that line below the O-Cash entry on
   `/payments/`.

`python manage.py check`, `python manage.py migrate`, all clean.

## Out of scope

- No multi-currency: amounts are still always SDG.
- No payment-gateway integration. Still manual transfer + screenshot upload.
- No country-based filtering of methods.
- No QR codes for the account numbers.

## Style guide

- Match the existing model patterns in `payments/models.py`: HelpText on
  fields admins will edit, `Meta.ordering`, descriptive `__str__`.
- Don't add a `verbose_name` for fields unless it'd be misleading without one.
- Keep the data migration self-contained in the same `0002_*.py` file as
  the schema migration. Don't split.

## What to deliver

A patched `onlenco_django.zip` with:

- `payments/models.py`: new `PaymentMethodAccount` model
- New migration file (schema + data) that seeds Bankak/Fawry/O-Cash
- `payments/views.py`: `ACCOUNT_INFO` removed, replaced with DB query
- `payments/forms.py`: `clean_method()` validation added
- `payments/admin.py`: `PaymentMethodAccountAdmin` registered
- `templates/payments/subscribe.html`: `instructions` rendered when present
- (Optional) test in `payments/tests.py`

`python manage.py check`, `python manage.py migrate`, and `python manage.py
seed_demo` all run clean. Existing payment submissions still work.
<!-- END: 11_editable_payment_accounts.md -->

---

<!-- BEGIN: 12_cleanup_dead_code.md -->
# 12 — Cleanup: Dead Fixture, Stale Comments, Empty Test Files

## Context

The **Onlenco** Django project has accumulated a small amount of cruft
during its build:

- `lessons/fixtures/sample_lessons.json` — was used by an earlier
  approach (`python manage.py loaddata sample_lessons`). The current
  approach uses `python manage.py seed_demo`, which builds the same data
  programmatically. The fixture file is unreferenced.
- A few empty `tests.py` files across apps (auto-generated by
  `startapp`) that contribute nothing.
- Some context comments in views that reference the React app
  ("mirrors `Index.tsx`") which were helpful during porting but are noise
  now.
- README mentions `loaddata sample_lessons` in one or two places that
  should reference `seed_demo` instead.

## Goal

Remove dead code, tighten comments, and make sure the project's surface
area accurately reflects how it works today.

## Spec

### 1. Delete the fixture file

```bash
rm lessons/fixtures/sample_lessons.json
rmdir lessons/fixtures   # only if empty
```

If `lessons/fixtures/` is empty after removing the JSON, drop the directory.
If it's not empty (a future fixture might be added), leave it.

### 2. Remove empty `tests.py` files

For each app, check whether `tests.py` has anything non-trivial in it:

```bash
for app in accounts core lessons placement payments; do
    file="$app/tests.py"
    # Check if file is empty or only has Django's default 2-line stub
    lines=$(grep -cE '^[^#]' "$file" 2>/dev/null || echo 0)
    if [ "$lines" -lt 5 ]; then
        echo "Removing empty $file"
        rm "$file"
    fi
done
```

If any `tests.py` has actual test classes, **leave it alone**. Only delete
the auto-generated stubs (which look like:

```python
from django.test import TestCase

# Create your tests here.
```

).

If the user is adopting Django 5+, prefer creating a `tests/` package
directory in apps where you'd want to add tests later, but **only do this
if it doesn't already exist**. Don't churn for the sake of churning.

### 3. Comment cleanup

Search for these strings across the project and update them:

| Find | Action |
|------|--------|
| `# mirrors React`, `# matches the Supabase`, `# from React i18n.tsx` | Remove or rephrase generically (not "mirrors X", just describe what the code does) |
| `// (originally`, `# (the React app called this `, `# Supabase trigger equivalent` | Remove |
| `# TODO: ...` (any) | Audit. If the TODO is now done, remove it. If still relevant, leave it. |
| `# FIXME` | Keep but verify they're real problems |

Do this with the `Edit`/`str_replace` tool, not regex find/replace, so each
edit is reviewed.

### 4. README updates

Open `README.md` and:

- Replace any `python manage.py loaddata sample_lessons` reference with
  `python manage.py seed_demo`. (`seed_demo` does both: creates an admin
  and seeds lessons.)
- Verify the "Quick start" section's commands match the current code paths.
- Verify the table at the top listing apps is accurate (it should be — but
  worth a glance).

### 5. `requirements.txt` audit

Confirm it lists exactly:

```
Django>=5.0,<6.0
Pillow>=10.0
requests>=2.31
```

No more, no fewer. If anything else snuck in, audit whether it's actually
imported anywhere; remove if not.

### 6. `.env.example` audit

Confirm it has these keys and only these:

```bash
DJANGO_SECRET_KEY=change-me-in-production
DJANGO_DEBUG=1

AI_API_KEY=
AI_API_BASE=https://api.openai.com/v1
AI_MODEL=gpt-4o-mini
```

### 7. Stray empty directories

Quick scan for empty directories that shouldn't exist:

```bash
find . -type d -empty -not -path './.git/*' -not -path '*/migrations*' -not -path '*/__pycache__*'
```

Remove anything that turns up that isn't intentional. (The `migrations/`
directories with only `__init__.py` are intentional — leave those.)

### 8. Run final checks

```bash
python manage.py check        # must be clean
python manage.py migrate       # must apply cleanly to a fresh DB
python manage.py seed_demo     # must succeed
python manage.py runserver &   # boot the server
sleep 3
curl -sf -o /dev/null http://127.0.0.1:8000/        # 200
curl -sf -o /dev/null http://127.0.0.1:8000/auth/   # 200
kill %1
```

## Acceptance criteria

A reviewer should be able to:

1. Extract the patched zip into a fresh directory.
2. Run `pip install -r requirements.txt && python manage.py migrate &&
   python manage.py seed_demo && python manage.py runserver`.
3. Land at `http://localhost:8000/` with no errors.
4. Run `find . -name 'sample_lessons.json'` → no results.
5. Run `grep -r "mirrors React\|originally Supabase\|from i18n.tsx" .` →
   no results (or only matches in this prompt's description).
6. Read `README.md` → no references to `loaddata sample_lessons` (only
   `seed_demo`).
7. `requirements.txt` is exactly 3 lines (plus version pins).

## Out of scope

- No new features.
- No refactoring of working code.
- No renames of existing classes / functions / templates.
- No formatting changes (don't run `black`, `isort`, `ruff format`).
- No type hints additions.
- No docstring style changes beyond removing genuinely outdated ones.

## Style guide

This is a delete-only-or-tighten prompt. Be conservative. When in doubt,
leave it. The goal is removing cruft, not rewriting the project.

## What to deliver

A patched `onlenco_django.zip` with:

- `lessons/fixtures/sample_lessons.json` removed (and parent dir if empty)
- Empty stub `tests.py` files removed
- Stale "mirrors React" / "from Supabase" comments scrubbed or generalized
- README updated to reference `seed_demo` only
- `requirements.txt` and `.env.example` confirmed minimal
- No empty directories

`python manage.py check` passes. The full quick-start sequence still works
end-to-end. Total diff should be small (mostly deletions).
<!-- END: 12_cleanup_dead_code.md -->

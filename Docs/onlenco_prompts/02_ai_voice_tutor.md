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

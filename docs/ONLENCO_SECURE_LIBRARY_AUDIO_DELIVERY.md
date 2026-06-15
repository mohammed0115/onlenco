# Onlenco — Secure Library Audio Delivery & Minute Enforcement (Phase 19.0G)

## 1. Why raw MEDIA_URL links are risky
Before this phase the student listen page printed the chapter recording's
`audio_file.url` (a public `MEDIA_URL` path) directly into the HTML. Normal
listening went through the library-minutes session, **but** anyone who copied
that raw URL could download or replay the recording with **zero** minute
deduction and **no** subscription / publish / copyright check. The file was, in
effect, an open public asset.

## 2. Secure audio delivery design
The raw URL is gone. An uploaded recording is now served only through a
protected Django view:

```
GET /library/chapters/<chapter_id>/audio/stream/?s=<session_id>   (student)
GET /admin/library/chapters/<pk>/audio/preview/                   (staff)
```

The view streams the file from storage via
`library/services/audio_delivery.py::audio_file_response`, which opens the
file through the storage backend (no absolute filesystem path is exposed) and
sets safe headers. The student template never contains `audio_file.url`.

## 3. Session / token flow (Option 1 — session-gated streaming)
We reuse the existing `LibraryAudioSession` as the short-lived, user-scoped
token — no new token system was needed:

1. The player calls the existing `chapter_audio_start` endpoint, which creates
   an `in_progress` `LibraryAudioSession` **after a quota check** (HTTP 402 when
   minutes are exhausted).
2. Only then does the JS set the audio `src` to
   `…/audio/stream/?s=<session_id>`.
3. The stream view accepts the request **only** when a `LibraryAudioSession`
   exists with that id, `user == request.user`, `chapter_id == chapter.pk`, and
   `status == "in_progress"`. Otherwise → `403`.
4. On `ended`/stop the existing `chapter_audio_finish` endpoint closes the
   session and deducts the elapsed seconds.

A user cannot reach the stream without first opening a quota-checked session,
and cannot reuse another user's (or a finished) session.

## 4. Student access rules (all enforced by the stream view)
- `login_required`.
- `request.user.profile.is_subscribed` must be true → else `403`.
- Book must be `is_published=True` **and** `is_copyright_cleared=True` → else `404`.
- Chapter must belong to that book and have an `audio_file` → else `404`.
- A valid in-progress session for this user + chapter must be supplied → else `403`.

## 5. Platform Admin preview behavior
Admins preview through `library_chapter_audio_preview`, gated by
`CAP_LIBRARY_VIEW` (staff capability). It streams via the same secure helper,
so the admin page no longer embeds the raw `MEDIA_URL` either. No student
subscription / session is required for the staff preview — the capability check
is the gate.

## 6. Library minute enforcement
Unchanged and intact. Minutes are still created/checked at `start` and deducted
at `finish` exactly as before. The new stream route does **not** alter any
minute math; it only refuses to serve bytes unless a live session exists, which
closes the raw-URL bypass. External hosted `audio_url` chapters (admin-set, not
our `MEDIA_URL`) still play through the same start → finish session, so their
minutes are also deducted.

## 7. What is intentionally NOT included
- ❌ DRM / encryption of the audio.
- ❌ Perfect download prevention (a determined logged-in subscriber with a live
  session can still capture the stream — this stops casual raw-link sharing and
  minute bypass, not screen/stream capture).
- ❌ HTTP Range / seek support (full file is returned; documented as a later
  enhancement — `Accept-Ranges` is deliberately not advertised).
- ❌ Segment-level timestamps.
- ❌ Audio generation / TTS. ❌ Translation / vocabulary generation.
- ❌ Publishing The Black Tulip to students.
- ❌ AI Tutor / Daily Quiz / payment / subscription changes.

## 8. Production notes
- In production, media should be served as **private** files. The app-level
  stream view is the gate; ensure nginx (or the CDN) does **not** also expose
  `/media/library/audio/...` directly. Prefer an internal-redirect pattern
  (e.g. nginx `X-Accel-Redirect` to an `internal;` location) so the gate cannot
  be bypassed at the web-server layer. The response already sets
  `X-Accel-Buffering: no` and `Cache-Control: private, no-store`.
- Until media is locked down, direct `MEDIA_URL` serving of protected audio
  must be disabled at the proxy; otherwise the bytes remain reachable outside
  the app gate even though the HTML no longer links them.

## 9. Next phase recommendation
**Prompt 19.0G-Git — Commit and Push Secure Library Audio Delivery.**
After that, a hardening follow-up could add nginx internal-redirect serving and
HTTP Range support for seeking.

---

### Files added / changed
- `library/services/audio_delivery.py` — secure `audio_file_response` helper (new).
- `library/views.py` — `chapter_audio_stream` view; `chapter_listen` exposes the
  secure stream URL instead of the raw URL.
- `library/urls.py` — `library_audio_stream` route.
- `templates/library/chapter_listen.html` — plays via the session-scoped stream
  route; no raw `MEDIA_URL`.
- `platform_admin/views_library.py` — `library_chapter_audio_preview` (staff).
- `platform_admin/urls.py` — preview route.
- `platform_admin/templates/platform_admin/library/chapter_audio.html` — preview
  uses the secure route.
- `library/tests/test_secure_audio.py` — stream + preview tests (new).
- `platform_admin/tests/test_chapter_audio.py` — integration tests updated to the
  secure flow.

19.0G secured library chapter audio delivery so uploaded audio is not exposed through raw MEDIA_URL links.

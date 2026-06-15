# Onlenco — Platform Admin Chapter Audio Upload (Phase 19.0F)

## 1. Purpose
Let a non-technical admin upload a **per-chapter audio recording** for a library book (e.g. The Black Tulip's 33 chapters) directly from the Platform Admin / Control Center, see each chapter's audio status, and have students hear the uploaded recording — all without Django admin, without committing audio to Git, and without generating any TTS.

## 2. Why audio is uploaded from Platform Admin
Files must NOT be hand-placed in a production folder. Uploading through the Control Center routes the file into managed media storage, applies validation (type/size/safe name), records status, and keeps the workflow auditable and role-gated.

## 3. Chapter-level audio model
Reuses the **existing** `Chapter` fields — **no migration**:
- `audio_file` (FileField, `upload_to="library/audio/%Y/%m/"`)
- `audio_url` (URLField, optional external)
- `duration_seconds` (PositiveIntegerField)
- `Chapter.has_audio` (property) / `Chapter.get_audio_src()` (method)

## 4. Supported formats
`.mp3`, `.wav`, `.m4a` only. Extension + (best-effort) content-type are validated; PDFs/images/scripts are rejected; the basename's extension is used (blocks path traversal).

## 5. File size setting
`LIBRARY_CHAPTER_AUDIO_MAX_MB` (default **100**, env-overridable) in `config/settings/base.py`. The form reads it via `getattr(settings, ..., 100)` so a missing env never breaks.

## 6. Storage path
Files land under `MEDIA_ROOT/library/audio/%Y/%m/...` (the field's `upload_to`). Never under `static/`, never in Git, never in `local_content_sources`. The DB stores the FileField relative name (not an absolute path).

## 7. Upload / replace / remove workflow
Page: `/admin/library/chapters/<id>/audio/`
- Shows current status (Audio attached / Missing audio), filename, duration, an inline player.
- **Upload / Replace:** `PlatformChapterAudioUploadForm` (multipart) → validates → saves `audio_file` + optional `duration_seconds`.
- **Remove:** `POST /admin/library/chapters/<id>/audio/remove/` deletes the stored file and clears `audio_file`/`duration_seconds`. It does **not** touch copyright/publish.
- Warnings shown: "This is chapter-level audio." / "Segment-level timestamps are not included yet."

## 8. Audio status in dashboard / book detail
- **Dashboard** (`/admin/library/`): new counters **Chapters with audio** / **Chapters missing audio**.
- **Book detail** (`/admin/library/books/<id>/`): each chapter row shows an **Audio / No audio** badge and an **Audio** link to the upload page.

## 9. Library minutes enforcement
The student listen page (`chapter_listen`) now prefers the uploaded recording when present (`chapter_audio_src`); otherwise it falls back to the existing Natural Reader (TTS). Either way playback still opens a **`LibraryAudioSession`** via the existing `start → finish` endpoints, so library minutes are deducted exactly as before — **no minutes logic changed**. The pre-recorded player calls `start` (quota gate, 402 when exhausted) and `finish` (deduct elapsed) just like the TTS path.

## 10. What is intentionally NOT included
- ❌ Bulk zip upload of all 33 files (per-chapter upload only for this MVP).
- ❌ Segment-level audio / timestamps.
- ❌ Audio generation / TTS for this phase. ❌ Translation generation. ❌ Vocabulary generation.
- ❌ Publishing the novel to students. ❌ AI Tutor / Daily Quiz / payment / subscription changes.

## 11. Next phase recommendation
**Bulk chapter-audio upload** (upload all 33 recordings in one batch, matched to chapters by order), then **segment-level timestamps** so the reader can highlight while the recording plays.

---

### Files added / changed
- `config/settings/base.py` — `LIBRARY_CHAPTER_AUDIO_MAX_MB`.
- `library/forms.py` — `PlatformChapterAudioUploadForm` (+ allowed ext/content-type constants).
- `platform_admin/views_library.py` — `library_chapter_audio`, `library_chapter_audio_remove`, dashboard audio counters.
- `platform_admin/urls.py` — chapter audio routes.
- `platform_admin/templates/platform_admin/library/` — `chapter_audio.html` (new) + `dashboard.html` / `book_detail.html` (audio status).
- `library/views.py` + `templates/library/chapter_listen.html` — use uploaded recording through the existing minutes session.
- `platform_admin/tests/test_chapter_audio.py` — 15 tests.

### Risk note
A pre-recorded `audio_file` is served from `MEDIA_URL` (a public path, like any media). Normal listening goes through the minutes session, but the raw file URL is not itself minute-gated — hardening it (signed URLs / a streaming view) is a separate task and is noted here, not done in this MVP.

Next: **Prompt 19.0F-Git — Commit and Push Platform Admin Chapter Audio Upload.**

19.0F added Platform Admin chapter audio upload without committing audio files or generating new TTS.

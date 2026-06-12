# Onlenco — Interactive Novel Reader UI & Safe Demo Novel (19.0C)

> First student-facing reader UI + one short, copyright-safe demo novel.
> No quizzes, no Daily-Quiz integration, no XP/streak, no image/audio
> generation, no OpenAI, no raw PDF imported. Reuses the existing Natural
> Reader and library-minute metering. Builds on 19.0B schema.
> Branch: `feat/beginner-media-and-tutor-usage`.

---

## 1. What Was Added

- **Library nav link** in the app header (`Library` / `المكتبة`), mobile-friendly, for authenticated users.
- **Reader view + route**: `chapter_reader` at `/library/chapters/<chapter_id>/reader/` (`library_chapter_reader`).
- **Reader template** `templates/library/chapter_reader.html` — segmented reader with translation toggle, vocabulary popups, Arabic summary, and a Listen button.
- **"Read interactively" link** on the book-detail page (shown only when the book is cleared and has published segments).
- **Safe demo seed** `python manage.py seed_library_demo_black_tulip`.
- **Tests** — `library/tests/test_novel_reader_ui.py` (16 tests).

No new model/migration — purely view/template/command/test on top of the 19.0B schema.

---

## 2. Demo Novel Policy

The seeded book "The Black Tulip — Demo Reader":
- `copyright_status = adapted_original`, `is_copyright_cleared = True`.
- `is_school_curriculum = True`, `school_country = "Sudan"`, `school_stage = "Secondary"`, `target_cefr_level = "A2"`.
- 1 chapter, 4 very short **original** segments, each with an Arabic translation, a short Arabic explanation, and 3 vocabulary words.
- One `needs_review` illustration row with **no file** — proves the approval gate (never student-visible).

The text is **original Onlenco prose** that only borrows the public-domain *theme* of Dumas' story (a rare black tulip, a young grower, hope/jealousy/prison/courage). **No source passages are reproduced.**

---

## 3. Why the PDF Was Not Imported

`The_Black_Tulip-Alexandre_Dumas_pere.pdf` sits untracked in the repo root. It is **not** added to Git, **not** read, and **not** used as a project file. The demo content is hand-written original text, so there is zero dependency on the PDF and no risk of copying a copyrighted school/publisher edition. The PDF stays a future *reference only*.

---

## 4. Reader UI Behavior

`templates/library/chapter_reader.html` renders each published segment as a card:
- Part number + optional title.
- Illustration **only** when `is_student_visible` (approved + file); otherwise nothing (clean).
- English text (`text_en`).
- Translation toggle (Arabic).
- Tappable vocabulary chips.
- "Explanation in Arabic" box (`arabic_summary`).
- A **Listen** button (top) linking to the existing Natural Reader page.

**Progressive enhancement:** the translation toggle and vocabulary popups use native HTML `<details>`/`<summary>` — they work **without JavaScript**. With JS off, all text, translations, meanings, and summaries remain reachable. The layout is Tailwind-responsive (`max-w-3xl`, flex-wrap), mobile-first, RTL-aware (`dir="rtl"` on Arabic blocks).

---

## 5. Translation Toggle

Each segment with `text_ar` renders a `<details data-testid="segment-translation">` whose summary is "Show Arabic translation / إظهار الترجمة العربية". The Arabic text is in the DOM (so it is testable and accessible) but **collapsed by default** — shown only when the student opens it. English is the default reading language.

---

## 6. Vocabulary Highlights

Active `NovelVocabularyHighlight`s render as chips; opening a chip (`<details>`) reveals `meaning_ar`, optional `explanation_ar`, and an optional `example_sentence`. Matching is by word/phrase (offsets are not required), exactly as the 19.0B schema intended.

---

## 7. Natural Reader Integration

The Listen button **reuses the existing chapter Natural Reader** (`library_chapter_listen` → `library_audio_service` start/chunk/finish). That pipeline already:
- normalizes text via `text_humanizer` (no commas/underscores/HTML read aloud),
- reads English only,
- uses the user's selected voice,
- opens a `LibraryAudioSession` and **deducts library minutes on finish**.

**Documented gap:** per-segment audio (reading just one segment) is not yet wired — the current Listen reads the chapter via the existing endpoint. Per-segment listening + an inline player is a **19.0E** enhancement; no new audio service was built in 19.0C, per scope.

---

## 8. Subscription / Library-Minutes Behavior

- The reader requires `profile.is_subscribed` (unsubscribed → redirect to subscribe).
- Remaining library minutes are shown at the top of the reader (read from `quota_service.get_remaining_library_seconds`).
- When minutes run out, the existing Natural Reader returns its quota-exhausted response (HTTP 402). A friendly Arabic message — "انتهى وقت الاستماع في المكتبة اليوم حسب خطتك." — is the intended copy for the listen screen; the deduction itself is unchanged and owned by the existing service.

---

## 9. Copyright Gate

A chapter is readable only when **`book.is_published` AND `book.is_copyright_cleared`** (enforced in `chapter_reader` via `get_object_or_404`). Non-cleared books → 404. Only **published** segments render; non-`is_student_visible` illustrations never render. The legacy library list keeps its existing `is_published` gate; the copyright gate is enforced at the novel-reader boundary so existing non-novel books are unaffected.

---

## 10. Remaining Work (19.0D / 19.0E / 19.0F)

- **19.0D** — vocabulary interaction polish + richer Arabic explanations (inline tap targets within the text, not just chips).
- **19.0E** — per-segment AI voice reading + voice picker inline + tighter per-segment library-minute accounting.
- **19.0F** — Duolingo-style part quizzes (reuse `LessonQuestion` + `ChallengeSession`), then XP/streak.

---

> **19.0C added the interactive reader UI with a safe demo novel without importing the raw PDF or copyrighted school edition content.**

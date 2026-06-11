# Onlenco — Interactive Novel Reader MVP: Schema & Admin (19.0B)

> Additive schema + admin only. No reader UI, no quizzes, no content, no media
> generation, no OpenAI calls, no copyrighted novel text imported. Book/Chapter
> were reused untouched. Builds on the 19.0A audit.
> Branch: `feat/beginner-media-and-tutor-usage`.

---

## 1. What Was Added

- **`Book` extended** with copyright/provenance + school-curriculum fields (additive, conservative defaults).
- **`NovelSegment`** — breaks a `Chapter` ("part") into small reader cards (English text + optional Arabic translation + optional Arabic summary).
- **`NovelVocabularyHighlight`** — tappable vocabulary attached to a segment.
- **`NovelIllustration`** — one illustration per segment on the existing media-review lifecycle (`GeneratedMediaReviewMixin`).
- **Admin** for all of the above + copyright filters on `Book` and a segment count on `Chapter`.
- **Migration** `library/0008_…` (additive: add fields + create 3 models; no deletions/renames).
- **Tests** `library/tests/test_novel_reader_schema.py` (13 tests).

No reader UI, no quiz wiring, no Daily-Quiz integration, no content — by design.

---

## 2. Why Book / Chapter Were Reused

19.0A established that the Library is already built. A novel maps cleanly onto the existing types:

- `Book` = **Novel** (title/author/level/category=`novel`/cover/pdf/code).
- `Chapter` = **Novel part** (body, optional audio, sort_order, code).

So 19.0B adds only what was missing — **segment-level granularity, per-segment illustration/translation/explanation, vocabulary highlights, and copyright provenance** — without a parallel `Novel`/`NovelPart` hierarchy. This keeps the Natural Reader, library-minute metering, and existing library tests intact.

---

## 3. Copyright Fields (on `Book`)

| Field | Type | Default | Purpose |
|-------|------|---------|---------|
| `copyright_status` | choice | `unknown` | unknown / public_domain / licensed / adapted_original / school_excerpt_with_permission |
| `source_title` | char | "" | Original work title (e.g. Gutenberg edition) |
| `source_url` | url | "" | Where the source text legitimately comes from |
| `license_notes` | text | "" | Permission/license detail |
| `is_copyright_cleared` | bool | **False** | **Publish gate** — must be True before student-facing |
| `content_language` | char | `en` | Content language |
| `target_cefr_level` | choice | "" | Target CEFR |
| `is_school_curriculum` | bool | False | Sudan-curriculum flag |
| `school_country` | char | "" | e.g. "Sudan" |
| `school_stage` | char | "" | e.g. "Secondary — Certificate" |
| `curriculum_notes` | text | "" | Free notes |

**Gate rule (intended for 19.0C):** a title is student-facing only when `is_copyright_cleared=True` AND `is_published=True`. Defaults (`unknown` + not cleared) ensure no existing book is mistakenly treated as cleared novel content.

---

## 4. NovelSegment Design

`NovelSegment(chapter FK, order, title, text_en, text_ar, arabic_summary, cefr_level, estimated_reading_seconds, estimated_audio_seconds, is_published, created_at, updated_at)`

- **Unique** `(chapter, order)`; **ordering** `(chapter, order, id)`.
- `text_ar` powers the **translation toggle**; `arabic_summary` is the **short Arabic explanation** at the end of a segment.
- `estimated_audio_seconds` lets the reader (19.0E) pre-bound a listen against `library_session_cap_seconds` without re-synthesizing.
- `is_published` defaults **False** so a half-authored segment is never shown.

---

## 5. Vocabulary Highlight Design

`NovelVocabularyHighlight(segment FK, word, phrase, meaning_ar, explanation_ar, example_sentence, cefr_level, start_offset?, end_offset?, order, is_active)`

- **Word/phrase is enough for the MVP.** `start_offset`/`end_offset` are **nullable** on purpose — text may be re-edited and offsets would drift. The reader matches by word/phrase, using offsets only when present and still valid.
- `meaning_ar` (required) + optional `explanation_ar`/`example_sentence` drive the tap-word popup.
- `is_active` lets editors hide a highlight without deleting it.

---

## 6. NovelIllustration / Media Lifecycle

`NovelIllustration(segment FK, description, image, alt_text, order)` **+ `GeneratedMediaReviewMixin`**.

- Reuses the exact lesson-media lifecycle: `generation_status ∈ {pending_generation, generated, needs_review, approved, rejected, failed}` + review provenance fields.
- `is_student_visible == (generation_status == "approved" and bool(image))` — **pending / failed / rejected illustrations are never shown** to students (verified by tests). The reader (19.0C+) gates on this property exactly like lesson images.
- No generation happens in 19.0B; uploads/approval are admin-driven for now.

---

## 7. Admin Workflow

- **`Book`** — fieldsets for Copyright/provenance and School curriculum; list filters: `copyright_status`, `is_copyright_cleared`, `is_school_curriculum`, `school_country`, `target_cefr_level`.
- **`Chapter`** — adds a `Segments` count column (annotated, cheap); existing fields untouched.
- **`NovelSegment`** — list (chapter/order/title/cefr/is_published), filters, search; inlines for vocabulary highlights and illustrations.
- **`NovelVocabularyHighlight`** — list/filter/search by word/phrase/meaning.
- **`NovelIllustration`** — list shows `generation_status` + a boolean **Student visible** column; filter by status.

Editor flow: create a `Book` (set copyright) → add `Chapter`s → split each chapter into `NovelSegment`s → add highlights + (later) illustrations → approve illustrations → publish.

---

## 8. Intentionally Not Included Yet

- Reader UI / templates (19.0C).
- Duolingo-style part quizzes — will **reuse** `LessonQuestion` + `ChallengeSession` (19.0F), not new tables.
- Daily-Quiz vocabulary review (19.0G).
- AI image/audio generation, OpenAI calls, manifests.
- Any novel content or seed data. The untracked `The_Black_Tulip-Alexandre_Dumas_pere.pdf` in the repo root is **excluded** — not added to Git, not imported, noted only as a future public-domain source.

---

## 9. Next Phase

**Prompt 19.0C — Interactive Novel Reader UI and Safe Demo Novel:** build the segmented reader (translation toggle, tap-word vocabulary, voice picker via the existing Natural Reader, per-segment Arabic summary), gated on `is_copyright_cleared` + `is_published`, with one copyright-safe `adapted_original` demo.

---

> **19.0B added the Interactive Novel Reader MVP schema and admin without importing copyrighted novel content.**

# Onlenco — Black Tulip Full Import Pipeline (19.0D)

> A safe pipeline to import the full public-domain novel from a LOCAL source
> into review-only DB rows. The raw PDF is never committed; the full novel is
> never auto-published to students. No images/audio generated, no OpenAI.
> Branch: `feat/beginner-media-and-tutor-usage`.

---

## 1. Why the Full Book Was Not Imported in 19.0C

19.0C shipped a tiny, copyright-safe `adapted_original` demo so students had a
working reader without any bulk text. The full novel is much larger (≈74k
words, 237 PDF pages) and must be **cleaned, chaptered, segmented, and human-
reviewed** before it is fit to publish — that is exactly what this pipeline
does, behind a copyright gate.

---

## 2. Source PDF Policy

- The source file (`The_Black_Tulip-Alexandre_Dumas_pere.pdf`) lives **outside
  Git**. It is added to `.gitignore` (`*.pdf` + `local_content_sources/`) so it
  can never be committed.
- The importer accepts any local path via `--source` and never assumes the file
  is inside the repo. Production does not depend on it.
- Recommended convention: keep source files under a local, untracked
  `local_content_sources/` directory.
- Missing source → a **clean `CommandError` message**, never a traceback.

---

## 3. Import Command Usage

```
# Preview (writes nothing):
python manage.py import_black_tulip_pdf --source /path/The_Black_Tulip.pdf --dry-run
python manage.py import_black_tulip_pdf --source /path/file.pdf --dry-run --max-chapters 2

# Write review rows (NON-student-visible):
python manage.py import_black_tulip_pdf --source /path/file.pdf --apply
python manage.py import_black_tulip_pdf --source /path/file.pdf --apply --replace
```

Flags: `--source` (required), `--dry-run` (default behavior), `--apply`,
`--max-chapters N`, `--replace`. There is **no `--publish`** — publication is a
separate human action.

A `.txt` source is also accepted (used by tests and for clean re-imports
without a PDF library).

---

## 4. Dry-run vs Apply

- **Dry-run** (default): extract → clean → detect → segment, then print page
  count, cleaned word count, chapters detected, segments expected, first 3
  chapter titles, a short first-segment preview, and warnings. **No DB writes.**
- **Apply**: same pipeline, then create/refresh the review `Book` + `Chapter`s +
  `NovelSegment`s in one transaction. Always `is_published=False` and
  `is_copyright_cleared=False`. No illustrations or vocabulary are created.

---

## 5. Cleaning Strategy (`novel_importer.clean_text`)

- NFKC-normalize; strip `\x00`, the replacement char `�`, other control chars,
  and zero-width/invisible chars (`​`–`‍`, BOM, soft hyphen).
- Repair hyphenation across line breaks (`exam-\nple` → `example`).
- Drop standalone page-number lines.
- Collapse runs of spaces; collapse 3+ newlines to a paragraph break.
- Emit warnings (null chars removed, replacement chars found, page-number lines
  dropped) so reviewers know where the source was lossy. Raw uncleaned text is
  never persisted.

---

## 6. Chapter Detection Strategy (`detect_chapters`)

- Detect headings: a line that is a bare UPPERCASE roman numeral (`I`, `II`, …,
  uppercase-only to avoid the pronoun "i"), optionally prefixed by `CHAPTER`,
  or `CHAPTER <digits>`. Roman numerals are validated and range-checked.
- If fewer than 2 headings are found, **fall back** to fixed ~1500-word chunks
  so the importer is never fragile (with a warning).
- Real PDF result: **33 chapters detected** (≈591 expected segments).

---

## 7. Segment Strategy (`segment_text`)

- Split each chapter into ~120-word segments (soft ceiling 160) on **sentence
  boundaries** — never mid-sentence.
- `estimated_reading_seconds` / `estimated_audio_seconds` computed from word
  count (200 / 150 wpm).
- `text_ar`, `arabic_summary` left empty (filled in 19.0E); `is_published=False`.

---

## 8. Copyright Review Gate

The imported Book is `copyright_status=public_domain` but **`is_copyright_cleared=False`
and `is_published=False`**, and every segment is `is_published=False`. The
reader gate (`chapter_reader`) requires `is_published` AND `is_copyright_cleared`,
so the imported novel returns **404 for students** until a human reviews and
clears it. Even public-domain source text is not auto-published — the school
edition concern means a human must confirm the text is an acceptable,
non-infringing version.

---

## 9. Admin Review Workflow

No new admin fields/migration were needed — the existing `BookAdmin` filters
already isolate import-review books:
- Filter `is_copyright_cleared = No` + `copyright_status = public_domain` +
  `is_published = No` to find imports awaiting review.
- `NovelSegmentAdmin` filters by `is_published` and `chapter__book` to walk the
  segments; search by `text_en`.
- Reviewer flow: read segments → fix any extraction artifacts → (19.0E) add
  translations/vocabulary → set `is_published=True` on good segments → finally
  set the Book `is_copyright_cleared=True` + `is_published=True` to publish.

---

## 10. What Is Not Included Yet

- **Translation** (`text_ar`) — empty after import.
- **Vocabulary auto-highlight** — none created by the importer.
- **Audio per segment** — uses the existing chapter Natural Reader only.
- **Quizzes / Daily-Quiz** — not wired.
- **Publication** — deliberately manual; no `--publish`.
- **New dependency note:** `pypdf` was added to `requirements.txt` — it is the
  minimal, pure-Python library needed to extract PDF text. The cleaner /
  detector / segmenter are library-independent and tested via a `.txt` fixture.

---

## 11. Next Phase

**Prompt 19.0E — Black Tulip Translation and Vocabulary Highlight Generation
Workflow:** fill `text_ar` + `arabic_summary`, generate `NovelVocabularyHighlight`s
per segment, and add a reviewer flow to publish cleared segments.

---

> **19.0D added a full Black Tulip import pipeline for admin review without committing the raw PDF or publishing the full novel to students.**

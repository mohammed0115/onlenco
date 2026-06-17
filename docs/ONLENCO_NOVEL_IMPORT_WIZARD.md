# Onlenco — Novel Import Wizard for Platform Admin (Phase 19.0I)

## 1. Purpose
Let a non-technical admin turn a novel document (PDF/TXT/DOCX) into structured
`Book → Chapter → NovelSegment` text **from the Control Center**, with a safe
**dry-run analysis** first and a **hidden-by-default** import — no developer, no
Django admin, no command line required.

## 2. Why a Platform Admin wizard is needed
The CLI importer (`import_black_tulip_pdf`) is developer-only and hard-coded to
one book. Product owners need to import any novel themselves, preview what will
be created before committing, and keep everything behind the copyright/publish
gate. The wizard generalises the same extraction/segmentation engine behind a
guided UI.

## 3. Supported formats
- **PDF** — text extracted with `pypdf`.
- **TXT** — read as UTF-8 (safe fallback on bad bytes).
- **DOCX** — accepted at upload, but extracted **only if `python-docx` is
  installed** on the server. It is **not** installed today, so a DOCX upload is
  reported clearly at analyze time ("DOCX support is not enabled on this
  server") rather than failing silently. No new dependency was added.

## 4. Upload validation
`PlatformNovelImportUploadForm` enforces:
- extension whitelist `.pdf/.txt/.docx` (only the **basename** ext — blocks path
  traversal); an explicit blocklist rejects `.exe/.js/.html/.zip/.png/.mp3/…`;
- best-effort content-type check;
- size limit `LIBRARY_NOVEL_IMPORT_MAX_MB` (default **50 MB**, env-overridable);
- the uploaded file is stored under `MEDIA_ROOT/library/imports/%Y/%m/` — never
  in Git, never student-facing.

## 5. Text extraction vs OCR detection
- The engine extracts the embedded text layer only.
- For PDFs it computes words-per-page; below
  `OCR_WORDS_PER_PAGE_THRESHOLD` (10) it sets `needs_ocr=True` and adds a
  warning ("This file appears scanned … needs OCR").
- **OCR is never run automatically** in this phase — detection/warning only. A
  `needs_ocr` job has its Import button disabled.

## 6. Dry-run / analyze workflow
`Analyze` runs `novel_importer.analyze_source` and stores on the job: page
count, word count, detected text layer, `needs_ocr`, chapters detected,
segments expected, first 3 chapter titles, a short first-segment preview, and
warnings. It **writes no Book/Chapter/Segment** and publishes nothing. It is
repeatable.

## 7. Import / apply workflow
`Import` runs `novel_importer.import_novel` inside `transaction.atomic` and
creates the Book + Chapters + NovelSegments from the metadata form. Regardless
of metadata it **forces**:
- `Book.is_published = False`, `Book.is_copyright_cleared = False`;
- segments `is_published = False`, `text_en` filled, `text_ar=""`,
  `arabic_summary=""`;
- no vocabulary, no illustrations, no audio, no publishing.
The job is linked to the created book (`created_book`) and marked `imported`.

## 8. Hidden-by-default rule
An imported book is invisible to students (`is_published=False`) until a human
explicitly publishes it. Students only ever see books that pass the publish gate.

## 9. Copyright review gate
`copyright_status` defaults to `unknown` (admin may pick public_domain /
licensed / adapted_original / school_excerpt_with_permission). Publishing stays
governed by `library.services.publishing.can_publish_book`: needs a non-unknown
cleared copyright, published segments with text, etc. An `unknown` import can
never be published.

## 10. Admin review after import
After import the admin lands on the Book Review page to set copyright, review
segments, and decide on publishing. The import job list and dashboard counters
(jobs / failed / needs-OCR / imported-hidden-books) track progress. Books list
shows "Text imported" and "Imported via wizard" badges.

## 11. Audio upload after import
Chapter audio is added separately via the existing Platform Admin chapter audio
upload (19.0F) and served through the secure stream (19.0G). The wizard never
creates or generates audio.

## 12. What is intentionally NOT included
- ❌ Automatic OCR (detection/warning only).
- ❌ Translation (`text_ar`) generation.
- ❌ Vocabulary generation. ❌ Illustration generation.
- ❌ Audio generation. ❌ Quiz/comprehension generation.
- ❌ Automatic publishing of any imported novel.
- ❌ Adding a new DOCX dependency.
- ❌ OpenAI / AI Tutor / Daily Quiz / payment / subscription changes.

## 13. Production notes
- Take a **DB backup** before large imports.
- Uploaded sources live in **media storage** (`library/imports/…`), which must
  be private and is **never committed to Git** (`*.pdf`, `media/` are ignored).
- For production, ensure the media path for import sources is not publicly
  served (same principle as 19.0G secure audio).

## 14. Next phase recommendation
**Prompt 19.0I-Git — Commit and Push Novel Import Wizard.**

---

### Files added / changed
- `library/models.py` — `LibraryImportJob` model (+ migration `0009_libraryimportjob`).
- `library/services/novel_importer.py` — `analyze_source`, generalized `import_novel`,
  `source_format`, DOCX branch + OCR detection.
- `library/forms.py` — `PlatformNovelImportUploadForm`, `PlatformNovelImportMetadataForm`.
- `platform_admin/views_library.py` — wizard views + dashboard/books counters.
- `platform_admin/urls.py` — wizard routes.
- `platform_admin/templates/platform_admin/library/` — `imports_list.html`,
  `import_new.html`, `import_detail.html` (new) + dashboard/books badges.
- `config/settings/base.py` — `LIBRARY_NOVEL_IMPORT_MAX_MB`.
- `library/tests/test_novel_import_wizard.py` — wizard tests (new).

19.0I added a Platform Admin Novel Import Wizard with safe upload, analysis, and hidden-by-default import.

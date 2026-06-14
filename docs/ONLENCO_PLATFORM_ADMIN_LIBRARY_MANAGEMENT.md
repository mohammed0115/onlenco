# Report 19.0E — Platform Admin Library Management UI

## 1. Django Admin vs Platform Admin
- **Django Admin** (`/django-admin/`) is the framework's generic CRUD — technical, not for non-technical staff.
- **Platform Admin / Control Center** (`platform_admin` app, mounted at `/admin/` and `/control/`) is Onlenco's own in-product admin with role-based capabilities, a branded sidebar, bilingual UI, and safe action buttons. **19.0E adds Library Management here — NOT in Django admin.**

## 2. What was added
A full Library Management section inside the Control Center: a dashboard, a books list with filters/search, a book review/copyright/publish page, chapter+segment review, segment editor, vocabulary review, and illustration review — plus a publishing gate service and narrow forms.

## 3. Admin navigation
A new sidebar item **“Library Management / إدارة المكتبة”** (icon `book`, gated by `CAP_LIBRARY_VIEW`) added in `platform_admin/permissions.py` `nav_items_for`. Shown only to authorised admin/staff; never to students or anonymous visitors.

## 4. Library dashboard — `/admin/library/`
Counts + badges: total/published/draft books, needs-copyright-review, copyright-cleared, total chapters, total segments, published segments, total/active vocabulary, illustrations pending/approved. Badge legend: Needs copyright review · Ready to publish · Published · Draft · Hidden from students.

## 5. Books management — `/admin/library/books/`
Table per book: title, author, CEFR, copyright_status, cleared badge, published badge, school (country/stage), chapters/segments/published-segments counts, Review action. **Filters:** copyright_status, cleared, published, school curriculum, country, target CEFR. **Search:** title, source_title, school_stage, curriculum_notes.

## 6. Book review / copyright workflow — `/admin/library/books/<id>/`
`PlatformBookReviewForm` lets the admin edit safe fields: title, summary, copyright_status, source_title, source_url, license_notes, is_copyright_cleared, content_language, target_cefr_level, is_school_curriculum, school_country, school_stage, curriculum_notes. **`is_published` is NOT in the form** — publishing only happens through the gated action.

## 7. Publishing gate — `library/services/publishing.py`
`can_publish_book(book) -> PublishCheck(allowed, reasons)`. Blocks publishing unless: title non-empty; copyright_status != "unknown"; is_copyright_cleared=True; ≥1 chapter; ≥1 published segment; no published segment with empty `text_en`; and licensed/school-excerpt books carry a source title/URL/license notes. Used by the UI (shows reasons), the publish action, and tests.

## 8. Segment review workflow — `/admin/library/segments/<id>/`
`PlatformSegmentReviewForm` edits: title, text_en, text_ar, arabic_summary, cefr_level, estimated_reading_seconds, estimated_audio_seconds, is_published. The form **refuses to publish a segment with empty English text**. The book detail page lists every chapter + its segments with edit links.

## 9. Vocabulary review workflow
On the segment page, each highlight is editable via `PlatformVocabularyReviewForm`: meaning_ar, explanation_ar, example_sentence, cefr_level, is_active. **No generation** — manual review/edit only.

## 10. Illustration review workflow
Each illustration shows preview, status, and student-visibility badge. `PlatformIllustrationReviewForm` edits only **alt_text** and **order**. The `generation_status`/image are intentionally left to the existing media-review lifecycle (`GeneratedMediaReviewMixin`), so a pending/rejected image can never be flipped student-visible from here.

## 11. Permissions
New capabilities `CAP_LIBRARY_VIEW` / `CAP_LIBRARY_MANAGE` in `platform_admin/permissions.py`. Granted to Super Admin & Platform Admin (`*`), Academic Admin (view+manage), and Read-only Admin (view only). Read views use `@control_permission_required(CAP_LIBRARY_VIEW)`; every mutation re-checks `can_mutate(user, CAP_LIBRARY_MANAGE)`. Students → 403; anonymous → redirect to login; teachers without a library capability → 403.

## 12. What is intentionally NOT included
- ❌ Full PDF import (no importer built; no PDF read or added to Git).
- ❌ Translation generation. ❌ Vocabulary generation. ❌ Audio/image generation. ❌ Any OpenAI call.
- ❌ Quizzes. ❌ Changes to AI Tutor / Daily Quiz / payment / subscription / Library-minutes logic.

## 13. Next phase
**Translation + Vocabulary Highlight Workflow** (assisted review of segment translation + structured vocabulary), still behind the same publish gate.

---

### Forms / services added
- `library/services/publishing.py` — `can_publish_book`.
- `library/forms.py` — `PlatformBookReviewForm`, `PlatformSegmentReviewForm`, `PlatformVocabularyReviewForm`, `PlatformIllustrationReviewForm`.
- `platform_admin/views_library.py` — dashboard, books list, book detail/review, publish/unpublish action, segment edit, vocab edit, illustration edit.
- Templates under `platform_admin/templates/platform_admin/library/`: `dashboard.html`, `books.html`, `book_detail.html`, `segment_edit.html`.

### Tests added — `platform_admin/tests/test_library.py` (24)
Permissions (anonymous/student/teacher blocked; platform & academic admin allowed; nav link shown), dashboard counts, books list + needs-review badge, publish-gate conditions (unknown copyright, not cleared, no chapters, no published segments, empty title, licensed-needs-source, full book allowed), publish/unpublish actions (blocked when incomplete, works when complete, student forbidden), empty-segment publish rejected, vocab edit updates, pending illustration not student-visible, unpublished book → student reader 404.

### Final Status
- **Is this Django Admin?** **No.** It is the custom Platform Admin / Control Center.
- **Platform Admin Library Management built?** **Yes.**
- **Can the admin manage the library from the platform panel?** **Yes** (books, copyright, chapters/segments, vocabulary, illustrations, publish/unpublish).
- **Are students blocked from the admin pages?** **Yes** (403; anonymous → login).
- **Does the publish gate prevent unsafe publishing?** **Yes** (`can_publish_book`).
- **Was a PDF imported?** **No.**
- **Was translation/vocabulary/audio generated?** **No.**
- **Are check/tests green?** `manage.py check` = 0 issues; `makemigrations --check` = no changes; the 24 new tests pass; `library`+`platform_admin` suites pass except one **pre-existing flaky** teacher-registration test unrelated to this change (passes in isolation).

19.0E added Platform Admin Library Management UI separate from Django Admin.

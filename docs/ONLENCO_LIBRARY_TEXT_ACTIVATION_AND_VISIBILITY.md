# Onlenco — Library Text Activation & Visibility (Phase 19.0H)

## 1. Goal
Make **The Black Tulip** exist as real **text** inside the system
(`Book` → `Chapter` → `NovelSegment`) and hide every other library book /
demo from students **without deleting anything** — all books stay fully
visible and reviewable in Platform Admin.

## 2. Why text-in-DB beats a PDF for the student
- The interactive reader works on `NovelSegment.text_en` (per-segment paging,
  vocabulary highlights, illustrations, comprehension, secure audio). A PDF is
  an opaque blob the reader can't segment, highlight, or gate by minutes.
- Text stays inside our copyright/publish gate; a PDF tends to leak as a raw
  downloadable file (the same class of risk fixed for audio in 19.0G).
- Text is searchable, levelable (CEFR), and translatable later. The PDF stays
  **outside Git** and is only ever a one-time import source.

## 3. How The Black Tulip is imported as text
Existing pipeline (no new importer built this phase):

```
python manage.py import_black_tulip_pdf \
  --source The_Black_Tulip-Alexandre_Dumas_pere.pdf \
  --apply --replace
```

- The source PDF lives **outside Git** (`.gitignore: *.pdf`); only the extracted
  text rows are written to the DB.
- Creates `Book` "The Black Tulip — Full Import Review" with
  `is_published=False`, `copyright_status="public_domain"`,
  `is_copyright_cleared=False`, plus 33 `Chapter`s and 591 `NovelSegment`s.
- Each segment has `text_en` filled; `text_ar=""` and `arabic_summary=""`.
- No vocabulary, no illustrations, no audio, no auto-publish.

## 4. Hide vs delete
- **Hide** = `Book.is_published = False`. The book vanishes from the student
  library but is untouched in the DB and fully editable in Platform Admin.
- **Delete** = removing rows permanently. **Not done** in this phase — there is
  deliberately no `--delete` / hard-delete anywhere in the cleanup tooling.

## 5. Visibility policy for the other books
- **Keep:** "The Black Tulip — Full Import Review" (the full text).
- **Hide from students:** the safe demo Black Tulip, old seed books, and any
  book not wanted in the current student experience → `is_published=False`.
- Hiding never changes copyright clearance and never changes content.
- Implemented by the `library_visibility_cleanup` command (see §7). In the dev
  DB every book was already `is_published=False`, so the student library shows
  zero books until one passes the publish gate.

## 6. When a book becomes student-visible
Only when **all** hold (enforced by `library.services.publishing.can_publish_book`):
- `copyright_status != "unknown"`
- `is_copyright_cleared = True`
- `is_published = True`
- has at least one `Chapter`
- has at least one **published** `NovelSegment`
- those published segments have non-empty `text_en`

Until review is complete, The Black Tulip is **in the DB as text**, **visible in
Platform Admin**, and **hidden from students**.

## 7. Management command
```
python manage.py library_visibility_cleanup \
  --keep-book "The Black Tulip — Full Import Review" --hide-others --dry-run
python manage.py library_visibility_cleanup --keep-book-id 16 --hide-others --apply
```
- `--dry-run` (default) prints: kept book, currently-visible books, books that
  would be hidden, and the expected after-state — **writes nothing**.
- `--apply` sets `is_published=False` on every other book. It **never** deletes,
  **never** touches copyright clearance, **never** changes content, and **never**
  publishes the kept book.
- Requires `--keep-book` or `--keep-book-id`, and `--hide-others` to act.

## 8. What was intentionally NOT built
- ❌ Translation (`text_ar`) generation.
- ❌ Vocabulary highlight generation.
- ❌ Audio upload content itself (only the existing secure pipeline remains).
- ❌ Quizzes / comprehension generation.
- ❌ Production publishing of The Black Tulip.
- ❌ Hard-delete of any book.
- ❌ OpenAI / AI Tutor / Daily Quiz / payment / subscription changes.

## 9. Next step
**Prompt 19.0I — Novel Import Wizard for Platform Admin**: a guided in-UI
upload → preview → import → review flow so admins can run the import without the
command line.

---

### Files added / changed
- `library/management/commands/library_visibility_cleanup.py` — hide-others command (new).
- `platform_admin/templates/platform_admin/library/books.html` — "Text imported" /
  "Hidden from students" badges.
- `library/tests/test_visibility.py` — import + cleanup + visibility tests (new).

19.0H made The Black Tulip available as text content while hiding other library books from students without hard-deleting content.

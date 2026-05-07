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

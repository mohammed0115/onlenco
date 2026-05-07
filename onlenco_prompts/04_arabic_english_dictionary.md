# 04 — Arabic ↔ English Dictionary

## Context

This task adds the **Arabic–English dictionary** to the **Onlenco** Django
project — listed as a feature on the marketing page but not yet built.

Project conventions:
- `{% load i18n_dict %}` plus `{% t "key" %}` and `{% t_either "en" "ar" %}`.
- Tailwind via Play CDN + `static/css/onlenco.css`.
- Component classes: `.btn`, `.btn-hero`, `.btn-outline`, `.card`, `.badge`,
  `.input`, `.label`.
- Lucide icons: `<i data-lucide="..."></i>`.
- AI client pattern in `placement/services.py` (OpenAI-compatible).

## Goal

Add a `dictionary` app with a `DictionaryEntry` model and a search page
that lets logged-in users look up an English or Arabic word and see the
translation, part of speech, example sentences, and a small list of related
words.

The dictionary has a curated DB-stored set of common words, plus an optional
AI fallback for words that aren't in the DB. The AI fallback is cached so we
don't pay for the same word twice.

## Spec

### Models — `dictionary/models.py`

**`DictionaryEntry`**
- `english = CharField(max_length=80, db_index=True)`
- `arabic = CharField(max_length=80, db_index=True)`
- `pos = CharField(max_length=20, blank=True,
    choices=[
      ("noun","Noun"), ("verb","Verb"), ("adj","Adjective"),
      ("adv","Adverb"), ("prep","Preposition"), ("phrase","Phrase"),
      ("other","Other")])` — part of speech
- `example_en = CharField(max_length=300, blank=True)`
- `example_ar = CharField(max_length=300, blank=True)`
- `notes = TextField(blank=True)` — admin-only style/usage notes
- `source = CharField(max_length=20, default="curated",
    choices=[("curated","Curated"),("ai","AI-generated")])`
- `lookup_count = PositiveIntegerField(default=0)` — bump on each lookup,
  useful for "popular searches"
- `created_at = DateTimeField(auto_now_add=True)`
- Meta `ordering = ["english"]`, `unique_together = [("english","arabic")]`
- `__str__` returns `f"{english} ↔ {arabic}"`

### Service — `dictionary/services.py`

Two helpers:

**`search(query: str, lang_hint: str = "auto") -> List[DictionaryEntry]`**
- Normalize whitespace + lowercase the query.
- If `lang_hint == "auto"`, detect: if the query contains any character in
  the U+0600–U+06FF range, treat as Arabic; otherwise English.
- Query the DB:
  - English query → `Q(english__icontains=q)`, ordered by exact-match first,
    then prefix, then contains, then `-lookup_count`.
  - Arabic query → `Q(arabic__icontains=q)` with the same ordering rules.
- Return up to 20 entries.
- Bump `lookup_count` for the entries returned (single bulk `.update()` —
  don't loop).

**`ai_lookup(query: str, lang_hint: str) -> Optional[DictionaryEntry]`**
- Used only when `search()` returns nothing.
- If `AI_API_KEY` is empty → return `None` (no crash, no fallback fabrication).
- Call the same OpenAI-compatible endpoint pattern that `placement/services.py`
  uses, with a system prompt asking the model to return a single JSON object
  via function calling: `{english, arabic, pos, example_en, example_ar}`.
- On success, save a new `DictionaryEntry(source="ai")` and return it.
- On any error (API down, missing fields, bad JSON), log the error and return
  `None` — never crash.

Use Python's `logging` module (`logger = logging.getLogger(__name__)`).

### Views & URLs — `dictionary/views.py`, `dictionary/urls.py`

**`dictionary_view(request)`** — `GET /dictionary/?q=hello`
- `@login_required`. Subscription is **not** required (this is a free
  utility — the marketing page lists it without "subscribe to unlock").
- Read `q` from querystring. If empty: render the page with a search box
  and a "Popular lookups" section showing the top 12 entries by `lookup_count`.
- If `q` is present:
  1. Call `services.search(q)`.
  2. If empty, call `services.ai_lookup(q)`. If that returns an entry, show
     it with a small "AI-generated" badge so users know it isn't curated.
  3. If still empty, show a "No results found" empty state with a "Try a
     different spelling" hint.

URL:
```python
urlpatterns = [
    path("", views.dictionary_view, name="dictionary"),
]
```
Mount in `onlenco/urls.py`: `path("dictionary/", include("dictionary.urls"))`.

### Template — `templates/dictionary/dictionary.html`

- Standard `_app_header.html` shell.
- Big centred search box at the top with a search icon, autofocus.
  Form GETs to `?q=`. Bilingual placeholder: in EN show "Search English or
  Arabic…", in AR show "ابحث بالإنجليزية أو العربية…".
- Recent / popular lookups shown as pill links below the box when `q`
  is empty.
- Results list: each entry as a card with:
  - Big `english` and `arabic` next to each other (both in the appropriate
    direction)
  - Part-of-speech badge
  - Example sentences (en + ar) below in smaller text
  - A small "🤖 AI-generated" badge in the corner if `source == "ai"`
- Empty state with a friendly icon (Lucide `search-x`) and a tip.

### Admin — `dictionary/admin.py`

- `list_display = ("english", "arabic", "pos", "source", "lookup_count")`
- `list_filter = ("pos", "source")`
- `search_fields = ("english", "arabic")`
- `readonly_fields = ("lookup_count", "created_at")`

### Seed data — `dictionary/management/commands/seed_dictionary.py`

Create a `seed_dictionary` management command that loads ~60 high-frequency
words across parts of speech: hello/مرحبا, water/ماء, book/كتاب,
to read/يقرأ, fast/سريع, slowly/ببطء, on/على, etc. Include short example
sentences in both languages. Categorize each by `pos`.

Update `seed_demo.py` to call `call_command("seed_dictionary")`.

### i18n strings — add to `core/translations.py`

```python
"dict.title":         {"en": "Arabic ↔ English Dictionary",
                       "ar": "قاموس عربي ↔ إنجليزي"},
"dict.subtitle":      {"en": "Look up any word, see examples, learn faster.",
                       "ar": "ابحث عن أي كلمة، شاهد الأمثلة، تعلم بسرعة."},
"dict.search":        {"en": "Search",                  "ar": "بحث"},
"dict.search_hint":   {"en": "Search English or Arabic…",
                       "ar": "ابحث بالإنجليزية أو العربية…"},
"dict.popular":       {"en": "Popular lookups",         "ar": "الكلمات الشائعة"},
"dict.no_results":    {"en": "No results found.",       "ar": "لم يتم العثور على نتائج."},
"dict.ai_generated":  {"en": "AI-generated",            "ar": "مولّد بالذكاء الاصطناعي"},
"dict.example":       {"en": "Example",                 "ar": "مثال"},
"dict.pos.noun":      {"en": "noun",                    "ar": "اسم"},
"dict.pos.verb":      {"en": "verb",                    "ar": "فعل"},
"dict.pos.adj":       {"en": "adjective",               "ar": "صفة"},
"dict.pos.adv":       {"en": "adverb",                  "ar": "ظرف"},
"dict.pos.prep":      {"en": "preposition",             "ar": "حرف جر"},
"dict.pos.phrase":    {"en": "phrase",                  "ar": "عبارة"},
```

### Header / dashboard integration

- Add a "Dictionary" link in `_site_header.html`'s nav (visible to everyone)
  — between Curriculum and Pricing on the public site, leading to
  `/dictionary/` (will redirect to login for anonymous users).
- Add a "Dictionary" card in the dashboard secondary CTAs row alongside
  AI Tutor / Library. Use Lucide icon `book-a` or `languages`.

## Acceptance criteria

A reviewer should be able to:

1. Click "Dictionary" from the dashboard → land on `/dictionary/`.
2. See popular lookups when no query.
3. Search "hello" → see the curated entry with English, Arabic, examples.
4. Search "مرحبا" → see the same entry from the Arabic side.
5. Search a word that's not in the DB (e.g. "serendipity") → either get an
   AI-generated entry with the AI badge (if `AI_API_KEY` is set) or the
   "No results" empty state (if not).
6. The AI-generated entry is saved to the DB so the next search for the
   same word is instant.
7. Click a "Popular lookups" pill → it pre-fills the search box and runs
   the query.
8. In `/admin/`, edit an existing entry's translation or example.

`python manage.py check` and `python manage.py migrate` clean.

## Out of scope

- No verb conjugations, no diacritics handling beyond basic normalization,
  no morphological root mapping.
- No audio pronunciation.
- No flashcard / spaced-repetition saving.
- No bulk import from external dictionary files (CSV / dictionary APIs).
- No favorites or per-user history.

## Style guide

- The two big words (English + Arabic) on each result card should each be
  in their natural script direction. Use inline `dir="ltr"` and `dir="rtl"`
  on those spans regardless of the page direction.
- Results should feel close to a printed dictionary: serif display font for
  the headwords (Fraunces / Cairo), generous spacing, examples italicised.
- Search input: `.input` class, full width, with a Lucide `search` icon
  inside-left and a Lucide `arrow-right` submit hint inside-right.
- AI-generated badge: subtle, `badge-outline` with a small bot emoji or icon.

## What to deliver

A patched `onlenco_django.zip` with:

- New `dictionary` app added to `INSTALLED_APPS`
- `DictionaryEntry` model + migration
- `services.py` with `search()` and `ai_lookup()`
- `dictionary_view`, URL, template
- Admin
- `seed_dictionary` command + integration into `seed_demo`
- Header nav link + dashboard card
- New i18n strings

`python manage.py check` passes; `seed_demo` populates ~60 entries.

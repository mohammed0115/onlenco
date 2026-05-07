# 00 — Project Context (shared)

> **Note:** Every numbered prompt in this directory inlines the essential bits
> of this context, so you usually don't need to paste this file separately.
> It exists as a single source of truth.

## What Onlenco is

Onlenco is an AI-powered English learning platform aimed at Sudanese learners.
It was originally prototyped as a React/Vite + Supabase app, then ported to
Django. The marketing page promises:

- AI placement test (CEFR A0–C2)
- AI voice tutor
- Structured video lessons across reading / writing / listening / speaking
- Weekly English Club over Google Meet
- Digital library
- Arabic–English dictionary
- Local payment via Bankak / Fawry / O-Cash

## Existing Django apps

| App | What it does |
|-----|--------------|
| `accounts` | `Profile` model (CEFR level, subscription, role), email-based signup/login, language-preference middleware |
| `core` | Public landing page, EN/AR translation dict, language switcher, 404 |
| `lessons` | `Lesson` model (`title`, `description`, `skill`, `level`, `video_url`, `duration_minutes`, `sort_order`), student dashboard at `/dashboard/` |
| `placement` | `PlacementResult` model + AI scoring service that calls any OpenAI-compatible endpoint, deterministic fallback when no key |
| `payments` | `PaymentSubmission` model, screenshot upload, admin approve/reject actions, subscription activation/extension |

## Existing patterns to match

- **Templates** use a `{% load i18n_dict %}` helper that gives `{% t "key" %}`
  (looks up an EN/AR pair from `core/translations.py`) and
  `{% t_either "english" "عربي" %}` for one-off labels.
- **Styling** uses Tailwind via the Play CDN (config in `templates/base.html`)
  plus `static/css/onlenco.css` for design tokens — HSL color vars, gradients,
  and component classes (`.btn`, `.btn-hero`, `.btn-outline`, `.btn-ghost`,
  `.btn-glass`, `.btn-lg`, `.card`, `.badge`, `.badge-secondary`,
  `.badge-outline`, `.badge-popular`, `.input`, `.label`, `.radio-card`).
- **Icons** are Lucide via UMD bundle: `<i data-lucide="check"></i>`.
- **Auth** uses Django's built-in User model with email as username; the
  `Profile` is auto-created via a `post_save` signal.
- **Login required** is a function decorator: `@login_required` from
  `django.contrib.auth.decorators`.
- **Admin** is registered with `@admin.register(Model)` and uses concise
  `list_display` + `list_filter` + `search_fields`.
- **Models** use `models.BigAutoField` for IDs (set by `DEFAULT_AUTO_FIELD`).
- **Migrations** are committed to git — every prompt that adds a model must
  also include the new migration file.

## Code style

- Type hints are used sparingly — match the existing style (none in views,
  some in pure-Python service modules).
- Docstrings on classes and public functions, none on obvious one-liners.
- Comments explain *why*, not *what*. Keep them short and well-placed.
- No bullet lists in docstrings; prefer prose.
- Keep imports grouped: stdlib, Django, third-party, local. Each group
  separated by a blank line.

## What NOT to add

- No new dependencies unless absolutely necessary. The current `requirements.txt`
  is `Django + Pillow + requests` — keep it that way.
- No HTMX, Alpine, React, or other frontend frameworks. Server-rendered HTML
  with vanilla JS for interactions, matching what's already there.
- No DRF / GraphQL. Plain Django views.
- No new auth backends. Use the existing email-as-username pattern.

## i18n

Add new translation keys to `core/translations.py` in the `DICT` dict.
Always include both `en` and `ar` entries. Use the same naming convention
as existing keys: `area.subarea.detail`, e.g. `tutor.title`, `library.book.read`.

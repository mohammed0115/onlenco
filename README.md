# Onlenco — AI English Learning Platform (Django)

AI-powered English learning for Sudanese learners, with bilingual EN/AR UI, CEFR
placement testing, and the local payment flow (Bankak / Fawry / O-Cash) described
in the technical document.

## What's inside

| App | Responsibility |
|-----|----------------|
| `accounts` | `Profile` model (CEFR level, subscription, role), email-based signup/login, language-preference middleware |
| `core`     | Public landing page, the EN/AR translation dictionary, language switcher, 404 handler |
| `lessons`  | `Lesson` model (skill × CEFR level), student dashboard |
| `placement`| `PlacementResult` model + AI scoring service (OpenAI-compatible, with a deterministic offline fallback) |
| `payments` | `PaymentSubmission` model, screenshot upload, admin approve/reject actions, subscription activation |

## Quick start

```bash
# 1. Create a virtualenv
python -m venv .venv
source .venv/bin/activate

# 2. Install dependencies
pip install -r requirements.txt

# 3. Apply migrations
python manage.py migrate

# 4. Seed an admin user + 12 demo lessons (one shot)
python manage.py seed_demo
#   → creates admin@onlenco.local / onlenco123

# 5. Run
python manage.py runserver
```

Then open [http://localhost:8000](http://localhost:8000).
Sign in to the admin at [http://localhost:8000/admin/](http://localhost:8000/admin/)
with `admin@onlenco.local` / `onlenco123`.

> The default admin password is fine for local demos but **change it before
> deploying anywhere reachable**:
> `python manage.py seed_demo --admin-email you@example.com --admin-password "your-strong-pw"`

## Routes

| URL | What |
|-----|------|
| `/`              | Public landing page (hero, features, CEFR ladder, pricing) |
| `/auth/`         | Combined sign-in / sign-up. Add `?mode=signup` for the signup tab |
| `/auth/logout/`  | Sign out |
| `/dashboard/`    | Student dashboard — placement banner, lesson grid, subscribe CTA |
| `/placement/`    | AI placement test (4 questions → CEFR level) |
| `/payments/`     | Pick plan + method, upload transfer screenshot |
| `/payments/history/` | Past payment submissions and their statuses |
| `/admin/`        | Django admin — review pending payments, edit lessons, manage users |
| `/set-language/` | Toggle between English and Arabic (POST or GET `?lang=ar`) |

## AI placement scoring

The `placement.services.assess()` function calls any OpenAI-compatible
chat-completions endpoint with function calling. Configure it via env vars:

```bash
export AI_API_KEY="sk-..."
export AI_API_BASE="https://api.openai.com/v1"     # or any compatible gateway
export AI_MODEL="gpt-4o-mini"                       # or another model name
```

If `AI_API_KEY` is not set, the service falls back to a deterministic heuristic
scorer so the app stays demoable offline. The heuristic looks at MCQ correctness,
sentence count, and lexical variety.

## Payment flow (Sudan)

Mirrors section 4 of the technical document:

1. Student picks a plan (Monthly 8,000 SDG / Quarterly 18,000 SDG)
2. Student picks a method (Bankak / Fawry / O-Cash) and sees the destination
   account details
3. Student transfers the amount out-of-band
4. Student uploads a transfer screenshot in the Onlenco UI
5. Submission appears in `/admin/payments/paymentsubmission/` as `pending`
6. Admin reviews the screenshot and uses the **"Approve selected payments"**
   bulk action — this flips the user's `subscription_status` to `active` and
   sets `subscription_expires_at` to today + 30 / 90 days
7. If the user already has time on the clock, approve **extends** rather than
   resets the expiration

Account details for the three methods are stored in `PaymentMethodAccount` and
editable via `/admin/` (Payment method accounts).

## i18n

Translation strings live in `core/translations.py` as a flat dict. Templates use the `{% t "key" %}`
template tag (in `core/templatetags/i18n_dict.py`) for keyed strings and
`{% t_either "english" "عربي" %}` for one-off bilingual labels.

The active language is stored in the session and (for logged-in users) on the
`Profile.preferred_language` field, so it persists across devices.

## Architecture notes

- **No build step.** Tailwind ships via the Play CDN with a config block in
  `templates/base.html` that maps utility classes (`bg-primary`,
  `text-foreground`, `border-border`, …) onto HSL CSS variables defined in
  `static/css/onlenco.css` (teal/amber palette, gradients, shadows).
- **Auth.** Email is used as the username (Django's built-in `User` model
  needs *some* username, and email is the cleanest choice). The signup form
  copies email → username and creates the linked `Profile` automatically via
  a `post_save` signal.
- **Lucide icons.** Use the official Lucide UMD bundle. Templates write
  `<i data-lucide="check"></i>` and a small init script swaps each placeholder
  for the SVG on page load.

## Production checklist (when you're ready)

- [ ] Set `DJANGO_SECRET_KEY` and `DJANGO_DEBUG=0`
- [ ] Switch `DATABASES` to PostgreSQL
- [ ] Replace the Tailwind Play CDN with a built CSS file (`npx tailwindcss build`)
- [ ] Configure media storage (S3 / R2 / GCS) — payment screenshots are private
      user data and should not sit on the local filesystem
- [ ] Review `PaymentMethodAccount` entries in `/admin/` (real account numbers, availability)
- [ ] Add `ALLOWED_HOSTS`, HTTPS settings, CSRF trusted origins
- [ ] Real email backend for signup confirmation / password reset
- [ ] `gunicorn` + `whitenoise` (or a CDN) for static files
"# onlenco" 

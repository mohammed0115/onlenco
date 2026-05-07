# Onlenco Gap-Filling Prompts

## مقدمة (AR)

هذه حزمة من 12 prompt، كل واحد منها يصف فجوة واحدة في مشروع Onlenco (نسخة
Django) وكيفية إغلاقها بشكل كامل. كل ملف مستقل بذاته: ضع محتواه في محادثة جديدة
مع Claude (أو أي مساعد برمجي) مع إرفاق ملف المشروع `onlenco_django.zip`،
وستحصل على الكود الجاهز لتلك الميزة.

ال prompts مكتوبة بالإنجليزية لأن الكود نفسه (Django/Python) بالإنجليزية،
لكن نصوص الواجهة المطلوب توليدها بالعربية والإنجليزية معاً.

## How to use these prompts (EN)

Each file is a self-contained, copy-paste-ready prompt. Paired with the
`onlenco_django.zip` from the previous turn, each one fully specifies one
feature or fix, with models, views, templates, URLs, admin config,
acceptance criteria, and i18n strings.

### Recommended order

The prompts are numbered by **leverage** — earlier ones unlock more value
than later ones. You can run them in numeric order, or skip around if you
have different priorities.

| # | Prompt | Type | Why this order |
|---|--------|------|----------------|
| 01 | `lesson_detail_and_quizzes.md` | Feature | Makes the dashboard actually clickable; biggest gap |
| 02 | `ai_voice_tutor.md` | Feature | Headline feature from the marketing page; unlocks the homepage promise |
| 03 | `digital_library.md` | Feature | Listed in section 3; small + high value |
| 04 | `arabic_english_dictionary.md` | Feature | Listed in section 3; small + high value |
| 05 | `english_club_events.md` | Feature | Listed in section 3; events + Google Meet links |
| 06 | `placement_speaking.md` | Feature | Spec said "written + speaking"; we shipped written only |
| 07 | `admin_analytics.md` | Feature | Section 2 says admin needs "analytics" |
| 08 | `subscription_expiry.md` | Polish | Subscriptions never expire automatically right now |
| 09 | `placement_retake_guard.md` | Polish | Users can re-take and overwrite their level |
| 10 | `payment_reject_ui.md` | Polish | Rejected users have nowhere to see why |
| 11 | `editable_payment_accounts.md` | Polish | Hardcoded `ACCOUNT_INFO` should be a model |
| 12 | `cleanup_dead_code.md` | Polish | Remove the unused `sample_lessons.json` fixture |

### How to run one

1. Open a fresh Claude conversation
2. Upload `onlenco_django.zip` (the Django project from the previous turn)
3. Paste the entire contents of one prompt file
4. Claude will produce a patched zip with the new feature added

### How to run all of them

Same as above, but feed prompts in order. After each one, replace your
`onlenco_django.zip` with the patched version Claude returns, then run the
next prompt against the updated zip. This keeps each conversation focused
and avoids context bloat.

## What's in each prompt

Every prompt follows the same structure so they're predictable:

- **Context** — one-paragraph reminder of what Onlenco is and what already exists
- **Goal** — what this prompt accomplishes
- **Spec** — concrete deliverables: models, views/URLs, templates, admin
- **i18n strings** — English + Arabic strings to add to `core/translations.py`
- **Acceptance criteria** — testable behaviors the result must demonstrate
- **Out of scope** — what NOT to build (so the prompt stays focused)
- **Style guide** — patterns to match from the existing codebase

## Tips

- The prompts assume the project from `onlenco_django.zip`. Don't run them
  on a stale or modified version — paths and names will drift.
- If a prompt feels too large, ask the assistant to do "phase 1 only"
  (models + migrations) first, then "phase 2" (views + templates).
- Each prompt is independent — you can skip 04, 05, 07 and just do 01, 02,
  03 if those are your priorities. They don't depend on each other.
- Exception: prompt **01** (lesson detail + quizzes) extends the `Lesson`
  model. If you want quizzes, do 01 before any prompt that touches lessons.

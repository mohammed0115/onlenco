# Onlenco — Student Home Mobile Layout Redesign (Phase 20.0C)
Date: 2026-06-14 · Type: **layout / display order only** · No content · No models · No migrations · No commit

---

## Summary

Phase 20.0C reorders the **Student Home / Dashboard** (`templates/lessons/dashboard.html`) into a clear mobile-first flow that answers *"ماذا أفعل الآن؟ / what do I do now?"* — Greeting → status chips → **Continue learning** → **Daily Quiz** → **AI Tutor** → **Library** → **Progress** → Courses, with all other tools moved into a clearly-separated secondary block below.

This is a **pure reordering of existing template blocks**. Every card's markup, link, condition, translation and `data-testid` was copied **verbatim** — no content, data, logic, routes or scoring were touched. The reorder is applied to the single shared dashboard template, so it improves both mobile and desktop (the primary action sits first in DOM order on both).

---

## Files changed

| File | Change |
|---|---|
| `templates/lessons/dashboard.html` | Reordered the `<main>` cards into the mobile-first action flow; wrapped the lower tools in a `.onl-secondary-start` divider block; refreshed the page-scoped `<style>` comment + added one small `.onl-secondary-start` rule. **No card content/link/logic changed.** |
| `docs/ONLENCO_STUDENT_HOME_MOBILE_REDESIGN.md` | **NEW** — this report |

No other files were modified in this phase.

---

## What changed

- **New top-to-bottom order (mobile-first):**
  1. Greeting + status chips (level · 🔥 streak · ⭐ XP · level number) — unchanged content
  2. Banners (rejected payment / subscription status) — unchanged
  3. Onboarding hero (only if onboarding not completed) — unchanged
  4. A0 World hero (the A0 "continue" entry) — unchanged, keeps `beginner-a0-dashboard`
  5. **Continue learning** primary card — unchanged, keeps `recommended-course-hero`
  6. **Daily Quiz + Weekly Test** grid — moved up directly under Continue
  7. **AI Tutor** card (minutes remaining) — moved up
  8. **Library / Novel** card — moved up
  9. **Progress summary** ("My English level" + skills + success rate + CEFR progress) — moved above the course list
  10. **Courses** list (secondary) + empty-state — unchanged, keeps course links
  11. — divider (`.onl-secondary-start`) —
  12. Today's tasks (daily plan) + quick-practice chips — kept, moved into the secondary block (keeps `daily-plan-cta`)
  13. More tools · Club event · Achievements/challenges/messages · Recent mistakes — kept, secondary

- **One tiny CSS addition:** `.onl-secondary-start` (a top border + spacing) to visually separate the primary action flow from secondary tools. Spacing between cards still uses the existing `space-y-5 md:space-y-6`.

- **Touch/spacing/safe-area:** cards are large tap targets; buttons keep the existing `.btn`/`.btn-hero` classes (≥44px on touch via `onlenco-components.css` `@media (pointer:coarse)`); bottom clearance for the App-Shell bottom nav comes from `body.student-shell` padding added in 20.0B, so the last cards never sit under the tab bar.

## What did NOT change

- ❌ No lesson text, vocabulary, examples, quiz questions/answers, or scoring.
- ❌ No course content order, audio/image files, CEFR levels, or content DB rows.
- ❌ No models, migrations, seed data, media, routes, or payment/subscription logic.
- ❌ No view/context changes — the template uses the **same context variables** it already received.
- ❌ No links changed — every `{% url %}` and `continue_url` is the original.
- ❌ No `data-testid` removed (`recommended-course-hero`, `beginner-a0-dashboard`, `daily-plan-cta` all preserved).
- ❌ No App-Shell change from 20.0B. ❌ No daily-route unification. ❌ No PWA. ❌ No commit.

---

## Content Freeze Confirmation ✅

The dashboard was reordered only. No educational content was read-modified, no new data/queries/calculations were introduced, and no backend logic was touched. `python manage.py check` passes with 0 issues; no migrations exist or were needed.

---

## Data / context used (all pre-existing — nothing new computed)

`profile` (full_name, cefr_level, subscription_status/expires_at, placement_completed, onboarding_completed) · `motivation` (current_streak, xp_total, level_number, weekly_xp, cefr_progress, recent_achievements, badges_count, challenges, recent_messages, next_milestone) · `learning_plan` (recommended_course, recommended_lesson, continue_url, progress_percentage, current_level) · `learning_summary` (weekly_assessment_id, cefr_level, exercise_success_rate, recent_errors) · `ai_tutor_minutes_remaining` · `skills_progress` · `library_last` · `today_plan` · `a0_dashboard_world` · `student_courses` · `last_rejected` · `next_club_event` / `next_club_rsvp` / `is_subscribed`.

No value is invented; every card still renders only when its data exists (same `{% if %}` guards as before).

---

## Mobile layout order (final)

Greeting → Status chips → (banners / onboarding / A0) → **Continue learning** → **Daily Quiz + Weekly** → **AI Tutor** → **Library** → **Progress summary** → **Courses** → ─ secondary ─ → Today's tasks + chips → More tools → Club → Achievements → Recent mistakes.

---

## Desktop impact

Minimal and safe. The same DOM order applies on desktop; the grids that already used `sm:`/`lg:` columns (Daily/Weekly, courses, achievements) are unchanged, so desktop keeps its multi-column layout. The only new desktop-visible element is the thin `.onl-secondary-start` divider before the secondary tools. No desktop regressions expected.

---

## QA commands

```bash
python manage.py check                                   # → 0 issues
python manage.py test lessons.tests.test_dashboard_view  # dashboard cards/testids/bottom-nav
python manage.py test courses.tests.test_beginner_student_journey_e2e  # student journey renders
python manage.py test courses.tests.test_lesson_media_rendering        # base/header render + no leaks
```
Result: `check` → 0 issues; the three suites above → **OK** (41 tests). Full suite not run here because this phase only touches one presentation template; the dashboard + student-render tests are the relevant safe set.

---

## Risks / follow-up items

- **R1 — DOM order on desktop:** Continue/Daily/Tutor/Library now precede the course grid on desktop too. This is intended (action-first) and tests pass; revert is trivial if a desktop-specific order is later wanted.
- **R2 — Two "daily" entries still exist** (Daily Quiz card → `exam_daily`, and Today's tasks → `daily_learning:daily_plan`). Left intact per scope; unification is Phase 20.0F.
- **R3 — Status chips** still rely on `motivation`; when absent, only the level chip shows (same as before). No subscription/minutes chip was added to avoid new computation — subscription shows as its existing banner, minutes in the AI Tutor card.
- **R4 — Quick-practice chips** duplicate some nav targets; kept to avoid removing content. Could be trimmed in a later polish phase.

---

## Recommended manual mobile checks

1. 360–375px: order reads Greeting → Continue → Daily Quiz → AI Tutor → Library → Progress → Courses → secondary.
2. Primary CTA (Continue learning) is the first large card and easy to tap.
3. Last cards clear the bottom nav (safe-area) — nothing hidden behind the tab bar.
4. RTL (Arabic) + LTR (English): card order and chips correct in both.
5. New student (no onboarding): onboarding hero shows; A0 student: A0 hero shows.
6. Desktop ≥768px: grids still multi-column; no bottom nav; secondary divider visible.
7. No `{# … #}` text visible anywhere on the page.

---

*End of Phase 20.0C. Next: 20.0D — Lesson UI cleanup (spacing/thumb-reach only, no content).*

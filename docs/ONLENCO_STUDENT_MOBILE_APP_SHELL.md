# Onlenco — Student Mobile App Shell (Phase 20.0B)
Date: 2026-06-14 · Type: presentation/navigation only · **No content change · No migrations · No commit**

---

## Summary

Phase 20.0B introduces a **unified Student Mobile App Shell**: a single, persistent **bottom navigation** (5 tabs) that now appears on **every** student page (not just the dashboard), proper **safe-area** handling for notch/home-indicator devices, and a **de-cluttered mobile header** (links duplicated by the bottom nav are hidden on phones). Desktop is unchanged.

This was achieved by wiring the shell into `base.html` (which every student page already extends) + a tiny context-processor addition for active-tab/“my course” resolution — **without editing per-screen content** and **without per-view changes**.

The student now gets an app-like frame (slim header on top, fixed tab bar on the bottom) around the existing, unchanged learning content.

---

## Files changed

| File | Change |
|---|---|
| `templates/base.html` | `viewport-fit=cover`; link `student_shell.css`; `body class="student-shell"` when authenticated; include `_student_bottom_nav.html` after the content block |
| `templates/_student_bottom_nav.html` | **NEW** — the 5-tab bottom nav partial (mobile only), guarded by `student_nav.show` |
| `static/css/student_shell.css` | **NEW** — bottom-nav styling, safe-area insets, mobile body padding, mobile header de-dup rule |
| `core/context_processors.py` | `site_context` now exposes `student_nav` = `{show, active, course_url}` via `_active_student_tab` (path-based, no DB) + `_student_course_url` (one light indexed query for authenticated users) |
| `templates/_app_header.html` | Added `onl-hdr-dup` class to the **Home / AI Tutor / Library** links so they hide on mobile (covered by the bottom nav); Profile/lang/logout/staff links unchanged |
| `templates/lessons/dashboard.html` | Removed the page-local bottom nav + its scoped CSS (now provided globally by the shell); dropped the now-redundant `pb-24` mobile padding |
| `templates/courses/detail.html` | Collapsed a **multi-line `{# … #}` comment** to one line (it would otherwise leak as visible text — see “Internal text” below) |
| `lessons/tests/test_dashboard_view.py` | Updated `test_mobile_bottom_nav_present` to assert the new shell class `onl-shell-nav` + the new tab set (library replaces profile) |
| `docs/ONLENCO_STUDENT_MOBILE_APP_SHELL.md` | **NEW** — this report |

---

## What changed (behavior)

- **Persistent bottom nav on all student pages.** 5 tabs: الرئيسية (Home → `dashboard`), الكورس (Course → most-recent enrolled course, else dashboard), الاختبار (Quiz → `exam_daily`), المعلّم (AI Tutor → `tutor`), المكتبة (Library → `library`). Mobile-only (`display:none` ≥768px). Touch targets 56px. Active tab highlighted via `aria-current="page"`, resolved from `request.path`.
- **Safe-area support.** `viewport-fit=cover` + `padding-bottom: env(safe-area-inset-bottom)` on the nav + `body.student-shell` mobile bottom padding so content never hides behind the bar and the bar clears the iPhone home indicator.
- **De-cluttered mobile header.** The Home / AI Tutor / Library buttons (now duplicated by the bottom nav) are hidden on phones; the logo, Profile, language toggle and logout remain. Admin/Teacher links remain role-gated as before. Desktop header is untouched.
- **Profile** moved off the bottom bar into the header (per the 5-tab spec: Home/Course/Quiz/Tutor/Library).

## What did NOT change

- ❌ No lesson text, vocabulary, examples, questions, answers, or scoring.
- ❌ No course content order, audio/image files, CEFR levels, or content DB rows.
- ❌ No models, migrations, seed data, media, or production settings.
- ❌ No page content/sections removed; `{% block body %}` of every page is rendered exactly as before — the shell only wraps it.
- ❌ No new frontend libraries (uses existing Lucide + the existing CSS pipeline).
- ❌ No PWA (manifest/service worker) — deferred to 20.0I.
- ❌ No `/daily/` vs `/exam/daily/` route unification — deferred to 20.0F (the Quiz tab points at the existing `exam_daily`).
- ❌ No git commit.

---

## Content Freeze Confirmation ✅

No educational content was read-modified. The only template edits are structural/navigation (shell, header classes, dashboard nav removal) and one dev-comment collapse. `python manage.py check` passes; no migrations were created or needed.

---

## Pages covered (get the shell automatically via `base.html`)

Every authenticated student page that extends `base.html`, including:
- Student Dashboard / Home · Course Home / Course Detail · Lesson Screen · Quiz / Challenge · Daily plan & Daily exam · Weekly Test · AI Tutor · Library / Novel Reader · Profile / Subscription · Subscribe.

## Pages NOT covered (by design)

- **Teacher Portal** and **Platform Admin** screens — they use their own base templates (`teacher_portal/base.html`, admin bases), so the student shell does not leak into staff areas. ✅ Correct.
- **Anonymous/public** visitors — the nav is guarded by `student_nav.show` (authenticated only), so the landing/pricing pages show no student tab bar to logged-out users.
- **Immersive flows** (challenge player, voice call) currently still show the bottom nav. If a fully-immersive (nav-hidden) mode is desired there, it can be added as a per-page opt-out in a later phase — noted as follow-up.

---

## Internal text / `{# #}` leak note (user-flagged)

Per the known Django behaviour (multi-line `{# … #}` comments render as **visible literal text**) and the user's explicit request:
- A project-wide sweep was run for multi-line `{# … #}` comments in student templates.
- **One** instance was found and fixed: `templates/courses/detail.html:257` (a 2-line sample-audio dev comment) — collapsed to a single line.
- All Phase 20.0B additions use single-line `{# … #}` or the safe `{% comment %}…{% endcomment %}` block, so they cannot leak.
- (A previous similar leak in the challenge feedback card was fixed earlier.) Detailed AI-Tutor template sweep remains scheduled for Phase 20.0G.

Detection command used:
```bash
grep -rn --include=*.html '{#' templates/ courses/ daily_learning/ tutor/ library/ lessons/ | grep -v '#}'
# (now returns nothing → no multi-line {# #} comments remain)
```

---

## QA commands

```bash
# System check (passed)
python manage.py check

# Safe UI / navigation / template tests (passed)
python manage.py test lessons.tests.test_dashboard_view \
                      courses.tests.test_lesson_media_rendering \
                      courses.tests.test_examples_listen_repeat
# Broader student-page render smoke (passed: 174 tests)
python manage.py test courses.tests.test_challenge_engine \
                      courses.tests.test_mistakes_review \
                      courses.tests.test_lesson_video_step \
                      daily_learning \
                      courses.tests.test_beginner_student_journey_e2e
```
Results: `python manage.py check` → **0 issues**. All listed suites → **OK** (no content assertions touched).

---

## Risks / follow-up items

- **R1 — `student_course_url` query cost:** `site_context` now runs one extra indexed `CourseEnrollment` query per request for authenticated users. Light and guarded; could be memoised on the request if profiling shows cost.
- **R2 — Bottom nav on immersive screens:** the challenge player & voice call still show the tab bar. Follow-up: add a per-page `{% block hide_student_nav %}` opt-out if a distraction-free mode is wanted (20.0D/20.0E).
- **R3 — Course tab fallback:** a brand-new student with no enrollment yet gets الكورس → dashboard (sensible default).
- **R4 — Header on small phones:** Profile + language + logout + (staff links) remain; still reasonable but a future drawer could consolidate further (20.0C).
- **R5 — Active-tab path matching** is path-prefix based; if URL prefixes change, update `_active_student_tab`.

---

## Recommended manual checks (mobile)

1. 360–375px viewport: bottom nav visible and fixed on dashboard, lesson, quiz, daily, tutor, library, profile.
2. iPhone notch device: nav clears the home indicator (safe-area); header not under the notch.
3. RTL (Arabic) + LTR (English): tab order and active highlight correct in both directions.
4. Tap each tab → lands on the correct existing page; active tab highlights.
5. Desktop ≥768px: bottom nav hidden; header shows the full link set (unchanged).
6. Logged-out landing page: no student tab bar.
7. Open a lesson and confirm **no `{# … #}` text** appears anywhere on screen.

---

*End of Phase 20.0B. Next: 20.0C — Student Home layout reorder (display order only).*

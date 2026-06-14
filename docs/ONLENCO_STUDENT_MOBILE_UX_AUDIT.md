# Onlenco — Student Mobile Architecture & UI/UX Audit
### Prompt 20.0A-R — Audit-only, Strict Content Freeze
Date: 2026-06-14 · Scope: student-facing mobile experience · Type: **report only (no code/content changes, no commit)**

---

## 1. Executive Summary

Onlenco's student experience is **functionally complete and already mostly mobile-first at the CSS level** (the design-system CSS is mobile-first, RTL-aware, and a real Duolingo-style step-by-step Quiz/Challenge engine already exists). However, it still **reads as a responsive website, not a native-feeling learning app**, for four structural reasons:

1. **No unified app shell.** The 5-item bottom navigation exists **only on the dashboard** (`templates/lessons/dashboard.html`). The moment a student opens a lesson, quiz, daily plan, AI tutor, library, or profile, the app-like bottom bar disappears and they are back to a web header. There is no persistent shell.
2. **A web-style, role-crowded top header.** `_app_header.html` renders ~9–10 inline icons including **admin/teacher/role-switch links** that should never crowd a student's phone header, with no hamburger/drawer and sub-44px tap targets.
3. **No mobile-platform polish.** No `viewport-fit=cover`, no `env(safe-area-inset-*)` (notch/home-indicator overlap on iPhone), no PWA manifest/service worker (not installable, no offline).
4. **Two parallel "daily" experiences** (`/daily/` in `daily_learning` vs `/exam/daily/` in `lessons`) plus a profile page built with non-responsive inline CSS — inconsistencies that make the product feel stitched together.

**The good news:** because the content architecture (Lesson = teach, Quiz/Challenge = Duolingo practice, AI Tutor = voice, Daily = review, Weekly = level test) is already in place and the CSS is mobile-first, the required work is **presentation/navigation only** and can be done **without touching any educational content**.

This document is the **Phase 20.0A-R audit**. No content, models, migrations, seeds, media, or settings were changed. No commit was made.

---

## 2. Content Freeze Confirmation ✅

This audit changed **none** of the following. They remain byte-for-byte as they were:

- ❌ No lesson text changed · ❌ No vocabulary changed · ❌ No examples changed
- ❌ No quiz/challenge questions changed · ❌ No quiz answers changed · ❌ No scoring logic changed
- ❌ No course content order changed · ❌ No audio/image files changed · ❌ No CEFR levels changed
- ❌ No content DB rows changed · ❌ No new educational content added · ❌ No existing content deleted
- ❌ No migrations · ❌ No model changes · ❌ No seed changes · ❌ No media changes · ❌ No production settings changes · ❌ **No git commit**

The **only** file created by this task is this report: `docs/ONLENCO_STUDENT_MOBILE_UX_AUDIT.md`.

---

## 3. Current Student Mobile UX Problems (system-wide)

| # | Problem | Evidence | Severity |
|---|---------|----------|----------|
| P1 | App-shell bottom nav exists only on the dashboard; every other screen loses it | bottom nav defined inline in `templates/lessons/dashboard.html` (≈ lines 18–20, 380–389), absent from `base.html` | **High** |
| P2 | Student header is web-style + role-crowded (~9–10 inline icons incl. admin/teacher/role-switch), no drawer | `templates/_app_header.html` lines 3–74 | **High** |
| P3 | No safe-area support → notch / home-indicator overlap fixed header & bottom nav | `base.html` line 5 (no `viewport-fit=cover`); dashboard bottom nav has no `env(safe-area-inset-bottom)` | **High (iPhone)** |
| P4 | Not PWA-ready — no manifest, no service worker, no theme-color, no offline | `static/` (no `manifest.webmanifest`/`sw.js`); `base.html` head | **Medium** |
| P5 | Two parallel "Daily" experiences confuse the model | `/daily/` (`daily_learning`) **and** `/exam/daily/` (`lessons` → `exam_play.html`) | **Medium** |
| P6 | Header tap targets below 44px (`.btn-sm` = 36px) — mitigated only by `@media (pointer:coarse)` | `static/css/onlenco-components.css` `.btn-sm` (≈ line 84) | **Medium** |
| P7 | Profile page uses non-responsive inline CSS (fixed 140px label, raw seconds, 11px pills) | `templates/accounts/profile.html` `<style>` block (≈ lines 9–47) | **Medium** |
| P8 | Gamification toast hard-coded at `top:80px` overlaps content on short phones | `templates/_gamification_toast.html` (≈ line 20) | **Low/Med** |
| P9 | Subscribe payment-method grid `sm:grid-cols-3` cramps on small phones; `<code>` blocks can overflow | `templates/payments/subscribe.html` (≈ lines 86, 108) | **Low/Med** |
| P10 | Risk of internal/technical text leaking to students (already one confirmed-and-fixed case) | multi-line `{# … #}` leak previously found in challenge feedback (now fixed) — see §13 | **Critical class** |

---

## 4. Screen-by-Screen Findings

Legend: 📱 mobile-first · 🧭 next-step clarity · 👆 tap targets · ↔️ RTL · 🧹 visual clutter · 🔒 internal-text leak.

### 4.1 Landing (`templates/core/home.html` · `core.views.home` · `/`)
- 📱 Yes (responsive `sm:/lg:` cascades; CTAs stack full-width). 🧭 Clear (Sign up / placement). ↔️ Bilingual via `t_either`. 🧹 Clean. 🔒 None.
- **Verdict:** Good. Minor: pricing-teaser "choose plan" buttons small on ≤320px.

### 4.2 Pricing / Subscribe (`templates/payments/subscribe.html` · `payments.views.subscribe` · `/subscribe/`)
- 📱 Partial: plan cards stack (`sm:grid-cols-2`) but **payment methods `sm:grid-cols-3`** cramp on small phones; bank-detail `<code>` can overflow (no `overflow-x-auto`). 🧭 After activation there's **no CTA back into learning** (success card has no button). ↔️ Uses `inset-inline-*` (good).
- **Verdict:** Needs mobile breakpoints + a "Start learning →" CTA on success.

### 4.3 Student Home / Dashboard (`templates/lessons/dashboard.html` · `lessons` dashboard view · `/dashboard/`)
- 📱 Yes — **the only screen with the app bottom nav** (home/course/quiz/tutor/profile, 56px, `pb-24 md:pb-10`). Has Continue-Learning hero, daily, AI tutor, daily/weekly cards, skills, library.
- 🧹 Dense: many cards competing; greeting/level/streak/XP not consolidated into a compact strip. 🧭 Good but the primary "continue" action competes with several CTAs.
- **Verdict:** Strong base; needs reorder + the bottom nav promoted into the shell so it persists everywhere.

### 4.4 Course Home (`templates/courses/lesson_detail.html` + `templates/courses/detail.html` · `courses.views.course_lesson_detail` / course detail)
- 📱 Yes (step cards loop, `aspect`/grid). 🧭 Good — "ابدأ الدرس" + step cards + unlock badge ("أكمل الدرس ليُفتح التالي"). Video step card appears before finish only when a video exists. ↔️ OK.
- 🧹 Step cards are clear; no bottom nav (loses shell).
- **Verdict:** Good content launcher; just inherits the shell gap.

### 4.5 Lesson Screen (`templates/courses/lesson_step.html` · `courses.views.lesson_step`)
- 📱 Yes — per-step immersive stage, progress dots, prev/next, natural listen-and-repeat audio (with autoplay attempt), dialogue bubbles, optional video step, image placeholder fallback.
- 🧭 Each step has prev/next; the **finish step launches the Quiz/Challenge** (correct Lesson↔Quiz separation). 🧹 Generally clean; the dot bar + per-step accents are app-like. 🔒 No leaks after the earlier fix.
- **Verdict:** Already teaching-only and close to app-grade. Keep as-is content-wise; only shell + spacing polish (see §9). **Do NOT turn the lesson into a quiz flow.**

### 4.6 Quiz / Practice — Challenge engine (`templates/courses/challenge_session.html`, `templates/courses/question_renderers/*`, `challenge_summary.html` · `courses.views.challenge_*`)
- 📱 **Already Duolingo step-by-step**: one card per screen, hearts, XP, per-answer feedback, 20+ question renderers (tap_choice, word_bank_sentence, listen_and_choose, …), results summary, 70% pass gate, mistake review. 🧭 Excellent. ↔️ OK.
- **Verdict:** This is the model the rest of the app should aspire to. **No content change needed** — it already uses the existing question bank. Only minor mobile polish (see §10).

### 4.7 Daily Quiz — **two implementations** ⚠️
- (a) `/daily/` — `daily_learning/templates/daily_learning/daily_plan.html` (`daily_learning.views.daily_plan_view`): plan + "today's lesson" two buttons (Vocabulary / Lesson test) + a stepper of mixed items. 📱 Yes. 🧹 Mixes review items with a "today's challenge" banner.
- (b) `/exam/daily/` — `templates/lessons/exam_play.html` (`lessons.views`): a clean single-question player (hearts, `.opt` cards, 17px inputs to avoid iOS zoom). 📱 Yes.
- **Problem:** two daily surfaces = unclear mental model (Daily Quiz should be ONE thing = weakness review). 🧹 Picture-emoji `style="font-size:120px"` can overflow on ≤375px.
- **Verdict:** Pick ONE daily surface (recommend the `exam_play` step-by-step player driven by weakness selection) and make the other link into it. Presentation/routing only.

### 4.8 Weekly Test (`templates/lessons/weekly_assessment.html`, `weekly_assessment_result.html`, shared `exam_play.html` · `lessons.views.weekly_assessment` / `exam_play` / result)
- 📱 Player is mobile-first; **start screen uses bare radio inputs** (no `.opt` card styling like `exam_play`); start screen lacks "what/why/how many questions". Result screen shows score + a recommendation/CTA.
- 🧭 Partial at the start (no framing). 🧹 Inconsistent with the polished player.
- **Verdict:** Reuse the `.opt` card pattern + add a clear start card (count, purpose, "Begin"). No question/scoring change.

### 4.9 AI Tutor (`templates/tutor/voice_call.html`, `templates/tutor/detail.html` · `tutor.views`)
- 📱 Voice-call screen is app-like (avatar orb, mic, minutes pill, end-call). 🧭 Clear. ↔️ OK.
- 🔒 **Must verify no internal text reaches students** — system prompts, tutor instructions, expected keywords, raw model instructions, debug/developer notes. A confirmed instance of this class (a multi-line `{# … #}` leaking as visible text) was found in the **challenge feedback** card and already fixed; treat any similar occurrence as **Critical**.
- **Verdict:** Audit the tutor templates + any server-rendered tutor strings for leaks; ensure only user-facing copy shows. Do not author new teaching text — hide/replace with existing user-facing strings.

### 4.10 Library / Novel Reader (`templates/library/list.html`, `templates/library/chapter_reader.html` · `library.views`)
- 📱 Yes — list is `grid-cols-2 md:3 xl:4` with `aspect-[3/4]`; reader is `max-w-3xl`, `.prose leading-relaxed`, RTL-tagged Arabic notes, vocab `details/summary`, listen button. 🧭 Good. ↔️ Good.
- **Verdict:** Solid; only shell + reader controls (font-size toggle, sticky progress) as enhancements.

### 4.11 Profile / Subscription (`templates/accounts/profile.html` · `accounts.views.profile_view` · `/auth/profile/`)
- 📱 **No** — inline `<style>` with **fixed 140px label width** (cramps values on ≤375px), language buttons don't stack, 11px pills, **AI-tutor quota shown as raw seconds** (e.g., 3600 instead of "60 min"). 🧭 Subscription status de-emphasized (text links, no prominent "Renew"). ↔️ Rows don't explicitly mirror in RTL.
- **Verdict:** Highest-need responsive refactor; presentation only (no data/quota logic change — only format seconds→minutes for display).

---

## 5. Architecture Recommendation (presentation layer)

Keep the **adopted content architecture** exactly:

| Surface | Role | Implementation today | Keep / change |
|---|---|---|---|
| **Lesson** | Teach & explain only | `lesson_step.html` (intro/vocab/examples/dialogue/listening/speaking/[video]/finish) | **Keep** — teaching only |
| **Quiz / Practice** | Duolingo step-by-step practice | `challenge_*` engine | **Keep** — already correct |
| **AI Tutor** | Voice conversation + correction | `tutor/voice_call.html` | **Keep** — clean internal text |
| **Daily Quiz** | Daily weakness review | split across `/daily/` + `/exam/daily/` | **Unify** into one surface |
| **Weekly Test** | Level transition / week consolidation | `weekly_assessment` + `exam_play` | **Keep** — polish start/result |

The **only architectural change** is introducing a **persistent Student Mobile App Shell** (§7) that wraps every student screen and hosts navigation, so the product stops feeling like separate web pages.

---

## 6. Lesson vs Quiz Separation (must stay strict)

- **Lesson = input/teaching.** `lesson_step.html` shows intro, explanation, audio (listen-and-repeat), vocabulary, examples, dialogue, optional video, then a single clear CTA: **"ابدأ التحدّي / Start the challenge"** at the finish step. ✅ Already implemented.
- **Quiz = output/practice (Duolingo).** Step-by-step cards, hearts, XP, feedback, summary, pass gate. ✅ Already implemented in the challenge engine.
- **Rule for all future phases:** never embed questions inside the lesson; never reword teaching text; never reorder lesson content. The lesson's only job at the end is to hand off to the Quiz.

---

## 7. Student Mobile App Shell Recommendation (Phase 20.0B)

Create a single shell partial (e.g. `templates/_student_shell.html`) that **all student pages extend**, providing:

- **Slim top header** (logo + page title + ONE overflow/profile affordance). Move admin/teacher/role-switch links OUT of the student header (show only for staff, ideally in a separate area).
- **Persistent bottom navigation** (promote the dashboard's `.onl-bottomnav` into the shell so it appears on lesson/quiz/daily/tutor/library/profile too):
  - الرئيسية (Home → `dashboard`)
  - الكورس (Course → current/last course)
  - الاختبار (Quiz/Practice → challenge or daily)
  - المعلّم الذكي (AI Tutor → `tutor`)
  - المكتبة (Library → `library`)
- **Safe areas:** add `viewport-fit=cover` to the viewport meta and `padding-bottom: env(safe-area-inset-bottom)` to the bottom nav, `padding-top: env(safe-area-inset-top)` to the header.
- **Touch targets:** ensure all shell controls ≥ 44×44px (raise `.btn-sm` in shell context).
- **De-clutter:** collapse rarely-used header icons into the profile/menu; keep all existing links/functions reachable (no functionality removed).
- Immersive flows (the challenge player, voice call) may **hide** the bottom nav intentionally — make that a shell option, not the default.

All links/URLs stay the same; this is a wrapper, not a rewrite.

---

## 8. Student Home Recommendation (Phase 20.0C — display order only)

Re-order the existing dashboard cards (no data/calculation change):

1. **Greeting** (short) + compact **level · streak · XP** strip (one row, small).
2. **Continue today's lesson** — the single hero CTA.
3. **Daily Quiz** (one entry, the unified one).
4. **AI Tutor minutes** (remaining today).
5. **Library / Novel**.
6. **Progress summary** (skills/level).
7. **Subscription status** (with a clear renew CTA when expiring).

Keep all existing `data-testid`s (`recommended-course-hero`, `beginner-a0-dashboard`, `daily-plan-cta`, etc.) so tests keep passing.

---

## 9. Lesson UI Cleanup Recommendation (Phase 20.0D — no content change)

- Keep the per-step stage; tighten mobile vertical spacing and ensure the stage fits one screen with the audio control + content below.
- Ensure prev/next + the finish "Start challenge" CTA are thumb-reachable (bottom of viewport).
- Verify the progress dots fit on a 360px width (scroll/condense if > 7–8 steps).
- Keep listen-and-repeat, dialogue bubbles, video step, image placeholder exactly as they are. **No question insertion, no reorder, no reword.**

---

## 10. Quiz Step-by-Step UI Recommendation (Phase 20.0E — existing content only)

The challenge engine already does this. Mobile polish only:
- One question per screen ✅ (keep). Hearts/XP/progress ✅.
- Make the primary action button (Check / Continue) a fixed bottom bar with safe-area padding.
- Constrain picture/emoji hero to `min(80vw, 120px)` so it never overflows (`exam_play.html` line ~75).
- Ensure option `.opt` cards are ≥44px and full-width on mobile (already close).
- **No new questions, no answer edits, no scoring change** (flag scoring bugs in a report only).

---

## 11. Daily Quiz Recommendation (Phase 20.0F — existing questions only)

- **Unify** to ONE daily surface. Recommended: keep the clean `exam_play.html` single-question player as the Daily Quiz UI, and have `/daily/` route/link into it (or render the weakness-selected items through it). Presentation/routing change only.
- One question at a time ✅, clear feedback ✅, progress ✅, XP/streak ✅ (already present in the player).
- Fix the 120px picture overflow; ensure the answer input uses ≥16px font (it uses 17px ✅ — keep).
- **No change to which questions are selected or their content.**

---

## 12. Weekly Test Recommendation (Phase 20.0G-adjacent — UI only)

- Add a clear **start card**: title, "Weekly level test", number of questions, purpose ("measure if you move up / consolidate the week"), and a big **Begin** button.
- Use the same `.opt` card pattern as `exam_play.html` on the weekly start (replace the bare radios).
- Result screen: keep score; make the **recommendation + next CTA** prominent (e.g., "You're ready for B2 →" or "Review these skills →").
- **No question or scoring change** (report bugs separately).

---

## 13. AI Tutor Cleanup Recommendation (Phase 20.0G — Critical: no internal text)

- Audit `tutor/voice_call.html`, `tutor/detail.html`, and any server-built tutor strings for leaks of: system/AI prompts, tutor instructions, expected keywords, raw model instructions, debug text, developer notes.
- **Known pattern (Critical):** multi-line Django `{# … #}` comments render as visible literal text. One such leak ("Phase 7: optional AI Tutor explanation …") was found in the **challenge feedback card** and already collapsed to a single line. Sweep all tutor/quiz templates for multi-line `{# #}` and any `expected_*`/`instruction`/`system_prompt` variables printed to the page.
- If a leak is found: classify **Critical**, hide it or swap in an existing user-facing string. **Do not author new teaching text.**
- Keep: conversation, voice correction, gentle practice, minutes binding to the plan.

---

## 14. Library Mobile Recommendation (Phase 20.0H)

- Reader is already good; add (presentation only): a **font-size toggle**, a **sticky reading-progress bar**, larger listen/controls as a bottom bar, and verify mixed RTL/LTR vocab boxes on 320px.
- Keep book grid `grid-cols-2` on mobile.

---

## 15. Implementation Phases (safe, incremental)

| Phase | Title | Content-safe? | Notes |
|---|---|---|---|
| 20.0A-R | Audit + Content Freeze | ✅ (this doc) | no code change |
| 20.0B | Student Mobile App Shell | ✅ | shell partial + persistent bottom nav + safe-area + viewport-fit |
| 20.0C | Student Home layout reorder | ✅ | display order only; keep testids |
| 20.0D | Lesson UI cleanup | ✅ | spacing/thumb-reach only; no content |
| 20.0E | Quiz step-by-step mobile polish | ✅ | fixed action bar, emoji clamp; existing questions |
| 20.0F | Daily Quiz unify + mobile UX | ✅ | route to one player; existing questions |
| 20.0G | AI Tutor cleanup + leak sweep | ✅ | hide internal text only |
| 20.0H | Library reader mobile UX | ✅ | controls/typography only |
| 20.0I | PWA readiness | ✅ | manifest + service worker + theme-color + apple meta |

Each phase: small PR, run the test suite, no content/model/migration/media/settings changes.

---

## 16. Risks

- **R1 — Shell regression:** wrapping all pages in a new shell could break existing per-page headers/blocks. Mitigation: introduce the shell as an opt-in base that re-includes `_app_header.html` initially; migrate page-by-page.
- **R2 — Test breakage:** templates assert specific markers/testids (`data-testid`, `onlenco-mega-player`, `data-lr-start`, `recommended-course-hero`). Mitigation: preserve all testids and class hooks; run the suite after each phase.
- **R3 — Daily unification:** merging two daily surfaces could change a URL a student/bookmark uses. Mitigation: keep both URLs, redirect one to the other.
- **R4 — RTL breakage:** new shell CSS must use logical properties (`inset-inline-*`, `padding-inline`) to keep Arabic correct.
- **R5 — iOS safe-area:** `viewport-fit=cover` changes layout insets; test on a notch device.
- **R6 — Content-freeze violation (must avoid):** any phase that edits lesson/quiz/daily/weekly **content** is out of scope. Only templates/CSS/JS/presentation views.

---

## 17. Test Plan

**Static check (run now):**
- `python manage.py check` — Django system check (templates/URLs/apps load).

**Per-phase safe template/UI tests (already in the suite, no content touched):**
- `python manage.py test courses.tests.test_lesson_media_rendering` — student lesson step rendering + no internal-text leaks.
- `python manage.py test courses.tests.test_examples_listen_repeat` — listen-and-repeat + dialogue/listening/speaking audio + template hooks.
- `python manage.py test courses.tests.test_lesson_video_step` — optional video step card/render.
- `python manage.py test courses.tests.test_lesson_gate` — sequential unlock states.
- `python manage.py test courses.tests.test_dashboard_view` (under `lessons.tests.test_dashboard_view`) — dashboard cards/testids.
- `python manage.py test courses.tests.test_placement_level_access courses.tests.test_lesson_access_override` — access gating (visibility, not content).
- `python manage.py test daily_learning` — daily plan rendering.
- `python manage.py test courses.tests.test_challenge_engine courses.tests.test_mistakes_review` — quiz/challenge flow + review.

**Manual mobile QA (per phase):** 360–375px viewport, iPhone notch device, RTL (Arabic) + LTR (English), bottom-nav persistence across lesson→quiz→daily→tutor→library→profile, safe-area on a notch phone, tap targets ≥44px.

> Note: the UI tests above assert markup/testids only; none assert or modify educational content, so they are safe to run repeatedly during the redesign.

---

## 18. Files Reviewed

**Shell / base:**
- `templates/base.html` · `templates/_app_header.html` · `templates/_gamification_toast.html`
- `static/css/onlenco-tokens.css` · `onlenco-components.css` · `onlenco.css` · `daily_journey.css` · `ai_tutor_voice.css` · `ai_tutor_realtime.css`
- `static/js/dashboard-shell.js` · `speech_clean.js` · `ai_tutor_voice.js` · `ai_tutor_realtime.js`

**Screens:**
- Landing: `templates/core/home.html`
- Pricing/Subscribe: `templates/payments/subscribe.html`
- Student Home: `templates/lessons/dashboard.html`
- Course Home: `templates/courses/lesson_detail.html` · `templates/courses/detail.html`
- Lesson: `templates/courses/lesson_step.html`
- Quiz/Challenge: `templates/courses/challenge_session.html` · `templates/courses/challenge_summary.html` · `templates/courses/question_renderers/*` · `templates/courses/challenge/components/feedback_card.html`
- Daily: `daily_learning/templates/daily_learning/daily_plan.html` · `templates/lessons/exam_play.html`
- Weekly: `templates/lessons/weekly_assessment.html` · `templates/lessons/weekly_assessment_result.html`
- AI Tutor: `templates/tutor/voice_call.html` · `templates/tutor/detail.html`
- Library: `templates/library/list.html` · `templates/library/chapter_reader.html`
- Profile: `templates/accounts/profile.html`
- Mistake review: `templates/courses/mistakes_review.html`

**Views (display only, read for routing/context — not modified):**
- `courses/views.py` (`course_lesson_detail`, `lesson_step`, `challenge_*`, `mistakes_review`)
- `daily_learning/views.py` (`daily_plan_view`) · `lessons/views.py` (`exam_play`, `weekly_assessment`, dashboard)
- `tutor/views.py` · `library/views.py` · `payments/views.py` · `accounts/views.py` · `core/views.py`

---

*End of Phase 20.0A-R audit. No content changed. No commit made. Next actionable phase: 20.0B — Student Mobile App Shell.*

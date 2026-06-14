# Onlenco — Lesson Mobile UI Cleanup (Phase 20.0D)
Date: 2026-06-14 · Type: **lesson UI / CSS only** · No content · No models · No migrations · No routes · No commit

---

## Summary

Phase 20.0D polishes the **lesson screen** (`templates/courses/lesson_step.html`) for mobile: bigger touch targets on the step tabs/buttons/tappable words, a clearer bottom step-navigation, safe-area-aware bottom spacing so nothing hides behind the App-Shell bottom nav, and a small label fix for the optional Video step. The lesson stays **teaching-only** (intro · vocabulary · examples · dialogue · listening · speaking · [video] · finish) — no quiz/game mechanics were added.

All changes are CSS + one template label; **no educational content, links, routes, scoring, or step order changed.**

---

## Files changed

| File | Change |
|---|---|
| `templates/courses/lesson_step.html` | (1) Step-dot label now shows **“Video / فيديو”** for the optional video step (was wrongly falling into “Done/إنهاء”). (2) Extended the existing `@media (max-width:640px)` block with touch-target + bottom-nav + safe-area rules. **No content/link/logic touched.** |
| `docs/ONLENCO_LESSON_MOBILE_UI_CLEANUP.md` | **NEW** — this report |

No other files were modified.

---

## What changed (mobile UI only)

- **Touch targets ≥44px on phones:**
  - `.onlenco-step-dot` → `min-height:44px` (the step tabs are now easy to tap)
  - `.onlenco-step-dots__home` → `44×44px`
  - `.onlenco-btn` (prev/next) → `min-height:48px`; `.onlenco-lr-start` (Listen) → `min-height:48px`
  - `.onlenco-vocab__word` (tappable words) → larger padding (`11px 18px`)
- **Clearer bottom step navigation:** on mobile the primary **Next** button grows (`flex:1`, centered) so the main forward action is the obvious, comfortable target; the prev/overview stays a ghost button.
- **Safe-area / no overlap:** `.onlenco-step-main` gets `padding-bottom: calc(88px + env(safe-area-inset-bottom))` on mobile so the last controls clear the App-Shell bottom nav and the iPhone home indicator.
- **Video step label fix:** the deep-link step-tabs now label the optional video step correctly.

## What did NOT change

- ❌ No lesson text, vocabulary, examples, dialogue, audio, or images.
- ❌ No quiz questions/answers, no scoring, no step order (DB-driven order untouched).
- ❌ No models, migrations, seed data, media, CEFR levels.
- ❌ No routes / no `{% url %}` changed. ❌ No views changed.
- ❌ No Quiz / Daily / Weekly / AI Tutor / Library / Home / App-Shell logic changed.
- ❌ No hearts, scoring, new questions, sentence-ordering, or speaking-validation added to the lesson.
- ❌ No commit.

---

## Content Freeze Confirmation ✅

The lesson screen was styled only (CSS) plus one navigation **label** correction. No teaching content was read-modified, no data/queries added, no backend logic touched. `python manage.py check` → 0 issues; no migrations exist or were needed.

---

## Lesson / Quiz separation confirmation ✅

The lesson remains **input/teaching only**: intro, explanation, audio (listen-and-repeat), vocabulary, examples, dialogue, optional video, and a finish step whose single CTA — **“Start the challenge / ابدأ التحدّي”** (`courses:challenge_start`, link unchanged) — hands off to the Quiz. No Duolingo step-by-step, hearts, or scoring were introduced into the lesson. The step-by-step game experience stays in the Quiz/Challenge engine only.

---

## Mobile UI improvements (checklist from the prompt)

| Item | Result |
|---|---|
| Text clarity | Stage title `clamp()` + LTR transcript panel (unchanged) — readable |
| Lesson card fits screen | Stage padding reduced on ≤640px (existing) |
| Audio buttons large/comfortable | Listen button ≥48px; mega-player play 76px on mobile |
| Step tabs easy to tap | step-dots now ≥44px tap height |
| Step number clear | step badge “Step X / N” + numbered dots (unchanged) |
| Prev/Next clear | Next is the wide primary target on mobile |
| Content not stuck to bottom nav | `padding-bottom: 88px + safe-area` on the lesson main |
| Safe-area | honored via `env(safe-area-inset-bottom)` |
| RTL/LTR correct | see notes below |

---

## RTL / LTR notes

- The lesson **transcript panel** (vocabulary, examples, dialogue lines) renders inside `dir="ltr"`, so English content displays left-to-right and never breaks inside the Arabic (RTL) UI — this was already correct and is preserved.
- RTL-specific rules (e.g. `[dir="rtl"] .onlenco-example-list li` number placement, `rtl-flip` on arrows) are untouched.
- No English text was edited; only container/touch styling changed.

---

## QA commands

```bash
python manage.py check
python manage.py test courses.tests.test_lesson_media_rendering   # lesson step render + no internal-text leaks
python manage.py test courses.tests.test_examples_listen_repeat   # listen-and-repeat / dialogue audio + hooks
python manage.py test courses.tests.test_lesson_video_step        # optional video step + label
python manage.py test courses.tests.test_lesson_gate              # step unlock states
python manage.py test lessons.tests.test_dashboard_view           # 20.0B/C shell + dashboard not broken
```
Result: `check` → **0 issues**; all suites above → **OK** (61 tests). Full suite not run because this phase touches only one lesson template's CSS/label; the lesson + shell + dashboard suites are the relevant safe set.

---

## Risks / follow-up items

- **R1 — Step-dots horizontal scroll:** with 8 steps (when a video exists) the labelled tabs scroll horizontally on narrow phones; acceptable and now tappable. A future option: show numbers-only under ~360px.
- **R2 — `min-height` on inline-flex buttons** relies on `align-items:center` (already set) — verified visually via tests; confirm on a real device.
- **R3 — Stage title in RTL:** an English lesson title in the hero is right-aligned in Arabic mode (readable, not broken). Could wrap in `dir="ltr"` later if desired; left untouched to avoid affecting Arabic titles.

---

## Recommended manual mobile checks

1. 360–375px: open a lesson step — tabs, Listen button, prev/next all easy to tap (≥44px).
2. Scroll to the bottom: prev/next not hidden behind the App-Shell bottom nav (safe-area clearance).
3. A lesson **with a video**: the step tab reads “Video/فيديو” (not “Done”), and the video step plays.
4. Vocabulary/examples/dialogue: English content reads LTR and wraps cleanly inside the Arabic UI.
5. Finish step: the “Start the challenge / ابدأ التحدّي” CTA is prominent and links to the quiz (unchanged).
6. RTL (Arabic) + LTR (English): arrows mirror correctly; layout intact.
7. No `{# … #}` text visible anywhere on the lesson screen.

---

*End of Phase 20.0D. Next: 20.0E — Quiz Mobile Step-by-Step UI polish (existing questions only).*

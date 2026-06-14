# Onlenco — Quiz Mobile Step-by-Step UI Polish (Phase 20.0E)
Date: 2026-06-14 · Type: **Quiz/Challenge UI (CSS) only** · No content · No scoring · No routes · No models · No migrations · No commit

---

## Summary

The Quiz/Practice surface (the **Challenge engine**: `challenge_session.html` + `question_renderers/*` + feedback/summary components) is **already a polished, mobile-first, Duolingo-style step-by-step experience** — one question per screen, progress bar, hearts, XP, per-answer feedback, a sticky Check button, 25 question renderers, reduced-motion + focus-ring support, and a mobile media query.

The one real mobile problem introduced earlier: the **App-Shell bottom nav (Phase 20.0B, `z-index:50`) was covering the quiz's sticky “Check” button (`z-index:5`)** on the immersive player. Phase 20.0E fixes this by **hiding the global bottom nav on the immersive quiz screen** (the exit “X” already handles leaving), making the Check button safe-area-aware, and bumping a couple of small tap targets. **CSS-only, page-scoped; no question/answer/scoring/route/logic touched.**

---

## Files changed

| File | Change |
|---|---|
| `templates/courses/challenge_session.html` | Appended a small CSS block to the page's existing `<style>`: hide `.onl-shell-nav` on the quiz player + zero the shell body padding there; make the sticky `.onlenco-ch-footer` Check button clear the home indicator (`env(safe-area-inset-bottom)`); bump `.onlenco-qr__word` / `.onlenco-qr__pill` tap padding on ≤480px. **No markup/logic/testids changed.** |
| `docs/ONLENCO_QUIZ_MOBILE_STEP_UI.md` | **NEW** — this report |

No other files were modified. The challenge renderers, feedback card, summary, check button, and all JS were left exactly as-is.

---

## What changed (UI only)

- **No bottom-nav overlap:** on the immersive quiz player, the App-Shell bottom nav is hidden so the sticky Check button is fully visible and tappable (it was being covered by the fixed nav). The page `<style>` is only loaded on the quiz page, so this is page-scoped and does not affect other student screens.
- **Safe-area:** the sticky Check footer now uses `bottom: calc(12px + env(safe-area-inset-bottom))` so it clears the iPhone home indicator.
- **Touch targets:** word-bank words and audio pills get ≥44px-friendly padding on small phones (other choices were already 44–48px).

## What did NOT change

- ❌ No quiz questions, answers, correct answers, question ordering.
- ❌ No scoring / grading / attempt / progress / XP / streak / weak-point logic.
- ❌ No backend, no views, no routes, no context.
- ❌ No new question type, no generated questions, no edited answers.
- ❌ No audio/media/files, no models, migrations, seed data.
- ❌ No Lesson / Daily route unification / Weekly logic / AI Tutor / Library / Home changes.
- ❌ No new frontend libraries. ❌ No PWA. ❌ No commit.

---

## Content Freeze Confirmation ✅

Only CSS was added (page-scoped) to one quiz template. No educational content was read-modified; the question text, options, correct-answer reveal, and feedback all render exactly as before.

## Scoring Freeze Confirmation ✅

No grading/scoring/attempt code was touched. The challenge engine's `challenge_runner` / `challenge_grading` / question graders are untouched; this phase changed presentation only. The `test_challenge_engine` suite passes unchanged.

---

## Question types covered (existing renderers — display verified, none added)

`tap_choice`, `image_choice`, `listen_and_choose`, `listen_and_type`, `sound_to_word`, `picture_labeling`, `mini_story_choice`, `word_bank_sentence` (arrange words), `match_pairs`, `fill_blank_card`, `conversation_reply`, `frequency_scale`, `table_sentence_builder`, `question_transform`, `mistake_correction`, `translate_to_arabic`, `translate_to_english`, `speaking_placeholder` (speak), plus legacy MCQ/fill/text and the finish/summary screen. All already render one-per-screen with ≥44px controls; the **Listen** (`<audio controls>` / pills), **Arrange words** (word-bank tray + reset), **Speak** (mic card + self-check), **Choose**, **Feedback**, and **Finish/Result** flows are intact.

---

## Mobile UI improvements (checklist)

| Item | Result |
|---|---|
| One clear question per screen | Already ✅ (kept) |
| Progress clear | Progress bar + “n/total” label ✅ |
| Question type clear | Kicker label per question ✅ |
| Clear CTA | Sticky **Check** button, now uncovered + safe-area ✅ |
| Feedback after answering | Correct/wrong card with badge + icon (not colour-only) ✅ |
| No visual clutter | Single card layout ✅ |
| No overlap with bottom nav | **Fixed** — nav hidden on the player ✅ |
| Not stuck to screen edge / safe-area | `main` padding 120px + footer safe-area ✅ |
| Touch targets ≥44px | choices 44–48px; words/pills bumped on mobile ✅ |

---

## RTL / LTR notes

- The question text and English source/sentence content render inside `dir="ltr"` (`question__text`, `question_transform.statement`, `fill_blank.sentence_with_blank`, `translate_*` sources, `mistake_correction.wrong_sentence`), so English never breaks inside the Arabic (RTL) UI; the optional Arabic translation line uses `dir="rtl"`. Unchanged and correct.
- No text was edited; only container padding/visibility CSS changed.

---

## Internal / debug text sweep result ✅

Swept `challenge_session.html`, `challenge_summary.html`, all `challenge/components/*`, and all `question_renderers/*` for: multi-line `{# … #}` comments, AI prompts/instructions, expected keywords, raw JSON, debug/developer notes.
- **No multi-line `{# #}` comments** (the `sfx_hooks` TODO is inside a safe `{% comment %}` block; not rendered).
- The `{{ question_metadata.* }}` / `{{ question.correct_answer }}` values found are **intended student-facing content** (the sentence to transform, the blank, the mistake to fix, the translation source, the revealed correct answer in feedback) — **not** internal/debug leaks.
- **No fix needed** in this phase. (The earlier challenge-feedback multi-line comment leak was already fixed in a prior phase.)

---

## QA commands

```bash
python manage.py check
python manage.py test courses.tests.test_challenge_engine      # quiz engine flow + grading unchanged
python manage.py test courses.tests.test_mistakes_review        # post-quiz review
python manage.py test courses.tests.test_lesson_media_rendering # lesson/base render not broken
python manage.py test courses.tests.test_examples_listen_repeat # listen-and-repeat hooks
python manage.py test lessons.tests.test_dashboard_view         # 20.0B/C/D shell+home not broken
```
Result: `check` → **0 issues**; all suites above → **OK** (70 tests). Full suite not run — this phase only adds page-scoped CSS to one quiz template; the quiz + lesson + shell + dashboard suites are the relevant safe set.

---

## Risks / follow-up items

- **R1 — Daily/Weekly player (`templates/lessons/exam_play.html`)** is a *separate* quiz surface (daily/weekly) and is intentionally **out of scope** here. Its audit-flagged 120px picture emoji + bottom-nav overlap should be polished in a later phase (alongside 20.0F daily / weekly UI), not now.
- **R2 — Hiding the bottom nav on the player** relies on the page `<style>` loading; verified via tests + the element is simply `display:none`. If the quiz is ever embedded elsewhere, re-confirm.
- **R3 — `challenge_summary.html`** keeps the bottom nav (it's a results screen, not immersive); its action buttons clear the nav via the shell body padding. Acceptable.

---

## Recommended manual mobile checks

1. Start a lesson challenge on a 360–375px phone: one question per screen; the **Check** button is fully visible (not under any bar) and easy to tap.
2. iPhone notch device: Check button clears the home indicator; nothing hidden.
3. Arrange-words question: words and the answer tray are easy to tap; reset works.
4. Listen question: the audio control / pills are comfortably tappable.
5. Wrong answer: feedback shows a red badge + icon + the correct answer (not colour-only); “Review mistakes”/continue visible.
6. Finish: the summary shows score + “Next lesson”/“Review mistakes”; bottom nav present there for navigation.
7. RTL (Arabic) + LTR (English): question English text reads LTR; layout intact.
8. No `{# … #}` text or internal/debug text visible anywhere in the quiz.

---

*End of Phase 20.0E. Next (later): 20.0F — Daily Quiz mobile UX (existing questions) / weekly UI polish.*

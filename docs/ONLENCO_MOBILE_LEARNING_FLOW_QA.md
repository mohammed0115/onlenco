# Onlenco — Mobile Learning Flow QA + Navigation Consistency (Phase 20.0F)
Date: 2026-06-14 · Type: **QA + tiny UI tweak (CSS only)** · No content · No scoring · No routes · No views · No migrations · No commit (yet)

---

## 1. Summary

Phase 20.0F is a **QA pass over the mobile learning journey** — Course Detail → Lesson launcher → Lesson Step → Start Challenge → Challenge Session → Result → back — verifying navigation consistency, touch targets, safe-area, RTL/LTR, and template-comment leaks. The flow is **already consistent and mobile-friendly** after phases 20.0B–E. The audit surfaced **one** genuine sub-44px touch target (a custom breadcrumb "back" link on the lesson launcher), which was fixed with a **CSS-only, touch-scoped** rule. No behaviour, content, scoring, routes, or views changed.

---

## 2. Files changed

| File | Change |
|---|---|
| `templates/courses/lesson_detail.html` | Added one `@media (pointer:coarse)` rule giving the custom `.onlenco-back` breadcrumb a 44px tap height on touch devices. **CSS only — no markup/link/logic.** |
| `docs/ONLENCO_MOBILE_LEARNING_FLOW_QA.md` | **NEW** — this report |

---

## 3. UI inconsistencies found (audit)

Screens checked: `detail.html` (Course), `lesson_detail.html` (lesson launcher), `lesson_step.html` (step), `challenge_session.html` (quiz), `challenge_summary.html` (result), `challenge/components/*`.

1. **Lesson vs Quiz button styles** — each screen uses its own page-scoped button class (`.onlenco-cta-start`, `.onlenco-btn`, `.onlenco-ch-btn`, global `.btn`). They are **visually consistent** (wide accent pills, clear primary) but not a single shared class. Unifying would be a large cross-page refactor → **left as-is** (out of scope for a safe QA tweak; noted as a follow-up).
2. **Sub-44px tap target** — `.onlenco-back` on the lesson launcher is a custom class (~32px), not covered by the global `.btn` `@media (pointer:coarse)` min-height rule. → **fixed** (this phase).
3. **Bottom nav / safe-area** — already handled: lesson step has safe-area bottom padding (20.0D); the quiz player hides the bottom nav so the sticky Check button is clear (20.0E); `detail`/`lesson_detail`/`summary` clear the nav via the App-Shell `body.student-shell` padding. **No issue.**
4. **RTL/LTR** — consistent: English instructional text sits in `dir="ltr"` (question text, examples, dialogue, translation sources), arrows use `rtl-flip`, lesson cards mirror via `[dir="rtl"]` rules. **No issue.**
5. **Unclear labels** — none found; steps, "Start the lesson", "Start the challenge", "Next unit", "Back" are clear and bilingual.
6. **Back path from quiz** — present everywhere: quiz has the exit "X"; result has "Back to lesson" + "Next lesson"; step has "Overview/Previous"; launcher has a breadcrumb back to the course. **No issue.**
7. **Empty/error states** — covered: missing media → clean "coming soon" placeholders; locked lessons → drip message; no-questions → handled by the challenge composer. **No bad states found.**
8. **Leaked Django comments** — swept all journey templates for multi-line `{# … #}`: **none** (the only multi-line comment is `sfx_hooks` inside a safe `{% comment %}` block).
9. **Dead template scaffolding** — `lesson_detail.html` has two no-op blocks (an unused `{% with %}`/empty-`for`, and a `{% if not step_cards %}` fallback with an empty loop). They produce **no output** (not a leak) and were **left untouched** to avoid any structural change; flagged as an optional future cleanup.

---

## 4. Changes made

- `lesson_detail.html`: `@media (pointer: coarse) { .onlenco-back { min-height: 44px; } }` — the breadcrumb "back to course" is now a comfortable tap on phones; desktop/mouse rendering is unchanged.

That is the only functional UI change. Everything else in the flow already met the bar.

---

## 5. What was NOT changed

- ❌ No view logic, urls, route names (`challenge_start`, `lesson_step`, `lesson_detail`, `lesson_tts_clip` untouched).
- ❌ No scoring / answer validation / attempt / session logic.
- ❌ No questions, answers, lesson content, vocabulary, examples, audio, media.
- ❌ No models, migrations, seed, database, CEFR/progression logic.
- ❌ No quiz-inside-lesson, no lesson-logic-inside-quiz, no gamification logic.
- ❌ No new libraries, no PWA. ❌ No commit, no push.

---

## 6. Lesson / Quiz separation

Confirmed intact: the lesson launcher and lesson step are teaching-only and hand off to the quiz via `challenge_start` (unchanged link); the Duolingo step-by-step lives solely in the challenge engine. Nothing in this phase blurred that boundary.

## Mobile navigation notes

- Persistent App-Shell bottom nav on browse/learn screens; **hidden** on the immersive quiz player (20.0E) so the sticky Check button owns the bottom.
- Primary CTAs are wide accent pills on every step of the journey; back/exit affordances exist on every screen.
- All interactive targets in the journey are now ≥44px on touch (last gap closed here).

## RTL/LTR notes

Arabic UI stays RTL; English instructional content is wrapped in `dir="ltr"` where it appears (questions, examples, dialogue lines, translation sources). No content text was edited; the back-link fix is direction-neutral (`min-height`).

---

## 7. Commands run / results

```bash
git status --short ; git log --oneline -3        # safety gate: clean ✅
python manage.py makemigrations --check --dry-run # → "No changes detected" (no migrations) ✅
python manage.py check                            # → 0 issues ✅
# leaked-comment sweep over the 5 journey templates → none
python manage.py test \
  courses.tests.test_lesson_media_rendering courses.tests.test_examples_listen_repeat \
  courses.tests.test_lesson_video_step courses.tests.test_lesson_gate \
  courses.tests.test_challenge_engine courses.tests.test_mistakes_review \
  lessons.tests.test_dashboard_view                # → Ran 86, OK ✅
```

## 8. No migrations confirmation
`makemigrations --check --dry-run` → **No changes detected**. ✅

## 9. No scoring/content/routes confirmation
Only `lesson_detail.html` CSS + a new doc changed (see git status). No views/urls/models/grading/content touched. ✅

---

## 10. Manual QA checklist

**Mobile (360–375px):**
- [ ] Open course detail → lessons list readable, lock badges clear.
- [ ] Open lesson launcher → breadcrumb "back" easy to tap (≥44px); "Start the lesson" prominent.
- [ ] Open a step → tabs/dots, Listen button, prev/next all ≥44px; nothing under the bottom nav.
- [ ] Tap "Listen and repeat" → audio plays.
- [ ] Prev/Next move between steps; finish step shows "Start the challenge".
- [ ] Start challenge → one card per screen; Check button fully visible (no nav overlap), safe-area clear.
- [ ] Complete a step → feedback (badge + icon, not colour-only) → Continue.
- [ ] Result screen → score + "Next lesson"/"Review mistakes"/"Back to lesson" all tappable.
- [ ] Back returns to lesson/course correctly.

**Desktop:** layout not degraded (bottom nav hidden ≥768px; breadcrumb unchanged for mouse).

**RTL (Arabic):** arrows mirror; cards/labels correct.

**LTR (English content):** question/example/dialogue English reads left-to-right inside the Arabic shell.

---

## 11. Risks / notes

- **R1 — Button-class unification** across the journey is deferred (visually consistent today; a shared class would be a larger, riskier refactor).
- **R2 — Dead template scaffolding** in `lesson_detail.html` (no-op blocks) left in place; safe to remove in a future cleanup.
- **R3 — `@media (pointer: coarse)`** matches the project's existing touch-target pattern (`onlenco-components.css`); verify on a real device.

---

## 12. Does it need a commit?

**Yes** — two files (`templates/courses/lesson_detail.html` + this doc) are uncommitted. Per instructions, **no commit was made**; awaiting an explicit request. Suggested message when approved:
`fix: 44px touch target for lesson back link + mobile flow QA (20.0F)`

---

*End of Phase 20.0F. Working tree has only the two files above; no commit/push performed.*

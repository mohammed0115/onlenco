# PLACEMENT — Final Validation Report

> No deploy, no `scripts/update.sh`, no push performed. Evidence below is from
> the working tree + local test runs only.

---

## 1) Where are `ai_alternatives` stored? General or per-transcript?

**Storage:** `PlacementQuestion.ai_alternatives` — a `JSONField` on the QUESTION,
not on the attempt/answer.
- [placement/models.py:143](placement/models.py#L143) — `ai_alternatives = models.JSONField(default=list, blank=True, ...)`

**General per-question, NOT per-student-transcript (for display):**
- The result page resolves them read-only: [placement/views.py](placement/views.py) `_annotate()` calls
  `alternatives_for(q, student_transcript=aq.student_answer)` **with `generate=False`** (the default),
  so it returns the cached/starter list and **ignores the transcript** for display.
- [placement/services/ai_alternatives.py](placement/services/ai_alternatives.py) `alternatives_for(question, *, generate=False, student_transcript=None, ...)`:
  resolution order = cached on question → built-in starter set → (only if `generate=True`) one AI call, then cached.
- The `student_transcript` is only ever passed to the AI **generate** path (custom questions), never used to vary the displayed list for the fixed bank.

**No fixed John/Egypt (fixed your concern):** the starter suggestions are now sentence
FRAMES with a blank `…`, not fixed names/countries:
- [placement/services/ai_alternatives.py](placement/services/ai_alternatives.py) `STARTER_ALTERNATIVES`:
  - name → `"My name is … ."`, `"I'm … ."`, `"… (your name)."`
  - from → `"I'm from … ."`, `"I come from … ."`, `"I'm originally from … ."`
  - (no `"John"`, no `"Egypt"`)
- Test guard: `test_starter_questions_need_no_ai_call` asserts `"Egypt"`/`"John"` are NOT present;
  `ResultPageAlternativesTests` asserts `"I come from"` renders and `"Egypt"` does not.

---

## 2) Proof: Placement Speaking / VoiceCallEvaluation / STT does NOT consume AI-Tutor minutes

This is about the **voice call itself**, not just `placement_alternatives`.

**File + function that prevents consumption:**
- `subscriptions/services/session_service.py` → `end_session()`:
  [subscriptions/services/session_service.py:153](subscriptions/services/session_service.py#L153)
  ```python
  if session.source == "placement_voice":
      remaining, _src = quota_service.effective_ai_tutor_remaining(session.user)
      charged_source = "none"          # nothing deducted
  else:
      remaining, charged_source = quota_service.deduct_session_seconds(...)
  ```
- The session is opened with that source + quota skipped in
  `tutor/api/views.py` → `voice_call_session()`:
  [tutor/api/views.py:905](tutor/api/views.py#L905) `source="placement_voice" if is_placement_call else "voice_call"`,
  [tutor/api/views.py:910](tutor/api/views.py#L910) `skip_quota=is_placement_call`.
- The realtime session-start log uses `feature=placement_speaking` (NOT `ai_tutor`), and `voice_call_log`
  skips the fallback deduction for placement calls.

**Test that proves the daily quota does NOT decrease after a placement speaking call:**
- `placement/tests/test_speaking_quota.py::PlacementSpeakingPolicyTests::test_placement_speaking_does_not_consume_ai_tutor_minutes`
  [placement/tests/test_speaking_quota.py:118](placement/tests/test_speaking_quota.py#L118)
  - Subscribes the user (real plan minutes), runs a full session→log placement call (180s),
    then asserts:
    `UserDailyQuota.objects.filter(user=..., ai_tutor_seconds_used__gt=0).exists()` is **False**
    and the session row is `source="placement_voice"`, `quota_source="none"`.
- Contrast (proves a REGULAR call DOES consume): `test_regular_ai_tutor_consumes_daily_plan_minutes`
  [placement/tests/test_speaking_quota.py:221](placement/tests/test_speaking_quota.py#L221) — after a regular call,
  `UserDailyQuota.ai_tutor_seconds_used == 120`.
- STT: the realtime call's transcription is part of the same `placement_voice` session, so it is
  covered by the same non-deduction path. There is no separate STT minute charge.

---

## 3) Full student journey

| Step | Where | Test |
|---|---|---|
| New student (no course/placement) sees the choice | `accounts/views.py::onboarding_choice` ([accounts/views.py:498](accounts/views.py#L498)) | `test_full_placement_journey_register_to_dashboard` |
| **Start from Beginner → A0, no placement again** | `accounts/views.py::onboarding_beginner` → `accounts/onboarding.py::complete_beginner_onboarding` (`DEFAULT_BEGINNER_LEVEL="A0"`, `onboarding_path="beginner_start"`) [accounts/onboarding.py:118](accounts/onboarding.py#L118) | `test_full_beginner_journey_register_to_first_lesson` asserts `profile.cefr_level == "A0"` |
| **Take Placement → written + speaking + result** | `placement_start → placement_written → placement_voice_handoff → placement_voice_finalise → placement_result` | `test_full_placement_journey_register_to_dashboard` (written answers → speaking → result) |
| Course assigned after result | `placement_voice_finalise` / `_score_and_finalise` → `complete_placement_onboarding(profile, level)` | journey test asserts `onboarding_path == "placement_test"`, dashboard renders |
| logout/login → no placement again | `onboarding_lib.next_url_for(user)` returns `None` once placed | journey test: `self.assertIsNone(onboarding_lib.next_url_for(user))` |
| Starting placement alone doesn't finalize onboarding | entry redirect + `placement_start` | `test_starting_placement_does_not_complete_onboarding` |

Returning student with an in-progress attempt resumes at the right step
(`placement_start` resume logic), and admin reset reopens the speaking test.

---

## 4) Proof: oral alternatives do NOT enter the final score

- **Scoring file/function:** `placement/views.py::map_speaking_transcript()` — per-question speaking
  score comes ONLY from the rubric keyword match or the call's overall score:
  [placement/views.py:463](placement/views.py#L463) `score = 100.0` (keyword hit) /
  [placement/views.py:465](placement/views.py#L465) `score = overall` — it never reads `ai_alternatives`.
  Written scoring (`grade_written_section`, [placement/views.py:369](placement/views.py#L369)) is the answer key only.
- **Alternatives are attached separately, read-only**, in `placement_result::_annotate` (`aq.alternatives = …`),
  with the UI label "for learning only — these do not affect your score".
- **Test:** `placement/tests/test_placement_v2_features.py::test_alternatives_do_not_affect_grading`
  [placement/tests/test_placement_v2_features.py:96](placement/tests/test_placement_v2_features.py#L96) —
  sets `aq.score=70.0`, calls `alternatives_for(...)`, refreshes, asserts `aq.score == 70.0` (unchanged).

---

## 5) Is oral-section completion required before the final result?

**YES — a STRICT-but-safe gate is now enforced (your decision, implemented).**
Default `PLACEMENT_REQUIRE_SPEAKING_FOR_FINAL_RESULT = True`
([config/settings/base.py:320](config/settings/base.py#L320)), min answers configurable via
`PLACEMENT_SPEAKING_MIN_ANSWERS` (default 3, [base.py:324](config/settings/base.py#L324)).

**The gate ([placement/views.py:538](placement/views.py#L538), in `placement_voice_finalise`):**
```python
speaking_ok = (eval_obj is not None) and (answered >= completion.min_answers())
if completion.require_speaking() and not speaking_ok:
    _block_speaking_and_retry(request, attempt, conv, answered)   # no result, no course
    messages.warning(request, _speaking_retry_message(request, answered))
    return redirect("placement_voice_handoff", attempt_id=attempt.id)
```
- **Written-only is not enough:** the result page itself is gated
  ([placement/views.py:653](placement/views.py#L653)) — `if require_speaking and not is_finalised(attempt): redirect to speaking`.
- **`is_finalised` = `status=="completed"` AND a `PlacementResult` row exists** — set only when speaking completes.

**Retry behavior ([placement/views.py:487](placement/views.py#L487) `_block_speaking_and_retry`):**
- **Speaking not completed** → redirect to the speaking step, no result, no course, message
  AR: "يرجى إكمال جزء التحدث قبل عرض النتيجة النهائية."
- **Empty / too short** (1..min-1 answers) → `PlacementSpeakingAttempt.status = needs_retry`,
  `is_used_attempt=False` (lifetime attempt KEPT), message
  AR: "لم نتمكن من سماع إجابتك بوضوح. حاول مرة أخرى." The partial call (messages + eval) is
  cleared so the retry is clean.
- **STT / VoiceCallEvaluation failure** (`eval_obj is None`) → same safe path: no crash, no result,
  `needs_retry`, retry allowed, **no AI-Tutor minutes consumed**, placement NOT finalised.
- A too-short / failed attempt is now retryable WITHOUT an admin reset — `finalise_attempt` marks
  `< min` answers as `needs_retry` / `is_used_attempt=False`
  ([placement/services/speaking_quota.py:140](placement/services/speaking_quota.py#L140)).

**Admin override (explicit + audited) — [platform_admin/views.py:190](platform_admin/views.py#L190),
[placement/services/admin_override.py](placement/services/admin_override.py):**
- Action `finalise-placement` on the student detail page: admin picks a level + **must enter a reason**.
- `admin_finalise_placement(...)` assigns the level + course, creates the `PlacementResult`, and writes
  an audit (`source="admin_override"`, `actor_id`, `reason`, `at`) onto the result transcript and the
  `PlacementSpeakingAttempt.metadata`. Never automatic for normal students.

**Tests ([placement/tests/test_placement_gate.py](placement/tests/test_placement_gate.py)):**
| Scenario | Test | Result |
|---|---|---|
| Written done, speaking missing → result blocked | `test_result_blocked_when_speaking_missing` | ✅ |
| Too-short speaking → blocked + retryable | `test_too_short_speaking_blocks_and_is_retryable` | ✅ |
| STT/eval failure → no crash, no result, retry | `test_stt_failure_no_crash_no_result` | ✅ |
| Valid speaking → finalises + course assigned | `test_valid_speaking_finalises_and_assigns` | ✅ |
| Course only after written+speaking | `test_course_not_assigned_until_speaking_complete` | ✅ |
| Gate never consumes AI-Tutor minutes | `test_gate_does_not_consume_minutes` | ✅ |
| Admin override finalises (reason required) | `test_admin_override_finalises` | ✅ |

### 5b) Tutor-led speaking + no infinite block for true beginners

**Tutor-led conversation (the learner never starts):** the realtime prompt makes the
tutor ask every question first, retry per question (repeat slowly → beginner hint, up to
`PLACEMENT_SPEAKING_MAX_RETRIES_PER_QUESTION`), then move on so all 5 are asked
([tutor/services/realtime_session.py](tutor/services/realtime_session.py)). The call page shows
the helper text — AR: "استمع إلى السؤال ثم أجب بصوتك بكلمة أو جملة قصيرة."
([templates/tutor/voice_call.html](templates/tutor/voice_call.html), test `test_call_page_shows_tutor_led_helper`).

**Three speaking outcomes ([placement/views.py](placement/views.py) `placement_voice_finalise`):**
| Outcome | Condition | Result |
|---|---|---|
| **(A) completed_by_answers** | `eval` present AND answered ≥ `MIN_ANSWERS` (3) | Normal finalise |
| **(B) unable_to_answer_after_retries** | `eval` present, answered < MIN, but the tutor asked ≥ MIN questions **OR** `speaking_retry_count ≥ PLACEMENT_SPEAKING_MAX_RETRIES` (3) | **Conservative** finalise — never blocked forever |
| **(6) failed_system** | `eval` is None (STT/provider/system error) | NOT finalised, retry, no minutes |

**unable_to_answer vs technical failure (the key distinction):**
- *unable_to_answer* = the **system worked** (we have a VoiceCallEvaluation) but the **student**
  couldn't answer after the tutor asked + retried. This is treated as evidence of very low
  speaking ability, NOT an error: `_finalise_speaking_unable` sets `speaking_score=0`, speaking
  level = `PLACEMENT_SPEAKING_UNABLE_LEVEL` (A0), and caps the overall level at
  `PLACEMENT_FINAL_CAP_WHEN_UNABLE` (A1) via `level_mapping.cap_level`. The placement IS finalised
  and the course assigned — a beginner moves forward instead of looping. `PlacementSpeakingAttempt`
  → `unable_to_answer_after_retries`, `is_used_attempt=True`.
- *failed_system* = the **system failed** → `_mark_speaking_failed_system`: status `failed_system`,
  `is_used_attempt=False`, retryable, NOT finalised, **no AI-Tutor minutes consumed**.

**Conservative placement / no infinite blocking — tests:**
| Scenario | Test | Result |
|---|---|---|
| Tutor asked all, student couldn't → conservative finalise (capped A1) | `test_unable_after_full_call_finalises_conservatively` | ✅ |
| Repeated short calls reach unable after max retries | `test_repeated_silence_reaches_unable_after_max_retries` | ✅ |
| Tutor-led helper text shown on call page | `test_call_page_shows_tutor_led_helper` | ✅ |

---

## 6) Exact modified/added file paths

| File | Change |
|---|---|
| [placement/models.py](placement/models.py) | `+ ai_alternatives` JSONField on `PlacementQuestion` |
| [placement/views.py](placement/views.py) | `map_speaking_transcript` alignment; finalise prefetches alternatives + uses level mapping fallback; result `_annotate` attaches `aq.alternatives` |
| [placement/services/ai_alternatives.py](placement/services/ai_alternatives.py) | NEW — suggestions service (starter frames, cache, AI generate, graceful) |
| [placement/services/level_mapping.py](placement/services/level_mapping.py) | NEW — configurable %→CEFR mapping |
| [templates/placement/result.html](templates/placement/result.html) | "Other possible answers / إجابات أخرى مقترحة" block |
| [placement/tests/test_placement_v2_features.py](placement/tests/test_placement_v2_features.py) | NEW — 8 tests |
| [ai_usage/constants.py](ai_usage/constants.py) | `+ FEATURE_PLACEMENT_ALTERNATIVES` |
| [config/settings/base.py](config/settings/base.py) | `+ PLACEMENT_LEVEL_MAP` |
| [placement/migrations/0010_placementquestion_ai_alternatives.py](placement/migrations/0010_placementquestion_ai_alternatives.py) | migration |
| [ai_usage/migrations/0006_alter_aiusagelog_feature.py](ai_usage/migrations/0006_alter_aiusagelog_feature.py) | migration |

---

## 6b) Files added/modified for the strict gate

| File | Change |
|---|---|
| [config/settings/base.py](config/settings/base.py) | `+ PLACEMENT_REQUIRE_SPEAKING_FOR_FINAL_RESULT` (True), `+ PLACEMENT_SPEAKING_MIN_ANSWERS` (3) |
| [placement/models.py](placement/models.py) | `+ STATUS_NEEDS_RETRY` on `PlacementSpeakingAttempt` |
| [placement/services/completion.py](placement/services/completion.py) | NEW — gate helpers (`require_speaking`, `speaking_is_complete`, `is_finalised`) |
| [placement/services/admin_override.py](placement/services/admin_override.py) | NEW — audited admin finalise |
| [placement/services/speaking_quota.py](placement/services/speaking_quota.py) | `finalise_attempt` uses min-answers threshold → `needs_retry` (not used); `+ mark_needs_retry` |
| [placement/views.py](placement/views.py) | gate in `placement_voice_finalise`; `placement_result` guard; `_block_speaking_and_retry`, `_speaking_retry_message` |
| [platform_admin/views.py](platform_admin/views.py) | `+ finalise-placement` admin action |
| [platform_admin/templates/platform_admin/students/detail.html](platform_admin/templates/platform_admin/students/detail.html) | admin override form (level + reason) |
| [placement/tests/test_placement_gate.py](placement/tests/test_placement_gate.py) | NEW — 7 gate tests |
| [placement/migrations/0011_alter_placementspeakingattempt_status.py](placement/migrations/0011_alter_placementspeakingattempt_status.py) | migration |

---

## 7) Command results (run locally just now — strict-gate build)

```
$ python manage.py check
System check identified no issues (0 silenced).

$ python manage.py makemigrations --check --dry-run
No changes detected

$ python manage.py migrate --check
(exit code 0 — no unapplied migrations)

$ python manage.py test placement
Ran 108 tests — OK

$ python manage.py test ai_usage
Ran 91 tests — OK

$ python manage.py test accounts
Ran 96 tests — OK
```

> Strict-gate + tutor-led build adds migration `placement.0012`
> (`speaking_retry_count`, new `failed_system` / `unable_to_answer_after_retries` statuses)
> and settings `PLACEMENT_SPEAKING_MAX_RETRIES_PER_QUESTION` (2),
> `PLACEMENT_SPEAKING_MAX_RETRIES` (3), `PLACEMENT_SPEAKING_UNABLE_LEVEL` (A0),
> `PLACEMENT_FINAL_CAP_WHEN_UNABLE` (A1).

---

## 8–10) No production deploy, no `update.sh`, no push in these validation turns.

Git state at validation time:
- `HEAD == origin/main == 643cfc6` — earlier placement work (incl. migrations
  `placement.0010`, `ai_usage.0006`) was pushed in a PRIOR turn, before your "no push" instruction.
- All work from the validation + strict-gate turns is **uncommitted and unpushed**, awaiting your review:
  - John/Egypt → neutral frames (`ai_alternatives.py` + its tests).
  - Strict gate: `completion.py`, `admin_override.py`, `speaking_quota.py`, `views.py`,
    `models.py` (+ migration `placement.0011`), `platform_admin` action + form, `settings/base.py`,
    `test_placement_gate.py`, updated `test_speaking_quota.py` / `test_placement_v2_features.py`.
  - `PLACEMENT_FINAL_VALIDATION.md` — this report.

No `scripts/update.sh`, no production deploy, no `git push` were run.

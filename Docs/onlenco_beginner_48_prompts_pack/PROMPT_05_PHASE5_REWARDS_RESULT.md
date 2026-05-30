# تقرير Prompt 05 — XP / Hearts / Streak / Daily Goal / Badges / Rewards

**التاريخ:** 2026-05-29
**المرحلة:** Phase 5 — نظام تحفيز حقيقي داخل Onlenco
**الحالة:** ✅ مكتمل + اختبارات خضراء (422 اختبار في `motivation` + `courses` — كلها ناجحة)
**المبدأ:** توسيع `motivation` app الموجود (لا app جديد)، احترام idempotency في كل منح XP.

---

## 1) الملخّص التنفيذي

### قبل Prompt 05
- **UserXP** موجود كـ aggregate فقط: total / weekly / monthly / level.
- **UserBadge** موجود كـ ledger مع UNIQUE(user, badge_code) لكن **بدون catalog** (BadgeDefinition).
- **`streak_service.get_current_streak`** يقرأ فقط من `LearnerActivitySnapshot` — لا state model مستقل.
- **لا يوجد** Daily Goal model.
- **لا يوجد** XPTransaction (ledger للسجلّ).
- منح XP عبر `challenge_rewards.credit_user_xp` يستدعي `xp_service.award_xp` — لكن **بدون idempotency على مستوى المصدر**: الـ refresh يمكن أن يكرّر القيد.

### بعد Prompt 05
- ✅ **XPTransaction** + ledger-aware grants — كل XP يُسجَّل بمفتاح فريد (source_type + source_id) ولا يتكرّر.
- ✅ **StudentStreak + StreakActivity** كمصدر حقيقة (state model + log).
- ✅ **DailyGoal + DailyGoalProgress** + مكافأة لمرّة واحدة يومياً.
- ✅ **BadgeDefinition** catalog مع 10 شارات + seed command + evaluator تلقائي بعد الـ Challenge.
- ✅ **Encouragement service** بسيط (deterministic، بلا AI) عربي/إنجليزي.
- ✅ **Hearts policy** مركزية في service واحد (الإعداد + خصم + إعادة تعبئة عند retry).
- ✅ **Summary screen** يعرض: XP breakdown + Streak + Daily Goal bar + Recent Badges + Encouragement.
- ✅ Challenge / Quiz / Question Types / Game UI كلّها سليمة (91 اختبار سابق + 38 جديد + كل الـ courses الأخرى).
- ✅ **422 اختبار** — كلها خضراء.

### هل أصبح نظام التحفيز حقيقياً؟
نعم. كل grant مسجَّل، كل streak يُحسب من state model، كل badge له catalog قابل للتعديل من الإدارة، وكل رسالة تشجيع بسيطة لكن لطيفة. الأهم: لا تكرار XP عند الـ refresh أو الـ retry.

---

## 2) الملفات المعدلة أو المُنشأة

### ملفات جديدة (9)

| الملف | الدور |
|---|---|
| `motivation/migrations/0008_badgedefinition_dailygoal_studentstreak_and_more.py` | إنشاء 6 جداول جديدة |
| `motivation/services/xp_ledger.py` | XPTransaction + idempotency + breakdown |
| `motivation/services/streak_v2.py` | StudentStreak/StreakActivity state machine |
| `motivation/services/daily_goal_service.py` | Daily goal progress + one-shot bonus |
| `motivation/services/badge_catalog.py` | BadgeDefinition catalog + evaluator |
| `motivation/services/encouragement_service.py` | عبارات تشجيع EN/AR deterministic |
| `motivation/services/hearts_service.py` | Hearts policy |
| `motivation/management/commands/seed_badge_definitions.py` | seed 10 badges (idempotent) |
| `motivation/tests/test_rewards_phase5.py` | 38 اختباراً |
| `Docs/.../PROMPT_05_PHASE5_REWARDS_RESULT.md` | هذا التقرير |

### ملفات مُحدَّثة (4)

| الملف | التعديل | السبب |
|---|---|---|
| `motivation/models.py` | إضافة 6 models: XPTransaction, StudentStreak, StreakActivity, DailyGoal, DailyGoalProgress, BadgeDefinition | البنية المطلوبة لـ Phase 5 |
| `courses/services/challenge_rewards.py` | استبدال raw awards بـ ledger helpers (credit_answer_xp, credit_completion_bonus, credit_perfect_bonus) + XP حسب skill (listening 12 / speaking placeholder 5) | منع double-award + breakdown دقيق |
| `courses/services/challenge_runner.py` | استدعاء daily_goal + streak + badge_catalog عند الإجابة الصحيحة و عند الإكمال + حفظ status قبل تقييم البادجز | wiring الكامل |
| `courses/views.py` | `_build_rewards_context` يبني rewards dict ويرسله للـ Summary | تمرير للـ template |
| `templates/courses/challenge_summary.html` | أقسام XP breakdown + Streak + Daily goal + Recent badges + Encouragement banner | عرض الـ rewards |

---

## 3) XP System

### الـ Aggregate (موجود مسبقاً)
- `UserXP` row واحد لكل مستخدم: `total_xp`, `weekly_xp`, `monthly_xp`, `level_number`.

### الـ Ledger (جديد)
- **`XPTransaction`** — صف لكل منح XP:
  - `user`, `amount`, `reason`, `source_type`, `source_id`, `metadata` (JSON), `created_at`.
  - **UNIQUE PARTIAL INDEX** على `(user, source_type, source_id)` حيث `source_id != ""`.
  - الـ aggregate يُحدَّث بعد كتابة الـ row في نفس الـ atomic block.

### قواعد XP (مركزية في `courses/services/challenge_rewards.py`)

| الحدث | XP | source_type | source_id |
|---|---|---|---|
| إجابة صحيحة عادية | 10 | `challenge_answer` | answer.pk |
| إجابة صحيحة listening | 12 | `challenge_answer` | answer.pk |
| Speaking placeholder | 5 | `challenge_answer` | answer.pk |
| إجابة خطأ | 0 | — | — |
| إكمال Challenge | 20 | `challenge_completion` | session.pk |
| Perfect bonus | +10 | `perfect_bonus` | session.pk |
| Daily goal bonus | 25 | `daily_goal_bonus` | date string |
| Badge reward | حسب badge | `badge_reward` | badge.code |

### منع التكرار
- كل grant له `source_id` ثابت → INSERT يفشل بـ IntegrityError → الـ service يعيد `None` بهدوء.
- Refresh الـ Summary لا يعيد القيد.
- Retry نفس الـ Challenge → session جديد → answer جديد → grant جديد (سلوك مقصود).
- `_on_session_terminate` لو نُودي مرتين → completion + perfect لا يتكرّران.

### الـ Breakdown
- `xp_ledger.xp_breakdown_for_session(session)` يرجّع dict: `{challenge_answer: 30, challenge_completion: 20, perfect_bonus: 10, total: 60}`.
- Summary screen يقرأ منه ويعرض كل سطر.

---

## 4) Hearts Policy

- **عدد القلوب الافتراضي:** 5 (من `MOTIVATION_DEFAULT_HEARTS`).
- **عند الخطأ:** `hearts_service.apply_wrong_answer(session)` تنقص واحداً وتحفظ.
- **عند انتهاء القلوب:** الـ runner يضع `session.status = "failed"` ويُنهي الجلسة → الـ Summary يعرض "Practice again" برسالة لطيفة:
  - EN: *"Good effort. Try again to strengthen this skill."*
  - AR: *"محاولة جيدة. جرّب مرة أخرى لتقوية هذه المهارة."*
- **عند Retry:** session جديد بـ 5 قلوب (Phase 5 لا يحدّ عدد المحاولات).
- **`get_hearts_display(session)`** → dict: `{remaining, total, lost, low, depleted}`.
- **TODO Phase 6:** wallet عام، refill كل 4 ساعات، خيار شراء بـ XP.

---

## 5) Streak System

### State Machine
- `StudentStreak` (one per user): `current_streak`, `longest_streak`, `last_activity_date`, `streak_freeze_count`.
- `StreakActivity` (one per user/date/type): سجل الأحداث.

### القواعد
- **Counting types** (تَزِيد streak): `challenge_completed`, `lesson_completed`, `daily_goal_completed`.
- **Non-counting** (مُسجَّلة فقط): `challenge_started`.
- **منع التكرار في نفس اليوم:** UNIQUE(user, date, type) — إعادة الحدث في نفس اليوم لا تَزِيد streak.
- **التقدم:**
  - `last == None` → current = 1، advanced = True.
  - `when == last` → no-op.
  - `when == last + 1day` → current += 1.
  - `when > last + 1day` → current = 1 (reset).
  - `when < last` → backdated، تُتجاهَل.
- **longest_streak** يُحدَّث تلقائياً.

### Service API
- `record_learning_activity(user, type, xp_earned, on_date, metadata)` → `(StudentStreak, advanced: bool)`.
- `get_streak(user)`.
- `would_continue_streak(user, on_date)`.

---

## 6) Daily Goal

### المودلز
- `DailyGoal` (one per user): `goal_type` (xp/minutes/challenges)، `target_value`، `is_active`.
- `DailyGoalProgress` (one per user/date): `xp_earned`, `minutes_spent`, `challenges_completed`, `completed`, `completed_at`, `bonus_awarded`.

### الإعدادات
- **النوع الافتراضي:** XP.
- **الهدف الافتراضي:** 50 XP/يوم (من `MOTIVATION_DAILY_GOAL_XP`).
- **المكافأة:** 25 XP لمرة واحدة (من `MOTIVATION_DAILY_GOAL_BONUS_XP`).

### كيف يُحسب التقدم
- بعد كل grant XP من Challenge → `update_daily_goal_progress(user, xp_delta)`.
- يُحدَّث `xp_earned`.
- لو تخطى الهدف ولم يكن `completed=True`: يُعيَّن، ويُسجَّل `completed_at`.
- لو `completed=True` ولم تُمنح المكافأة (`bonus_awarded=False`):
  - يُمنَح `daily_goal_bonus` (25 XP) عبر الـ ledger مع `source_id=date`.
  - يُسجَّل `daily_goal_completed` كـ StreakActivity.
  - `bonus_awarded = True`.

### الـ Summary
- `get_daily_goal_summary(user)` → `{goal_type, target, earned, remaining, pct, completed, bonus_awarded, bonus_value}`.
- الـ template يرسم progress bar أزرق.

---

## 7) Badges

`BadgeDefinition` catalog + `UserBadge` ledger (الموجود سابقاً) + evaluator يدير المنح.

| Badge | Criteria | XP reward | Status |
|---|---|---|---|
| FIRST_CHALLENGE | أول challenge مكتمل | 0 | ✅ |
| FIRST_LESSON | أول درس مكتمل | 50 | ✅ (يدوي حالياً — لم يُربط بـ lesson completion) |
| PERFECT_CHALLENGE | challenge بلا أخطاء | 25 | ✅ |
| FIVE_CHALLENGES | 5 challenges مكتملة | 50 | ✅ |
| SEVEN_DAY_STREAK | streak 7 أيام | 50 | ✅ |
| LISTENING_STAR | 10 إجابات listening صحيحة | 25 | ✅ |
| SPEAKING_BRAVE | 5 بطاقات speaking placeholder صحيحة | 25 | ✅ |
| VOCAB_HERO | 20 إجابات vocabulary صحيحة | 25 | ✅ |
| GRAMMAR_BUILDER | 20 إجابات grammar صحيحة | 25 | ✅ |
| COMEBACK_LEARNER | عاد بعد ≥3 أيام غياب وأكمل challenge | 25 | ✅ |

### الـ Evaluator
- `badge_catalog.evaluate_badges_after_challenge(user, session)` → يقيّم كل badge ضد التاريخ → يُسجِّل ما لم يُسجَّل + يمنح xp_reward عبر الـ ledger (مع `source_id=code`).
- المعرفة بالـ skill تأتي من `question_type_registry.get_spec(qt).skill`.

### Seed Command
```bash
python manage.py seed_badge_definitions
# [OK] Badge catalog seeded: 10 created, 0 updated, 10 total.
```
- Idempotent: re-run = 0 created, 10 updated.

---

## 8) Encouragement Messages

`encouragement_service.get_message(event_type, language, context)`:
- 10 event types: `correct_answer`, `wrong_answer`, `challenge_completed`, `challenge_failed`, `perfect_challenge`, `daily_goal_completed`, `streak_continued`, `badge_awarded`, `comeback`, `low_hearts`, `first_lesson`.
- Bilingual pairs (EN/AR).
- Deterministic via `hashlib.md5(context)` → نفس السياق دائماً يُعطي نفس الـ message عند الـ refresh.

### أمثلة
| Event | EN | AR |
|---|---|---|
| correct_answer | "Great job!" أو "Nice work!" أو "Right on." | "رائع جداً!" / "أحسنت!" / "إجابة صحيحة." |
| wrong_answer | "Good try. Mistakes help you learn." | "محاولة جيدة. الأخطاء تساعدك على التعلم." |
| challenge_completed | "Nice work! You completed this challenge." | "عمل ممتاز! أكملت هذا التحدي." |
| perfect_challenge | "Perfect! You answered everything correctly." | "ممتاز! أجبت على كل شيء بشكل صحيح." |
| daily_goal_completed | "You reached your daily goal!" | "حققت هدفك اليومي!" |
| challenge_failed | "Good effort. Try again to strengthen this skill." | "محاولة جيدة. جرّب مرة أخرى لتقوية هذه المهارة." |
| comeback | "Welcome back. Good to see you again." | "أهلاً بعودتك. سعيدون برؤيتك مجدداً." |

التون: قصير، محترم، يناسب الكبار والصغار، لا exclamations مبالغ فيها.

---

## 9) Challenge Integration

### عند Correct Answer (`submit_answer`)
1. `xp = xp_for_answer(question, is_correct=True)` — حسب skill.
2. ChallengeAnswer يُكتب.
3. `credit_answer_xp(user, amount=xp, answer=answer, session=session)` → ledger entry بـ source_id=answer.pk.
4. `daily_goal_service.update_daily_goal_progress(user, credited)` → يُحدِّث الـ progress + (لو تخطى الهدف) يمنح bonus + يسجل StreakActivity.

### عند Wrong Answer
1. `hearts_service.apply_wrong_answer(session)` → ينقص قلب.
2. لو وصل لـ 0 → status="failed" → `_on_session_terminate(perfect=False)`.

### عند Challenge Completion (`continue_to_next` → نهاية الـ deck)
1. `session.status = "completed"` + يُحفَظ في DB **قبل** التقييم (لأن evaluator يقرأ الـ count).
2. `credit_completion_bonus(session)` → 20 XP (مرة واحدة لكل session).
3. `credit_perfect_bonus(session)` → 10 XP لو `wrong_count=0` (مرة واحدة).
4. `daily_goal_service.update_daily_goal_progress(...)` بـ challenges_delta=1.
5. `streak_v2.record_learning_activity(user, "challenge_completed", xp)` → يقفز streak يوماً واحداً (أو يبدأه).
6. `badge_catalog.evaluate_badges_after_challenge(user, session)` → يمنح كل badge مستوفية الشرط (idempotent عبر UserBadge UNIQUE).
7. Mirror score إلى `CourseLessonProgress`.

### عند Challenge Failed (hearts = 0)
1. `_on_session_terminate(perfect=False)` يُنفَّذ.
2. **لا** completion bonus، **لا** perfect bonus، **لا** streak record.
3. الـ progress score يُحدَّث (mirror).
4. Summary يعرض رسالة لطيفة: "Good effort. Try again."

---

## 10) Summary Screen

الـ Summary الآن يحمل أقسام جديدة (`data-encouragement`, `data-xp-breakdown`, `data-streak`, `data-daily-goal`, `data-badges`):

```
┌─────────────────────────────┐
│ 🏆 Perfect Challenge!       │
│ Perfect Bonus +10 XP        │
├─────────────────────────────┤
│ "Perfect! You answered..."   │  encouragement banner
├─────────────────────────────┤
│ 6 stat tiles                 │  XP / Accuracy / Correct / Hearts / Time / Wrong
├─────────────────────────────┤
│ XP BREAKDOWN                 │
│ Answers          +30 XP      │
│ Completion       +20 XP      │
│ Perfect bonus    +10 XP      │  (highlighted)
│ Daily goal bonus +25 XP      │  (highlighted)
│ ─────────                    │
│ Total           +85 XP       │
├─────────────────────────────┤
│ 🔥 STREAK     🎯 DAILY GOAL  │
│ 3d           ▓▓▓▓▓▓░░ 60/50 │
│ Longest 5d   Done!          │
├─────────────────────────────┤
│ RECENT BADGES               │
│ 🏆 First Challenge          │
│ ✨ Perfect Challenge        │
├─────────────────────────────┤
│ [Practice Again] [Next →]   │
│ [Review mistakes (soon)]    │
│ [Back to lesson]            │
└─────────────────────────────┘
```

- إن لم تكن هناك badges جديدة → القسم لا يَظهر (لا empty section).
- Streak/Daily-goal دائماً يظهران مع defaults صحيحة.
- Encouragement banner يدوّر تلقائياً حسب status + session.pk.

---

## 11) الاختبارات

| Test class | عدد | النتيجة |
|---|---|---|
| XPLedgerTests | 7 | ✅ |
| HeartsPolicyTests | 4 | ✅ |
| StreakTests | 6 | ✅ |
| DailyGoalTests | 5 | ✅ |
| BadgeCatalogTests | 4 | ✅ |
| EncouragementTests | 4 | ✅ |
| ChallengeIntegrationTests | 7 | ✅ |
| SummaryRewardsRenderingTests | 1 | ✅ |
| **مجموع Phase 5** | **38** | **✅** |

### تفصيل الاختبارات (قائمة كاملة)

**XP:**
- `test_xp_transaction_created_for_correct_answer` ✅
- `test_xp_total_updates` ✅
- `test_xp_not_awarded_twice_for_same_answer` ✅
- `test_zero_amount_is_noop` ✅
- `test_completion_bonus_awarded_once` ✅
- `test_perfect_bonus_awarded_once` ✅
- `test_perfect_bonus_not_awarded_when_wrong_count` ✅

**Hearts:**
- `test_get_default_hearts_returns_5` ✅
- `test_wrong_answer_removes_heart` ✅
- `test_hearts_zero_fails_session` ✅
- `test_retry_resets_hearts` ✅

**Streak:**
- `test_streak_starts_on_first_completed_challenge` ✅
- `test_streak_does_not_increment_twice_same_day` ✅
- `test_streak_increments_next_day` ✅
- `test_streak_resets_after_gap` ✅
- `test_longest_streak_updates` ✅
- `test_non_counting_activity_logged_but_no_advance` ✅

**Daily Goal:**
- `test_daily_goal_progress_updates_with_xp` ✅
- `test_daily_goal_completed_when_target_crossed` ✅
- `test_daily_goal_bonus_awarded_once` ✅
- `test_daily_goal_summary` ✅
- `test_daily_goal_records_streak_activity` ✅

**Badges:**
- `test_seed_badge_definitions_idempotent` ✅
- `test_award_badge_creates_userbadge_and_credits_xp` ✅
- `test_badge_not_awarded_twice` ✅
- `test_award_unknown_badge_is_safe` ✅

**Encouragement:**
- `test_correct_answer_returns_english_default` ✅
- `test_arabic_branch_returns_arabic` ✅
- `test_bilingual_returns_both` ✅
- `test_unknown_event_returns_empty` ✅

**Challenge Integration:**
- `test_challenge_completion_credits_xp_ledger` ✅
- `test_challenge_completion_updates_streak` ✅
- `test_challenge_completion_updates_daily_goal` ✅
- `test_challenge_failed_does_not_increment_streak` ✅
- `test_perfect_challenge_awards_perfect_badge` ✅
- `test_first_completed_challenge_awards_first_badge` ✅
- `test_completion_idempotent_on_repeat_terminate` ✅

**Summary UI:**
- `test_summary_includes_xp_breakdown_and_streak` ✅

### Regression (السابقة) — كلها سليمة:
- 18 challenge engine tests ✅
- 39 question types tests ✅
- 34 UI polish tests ✅
- باقي اختبارات courses (231) ✅
- كل اختبارات motivation الأخرى ✅

---

## 12) أوامر الاختبار ونتائجها

```bash
$ DJANGO_SETTINGS_MODULE=config.settings.test python manage.py check
System check identified no issues (0 silenced).

$ DJANGO_SETTINGS_MODULE=config.settings.test python manage.py test motivation
Ran 144 tests in 7.510s
OK

$ DJANGO_SETTINGS_MODULE=config.settings.test python manage.py test courses
Ran 278 tests in 35.247s
OK

$ DJANGO_SETTINGS_MODULE=config.settings.test python manage.py test motivation courses
Ran 422 tests in 42.225s
OK

$ DJANGO_SETTINGS_MODULE=config.settings.test python manage.py test motivation.tests.test_rewards_phase5
Ran 38 tests in 1.035s
OK
```

أوامر تشغيلية للإنتاج:

```bash
python manage.py migrate motivation
python manage.py seed_badge_definitions
# [OK] Badge catalog seeded: 10 created, 0 updated, 10 total.
```

---

## 13) المشاكل المتبقية

### P0 — حاسمة
لا يوجد.

### P1 — مهمّة لـ Phase 6
- 🔜 **FIRST_LESSON badge** ليس مربوطاً تلقائياً بإكمال الـ Lesson — يجب ربطه بحدث lesson_completion من `CourseLessonProgress.save`.
- 🔜 **Streak freeze** غير مفعّل (الـ field موجود لكن بدون منطق consume).
- 🔜 **Heart refill** عبر الزمن (الآن: unlimited retry).

### P2 — تحسينات Phase 6+
- 🔜 Dashboard widget يعرض total XP + streak + daily goal (الآن: فقط في Summary).
- 🔜 صفحة Rewards شخصية تستعرض كل XP transactions + كل badges.
- 🔜 Per-user Daily Goal editor (الآن: default ثابت 50 XP، يمكن للـ admin تعديله).
- 🔜 SFX حقيقية مع badge unlock (الـ hooks جاهزة من Phase 4).

### P3 — تحسينات صغيرة
- توسعة `MOTIVATION_DAILY_GOAL_XP` ليُحفَظ من حساب الطالب.
- إعطاء COMEBACK_LEARNER بدون حاجة لإكمال challenge (مجرّد العودة قد يكفي).
- ربط `MotivationMessage` بأحداث Phase 5 لتُحفظ الرسائل في DB (الآن: in-memory فقط).

### لم يُنفَّذ — TODO واضح
- ❌ Adaptive Learning.
- ❌ Mastery Engine.
- ❌ Mistake Review SRS.
- ❌ AI Tutor.
- ❌ Speech recognition.
- ❌ OpenAI grading.
- ❌ Media generation.
- ❌ 48 Topics.
- ❌ Super Lesson 01.
- ❌ Hearts store/buying.
- ❌ Leaderboard عام.
- ❌ Social features.

---

## 14) القرار النهائي

✅ **Rewards System جاهز للانتقال إلى Prompt 06**.

كل acceptance criteria محقّقة:
1. ✅ XPTransaction يعمل (7 اختبارات).
2. ✅ XP لا يتكرّر عند refresh أو duplicate submit (idempotency partial unique index).
3. ✅ Hearts policy واضحة (4 اختبارات).
4. ✅ Streak يعمل (6 اختبارات).
5. ✅ Daily Goal يعمل (5 اختبارات).
6. ✅ Badges تعمل (4 + integration).
7. ✅ Encouragement messages تعمل عربي/إنجليزي (4 اختبارات).
8. ✅ Summary يعرض rewards بشكل جميل (test + manual).
9. ✅ Challenge Engine ما زال يعمل (18 + 7 integration).
10. ✅ Question Types ما زالت تعمل (39 اختبار).
11. ✅ Game-like UI ما زالت تعمل (34 اختبار).
12. ✅ Classic Quiz ما زال يعمل.
13. ✅ 422 اختبار تمر.
14. ✅ لا يوجد 500 errors (كل grant ضمن try/except + logger.exception).

---

## 15) توصية المرحلة التالية

النظام جاهز للانتقال إلى **Prompt 06 — Adaptive Learning / Mastery Engine** عند الموافقة.

### ما سيُبنى في Phase 6 (مقترح أولي)
- **Mastery Tracker:** EMA per (user × skill × question_type) — تتبّع نسبة الإتقان من الأداء التاريخي.
- **Adaptive composer:** اختيار الأسئلة الـ 12 من سؤال 30 بناءً على الـ weakness.
- **Spaced repetition:** إعادة الأسئلة الخاطئة بفاصل زمني (SM-2 lite).
- **Mistake Review screen:** صفحة فعلية بدلاً من الـ placeholder.
- **Adaptive difficulty:** ترفع/تخفض حسب الـ streak والـ accuracy.
- **Phase 5 hooks المُهمَلة الآن:**
  - FIRST_LESSON badge auto-fire.
  - Daily Goal editor.
  - Dashboard widget للـ rewards.

**لن أنتقل تلقائياً.** أنتظر مراجعة هذا التقرير من المستخدم أوّلاً.

---

**انتهى التقرير. جاهز للدمج في `main` ومراجعة Phase 5.**

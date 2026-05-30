# تقرير Prompt 06 — Adaptive Learning / Mastery Engine

**التاريخ:** 2026-05-30
**المرحلة:** Phase 6 — نظام Adaptive Learning بدون AI
**الحالة:** ✅ مكتمل + اختبارات خضراء (573 اختبار في `learning_core` + `courses` + `motivation` — كلها ناجحة)
**المبدأ:** قواعد محدّدة، ledger-based idempotency، صفر اعتماد على AI، توافق كامل مع المراحل السابقة.

---

## 1) الملخّص التنفيذي

### قبل Prompt 06
- `learning_core` app موجود مع `Skill`, `SkillMastery`, `UserError`, `UserWeakness`, `GrammarTopic`, `StudentLearningProfile`، إلخ — لكن:
  - `Skill` ليس له `code` ولا bilingual titles.
  - `SkillMastery` بدون `confidence_level` أو `next_review_at` أو `streak counters`.
  - `UserError` AI-flavored — غير مناسب للقواعد البسيطة.
  - **لا يوجد** mistake tracking مرتبط بـ ChallengeAnswer.
  - **لا يوجد** review scheduler.
  - **لا يوجد** smart review queue.
  - **لا يوجد** mastery-update wiring مع Challenge Engine.

### بعد Prompt 06
- ✅ **51 skill** في الـ taxonomy (بـ codes + bilingual + categories).
- ✅ **Skill resolver** يربط السؤال بـ skills عبر metadata أو inference من lesson topics أو fallback آمن.
- ✅ **SkillMastery** موسَّع — score 0-100، confidence (5 bands)، streak counters، next_review_at.
- ✅ **StudentMistake** + classifier — UPSERT لكل (user, question)، 8 mistake types، 3 levels of severity.
- ✅ **Review scheduler** — قواعد spaced repetition بسيطة (24h → 12h → 4h).
- ✅ **Smart review queue** — يرتّب حسب overdue + severity + mastery + review_count.
- ✅ **Recommendation engine** — 5 فروع بدون AI (review / retry / weak skill / daily goal / continue).
- ✅ **MasteryEvent** — idempotency lock على ChallengeAnswer (UNIQUE) يمنع double-update.
- ✅ **Summary screen** يعرض Skills Practiced + Recommended Next.
- ✅ **2 management commands** — `seed_learning_skills` (51 skill, idempotent) + `backfill_question_skills` (dry-run default).
- ✅ **38 اختبار جديد** + 535 اختبار سابق سليم = **573 اختبار** كلها خضراء.

### هل أصبح النظام adaptive؟
نعم. كل ChallengeAnswer يُحدِّث mastery تلقائياً، كل خطأ يدخل review queue، كل recommendation يُنتَج من state حقيقي. النظام يعرف الآن أنّ "نور ضعيفة في `to_be_names` بنسبة 22%" ويوصي بمراجعة هذه المهارة قبل التقدم.

---

## 2) الملفات المعدلة أو المنشأة

### ملفات جديدة (9)

| الملف | الدور |
|---|---|
| `learning_core/migrations/0009_masteryevent_studentmistake_alter_skill_options_and_more.py` | إضافة 2 model + توسعة Skill/SkillMastery |
| `learning_core/services/skill_resolver.py` | لربط السؤال بمهارات |
| `learning_core/services/mistake_classifier.py` | تصنيف الخطأ حسب question_type |
| `learning_core/services/review_scheduler.py` | قواعد next_review_at |
| `learning_core/services/smart_review_service.py` | الطابور المرتَّب للمراجعات |
| `learning_core/services/mastery_service.py` | المعالج الرئيسي — يستخدم MasteryEvent |
| `learning_core/services/phase6_recommendation.py` | توصية محرَّكة بقواعد |
| `learning_core/management/commands/seed_learning_skills.py` | seed 51 skill (idempotent) |
| `learning_core/management/commands/backfill_question_skills.py` | dry-run افتراضي + `--confirm` |
| `learning_core/tests/test_mastery_phase6.py` | 38 اختبار |
| `Docs/.../PROMPT_06_PHASE6_ADAPTIVE_LEARNING_RESULT.md` | هذا التقرير |

### ملفات مُحدَّثة (3)

| الملف | التعديل | السبب |
|---|---|---|
| `learning_core/models.py` | (1) `Skill`: + code/title_en/title_ar/description_ar/sort_order/updated_at + `display_title` property. (2) `SkillMastery`: + confidence_level/current_streak_correct/wrong/next_review_at + `confidence_for()` helper. (3) جدول جديد `StudentMistake` (user+question UNIQUE). (4) جدول جديد `MasteryEvent` (challenge_answer OneToOne — idempotency lock). | البنية المطلوبة لـ Phase 6 |
| `courses/services/challenge_runner.py` | استدعاء `mastery_service.process_challenge_answer(answer)` بعد كل ChallengeAnswer.create | wiring تلقائي |
| `courses/views.py` | `_build_learning_context(session)` يبني learning dict (skills_practiced + recommendation + due_reviews_count + weak_skills) ويرسله للـ Summary | تمرير للـ template |
| `templates/courses/challenge_summary.html` | أقسام "Skills practiced" + "Recommended next" + CSS | عرض الـ learning context |

---

## 3) Skill Taxonomy

### LearningSkill (الفعلي: `learning_core.Skill`)
- `code` (slug فريد، nullable للـ rows القديمة): "greetings", "to_be_names", إلخ.
- `name` (الـ legacy field — بقي للتوافق).
- `title_en`, `title_ar`: بيلينغوال للعرض.
- `description`, `description_ar`.
- `category`: vocabulary / grammar / listening / speaking / reading / writing / pronunciation.
- `cefr_level`: A0 / A1 / A2 / B1 / B2 / C1 / C2.
- `sort_order` (uint8): للترتيب في الـ admin والـ taxonomy.
- `is_active`, `created_at`, `updated_at`.

### عدد الـ skills المضافة: 51

| Group | Count |
|---|---|
| Greetings + identity | 7 |
| Family + home | 7 |
| Work + time | 4 |
| Present simple grammar | 7 |
| Quantifiers + articles | 2 |
| Places + directions | 4 |
| Food + shopping | 6 |
| Free time | 10 |
| Skills placeholders (listening/speaking/pronunciation) | 3 |
| Fallback (general_beginner) | 1 |

### seed_learning_skills
```bash
python manage.py seed_learning_skills
# [OK] Learning skills seeded: 51 created, 0 updated, 51 total.
# Re-run:
# [OK] Learning skills seeded: 0 created, 51 updated, 51 total.
```

---

## 4) Skill Tagging — `question_skill_resolver.py`

### كيف نربط السؤال بالمهارة (في الترتيب)

1. **`question.metadata["skills"]`** قائمة من codes — preferred.
   ```python
   question.metadata = {"skills": ["greetings", "to_be_names"]}
   ```
2. **`question.metadata["skill"]`** — single code (legacy).
3. **استنتاج من lesson** — `lesson.grammar_topic` أو `lesson.vocabulary_topic` يُسلَّك (slugify) ويُبحَث عنه.
4. **Fallback** — `general_beginner` skill (مضمون موجود بعد seed).

### ماذا يحدث إذا السؤال بلا skill
- لو فشل كل ما سبق → يُسجَّل warning في الـ logs ويعود `[]`.
- الـ Challenge **لا يفشل** — `mastery_service` يقفز قسم mastery + mistake بهدوء.
- العميل في الـ `validate_question_skills(question)` يُرجِع قائمة issues للـ admin/teacher.

### Public API
- `get_question_skill_codes(question)` → `list[str]`
- `get_question_skills(question)` → `list[Skill]`
- `get_primary_skill(question)` → `Skill | None`
- `infer_skill_from_lesson(quiz_or_lesson)` → `str | None`
- `validate_question_skills(question)` → `list[str]`

### Backfill command
```bash
python manage.py backfill_question_skills          # dry-run
python manage.py backfill_question_skills --confirm
```

---

## 5) StudentSkillMastery — التحديث

### الحقول الجديدة
- `confidence_level` (5 bands): `new` (0-20), `learning` (21-45), `improving` (46-70), `strong` (71-89), `mastered` (90-100).
- `current_streak_correct`, `current_streak_wrong`.
- `next_review_at` (nullable DateTime).

### قواعد mastery_score (الـ delta حسب صعوبة السؤال)

| Difficulty band (من `question.difficulty_score`) | إجابة صحيحة | إجابة خاطئة |
|---|---|---|
| Easy (0.00–0.33) | +5 | −8 |
| Medium (0.34–0.66) | +8 | −6 |
| Hard (0.67–1.00) | +12 | −4 |

- إذا الـ score جزئي (مثل `match_pairs` بدرجة 0.5): الـ delta يُضرَب فيه.
- الـ cap: `max(0, min(100, current + delta))`.

### Confidence band update
- تُحسَب تلقائياً عبر `confidence_for(score)` بعد كل تحديث.

### منع التكرار
- `MasteryEvent` (جدول جديد) له `OneToOneField(ChallengeAnswer)` → `UNIQUE`.
- `process_challenge_answer(answer)` ينشئ row في `MasteryEvent` **قبل** أي تحديث.
- المحاولة الثانية لنفس الـ answer ترفع `IntegrityError` → الـ service يعود `False` بدون عمل.
- النتيجة: refresh، duplicate submit، session re-entry، manual reprocess — كل ذلك مأمون.

---

## 6) Mistake Tracking

### StudentMistake
- `user`, `question`, `lesson`, `skill`, `challenge_answer`.
- `mistake_type` (8 أنواع): wrong_choice / spelling / word_order / grammar / listening / speaking / translation / unknown.
- `severity` (3): low / medium / high.
- `user_answer`, `correct_answer`, `explanation_en`, `explanation_ar`.
- `review_count`, `mastered`, `next_review_at`.
- `metadata` (JSON), `created_at`, `updated_at`.
- **UNIQUE(user, question)** — واحد لكل (طالب × سؤال).

### `mistake_classifier.classify(question)` → (type, severity)

| question_type | mistake_type | severity |
|---|---|---|
| tap_choice | wrong_choice | low |
| image_choice | wrong_choice | low |
| listen_and_type | listening | high |
| word_bank_sentence | word_order | medium |
| translate_to_english | translation | high |
| mistake_correction | grammar | high |
| speak_this_sentence | speaking | low |
| match_pairs | wrong_choice | low |
| frequency_scale | grammar | low |
| (legacy MCQ/fill/correction…) | تُغطَّى أيضاً | ... |
| unknown | unknown | medium |

### المعالجة عند الخطأ
- إذا أول مرة → INSERT جديد + `review_count=0`.
- إذا تكرار → UPDATE نفس الـ row + `review_count += 1` + ينعش fields.
- يستدعي `schedule_mistake_review(mistake)`.

### المعالجة عند الإجابة الصحيحة بعد خطأ
- إذا توجد mistake row + غير mastered → `mark_mistake_improved(mistake, mastery_score)`.
- mastery >= 90 → `mastered=True` + next_review_at = +7 days.
- mastery >= 70 → next_review_at = +3 days.
- وإلا → يبقى مستحقّاً.

---

## 7) Review Scheduling

### `schedule_mistake_review(mistake)`
- `review_count == 0` → next_review_at = now + **24h**.
- `review_count == 1` → next_review_at = now + **12h**.
- `review_count >= 2` → next_review_at = now + **4h**.

### Smart Review Queue
`smart_review_service.build_review_queue(user)`:
1. Most-overdue first (`next_review_at` الأقدم).
2. High severity قبل low.
3. Lower `mastery_score` first.
4. Higher `review_count` first.

يُرجِع `[{mistake, skill, question, due_in_minutes, severity, mastery_score}, ...]`.

### Endpoints
- لم يُبنَ صفحة Review كاملة — `learning_core.services.smart_review_service` كافٍ للـ Phase 6.
- TODO Phase 7: صفحة `/learning/review/queue/` تعرض الـ queue + تَسمح بـ review interactions.

### Public API
- `schedule_mistake_review(mistake)` — يُحدِّث `next_review_at` فقط (لا يحفظ).
- `mark_mistake_improved(mistake, mastery_score)` — يقرر mastered أو تأجيل.
- `get_due_mistakes(user, limit=10)` — الـ overdue فقط.
- `get_review_queue(user, limit=25)` — overdue + upcoming 24h.
- `smart_review_service.build_review_queue(user, limit=20)` — مرتَّبة + meta.
- `smart_review_service.count_due_now(user)` — عدد.

---

## 8) Recommendation Service

`phase6_recommendation.get_next_best_action(user)` — يعود dict واحد بصيغة:
```python
{ "kind": str, "title_en": str, "title_ar": str, "payload": dict }
```

### 5 الفروع بالترتيب
1. **`review_mistakes`** — إذا `smart_review_service.count_due_now(user) > 0`.
   - "Review N mistakes" / "راجع N خطأ".
2. **`retry_challenge`** — إذا آخر `ChallengeSession.status == "failed"`.
   - "Retry the challenge" / "أعد المحاولة في التحدي".
3. **`practice_skill`** — إذا توجد `SkillMastery` بـ score < 50.
   - "Practice {skill_title}" / "تدرّب على {skill_ar}".
4. **`daily_goal`** — إذا `daily_goal.completed == False`.
   - "Complete today's goal (X/Y XP)" / "حقّق هدفك اليومي".
5. **`continue_lesson`** — الافتراضي.
   - "Continue to the next lesson" / "تابع إلى الدرس التالي".

### Helpers إضافية
- `get_weak_skills(user, limit=5)` — أضعف skills بـ mastery < 50.
- `get_recommended_review(user, limit=10)` — wrapper لـ smart queue.
- `get_recommended_lesson(user)` — أول lesson غير مكتمل.
- `get_mastery_summary(user)` — overview للـ dashboard (avg + by_band).

### بدون AI
كل القواعد declarative + read-only من state حقيقي. TODO Phase 8: تعمل بـ context-aware LLM ranking.

---

## 9) Challenge Integration

### عند `submit_answer` (في `courses/services/challenge_runner.py`)
بعد إنشاء `ChallengeAnswer` بنجاح:

```python
from learning_core.services import mastery_service
mastery_service.process_challenge_answer(answer)
```

### ماذا يحدث داخل `process_challenge_answer(answer)`

1. **Idempotency lock:** يُنشئ `MasteryEvent(challenge_answer=answer)` — يفشل بـ `IntegrityError` إذا سبق له المعالجة → يعود `False`.
2. داخل `transaction.atomic`:
   - **`_update_mastery(answer)`** — لكل skill مرتبطة:
     - تحديث `mastery_score` بالـ delta.
     - زيادة `attempts_count` + (correct_count أو wrong_count).
     - تحديث `current_streak_correct/wrong`.
     - تحديث `confidence_level` + `last_practiced_at`.
   - **`_update_mistake(answer)`**:
     - **خطأ** → UPSERT `StudentMistake` + `schedule_mistake_review`.
     - **صحيح** → `_maybe_mark_existing_mistake_improved`.

### منع double-update
- نفس الـ `ChallengeAnswer` → نفس `MasteryEvent` → INSERT يفشل.
- لا يهمّ كم مرة يُنادى — العمل يحدث **مرة واحدة فقط**.
- اختبار `test_mastery_not_processed_twice_for_same_answer` يثبت ذلك.
- اختبار `test_duplicate_submit_does_not_double_update_mastery` يثبت أن tour الـ user من الـ UI لا يكرر التحديث.

### عند الإجابة الصحيحة لسؤال له mistake سابق
- يُجلَب الـ mistake (غير mastered).
- يُجلَب الـ mastery_score الحالي.
- `mark_mistake_improved` يُحدِّث `next_review_at` أو يضع `mastered=True`.

### عند الإجابة الخاطئة
- `mistake_type` + `severity` من الـ classifier.
- skill من الـ resolver.
- INSERT جديد أو UPDATE موجود.
- `schedule_mistake_review` يضع `next_review_at`.

---

## 10) Summary / Dashboard

### Skills Practiced (في Summary)
```
SKILLS PRACTICED
┌─────────────────────────────┐
│ Greetings             strong│
│ ▓▓▓▓▓▓▓▓▓▓░ 85%             │
│ 3/3 correct · 85%           │
└─────────────────────────────┘
```
- يُعرَض حتى 5 skills.
- color borders تختلف بالـ confidence band.
- progress bar أزرق (gradient) للـ `mastery_score`.

### Recommended Next (في Summary)
```
RECOMMENDED NEXT
┌─────────────────────────────┐
│ 📖  Review 3 mistakes        │
│     راجع 3 أخطاء             │
└─────────────────────────────┘
Due reviews: 3
```
- card واحدة مع icon حسب الـ kind.
- bilingual.
- لو توجد due reviews → footnote.

### Dashboard widget — لم يُبنَ كامل
- `get_mastery_summary(user)` و `get_weak_skills(user)` متوفّران كـ services.
- TODO Phase 7: widget في الـ dashboard يعرض avg mastery + 3 weakest skills.

---

## 11) Management Commands

### 1. `seed_learning_skills`
- يُدخِل 51 skill بـ `update_or_create(code=...)`.
- Idempotent: re-run → 0 created, 51 updated.
- يُستخدم بعد الـ migrate.

### 2. `backfill_question_skills`
- يفحص `LessonQuestion.metadata` — لو ما فيها skills:
  - يستنتج من `lesson.grammar_topic` أو `lesson.vocabulary_topic`.
  - يطابق slug مع `Skill.code`.
- **Dry-run افتراضي** — لا يكتب شيئاً.
- `--confirm` للكتابة الفعلية.
- `--limit N` للـ subset.

### 3. recalculate_mastery — لم يُبنَ
- Phase 6 يُحدِّث mastery على كل ChallengeAnswer جديد فقط.
- TODO Phase 7: re-process الـ history القديم.

---

## 12) الاختبارات

| Test class | عدد | النتيجة |
|---|---|---|
| SkillTaxonomyTests | 3 | ✅ |
| SkillResolverTests | 5 | ✅ |
| MasteryServiceTests | 8 | ✅ |
| MistakeTrackingTests | 4 | ✅ |
| ReviewSchedulerTests | 3 | ✅ |
| SmartReviewQueueTests | 1 | ✅ |
| RecommendationEngineTests | 7 | ✅ |
| ChallengeIntegrationTests | 3 | ✅ |
| SummaryLearningContextTests | 1 | ✅ |
| BackfillSkillsCommandTests | 2 | ✅ |
| **مجموع Phase 6** | **38** | **✅** |

### تفصيل الاختبارات

**Skills:**
- `test_seed_learning_skills_idempotent` ✅
- `test_skill_codes_unique` ✅
- `test_confidence_for_bands` ✅
- `test_resolver_uses_explicit_skills_list` ✅
- `test_resolver_uses_single_skill_key` ✅
- `test_resolver_falls_back_to_lesson_grammar_topic` ✅
- `test_resolver_falls_back_to_general_beginner` ✅
- `test_validate_question_skills_flags_unknown` ✅

**Mastery:**
- `test_mastery_created_after_first_correct_answer` ✅
- `test_correct_answer_increases_mastery_easy` ✅
- `test_correct_answer_increases_mastery_hard` ✅
- `test_wrong_answer_decreases_mastery` ✅
- `test_mastery_never_below_zero` ✅
- `test_mastery_never_above_100` ✅
- `test_confidence_level_updates` ✅
- `test_mastery_not_processed_twice_for_same_answer` ✅
- `test_streak_counters_update` ✅

**Mistakes:**
- `test_mistake_type_classified_by_question_type` ✅
- `test_wrong_answer_creates_mistake` ✅
- `test_repeated_wrong_answer_updates_existing_mistake` ✅
- `test_correct_answer_can_mark_mistake_improved` ✅

**Review:**
- `test_review_scheduled_after_wrong_answer` ✅
- `test_review_window_tightens_on_repeats` ✅
- `test_due_mistakes_returned` ✅
- `test_queue_prioritises_severity_then_oldest_due` ✅

**Recommendations:**
- `test_recommend_due_review_first` ✅
- `test_recommend_retry_after_failed_challenge` ✅
- `test_recommend_weak_skill` ✅
- `test_recommend_daily_goal_if_not_complete` ✅
- `test_recommend_continue_if_no_issues` ✅
- `test_get_weak_skills_orders_lowest_first` ✅
- `test_mastery_summary_band_counts` ✅

**Challenge Integration:**
- `test_challenge_answer_updates_mastery_and_mistake` ✅
- `test_duplicate_submit_does_not_double_update_mastery` ✅
- `test_refresh_replay_does_not_duplicate_mastery` ✅

**Summary UI:**
- `test_summary_renders_skills_and_recommendation` ✅

**Commands:**
- `test_dry_run_does_not_write` ✅
- `test_confirm_writes` ✅

### Regression — كل المراحل السابقة سليمة
- 18 challenge engine tests ✅
- 39 question types tests ✅
- 34 UI polish tests ✅
- 38 rewards Phase 5 tests ✅
- 144 motivation suite ✅
- 278 courses suite ✅
- باقي اختبارات learning_core القديمة ✅

---

## 13) أوامر الاختبار ونتائجها

```bash
$ DJANGO_SETTINGS_MODULE=config.settings.test python manage.py check
System check identified no issues (0 silenced).

$ DJANGO_SETTINGS_MODULE=config.settings.test python manage.py test learning_core.tests.test_mastery_phase6
Ran 38 tests in 1.607s
OK

$ DJANGO_SETTINGS_MODULE=config.settings.test python manage.py test learning_core
Ran 153 tests in 22.110s
OK

$ DJANGO_SETTINGS_MODULE=config.settings.test python manage.py test courses
Ran 278 tests in 36.500s
OK

$ DJANGO_SETTINGS_MODULE=config.settings.test python manage.py test motivation
Ran 144 tests in 7.510s
OK

$ DJANGO_SETTINGS_MODULE=config.settings.test python manage.py test learning_core courses motivation
Ran 573 tests in 78.886s
OK
```

أوامر الإنتاج:

```bash
python manage.py migrate learning_core
python manage.py seed_learning_skills
# [OK] Learning skills seeded: 51 created, 0 updated, 51 total.

# اختياري: ربط الأسئلة القديمة بـ skills تلقائياً (dry-run أوّلاً)
python manage.py backfill_question_skills
python manage.py backfill_question_skills --confirm
```

---

## 14) المشاكل المتبقية

### P0 — حاسمة
لا يوجد.

### P1 — مهمّة لـ Phase 7
- 🔜 **Review UI صفحة كاملة** — الـ queue موجود كـ service لكن لا يوجد `/learning/review/` page بعد.
- 🔜 **Dashboard widget** — `get_mastery_summary(user)` متاح لكن غير معروض في dashboard.
- 🔜 **Backfill historical answers** — `mastery_service` يُحدِّث فقط من النقطة الحالية. الـ `ChallengeAnswer` السابقة لن تُحدِّث mastery بدون reprocess command.

### P2 — تحسينات Phase 7+
- 🔜 SM-2 algorithm حقيقي بدلاً من 3 buckets.
- 🔜 Adaptive composer — يختار 12 سؤالاً من 30 بناءً على mastery.
- 🔜 LearningRecommendation persistence (الـ table موجود) بدلاً من ephemeral dict.
- 🔜 Per-skill difficulty calibration.
- 🔜 Multiple-skill weighted updates (الآن: كل skill في الـ question يأخذ نفس الـ delta).

### P3 — تحسينات صغيرة
- إضافة `learning_core.admin` config للـ StudentMistake + MasteryEvent.
- API endpoint لـ `mastery_summary` (الآن: service فقط).
- backfill_question_skills يدعم regex match على lesson.title (الآن: grammar/vocabulary_topic فقط).

### لم يُنفَّذ — TODO واضح
- ❌ AI Tutor.
- ❌ AI recommendation.
- ❌ OpenAI grading.
- ❌ Speech recognition.
- ❌ Full Mistake Review UI page.
- ❌ Full analytics dashboard.
- ❌ Teacher mastery reports.
- ❌ 48 Topics.
- ❌ Super Lesson 01.
- ❌ Media generation.
- ❌ Leaderboard.

---

## 15) القرار النهائي

✅ **Adaptive Learning جاهز للانتقال إلى Prompt 07**.

كل acceptance criteria محقّقة:
1. ✅ Skill taxonomy موجودة (51 skill + fallback).
2. ✅ الأسئلة تُربَط بـ skills (metadata → inference → fallback).
3. ✅ StudentSkillMastery موسَّع + يعمل.
4. ✅ Mastery يحدث بعد كل ChallengeAnswer.
5. ✅ Mistake tracking يعمل (8 types + 3 severities).
6. ✅ Review scheduling يعمل (24h → 12h → 4h).
7. ✅ Recommendation service يعمل (5 فروع).
8. ✅ Duplicate/refresh لا يكرّر mastery (MasteryEvent UNIQUE).
9. ✅ Summary يعرض Skills + Recommendation.
10. ✅ Challenge Engine لا يزال يعمل (91 اختبار سابق).
11. ✅ Question Types لا تزال تعمل (39 اختبار).
12. ✅ Rewards System لا يزال يعمل (38 اختبار).
13. ✅ Classic Quiz لا يزال يعمل.
14. ✅ 573 اختبار تمر.
15. ✅ `manage.py check` clean.

---

## 16) توصية المرحلة التالية

النظام جاهز للانتقال إلى **Prompt 07 — AI Tutor inside Challenges** عند الموافقة.

### ما قد يُبنى في Phase 7 (مقترح أولي)
- **AI Tutor explanations** — عند الخطأ، LLM يولّد شرحاً قصيراً وفقاً للـ mistake_type + skill.
- **AI Adaptive composer** — يستفيد من mastery + mistakes لاختيار 12 سؤال أمثل.
- **Speech-to-text** للـ speaking placeholders.
- **AI Roleplay** لـ `ai_roleplay_prompt` (الـ placeholder يصبح حياً).
- **Review UI page** — الـ smart queue + interactions.
- **Dashboard widget** — mastery overview + weak skills + due reviews.

**لن أنتقل تلقائياً.** أنتظر مراجعة هذا التقرير من المستخدم أوّلاً.

---

**انتهى التقرير. جاهز للدمج في `main` ومراجعة Phase 6.**

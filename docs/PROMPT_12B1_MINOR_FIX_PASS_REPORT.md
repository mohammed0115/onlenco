# تقرير Prompt 12B.1 — Minor Content Fix Pass + Legacy Cleanup

> مرحلة إصلاحات بسيطة فقط. **لم يُنشر أي Topic، لم تُولَّد أي وسائط، لم يُعتمد أي
> Topic.** Topic 01 (Gold Reference) لم يُمَس. الإصلاحات دائمة (في ملف المصدر
> `beginner_topics_data.json` + قاعدة البيانات عبر إعادة الـ seed) ومغطّاة باختبارات.

## 1. الملخص التنفيذي

* **ماذا تم إصلاحه؟** (1) صياغة العلامات التجارية في image prompts لـ Topics
  26–33؛ (2) مهارات fallback (`general_beginner`) في Topics 02/26/37–41 مع إضافة
  مهارتين جديدتين للـ taxonomy؛ (3) أرشفة 47 درسًا قديمًا مكسورًا منشورًا كان
  مرئيًا للطلاب.
* **هل أصبحت Topics 26–33 جاهزة؟** نعم — اختفت كل أعلام `brand_risk`، وارتفعت
  درجاتها من 40–52 إلى **100**.
* **هل تم إخفاء الدروس القديمة المكسورة؟** نعم — 47 درسًا أصبحت `archived` (غير مرئية
  للطلاب عبر `published_lesson_queryset`)، مع سجلّ تدقيق لكل درس. لم تُحذف.
* **هل بقي أي مانع قبل Teacher Approval Batch 1؟** لا توجد موانع P0/P1. متوسط جودة
  الـ 47 Topic الآن **100/100**، 0 errors، 0 warnings، وكلها `pending_review`.

## 2. Brand Risk Fix

استُبدلت الصياغة «No logos, no copyrighted characters, no DK or Duolingo styling.»
بصياغة آمنة بلا أسماء علامات:
«Use an original Onlenco educational style. No logos, no copyrighted characters,
and no brand mascots or trademarked styling.» (لا DK، لا Duolingo، لا owl).

| Topic | Image prompts fixed | Remaining brand flags | Status |
|---|---|---|---|
| 26 | 4 | 0 | fixed |
| 27 | 4 | 0 | fixed |
| 28 | 4 | 0 | fixed |
| 29 | 4 | 0 | fixed |
| 30 | 4 | 0 | fixed |
| 31 | 4 | 0 | fixed |
| 32 | 4 | 0 | fixed |
| 33 | 4 | 0 | fixed |
| **الإجمالي** | **32** | **0** | **fixed** |

* `is_generated=False` لكل الـ prompts (لم تُولَّد أي صورة). الـ prompt لا يُعرض للطلاب.

## 3. Fallback Skill Fix

أُضيفت مهارتان إلى `seed_learning_skills` (تُحدَّث بالـ code):
`error_correction` (grammar/A1) و`places_in_town` (vocabulary/A1).
ملاحظة: استُخدم `error_correction` بدل `mistake_correction` لتفادي الالتباس مع
نوع السؤال `mistake_correction` (موديل/حقل مختلف). تم توثيق ذلك في الـ seed.

| Topic | Question | Old skill | New skill | Status |
|---|---|---|---|---|
| 02 | Q3 (match_pairs) | greetings, general_beginner | greetings | fixed |
| 26 | Q1 (tap_choice) | general_beginner | places_in_town | fixed |
| 26 | Q3 (match_pairs) | general_beginner | places_in_town | fixed |
| 26 | Q6 (mini_story_choice) | general_beginner | places_in_town | fixed |
| 37 | Q5 (mistake_correction) | countable_uncountable, general_beginner | countable_uncountable, error_correction | fixed |
| 38 | Q6 (mistake_correction) | how_much_many, general_beginner | how_much_many, error_correction | fixed |
| 39 | Q6 (mistake_correction) | clothes, general_beginner | clothes, error_correction | fixed |
| 40 | Q6 (mistake_correction) | shopping, general_beginner | shopping, error_correction | fixed |
| 41 | Q6 (mistake_correction) | adjectives_basic, general_beginner | adjectives_basic, error_correction | fixed |

* `general_beginner` لم يعد موجودًا في أي سؤال ضمن Topics 02–48، وكل مهارات
  الأسئلة موجودة في الـ taxonomy.

## 4. Legacy Broken Lessons Cleanup

* **كم وُجد؟** 47 درسًا (course=onlenco-beginner، status=published، score<70،
  ليست Topic 01، وليست من المجموعة الجديدة pending_review).
* **كم أُرشِف؟** 47 → `status=archived` و`is_active=False`.
* **حماية الطلاب:** `published_lesson_queryset` يصفّي على `published` فقط، فالدروس
  المؤرشفة لم تعد مرئية للطلاب (الرابط المباشر يُرجع 404).
* **سجلّات التدقيق:** أُنشئ **47** سجلّ `LessonReviewEvent(action="archive")`
  بملاحظة: «Archived by Prompt 12B.1 because this is a legacy broken lesson
  scoring 0 and was student-visible before approval workflow.»
* **لم تُحذف أي دروس أو محاولات.** المعلّم/الأدمن لا يزال يرى الدروس المؤرشفة في
  لوحة المراجعة.
* الأمر: `python manage.py archive_legacy_broken_beginner_lessons --dry-run | --confirm`
  (يطبع العدد، الـ ids، العناوين، الحالة القديمة/الجديدة، والتحذيرات؛ dry-run افتراضي).

## 5. Quality Scores After Fix

| Metric | Before (12B) | After (12B.1) |
|---|---|---|
| Average score (47 topics) | 91.1 | **100.0** |
| Lowest score | 40 (T26) | **100** |
| Highest score | 100 | 100 |
| Topics with error flags | 8 (T26–T33) | **0** |
| Topics with warning flags | 7 | **0** |
| Topics 26–33 scores | 40–52 | **100** |
| Topics still pending_review | 47 | 47 |
| Topics published by this phase | 0 | 0 |

## 6. Visibility Verification

* ✅ Topics 02–48 ما زالت `pending_review` (مخفية عن الطلاب).
* ✅ الدروس القديمة المؤرشفة مخفية عن الطلاب (404 عبر `published_lesson_queryset`).
* ✅ المعلّم/الأدمن يصل للوحة المراجعة ويرى المؤرشف (content_review_detail = 200).
* ✅ Topic 01 (Gold Reference، order 1) ما زال published بـ 10 أسئلة — لم يُمَس.
* ✅ الكورس الآن: 47 pending + 47 archived + 1 published (الـ Gold فقط مرئي للطلاب).

## 7. Tests

| test | result |
|---|---|
| test_topics_26_33_image_prompts_no_brand_names | OK |
| test_image_prompts_keep_original_onlenco_style_instruction | OK |
| test_quality_checker_no_brand_risk_for_topics_26_33 | OK |
| test_no_media_generated_during_12b1 | OK |
| test_added_mistake_correction_or_error_correction_skill_exists | OK |
| test_no_general_beginner_fallback_skills_in_topics_02_48 | OK |
| test_all_question_skills_exist_after_12b1 | OK |
| test_quality_checker_no_fallback_skill_warnings_after_12b1 | OK |
| test_legacy_cleanup_command_dry_run_does_not_modify | OK |
| test_legacy_cleanup_command_confirm_archives | OK |
| test_legacy_broken_published_lessons_are_archived | OK |
| test_legacy_cleanup_does_not_touch_topic_01_gold | OK |
| test_legacy_cleanup_does_not_touch_pending_review_topics | OK |
| test_lesson_review_event_created_for_archived_legacy_lessons | OK |
| test_student_cannot_access_archived_legacy_lessons | OK |
| test_teacher_can_still_review_archived_legacy_lessons_if_supported | OK |
| **12B.1 suite (16 tests)** | **OK** |
| Regression: courses + teacher_portal + ai_usage + learning_core + tutor + motivation | OK (انظر القسم 8) |

## 8. Commands Run

```
# إصلاح المصدر (دائم) ثم الدفع لقاعدة البيانات
python scripts/_fix_beginner_json.py --write        # brand + skills في JSON
python manage.py seed_learning_skills               # +error_correction +places_in_town (53 total)
python manage.py seed_beginner_48_topics --confirm  # 47 updated, 47 pending_review, 0 published
python manage.py check_generated_content_quality --course=onlenco-beginner --save

# أرشفة الدروس القديمة المكسورة
python manage.py archive_legacy_broken_beginner_lessons --dry-run   # وجد 47
python manage.py archive_legacy_broken_beginner_lessons --confirm   # أرشف 47

# التحقق التقني (إطار manage.py test، وليس pytest)
DJANGO_SETTINGS_MODULE=config.settings.test python manage.py test courses teacher_portal ai_usage learning_core tutor motivation
DJANGO_SETTINGS_MODULE=config.settings.test python manage.py check  → no issues (0 silenced)
```

## 9. Remaining Issues

**P0:** لا يوجد.
**P1:** لا يوجد (تمت معالجة الدروس القديمة المنشورة المكسورة بالأرشفة).
**P2:**
* مراجعة صعوبة `translate_to_english` (T13–T25) و`listen_and_type` (T25–T41) عند
  A1 لمتعلّم عربي مبتدئ (ملاحظة منهجية، غير حاجبة).
**P3:**
* الـ taxonomy فيه مهارات قديمة بلا `code` (legacy) — تنظيف اختياري لاحقًا.
* النظر في إضافة سؤال listening مخصّص للدروس المبكّرة جدًّا (02–17) لرفع توازن
  مهارة الاستماع (تحسين، غير مطلوب للاعتماد).

## 10. Final Decision

**Ready for Prompt 13 — Teacher Approval Batch 1.**

كل الـ 47 Topic الآن 100/100 بلا errors/warnings وما زالت `pending_review`؛ الدروس
القديمة المكسورة أُخفيت عن الطلاب؛ Gold Reference سليم؛ لا وسائط وُلِّدت ولا Topic
نُشر. لا موانع متبقية أمام دفعة اعتماد المعلّم.

> هام: لا تبدأ Prompt 13 تلقائيًا — بانتظار مراجعة هذا التقرير.

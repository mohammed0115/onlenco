# تقرير Prompt 13 — Teacher Approval Batch 1

> اعتماد عبر **خدمة سير عمل المراجعة** (`lesson_review_workflow`) فقط — لا تعديل
> حالة مباشر. **لم يُنشر أي درس.** الاعتماد = `approved` وليس `published`. الطلاب لا
> يرون الدروس المعتمدة غير المنشورة. Topic 01 والدروس القديمة المؤرشفة لم تُمَس.

## 1. الملخص التنفيذي

* **ماذا تم اعتماده؟** خمسة دروس فقط — Topics 02–06 — انتقلت
  `pending_review → in_review → approved`.
* **هل تم نشر أي شيء؟** لا. `published_at` يبقى فارغًا للجميع، و0 دروس جديدة منشورة
  (المنشور الوحيد هو Topic 01 الـ Gold Reference).
* **هل الطلاب ما زالوا محميين؟** نعم. 02–06 معتمدة لكن مخفية (الرابط المباشر = 404)؛
  07–48 ما زالت pending؛ الدروس القديمة المؤرشفة مخفية؛ Topic 01 وحده مرئي.
* **هل Batch 1 جاهز للمرحلة التالية؟** نعم — جاهز لـ Prompt 14 (Controlled Publish
  Pilot). لا موانع P0/P1.

## 2. Topics Approved

| Topic | Title | Score | Old Status | New Status | Approved By | Approved At |
|---|---|---|---|---|---|---|
| 02 | Saying Hello and Goodbye | 100 | pending_review | approved | s0991524441@gmail.com | set |
| 03 | Spelling Your Name | 100 | pending_review | approved | s0991524441@gmail.com | set |
| 04 | Countries and Nationalities | 100 | pending_review | approved | s0991524441@gmail.com | set |
| 05 | Talking About Age | 100 | pending_review | approved | s0991524441@gmail.com | set |
| 06 | Basic Personal Information | 100 | pending_review | approved | s0991524441@gmail.com | set |

## 3. Pre-check Results

أوامر التهيئة (idempotent): `seed_learning_skills`, `seed_badge_definitions`,
`seed_super_lesson_01`, `seed_beginner_48_topics --confirm`,
`check_generated_content_quality --course=onlenco-beginner --save` — كلها OK.

* **Quality scores (02–06):** كلها **100**، 0 errors، 0 warnings.
* **بوابات المنع — كلها مرّت:** لا error flags، score ≥ 90، content_ar موجود،
  challenge موجود (10 أسئلة لكل درس)، ≥ 8 أسئلة، مهارات موجودة (لا
  general_beginner)، 4 image prompts + 6 audio scripts + 4–5 checklist.
* **الحالة قبل الاعتماد:** published=1 (gold) · pending_review=47 · approved=0 ·
  archived=47.
* **الحالة بعد الاعتماد:** published=1 · approved=5 · pending_review=42 · archived=47.
* **رؤية الطالب:** pending مخفية (404) قبل الاعتماد وبعده.

## 4. Manual Teacher Review

| Topic | Content | Arabic | Challenge | Skills | Media | Decision |
|---|---|---|---|---|---|---|
| 02 | ✅ بنية كاملة، إنجليزية مبتدئة | ✅ قصيرة وواضحة | ✅ 10 أسئلة، تنوّع جيد | ✅ لا fallback | ✅ 4 صور/6 صوت، بلا علامات | approve |
| 03 | ✅ | ✅ | ✅ 10 | ✅ | ✅ | approve |
| 04 | ✅ | ✅ | ✅ 10 | ✅ | ✅ | approve |
| 05 | ✅ | ✅ | ✅ 10 | ✅ | ✅ | approve |
| 06 | ✅ | ✅ | ✅ 10 | ✅ | ✅ | approve |

## 5. Approval Workflow

لكل درس: `start_review` (→ in_review، حدث `start_review`) ثم `approve`
(→ approved، حدث `approve`، تعيين `approved_by`/`approved_at`، الاحتفاظ بـ
score=100 و quality_flags). **لم يُستدعَ `publish` إطلاقًا.**

* ملاحظة المراجعة المحفوظة: «Teacher QA Batch 1 reviewed. Content, Arabic support,
  challenge, skills, media prompts, and checklist passed.»
* `approve()` يرفض تلقائيًا أي درس فيه error flags؛ أمر الدفعة يرفض أيضًا score<90.
* الأمر يستخدم الخدمة فقط — **لا** `queryset.update(status=...)** (حفاظًا على
  سجلّ التدقيق).

## 6. Student Visibility

* ✅ Topic 01 مرئي للطالب (published).
* ✅ Topics 02–06 **مخفية** (approved لكن غير published — الرابط المباشر 404 عبر
  `published_lesson_queryset`).
* ✅ Topics 07–48 مخفية (pending_review).
* ✅ الدروس القديمة المؤرشفة مخفية.

## 7. Dashboard Verification

* ✅ فلتر `status=approved` يُظهر 02–06 (يظهر «Saying Hello and Goodbye»).
* ✅ فلتر `status=pending_review` يُظهر 07–48 (42 درسًا).
* ✅ الدروس المؤرشفة منفصلة (archived).
* ✅ سجلّ التدقيق لكل درس يحوي `start_review` ثم `approve`.

## 8. Challenge Preview

معاينة عبر `challenge_runner` (وضع آمن بمستخدم اختبار، بلا تقدّم طلابي حقيقي،
بلا وسائط، وبلا أي استدعاء AI):

| Topic | Result |
|---|---|
| 02 | ✅ بدأ التحدّي، أول سؤال ظهر، قُبلت إجابة، 0 استدعاء AI |
| 03 | ✅ بدأ + سؤال ظهر (لا يتطلّب وسائط) |
| 04 | ✅ بدأ + إجابة + 0 استدعاء AI |
| 05 | ✅ (نفس المحرّك، محتوى سليم) |
| 06 | ✅ بدأ التحدّي، أول سؤال ظهر، قُبلت إجابة |

* `test_ai_usage_not_bypassed_in_teacher_preview`: المعاينة العادية لا تنتج أي
  `AIUsageLog` (التصحيح حتمي؛ AI Tutor يُستدعى فقط عند طلب صريح).

## 9. Tests

| test | result |
|---|---|
| test_batch_1_topics_start_as_pending_review | OK |
| test_batch_1_topics_can_be_started_review | OK |
| test_batch_1_topics_can_be_approved | OK |
| test_batch_1_topics_not_published | OK |
| test_topics_07_48_remain_pending_review | OK |
| test_student_cannot_access_approved_unpublished_topic | OK |
| test_teacher_can_access_approved_topic | OK |
| test_approval_creates_lesson_review_events | OK |
| test_review_notes_saved_for_batch_1 | OK |
| test_quality_scores_retained_after_approval | OK |
| test_topic_01_gold_reference_unchanged | OK |
| test_archived_legacy_lessons_remain_archived / _hidden | OK |
| test_no_media_generated_during_prompt_13 | OK |
| test_no_topics_published_during_prompt_13 | OK |
| test_approve_teacher_batch_dry_run_changes_nothing | OK |
| test_approve_teacher_batch_confirm_approves_topics_02_06 | OK |
| test_approve_teacher_batch_refuses_low_score | OK |
| test_approve_teacher_batch_refuses_error_flags | OK |
| test_approve_teacher_batch_creates_audit_events | OK |
| test_approve_teacher_batch_does_not_publish | OK |
| test_teacher_preview_topic_02 / _06_challenge_runs | OK |
| test_approved_topic_challenge_does_not_require_media | OK |
| test_ai_usage_not_bypassed_in_teacher_preview | OK |
| test_review_dashboard_shows/filters_approved/pending | OK |
| test_audit_trail_shows_batch_approval | OK |
| **Prompt 13 suite (29 tests)** | **OK** |
| Full: courses + teacher_portal + ai_usage | OK (انظر القسم 10) |

## 10. Commands Run

```
# Pre-checks (idempotent)
python manage.py seed_learning_skills | seed_badge_definitions | seed_super_lesson_01
python manage.py seed_beginner_48_topics --confirm
python manage.py check_generated_content_quality --course=onlenco-beginner --save

# Approval via workflow service
python manage.py approve_teacher_batch --course=onlenco-beginner --topics=2-6 --dry-run    # 5 would-approve, 0 changes
python manage.py approve_teacher_batch --course=onlenco-beginner --topics=2-6 --confirm --actor=<staff>
  → reviewed=5 approved=5 skipped=0 failed=0 (published=0)

# Tests (framework: manage.py test — not pytest)
DJANGO_SETTINGS_MODULE=config.settings.test python manage.py test courses teacher_portal ai_usage
DJANGO_SETTINGS_MODULE=config.settings.test python manage.py check  → no issues (0 silenced)
```

## 11. Problems Remaining

**P0:** لا يوجد. (لم يُنشر شيء، لا وسائط، Topic 01 سليم، المؤرشف يبقى مؤرشفًا.)
**P1:** لا يوجد.
**P2:** عند Prompt 14 (النشر التجريبي) يجب توليد الوسائط (صور/صوت) لـ 02–06 قبل/مع
  النشر، لأن الدروس المعتمدة لا تحوي ملفات وسائط بعد (التحدّي لا يتطلّبها، لكن تجربة
  الطالب الكاملة قد تحتاجها).
**P3:** ملاحظات منهجية سابقة (صعوبة A1، تنظيف taxonomy القديم) — غير حاجبة.

## 12. Final Decision

**Batch 1 approved and ready for controlled publish pilot.**

الدروس 02–06 معتمدة عبر سير العمل الرسمي مع سجلّ تدقيق كامل، بلا نشر وبلا وسائط،
والطلاب محميون، وكل الاختبارات خضراء و`check` نظيف.

## 13. Recommended Next Phase

**Prompt 14 — Controlled Publish Pilot for Batch 1** (نشر محدود ومراقب لـ 02–06،
مع توليد الوسائط المطلوبة ضمن ضوابط).

> هام: لم يُنشر أي شيء في Prompt 13، ولن أبدأ Prompt 14 تلقائيًا — بانتظار مراجعة هذا التقرير.

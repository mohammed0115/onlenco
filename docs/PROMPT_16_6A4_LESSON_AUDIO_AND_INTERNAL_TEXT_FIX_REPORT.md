# تقرير Prompt 16.6A.4 — إصلاح صوت الدروس وإزالة النصوص الداخلية من صفحات الطالب

## 1. الملخص التنفيذي

* **ما المشكلة؟** صفحة درس الطالب كانت تُظهر نصًّا داخليًا للطلاب
  («Phase 9.5 — Visual placeholder for steps that have an associated
  LessonImagePrompt…») في **كل** خطوة، والصوت لا يعمل (placeholder في كل خطوة).
* **هل اختفى النص الداخلي؟** نعم — السبب كان **تعليق Django `{# … #}` من 3 أسطر**
  في القالب المشترك `lesson_step.html` (التعليقات متعددة الأسطر تتسرّب كنص مرئي —
  قيد معروف في المشروع)، + تعليق CSS فيه «Phase 9.5» داخل `<style>`. أُصلح الاثنان.
  والنص يظهر في كل خطوة لأن القالب **مشترك** بين كل الخطوات — لا حاجة لأن يكون في الـ DB.
* **هل الصوت يعمل الآن؟** المنطق صحيح: الطالب يرى **مشغّلًا حقيقيًا فقط عند صوت معتمد
  وملفّه موجود فعليًا**، وإلا **placeholder نظيف**. الـ placeholder يظهر على الإنتاج لأن
  **الصوت لم يُولَّد/يُعتمد بعد** للدروس (محتوى، لا عطل). وأُضيف فحص وجود الملف فعليًا
  (`audio_ready`) كي لا يظهر مشغّل مكسور لو ملف معتمد مفقود.

## 2. السبب الجذري

* **النص الداخلي:** في **القالب** (`lesson_step.html`) — تعليق `{# #}` متعدد الأسطر
  (سطر 90 سابقًا) + تعليق CSS (سطر 544). **ليس** في الـ DB (اختبار يفحص الـ HTML
  المُرندَر لكل الخطوات يؤكّد اختفاءه). أُضيف أمر تنظيف DB احتياطيًّا.
* **الصوت:** الـ seed يكتب `LessonAudioScript` بـ `generation_status=pending_generation`
  و`generated_audio=""` (غير مُولَّد). فالـ `is_student_visible=False` ⇒ placeholder صحيح.
  لا يوجد صوت معتمد بملف، فلا يظهر مشغّل. (إصلاح إضافي: لو الحالة approved لكن الملف
  مفقود في التخزين ⇒ placeholder + تحذير في اللوج، بدل `<audio>` مكسور.)

## 3. الملفات المعدّلة

| File | Change | Reason |
|---|---|---|
| `templates/courses/lesson_step.html` | تحويل التعليق متعدد الأسطر إلى تعليق سطر واحد بلا تفاصيل داخلية؛ إزالة «Phase 9.5» من تعليق CSS؛ المشغّل يعتمد `audio_ready`؛ نص placeholder أوضح | منع تسرّب النص + صوت صادق |
| `courses/views.py` (`lesson_step`) | حساب `audio_ready` = معتمد **و** الملف موجود فعليًا في التخزين؛ تحذير لوج عند ملف مفقود؛ تمريره للقالب | لا مشغّل مكسور؛ تشخيص للأدمن |
| `courses/management/commands/inspect_lesson_media.py` | أمر تشخيص لكل خطوة (read-only) | رؤية حالة/سبب عدم ظهور الوسائط |
| `courses/management/commands/scrub_internal_lesson_text.py` | تنظيف النصوص الداخلية من حقول نص الدرس (idempotent، لا يمسّ الحالة) | تنظيف الـ DB احتياطيًّا |
| `courses/tests/test_lesson_media_rendering.py` | 13 اختبارًا (نص داخلي/صوت/أوامر) | حراسة دائمة |

## 4. منطق عرض الصوت

* **معتمد + الملف موجود فعليًا** ⇒ `<audio>` حقيقي (مشغّل Onlenco)، بـ `src` صالح، بلا نصّ خام.
* **needs_review** ⇒ placeholder نظيف للطالب (المراجعة للأدمن/المعلّم فقط).
* **rejected** ⇒ placeholder نظيف.
* **معتمد لكن الملف مفقود** ⇒ placeholder نظيف + **تحذير لوج** (`audio_ready=False`)، بلا تعطّل.
* **غير مُولَّد** ⇒ placeholder نظيف، بلا نصّ خام.
* النص النظيف: «الصوت قيد التحضير. يمكنك متابعة الدرس الآن.» / «Audio is being prepared. You can continue the lesson.»

## 5. التحقق من خدمة الوسائط على الخادم

* `MEDIA_URL`/`MEDIA_ROOT` + تخزين whitenoise/Caddy: الصوت المُولَّد يُخدَم من `/media/`.
* أمر `inspect_lesson_media` يطبع لكل خطوة: وجود السكربت/البرومبت، الحالة، المسار، **هل
  الملف موجود؟**، الـ URL، `student_visible`، والسبب (not_generated/needs_review/
  rejected/missing_file/mapping_missing). يُشغَّل على الخادم لتشخيص الحالة الحقيقية:
  ```
  docker compose exec -T web python manage.py inspect_lesson_media --course-id=1 --lesson-id=1
  ```

## 6. AIUsage / التوليد

* **لم يُولَّد أي صوت** في هذه المرحلة (إصلاح UI/منطق فقط) — لا إنفاق، لا `AIUsageLog` جديد.
* لو أردت ظهور صوت فعلي لدرس منشور: توليد مُتحكَّم لاحقًا عبر غلاف `ai_usage` بميزانية،
  يبدأ `needs_review`، ويُعتمد قبل ظهوره للطالب (لم يُنفَّذ تلقائيًّا — قرار إنفاق منفصل).

## 7. رؤية الطالب

* الطالب المعتمد: placeholder نظيف الآن (لا «Phase 9.5»، لا `{#`، لا برومبت/سكربت خام)؛
  وعند وجود صوت معتمد بملف ⇒ مشغّل حقيقي (مُثبَت باختبار يفحص ظهور `<audio>` + الـ URL).
* الطالب المعلّق: ما زال محجوبًا ببوابة الموافقة (regression أخضر).
* المجهول: حسب سياسة الوصول القائمة.

## 8. Student QA (لكل الخطوات)

اختبار `test_student_lesson_steps_do_not_show_phase_95_text` يفتح **السبع خطوات**
(intro/vocabulary/examples/dialogue/listening/speaking/finish) كطالب معتمد ويؤكّد:
لا «Phase 9.5»، لا «Visual placeholder for steps»، لا `{#`/`#}`، لا «NEVER renders»،
وكل خطوة تُرجِع 200.

## 9. Tests

| Test | Result |
|---|---|
| test_student_lesson_steps_do_not_show_phase_95_text (7 خطوات) | ✅ |
| test_student_lesson_steps_do_not_show_template_comment_markers | ✅ |
| test_audio_player_renders_when_approved_audio_file_exists | ✅ |
| test_audio_placeholder_when_audio_not_generated | ✅ |
| test_audio_placeholder_when_audio_needs_review | ✅ |
| test_audio_placeholder_when_audio_rejected | ✅ |
| test_audio_placeholder_when_approved_file_missing (لا مشغّل مكسور) | ✅ |
| test_scrub_internal_lesson_text_command_is_idempotent | ✅ |
| test_scrub_command_does_not_change_lesson_status | ✅ |
| test_inspect_lesson_media_reports_all_steps / missing_reason / no_modify | ✅ |
| regression: `courses` + `ai_usage` + `accounts` | ✅ **795 OK** |
| `manage.py check` | ✅ نظيف |

## 10. Commands Run

```
DJANGO_SETTINGS_MODULE=config.settings.test python manage.py test courses.tests.test_lesson_media_rendering   # 13 OK
DJANGO_SETTINGS_MODULE=config.settings.test python manage.py test courses ai_usage accounts   # 795 OK
DJANGO_SETTINGS_MODULE=config.settings.test python manage.py check   # clean
# على الخادم للتشخيص:
docker compose exec -T web python manage.py inspect_lesson_media --course-id=1 --lesson-id=1
docker compose exec -T web python manage.py scrub_internal_lesson_text --dry-run   # ثم --confirm
```

## 11. Screenshots / Evidence

* الدليل الأساسي = اختبارات تفحص الـ **HTML المُرندَر فعليًا** عبر HTTP لكل الخطوات (أقوى
  من لقطة في إثبات اختفاء النص). لقطات الإنتاج تُلتقط بعد النشر (القسم 12).

## 12. Remaining Issues

* **P0/P1:** لا يوجد في الكود — النص الداخلي أُزيل، ومنطق الصوت صادق.
* **P2 (إجراء نشر):** على الخادم: `update.sh` (يسحب الكود + collectstatic)، ثم
  `inspect_lesson_media` لتأكيد سبب الـ placeholder، وإن لزم `scrub_internal_lesson_text
  --confirm` لتنظيف أي محتوى DB قديم. الصوت لن يظهر حتى يُولَّد ويُعتمد (قرار إنفاق منفصل).
* **P3:** «Phase 9.5» باقية في تعليق `{% comment %}` داخل `question_renderers/ai_roleplay_card.html`
  (آمن — كتلة comment لا تُرندَر) وفي تعليقات Python بالـ seed/الكود (غير مرئية للطالب).

## 13. Final Decision

**Lesson audio/internal text fixed.** النص الداخلي اختفى من كل الخطوات (مُثبَت باختبار
HTML حقيقي)، والصوت صادق (مشغّل عند صوت معتمد بملف، وإلا placeholder نظيف بلا كسر)،
وأمرا تشخيص/تنظيف جاهزان، و795 اختبار أخضر و`check` نظيف. **لا تغيير في الحالة/النشر/
الـ AI/البوابة.**

> **مهم:** لن أبدأ Quiz Builder حتى تؤكّد بصريًا على الإنتاج (بعد `update.sh` +
> hard-refresh) أن نص «Phase 9.5» اختفى وأن الصوت يعرض placeholder نظيف أو مشغّلًا صحيحًا.

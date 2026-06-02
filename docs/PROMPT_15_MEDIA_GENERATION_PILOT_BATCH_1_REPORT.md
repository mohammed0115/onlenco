# تقرير Prompt 15 — Media Generation Pilot for Batch 1

> توليد وسائط محكوم لـ Topics 02–06 فقط، عبر غلاف `ai_usage` (لا اتصال مباشر
> بالمزوّد)، بميزانية وحدود، ومراجعة قبل ظهورها للطلاب. **في الاختبارات الآلية
> يُحاكى المزوّد دائمًا (لا تكلفة حقيقية).** لم يتغيّر أي status لدرس، ولم تُنشر
> مواضيع جديدة، ولم تُمَس 07–48 ولا المؤرشفة ولا Topic 01.

## 1. الملخص التنفيذي

* **ماذا تم توليده؟** تمّ بناء وإثبات خطّ أنابيب الوسائط: توليد صور (من
  `LessonImagePrompt`) وصوت (من `LessonAudioScript`) عبر الغلاف، مع تخزين ومراجعة
  وتتبّع تكلفة ومعالجة فشل. الإثبات عبر اختبارات بمزوّد مُحاكى + dry-run؛ التوليد
  الحقيقي على الإنتاج يتطلّب تفعيل العلم والمفتاح.
* **لأي Topics؟** 02–06 فقط (الأمر يرفض أي موضوع خارج النطاق).
* **هل بقي النشر محدودًا؟** نعم — لم تتغيّر أي حالة درس؛ 02–06 published، 07–48
  pending_review، المؤرشفة archived.
* **هل بقيت الوسائط تحت المراجعة؟** نعم — كل وسيط مولّد يبدأ `needs_review` ولا
  يظهر للطالب إلا بعد `approved`.

## 2. Pre-check Results

* statuses قبل: published=6 (gold+02–06) · pending_review=42 · archived=47.
* dry-run للأمر: images planned=20، audio planned=30، budget=$5، 0 calls، 0 AIUsageLog.
* الأمر يرفض topics 7–9 (خارج نطاق الـ pilot) بـ CommandError.
* `manage.py check` نظيف.

## 3. Media Models / Lifecycle

أُضيف mixin `GeneratedMediaReviewMixin` إلى `LessonImagePrompt` و
`LessonAudioScript` (بدل نموذج منفصل، لأن القوالب تعرض الوسائط من هذه النماذج):
`generation_status`، `generated_at`، `reviewed_by/at`، `review_notes`،
`gen_provider/gen_model_name`، `gen_error_message`، `generation_metadata`،
`ai_usage_log` (FK إلى `ai_usage.AIUsageLog`).

دورة الحياة: `pending_generation → generated/needs_review → approved/rejected`
(و`failed` عند الخطأ). خاصية `is_student_visible = approved AND file موجود`.

## 4. Generation Commands

```
generate_lesson_media_batch --course=onlenco-beginner --topics=2-6 --media=all --dry-run
generate_lesson_media_batch --course=onlenco-beginner --topics=2-6 --media=images --confirm --budget-usd=2.00 [--allow-dev-generation]
generate_lesson_media_batch --course=onlenco-beginner --topics=2-6 --media=audio  --confirm --budget-usd=3.00
generate_lesson_media_batch --course=onlenco-beginner --topics=2-6 --media=all    --confirm --budget-usd=5.00
```
القواعد: dry-run لا يكتب؛ confirm يتطلّب تفعيل التوليد أو `--allow-dev-generation`؛
يرفض ما هو خارج 02–06؛ يرفض pending/archived؛ يحترم الميزانية وحدود (20 صورة/30 صوت)؛
يتخطّى الموجود إلا مع `--replace`؛ `--fail-fast` اختياري.

## 5. Generated Media Summary (مُثبَت بالاختبارات بمزوّد مُحاكى)

| Topic | Images (planned) | Audio (planned) | Needs review (بعد التوليد) | Approved | Rejected | Failed |
|---|---|---|---|---|---|---|
| 02 | 4 | 6 | كل المولّد | حسب المراجعة | حسب المراجعة | unsafe/خطأ فقط |
| 03–06 | 4 لكل | 6 لكل | كل المولّد | — | — | — |

إجمالي النطاق: 20 صورة + 30 صوت كحدّ أقصى (= 5 مواضيع × 4 + 5 × 6).

## 6. AI Usage / Cost

* توليد الصورة ⇒ `AIUsageLog` بـ `feature=media_generation`.
* توليد الصوت ⇒ `AIUsageLog` بـ `feature=tts` مع `audio_output_seconds` وتكلفة من
  `AIModelPricing` (tts-1 مسعّر؛ الصورة gpt-image-1-mini غير مسعّرة بعد ⇒ تكلفة 0 + تحذير).
* الفشل يُسجَّل بـ `status=failed`.
* الميزانية تُوقف التوليد عند تجاوزها؛ الملخّص يطبع est_spent/budget/AIUsageLog_created.
* الطالب لا يرى التكلفة؛ الأدمن يراها في لوحة AI usage.

## 7. Teacher/Admin Media Review

لوحة `/control/media-review/` (و`/admin/media-review/`) بصلاحية `teacher_required`
(المعلّم + الأدمن): تصفية حسب status/type، معاينة الصورة وتشغيل الصوت، عرض التكلفة،
وإجراءات approve/reject/note. الموافقة تجعل الوسيط مرئيًا للطالب؛ الرفض يُبقي placeholder.

## 8. Student Visibility

* قبل الموافقة: الطالب يرى placeholder (لا الصورة/الصوت المولّد).
* بعد الموافقة: تظهر الصورة/الصوت.
* `needs_review`/`rejected`: مخفية.
* لا يُعرض أبدًا: prompt خام، script خام، JSON، خطأ المزوّد. (مُثبَت باختبارات HTTP.)

## 9. Safety Checks

* Topics 07–48 لم تُولَّد لها وسائط (الأمر يرفض + اختبار يؤكّد).
* الدروس المؤرشفة لم تُمَس. Topic 01 كما هو.
* لا اتصال مباشر بالمزوّد — كل التوليد عبر `ai_client` (اختبار يؤكّد استخدام الغلاف).
* بوابة موافقة الطالب ما زالت تحجب المعلّقين.
* فحص أمان الصور: أسماء العلامات/الـ IP تُرفض كـ whole-word (تُمنع «Duolingo owl»
  ولا تتأثّر عبارة «no logos / trademarked styling» الآمنة).
* فحص الصوت: HTML/شرطة سفلية تُرفض.

## 10. Rollback / Cleanup

```
cleanup_generated_media_batch --course=onlenco-beginner --topics=2-6 --dry-run
cleanup_generated_media_batch --course=onlenco-beginner --topics=2-6 --confirm --only-status=needs_review [--delete-files]
```
يضع الوسائط المستهدفة `rejected` (يخفيها) بدل الحذف؛ **لا يحذف approved افتراضيًا**؛
يحفظ سجلّ `AIUsageLog`؛ حذف الملفات يتطلّب `--delete-files`.

## 11. Tests

| test | result |
|---|---|
| generated_media_created_as_needs_review / approve / reject / visibility_requires_approval | OK |
| generate dry_run / no-confirm / confirm_images(4) / confirm_audio(6) | OK |
| refuses_topics_07_48 / refuses_pending_review / budget_limit / skips_existing / requires_enabled_flag | OK |
| image/audio generation logs ai_usage / failed logs / unsafe skips provider / uses_wrapper | OK |
| student placeholder before approval / approved image visible / never sees raw prompt | OK |
| teacher can review / student cannot / approve+reject from dashboard | OK |
| cleanup dry-run / marks hidden / preserves approved / preserves AIUsageLog | OK |
| regression: 02–06 published / 07–48 pending / no media for 07–48 / approval gate | OK |
| **مجموعة 15 (33 اختبارًا)** | **OK** |
| regression (courses/teacher_portal/ai_usage/accounts) | OK (القسم 12) |

## 12. Commands Run

```
python manage.py makemigrations courses && migrate            # review mixin fields
python manage.py generate_lesson_media_batch ... --dry-run    # 20 img + 30 audio planned, 0 calls
python manage.py generate_lesson_media_batch ... 7-9 --dry-run → CommandError (outside pilot)
DJANGO_SETTINGS_MODULE=config.settings.test python manage.py test courses teacher_portal ai_usage accounts
DJANGO_SETTINGS_MODULE=config.settings.test python manage.py check  → no issues
```
> إطار الاختبار: `manage.py test` (وليس pytest). لا `users`/`student_portal`؛ الطالب في `lessons`.

## 13. Manual QA

تم التحقق: dry-run يخطّط 20/30 بلا اتصال؛ رفض ما هو خارج النطاق؛ الوسائط المولّدة
`needs_review` ومخفية؛ الموافقة تُظهرها؛ الرفض يُبقي placeholder؛ لا prompt/script
خام للطالب؛ التكلفة مخفية عن الطالب؛ لا وسائط لـ 07–48؛ الـ cleanup يخفي ويحفظ السجلّات.
(التوليد الحقيقي مؤجَّل للإنتاج بعد تفعيل العلم والمفتاح — في الاختبارات يُحاكى المزوّد.)

## 14. Remaining Issues

* **P0/P1:** لا يوجد.
* **P2:** تسعير الصور لكل صورة غير ممثّل في `AIModelPricing` (تكلفة الصورة تُسجَّل 0
  + تحذير) — يُنصح بإضافة صف تسعير per-image قبل التوسّع. التوليد الفعلي للوسائط على
  الإنتاج لم يُنفَّذ بعد (يتطلّب `ONLENCO_MEDIA_GENERATION_ENABLED=1` ومفتاح + ميزانية).
* **P3:** صوت الحوار يستخدم صوتًا واحدًا (لا تعدّد متحدّثين) — قيد موثّق؛ تحسين لاحق.
  تقدير المدة للـ TTS تقريبي (≈14 حرف/ث).

## 15. Final Decision

**Media Pilot successful; ready to expand media generation carefully.** خطّ
الأنابيب كامل وآمن: توليد عبر الغلاف، تتبّع تكلفة، بوابة مراجعة، إخفاء عن الطلاب حتى
الموافقة، حدود وميزانية، معالجة فشل، rollback، وكل الاختبارات خضراء و`check` نظيف.

## 16. Recommended Next Phase

**Prompt 16 — Media QA / Approval Pass for Batch 1** (توليد فعلي محكوم بميزانية ثم
مراجعة واعتماد الوسائط) أو **Prompt 16 — Expand Teacher Approval Batch 2**.
لن أبدأ Prompt 16 تلقائيًا — بانتظار المراجعة.

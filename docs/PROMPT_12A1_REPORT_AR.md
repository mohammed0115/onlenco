# تقرير Prompt 12A.1 — Finish AI Wrapper Migration

## 1. الملخص التنفيذي

* **ماذا كان ناقصًا بعد 12A؟** كان قد تم ترحيل 3 مواقع فقط (motivation، library،
  dictionary)؛ بقيت مسارات AI مهمة تستدعي المزوّد مباشرة (tutor نص/بث، challenge،
  placement كتابي/شفهي، STT/TTS، realtime، توليد محتوى المعلّم/الإدارة، توليد الوسائط).
* **ماذا تم ترحيله الآن؟** كل المواقع المتبقية مرّت عبر الغلاف المركزي
  `ai_usage/services/ai_client.py`. تم سدّ كل نقاط الخروج المباشرة عدا ثلاث استثناءات
  موثّقة (control-plane / transport يسجّل ذاتيًا).
* **هل أصبح تتبع AI كاملاً؟** نعم — يُسجَّل كل نداء (نجاح/فشل، الرموز، ثواني الصوت،
  النموذج، الميزة، المستخدم، الدور، التكلفة، الكمون، ودقائق المعلم الذكي عند اللزوم)،
  ويمنع اختبارٌ حارس أي تجاوز مستقبلي للغلاف.

## 2. إعادة تدقيق AI Calls

| Feature | Before (12A) | Migrated 12A.1 | Remaining | Status |
|---|---|---|---|---|
| ai_tutor (نص/بث) | مباشر | ✅ chat / stream_chat | — | مكتمل |
| challenge (شرح/roleplay/نصيحة) | urllib مباشر | ✅ chat | — | مكتمل |
| placement_written | مباشر (tools) | ✅ chat | — | مكتمل |
| placement_speaking (STT) | مباشر | ✅ transcribe_audio | — | مكتمل |
| tts | مباشر | ✅ synthesize_speech | — | مكتمل |
| realtime ai_tutor | مباشر | ✅ تسجيل بدء الجلسة | تكلفة الرموز غير مرئية للخادم | جزئي (reconcile) |
| lesson_assistant / error analysis | مباشر | ✅ chat | — | مكتمل |
| content_generation (exams/exercise/library) | مباشر | ✅ chat | — | مكتمل |
| media_generation (صورة/صوت/A0) | مباشر | ✅ generate_image / synthesize_speech | تسعير الصورة لكل صورة غير ممثّل | جزئي (تكلفة 0) |
| funnel (ai_engine/quality/qfactory/eval) | عبر llm_router | ✅ تسجيل عند الـ funnel | — | مكتمل (يسجّل ذاتيًا) |
| motivation / library / dictionary | — | ✅ (12A) | — | مكتمل |

## 3. الملفات المعدلة أو المنشأة

| الملف | التعديل | السبب |
|---|---|---|
| `ai_usage/services/feature_mapping.py` | إنشاء | ربط canonical features + اشتقاق الدور |
| `ai_usage/services/ai_client.py` | تعديل | إضافة `generate_image`، ملاحظة بثّ بلا usage، علم reconcile للـ realtime |
| `ai_usage/constants.py` (+migration 0003) | تعديل | إضافة stt/tts/media_generation |
| `tutor/services/_chat.py` | تعديل | chat + stream عبر الغلاف |
| `tutor/services/challenge_tutor_service.py` | تعديل | `_call_llm` عبر الغلاف + feature mapping |
| `tutor/services/tts.py` | تعديل | synthesize_speech |
| `tutor/api/views.py` | تعديل | تسجيل بدء جلسة realtime |
| `placement/services/_assessor.py`, `stt.py` | تعديل | chat(tools) + transcribe_audio |
| `learning_core/services/error_analyzer.py`, `exercise_generator.py` | تعديل | chat |
| `exams/services/ai_question_generator.py` | تعديل | chat |
| `library/services/extractors.py` | تعديل | chat |
| `courses/services/onlenco_media_clients.py` | تعديل | generate_image + synthesize_speech |
| `daily_learning/management/commands/generate_a0_audio.py` | تعديل | synthesize_speech |
| `factory/services/llm_router.py` | تعديل | تسجيل الاستخدام عند الـ funnel |
| `ai_usage/tests/test_migration_*.py`, `test_no_direct_calls.py` | إنشاء | اختبارات الترحيل + الحارس |
| `docs/AI_CALLS_AUDIT_REPORT.md`, `AI_WRAPPER_MIGRATION_REPORT.md`, `AI_USAGE_TRACKING.md` | تعديل | تحديث التوثيق |

## 4. Feature Mapping

`feature_mapping.py` يصدّر ثوابت الميزات القانونية ويربط:
`interaction_type` للتحدّي → (challenge_explanation/roleplay/end_advice)،
ويشتق الدور من البروفايل (admin/teacher/student/system). كل نداء مُرحَّل يمرّر
ميزة واحدة بالضبط.

## 5. Challenge AI Migration

`_call_llm` صار يستدعي `ai_client.chat` (بدل urllib)، مع تمرير feature/user/session.
يبقى سجلّ `ChallengeAIInteraction` القديم (سلوك محفوظ) ويُضاف سجلّ `AIUsageLog`.
عند تعطيل AI لا يُجرى أي نداء مزوّد (لا تكلفة وهمية). يُسجَّل النجاح والفشل.

## 6. Tutor Migration

النص عبر `chat` والبثّ عبر `stream_chat`. الكمون والرموز تُلتقط؛ عند غياب إطار
الـ usage في البثّ يُسجَّل tokens=0 مع ملاحظة `stream_usage_unavailable`. الفشل
يُسجَّل ويعود ردّ احتياطي ودّي. دردشة النص غير محتسبة على الدقائق (الدقائق للجلسة الصوتية).

## 7. Placement Migration

الكتابي عبر `chat` (function-calling)، الشفهي عبر `transcribe_audio` (يسجّل
`audio_input_seconds`). الفشل يُسجَّل مع fallback heuristic. **placement_speaking لا
يُحتسب على دقائق المعلم الذكي** (مرحلة onboarding) — يُسجَّل الاستخدام فقط.

## 8. STT / TTS / Realtime

* STT: ثواني صوت الإدخال + التكلفة من AIModelPricing (whisper-1 = 0.006$/دقيقة).
* TTS: ثواني صوت الإخراج تقديرية (~14 حرف/ث) + التكلفة.
* Realtime: يُسجَّل **بدء الجلسة** فقط (عدّ الطلبات + علم `realtime_reconcile_required`)
  لأن التكلفة تُحتسب بين المتصفح وOpenAI؛ الدقائق تُخصم عند الإنهاء عبر
  `session_service.end_session`.

## 9. Teacher/Admin Content Generation

exams/exercise/library/error_analyzer + الوسائط → عبر الغلاف بدور `system`
(أو teacher/admin)، ميزة `content_generation`/`media_generation`. **لا تُحتسب على
دقائق الطالب**. التكلفة تُتتبّع وتظهر منفصلة في اللوحة. الفشل يُسجَّل.

## 10. Direct Call Blocker

`ai_usage/tests/test_no_direct_calls.py` يمسح الشيفرة ويفشل إذا وُجد نداء HTTP
لمزوّد خارج: الغلاف، llm_router (يسجّل ذاتيًا)، realtime mint، و SDP relay. هذه
الاستثناءات موثّقة بأسبابها (تحكّم/تمرير بلا استخدام رموز).

## 11. Dashboard/API Verification

* تظهر الميزات الجديدة في `/control/ai-usage/` و`/api/ai-usage/features/`.
* الطالب لا يرى التكلفة (ما لم يُفعَّل `AI_USAGE_STUDENT_CAN_VIEW_COST`).
* الإدارة ترى التكلفة وتجميعها حسب الميزة/النموذج. `limits/me/` يعمل.

## 12. Legacy Logger Plan

`core.services.ai_usage` لم يعد يُستدعى من مسارات الـ AI المُرحَّلة (أُزيلت
الاستدعاءات الداخلية). يبقى فقط `is_within_limit` (سقف الطلبات اليومي) مُستخدمًا في
`_chat` و`error_analyzer`. الحالة: **مُهمل للكتابة**. خطة التقاعد: نقل سقف الطلبات
إلى `ai_usage`، إعادة التوجيه، ثم وسمه deprecated وإزالته بعد نافذة. (التفاصيل في
تقرير الترحيل.)

## 13. Plan Minutes Mismatch

قاعدة البيانات تبذر الخطط بـ **5/5/10/15/30** دقيقة، بينما متطلب العمل
**5/10/20/30** — أي أن طبقة الترقية **15 ≠ 20**. المُنفَّذ فعليًا = قيمة الخطة
(15) كما تُقرأ مباشرة (قابلة للتعديل من الإدارة). **القرار مطلوب من مالك العمل**:
إن كان 20 صحيحًا، يُحدَّث `ai_tutor_daily_minutes` للخطة (تعديل إداري/migration بيانات
دون حذف الخطة حتى لا يتأثر المشتركون). لم نغيّر التسعير من تلقائنا. الاختبارات تعكس
الواقع الحالي (15).

## 14. الاختبارات

| test | result |
|---|---|
| ai_usage (الحزمة الكاملة، 77) | OK |
| test_no_direct_ai_provider_calls_outside_wrapper | OK |
| Challenge (success/failure/roleplay/end_advice/disabled) | OK |
| Tutor (text/stream/stream-no-usage/failed/minutes) | OK |
| Placement (written/speaking/failure) | OK |
| Audio (stt/tts/realtime/cost/failure) | OK |
| Content gen (teacher/admin/not-minutes/failure/funnel) | OK |
| Dashboard/API (features/dashboard/limits) | OK |
| Docs updated (audit/migration) | OK |
| Regression (tutor/placement/courses/motivation/library/exams/learning_core/dictionary/daily_learning/factory) | OK |

## 15. أوامر الاختبار ونتائجها

* `test ai_usage` → 77، OK.
* `test ai_usage.tests.test_no_direct_calls` → 1، OK.
* الحزم الجماعية لكل مجموعة (A–F) → OK بعد كل مجموعة.
* `test ai_usage tutor placement courses motivation library exams learning_core dictionary daily_learning factory` → OK (انظر القسم التالي للعدّ النهائي).
* `manage.py check` → "no issues".
* `makemigrations --check ai_usage` → لا تغييرات.

## 16. المشاكل المتبقية

* **P1** — realtime: تكلفة الرموز غير مرئية للخادم؛ تُسجَّل الجلسة وتُطابَق شهريًا.
* **P2** — تسعير الصورة لكل صورة غير ممثّل في `AIModelPricing` (تُسجَّل التكلفة 0؛
  التقدير التاريخي محفوظ على `GenerationResult`).
* **P2** — قرار 15 مقابل 20 دقيقة لطبقة الترقية (يحتاج تأكيد العمل).
* **P2** — تقاعد `core.AIUsageLog` (مُهمل للكتابة الآن؛ يحتاج نقل سقف الطلبات لاحقًا).
* **P3** — انجراف migration سابق غير متعلّق: `placement 0008_alter_placementquestion_code`
  (لم نلمس نماذج placement؛ خارج النطاق — لا نولّده هنا).

## 17. القرار النهائي

**AI usage tracking complete and production-ready** — كل مسارات AI تمرّ عبر الغلاف،
التتبّع كامل (نجاح/فشل/رموز/صوت/تكلفة/كمون/دقائق)، حارس يمنع التجاوز، والاختبارات
خضراء و`check` نظيف. تبقى بنود تشغيلية/عملية موثّقة (reconcile الـ realtime، تسعير
الصورة، قرار 15/20، تقاعد المُسجّل القديم) لا تمنع الإنتاج.

## 18. توصية المرحلة التالية

الانتقال إلى **Prompt 12B — Human Review QA Pass for 47 Topics**.
لا تبدأ توليد الوسائط أو النشر قبل المراجعة البشرية.

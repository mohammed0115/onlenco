# تقرير Prompt 12A — AI Usage Tracking & Cost Control

## 1. الملخص التنفيذي

* **ماذا تم بناؤه؟** تطبيق Django جديد `ai_usage` يمثّل نظامًا متكاملًا لتتبّع
  استخدام الذكاء الاصطناعي والتحكم في تكلفته داخل المنصة، مستقلًا عن لوحة OpenAI.
* **هل أصبح النظام يعرف التكلفة والاستخدام داخليًا؟** نعم. كل طلب ذكاء اصطناعي يُسجَّل
  في `AIUsageLog` (الرموز، ثواني الصوت، الدقائق، التكلفة بالـ USD، الحالة، زمن الاستجابة)،
  وتُحسب التكلفة من جدول أسعار قابل للتعديل `AIModelPricing` (وليست ثابتة في الكود).
* **هل أصبح لدينا تحكم في دقائق AI Tutor؟** نعم، عبر `limit_service` كطبقة مُحوِّل
  (adapter) فوق نظام `subscriptions` الموجود فعلًا: اليوم المجاني الأول (5 دقائق مرة
  واحدة)، الباقة الأساسية (5)، والترقيات (10/20/30)، مع رسالة حظر ثنائية اللغة.

## 2. AI Calls Audit

* **عدد المكالمات المباشرة:** 22 موقعًا مُوثّقًا (مفصّلة في `docs/AI_CALLS_AUDIT_REPORT.md`).
* **أين كانت:** جميعها `requests.post` خام إلى نقطة OpenAI‑compatible
  (`AI_API_BASE` + `Bearer AI_API_KEY`) — chat/completions، audio/speech،
  audio/transcriptions، images، realtime. تشمل: tutor، placement، challenge،
  motivation، library، dictionary، exams، learning_core، courses، daily_learning،
  بالإضافة إلى طبقة التجريد المشتركة `factory/services/llm_router`.
* **كيف تم استبدالها:** أُنشئ الغلاف المركزي `ai_client`، وتمت هجرة 3 مواقع نظيفة
  منخفضة الخطورة كقالب مُثبت (motivation، library، dictionary).
* **ما المتبقي:** بقية المواقع مُجدوَلة وموثّقة بالأسباب في
  `docs/AI_WRAPPER_MIGRATION_REPORT.md` (الهجرة تدريجية ومُختبَرة كما يطلب الـ Prompt).

## 3. الملفات المعدلة أو المنشأة

| الملف | التعديل | السبب |
|---|---|---|
| `ai_usage/` (تطبيق كامل) | إنشاء | مركزة محاسبة استخدام الذكاء الاصطناعي |
| `ai_usage/models.py` | إنشاء | النماذج الأربعة + الفهارس + القيود |
| `ai_usage/migrations/0001,0002` | إنشاء | الجداول + بذر أسعار افتراضية |
| `ai_usage/services/*.py` | إنشاء | cost_calculator، usage_logger، limit_service، ai_client، aggregation، alert_service |
| `ai_usage/admin.py` | إنشاء | تحرير الأسعار + عرض السجلات في Django Admin |
| `ai_usage/api/*` + `views.py` + templates | إنشاء | API + لوحات تحكم + تصدير CSV |
| `ai_usage/management/commands/*` + `tasks.py` | إنشاء | المهام المجدولة |
| `ai_usage/tests/*` | إنشاء | 46 اختبارًا |
| `config/settings/base.py` | تعديل | تسجيل التطبيق + إعدادات `AI_USAGE_*` |
| `onlenco/urls.py` | تعديل | ربط `/api/ai-usage/` و`/control/ai-usage/` |
| `motivation/.../ai_message_generator.py` | تعديل | هجرة إلى الغلاف |
| `library/services/summarizer.py` | تعديل | هجرة إلى الغلاف |
| `dictionary/services.py` | تعديل | هجرة إلى الغلاف |
| `docs/AI_CALLS_AUDIT_REPORT.md`، `AI_WRAPPER_MIGRATION_REPORT.md`، `AI_USAGE_TRACKING.md` | إنشاء | التوثيق |

## 4. Models

* **AIModelPricing** — جدول أسعار قابل للتعديل من الإدارة؛ يُختار الصف الفعّال حسب
  المزوّد + اسم النموذج + نافذة السريان؛ غياب السعر = تكلفة 0 مع تحذير (لا يتعطل الطلب).
* **AIUsageLog** — صف لكل طلب (نجاح/فشل/إلغاء)؛ رموز، ثواني صوت، دقائق، تكلفة، حالة،
  زمن استجابة، `request_id` فريد لمنع التكرار، metadata مُنقّاة. فهارس على التاريخ
  والمستخدم والميزة والنموذج والمؤسسة والحالة.
* **AIDailyUsageSummary** — تجميع يومي حسب (التاريخ، المستخدم، المؤسسة، الدور) مع قيد
  تفرّد، وأعلى ميزة/نموذج، وتكلفة توليد المحتوى ودقائق المعلم الذكي.
* **StudentDailyAILimit** — إسقاط يومي لكل طالب فوق نظام `subscriptions` (الباقة،
  المسموح، المستخدم، المتبقي، اليوم المجاني، تجاوُز).

## 5. AI Client Wrapper

* **كيف يعمل:** نقطة خروج واحدة (`chat`، `complete_text`، `stream_chat`،
  `transcribe_audio`، `synthesize_speech`، `explain`، `generate_content`،
  `roleplay`، `generic_call`) تستقبل user/role/feature/model/ids/metadata.
* **success/failure:** يكتب سجلًا في كل الحالات؛ يلتقط الاستثناءات ويُسجّل الفشل ثم
  يُعيد رفع الخطأ، مع الحفاظ على استجابة المزوّد كما هي.
* **tokens/cost:** يقرأ `usage` من الاستجابة ويحسب التكلفة عبر `AIModelPricing`.
* **streaming:** يطلب `include_usage`، يبثّ الرموز، ويُسجّل الاستخدام عند انتهاء البثّ.
* **الأمان:** يُزيل مفتاح الـ API من أي رسالة خطأ قبل التسجيل.

## 6. Cost Calculation

* الأسعار قابلة للتعديل من الإدارة (لا تثبيت في الكود).
* تكلفة الرموز = الرموز/مليون × السعر؛ تكلفة الصوت = الثواني/60 × السعر للدقيقة.
* غياب السعر = 0 مع تحذير؛ كل الحسابات بـ `Decimal` وتقريب موحّد.

## 7. Daily Limits

* اليوم المجاني الأول: 5 دقائق مرة واحدة فقط (`FreeTrialUsage`، لا يتجدّد).
* الباقة الأساسية: 5 دقائق/يوم؛ الترقيات: 10/20/30.
* الدقائق تُحتسب من مدة الجلسة الفعلية لا من الرموز.
* المتبقي لا يكون سالبًا أبدًا؛ رسالة الحظر ثنائية اللغة.

## 8. Dashboard

* **Overview:** إنفاق اليوم/الأمس/الشهر، الطلبات، الرموز، دقائق المعلم، الطلبات الفاشلة،
  أعلى المستخدمين/الميزات/النماذج، نسبة الميزانية.
* **Daily report:** فلترة حسب التاريخ/المستخدم/الدور/الميزة/النموذج/الحالة.
* **Student usage:** الباقة والدقائق والاستخدام الشهري وآخر جلسة.
* **Export:** CSV (Excel/PDF كـ TODO).

## 9. API

نقاط النهاية تحت `/api/ai-usage/` مع صلاحيات: الطالب يرى استخدامه ودقائقه فقط (دون
التكلفة ما لم يُفعَّل الإعداد)، المعلّم يرى صفوفه فقط، الإدارة ترى كل شيء وتُعيد الحساب.

## 10. Scheduled Jobs

أوامر إدارة (مع نسخ Celery اختيارية): `aggregate_ai_usage_daily`،
`update_student_daily_limits`، `ai_usage_alerts`.

## 11. Privacy & Security

* لا تُخزَّن المحادثات الكاملة؛ مقاييس فقط.
* لا تُخزَّن مفاتيح الـ API ولا تظهر في السجلّات.
* الطالب لا يرى التكلفة الداخلية ما لم تُفعّلها الإدارة؛ الـ metadata مُنقّاة افتراضيًا.

## 12. Tests

| المجموعة | النتيجة |
|---|---|
| `ai_usage` (46 اختبارًا: models, cost, wrapper, limits, aggregation, api) | نجاح |
| `motivation` (يشمل هجرة الغلاف) | نجاح |
| `library` / `dictionary` (هجرة الغلاف) | نجاح |
| `tutor` + `placement` (regression، 237) | نجاح |
| `courses` / `core` (regression) | نجاح |
| `manage.py check` | نظيف |

## 13. أوامر الاختبار ونتائجها

* `test ai_usage` → 46 اختبارًا، OK.
* `test ai_usage motivation library dictionary` → 195 اختبارًا، OK.
* `test tutor placement` → 237 اختبارًا، OK.
* `test tutor courses placement core` → exit 0 (نجاح).
* `manage.py check` → "no issues".
* `makemigrations --check` → لا هجرات ناقصة.

## 14. المشاكل المتبقية

* **P1** — تكلفة جلسات realtime غير مرئية للخادم؛ تُسعَّر بالدقيقة وتُطابَق شهريًا مع الفاتورة.
* **P2** — بقية مواقع المكالمات (tutor/placement/challenge/content/media) مُجدوَلة للهجرة
  (موثّقة بالأسباب)؛ وجود جدولَي سجلّ مؤقتًا (`core` القديم + `ai_usage`) حتى اكتمال الهجرة.
* **P2** — تصدير Excel/PDF غير منفّذ بعد (CSV جاهز).
* **P3** — أسعار realtime/TTS تقديرية وتحتاج معايرة من الفاتورة الحقيقية.

## 15. القرار النهائي

**يحتاج إصلاحات بسيطة** — البنية التحتية (النماذج، الغلاف، التسعير، الحدود اليومية،
اللوحات، الـ API، المهام، الاختبارات، التوثيق) جاهزة للإنتاج وكل الاختبارات خضراء؛
المتبقّي هو إكمال هجرة بقية مواقع المكالمات تدريجيًا ومعايرة أسعار الصوت/الـ realtime.

## 16. توصية المرحلة التالية

* إكمال هجرة المواقع المُجدوَلة (Batch A/C) إلى الغلاف ثم تقاعد مُسجّل `core` القديم.
* بعد نجاح ذلك يمكن الانتقال إلى **Prompt 12B — Human Review QA Pass for 47 Topics**
  أو **Prompt 13 — First Approved Content Batch**.
* تذكير: لا نشر للمحتوى ولا توليد media بدون مراجعة بشرية.

# Onlenco — Final UAT Readiness & Gap List
# جاهزية القبول النهائية وقائمة الفجوات — Onlenco

_آخر تحديث: مرحلة 18.4C (توحيد). يجمّع تقارير 16.7C، 17.2–17.5، 18.0–18.4B._

وثائق مرجعية مفصّلة:
[Daily/Weekly](ONLENCO_DAILY_WEEKLY_UAT_READINESS.md) ·
[Beginner Journey](ONLENCO_BEGINNER_STUDENT_JOURNEY_UAT.md) ·
[AI Tutor + Course](ONLENCO_AI_TUTOR_BEGINNER_INTEGRATION_UAT.md) ·
[Browser/Mobile Manual QA Runbook](ONLENCO_BROWSER_MOBILE_MANUAL_QA_RUNBOOK.md) ·
[Production Media Sync](ONLENCO_PRODUCTION_MEDIA_SYNC_RUNBOOK.md) ·
[Deployment Readiness](ONLENCO_DEPLOYMENT_READINESS_RUNBOOK.md) ·
[UAT Deployment Dry-Run Checklist](ONLENCO_UAT_DEPLOYMENT_DRY_RUN_CHECKLIST.md).

---

## 1. Executive Summary

كورس المبتدئين (`onlenco-beginner` = 16 وحدة × 3 = **48 درسًا**) مكتمل ببنية
ووسائط معتمَدة ومرئية للطالب (48 غلافًا، 144 رسمًا، 288 سكربت صوت). رحلة الطالب
A0 الأساسية (لوحة → كورس → درس → تقدّم → اختبار يومي → بوّابة أسبوعية) مُختبَرة
E2E، ويعمل **AI Tutor** بجانبها دون كسر التقدّم أو حدود الاستخدام أو سياسة اللغة.
الاختبارات خضراء بالكامل وبلا migrations في مراحل الـsmoke الأخيرة.

**النظام جاهز لـUAT داخلي محدود. الإنتاج العام مُعلَّق (HOLD) حتى إغلاق
production blockers** (مزامنة الوسائط، مراقبة الاستخدام، QA متصفّح/صوت حقيقي،
runbook نشر).

---

## 2. UAT Go/No-Go Decision

| القرار | الحالة | السبب |
|---|---|---|
| **UAT داخلي محدود** | **GO ✅** | الرحلة الأساسية + AI Tutor + اليومي + البوّابة مختبَرة وخضراء |
| **إنتاج عام** | **HOLD ⛔** | production blockers مفتوحة (القسم 8) |

**الفرق:** UAT = مجموعة محدودة من المستخدمين/الفريق في بيئة مُراقَبة لاكتشاف مشاكل
التجربة الحقيقية (صوت/متصفّح/موبايل)، مع تحمّل وجود فجوات معروفة. الإنتاج العام =
انفتاح كامل يتطلّب وسائط على تخزين إنتاج، مراقبة استخدام، QA صوت/متصفّح حقيقي،
وrunbook نشر/نسخ احتياطي.

> القرار صالح لأن **check/tests خضراء**: tutor 261، daily_learning 130، courses 729.

---

## 3. What Is UAT Ready ✅

| المجال | الحالة | الإثبات |
|---|---|---|
| بنية كورس المبتدئين | جاهز | 16×3=48 درسًا (seed idempotent) |
| وسائط الطالب | جاهز | 48 غلاف + 144 رسم + 288 صوت معتمَدة؛ المعلّق محجوب بـ`is_student_visible` |
| رحلة الطالب A0 E2E | جاهز | `test_beginner_student_journey_e2e.py` (14) |
| تصحيح Daily Quiz الخلفي | جاهز | `daily_grading`؛ درجة بالصحّة؛ لا تسريب إجابة |
| حماية CEFR / A0 | جاهز | مطابقة دقيقة؛ A0 لا يرى >A0 |
| Weekly Review Gate | جاهز كـبوّابة | بطاقة بعد 3 دروس، زرّ معطَّل آمن، قراءة فقط |
| تكامل AI Tutor مع الكورس | جاهز | `test_beginner_ai_tutor_integration.py` (17)؛ لا يكسر التقدّم |
| حدود الاستخدام | جاهز | نص لا يخصم؛ صوت/مكالمة تخصم؛ لا double-bill؛ نفاد عربي آمن |
| فصل placement | جاهز | placement لا يخصم دقائق AI العادية |
| سياسة لغة A0 + تنقية | جاهز | عربي + قصير؛ إزالة provider/JSON/file؛ fallback عربي |

---

## 4. What Is Not Production Ready Yet ⚠️

- **Weekly Review** بوّابة/بطاقة فقط — **لا محرّك مراجعة أسبوعي كامل**.
- **listen_build** opt-in (`DAILY_LISTEN_BUILD_ENABLED=False`) ويحتاج `audio_url` حقيقي.
- **`media/` خارج git** — يحتاج مزامنة لتخزين الإنتاج (S3/خادم).
- **QA متصفّح/موبايل/صوت حقيقي** غير منفّذ (لا browser tooling؛ كله Django test client/mocks).
- **Real OpenAI/audio runtime QA** غير منفّذ (mock فقط).
- **production usage monitoring** للدقائق غير مفعّل.

---

## 5. Tested Student Journeys

1. **رحلة A0 الأساسية** (18.4A): لوحة → كورس → درس (وسائط معتمَدة فقط) → تقدّم →
   اختبار يومي (تصحيح خلفي، درجة بالصحّة) → بوّابة الأسبوع بعد 3 دروس → خروج/دخول
   بلا إعادة placement.
2. **رحلة AI Tutor المدمجة** (18.4B): كورس → درس → تقدّم → **AI Tutor شات (mock)** →
   عودة للكورس (تقدّم سليم) → اختبار يومي → بوّابة الأسبوع، مع فحص حدود نص/صوت/مكالمة،
   فصل placement، وسياسة A0/التنقية.

> القناة: **Django test client + mocks**. **Browser/Mobile QA الحقيقي مؤجَّل.**

---

## 6. Test Results

| الأمر | النتيجة |
|---|---|
| `manage.py check` | **clean** (0 issues) |
| `manage.py test tutor` | **261 OK** |
| `manage.py test daily_learning` | **130 OK** |
| `manage.py test courses` | **729 OK** |
| migrations في الـsmoke الأخير | **لا شيء** |

> placement/users/dashboard: مغطّاة ضمنيًا عبر رحلة الطالب (onboarding، dashboard،
> course_detail)؛ مجموعات اختبار تلك التطبيقات بالكامل **خارج نطاق** هذه المرحلة.

---

## 7. Known UAT Risks

- Browser/Mobile QA غير منفّذ (RTL، أجهزة صغيرة).
- Real microphone/audio permission QA غير منفّذ.
- Real OpenAI/audio runtime QA غير منفّذ (mock فقط).
- A0 Daily Quiz فيه **عنصر مصحَّح واحد** فقط (vocabulary/grammar/listening/speaking/
  motivation بلا إجابة).
- **drip sequencing** يحتاج فحصًا يدويًا (الاختبارات تفتح الدروس بـ`drip_enabled=False`).

---

## 8. Production Blockers

- [ ] مزامنة `media/` المعتمَد إلى تخزين الإنتاج.
- [ ] production usage monitoring للدقائق (خصم فعلي + منع double-bill تحت الحمل).
- [ ] Real OpenAI/audio runtime QA في بيئة آمنة.
- [ ] Browser/Mobile voice QA (مايك/أذونات/RTL).
- [ ] deployment runbook.
- [ ] backup/restore.
- [ ] monitoring/logging.
- [ ] تأكيد اكتمال payment/subscription confirmation (خارج نطاق الـsmoke الحالي).
- [ ] قرار `audio_url` لعناصر listen_build.
- [ ] (اختياري) محرّك Weekly Review كامل.
- [ ] نظافة مستودع: `test_db.sqlite3` متعقَّب في git بينما `.gitignore` يغطّي
      `db.sqlite3` فقط — يُفضَّل إزالته من التتبّع.

---

## 9. Manual UAT Checklist

### الطالب (Student)
- [ ] تسجيل/دخول.
- [ ] اختيار Beginner.
- [ ] فتح اللوحة.
- [ ] فتح كورس المبتدئين.
- [ ] فتح أول درس.
- [ ] تشغيل الصوت.
- [ ] رؤية الصور.
- [ ] إكمال الدرس.
- [ ] فتح الاختبار اليومي.
- [ ] إجابة صحيحة/خاطئة.
- [ ] التحقّق من الدرجة.
- [ ] إكمال 3 دروس.
- [ ] ظهور بطاقة مراجعة الأسبوع.
- [ ] فتح AI Tutor نصّي.
- [ ] **اختبار رسالة صوتية/مكالمة يدويًا في بيئة آمنة.**
- [ ] خروج ثم دخول مجددًا.

### الإدارة/المعلّم (Admin/Teacher)
- [ ] التحقّق من بنية الكورس.
- [ ] التحقّق من اعتماد الوسائط.
- [ ] التحقّق من تقدّم الطالب.
- [ ] التحقّق من نتائج الاختبار.
- [ ] التحقّق من سجلّات استخدام AI.
- [ ] التأكّد أن لا وسائط معلّقة/فاشلة تظهر للطالب.

---

## 10. Recommended Next Phases

1. **18.4D — Browser/Mobile Manual QA Runbook** (مايك/صوت/RTL/أجهزة).
2. **18.4E — Production Media Sync & Deployment Readiness** (مزامنة `media/`، runbook، backup، monitoring).
3. **18.5A — Payment/Subscription UAT** (إن لم تكن مغلقة).
4. **19.0 — Novels Module** أو **Mobile/PWA** لاحقًا.

---

## 10-b. Deployment Readiness Status (18.4E)

- ✅ **Production Media Sync runbook** أُنشئ ([رابط](ONLENCO_PRODUCTION_MEDIA_SYNC_RUNBOOK.md)) —
  المصدر المحلي معتمَد: **480 ملفًا** (48 غلاف + 144 رسم + 288 صوت)، **0 مفقود**، ~284 MB.
- ✅ **Deployment Readiness runbook** أُنشئ ([رابط](ONLENCO_DEPLOYMENT_READINESS_RUNBOOK.md)).
- ⛔ **الإنتاج ما زال HOLD** حتى يكتمل فعليًا:
  - [ ] مزامنة media الفعلية إلى تخزين الإنتاج (`media_data` volume).
  - [ ] أخذ نسخ احتياطية للإنتاج (DB + media).
  - [ ] Real OpenAI/audio runtime QA في بيئة آمنة.
  - [ ] Browser/Mobile QA على أجهزة حقيقية.
  - [ ] فحص/تفعيل مراقبة استخدام الدقائق.
  - [ ] تأكيد payment/subscription.

---

## 11. Release Notes Summary

- كورس مبتدئين A0 كامل (48 درسًا) بوسائط معتمَدة ومرئية.
- اختبار يومي بتصحيح خلفي ودرجة بالصحّة مع حماية CEFR.
- بوّابة مراجعة أسبوعية (بطاقة آمنة بعد 3 دروس).
- AI Tutor موحّد الحدود (نص مجاني، صوت/مكالمة بالدقائق، فصل placement، تنقية تقنية،
  سياسة لغة حسب CEFR).
- **جاهز لـUAT محدود؛ الإنتاج العام مُعلَّق حتى إغلاق blockers.**

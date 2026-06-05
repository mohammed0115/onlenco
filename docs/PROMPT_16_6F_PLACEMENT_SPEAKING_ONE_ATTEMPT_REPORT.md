# تقرير Prompt 16.6F — اختبار التحدث مرة واحدة فقط بدون خصم من دقائق AI Tutor

## 1. الملخص التنفيذي

- **ما المشكلة؟** كان اختبار تحديد المستوى الشفهي (المكالمة الصوتية المباشرة) يستهلك من رصيد دقائق "المعلّم الذكي" اليومية، وكان يُمنع/يُقطع عندما يكون الرصيد = 0. هذا غير منطقي لأن الطالب الجديد يؤدّي الاختبار أثناء التهيئة (Onboarding) قبل أي اشتراك أو دفع. كما لم يكن هناك ضابط يمنع تكرار اختبار التحدث.
- **ما السياسة الجديدة؟** اختبار التحدث أصبح **محاولة واحدة فقط مدى الحياة** لكل طالب، **منفصل تمامًا** عن رصيد دقائق المعلّم الذكي. الدراسة عبر المعلّم الذكي تبقى بالاشتراك المدفوع (5/10/20/30 — Bronze/Silver/Gold)، أما اختبار التحديد فمجاني ولمرة واحدة. إعادة الاختبار لا تتم إلا بقرار إداري مُدقّق.
- **هل الاختبار لا يخصم دقائق AI Tutor؟** نعم. لا يفحص رصيد المعلّم الذكي، ولا يخصم منه، ولا يُحظر عند نفاده، ولا يُظهر رسالة "انتهى رصيدك اليومي". ومع ذلك يُسجَّل الاستخدام كاملًا في `ai_usage` تحت `feature = placement_speaking` (وليس `ai_tutor`).

## 2. السياسة النهائية

- **محاولة واحدة فقط:** يحصل كل طالب على محاولة تحدّث صالحة واحدة. تُستهلك المحاولة بمجرد الإجابة عن سؤال واحد أو أكثر.
- **لا خصم من AI Tutor:** جلسة اختبار التحدث لا تمسّ `UserDailyQuota` ولا `FreeTrialUsage`، ولا ترتبط بخطط الاشتراك.
- **سقف زمني للمحاولة:** 7 دقائق كحد أقصى للمحاولة الواحدة (`PLACEMENT_SPEAKING_MAX_MINUTES_PER_ATTEMPT`).
- **بدء فاشل لا يُحسب:** إذا انقطع الاتصال قبل تسجيل أي إجابة → `failed_start` و`is_used_attempt=False` → يُسمح بإعادة البدء.
- **reset إداري فقط:** المحاولة المستهلكة لا تُعاد إلا عبر إجراء إداري يتطلّب سببًا ويُسجَّل في سجل التدقيق، **بدون حذف** أي سجل قديم.

### الإعدادات (config/settings/base.py)

```python
PLACEMENT_SPEAKING_ENABLED = True
PLACEMENT_SPEAKING_ONE_ATTEMPT_ONLY = True
PLACEMENT_SPEAKING_MAX_MINUTES_PER_ATTEMPT = 7
PLACEMENT_SPEAKING_ALLOW_ADMIN_RESET = True
PLACEMENT_SPEAKING_EST_COST_PER_MIN_USD = "0.30"  # لتقدير التكلفة في ai_usage فقط
```

## 3. الملفات المعدّلة

| File | Change | Reason |
|------|--------|--------|
| `config/settings/base.py` | إعدادات `PLACEMENT_SPEAKING_*` الجديدة | ضبط سياسة المحاولة الواحدة والسقف الزمني وتقدير التكلفة |
| `placement/models.py` | موديل جديد `PlacementSpeakingAttempt` | تتبّع المحاولة الواحدة + حقول التدقيق وإعادة الفتح |
| `placement/migrations/0009_placementspeakingattempt.py` | هجرة الموديل | إنشاء الجدول |
| `placement/services/speaking_quota.py` | خدمة السياسة (gate + lifecycle + reset) | المكان الوحيد لقراءة/كتابة سياسة اختبار التحدث |
| `placement/views.py` | بوابة المنع في `placement_voice_handoff` | عرض صفحة "مُقفل" قبل بدء مكالمة ثانية |
| `placement/admin.py` | تسجيل `PlacementSpeakingAttempt` (للقراءة) | رؤية المحاولات والتدقيق في Django admin |
| `templates/placement/speaking_locked.html` | صفحة "تم إكمال الاختبار" | رسالة ودّية + روابط النتيجة/اللوحة |
| `ai_usage/services/ai_client.py` | `log_realtime_session_start(feature=…)` | السماح بتسجيل بدء الجلسة تحت `placement_speaking` |
| `subscriptions/models.py` | خيار مصدر `placement_voice` على `AITutorSession` | تمييز جلسة الاختبار لمنع الخصم |
| `subscriptions/migrations/0012_alter_aitutorsession_source.py` | هجرة الخيار | اتساق حالة الهجرات |
| `subscriptions/services/session_service.py` | تخطّي الخصم عند `source == placement_voice` | عدم لمس رصيد المعلّم الذكي |
| `tutor/api/views.py` | `voice_call_session` (بوابة + فتح محاولة + سقف) و`voice_call_log` (إنهاء المحاولة + تسجيل `ai_usage`) | تطبيق السياسة على مسار المكالمة الفعلي |
| `templates/tutor/voice_call.html` | ملاحظة UX "مجاني — اختبار تحديد المستوى" + رفع نسخة JS | عدم إظهار تكلفة/رصيد للطالب |
| `static/js/ai_tutor_realtime.js` | تمرير رسالة الخادم لرموز منع الاختبار | عرض الرسالة الودّية عند المنع |
| `platform_admin/views.py` | إجراء `reset-placement-speaking` | إعادة الفتح الإدارية المُدقّقة |
| `platform_admin/templates/platform_admin/students/detail.html` | زر "إعادة فتح اختبار التحدث" + حقل السبب | تنفيذ reset من لوحة الإدارة |
| `placement/tests/test_speaking_quota.py` | 14 اختبارًا | تثبيت العقد |

## 4. منطق المحاولة

تحديد الحالة عند انتهاء المكالمة حسب عدد الأسئلة المُجاب عنها (عدد أدوار المستخدم في النص):

| الحالة | الشرط | `is_used_attempt` | المسار |
|--------|-------|-------------------|--------|
| `completed` | أجاب 5 أسئلة | True | صفحة النتيجة |
| `insufficient_answers` | أجاب 1–4 أسئلة | True | retry/نتيجة بديلة |
| `failed_start` | لم يُجب أي سؤال | **False** | يُسمح بإعادة البدء |
| `cancelled` | إلغاء صريح (محجوز) | حسب الإجابات | retry |
| `reset` | إعادة فتح إدارية | يُزال الحظر | يُسمح بمحاولة جديدة |

- **بوابة المنع:** يُحظر البدء فقط إذا وُجد صف `is_used_attempt=True` و`reset_at` فارغ (محاولة مستهلكة لم تُعاد). إعادة الفتح تختم `reset_at` فتُزيل الصف من مجموعة الحظر.
- **عدم التعليق:** عند أي إنهاء يُوجَّه الطالب إلى النتيجة أو retry ولا يبقى عالقًا في شاشة المكالمة (`result_route`).

## 5. AI Usage

- **feature:** `placement_speaking` فقط — لا يُسجَّل أبدًا تحت `ai_tutor` (مؤكَّد باختبار `test_placement_speaking_does_not... / creates_ai_usage_log...`).
- **cost:** `estimated_cost_usd = minutes × PLACEMENT_SPEAKING_EST_COST_PER_MIN_USD` (تقدير فقط؛ الفوترة الحقيقية تُسوّى شهريًا مقابل فاتورة المزوّد، مع `realtime_reconcile_required=true`).
- **duration:** يُسجَّل `ai_minutes_used` و`audio_input_seconds/audio_output_seconds`.
- **metadata:** `placement_attempt_id`, `placement_speaking_attempt_id`, `question_count_answered`, `ended_reason`, `is_used_attempt`.
- **الغلاف الموحّد:** كل التسجيل يمرّ عبر `ai_usage/services` (`log_realtime_session_start` / `usage_logger.log_success`) — لا اتصال مباشر بأي مزوّد (مؤكَّد باختبار `test_no_direct_ai_calls_outside_ai_usage_wrapper`). صفّان مفتاحهما `request_id` واحد (بداية + نهاية) فيُحدَّث نفس السجل.

## 6. Admin Reset

- **المكان:** بطاقة الطالب في مركز التحكّم → زر **«إعادة فتح اختبار التحدث»** مع حقل **سبب إلزامي**.
- **audit:** يُختم على الصف الحاجب: `reset_by` (المُنفِّذ) و`reset_at` (الوقت) و`reset_reason` (السبب) و`metadata.admin_reset=true`.
- **reason إلزامي:** السبب الفارغ يُرفض (`ResetError`).
- **لا حذف:** السجلات القديمة تبقى كما هي؛ إعادة الفتح تعمل بالختم فقط (لا تحذف ولا تفتح محاولات غير محدودة — محاولة واحدة لكل reset).
- **الصلاحية:** يتطلّب `CAP_STUDENTS_MANAGE`، ويمكن تعطيل الميزة عبر `PLACEMENT_SPEAKING_ALLOW_ADMIN_RESET=False`.

## 7. الاختبارات

`placement/tests/test_speaking_quota.py` — 14 اختبارًا، جميعها **ناجحة**:

| Test | Result |
|------|--------|
| test_placement_speaking_does_not_consume_ai_tutor_minutes | ✅ |
| test_placement_speaking_allows_when_ai_tutor_minutes_zero | ✅ |
| test_placement_speaking_creates_ai_usage_log_feature_placement_speaking | ✅ |
| test_placement_speaking_one_attempt_only_after_completed | ✅ |
| test_placement_speaking_one_attempt_used_after_any_answer | ✅ |
| test_failed_start_without_answers_does_not_consume_attempt | ✅ |
| test_second_attempt_blocked_with_friendly_message | ✅ |
| test_admin_can_reset_placement_speaking_attempt | ✅ |
| test_reset_requires_reason_and_audit | ✅ |
| test_after_admin_reset_student_can_attempt_again | ✅ |
| test_regular_ai_tutor_still_consumes_daily_minutes | ✅ |
| test_regular_ai_tutor_still_blocks_when_minutes_finished | ✅ |
| test_auto_end_redirects_to_result_or_retry | ✅ |
| test_no_direct_ai_calls_outside_ai_usage_wrapper | ✅ |

نتائج المجموعات الكاملة:

```
placement : Ran 74 tests — OK
tutor     : Ran 191 tests — OK
ai_usage  : Ran 91 tests — OK
accounts  : Ran 96 tests — OK
check     : System check identified no issues (0 silenced)
```

## 8. القرار النهائي

**✅ Placement speaking one-attempt policy ready**

- محاولة واحدة مدى الحياة، منفصلة تمامًا عن دقائق المعلّم الذكي، مع تسجيل كامل في `ai_usage`، وإعادة فتح إدارية مُدقّقة بلا حذف.
- جميع الاختبارات الـ14 خضراء، والمجموعات الأربع تمرّ، و`check` نظيف.

### خطوات النشر (يقوم بها المستخدم)

```bash
cd /opt/onlenco && sudo bash scripts/update.sh   # git pull + migrate + seed + collectstatic + restart
```

> الهجرتان المطلوبتان على الإنتاج: `subscriptions.0012_alter_aitutorsession_source` و`placement.0009_placementspeakingattempt`.

> **مهم:** لا تبدأ Quiz Builder أو Marketplace قبل نشر هذا الإصلاح وتجربته على الإنتاج.

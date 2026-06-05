# تقرير Prompt 16.6F — فصل مكالمة تحديد المستوى عن مكالمة AI Tutor

## 1. الملخص التنفيذي

- **ما المشكلة؟** كان نوعا المكالمة (اختبار تحديد المستوى الشفهي، ومكالمة المعلّم الذكي العادية) يمرّان بنفس منطق الحصة: اختبار التحديد كان يخصم من رصيد دقائق المعلّم الذكي اليومي ويُمنع عند نفاده — رغم أن الطالب الجديد يؤدّيه أثناء التهيئة قبل أي اشتراك. كما لم يكن هناك ضابط يمنع تكرار اختبار التحدّث.
- **ما الفرق بين المكالمتين؟**
  - **Placement Speaking Call** = اختبار تقييم لمرة واحدة مدى الحياة، مجاني، لا يمسّ رصيد المعلّم الذكي، وإعادته إدارية فقط.
  - **Regular AI Tutor Call** = تدريب وممارسة، مرتبط بالخطة المدفوعة، يخصم من رصيد دقائق اليوم ويُمنع عند نفاده.
- **ماذا تم إصلاحه؟** فُصل المساران تمامًا على مستوى: فحص الحصة، خصم الدقائق، نوع جلسة `AITutorSession`، و`feature` في `AIUsageLog`. اختبار التحديد لا يلمس `UserDailyQuota`/`FreeTrialUsage` أبدًا، بينما يبقى المعلّم الذكي العادي محكومًا بدقائق الخطة المتراكمة يوميًا.

## 2. السياسة النهائية

### Placement Speaking Call
- محاولة **واحدة مدى الحياة** لكل طالب (`PlacementSpeakingAttempt.is_used_attempt`).
- لا تفحص ولا تخصم من رصيد المعلّم الذكي، ولا تُحظر عند الرصيد = 0.
- سقف 7 دقائق للمكالمة (حماية تكلفة + منع التعليق).
- بدء فاشل دون إجابات → `failed_start` لا يُحسب محاولة (يُعاد). أي إجابة فأكثر → محاولة مستخدمة.
- 5 إجابات → `completed` وانتقال للنتيجة.
- تُسجَّل في `AIUsageLog` بـ `feature = placement_speaking`.
- الإعادة إدارية فقط بسبب وتدقيق.

### Regular AI Tutor Call
- يُفحص قبل البدء مقابل خطة الطالب: `allowed_minutes = plan.ai_tutor_daily_minutes`.
- الرصيد اليومي = مجموع كل جلسات المعلّم الذكي في نفس اليوم (`UserDailyQuota.ai_tutor_seconds_used`).
- عند `remaining <= 0` تُمنع المكالمة (402) برسالة واضحة.
- بعد المكالمة يُحدَّث المستخدَم/المتبقّي، وتُسجَّل في `AIUsageLog` بـ `feature = ai_tutor`.
- أمثلة: Bronze=2 د/يوم، Silver=5 د/يوم، Gold=7 د/يوم، وأي خطة 10/20/30 → نفس الرقم سقفًا يوميًا تراكميًا.

## 3. الملفات المعدّلة

| File | Change | Reason |
|------|--------|--------|
| `config/settings/base.py` | إعدادات `PLACEMENT_SPEAKING_*` (ENABLED / ONE_ATTEMPT_ONLY / MAX_MINUTES / ALLOW_ADMIN_RESET / EST_COST) | ضبط سياسة الاختبار |
| `placement/models.py` | موديل `PlacementSpeakingAttempt` | تتبّع المحاولة الواحدة + التدقيق |
| `placement/migrations/0009_placementspeakingattempt.py` | هجرة الموديل | إنشاء الجدول |
| `placement/services/speaking_quota.py` | بوابة المحاولة الواحدة + lifecycle + reset إداري | المكان الوحيد لسياسة الاختبار |
| `placement/views.py` | بوابة المنع في `placement_voice_handoff` | صفحة "مُقفل" قبل مكالمة ثانية |
| `placement/admin.py` | تسجيل `PlacementSpeakingAttempt` للقراءة | رؤية المحاولات في admin |
| `templates/placement/speaking_locked.html` | صفحة "تم إكمال الاختبار" | رسالة ودّية |
| `ai_usage/services/ai_client.py` | `log_realtime_session_start(feature=…)` | تسجيل بدء الجلسة تحت الميزة الصحيحة |
| `subscriptions/models.py` | خيار مصدر `placement_voice` على `AITutorSession` | تمييز جلسة الاختبار لمنع الخصم |
| `subscriptions/migrations/0012_alter_aitutorsession_source.py` | هجرة الخيار | اتساق الهجرات |
| `subscriptions/services/session_service.py` | تخطّي الخصم عند `source == placement_voice` | عدم لمس رصيد المعلّم الذكي |
| `tutor/api/views.py` | فصل مساري `voice_call_session` و`voice_call_log` (بوابة الاختبار + تسجيل placement_speaking) و(فحص الخطة + تسجيل ai_tutor مع metadata) + رسالة النفاد المحلّاة | تطبيق الفصل على مسار المكالمة |
| `templates/tutor/voice_call.html` | ملاحظة UX للاختبار + رفع نسخة JS | إخفاء التكلفة/الرصيد عن طالب الاختبار |
| `static/js/ai_tutor_realtime.js` | عرض رسالة الخادم لرموز المنع ونفاد الرصيد | رسائل واضحة بالعربية |
| `platform_admin/views.py` | إجراء `reset-placement-speaking` المُدقّق | إعادة الفتح الإدارية |
| `platform_admin/templates/platform_admin/students/detail.html` | زر «إعادة فتح اختبار التحدث» + حقل السبب | تنفيذ reset من اللوحة |
| `placement/tests/test_speaking_quota.py` | 23 اختبارًا (placement + regular + ai_usage) | تثبيت العقد |

## 4. منطق Placement Speaking

| الحالة | الشرط | `is_used_attempt` | المسار |
|--------|-------|-------------------|--------|
| `completed` | 5 إجابات | True | النتيجة |
| `insufficient_answers` | 1–4 إجابات | True | retry |
| `failed_start` | 0 إجابة | **False** | يُعاد البدء |
| `reset` | إعادة فتح إدارية | يُزال الحظر | محاولة جديدة |

- **لا خصم:** الجلسة `source="placement_voice"` فلا يستدعي `end_session` خصم الدقائق.
- **بوابة المنع:** يُحظر فقط إن وُجد صف `is_used_attempt=True` و`reset_at` فارغ.
- **reset إداري:** يختم `reset_by/reset_at/reset_reason` ويُزيل الحظر — بلا حذف.

## 5. منطق AI Tutor العادي

- **حسب الخطة:** `daily_ai_tutor_limit_seconds = plan.ai_tutor_daily_minutes × 60`.
- **دقائق يومية تراكمية:** كل جلسة تزيد `UserDailyQuota.ai_tutor_seconds_used` في نفس بطاقة اليوم (تأكيد: `test_regular_ai_tutor_accumulates_minutes_across_sessions_same_day`).
- **المنع:** عند `effective_ai_tutor_remaining <= 0` تُرجع الجلسة 402 + رسالة:
  > «لقد انتهى رصيدك اليومي من دقائق المعلم الذكي. يمكنك المتابعة غدًا أو ترقية الباقة.»
- **التحديث بعد المكالمة:** `end_session` يخصم ويحدّث المتبقّي؛ ويُسجَّل snapshot الخطة في `AIUsageLog`.

## 6. AIUsageLog

| | Placement Speaking | Regular AI Tutor |
|---|---|---|
| `feature` | `placement_speaking` | `ai_tutor` |
| `role` | student | student |
| `ai_minutes_used` | مدة المكالمة | مدة المكالمة |
| `estimated_cost_usd` | minutes × سعر/دقيقة | (يُسوّى شهريًا) |
| `metadata` | `placement_attempt_id`, `placement_speaking_attempt_id`, `question_count_answered`, `ended_reason`, `is_used_attempt` | `ai_tutor_session_id`, `plan_name`, `allowed_minutes`, `used_minutes_after`, `remaining_minutes_after`, `quota_source` |

- **عدم الخلط:** مؤكَّد بـ `test_placement_and_ai_tutor_have_different_features` و`test_no_direct_ai_calls_outside_ai_usage_wrapper`. كل التسجيل يمرّ عبر غلاف `ai_usage` فقط.

## 7. تجربة المستخدم

- **صفحة الاختبار:** شارة «مجاني — اختبار تحديد المستوى» بدل عدّاد الدقائق (لا تظهر تكلفة).
- **إعادة الاختبار بعد الاستخدام:** «لقد أكملت اختبار التحدث لتحديد المستوى من قبل. إذا كنت تعتقد أن هناك مشكلة، تواصل مع الإدارة لإعادة فتح الاختبار.»
- **نفاد رصيد AI Tutor العادي:** «لقد انتهى رصيدك اليومي من دقائق المعلم الذكي. يمكنك المتابعة غدًا أو ترقية الباقة.»

## 8. الاختبارات

`placement/tests/test_speaking_quota.py` — 23 اختبارًا، جميعها **ناجحة**:

| Test | Result |
|------|--------|
| test_placement_speaking_does_not_consume_ai_tutor_minutes | ✅ |
| test_placement_speaking_allows_when_ai_tutor_minutes_zero | ✅ |
| test_placement_speaking_creates_ai_usage_log_feature_placement_speaking | ✅ |
| test_placement_speaking_one_attempt_only_after_completed | ✅ |
| test_placement_speaking_one_attempt_used_after_any_answer | ✅ |
| test_failed_start_without_answers_does_not_consume_attempt | ✅ |
| test_second_placement_attempt_blocked | ✅ |
| test_admin_can_reset_placement_speaking_attempt | ✅ |
| test_reset_requires_reason_and_audit | ✅ |
| test_after_admin_reset_student_can_attempt_again | ✅ |
| test_auto_end_redirects_to_result_or_retry | ✅ |
| test_regular_ai_tutor_consumes_daily_plan_minutes | ✅ |
| test_regular_ai_tutor_uses_plan_allowed_minutes | ✅ |
| test_regular_ai_tutor_blocks_when_daily_minutes_finished | ✅ |
| test_regular_ai_tutor_accumulates_minutes_across_sessions_same_day | ✅ |
| test_regular_ai_tutor_does_not_use_placement_attempt_quota | ✅ |
| test_bronze_plan_allows_only_2_minutes_if_configured | ✅ |
| test_silver_plan_allows_only_5_minutes_if_configured | ✅ |
| test_gold_plan_allows_only_7_minutes_if_configured | ✅ |
| test_placement_and_ai_tutor_have_different_features | ✅ |
| test_ai_usage_log_metadata_for_placement | ✅ |
| test_ai_usage_log_metadata_for_regular_ai_tutor | ✅ |
| test_no_direct_ai_calls_outside_ai_usage_wrapper | ✅ |

نتائج المجموعات الكاملة:

```
placement     : Ran 83 tests — OK
tutor         : Ran 191 tests — OK
ai_usage      : Ran 91 tests — OK
accounts      : Ran 96 tests — OK
subscriptions : Ran 118 tests — OK
check         : System check identified no issues (0 silenced)
makemigrations --check : No changes detected
```

## 9. القرار النهائي

**✅ Placement and AI Tutor calls separated correctly**

- اختبار التحديد: محاولة واحدة مدى الحياة، مجاني، منفصل تمامًا عن دقائق المعلّم الذكي، إعادته إدارية مُدقّقة.
- المعلّم الذكي العادي: محكوم بدقائق الخطة المتراكمة يوميًا، يُمنع عند النفاد برسالة واضحة.
- `feature` لا يختلط أبدًا، وكل الاستخدام مُسجَّل عبر غلاف `ai_usage`. جميع الاختبارات والمجموعات خضراء و`check` نظيف.

### النشر (يقوم به المستخدم)

```bash
cd /opt/onlenco && sudo bash scripts/update.sh
```

> الهجرتان: `subscriptions.0012_alter_aitutorsession_source` و`placement.0009_placementspeakingattempt`.
>
> **مهم:** لا تبدأ Quiz Builder أو Marketplace قبل نشر هذا الإصلاح وتجربته.

# Onlenco — AI Tutor + Beginner Course Integration: UAT
# تكامل المساعد الذكي مع كورس المبتدئين — اختبار القبول (UAT)

_آخر تحديث: مرحلة 18.4B._

ملخّص smoke مدمج يثبت أن **AI Tutor** يعمل بجانب **Beginner Course** دون كسر
الوصول/التقدّم/الاختبار اليومي/البوّابة الأسبوعية/حدود الاستخدام/سياسة اللغة.
مُغطّى بـ
[tutor/tests/test_beginner_ai_tutor_integration.py](../tutor/tests/test_beginner_ai_tutor_integration.py)
(17 اختبارًا). هذه الوثيقة **ملخّص UAT** وليست بديلًا عن الاختبارات.

> **بلا API حقيقي:** الـ`chat` seam مُموَّه (mock)؛ الاستخدام عبر الـfacade القائم.

---

## 1. السيناريو المُختبَر (Scenario Tested)

طالب A0 (`complete_beginner_onboarding` + اشتراك فعّال بدقائق AI) يمرّ بـ:
لوحة → كورس المبتدئين → درس (وسائط معتمَدة) → تعليم تقدّم → **AI Tutor شات** →
العودة للكورس → الاختبار اليومي → بوّابة الأسبوع، مع فحص حدود الاستخدام
(نص/صوت/مكالمة)، فصل placement، وسياسة اللغة/التنقية لـA0.

---

## 2. ما الذي نجح (What Passed) ✅

| المجال | البند | الإثبات (اختبار) |
|---|---|---|
| تكامل | كورس → AI Tutor → كورس بلا كسر | `test_course_then_tutor_then_course_roundtrip` |
| تقدّم | AI Tutor لا يكسر `CourseLessonProgress` | `test_ai_tutor_does_not_break_progress` |
| يومي | الاختبار اليومي يعمل بعد AI Tutor | `test_daily_quiz_works_after_ai_tutor` |
| أسبوعي | البطاقة تظهر بعد 3 دروس مع AI Tutor | `test_weekly_gate_after_three_lessons_with_tutor` |
| حدود | الشات النصي لا يخصم دقائق | `test_text_chat_does_not_deduct_minutes` |
| حدود | الرسالة الصوتية تخصم | `test_regular_voice_message_deducts` |
| حدود | المكالمة تخصم | `test_regular_call_deducts` |
| حدود | finalize مزدوج لا يخصم مرتين | `test_double_finalize_does_not_double_deduct` |
| حدود | النفاد ⇒ حالة عربية آمنة | `test_exhausted_usage_returns_arabic_state` |
| فصل | placement لا يخصم دقائق AI | `test_placement_voice_does_not_deduct_regular_minutes` |
| فصل | الاختبار اليومي لا يخصم دقائق AI | `test_daily_quiz_does_not_deduct_tutor_minutes` |
| لغة | سياسة A0 (عربي + قصير + ar_primary) | `test_a0_language_policy_is_beginner_friendly` |
| لغة | A1/A2/B1 لا تتداخل مع A0 | `test_levels_do_not_bleed_into_a0` |
| لغة | افتتاح المكالمة لـA0 بسيط بلا token تقني | `test_a0_call_opening_is_simple` |
| تنقية | إزالة provider/JSON/file/`___` | `test_sanitization_strips_technical_artifacts` |
| تنقية | مدخل تقني بالكامل ⇒ fallback عربي | `test_all_technical_input_falls_back_to_arabic` |
| عزل | الشات لا ينشئ/يغيّر خطة يومية | `test_chat_does_not_create_or_alter_daily_plan` |

---

## 3. ما الذي أُصلح (What Was Fixed)

- **لا إصلاحات.** الـsmoke لم يكشف أي bug حاجب؛ لم تُمَسّ AI usage limits ولا
  CourseLessonProgress ولا Daily grading ولا Weekly ولا media ولا placement.
  لا migration.

---

## 4. ما تبقّى كـUAT Risk

- **Browser/Mobile voice QA مؤجَّل**: تشغيل المايك/الصوت الحقيقي والمكالمة الحيّة في
  المتصفّح/الموبايل لم يُختبَر آليًا (لا browser tooling). يحتاج فحصًا يدويًا.
- **Real OpenAI/audio runtime QA مؤجَّل**: الاستجابة الحقيقية (نص/تفريغ/TTS) لم
  تُستدعَ في الاختبارات (mock فقط)؛ يحتاج بيئة آمنة بمفاتيح حقيقية.
- خطة A0 بعنصر quiz واحد مصحَّح (موروث من 18.4A).
- التقاط مدّة الصوت الفعلية في الإنتاج يعتمد على الواجهة؛ يحتاج مراقبة.

---

## 5. Production Blockers

- [ ] **Production usage monitoring مطلوب**: رصد الخصم الفعلي للدقائق (صوت/مكالمة)
      ومنع double-bill تحت الحمل الحقيقي.
- [ ] Real OpenAI/audio runtime QA في بيئة آمنة (مفاتيح، حدود معدّل، أخطاء الشبكة).
- [ ] Browser/Mobile voice QA (مايك، أذونات، RTL، أجهزة صغيرة).
- [ ] مزامنة `media/` المعتمَد (موروث) + قرار listen_build.

---

## 6. Manual QA Checklist (مختصر)

- [ ] طالب A0: لوحة → كورس → درس (صوت/صورة يعملان) → AI Tutor شات يردّ.
- [ ] ردّ A0 بالعربية + إنجليزية بسيطة، **بلا أسماء مزوّد/JSON/أسماء ملفات**.
- [ ] الشات النصي لا ينقص عدّاد الدقائق في الواجهة.
- [ ] رسالة صوتية/مكالمة تنقص العدّاد بشكل صحيح؛ إعادة الإرسال لا تخصم مرتين.
- [ ] نفاد الدقائق ⇒ رسالة عربية آمنة «انتهى وقت المساعد الذكي…» بلا تعطّل.
- [ ] مكالمة placement لا تنقص دقائق AI Tutor العادية.
- [ ] بعد AI Tutor: العودة للكورس، التقدّم سليم، `/daily/` يعمل، بطاقة الأسبوع تظهر.
- [ ] فحص المايك/الصوت/المكالمة الحيّة على موبايل (RTL).

---

## 7. ملاحظة صريحة

- **Browser/Mobile voice QA مؤجَّل.**
- **Real OpenAI/audio runtime QA مؤجَّل / يحتاج بيئة آمنة.**
- **Production usage monitoring مطلوب قبل الإطلاق.**

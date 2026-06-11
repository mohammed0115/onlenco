# Onlenco — Beginner (A0) Student Journey: UAT
# رحلة الطالب المبتدئ (A0) — اختبار القبول (UAT)

_آخر تحديث: مرحلة 18.4A._

ملخّص E2E smoke لرحلة طالب Beginner الأساسية، مُغطّى بـ
[courses/tests/test_beginner_student_journey_e2e.py](../courses/tests/test_beginner_student_journey_e2e.py).
هذه الوثيقة **ملخّص UAT** وليست بديلًا عن الاختبارات.

---

## 1. السيناريو المُختبَر (Scenario Tested)

طالب جديد عبر onboarding المبتدئ (`complete_beginner_onboarding` → A0،
`beginner_start`, `onboarding_completed=True`, اشتراك فعّال)، ثم:

1. فتح **لوحة الطالب** (`dashboard`).
2. فتح **كورس المبتدئين** `onlenco-beginner` (16 وحدة × 3 = 48 درسًا، A0 world).
3. فتح **أول درس** (`lesson_detail`) وخطوة الدرس (`lesson_step`).
4. التحقّق من **الوسائط**: الغلاف والصوت المعتمَدان يظهران؛ الوسائط
   `needs_review` لا تصل للطالب.
5. **تعليم تقدّم الدرس** (`mark_lesson_complete`) → إنشاء `CourseLessonProgress`.
6. **الاختبار اليومي** `/daily/`: فتح، إجابة صحيحة/خاطئة بتصحيح من الخادم، درجة بالصحّة.
7. **بوّابة مراجعة الأسبوع**: تظهر فقط بعد إكمال 3 دروس، بزرّ معطَّل آمن.
8. **توافق المسارات**: خروج/دخول لا يُعيد إجبار placement؛ A0 يوصي بمستويات المبتدئ.

---

## 2. ما الذي نجح (What Passed) ✅

| # | البند | الإثبات (اختبار) |
|---|---|---|
| 1 | A0 يفتح لوحة الطالب | `test_a0_student_opens_dashboard` |
| 2 | A0 يفتح كورس المبتدئين (A0 world) | `test_a0_student_opens_beginner_course` |
| 3 | A0 يفتح أول درس | `test_a0_student_opens_first_lesson` |
| 4 | الغلاف + الصوت المعتمَدان يظهران | `test_lesson_step_shows_approved_cover_and_audio` |
| 5 | الوسائط `needs_review` لا تظهر | `test_lesson_step_hides_pending_media` |
| 6 | إكمال الدرس ينشئ `CourseLessonProgress` | `test_completing_lesson_creates_progress` |
| 7 | الاختبار اليومي يفتح لـA0 | `test_daily_quiz_opens_for_a0` |
| 8 | تصحيح خلفي (صحيح/خطأ) بلا تسريب الإجابة | `test_daily_quiz_answer_flow_backend_grading` |
| 9 | الدرجة بالصحّة لا بالإكمال | `test_daily_quiz_score_is_correctness_based` |
| 10 | بطاقة الأسبوع مخفية قبل 3 دروس | `test_weekly_card_hidden_before_three_lessons` |
| 11 | بطاقة الأسبوع تظهر آمنة (معطَّلة، بلا رابط) بعد 3 | `test_weekly_card_visible_and_safe_after_three_lessons` |
| 12 | عرض البطاقة لا يغيّر التقدّم | `test_weekly_card_does_not_change_progress` |
| 13 | خروج/دخول لا يُعيد إجبار placement | `test_logout_login_does_not_force_placement` |
| 14 | A0 يوصي بمستويات المبتدئ | `test_a0_routing_recommends_beginner` |

---

## 3. ما الذي أُصلح (What Was Fixed)

- **لا إصلاحات مطلوبة.** الرحلة لم تكشف أي bug حاجب: المسارات، الوسائط
  (المحميّة بـ`is_student_visible`)، التقدّم، الاختبار اليومي، وبوّابة الأسبوع
  كلّها سليمة. لم تُجرَ migration ولم تُمَسّ media/grading/AI Tutor/placement.

---

## 4. ما تبقّى كـUAT Risk

- **A0 plan فيه عنصر quiz واحد قابل للتصحيح** (vocabulary/grammar/listening/
  speaking/motivation بلا `correct_answer`). التصحيح حقيقي على هذا العنصر؛ لكن
  تجربة "عدة أسئلة مصحَّحة" تتحقّق فعليًا في A1+ — يُنصح بمراجعة منتَج لتنوّع A0.
- **QA متصفّح/موبايل حقيقي مؤجَّل**: لا Playwright/browser tooling في المشروع؛
  هذه الرحلة عبر Django test client. RTL والأجهزة الصغيرة تحتاج فحصًا يدويًا.
- **Weekly Review بوّابة فقط** (زر «قريبًا» معطَّل) — لا محرّك/صفحة مراجعة فعلية.
- **drip**: الاختبار يفتح الدروس مع `drip_enabled=False`؛ في الإنتاج يتحقّق
  التتابع اليومي — يُفحَص يدويًا أن فتح الدروس بالتسلسل لا يكسر التنقّل.

---

## 5. Production Blockers

- [ ] رفع/مزامنة `media/` المعتمَد إلى تخزين الإنتاج (خارج git).
- [ ] قرار/إعداد `DAILY_LISTEN_BUILD_ENABLED` + `audio_url` حقيقي (إن فُعّل).
- [ ] QA متصفّح/موبايل موسّع (RTL، أجهزة صغيرة، تتابع drip حقيقي).
- [ ] (اختياري) محرّك Weekly Review فعلي إن أُريد تجاوز «البوّابة فقط».

---

## 6. Manual QA Checklist (مختصر)

- [ ] دخول طالب A0 → لوحة → كورس المبتدئين تظهر بصورها.
- [ ] فتح أول درس → الغلاف + الصوت يعملان، لا أيقونة/رابط مكسور، لا نص تقني.
- [ ] التنقّل بين خطوات الدرس بلا تعطّل.
- [ ] إكمال الدرس → يُسجَّل التقدّم (شارة/حالة محدّثة).
- [ ] `/daily/` → 6 عناصر A0، إجابة صحيحة وخاطئة → feedback من الخادم.
- [ ] إكمال 3 دروس في الوحدة الأولى → ظهور بطاقة «مراجعة الأسبوع» معطَّلة.
- [ ] خروج ثم دخول → العودة للوحة/الكورس مباشرة بلا إعادة placement.
- [ ] فحص RTL على شاشة موبايل صغيرة.

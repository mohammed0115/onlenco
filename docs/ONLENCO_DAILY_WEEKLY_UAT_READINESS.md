# Onlenco — Daily Quiz & Weekly Review: UAT Readiness
# جاهزية القبول (UAT) — الاختبار اليومي ومراجعة الأسبوع

_آخر تحديث: مرحلة 18.3E._

هذه الوثيقة تلخّص جاهزية **Daily Quiz** و**Weekly Review Gate** لاختبار القبول
(UAT)، وما تبقّى قبل الإنتاج. مرجعية: التقارير 18.3A → 18.3E.

---

## 1. ما هو جاهز الآن (UAT-Ready) ✅

| المجال | الحالة | الإثبات |
|---|---|---|
| **تصحيح Daily Quiz من الخادم** | جاهز | `daily_grading.grade_item`؛ `complete_item` يصحّح خلفيًا، لا يثق بالواجهة |
| **إخفاء correct_answer** | جاهز | لا `data-quiz-target`/`-word-order-target`/`-writing-target`؛ لا placeholder للإجابة |
| **الدرجة بالصحّة** | جاهز | `complete_plan` = correct/graded×100 مع fallback للقديم |
| **حماية CEFR / A0** | جاهز | `Profile.cefr_level` مصدر الحقيقة؛ A0 لا يرى >A0؛ مطابقة دقيقة في الـselector |
| **listen_build_sentence** | جاهز (تجريبيًا) | `word_order + metadata.listen_build`؛ A1+ فقط؛ تصحيح tokens خلفي |
| **Daily UI smoke** | جاهز | صفحة `/daily/` 200، إرسال خلفي، feedback من الخادم |
| **Weekly Review Gate (قراءة فقط)** | جاهز | `weekly_review_gate.should_show_weekly_review`؛ بعد 3 دروس؛ لا يكتب progress |
| **Weekly Review card** | جاهز كـعرض | بطاقة في course detail بزرّ معطَّل آمن «المراجعة قريبًا» |
| **عزل CourseLessonProgress** | جاهز | Daily/Weekly لا يكتبان progress (مثبت) |
| **Beginner media (طالب)** | مغلق | 192/192 صورة، 288 صوت معتمَدة ومرئية؛ hero/cover محميّ بـis_student_visible |

---

## 2. ليس Production-Ready بعد ⚠️

- **Weekly Review** بطاقة/بوّابة فقط — **لا يوجد Weekly Assessment engine** كامل ولا
  صفحة مراجعة فعلية بعد (الزر معطَّل «قريبًا»).
- **listen_build** **غير مفعّل عالميًا** (`DAILY_LISTEN_BUILD_ENABLED=False`)؛ يُفعَّل
  عبر الإعداد عند الجاهزية.
- listen_build يعتمد TTS للجملة عبر `data-listen-src`؛ **يُفضَّل `audio_url` حقيقي**
  لتجربة استماع أنظف وبلا أي تمثيل للإجابة في مصدر الصفحة.
- **مزامنة media للإنتاج مطلوبة**: مجلّد `media/` خارج git؛ يجب رفع الصور/الأصوات
  المعتمَدة إلى تخزين الإنتاج (S3/الخادم) قبل الإطلاق.
- **QA متصفّح/موبايل أوسع** لاحقًا (الحالي عبر Django test client، لا Playwright).

---

## 3. سيناريوهات UAT المقترحة

1. **A0 يومي**: طالب Beginner → `/daily/` → 6 عناصر A0 مناسبة → إجابة صحيحة/خاطئة →
   feedback من الخادم → إنهاء → درجة مفهومة. (تأكّد: لا أسئلة >A0، لا إجابة مكشوفة.)
2. **A1 + listen_build (إعداد تجريبي)**: تفعيل الإعداد → عنصر استماع وبناء جملة →
   ترتيب صحيح = صحيح، خاطئ = خطأ.
3. **حماية A0**: حتى مع تفعيل الإعداد، A0 لا يرى listen_build.
4. **Weekly gate**: إكمال 3 دروس في وحدة → ظهور بطاقة «مراجعة الأسبوع جاهزة»؛ قبلها
   لا تظهر؛ الزر معطَّل لا يكسر التنقّل.
5. **عزل التقدّم**: لا الـDaily ولا البطاقة يغيّران `CourseLessonProgress`.
6. **توافق خلفي**: خطة قديمة بلا درجات → الدرجة = نسبة الإكمال (لا كسر).

---

## 4. Production Blockers (قبل الإطلاق)

- [ ] رفع/مزامنة `media/` المعتمَد إلى تخزين الإنتاج (الصور/الأصوات ليست في git).
- [ ] قرار تفعيل `DAILY_LISTEN_BUILD_ENABLED` للإنتاج + توفير `audio_url` لعناصر الاستماع.
- [ ] بناء صفحة/محرّك Weekly Review فعلي إن أُريد تجاوز «البوّابة فقط» (اختياري للإطلاق الأول).
- [ ] QA متصفّح/موبايل موسّع (RTL، الأجهزة الصغيرة).

## 5. Deferred (مؤجَّل، غير حاجب)

- Weekly Assessment engine كامل (أسئلة/درجات/تقدّم أسبوعي).
- `audio_url` حقيقي لكل listen_build بدل TTS.
- ربط Daily/Weekly بتحليلات أعمق ولوحة معلّم.

---

## 6. خلاصة الجاهزية

- **Daily Quiz**: **جاهز لـUAT.**
- **Weekly Review**: **جاهز لـUAT كـبوّابة/عرض فقط** (ليس اختبارًا أسبوعيًا كاملًا).
- **بلا blocker قبل UAT.** Blockers الإنتاج: مزامنة media + قرار listen_build (القسم 4).

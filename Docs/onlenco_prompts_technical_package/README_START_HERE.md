# حزمة برومبتات Onlenco التنفيذية

هذه الحزمة مخصصة لتحويل سيناريو Onlenco إلى مشروع برمجي احترافي قابل للتنفيذ على Django + DRF + Celery + PostgreSQL.

## لماذا هذه الحزمة؟

لأن Onlenco ليست مجرد منصة دروس، بل منصة تعلم إنجليزي ذكية تعتمد على:

- اختبار تحديد مستوى كتابي وشفهي.
- AI Tutor بالصوت والنص.
- شخصية AI Avatar للحديث الشفهي.
- Learning Profile لكل طالب.
- CEFR Mapping لكل محتوى واختبار.
- Adaptive Learning حسب الأخطاء.
- Gamification لجعلها لعبة تعليمية.
- Behavioral Analytics لمعرفة نشاط الطالب وخطر الانقطاع.
- Smart Motivation لإرسال رسائل تشجيع ذكية.
- Academic Admin لمتابعة الطلاب.
- Finance Admin لمراجعة المدفوعات.
- Weekly English Club للمخاطبة الجماعية.
- Digital Library للقصص والفيديوهات والمفردات.

## طريقة الاستخدام

1. افتح الملف `00_MASTER_EXECUTION_ORDER.md`.
2. نفذ البرومبتات بالترتيب.
3. لا تنتقل من مرحلة إلى المرحلة التالية إلا بعد الاختبار.
4. استخدم Claude / Codex / GitHub Copilot لتنفيذ كل Prompt.
5. بعد كل Prompt اطلب من أداة البرمجة أن تخرج لك تقرير:
   - ماذا نفذت؟
   - ما الملفات التي تغيرت؟
   - ما الاختبارات التي نجحت؟
   - ما الأخطاء المتبقية؟
6. استخدم ملف `06_QA_ACCEPTANCE_CHECKLIST.md` كقائمة فحص قبل الانتقال للمرحلة التالية.

## أهم قرار معماري

لا تبني النظام حول AI Tutor فقط.

ابنِ النظام حول:

```text
Student Learning Profile
```

ثم اجعل كل شيء يخدمه:

```text
Placement Test
→ Learning Profile
→ CEFR Level
→ Recommended Unit
→ 3 Lessons
→ Exercises
→ AI Tutor
→ Adaptive Learning
→ Gamification
→ Motivation
→ Teacher Intervention
→ Progress Reports
```

## الهيكل التعليمي المعتمد

```text
CEFR Level
  └── Unit
        ├── Lesson 1
        ├── Lesson 2
        └── Lesson 3
```

كل وحدة دراسية تحتوي على 3 دروس.

# 06_QA_ACCEPTANCE_CHECKLIST.md

## قاعدة عامة

أي مرحلة لا تعتبر مكتملة إلا إذا نجحت الاختبارات التالية:

```text
pytest
python manage.py check
python manage.py makemigrations --check
python manage.py migrate
python manage.py seed_onlenco_core
```

## Checklist لكل مرحلة

### Architecture

- [ ] settings منفصلة.
- [ ] apps منظمة.
- [ ] لا يوجد business logic في views.
- [ ] services/selectors موجودة.
- [ ] Docker يعمل.
- [ ] README موجود.

### Accounts

- [ ] تسجيل طالب يعمل.
- [ ] تسجيل دخول يعمل.
- [ ] كل role يرى ما يخصه.
- [ ] student isolation يعمل.
- [ ] permissions مختبرة.

### Curriculum

- [ ] CEFR levels موجودة.
- [ ] Unit لا تتجاوز 3 Lessons.
- [ ] Unit لا تنشر بدون 3 Lessons.
- [ ] lesson progress يعمل.
- [ ] APIs تعمل.

### Placement Written

- [ ] بدء الاختبار.
- [ ] الإجابة على سؤال.
- [ ] إنهاء الاختبار.
- [ ] حساب النتيجة.
- [ ] تحديد نقاط الضعف.
- [ ] estimated CEFR level يعمل.

### Placement Speaking

- [ ] بدء جلسة speaking.
- [ ] جلب السؤال التالي.
- [ ] رفع صوت.
- [ ] mock speech provider يعمل.
- [ ] scoring يعمل.
- [ ] feedback يظهر.

### Learning Profile

- [ ] profile ينشأ بعد الاختبار.
- [ ] final CEFR محفوظ.
- [ ] weak skills محفوظة.
- [ ] recommended first unit محفوظة.
- [ ] next lesson يعمل.

### Adaptive Learning

- [ ] تسجيل الأخطاء.
- [ ] تحديث skill mastery.
- [ ] توليد recommendations.
- [ ] theta_score يتحدث.

### AI Tutor

- [ ] context builder يعمل.
- [ ] session تبدأ.
- [ ] text message تعمل.
- [ ] voice message تعمل.
- [ ] AIUsageLog يسجل.
- [ ] subscription limits تعمل.

### Gamification

- [ ] XP يمنح بعد الدرس.
- [ ] badge تمنح.
- [ ] streak يتحدث.
- [ ] club attendance يمنح XP.

### Motivation

- [ ] trigger يعمل.
- [ ] message template تعمل.
- [ ] in-app notification ترسل.
- [ ] email task تعمل.

### Behavioral Analytics

- [ ] activity log يسجل.
- [ ] engagement score يحسب.
- [ ] churn risk يحسب.
- [ ] at-risk alert يرسل للمعلم.

### Academic Admin

- [ ] يرى الطلاب.
- [ ] يرى ملف الطالب.
- [ ] يعين تمرين.
- [ ] يرسل رسالة.
- [ ] يضيف note.
- [ ] يرى الطلاب المعرضين للانقطاع.

### Finance Admin

- [ ] يرى المدفوعات المعلقة.
- [ ] يراجع الإيصال.
- [ ] يوافق.
- [ ] يرفض.
- [ ] الاشتراك يتفعل بعد الموافقة.

### Weekly Club

- [ ] إنشاء جلسة.
- [ ] تسجيل طالب.
- [ ] رفع إيصال.
- [ ] موافقة مالية.
- [ ] إرسال رابط.
- [ ] تسجيل حضور.
- [ ] إضافة feedback.

### Digital Library

- [ ] عرض حسب CEFR.
- [ ] فتح عنصر.
- [ ] تسجيل تقدم.
- [ ] مفردات تظهر.
- [ ] أسئلة فهم تعمل.

### Notifications

- [ ] welcome email.
- [ ] payment approved.
- [ ] placement completed.
- [ ] motivation message.
- [ ] mark as read.

### UI

- [ ] responsive.
- [ ] Arabic.
- [ ] English.
- [ ] RTL.
- [ ] LTR.
- [ ] mobile friendly.

### Deployment

- [ ] docker compose up يعمل.
- [ ] migrations تعمل.
- [ ] static files تعمل.
- [ ] celery worker يعمل.
- [ ] celery beat يعمل.
- [ ] nginx config جاهز.

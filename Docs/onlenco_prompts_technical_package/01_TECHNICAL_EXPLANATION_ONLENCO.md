# التوضيح التقني لمنصة Onlenco

## 1. الفكرة العامة

Onlenco يجب أن تُبنى كمنصة EdTech ذكية، وليست مجرد موقع لعرض فيديوهات أو دروس.

الفكرة الصحيحة:

- الطالب يدخل.
- يسجل حساب.
- يعمل اختبار تحديد مستوى.
- الاختبار يتكون من جزأين:
  - كتابي Multiple Choice.
  - شفهي مع AI Avatar بالصوت والصورة.
- النظام يحسب مستوى CEFR.
- النظام ينشئ Student Learning Profile.
- النظام يرشح أول Unit مناسبة.
- كل Unit بها 3 دروس.
- كل درس به فيديو قصير وتمارين وكويز ومحادثة.
- AI Tutor يساعد الطالب حسب مستواه وأخطائه.
- Adaptive Engine يتابع أخطاء الطالب ويغير المسار.
- Gamification Engine يجعل التجربة مثل لعبة.
- Motivation Engine يرسل رسائل تشجيع.
- Academic Admin يتابع الطالب ويتدخل عند الحاجة.
- Finance Admin يراجع المدفوعات.
- Weekly English Club يضيف ممارسة جماعية حقيقية.

## 2. لماذا نحتاج هذا التقسيم؟

لو بنينا كل شيء في app واحد سيصبح المشروع صعب التطوير ومليئاً بالتكرار.

الأفضل أن يكون كل نطاق Domain في app مستقل:

```text
accounts              = المستخدمون والصلاحيات
curriculum            = المستويات والوحدات والدروس
placement             = اختبار تحديد المستوى
learning_profiles     = ملف الطالب الذكي
ai_tutor              = المدرس الذكي
speech_assessment     = تقييم النطق
adaptive_learning     = متابعة الأخطاء والتوصيات
cefr_mapping          = ربط كل شيء بمستوى CEFR
gamification          = النقاط والشارات والسلاسل
motivation            = رسائل التشجيع
behavioral_analytics  = تحليل السلوك وخطر الانقطاع
digital_library       = المكتبة الرقمية
weekly_club           = نادي المخاطبة
subscriptions         = الاشتراكات
payments              = المدفوعات والإيصالات
notifications         = الإشعارات والإيميلات
academic_admin        = لوحة المعلم
finance_admin         = لوحة المالية
dashboards            = لوحات التحكم
reports               = التقارير
```

## 3. القاعدة الذهبية

لا تضع business logic داخل views.

استخدم:

```text
models.py       = تعريف البيانات
selectors.py    = قراءة واستعلام
services.py     = تنفيذ منطق العمل
serializers.py  = تحويل البيانات API
views.py        = استقبال الطلبات فقط
tasks.py        = مهام Celery
tests/          = اختبارات
```

## 4. كيف يعمل Student Learning Profile؟

Student Learning Profile هو قلب النظام.

يحتوي على:

- مستوى الطالب.
- درجة الكتابي.
- درجة الشفهي.
- نقاط الضعف.
- نقاط القوة.
- مهارات الطالب.
- مستوى النطق.
- مستوى الطلاقة.
- الدرس المقترح.
- الوحدة المقترحة.
- theta score.
- engagement score.
- churn risk score.

أي نشاط يحدث في المنصة يجب أن يحدث هذا الملف:

```text
Quiz
Speaking Attempt
AI Tutor Session
Lesson Completion
Library Reading
Weekly Club Attendance
Teacher Assigned Exercise
```

## 5. لماذا AI Tutor ليس هو الأساس؟

AI Tutor مهم، لكنه ليس الأساس.

لو جعلناه الأساس فقط، ستصبح المنصة Chatbot.

أما لو جعلنا الأساس هو Learning Profile، فالـ AI Tutor يصبح ذكياً فعلاً لأنه يعرف:

- مستوى الطالب.
- الدرس الحالي.
- أخطاء الطالب السابقة.
- نقاط الضعف.
- أهداف الطالب.
- اللغة المناسبة للشرح.

## 6. شكل التقنية المقترحة

Backend:

```text
Django
Django REST Framework
PostgreSQL
Redis
Celery
Celery Beat
JWT/Auth
Docker
Nginx
Gunicorn
```

Frontend كبداية:

```text
Django Templates + Tailwind + AlpineJS
```

ثم لاحقاً:

```text
Mobile App / React / Flutter عبر نفس APIs
```

## 7. AI Provider Strategy

لا تربط المشروع بمزود واحد.

استخدم Interface:

```text
BaseLLMProvider
BaseSpeechProvider
BaseAvatarProvider
BaseNotificationProvider
```

ثم نفذ:

```text
OpenAIProvider
GoogleProvider
AzureProvider
MockProvider
```

بهذا لو تغير السعر أو الخدمة، لا تعيد بناء النظام.

## 8. اختبار تحديد المستوى

### كتابي

- Multiple Choice.
- يبدأ من A0/A1.
- يختبر:
  - Grammar
  - Vocabulary
  - Reading
  - Sentence Structure
- يحسب score لكل مهارة.

### شفهي

- AI Avatar يظهر للطالب.
- يسأل أسئلة بسيطة.
- الطالب يرد بالصوت.
- النظام يحلل:
  - pronunciation
  - fluency
  - grammar
  - vocabulary
  - relevance
  - confidence

## 9. قاعدة Unit / Lesson

الصحيح:

```text
Level → Unit → 3 Lessons
```

وليس:

```text
Lesson → Unit
```

لأن الوحدة هي حاوية تعليمية، والدرس جزء منها.

## 10. ما الذي يجب اختباره؟

قبل اعتبار أي مرحلة مكتملة:

- هل الـ models سليمة؟
- هل migrations تعمل؟
- هل API يعمل؟
- هل الصلاحيات صحيحة؟
- هل الطالب لا يرى بيانات غيره؟
- هل الاختبارات تمر؟
- هل النظام يدعم العربية والإنجليزية؟
- هل RTL/LTR يعمل؟
- هل seed data لا يكرر البيانات؟
- هل Celery tasks تعمل؟

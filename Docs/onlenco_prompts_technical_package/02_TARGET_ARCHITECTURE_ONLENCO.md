# TARGET_ARCHITECTURE_ONLENCO.md

## الهيكل البرمجي المقترح

```text
onlenco/
│
├── config/
│   ├── settings/
│   │   ├── base.py
│   │   ├── development.py
│   │   ├── production.py
│   │   └── test.py
│   ├── urls.py
│   ├── celery.py
│   ├── asgi.py
│   └── wsgi.py
│
├── apps/
│   ├── accounts/
│   ├── organizations/
│   ├── curriculum/
│   ├── placement/
│   ├── learning_profiles/
│   ├── lessons/
│   ├── exercises/
│   ├── assessments/
│   ├── ai_tutor/
│   ├── speech_assessment/
│   ├── adaptive_learning/
│   ├── cefr_mapping/
│   ├── gamification/
│   ├── motivation/
│   ├── behavioral_analytics/
│   ├── digital_library/
│   ├── weekly_club/
│   ├── subscriptions/
│   ├── payments/
│   ├── notifications/
│   ├── academic_admin/
│   ├── finance_admin/
│   ├── dashboards/
│   └── reports/
│
├── templates/
├── static/
├── locale/
├── tests/
├── docker/
├── docs/
├── manage.py
├── Dockerfile
├── docker-compose.yml
├── docker-compose.prod.yml
├── pyproject.toml
├── .env.example
└── README.md
```

## قواعد التصميم

### 1. كل app له مسؤولية واضحة

لا تخلط المدفوعات مع التعليم.
لا تخلط الذكاء الاصطناعي مع لوحة المعلم.
لا تخلط التحليلات مع الاختبارات.

### 2. داخل كل app

```text
models.py
selectors.py
services.py
serializers.py
views.py
urls.py
tasks.py
permissions.py
admin.py
tests/
README.md
```

### 3. Services Layer

أي عملية منطقية توضع في service.

مثال:

```text
PlacementResultCalculator
LearningProfileBuilderService
NextLessonRecommender
PaymentApprovalService
MotivationTriggerEvaluator
ChurnRiskCalculator
```

### 4. Selectors Layer

أي استعلام معقد يوضع في selector.

مثال:

```text
get_student_current_progress()
get_students_at_risk()
get_pending_payment_receipts()
get_recommended_lessons_for_student()
```

### 5. Provider Interfaces

أي خدمة خارجية يجب أن تكون خلف interface:

```text
LLMProvider
SpeechToTextProvider
TextToSpeechProvider
AvatarProvider
EmailProvider
PaymentProvider
```

## قاعدة البيانات الأساسية

سيتم استخدام PostgreSQL.

## المهام الخلفية

يتم استخدام Celery للمهام التالية:

- تحليل الصوت.
- إرسال الإيميلات.
- إرسال رسائل التشجيع.
- حساب churn risk.
- تحديث engagement score.
- توليد تمارين إضافية.
- استخراج مفردات من المكتبة الرقمية.
- توليد أسئلة فهم.

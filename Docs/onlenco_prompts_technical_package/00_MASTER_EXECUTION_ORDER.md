# 00_MASTER_EXECUTION_ORDER.md

## ترتيب التنفيذ الصحيح

لا تنفذ كل شيء مرة واحدة.

استخدم هذا الترتيب:

```text
Phase 0  - System Audit & Vision Lock
Phase 1  - Project Architecture & Core Settings
Phase 2  - Accounts, Roles & Permissions
Phase 3  - Curriculum: CEFR Level → Unit → 3 Lessons
Phase 4  - Written Placement Test
Phase 5  - Speaking Placement Test with AI Avatar API readiness
Phase 6  - Student Learning Profile
Phase 7  - CEFR Mapping Engine
Phase 8  - Adaptive Learning Engine
Phase 9  - Lessons, Exercises & Quizzes
Phase 10 - AI Tutor Text & Voice
Phase 11 - Speech Assessment Engine
Phase 12 - Gamification Engine
Phase 13 - Smart Motivation Engine
Phase 14 - Behavioral Analytics Engine
Phase 15 - Student Dashboard
Phase 16 - Academic Admin Dashboard
Phase 17 - Finance Admin, Payments & Subscriptions
Phase 18 - Weekly English Club
Phase 19 - Digital Library
Phase 20 - Notifications & Emails
Phase 21 - Custom Admin Panel
Phase 22 - API Documentation
Phase 23 - Seed Data
Phase 24 - Security Review
Phase 25 - QA & E2E Testing
Phase 26 - Docker & Production Deployment
```

## شرط الانتقال من مرحلة إلى أخرى

لا تنتقل للمرحلة التالية إلا إذا تحقق التالي:

```text
1. migrations تعمل
2. tests تمر
3. API يعمل
4. permissions صحيحة
5. لا يوجد كود مكرر
6. لا يوجد business logic داخل views
7. تم تحديث README
8. تم تحديث docs
```

## قاعدة مهمة

في كل مرحلة اطلب من الذكاء الاصطناعي الذي ينفذ الكود أن يعطيك:

```text
1. Summary of changes
2. Files created
3. Files modified
4. Database migrations
5. APIs added
6. Tests added
7. How to run tests
8. Known limitations
9. Next recommended step
```

# تقرير Prompt 14 — Controlled Publish Pilot for Batch 1

> نشر محكوم لـ Topics 02–06 فقط، عبر **خدمة سير عمل المراجعة** (approved →
> published) مع سجلّ تدقيق وخطة rollback. **لم تُولَّد أي وسائط، ولم يُنشر أي
> Topic آخر، ولم يُمَس Topic 01 ولا الدروس المؤرشفة.** حدّ الأمان للطلاب هو
> **Student Approval Gate** (الطلاب غير المعتمدين لا يرون أي شيء).

## 1. الملخص التنفيذي

* **ماذا تم نشره؟** خمسة دروس فقط — Topics 02–06 — انتقلت من `approved` إلى
  `published`.
* **هل النشر كان محدودًا؟** نعم. 07–48 بقيت `pending_review`، والدروس القديمة بقيت
  `archived`، وTopic 01 كما هو.
* **هل الطلاب غير المعتمدين محميون؟** نعم. بوابة الموافقة تمنعهم من لوحة التحكم
  والدورات والـ AI حتى بعد النشر (إعادة توجيه HTML + 403 JSON).
* **هل Batch 1 جاهز للطلاب المعتمدين؟** نعم — الطالب المعتمد يرى ويُكمل Topics 01–06،
  والتحدّي يعمل بلا وسائط، والـ AI يمرّ عبر الـ wrapper. لا موانع P0/P1.

## 2. Pre-check Results

أوامر (idempotent): `seed_learning_skills`, `seed_badge_definitions`,
`seed_super_lesson_01`, `seed_beginner_48_topics --confirm`,
`check_generated_content_quality --course=onlenco-beginner --save`,
`initialize_student_approval_status --dry-run`.

* **Quality (02–06):** كلها **100**، 0 errors، 10 أسئلة لكل درس.
* **بوابات المنع — مرّت كلها:** score ≥ 90، لا error flags، الدروس approved قبل
  النشر، challenge موجود، ≥ 8 أسئلة، البوابة مفعّلة، Topics 07–48 غير مرئية،
  المؤرشف غير مرئي، الـ AI wrapper سليم، `manage.py check` نظيف.
* **الحالات قبل النشر:** published=1 (gold) · approved=5 (02–06) · pending_review=42 ·
  archived=47.
* **Student Approval Gate:** `ONLENCO_STUDENT_APPROVAL_REQUIRED=True`.
* **الطلاب (dev):** approved≈19 · pending≈4.
* **AI usage tracking:** جاهز للإنتاج، وكل المكالمات عبر `ai_usage/services/ai_client.py`.

> ملاحظة تشغيلية (P2): إعادة تشغيل `seed_beginner_48_topics --confirm` تُعيد ضبط
> حالة الدروس إلى `pending_review` (update_or_create بـ defaults). لذلك في الـ pilot
> أُعيد اعتماد 02–06 ثم نُشرت. يجب عدم إعادة الـ seed على الإنتاج بعد الاعتماد/النشر.

## 3. Published Topics

| Topic | Title | Old Status | New Status | Published At | Published By |
|---|---|---|---|---|---|
| 02 | Saying Hello and Goodbye | approved | published | set | s0991524441@gmail.com |
| 03 | Spelling Your Name | approved | published | set | s0991524441@gmail.com |
| 04 | Countries and Nationalities | approved | published | set | s0991524441@gmail.com |
| 05 | Talking About Age | approved | published | set | s0991524441@gmail.com |
| 06 | Basic Personal Information | approved | published | set | s0991524441@gmail.com |

الحالة النهائية: published=6 (gold + 02–06) · pending_review=42 · archived=47.
كل درس يحمل أحداث `approve` ثم `publish` في سجلّ التدقيق.

## 4. Visibility Verification

| User Type | Topic 01 | Topics 02–06 | Topics 07–48 | Archived Legacy |
|---|---|---|---|---|
| Approved student | ✅ مرئي | ✅ مرئي (الرابط يعمل) | ❌ مخفي (404) | ❌ مخفي (404) |
| Pending student | ❌ محجوب (→ صفحة الانتظار) | ❌ محجوب | ❌ محجوب | ❌ محجوب |
| Anonymous | ❌ (تسجيل دخول) | ❌ | ❌ | ❌ |
| Teacher/Admin | ✅ | ✅ published في اللوحة | ✅ pending_review | ✅ archived في الفلتر |

## 5. Student Journey Test

طالب معتمد: dashboard → الدورة → Topic 02 → بدء التحدّي → الإجابة (مع إجابة خاطئة
مقصودة) → إكمال → الوصول إلى الملخّص (حالة الجلسة غير `in_progress`) → XP/Hearts/
Mastery محدّثة → لا حاجة لأي ملف وسائط. تمّ تشغيل smoke لـ Topics 03–06 (التحدّي
يبدأ ويعرض أول سؤال).

## 6. AI Usage Verification

* مكالمات الطالب (شرح التحدّي/roleplay/المعلّم) تمرّ عبر `ai_client` وتُسجَّل في
  `AIUsageLog`.
* الطالب المعلّق: تُرفض مكالمته **قبل** المزوّد (لا تكلفة، لا دقائق، سجلّ `cancelled`).
* الطالب المعتمد: تنجح ضمن الحصّة وتُسجَّل.
* الطالب لا يرى التكلفة الداخلية (`/api/ai-usage/summary/today/` بلا
  `estimated_cost_usd`)؛ الأدمن يراها.

## 7. Media Placeholder Verification

* لا توجد ملفات وسائط مولّدة (`generated_image` فارغ، `is_generated=False`).
* صفحة الدرس لا تعرض نص الـ prompt الخام للطالب.
* الدرس والتحدّي يعملان بالكامل دون وسائط (placeholders آمنة).

## 8. Dashboard Verification

* لوحة المراجعة: 02–06 `published`، 07–48 `pending_review`، المؤرشف `archived`،
  Topic 01 published — وفلتر `?status=published` يعمل (200).
* لوحة الطالب: المعتمد يرى المنشور فقط؛ المعلّق يرى صفحة الانتظار.
* لوحة AI usage تستقبل أي استخدام مُشغَّل وتجمّعه حسب الميزة وتُخفي التكلفة عن الطالب.

## 9. Rollback Plan

أمر: `unpublish_teacher_batch --course=onlenco-beginner --topics=2-6 --dry-run | --confirm --actor=<admin>`.

* `published → approved` عبر الـ workflow؛ dry-run لا يغيّر شيئًا؛ confirm يعيد للـ
  approved ويكتب حدث `unpublish` بملاحظة «Rollback of Controlled Publish Pilot Batch 1.»
* الطالب يفقد الوصول بعد الـ rollback؛ المعلّم/الأدمن يبقى يرى الدرس.
* **لا يحذف** دروسًا ولا محاولات ولا تقدّمًا (مُختبَر: ChallengeSession يبقى).
* لم يُشغَّل الـ rollback على الإنتاج — فقط اختبار سلوك الأمر.

## 10. Audit Events

* أحداث `publish` لكل درس 02–06 (ملاحظة الـ pilot).
* أحداث `unpublish` تُكتب عند اختبار الـ rollback.
* بالإضافة إلى `approve`/`start_review` السابقة — السلسلة كاملة قابلة للتدقيق.

## 11. Tests

| test | result |
|---|---|
| publish dry-run/confirm/refuses-pending/refuses-archived/no-07-48/audit/no-media | OK |
| batch starts approved-not-published / 02–06 published / 07–48 pending | OK |
| approved student accesses 02–06 / cannot access 07–48 / archived hidden | OK |
| pending student blocked + redirected / gate still blocks dashboard | OK |
| anonymous blocked / teacher accesses published | OK |
| e2e challenge→summary / challenge runs 02–06 / rewards-mastery / no media required | OK |
| challenge AI via wrapper logs / pending AI blocked / no cost to student / admin sees cost | OK |
| no generated media / no raw prompt visible | OK |
| rollback dry-run/confirm/audit/student-loses-access/teacher-keeps/no-progress-deleted | OK |
| review dashboard reflects published | OK |
| **Prompt 14 suite (38 tests)** | **OK** |
| Full: courses + teacher_portal + accounts + ai_usage + tutor + motivation + learning_core | OK (القسم 12) |

## 12. Commands Run

```
# Pre-checks (idempotent)
python manage.py seed_learning_skills | seed_badge_definitions | seed_super_lesson_01
python manage.py seed_beginner_48_topics --confirm
python manage.py check_generated_content_quality --course=onlenco-beginner --save
python manage.py initialize_student_approval_status --dry-run

# Pilot publish (workflow service)
python manage.py approve_teacher_batch  --course=onlenco-beginner --topics=2-6 --confirm --actor=<admin>
python manage.py publish_teacher_batch  --course=onlenco-beginner --topics=2-6 --dry-run   # 0 changes
python manage.py publish_teacher_batch  --course=onlenco-beginner --topics=2-6 --confirm --actor=<admin>
  → reviewed=5 published=5 skipped=0 failed=0 (no media)

# Rollback (tested, NOT applied to prod)
python manage.py unpublish_teacher_batch --course=onlenco-beginner --topics=2-6 --dry-run

# Tests (framework: manage.py test — not pytest)
DJANGO_SETTINGS_MODULE=config.settings.test python manage.py test courses teacher_portal accounts ai_usage tutor motivation learning_core
DJANGO_SETTINGS_MODULE=config.settings.test python manage.py check  → no issues
```
> أسماء التطبيقات الفعلية: لا يوجد `users`/`student_portal`؛ لوحة الطالب في `lessons`.

## 13. Problems Remaining

**P0:** لا يوجد. (لم يُنشر خارج 02–06، المؤرشف مخفي، المعلّق محجوب من dashboard/AI،
Topic 01 سليم، لا وسائط، لا prompt خام، لا تكلفة للطالب، النشر عبر الـ workflow + تدقيق،
الـ rollback يُخفي الدروس مجددًا.)
**P1:** لا يوجد.
**P2:** (1) إعادة seed تُعيد ضبط الحالة — لا تُعد الـ seed بعد النشر على الإنتاج.
  (2) الدروس المنشورة بلا وسائط حقيقية (placeholders) — تجربة كاملة تحتاج Prompt 15.
**P3:** نظام cohort للـ pilot لم يُبنَ (استُخدمت رؤية «الطلاب المعتمدون فقط» كحدّ أمان —
  مُوثَّق)؛ يمكن لاحقًا إضافة LessonPilotAccess إن لزم تقييد أدقّ.

## 14. Final Decision

**Controlled Publish Pilot successful.** Topics 02–06 منشورة للطلاب المعتمدين فقط،
عبر سير العمل الرسمي مع تدقيق كامل وخطة rollback مُختبَرة، بلا وسائط وبلا تسريب
تكلفة، والاختبارات خضراء و`check` نظيف.

## 15. Recommended Next Phase

**Prompt 15 — Media Generation Pilot for Published Batch 1** (توليد صور/صوت محكوم
لـ 02–06 عبر `ai_usage` مع ميزانية وتتبّع)، أو **Prompt 15 — Expand Teacher Approval
Batch 2** (اعتماد 07–12). لن أبدأ Prompt 15 تلقائيًا — بانتظار مراجعة هذا التقرير.

> ملاحظة استراتيجية الوصول: لا يوجد cohort؛ النشر للطلاب المعتمدين فقط، وStudent
> Approval Gate هو حدّ الأمان (مُوثَّق كما طلب الـ Prompt).

---

> **Update (Prompt 14.5):** The seed command was hardened to preserve
> published/approved/archived statuses — re-running `seed_beginner_48_topics
> --confirm` no longer unpublishes or reverts live lessons (it skips
> reviewed lessons and only refreshes `pending_review` content). See
> `docs/PROMPT_14_5_SEED_IDEMPOTENCY_HARDENING_REPORT.md`.

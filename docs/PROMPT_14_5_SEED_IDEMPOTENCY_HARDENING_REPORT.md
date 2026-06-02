# تقرير Prompt 14.5 — Seed Idempotency Hardening / Preserve Review Status

> إصلاح أمان فقط لأمر الـ seed. **لم يُنشر/يُلغَ نشر أي درس، ولم تُولَّد وسائط، ولم
> تُعتمَد مواضيع جديدة، ولم يُمَس Topic 01 ولا الدروس المؤرشفة.** الحالات محفوظة كما هي.

## 1. الملخص التنفيذي

* **ما المشكلة؟** كان `seed_beginner_48_topics --confirm` يستخدم
  `update_or_create(..., defaults={"status":"pending_review", ...})` للدروس
  الموجودة، فيعيد ضبط حالة الدروس المعتمدة/المنشورة إلى `pending_review` — أي قد
  يُلغي نشر دروس حيّة ويكسر وصول الطلاب ويتجاوز سير عمل المراجعة.
* **ماذا تم إصلاحه؟** أعيدت كتابة منطق التحديث: `get_or_create` بدل
  `update_or_create`، مع **حفظ صارم** لحالة الدروس `approved`/`published`/`archived`
  وحقول المراجعة، وتحديث المحتوى فقط للدروس `pending_review`، وإنشاء أي درس ناقص
  كـ `pending_review`. أُضيف تأكيد أمان يُفشل الأمر إذا تغيّرت أي حالة بشكل غير متوقّع.
* **هل أصبح seed آمنًا بعد النشر؟** نعم. تشغيله على الحالة الإنتاجية الحالية:
  `status_changes=0` و«✅ No review/publish status changed»، والحالة قبل/بعد متطابقة.

## 2. السبب الجذري

* **أين؟** في `Lesson.objects.update_or_create(course, unit, order, defaults={... "status":"pending_review" ...})` — الـ defaults تُطبَّق على الدروس **الموجودة** أيضًا، فتدهور حالتها.
* **لماذا؟** خلط حقول **المحتوى** مع حقل **الحالة** في نفس الـ defaults، وافتراض أن الـ seed يملك الحالة دائمًا. كما كانت كائنات الأبناء (checklist/الصور/الصوت/الأسئلة) تُعاد كتابتها بصرف النظر عن الحالة.
* **هل كان `published_at`/`approved_*` يُمسَح؟** لم تكن في الـ defaults مباشرةً، لكن إعادة الحالة إلى `pending_review` كانت تُبطل النشر فعليًا؛ والآن لا تُلمس هذه الحقول إطلاقًا.
* **هل `--topic=N` فيه نفس المشكلة؟** نعم (نفس المسار) — والآن محفوظ أيضًا.
* **السلوك الآمن الجديد:** انظر القسم 4.

## 3. الملفات المعدلة

| File | Change | Reason |
|---|---|---|
| `courses/management/commands/seed_beginner_48_topics.py` | إعادة هيكلة منطق التحديث + علامات أمان + تأكيد قبل/بعد + تقارير | منع تدهور الحالة |
| `courses/tests/test_prompt_14_5_seed_safety.py` | إنشاء | 22 اختبارًا لحفظ الحالة |
| `docs/SEEDING_SAFETY_GUIDE.md` | إنشاء | دليل الـ seeding الآمن |
| `docs/PROMPT_14_CONTROLLED_PUBLISH_PILOT_BATCH_1_REPORT.md` | ملاحظة | الإشارة إلى التحصين |

## 4. Safe Seed Policy

* **published:** الحالة و`published_at` والمحتوى محفوظة — يُتخطّى الدرس.
* **approved:** الحالة و`approved_by/at` والمحتوى محفوظة — يُتخطّى.
* **archived:** يبقى مؤرشفًا ومخفيًّا — لا يُلمس.
* **pending_review (وdraft/changes_requested/in_review):** يُحدَّث المحتوى وكائنات
  الأبناء بشكل idempotent **مع إبقاء الحالة كما هي**.
* **درس جديد:** يُنشأ بحالة `pending_review` فقط (لا اعتماد ولا نشر تلقائي).
* **Topic 01:** يملكه `seed_super_lesson_01`؛ هذا الأمر يتخطّاه (order==1) ولا يلمسه.

لا `queryset.update(status=...)`، ولا `status` في defaults لدرس موجود، ولا مسح
لأحداث المراجعة/المحاولات/التقدّم.

## 5. Command Behavior

* `--confirm`: يطبّق السياسة الآمنة أعلاه ويطبع تقريرًا تفصيليًا.
* `--dry-run`: لا كتابة (يتفوّق على `--confirm` إن مُرّرا معًا).
* `--topic=N`: يقصر التشغيل على درس واحد، مع حفظ الحالة.
* **علامات خطرة (افتراضيًا غير مستخدمة):**
  * `--update-reviewed-content` (+`--confirm`): يحدّث محتوى الدروس المعتمدة/المنشورة
    لكن **لا يغيّر حالتها**.
  * `--reset-status` (+`--confirm` +`--topic=N` +`--i-understand-this-can-unpublish`):
    خطر — يعيد درسًا إلى `pending_review` (قد يُلغي النشر). للتطوير/الاسترداد فقط.
* تأكيد أمان: داخل المعاملة، تُقارن حالات الدروس الموجودة قبل/بعد؛ أي تغيير غير
  متوقّع (دون علم خطر) ⇒ `CommandError` وتُلغى المعاملة.

## 6. Status Preservation Verification

| Lesson group | Before seed | After seed | Result |
|---|---|---|---|
| Topic 01 (Gold) | published | published | ✅ محفوظ |
| Topics 02–06 | published | published | ✅ محفوظ (`published_at` كما هو) |
| Topics 07–48 | pending_review | pending_review | ✅ محتوى مُحدَّث، الحالة كما هي |
| Legacy lessons (47) | archived | archived | ✅ محفوظ |

ناتج الأمر الفعلي: `created=0 updated_pending_review=42 skipped_published=5
status_changes=0` — «✅ No review/publish status changed».

## 7. Student Visibility Verification

* **الطالب المعتمد:** يصل إلى Topics 01–06 بعد إعادة الـ seed (مُختبَر عبر HTTP +
  `published_lesson_queryset`).
* **الطالب المعلّق:** يبقى محجوبًا (إعادة توجيه إلى صفحة الانتظار) بعد إعادة الـ seed.
* **المعلّم/الأدمن:** لوحة المراجعة تعمل وفلتر `published` يعرض 01–06.

## 8. Tests

| Test | Result |
|---|---|
| preserves_published / approved / archived status | OK |
| does_not_clear_published_at / approved_fields | OK |
| preserves_topic_01_gold | OK |
| updates_pending_review_topics (status kept) | OK |
| creates_missing_topic_as_pending_review | OK |
| confirm_no_status_regression_after_prompt14 | OK |
| single_topic_preserves_status / dry_run_changes_nothing | OK |
| reports_skipped_published_and_archived | OK |
| reset_status_requires_explicit_flags (CommandError) | OK |
| published_batch_1_remains_visible_after_reseed | OK |
| student_access_to_02_06_survives_reseed | OK |
| topics_07_48_remain_pending_review_after_reseed | OK |
| archived_legacy_lessons_remain_archived_after_reseed | OK |
| publish/unpublish batch still work | OK |
| review_dashboard_status_counts_after_reseed | OK |
| student_approval_gate_still_blocks_pending | OK |
| topic_01_gold_reference_unchanged | OK |
| **مجموعة 14.5 (22 اختبارًا)** | **OK** |
| regression (courses/teacher_portal/accounts/ai_usage) | OK (القسم 9) |

## 9. Commands Run

```
# verification scenario (dev, prod-like state)
python manage.py seed_beginner_48_topics --confirm
  → created=0 updated_pending_review=42 skipped_published=5 status_changes=0 (✅ no status changed)
python manage.py seed_beginner_48_topics --topic=2 --confirm   → T02 published preserved
python manage.py seed_beginner_48_topics --dry-run             → no writes

# tests (framework: manage.py test — not pytest)
DJANGO_SETTINGS_MODULE=config.settings.test python manage.py test courses teacher_portal accounts ai_usage
DJANGO_SETTINGS_MODULE=config.settings.test python manage.py check  → no issues
```

## 10. Manual QA

تم التحقق: الحالة قبل = بعد (published 6 / archived 47 / pending_review 42)؛
`published_at`/`approved_*` لم تُمسح؛ الطالب المعتمد يصل لـ 02–06؛ الطالب المعلّق
محجوب؛ لوحة المراجعة سليمة؛ لا وسائط مولّدة؛ لا حذف لأحداث التدقيق.

## 11. Remaining Issues

* **P0/P1:** لا يوجد.
* **P2:** أوامر seed أخرى قديمة (مثل `seed_onlenco_beginner_48_units`,
  `seed_smart_curriculum`) قد تحمل نفس النمط؛ يُنصح بمراجعتها لاحقًا (خارج نطاق هذا الـ Prompt الذي يستهدف `seed_beginner_48_topics`).
* **P3:** يمكن لاحقًا إضافة فحص CI يمنع وضع `status` في defaults لأي `update_or_create` على Lesson.

## 12. Final Decision

**Seed hardening complete; safe to proceed to Prompt 15.** الأمر لم يعد يعيد ضبط
الدروس المنشورة/المعتمدة، يحفظ المؤرشفة وGold Reference، يحدّث pending_review بأمان،
لا يمسح حقول المراجعة، يبلّغ عن المتخطّى، ويفشل عند أي تغيير حالة غير متوقّع.
الاختبارات خضراء و`check` نظيف.

## 13. Recommended Next Phase

**Prompt 15 — Media Generation Pilot for Published Batch 1** أو
**Prompt 15 — Expand Approval Batch 2**. لن أبدأ Prompt 15 تلقائيًا.

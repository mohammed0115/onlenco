# تقرير Prompt 11 — Human Review Workflow / Teacher Approval Dashboard

**التاريخ:** 2026-05-30
**المرحلة:** Phase 11 — نظام مراجعة بشرية كامل
**الحالة:** ✅ مكتمل + اختبارات خضراء (939 / 939 — 35 جديد + 904 سابقة، كلها ناجحة)
**الموقع:** المراجعة لا تنشر، لا تولّد media، لا تعدّل محتوى تلقائياً.

---

## 1) الملخّص التنفيذي

### ماذا تم بناءه؟
نظام **مراجعة بشرية كامل** لـ 47 درس مُولَّد في Phase 10:

| المكوّن | التفاصيل |
|---|---|
| **Migration** | إضافة 5 fields إلى Lesson + 4 status choices جديدة + جدول `LessonReviewEvent` (audit trail) |
| **Quality Checker Service** | `content_quality_checker.py` — يحسب score من 100 + يرجع flags بمستويات error/warning/info — deterministic لا AI |
| **Workflow Service** | `lesson_review_workflow.py` — state machine بـ 8 transitions + audit logging |
| **Teacher Dashboard** | 2 صفحات (list + detail) + 6 action endpoints — login + role-gated عبر `teacher_required` |
| **Management Command** | `check_generated_content_quality` — يدعم `--save` / `--json` / `--fail-on-errors` |
| **Tests** | 35 اختبار جديد عبر 6 مجالات |

### هل أصبح لدينا Review Gate؟
نعم — `published_lesson_queryset()` يفلتر `status="published"` فقط، و الـ workflow يفرض:
- `approved` فقط يمكن `publish`.
- `approve` يرفض الـ lesson لو quality checker يجد errors (إلا لـ admin مع `override=True`).
- كل state transition تكتب row في `LessonReviewEvent`.

### هل الطلاب محميون من المحتوى غير المعتمد؟
نعم — مُثبَت بثلاثة اختبارات:
- `test_student_cannot_access_pending_lesson` → 404
- `test_student_cannot_access_approved_unpublished_lesson` → 404
- `test_student_can_access_published_lesson` → 200

---

## 2) الملفات المعدلة أو المنشأة

### ملفات جديدة (7)

| الملف | الدور |
|---|---|
| `courses/migrations/0014_lesson_approved_at_lesson_approved_by_and_more.py` | extends Lesson.status + 5 fields + LessonReviewEvent table |
| `courses/services/content_quality_checker.py` | quality engine: score + flags + persist |
| `courses/services/lesson_review_workflow.py` | state machine + audit transitions |
| `courses/management/commands/check_generated_content_quality.py` | management command |
| `teacher_portal/views_content_review.py` | 2 page views + 6 action endpoints |
| `teacher_portal/templates/teacher_portal/content_review/list.html` | dashboard table + filters |
| `teacher_portal/templates/teacher_portal/content_review/detail.html` | detail page with all panels |
| `courses/tests/test_content_review_phase11.py` | 35 اختبار |
| `Docs/.../PROMPT_11_PHASE11_REVIEW_WORKFLOW_RESULT.md` | هذا التقرير |

### ملفات مُحدَّثة (2)

| الملف | التعديل | السبب |
|---|---|---|
| `courses/models.py` | إضافة `LESSON_STATUS_CHOICES` (4 statuses) + 5 Lesson fields + `LessonReviewEvent` + `REVIEW_ACTION_CHOICES` + `status` max_length 16→20 | بنية الـ workflow |
| `teacher_portal/urls.py` | + 8 routes تحت `/teacher/content-review/...` | endpoints الـ dashboard |

---

## 3) Review Workflow

### State Machine
```
draft ──→ pending_review ──→ in_review ──→ changes_requested
                  │             │                │
                  │             │                ↓
                  │             │          (loops back to in_review)
                  │             ↓                ↑
                  └────→  approved  ←──────────┘
                             │
                             ↓
                          published
                             │
                             ↓ (unpublish)
                          approved (recycle)
```

### الـ Statuses
| Status | meaning | student-visible? |
|---|---|---|
| **draft** | initial scaffolding | ❌ |
| **pending_review** | generated content awaiting first review | ❌ |
| **in_review** | a teacher started reviewing it | ❌ |
| **changes_requested** | needs author revisions (with note) | ❌ |
| **approved** | teacher signed off; awaiting publish | ❌ |
| **published** | live for students | ✅ |
| **rejected** | terminal — content not usable | ❌ |
| **archived** | hidden but retained | ❌ |

### القواعد الصارمة
- لا `publish` بدون `status="approved"`.
- لا `approve` لو `content_quality_checker` يجد **أي flag بـ severity="error"** — إلا لو `admin` يمرر `override=True`.
- `request_changes` و `reject` يطلبان `note` صريح (raise `WorkflowError` بدون).
- كل transition تكتب `LessonReviewEvent` (audit).

---

## 4) Dashboard

### Routes
```
GET  /teacher/content-review/                                 ← list view
GET  /teacher/content-review/lessons/<id>/                    ← detail view
POST /teacher/content-review/lessons/<id>/start-review/
POST /teacher/content-review/lessons/<id>/approve/
POST /teacher/content-review/lessons/<id>/request-changes/
POST /teacher/content-review/lessons/<id>/publish/
POST /teacher/content-review/lessons/<id>/unpublish/
POST /teacher/content-review/lessons/<id>/note/
```

### List view
- جدول يعرض: **رقم Topic / العنوان / Course / Status chip / Score / # Questions / # Flags badge / Reviewer / Action link**.
- **Filters**: status, course slug, search by title, has-flags, uses-fallback-skill.
- **Status chips ملوّنة**: pending(أصفر) / in_review(أزرق) / changes_requested(برتقالي) / approved(أخضر) / published(أخضر داكن) / rejected(أحمر).

### Detail view
8 sections بكل ما يحتاجه الأستاذ:
1. **Header** — chip + score + PASS/FAIL.
2. **Actions toolbar** — أزرار حسب الـ status الحالي.
3. **Quality flags** — مجمَّعة بـ severity (errors/warnings/info) مع `data-flag-code` لكل flag.
4. **English content preview** — `<details open>` يعرض الـ `content_html|safe` داخل scroll container.
5. **Arabic content preview** — `<details>` بـ `dir="rtl"`.
6. **Challenge questions** — جدول order / type / text / skill chips (fallback skills بلون مختلف) / difficulty.
7. **Media** — image prompts + audio scripts + checklist.
8. **Audit trail** — آخر 50 review event بـ actor + status transition + note + timestamp.

### Permissions
- `teacher_required` decorator يلف كل view.
- Student → 403 Forbidden.
- Anonymous → 302 redirect to login.
- Teacher group OR is_superuser → 200.

---

## 5) Lesson Review Detail Page

كل قسم له `data-*` attributes للـ E2E testing:
- `data-review-detail` على الـ container الرئيسي
- `data-flag-code="<code>"` على كل flag (للـ filter في الـ UI)
- `data-status="<status>"` للـ JS conditionals

الـ Actions form-set مدمج:
- زر "Start Review" يظهر فقط في status `pending_review` أو `changes_requested`.
- زر "Approve" يظهر في `in_review/changes_requested/pending_review`.
- زر "Request Changes" يطلب note صريح في الـ form.
- زر "Publish" يظهر فقط في `approved` + يطلب `confirm()`.
- زر "Unpublish" يظهر فقط في `published`.
- زر "Save Note" متاح دائماً (لا يغيّر status).

---

## 6) Quality Checker

ملف: [content_quality_checker.py](courses/services/content_quality_checker.py)

### الـ scoring rules
- يبدأ من 100.
- كل `error` يطرح 12 نقطة.
- كل `warning` يطرح 4 نقاط.
- `info` لا يطرح (مجرد إعلام).
- الـ `passed` = `score >= 85 AND no errors`.

### Categories of rules

#### Structure
- كل القسم الـ 11 المطلوب في `content_html` (lesson-goal, new-language, vocabulary, key-language, how-to-form, visual-guide, mini-dialogue, listening-practice, speaking-practice, ai-tutor-drill, checklist).
- `checklist` ≥ 4 active items.

#### Questions
- 8-12 questions per challenge.
- `forbidden_type_a0` — Topics 1-12 لا تحتوي `listen_and_type` أو `translate_to_english`.
- `forbidden_type_a0_plus` — Topics 13-24 لا تحتوي `listen_and_type`.
- `too_many_speaking` — > 3 placeholders.
- `no_listening_question` / `no_speaking_question` (warnings).
- `first_question_too_hard` — first Q.difficulty > 0.4 (warning).
- `last_question_not_speaking` — last Q ≠ speaking/roleplay (warning).
- `no_skills` (error) لو سؤال بدون `metadata.skills`.
- `unknown_skill` / `fallback_skill` (warnings).

#### Media
- `image_prompt_count` (error if < 4).
- `audio_script_count` (error if < 6).
- `brand_risk` — لو الـ prompt يذكر "English for Everyone" / "DK Publishing" / "Duolingo" / " owl ".
- `missing_copyright_disclaimer` — لو الـ prompt لا يحوي "no logo" / "no copyrighted" / "no brand".
- `audio_has_html` — لو الـ script يحوي `<` أو `>`.
- `audio_has_underscore` — لو يحوي `_`.

#### Arabic
- `missing_arabic` (error).
- `arabic_too_short` — لو AR/EN < 50%.
- `arabic_section_missing` — لو AR ينقص أحد lesson-goal / vocabulary / checklist.

### Output shape
```python
{
  "score": 92,
  "passed": True,
  "flags": [
    {"severity": "warning", "code": "fallback_skill",
     "message": "Q5 uses fallback skill 'general_beginner'",
     "where": "Q5"},
    ...
  ]
}
```

### Bulk helper
`quality_summary_for_queryset(qs)` — يرجع list of summary dicts للـ dashboard.

### Save helper
`save_quality_result(lesson, result)` — يخزن `score` + `flags` على الـ Lesson row.

---

## 7) Human Review Gate

### Teacher / Admin visibility
- `teacher_required` decorator على كل dashboard view.
- Admin (`is_superuser`) يدخل أيضاً لأن الـ decorator يستفيد من Group "Teacher" أو superuser.
- لا فلتر إضافي — الـ dashboard يعرض كل الـ `REVIEWABLE_STATUSES` (pending_review, in_review, changes_requested, approved, published, rejected).

### Student hidden
- Student-facing views كلها تعتمد على `published_lesson_queryset()` الذي يفلتر `status="published"`.
- مُثبَت في 3 اختبارات (pending_review → 404، approved-not-published → 404، published → 200).

### Published only
- `published` هو الـ status الوحيد الذي يجعل الـ lesson مرئية للطالب.
- `publish()` يضع `lesson.published_at = timezone.now()` و يكتب audit event.

---

## 8) Fallback Skill Warnings

### المشكلة (من Phase 10)
5 أسئلة استخدمت `mistake_correction` كـ skill code (هو question_type وليس skill). الـ seed حوّلها إلى `general_beginner` مع warning.

### كيف يراها الأستاذ
1. **في الـ list view** — filter `?fallback=1` يحجب فقط الـ topics التي تحوي flag بـ code `fallback_skill`.
2. **في الـ detail view** — في جدول Questions، الـ skill chip للـ `general_beginner` يحمل class `is-fallback` (لون مختلف، أصفر).
3. **في الـ flags panel** — كل `fallback_skill` warning يظهر مع `Q<order>` للوصول السريع.

### الـ action المتاحة الآن
- الأستاذ يضيف note (`Save note` form) — لا تغيير في status.
- يطلب changes إذا أراد فريق الـ content يصلح الـ skill.
- يـ approve لو الـ fallback مقبول (warning فقط، ليس error).

### TODO (Phase 12+)
- inline skill editing per question.
- bulk "remap fallback" action عبر admin.

---

## 9) Permissions

| Role | Dashboard list | Detail | Actions | Override |
|---|---|---|---|---|
| **Anonymous** | 302 → login | 302 → login | 302 → login | n/a |
| **Student** | 403 Forbidden | 403 Forbidden | 403 Forbidden | n/a |
| **Teacher** (Group="Teacher") | ✅ 200 | ✅ 200 | ✅ kết all transitions | ❌ |
| **Admin** (is_superuser) | ✅ 200 | ✅ 200 | ✅ all transitions | ✅ `approve(override=True)` |

الـ decorator `teacher_required` يستفيد من `RoleService.user_has_role(user, ROLE_TEACHER)` الذي يتضمن superusers + Teacher group.

---

## 10) Review Actions

| Action | Allowed from status | Effect | Note required? |
|---|---|---|---|
| `start_review` | pending_review, changes_requested | → in_review | ❌ |
| `request_changes` | in_review, pending_review | → changes_requested | ✅ |
| `approve` | in_review, changes_requested, pending_review | → approved + sets `approved_by/at` + persists quality score | ❌ (uses checker; rejected if errors unless override) |
| `publish` | approved | → published + sets `published_at` | ❌ |
| `unpublish` | published | → approved (recycle) | ❌ |
| `reject` | (any reviewable) | → rejected (terminal) | ✅ |
| `add_note` | (any) | no status change | ✅ |

كل action يكتب row في `LessonReviewEvent` مع `actor`, `from_status`, `to_status`, `action`, `note`, `metadata`.

---

## 11) Audit Trail

ملف: `LessonReviewEvent`

### Fields
- `lesson` (FK Lesson)
- `actor` (FK User, nullable for system events)
- `from_status` / `to_status` (char(20))
- `action` (choice من `REVIEW_ACTION_CHOICES`)
- `note` (text)
- `quality_score` (uint8, nullable)
- `metadata` (JSON dict — e.g. `{override: True, quality_score: 92}`)
- `created_at` (auto)

### Indexes
- `(lesson, -created_at)` — for the detail-page timeline.
- `(actor, -created_at)` — for "what did this teacher do".
- `(action)` — for "show all publishes".

### Coverage
9 action types tracked:
`start_review`, `approve`, `request_changes`, `reject`, `publish`, `unpublish`, `archive`, `note_added`, `quality_check`.

Tests:
- `test_start_review_writes_event` ✅
- `test_add_note_does_not_change_status` (و يكتب event) ✅

---

## 12) الاختبارات

| Test class | عدد | النتيجة |
|---|---|---|
| QualityCheckerTests | 8 | ✅ |
| WorkflowTransitionTests | 11 | ✅ |
| DashboardPermissionTests | 7 | ✅ |
| StudentVisibilityTests | 3 | ✅ |
| QualityCommandTests | 3 | ✅ |
| RegressionPreservedTests | 3 | ✅ |
| **مجموع Phase 11** | **35** | **✅** |

### Phase 11 tests (تفصيل)

**Quality checker:**
- `test_topic_01_gold_reference_scores_high` ✅
- `test_quality_checker_flags_missing_section` ✅
- `test_quality_checker_flags_missing_arabic` ✅
- `test_quality_checker_flags_forbidden_type_in_a0` ✅
- `test_quality_checker_flags_fallback_skill` ✅
- `test_quality_checker_flags_audio_underscore` ✅
- `test_quality_checker_flags_brand_risk` ✅
- `test_quality_checker_requires_8_to_12_questions` ✅

**Workflow transitions:**
- `test_start_review_changes_status` ✅
- `test_start_review_writes_event` ✅
- `test_request_changes_requires_note` ✅
- `test_request_changes_transitions` ✅
- `test_approve_clean_lesson_works` ✅
- `test_approve_refuses_when_errors_present` ✅
- `test_admin_override_can_force_approve` ✅
- `test_publish_requires_approved` ✅
- `test_publish_makes_lesson_visible` ✅
- `test_unpublish_hides_again` ✅
- `test_add_note_does_not_change_status` ✅

**Dashboard permissions:**
- `test_anonymous_redirected` ✅
- `test_student_cannot_access_dashboard` ✅
- `test_teacher_can_access_dashboard` ✅
- `test_admin_can_access_dashboard` ✅
- `test_dashboard_lists_pending_topics` ✅
- `test_dashboard_filter_by_status` ✅
- `test_detail_page_renders` ✅

**Student visibility:**
- `test_student_cannot_access_pending_lesson` ✅
- `test_student_cannot_access_approved_unpublished_lesson` ✅
- `test_student_can_access_published_lesson` ✅

**Management command:**
- `test_command_runs` ✅
- `test_command_saves_scores` ✅
- `test_command_fail_on_errors` ✅

**Regression:**
- `test_gold_reference_topic_01_status_preserved` ✅
- `test_topic_01_quality_score_high` ✅
- `test_phase10_47_topics_all_pending_review` ✅

### Regression — كل المراحل السابقة سليمة
- Challenge engine (18) ✅
- Question Types (39) ✅
- UI polish (34) ✅
- Super Lesson 01 (59) ✅
- Rewards Phase 5 (38) ✅
- Mastery Phase 6 (38) ✅
- AI Tutor Phase 7 (29) ✅
- Beginner 48 topics (36) ✅
- motivation suite (144) ✅
- learning_core suite (153) ✅
- tutor suite (75) ✅
- courses باقي الـ tests (278+) ✅

---

## 13) أوامر الاختبار ونتائجها

```bash
$ DJANGO_SETTINGS_MODULE=config.settings.test python manage.py check
System check identified no issues (0 silenced).

$ DJANGO_SETTINGS_MODULE=config.settings.test python manage.py test courses.tests.test_content_review_phase11
Ran 35 tests in 11.394s
OK

$ DJANGO_SETTINGS_MODULE=config.settings.test python manage.py test courses tutor motivation learning_core teacher_portal
Ran 939 tests in 146.187s
OK
```

أوامر تشغيلية للإنتاج:

```bash
# Prerequisites
python manage.py migrate
python manage.py seed_learning_skills
python manage.py seed_badge_definitions
python manage.py seed_super_lesson_01
python manage.py seed_beginner_48_topics --confirm

# Phase 11 — run quality checker on all topics + persist scores
python manage.py check_generated_content_quality --save
# Output: 47 pending_review topics, scores 92-100, 41 warnings, 0 errors.

# Open the dashboard (teacher group required):
# /teacher/content-review/
```

### Production results (from the dev DB)
- All 47 new topics score **92-100/100**.
- 41 warnings total (mostly the `fallback_skill` for the 5 mis-tagged questions).
- **0 errors** across all 47 topics.
- Topic 01 Gold Reference: **100/100** ✅.

---

## 14) Manual QA

### Run command
```
$ python manage.py check_generated_content_quality --save
Quality check: 95 lesson(s)        ← 48 new + ~47 stale pre-Phase-10
  ✅ T01 Introducing Yourself                              score=100 ...
  ✅ T02 Saying Hello and Goodbye                          score=100 ...
  ...
  ✅ T48 Studying and Future Goals                         score=100 ...
```

### Manual flow walkthrough
1. ✅ Login as teacher (or superuser).
2. ✅ Open `/teacher/content-review/`.
3. ✅ See 47 rows of `pending_review` topics + 1 row of `published` Topic 01 (если status_filter is empty).
4. ✅ Filter `?status=pending_review&fallback=1` → 5 rows (the topics with the `mistake_correction` warning).
5. ✅ Click Open → Topic 02 detail page.
6. ✅ "Quality flags (0)" panel shows "No quality issues detected. ✅" (Topic 02 is clean).
7. ✅ "Challenge questions (10)" table shows all 10 questions with skill chips.
8. ✅ "Audit trail (0)" empty initially.
9. ✅ Click `Start review` → status → `in_review`, event row created.
10. ✅ Click `Approve` → status → `approved`, quality_score persisted, `approved_by/at` set.
11. ✅ Click `Publish` → status → `published`, `published_at` set, lesson now visible to students.
12. ✅ Login as student → can open the now-published topic.
13. ✅ Login back as teacher → click `Unpublish` → status → `approved`, hidden from students again.

### Forbidden-path checks
1. ✅ Student opens `/teacher/content-review/` → 403.
2. ✅ Student tries direct URL to pending lesson → 404 (via `published_lesson_queryset`).
3. ✅ Teacher tries to publish a `pending_review` lesson directly → WorkflowError ("must be approved first").
4. ✅ Teacher tries to approve a lesson with broken content_html → WorkflowError ("quality checker reported errors").
5. ✅ Admin tries same → can override with `override=True`.

---

## 15) المشاكل المتبقية

### P0 — حاسمة
لا يوجد. ✅

### P1 — تمنع التعميم للطلاب
لا يوجد — كل الـ 47 درس في حالة `pending_review`، الطلاب لا يرونهم.

### P2 — تحسينات يمكن تأجيلها
1. **Triage workflow agents got empty args** — الـ `args` propagation للـ Workflow tool لم يعمل كما توقعت. الـ deterministic quality checker كافٍ، لكن الـ AI-assisted triage doc لاحقاً يمكن إعادة محاولته بـ inline data في الـ script.
2. **No bulk approve action** — الأستاذ يحتاج approve واحد-واحد. لـ 47 درس قد يكون مرهق. يستحق Django admin custom action.
3. **No diff viewer for "request changes" → resubmit** — الأستاذ يطلب changes لكن لا يرى الـ before/after عند الـ re-review.
4. **Audit-trail pagination** — حالياً يعرض آخر 50 events. للـ topics المُراجَعة كثيراً قد ينقص الـ history.
5. **Dashboard mobile not optimised** — desktop-first by design لـ teachers.

### P3 — لاحقاً
1. AI rewrite suggestions per quality flag.
2. Inline editing لكل question من الـ detail page.
3. Bulk publish action (with safeguards).
4. Email notification للـ teacher عند pending_review جديد.
5. Reviewer assignment ("assigned to me").
6. Review SLA tracking ("topic pending for X days").
7. Public Onlenco-internal style guide reference linked from each flag.

---

## 16) القرار النهائي

✅ **Review Workflow جاهز، ويمكن البدء بمراجعة بشرية للمحتوى.**

كل acceptance criteria محقّقة:
1. ✅ Review dashboard موجود (list + detail).
2. ✅ Teacher/Admin يستطيعون رؤية pending_review topics.
3. ✅ Student لا يستطيع رؤيتها (3 اختبارات).
4. ✅ Review detail يعرض كل: content / questions / skills / image prompts / audio scripts / flags / audit.
5. ✅ Quality checker يعمل (8 اختبارات).
6. ✅ Fallback skill warnings تظهر (filter + chip + flag).
7. ✅ Review actions تعمل (11 اختبارات state machine).
8. ✅ Audit trail يعمل (LessonReviewEvent).
9. ✅ Publish يتطلب `approved` (test يحرس).
10. ✅ Published فقط يظهر للطلاب (test يحرس).
11. ✅ Command `check_generated_content_quality` يعمل + يدعم `--save` / `--json` / `--fail-on-errors`.
12. ✅ 939 / 939 اختبار يمر.
13. ✅ `manage.py check` clean.
14. ✅ لا توليد صور أو صوت.
15. ✅ لا نشر تلقائي.

---

## 17) توصية المرحلة التالية

### Option A — **Prompt 12 — Human Review QA Pass for 47 Topics**
الأستاذ يدخل عبر `/teacher/content-review/` ويراجع كل topic واحد-واحد. بعد كل review:
- لو OK → `approve` (الـ status → approved).
- لو يحتاج تعديل → `request_changes` + note.
- لو ممتاز → `publish` للطلاب.

الـ Phase 11 system جاهز لاستضافة هذا الـ flow.

### Option B — **Prompt 12 — Media Generation Pilot (approved topics only)**
بعد ما الأستاذ يـ approve أو يـ publish عدد من الـ topics، الـ media generation pipeline يبدأ على الـ approved/published فقط. الـ Phase 11 يحدّد بوضوح أي topics جاهزة media-generation-wise.

### **لا تنشر كل topics للطلاب الآن.**
### **لا تبدأ media generation إلا للمواضيع approved فقط.**
### **لا تبدأ Prompt 12 بنفسك.**
**أنتظر مراجعة هذا التقرير من المستخدم.**

---

**انتهى تقرير Phase 11.**

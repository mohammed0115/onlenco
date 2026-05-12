# Teacher & Academic-Admin Authoring Workflow

Onlenco does **not** ship a front-end teacher portal. By design, all
course authoring happens through the Django admin (`/admin/`). This
document is the contract.

## Roles

Roles live as Django auth `Group`s, not as `Profile.role` values. They
are seeded by `python manage.py seed_role_groups`:

| Group           | Code                          | Can do                                            |
|-----------------|-------------------------------|---------------------------------------------------|
| Teacher         | `courses.permissions.GROUP_TEACHER`         | Create + edit own courses, units, lessons, quizzes; submit for review |
| Academic Admin  | `courses.permissions.GROUP_ACADEMIC_ADMIN`  | All of Teacher + approve / publish / reject submitted content |
| Finance Admin   | `courses.permissions.GROUP_FINANCE_ADMIN`   | Payment review (see `payments/admin.py`) |
| Support Admin   | `courses.permissions.GROUP_SUPPORT_ADMIN`   | Student support read-only |
| Super Admin     | (Django `is_superuser`)                     | Everything |

`Profile.role` (in `accounts/models.py`) only knows `student` and
`admin` — it is independent of the group-based permission system above
and is **not** consulted by `courses.permissions`.

## How to onboard a new teacher

1. `python manage.py seed_role_groups` (idempotent — run once per fresh
   deploy to ensure the groups exist).
2. In Django admin, create the user, set `is_staff=True` (required for
   admin access), and add them to the **Teacher** group.
3. The user logs in at `/admin/` and sees only Course / Lesson /
   LessonQuiz / LessonQuestion / LessonResource models. They are
   restricted to objects where `created_by=user` (lessons also include
   `course__created_by=user OR course__teacher=user`) — see
   `courses/permissions.py::filter_courses_for` and
   `filter_lessons_for`.

## Authoring lifecycle

```
draft  ─submit_for_review─▶  pending_review  ─approve─▶  published
        (Teacher)                                       (Academic Admin)
                                          ─reject─▶    draft  (with note)
                                                     ─archive─▶  archived
```

* `Course.status` and `Lesson.status` both follow the same workflow.
* Status-change actions are admin **bulk actions** (`courses/admin.py`):
  `submit_for_review_action`, `approve_action`, `reject_action`,
  `archive_action`.
* Each transition writes a `ContentReviewLog` row (generic FK, captures
  both Course and Lesson reviews) and an `AdminActionLog` row.
* The `status` field is read-only for non-publishers
  (`courses/admin.py:97-103`) so a Teacher cannot bypass review by
  editing the field directly.

## Visibility

`courses.services.student_flow.published_course_queryset()` is the
**only** entry point students hit. It filters `status="published"
AND is_active=True AND level__is_active=True`. Draft/pending courses
404 for non-staff users via `get_object_or_404(published_course_queryset(), …)`.

## Why no separate teacher portal

A custom teacher front-end would duplicate the Django admin's form
generation, validation, and audit log — and break the principle that
the same workflow buttons mean the same thing for every role. If you
need a teacher portal in the future, the right shape is a thin
read-only dashboard (course stats, review queue position) rather than
a re-implementation of the admin forms.

## Tests

Coverage lives in `courses/tests/`:

* `test_admin_workflow.py` — submit/approve/reject status transitions,
  reviewer stamping, log entries.
* `test_permissions.py` — Teacher sees only own content; non-publisher
  cannot approve.
* `test_student_flow.py` — drafts are invisible to students; level
  filter works; B1 student does not see A1 course.

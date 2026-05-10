# Student Learning Architecture

## Decision

Onlenco uses **Option A: the `courses` app is the single source of truth for student learning**.

Teachers and academic admins create courses, units, lessons, quizzes, and questions in `courses`. Student dashboards, onboarding recommendations, placement recommendations, course detail pages, and lesson detail pages all resolve visible learning content through `courses.services.student_flow`.

## Current Legacy Boundary

The older `lessons` app still exists for compatibility with legacy lesson, quiz, and progress URLs. It is not used to decide which teacher/admin-created courses appear on the student dashboard.

## Visibility Rules

Students only see courses that are:

- `Course.status="published"`
- `Course.is_active=True`
- attached to an active `CourseLevel`
- matched to the student's current CEFR level
- A0/A1 when the student selected the beginner onboarding path

Students do not see draft, pending review, archived, inactive, or lesson-inactive content.

## Recommendation Rules

Beginner onboarding seeds a `LearningRecommendation` for the first published A0/A1 course when one exists.

Placement completion seeds a `LearningRecommendation` for the first published course matching the assigned CEFR level when one exists.

The dashboard resolves the recommended course and next lesson from `courses.services.student_flow.dashboard_learning_plan_for_user`.

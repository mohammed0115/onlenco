from __future__ import annotations

from platform_admin.services.audit_log_service import log_action


def save_quiz(request, form, lesson):
    quiz = form.save(commit=False)
    quiz.lesson = lesson
    quiz.save()
    log_action(
        request,
        action_type="teacher.quiz.save",
        object_type="LessonQuiz",
        object_id=quiz.pk,
        description=f"Teacher saved quiz '{quiz.title}'",
        metadata={"lesson_id": lesson.pk, "course_id": lesson.course_id},
    )
    return quiz


def save_question(request, form, quiz):
    question = form.save(commit=False)
    question.quiz = quiz
    question.save()
    log_action(
        request,
        action_type="teacher.question.save",
        object_type="LessonQuestion",
        object_id=question.pk,
        description=f"Teacher saved question #{question.pk}",
        metadata={"quiz_id": quiz.pk, "lesson_id": quiz.lesson_id},
    )
    return question


"""Smoke + invariant tests for the 10 LMS models."""
from __future__ import annotations

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.test import TestCase

from courses.models import (
    Course, CourseEnrollment, CourseLevel, CourseUnit, Lesson,
    LessonQuestion, LessonQuiz, LessonResource,
)

User = get_user_model()


def _level(code="A2", order=2):
    return CourseLevel.objects.create(code=code, name=f"Level {code}", order=order)


def _user(username, **kwargs):
    return User.objects.create_user(username=username, password="pw", **kwargs)


class CourseLevelTests(TestCase):
    def test_unique_code(self):
        CourseLevel.objects.create(code="A1", name="Beginner")
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                CourseLevel.objects.create(code="A1", name="Dup")

    def test_str_includes_code_and_name(self):
        lvl = CourseLevel.objects.create(code="B1", name="Intermediate")
        self.assertIn("B1", str(lvl))
        self.assertIn("Intermediate", str(lvl))


class CourseTests(TestCase):
    def setUp(self):
        self.level = _level()
        self.teacher = _user("teach")

    def test_course_defaults_to_draft(self):
        c = Course.objects.create(
            title="Conv 101", slug="conv-101", level=self.level,
            teacher=self.teacher, created_by=self.teacher,
        )
        self.assertEqual(c.status, "draft")
        self.assertTrue(c.is_active)

    def test_unique_slug(self):
        Course.objects.create(title="A", slug="dup", level=self.level)
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                Course.objects.create(title="B", slug="dup", level=self.level)


class LessonTests(TestCase):
    def setUp(self):
        self.level = _level()
        self.course = Course.objects.create(
            title="C", slug="c", level=self.level,
        )

    def test_lesson_defaults_to_draft(self):
        l = Lesson.objects.create(course=self.course, title="L1")
        self.assertEqual(l.status, "draft")

    def test_lesson_str(self):
        l = Lesson.objects.create(course=self.course, title="L1")
        self.assertIn("L1", str(l))
        self.assertIn(self.course.title, str(l))


class LessonQuestionValidationTests(TestCase):
    def setUp(self):
        level = _level()
        course = Course.objects.create(title="C", slug="qc", level=level)
        lesson = Lesson.objects.create(course=course, title="L")
        self.quiz = LessonQuiz.objects.create(lesson=lesson, title="Q")

    def test_mcq_requires_two_options(self):
        q = LessonQuestion(
            quiz=self.quiz, question_type="multiple_choice",
            question_text="?", options=["only one"], correct_answer="only one",
        )
        with self.assertRaises(ValidationError):
            q.full_clean()

    def test_mcq_correct_answer_must_be_in_options(self):
        q = LessonQuestion(
            quiz=self.quiz, question_type="multiple_choice",
            question_text="?", options=["a", "b", "c"],
            correct_answer="zzz",
        )
        with self.assertRaises(ValidationError):
            q.full_clean()

    def test_mcq_valid(self):
        q = LessonQuestion(
            quiz=self.quiz, question_type="multiple_choice",
            question_text="?", options=["a", "b"], correct_answer="a",
        )
        q.full_clean()  # must not raise


class CourseEnrollmentTests(TestCase):
    def setUp(self):
        self.level = _level()
        self.course = Course.objects.create(title="C", slug="ec", level=self.level)
        self.user = _user("stu")

    def test_unique_user_course(self):
        CourseEnrollment.objects.create(user=self.user, course=self.course)
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                CourseEnrollment.objects.create(user=self.user, course=self.course)


class CourseUnitTests(TestCase):
    def test_ordering(self):
        level = _level()
        course = Course.objects.create(title="C", slug="uc", level=level)
        u2 = CourseUnit.objects.create(course=course, title="U2", order=2)
        u1 = CourseUnit.objects.create(course=course, title="U1", order=1)
        units = list(course.units.all())
        self.assertEqual(units, [u1, u2])

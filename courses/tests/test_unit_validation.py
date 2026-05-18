"""Unit-level validation tests (Course → Unit → max 3 Lessons rule)."""
from __future__ import annotations

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.test import TestCase

from courses.models import Course, CourseLevel, CourseUnit, Lesson


User = get_user_model()


class CourseUnitLessonCapTests(TestCase):
    def setUp(self):
        self.level = CourseLevel.objects.create(code="A1", name="A1", order=1)
        self.teacher = User.objects.create_user(username="t@x.com", email="t@x.com", password="pw")
        self.course = Course.objects.create(
            title="Test Course", slug="test-course",
            level=self.level, teacher=self.teacher, status="published",
        )
        self.unit = CourseUnit.objects.create(course=self.course, title="Unit 1", order=1)

    def _make_lesson(self, order: int, *, unit: CourseUnit | None) -> Lesson:
        return Lesson.objects.create(
            course=self.course, unit=unit, title=f"L{order}",
            order=order, lesson_type="reading",
        )

    def test_three_lessons_attach_fine(self):
        self._make_lesson(1, unit=self.unit)
        self._make_lesson(2, unit=self.unit)
        self._make_lesson(3, unit=self.unit)
        self.assertEqual(self.unit.lesson_count, 3)

    def test_attaching_fourth_lesson_to_full_unit_raises(self):
        self._make_lesson(1, unit=self.unit)
        self._make_lesson(2, unit=self.unit)
        self._make_lesson(3, unit=self.unit)
        l4 = Lesson(
            course=self.course, unit=self.unit, title="L4",
            order=4, lesson_type="reading",
        )
        with self.assertRaises(ValidationError):
            l4.full_clean()

    def test_lessons_with_null_unit_unaffected(self):
        # Three legacy lessons sitting outside any unit — no constraint.
        for i in range(5):
            self._make_lesson(i, unit=None)
        self.assertEqual(self.unit.lesson_count, 0)
        self.assertEqual(self.course.lessons.filter(unit__isnull=True).count(), 5)

    def test_moving_a_lesson_to_full_unit_blocked(self):
        self._make_lesson(1, unit=self.unit)
        self._make_lesson(2, unit=self.unit)
        self._make_lesson(3, unit=self.unit)
        loose = self._make_lesson(4, unit=None)
        loose.unit = self.unit
        with self.assertRaises(ValidationError):
            loose.full_clean()


class CourseUnitPublishGateTests(TestCase):
    def setUp(self):
        self.level = CourseLevel.objects.create(code="A1", name="A1", order=1)
        self.teacher = User.objects.create_user(username="t2@x.com", email="t2@x.com", password="pw")
        self.course = Course.objects.create(
            title="C2", slug="c2", level=self.level, teacher=self.teacher,
        )

    def test_is_complete_false_with_two_lessons(self):
        unit = CourseUnit.objects.create(course=self.course, title="U", order=1)
        Lesson.objects.create(course=self.course, unit=unit, title="A", order=1, lesson_type="reading")
        Lesson.objects.create(course=self.course, unit=unit, title="B", order=2, lesson_type="reading")
        self.assertFalse(unit.is_complete)
        self.assertFalse(unit.can_be_published())

    def test_is_complete_true_with_three_active_lessons(self):
        unit = CourseUnit.objects.create(course=self.course, title="U", order=1)
        for i in range(1, 4):
            Lesson.objects.create(
                course=self.course, unit=unit, title=f"L{i}", order=i,
                lesson_type="reading", is_active=True,
            )
        self.assertTrue(unit.is_complete)
        self.assertTrue(unit.can_be_published())

    def test_publish_with_only_2_lessons_raises(self):
        unit = CourseUnit.objects.create(course=self.course, title="U", order=1)
        Lesson.objects.create(course=self.course, unit=unit, title="A", order=1, lesson_type="reading")
        Lesson.objects.create(course=self.course, unit=unit, title="B", order=2, lesson_type="reading")
        unit.is_published = True
        with self.assertRaises(ValidationError):
            unit.full_clean()

    def test_publish_with_3_lessons_passes(self):
        unit = CourseUnit.objects.create(course=self.course, title="U", order=1)
        for i in range(1, 4):
            Lesson.objects.create(
                course=self.course, unit=unit, title=f"L{i}", order=i,
                lesson_type="reading", is_active=True,
            )
        unit.is_published = True
        unit.full_clean()  # should not raise

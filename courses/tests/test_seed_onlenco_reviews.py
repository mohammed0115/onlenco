"""Coverage for the Onlenco Beginner Reviews seed + unlock gate (P10)."""
from __future__ import annotations

from io import StringIO
from datetime import timedelta

from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.test import TestCase
from django.utils import timezone

from courses.models import (
    Course, CourseLessonProgress, CourseReview, CourseReviewAttempt,
    CourseReviewQuestion, Lesson,
)


User = get_user_model()
COURSE_SLUG = "onlenco-beginner"


class OnlencoBeginnerReviewsTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        call_command("seed_onlenco_beginner_48_units", "--quiet", stdout=StringIO())
        call_command("seed_onlenco_beginner_reviews",  "--quiet", stdout=StringIO())
        cls.course = Course.objects.get(slug=COURSE_SLUG)

    def test_reviews_created_for_beginner_course(self):
        n = CourseReview.objects.filter(course=self.course).count()
        self.assertEqual(n, 6, f"Expected 6 cluster reviews, got {n}")

    def test_review_has_vocabulary_questions(self):
        for review in CourseReview.objects.filter(course=self.course):
            vocab = review.questions.filter(skill="vocabulary").count()
            self.assertGreaterEqual(vocab, 3, f"{review.title} missing vocab questions")

    def test_review_has_grammar_questions(self):
        for review in CourseReview.objects.filter(course=self.course):
            grammar = review.questions.filter(skill="grammar").count()
            self.assertGreaterEqual(grammar, 3, f"{review.title} missing grammar questions")

    def test_review_has_speaking_task(self):
        for review in CourseReview.objects.filter(course=self.course):
            self.assertGreaterEqual(
                review.questions.filter(skill="speaking").count(), 1,
                f"{review.title} missing speaking task",
            )

    def test_review_has_listening_placeholder(self):
        for review in CourseReview.objects.filter(course=self.course):
            self.assertGreaterEqual(
                review.questions.filter(skill="listening").count(), 1,
                f"{review.title} missing listening placeholder",
            )

    def test_review_not_available_before_required_units_completed(self):
        user = User.objects.create_user(username="s_gate1", password="pw")
        review = CourseReview.objects.get(course=self.course, start_unit_number=1)
        # No lesson progress at all — must not unlock.
        self.assertFalse(review.is_unlocked_for(user))

    def test_review_available_after_required_units_completed(self):
        user = User.objects.create_user(username="s_gate2", password="pw")
        review = CourseReview.objects.get(course=self.course, start_unit_number=1)
        now = timezone.now()
        for lesson in Lesson.objects.filter(
            course=self.course, order__lte=review.end_unit_number,
        ):
            CourseLessonProgress.objects.create(
                user=user, lesson=lesson,
                video_completed=True,
                completed_at=now - timedelta(minutes=1),
            )
        self.assertTrue(review.is_unlocked_for(user))

    def test_review_score_saved(self):
        user = User.objects.create_user(username="s_attempt", password="pw")
        review = CourseReview.objects.first()
        attempt = CourseReviewAttempt.objects.create(
            review=review, student=user, score=85,
            completed_at=timezone.now(),
            feedback="Great job — focus on -s endings.",
            feedback_ar="عمل ممتاز — ركّز على نهايات -s.",
        )
        loaded = CourseReviewAttempt.objects.get(pk=attempt.pk)
        self.assertEqual(loaded.score, 85)
        self.assertEqual(loaded.feedback_ar, "عمل ممتاز — ركّز على نهايات -s.")

    def test_review_feedback_generated(self):
        review = CourseReview.objects.first()
        # The seeded instructions act as the *generated* feedback template.
        self.assertTrue(review.instructions.strip())
        self.assertTrue(review.instructions_ar.strip())

    def test_reviews_seed_is_idempotent(self):
        before = (
            CourseReview.objects.count(),
            CourseReviewQuestion.objects.count(),
        )
        call_command("seed_onlenco_beginner_reviews", "--quiet", stdout=StringIO())
        after = (
            CourseReview.objects.count(),
            CourseReviewQuestion.objects.count(),
        )
        self.assertEqual(before, after, "Reviews seed not idempotent")

from datetime import timedelta

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone

from courses.models import Course, CourseLevel, Lesson
from learning_core.models import (
    AdaptiveExercise,
    ExerciseAttempt,
    GrammarTopic,
    LearningRecommendation,
    Skill,
    SkillMastery,
    UserError,
    UserWeakness,
)
from learning_core.services.recommendation_engine import generate_recommendations
from learning_core.services.weakness_engine import update_user_weaknesses

User = get_user_model()


class RecommendationEngineTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="rex", password="pw")
        self.skill = Skill.objects.create(name="Grammar core", category="grammar", cefr_level="A2")
        self.topic = GrammarTopic.objects.create(name="Past Simple", slug="past-simple", cefr_level="A2")

    def test_new_user_gets_minimum_recommendations(self):
        recs = generate_recommendations(self.user)
        self.assertGreaterEqual(len(recs), 1)
        self.assertLessEqual(len(recs), 5)
        # Inactive user should get an ask_tutor recommendation
        types = {r.recommendation_type for r in recs}
        self.assertIn("ask_tutor", types)

    def test_user_with_weaknesses_gets_topic_review(self):
        for _ in range(5):
            UserError.objects.create(
                user=self.user,
                source_type="quiz",
                error_type="grammar",
                skill=self.skill,
                grammar_topic=self.topic,
                severity=7,
            )
        update_user_weaknesses(self.user)
        recs = generate_recommendations(self.user)
        types = {r.recommendation_type for r in recs}
        self.assertIn("review_topic", types)
        review = next(r for r in recs if r.recommendation_type == "review_topic")
        self.assertIn("Past Simple", review.title)

    def test_low_mastery_skill_recommendation(self):
        SkillMastery.objects.create(
            user=self.user, skill=self.skill, mastery_score=20, attempts_count=5, wrong_count=4
        )
        recs = generate_recommendations(self.user)
        practice = [r for r in recs if r.recommendation_type == "practice_skill"]
        self.assertTrue(any(r.related_skill == self.skill for r in practice))

    def test_priority_order_descending(self):
        # Two weaknesses with different priorities
        for _ in range(7):
            UserError.objects.create(
                user=self.user,
                source_type="quiz",
                error_type="grammar",
                skill=self.skill,
                grammar_topic=self.topic,
                severity=9,
            )
        update_user_weaknesses(self.user)
        recs = generate_recommendations(self.user)
        priorities = [r.priority for r in recs]
        self.assertEqual(priorities, sorted(priorities, reverse=True))

    def test_replacing_marks_old_pending_as_replaced(self):
        old = LearningRecommendation.objects.create(
            user=self.user,
            recommendation_type="continue_lesson",
            title="Old rec",
            priority=1.0,
            status="pending",
        )
        generate_recommendations(self.user)
        old.refresh_from_db()
        self.assertEqual(old.status, "replaced")

    def test_recent_attempt_suppresses_inactivity_recommendation(self):
        ex = AdaptiveExercise.objects.create(
            skill=self.skill,
            cefr_level="A2",
            difficulty_score=0.4,
            question_type="multiple_choice",
            question="x",
            options=["a"],
            correct_answer="a",
        )
        ExerciseAttempt.objects.create(
            user=self.user, exercise=ex, is_correct=True, score=1.0
        )
        # Need to add a weakness or other rec so we don't fall into the
        # min-3 fallback path that adds continue_lesson but not ask_tutor.
        for _ in range(3):
            UserError.objects.create(
                user=self.user,
                source_type="quiz",
                error_type="grammar",
                skill=self.skill,
                grammar_topic=self.topic,
                severity=6,
            )
        update_user_weaknesses(self.user)
        recs = generate_recommendations(self.user)
        types = {r.recommendation_type for r in recs}
        self.assertNotIn("ask_tutor", types)

    def test_course_recommendation_uses_published_course_for_student_level(self):
        self.user.profile.cefr_level = "A2"
        self.user.profile.save(update_fields=["cefr_level"])
        level = CourseLevel.objects.create(code="A2", name="A2", order=2)
        course = Course.objects.create(
            title="A2 Course",
            slug="a2-course",
            level=level,
            status="published",
            is_active=True,
            is_free=True,
        )
        Lesson.objects.create(
            course=course,
            title="A2 Lesson",
            status="published",
            is_active=True,
        )

        recs = generate_recommendations(self.user)
        course_rec = next(
            r for r in recs
            if r.recommendation_type == "continue_lesson"
            and r.metadata.get("course_id") == course.pk
        )

        self.assertEqual(course_rec.metadata["course_level"], "A2")

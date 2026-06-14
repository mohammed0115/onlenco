from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from courses import permissions as perms
from courses.models import (
    Course, CourseEnrollment, CourseLevel, Lesson, LessonQuestion, LessonQuiz,
)
from courses.services.student_flow import (
    dashboard_courses_for_user,
    dashboard_learning_plan_for_user,
    seed_beginner_course_recommendation,
    seed_level_course_recommendation,
)
from learning_core.models import LearningRecommendation, StudentLearningProfile


User = get_user_model()


LEVEL_ORDER = {
    "A0": 0,
    "A1": 1,
    "A2": 2,
    "B1": 3,
    "B2": 4,
    "C1": 5,
    "C2": 6,
}


class StudentCourseFlowTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="learner", password="pw")
        self.user.profile.cefr_level = "A1"
        self.user.profile.preferred_language = "en"
        self.user.profile.save(update_fields=["cefr_level", "preferred_language"])
        self.client.force_login(self.user)

    def _level(self, code="A1"):
        return CourseLevel.objects.get_or_create(
            code=code,
            defaults={"name": f"Level {code}", "order": LEVEL_ORDER[code]},
        )[0]

    def _course(
        self,
        *,
        title="Course",
        slug="course",
        level_code="A1",
        status="published",
        is_active=True,
        is_free=True,
        lesson_status="published",
        lesson_active=True,
    ):
        course = Course.objects.create(
            title=title,
            slug=slug,
            description=f"{title} description",
            level=self._level(level_code),
            status=status,
            is_active=is_active,
            is_free=is_free,
        )
        lesson = Lesson.objects.create(
            course=course,
            title=f"{title} Lesson",
            content_html="<p>Welcome to the lesson.</p>",
            status=lesson_status,
            is_active=lesson_active,
            order=1,
        )
        return course, lesson

    def test_dashboard_service_returns_only_published_courses_for_student_level(self):
        visible, _ = self._course(title="Visible A1", slug="visible-a1")
        self._course(title="Hidden A2", slug="hidden-a2", level_code="A2")
        self._course(title="Hidden B2", slug="hidden-b2", level_code="B2")
        self._course(title="Hidden Draft", slug="hidden-draft", status="draft")
        self._course(title="Hidden Pending", slug="hidden-pending", status="pending_review")
        self._course(title="Hidden Archived", slug="hidden-archived", status="archived")
        self._course(title="Hidden Inactive", slug="hidden-inactive", is_active=False)

        courses = dashboard_courses_for_user(self.user)
        self.assertEqual([course.pk for course in courses], [visible.pk])

    def test_course_visible_but_unpublished_or_inactive_lessons_hidden(self):
        course, published = self._course(title="Mixed Lessons", slug="mixed-lessons")
        Lesson.objects.create(
            course=course,
            title="Draft Lesson",
            status="draft",
            is_active=True,
            order=2,
        )
        Lesson.objects.create(
            course=course,
            title="Inactive Lesson",
            status="published",
            is_active=False,
            order=3,
        )

        response = self.client.get(reverse("courses:course_detail", args=[course.pk]))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, published.title)
        self.assertNotContains(response, "Draft Lesson")
        self.assertNotContains(response, "Inactive Lesson")

    def test_b1_student_sees_all_levels_up_to_b1(self):
        # A B1 student sees every level from A0 through B1 (cumulative), but
        # not B2 and above.
        self.user.profile.cefr_level = "B1"
        self.user.profile.save(update_fields=["cefr_level"])
        a1_course, _ = self._course(title="A1 Course", slug="a1-course", level_code="A1")
        b1_course, _ = self._course(title="B1 Course", slug="b1-course", level_code="B1")
        self._course(title="B2 Course", slug="b2-course", level_code="B2")

        courses = dashboard_courses_for_user(self.user)

        pks = [course.pk for course in courses]
        self.assertIn(a1_course.pk, pks)        # lower level visible
        self.assertIn(b1_course.pk, pks)        # current level visible
        self.assertEqual(pks, [a1_course.pk, b1_course.pk])  # B2 hidden, ordered

    def test_learning_profile_current_level_overrides_profile_level(self):
        StudentLearningProfile.objects.create(
            user=self.user,
            current_cefr_level="B1",
        )
        a1_course, _ = self._course(title="A1 Course", slug="a1-profile", level_code="A1")
        b1_course, _ = self._course(title="B1 Course", slug="b1-learning-profile", level_code="B1")

        courses = dashboard_courses_for_user(self.user)

        # current level comes from the learning profile (B1) → A0..B1 visible.
        self.assertEqual([course.pk for course in courses], [a1_course.pk, b1_course.pk])

    def test_beginner_student_gets_first_beginner_course_recommendation(self):
        self.user.profile.cefr_level = "A0"
        self.user.profile.onboarding_path = "beginner_start"
        self.user.profile.save(update_fields=["cefr_level", "onboarding_path"])
        a1_course, _ = self._course(title="A1 Beginner", slug="a1-beginner", level_code="A1")
        self._course(title="B1 Course", slug="b1-not-beginner", level_code="B1")

        seed_beginner_course_recommendation(self.user)
        plan = dashboard_learning_plan_for_user(self.user)

        self.assertEqual(plan["recommended_course"].pk, a1_course.pk)
        self.assertTrue(
            LearningRecommendation.objects.filter(
                user=self.user,
                metadata__source="beginner_onboarding",
                metadata__course_id=a1_course.pk,
            ).exists()
        )

    def test_placement_student_gets_level_course_recommendation(self):
        self.user.profile.cefr_level = "B1"
        self.user.profile.onboarding_path = "placement_test"
        self.user.profile.save(update_fields=["cefr_level", "onboarding_path"])
        course, _ = self._course(title="Placement B1", slug="placement-b1", level_code="B1")

        seed_level_course_recommendation(self.user, "B1", source="placement")
        plan = dashboard_learning_plan_for_user(self.user)

        self.assertEqual(plan["recommended_course"].pk, course.pk)
        self.assertTrue(
            LearningRecommendation.objects.filter(
                user=self.user,
                metadata__source="placement",
                metadata__course_id=course.pk,
            ).exists()
        )

    def test_dashboard_plan_shows_recommended_course_next_lesson_progress_and_quiz(self):
        course, lesson = self._course(title="Plan Course", slug="plan-course")
        quiz = LessonQuiz.objects.create(lesson=lesson, title="Plan Quiz", is_active=True)
        LessonQuestion.objects.create(
            quiz=quiz,
            question_type="multiple_choice",
            question_text="Choose one",
            options=["one", "two"],
            correct_answer="one",
        )
        CourseEnrollment.objects.create(
            user=self.user,
            course=course,
            progress_percentage=35,
        )

        plan = dashboard_learning_plan_for_user(self.user)

        self.assertEqual(plan["current_level"], "A1")
        self.assertEqual(plan["recommended_course"], course)
        self.assertEqual(plan["recommended_lesson"], lesson)
        self.assertEqual(plan["progress_percentage"], 35)
        self.assertEqual(plan["quiz_status"]["state"], "available")
        self.assertIn(reverse("courses:lesson_detail", args=[course.pk, lesson.pk]), plan["continue_url"])

    def test_dashboard_renders_published_courses_next_to_legacy_lessons(self):
        self._course(title="Dashboard Course", slug="dashboard-course")

        response = self.client.get(reverse("dashboard"), HTTP_ACCEPT_LANGUAGE="en")

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Dashboard Course")
        self.assertEqual(response.context["student_courses"][0].title, "Dashboard Course")
        self.assertEqual(response.context["learning_plan"]["recommended_course"].title, "Dashboard Course")

    def test_course_detail_creates_enrollment_for_free_course(self):
        course, lesson = self._course(title="Free Course", slug="free-course")

        response = self.client.get(reverse("courses:course_detail", args=[course.pk]))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Free Course Lesson")
        self.assertTrue(CourseEnrollment.objects.filter(user=self.user, course=course).exists())
        self.assertContains(response, reverse("courses:lesson_detail", args=[course.pk, lesson.pk]))

    def test_paid_course_detail_does_not_enroll_unsubscribed_student(self):
        course, _ = self._course(title="Paid Course", slug="paid-course", is_free=False)

        response = self.client.get(reverse("courses:course_detail", args=[course.pk]))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Subscribe to open this course")
        self.assertFalse(CourseEnrollment.objects.filter(user=self.user, course=course).exists())

    def test_paid_course_lesson_blocks_unsubscribed_student(self):
        course, lesson = self._course(title="Locked Course", slug="locked-course", is_free=False)

        response = self.client.get(reverse("courses:lesson_detail", args=[course.pk, lesson.pk]))

        self.assertEqual(response.status_code, 403)
        self.assertFalse(CourseEnrollment.objects.filter(user=self.user, course=course).exists())

    def test_paid_course_lesson_enrolls_subscribed_student(self):
        self.user.profile.subscription_status = "active"
        self.user.profile.save(update_fields=["subscription_status"])
        course, lesson = self._course(title="Subscribed Course", slug="subscribed-course", is_free=False)

        response = self.client.get(reverse("courses:lesson_detail", args=[course.pk, lesson.pk]))

        self.assertEqual(response.status_code, 200)
        # Lesson launcher renders the title + "Start the lesson" CTA in
        # the hero (replaced inline content_html in the new design).
        self.assertContains(response, lesson.title)
        self.assertContains(response, "onlenco-cta-start")
        self.assertTrue(CourseEnrollment.objects.filter(user=self.user, course=course).exists())

    def test_teacher_cannot_publish_without_academic_admin_permission(self):
        self.assertFalse(perms.can_publish_course(self.user))

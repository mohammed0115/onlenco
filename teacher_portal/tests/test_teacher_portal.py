from django.template.loader import render_to_string
from django.test import RequestFactory
from django.utils import translation

from courses.models import Course, ContentReviewLog, Lesson, LessonQuestion, LessonQuiz
from notifications import constants as C
from notifications.models import NotificationEvent
from platform_admin.models import PlatformAuditLog
from teacher_portal.models import StudentAssignmentSubmission, TeacherAssignment, TeacherStudentNote
from teacher_portal.services.role_service import ROLE_STUDENT, ROLE_TEACHER, RoleService

from .utils import TeacherPortalTestMixin


class MultiRoleTests(TeacherPortalTestMixin):
    def test_teacher_with_default_student_profile_is_not_student(self):
        # Per the Admin+Teacher spec: belonging to the Teacher group flips
        # an account out of the student bucket, even when the legacy
        # ``profile.role`` field still reads "student".
        roles = RoleService.get_user_roles(self.teacher)
        self.assertNotIn(ROLE_STUDENT, roles)
        self.assertIn(ROLE_TEACHER, roles)
        # Profile.is_student is the raw flag; RoleService is the authority
        # for routing. Keep the property check as documentation.
        self.assertTrue(self.teacher.profile.is_student)
        self.assertTrue(self.teacher.profile.is_teacher)

    def test_role_switcher_shows_teacher_mode_only_if_user_is_teacher(self):
        request = RequestFactory().get("/")
        request.user = self.teacher
        with translation.override("en"):
            html = render_to_string(
                "_app_header.html",
                {
                    "request": request,
                    "lang": "en",
                    "can_access_teacher_portal": True,
                    "can_access_control_center": False,
                    "show_student_mode": False,
                    "primary_role_label": "Teacher",
                },
            )
        # New header uses "Teacher Portal" instead of legacy "Teacher Mode";
        # admin+teacher accounts no longer expose Student Mode.
        self.assertIn("Teacher Portal", html)
        self.assertNotIn("Student Mode", html)

        request.user = self.student
        with translation.override("en"):
            html = render_to_string(
                "_app_header.html",
                {
                    "request": request,
                    "lang": "en",
                    "can_access_teacher_portal": False,
                    "can_access_control_center": False,
                    "show_student_mode": False,
                    "primary_role_label": "",
                },
            )
        self.assertNotIn("Teacher Portal", html)

    def test_student_only_user_cannot_access_teacher_dashboard(self):
        self.client.force_login(self.student)
        response = self.client.get("/teacher/dashboard/")
        self.assertEqual(response.status_code, 403)

    def test_teacher_can_access_teacher_dashboard(self):
        self.client.force_login(self.teacher)
        response = self.client.get("/teacher/dashboard/")
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Teacher Dashboard")

    def test_switch_role_saves_active_role_in_session(self):
        self.client.force_login(self.teacher)
        response = self.client.get("/teacher/switch/teacher/")
        self.assertEqual(response.status_code, 302)
        self.assertEqual(self.client.session["active_role"], "teacher")

    def test_teacher_only_login_starts_on_teacher_dashboard(self):
        teacher_only = self.make_user(
            "teacheronly@example.com",
            role="admin",
            group="Teacher",
            is_staff=True,
        )
        response = self.client.post(
            "/auth/",
            {"mode": "signin", "username": teacher_only.email, "password": "pw"},
        )
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, "/teacher/dashboard/")


class TeacherCourseWorkflowTests(TeacherPortalTestMixin):
    def test_teacher_course_create_page_still_renders(self):
        self.client.force_login(self.teacher)
        response = self.client.get("/teacher/courses/create/")
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "tp-wizard-stepper")
        self.assertContains(response, "teacher.css?v=p166e-logo-fix-20260604")

    def test_teacher_course_create_not_blank(self):
        self.client.force_login(self.teacher)
        response = self.client.get("/teacher/courses/create/")
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "<form", html=False)
        self.assertContains(response, "tp-wizard-actions")

    def test_course_create_uses_stepper(self):
        self.client.force_login(self.teacher)
        response = self.client.get("/teacher/courses/create/")
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "tp-wizard-stepper")
        self.assertContains(response, "data-step-panel=\"5\"")

    def test_course_create_no_raw_json(self):
        self.client.force_login(self.teacher)
        response = self.client.get("/teacher/courses/create/")
        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, "JSON")

    def test_teacher_course_filters_work(self):
        self.client.force_login(self.teacher)
        response = self.client.get("/teacher/courses/", {"status": "draft", "language": "bilingual"})
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, self.course.title)
        self.assertNotContains(response, self.other_course.title)

    def test_teacher_can_create_course_and_status_defaults_to_draft(self):
        self.client.force_login(self.teacher)
        response = self.client.post(
            "/teacher/courses/create/",
            {
                "title_ar": "كورس جديد",
                "title_en": "New Course",
                "description_ar": "وصف",
                "description_en": "Description",
                "level": self.level.pk,
                "language": "bilingual",
                "objectives_ar": "هدف",
                "objectives_en": "Goal",
                "estimated_duration_hours": 4,
            },
        )
        self.assertEqual(response.status_code, 302)
        course = Course.objects.get(title_en="New Course")
        self.assertEqual(course.status, "draft")
        self.assertEqual(course.teacher, self.teacher)

    def test_teacher_can_edit_own_draft_course(self):
        self.client.force_login(self.teacher)
        response = self.client.post(
            f"/teacher/courses/{self.course.pk}/edit/",
            {
                "title_ar": "محدث",
                "title_en": "Updated Course",
                "description_ar": "",
                "description_en": "Updated",
                "level": self.level.pk,
                "language": "en",
                "objectives_ar": "",
                "objectives_en": "",
                "estimated_duration_hours": 5,
            },
        )
        self.assertEqual(response.status_code, 302)
        self.course.refresh_from_db()
        self.assertEqual(self.course.title, "Updated Course")

    def test_teacher_cannot_edit_another_teachers_course(self):
        self.client.force_login(self.teacher)
        response = self.client.get(f"/teacher/courses/{self.other_course.pk}/edit/")
        self.assertEqual(response.status_code, 404)

    def test_teacher_cannot_publish_course_directly(self):
        self.client.force_login(self.teacher)
        response = self.client.post(f"/admin/courses/{self.course.pk}/publish/")
        self.assertIn(response.status_code, [302, 403])
        self.course.refresh_from_db()
        self.assertNotEqual(self.course.status, "published")

    def test_teacher_can_submit_course_for_review(self):
        self.client.force_login(self.teacher)
        response = self.client.post(f"/teacher/courses/{self.course.pk}/submit-review/")
        self.assertEqual(response.status_code, 302)
        self.course.refresh_from_db()
        self.assertEqual(self.course.status, "pending_review")
        self.assertTrue(ContentReviewLog.objects.filter(object_id=self.course.pk, status="pending").exists())
        self.assertTrue(PlatformAuditLog.objects.filter(action_type="teacher.course.submit_review").exists())

    def test_academic_admin_can_approve_teacher_course(self):
        self.course.status = "pending_review"
        self.course.save(update_fields=["status"])
        self.client.force_login(self.academic_admin)
        response = self.client.post(f"/admin/courses/{self.course.pk}/approve/")
        self.assertEqual(response.status_code, 302)
        self.course.refresh_from_db()
        self.assertEqual(self.course.status, "published")
        self.assertTrue(NotificationEvent.objects.filter(event_type=C.TEACHER_COURSE_APPROVED, user=self.teacher).exists())


class TeacherLessonQuizTests(TeacherPortalTestMixin):
    def test_teacher_lesson_create_page_still_renders(self):
        self.client.force_login(self.teacher)
        response = self.client.get(f"/teacher/courses/{self.course.pk}/lessons/create/")
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "tp-wizard-stepper")
        self.assertContains(response, "teacher.css?v=p166e-logo-fix-20260604")

    def test_teacher_lesson_create_not_blank(self):
        self.client.force_login(self.teacher)
        response = self.client.get(f"/teacher/courses/{self.course.pk}/lessons/create/")
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "<form", html=False)
        self.assertContains(response, "tp-wizard-actions")

    def test_lesson_create_uses_stepper(self):
        self.client.force_login(self.teacher)
        response = self.client.get(f"/teacher/courses/{self.course.pk}/lessons/create/")
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "tp-wizard-stepper")
        self.assertContains(response, "data-step-panel=\"5\"")

    def test_lesson_create_no_raw_json(self):
        self.client.force_login(self.teacher)
        response = self.client.get(f"/teacher/courses/{self.course.pk}/lessons/create/")
        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, "JSON")

    def test_teacher_can_add_lesson_to_own_course(self):
        self.client.force_login(self.teacher)
        response = self.client.post(
            f"/teacher/courses/{self.course.pk}/lessons/create/",
            {
                "title_ar": "درس",
                "title_en": "New Lesson",
                "order": 2,
                "lesson_type": "reading",
                "cefr_level": "A1",
                "skill": "reading",
                "grammar_topic": "",
                "vocabulary_topic": "",
                "content_ar": "محتوى",
                "content_en": "Content",
                "video_url": "",
                "transcript": "",
                "duration_minutes": 12,
            },
        )
        self.assertEqual(response.status_code, 302)
        self.assertTrue(Lesson.objects.filter(title_en="New Lesson", course=self.course).exists())

    def test_teacher_can_add_quiz_to_own_lesson(self):
        self.client.force_login(self.teacher)
        response = self.client.post(
            f"/teacher/lessons/{self.lesson.pk}/quiz/",
            {
                "title_ar": "اختبار",
                "title_en": "Lesson Quiz",
                "passing_score": 70,
                "time_limit_minutes": 10,
                "is_active": "on",
            },
        )
        self.assertEqual(response.status_code, 302)
        self.assertTrue(LessonQuiz.objects.filter(lesson=self.lesson, title_en="Lesson Quiz").exists())

    def _mcq_payload(self, **overrides):
        data = {
            "question_type": "multiple_choice",
            "question_text_ar": "سؤال؟",
            "question_text_en": "Question?",
            "option_1": "A",
            "option_2": "B",
            "option_3": "",
            "option_4": "",
            "correct_option": "1",
            "correct_answer": "",
            "explanation_ar": "",
            "explanation_en": "Because",
            "difficulty_score": "0.4",
            "points": 2,
            "order": 1,
        }
        data.update(overrides)
        return data

    def test_teacher_can_add_questions(self):
        quiz = LessonQuiz.objects.create(lesson=self.lesson, title="Quiz", title_en="Quiz")
        self.client.force_login(self.teacher)
        response = self.client.post(f"/teacher/quizzes/{quiz.pk}/questions/", self._mcq_payload())
        self.assertEqual(response.status_code, 302)
        q = LessonQuestion.objects.get(quiz=quiz)
        self.assertEqual(q.correct_answer, "A")
        self.assertEqual(q.options, ["A", "B"])

    def test_quiz_question_builder_is_visual_stepper(self):
        quiz = LessonQuiz.objects.create(lesson=self.lesson, title="Quiz", title_en="Quiz")
        self.client.force_login(self.teacher)
        html = self.client.get(f"/teacher/quizzes/{quiz.pk}/questions/").content.decode()
        self.assertIn("tp-qb-stepper", html)
        self.assertIn("data-answer-builder", html)
        self.assertIn("id_option_1", html)
        self.assertIn("tp-qb-preview", html)

    def test_quiz_question_builder_no_json_for_normal_teacher(self):
        quiz = LessonQuiz.objects.create(lesson=self.lesson, title="Quiz", title_en="Quiz")
        self.client.force_login(self.teacher)
        html = self.client.get(f"/teacher/quizzes/{quiz.pk}/questions/").content.decode()
        # The advanced JSON escape hatch must never render for a normal teacher.
        self.assertNotIn("tp-qb-advanced", html)
        self.assertNotIn("options_json", html)

    def test_quiz_question_builder_text_answer_saves(self):
        quiz = LessonQuiz.objects.create(lesson=self.lesson, title="Quiz", title_en="Quiz")
        self.client.force_login(self.teacher)
        response = self.client.post(
            f"/teacher/quizzes/{quiz.pk}/questions/",
            self._mcq_payload(question_type="fill_blank", option_1="", option_2="", correct_option="", correct_answer="went"),
        )
        self.assertEqual(response.status_code, 302)
        q = LessonQuestion.objects.get(quiz=quiz)
        self.assertEqual(q.correct_answer, "went")
        self.assertEqual(q.options, [])

    def test_quiz_question_edit_prefills_visual_options(self):
        quiz = LessonQuiz.objects.create(lesson=self.lesson, title="Quiz", title_en="Quiz")
        q = LessonQuestion.objects.create(
            quiz=quiz, question_type="multiple_choice", question_text_en="Q",
            options=["Cat", "Dog"], correct_answer="Dog", order=1,
        )
        self.client.force_login(self.teacher)
        html = self.client.get(f"/teacher/questions/{q.pk}/edit/").content.decode()
        self.assertIn("tp-qb-stepper", html)
        self.assertIn('value="Cat"', html)
        self.assertIn('value="Dog"', html)


class TeacherStudentAssignmentTests(TeacherPortalTestMixin):
    def test_teacher_students_page_has_table_wrap(self):
        self.client.force_login(self.teacher)
        response = self.client.get("/teacher/students/")
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'class="table-wrap"')

    def test_teacher_students_page_table_not_direct_child_of_main(self):
        self.client.force_login(self.teacher)
        html = self.client.get("/teacher/students/").content.decode()
        self.assertNotIn('<main class="teacher-content">\n  <table class="teacher-table">', html)
        self.assertIn('<div class="table-wrap">', html)

    def test_teacher_students_action_buttons_inside_table_wrap(self):
        self.client.force_login(self.teacher)
        html = self.client.get("/teacher/students/").content.decode()
        self.assertIn('class="row-actions"', html)
        self.assertIn('class="table-wrap"', html)

    def test_all_teacher_table_pages_use_table_wrap(self):
        self.client.force_login(self.teacher)
        students_html = self.client.get("/teacher/students/").content.decode()
        courses_html = self.client.get("/teacher/courses/").content.decode()
        self.assertIn('class="table-wrap"', students_html)
        self.assertIn('class="table-wrap"', courses_html)

    def test_no_duplicate_sidebar_on_teacher_students(self):
        self.client.force_login(self.teacher)
        html = self.client.get("/teacher/students/").content.decode()
        self.assertEqual(html.count('id="teacher-sidebar"'), 1)

    def test_teacher_sees_only_students_enrolled_in_own_courses(self):
        self.client.force_login(self.teacher)
        response = self.client.get("/teacher/students/")
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, self.student.email)
        self.assertNotContains(response, self.student2.email)

    def test_teacher_cannot_see_payment_proof(self):
        self.client.force_login(self.teacher)
        response = self.client.get(f"/admin/payments/{self.payment.pk}/proof/")
        self.assertIn(response.status_code, [302, 403])

    def test_teacher_can_add_note_to_student(self):
        self.client.force_login(self.teacher)
        response = self.client.post(
            f"/teacher/students/{self.student.pk}/notes/",
            {
                "course": self.course.pk,
                "note": "Good work in this lesson. Focus more on short sentence pronunciation.",
                "visibility": "student_visible",
                "needs_support": "",
            },
        )
        self.assertEqual(response.status_code, 302)
        self.assertTrue(TeacherStudentNote.objects.filter(student=self.student, teacher=self.teacher).exists())

    def test_teacher_can_create_assignment(self):
        self.client.force_login(self.teacher)
        response = self.client.post(
            "/teacher/assignments/create/",
            {
                "course": self.course.pk,
                "lesson": self.lesson.pk,
                "title_ar": "واجب",
                "title_en": "Writing Assignment",
                "instructions_ar": "اكتب فقرة",
                "instructions_en": "Write a paragraph",
                "assignment_type": "writing",
                "xp_reward": 10,
                "is_active": "on",
            },
        )
        self.assertEqual(response.status_code, 302)
        self.assertTrue(TeacherAssignment.objects.filter(title_en="Writing Assignment").exists())

    def test_student_can_submit_assignment_and_notification_created(self):
        assignment = TeacherAssignment.objects.create(
            teacher=self.teacher,
            course=self.course,
            lesson=self.lesson,
            title_en="Homework",
            assignment_type="writing",
            is_active=True,
        )
        self.client.force_login(self.student)
        response = self.client.post(
            f"/teacher/assignments/{assignment.pk}/submit/",
            {"text_answer": "My answer"},
        )
        self.assertEqual(response.status_code, 302)
        self.assertTrue(StudentAssignmentSubmission.objects.filter(assignment=assignment, student=self.student).exists())
        self.assertTrue(NotificationEvent.objects.filter(event_type=C.TEACHER_ASSIGNMENT_SUBMITTED, user=self.teacher).exists())

    def test_teacher_can_review_assignment(self):
        assignment = TeacherAssignment.objects.create(
            teacher=self.teacher,
            course=self.course,
            lesson=self.lesson,
            title_en="Homework",
        )
        submission = StudentAssignmentSubmission.objects.create(
            assignment=assignment,
            student=self.student,
            text_answer="My answer",
        )
        self.client.force_login(self.teacher)
        response = self.client.post(
            f"/teacher/submissions/{submission.pk}/review/",
            {"score": 88, "feedback": "Good work", "status": "reviewed"},
        )
        self.assertEqual(response.status_code, 302)
        submission.refresh_from_db()
        self.assertEqual(submission.score, 88)
        self.assertTrue(PlatformAuditLog.objects.filter(action_type="teacher.assignment.review").exists())


class TeacherUiAnalyticsTests(TeacherPortalTestMixin):
    def test_teacher_analytics_loads(self):
        self.client.force_login(self.teacher)
        response = self.client.get("/teacher/analytics/")
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Teacher Analytics")

    def test_arabic_rtl_works(self):
        self.teacher.profile.preferred_language = "ar"
        self.teacher.profile.save(update_fields=["preferred_language"])
        self.client.force_login(self.teacher)
        response = self.client.get("/teacher/dashboard/")
        self.assertContains(response, 'dir="rtl"')
        self.assertContains(response, "لوحة المعلم")

    def test_english_ltr_works(self):
        self.teacher.profile.preferred_language = "en"
        self.teacher.profile.save(update_fields=["preferred_language"])
        self.client.force_login(self.teacher)
        response = self.client.get("/teacher/dashboard/")
        self.assertContains(response, 'dir="ltr"')
        self.assertContains(response, "Teacher Dashboard")

    def test_teacher_notification_page_loads(self):
        NotificationEvent.objects.create(event_type=C.TEACHER_CONTENT_NEEDS_REVISION, user=self.teacher, payload={"course": "x"})
        self.client.force_login(self.teacher)
        response = self.client.get("/teacher/notifications/")
        self.assertEqual(response.status_code, 200)
        # The page shows a human-readable title, not the raw event key.
        self.assertContains(response, "Content needs revision")
        self.assertNotContains(response, C.TEACHER_CONTENT_NEEDS_REVISION)


class TeacherQuickQuizInLessonTests(TeacherPortalTestMixin):
    """Phase 16.7C — quick quiz / questions live INSIDE the Lesson Builder."""

    def _add_url(self):
        return f"/teacher/lessons/{self.lesson.pk}/quick-quiz/add/"

    def _payload(self, **overrides):
        data = {
            "question_type": "multiple_choice",
            "question_text_ar": "سؤال؟",
            "question_text_en": "Question?",
            "option_1": "A", "option_2": "B", "option_3": "", "option_4": "",
            "correct_option": "1", "correct_answer": "",
            "explanation_ar": "", "explanation_en": "",
            "difficulty_score": "0.5", "points": 1, "order": 1,
        }
        data.update(overrides)
        return data

    def _lesson_create_payload(self, **overrides):
        data = {
            "title_ar": "درس", "title_en": "Lesson X", "order": 3,
            "lesson_type": "reading", "cefr_level": "A1", "skill": "reading",
            "grammar_topic": "", "vocabulary_topic": "",
            "content_ar": "محتوى", "content_en": "Content",
            "video_url": "", "transcript": "", "duration_minutes": 10,
        }
        data.update(overrides)
        return data

    def test_lesson_builder_includes_quick_quiz_step(self):
        self.client.force_login(self.teacher)
        html = self.client.get(f"/teacher/lessons/{self.lesson.pk}/edit/").content.decode()
        self.assertIn("data-quickquiz", html)
        self.assertIn("data-qq-add", html)
        self.assertIn('data-step-panel="4"', html)
        self.assertIn("data-answer-builder", html)

    def test_lesson_builder_quick_quiz_has_no_raw_json(self):
        self.client.force_login(self.teacher)
        html = self.client.get(f"/teacher/lessons/{self.lesson.pk}/edit/").content.decode()
        self.assertNotIn("options_json", html)
        self.assertNotIn("tp-qb-advanced", html)

    def test_lesson_create_redirects_into_builder(self):
        self.client.force_login(self.teacher)
        resp = self.client.post(
            f"/teacher/courses/{self.course.pk}/lessons/create/",
            self._lesson_create_payload(),
        )
        self.assertEqual(resp.status_code, 302)
        # Continues inside the same lesson so the quiz step is live.
        self.assertRegex(resp["Location"], r"/teacher/lessons/\d+/edit/")

    def test_quick_quiz_add_creates_quiz_and_question(self):
        self.client.force_login(self.teacher)
        resp = self.client.post(self._add_url(), self._payload())
        self.assertEqual(resp.status_code, 200)
        body = resp.json()
        self.assertTrue(body["ok"])
        quiz = LessonQuiz.objects.get(lesson=self.lesson)
        q = LessonQuestion.objects.get(quiz=quiz)
        self.assertEqual(q.correct_answer, "A")
        self.assertEqual(q.options, ["A", "B"])

    def test_quick_quiz_requires_question_text(self):
        self.client.force_login(self.teacher)
        resp = self.client.post(
            self._add_url(), self._payload(question_text_ar="", question_text_en="")
        )
        self.assertEqual(resp.status_code, 400)
        self.assertFalse(resp.json()["ok"])
        self.assertFalse(LessonQuestion.objects.filter(quiz__lesson=self.lesson).exists())

    def test_quick_quiz_requires_correct_answer(self):
        self.client.force_login(self.teacher)
        resp = self.client.post(
            self._add_url(), self._payload(correct_option="", correct_answer="")
        )
        self.assertEqual(resp.status_code, 400)
        self.assertFalse(LessonQuestion.objects.filter(quiz__lesson=self.lesson).exists())

    def test_quick_quiz_requires_question_type(self):
        self.client.force_login(self.teacher)
        resp = self.client.post(self._add_url(), self._payload(question_type=""))
        self.assertEqual(resp.status_code, 400)
        self.assertFalse(LessonQuestion.objects.filter(quiz__lesson=self.lesson).exists())

    def test_quick_quiz_add_does_not_publish_lesson(self):
        self.client.force_login(self.teacher)
        self.client.post(self._add_url(), self._payload())
        self.lesson.refresh_from_db()
        self.assertEqual(self.lesson.status, "draft")

    def test_quick_quiz_add_creates_no_student_progress(self):
        from courses.models import ChallengeAnswer, ChallengeSession
        self.client.force_login(self.teacher)
        self.client.post(self._add_url(), self._payload())
        self.assertEqual(ChallengeSession.objects.count(), 0)
        self.assertEqual(ChallengeAnswer.objects.count(), 0)

    def test_student_cannot_add_quick_quiz(self):
        self.client.force_login(self.student)
        resp = self.client.post(self._add_url(), self._payload())
        self.assertEqual(resp.status_code, 403)
        self.assertFalse(LessonQuestion.objects.filter(quiz__lesson=self.lesson).exists())

    def test_teacher_cannot_add_to_unowned_lesson(self):
        self.client.force_login(self.teacher2)
        resp = self.client.post(self._add_url(), self._payload())
        self.assertIn(resp.status_code, (403, 404))
        self.assertFalse(LessonQuestion.objects.filter(quiz__lesson=self.lesson).exists())

    def test_quick_quiz_delete_removes_question(self):
        quiz = LessonQuiz.objects.create(lesson=self.lesson, title="Q", title_en="Q")
        q = LessonQuestion.objects.create(
            quiz=quiz, question_type="fill_blank", question_text_en="Q",
            correct_answer="x", order=1,
        )
        self.client.force_login(self.teacher)
        resp = self.client.post(
            f"/teacher/lessons/{self.lesson.pk}/quick-quiz/{q.pk}/delete/"
        )
        self.assertEqual(resp.status_code, 200)
        self.assertTrue(resp.json()["ok"])
        self.assertFalse(LessonQuestion.objects.filter(pk=q.pk).exists())

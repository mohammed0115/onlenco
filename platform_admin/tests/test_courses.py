from django.test import TestCase

from courses.models import Lesson, LessonResource
from platform_admin.models import PlatformAuditLog
from platform_admin.tests.utils import PlatformAdminTestMixin
from django.core.files.uploadedfile import SimpleUploadedFile


class PlatformCourseTests(PlatformAdminTestMixin, TestCase):
    def test_admin_courses_detail_page_still_renders(self):
        self.client.force_login(self.academic_admin)
        response = self.client.get(f"/admin/courses/{self.course.pk}/")
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, self.course.title)

    def test_course_filters_work(self):
        self.client.force_login(self.academic_admin)
        response = self.client.get("/admin/courses/", {"status": "pending_review"})
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, self.course.title)
        self.assertNotContains(response, self.other_course.title)

    def test_course_approval_creates_audit_log(self):
        self.client.force_login(self.academic_admin)
        response = self.client.post(f"/admin/courses/{self.course.pk}/approve/")
        self.assertEqual(response.status_code, 302)
        self.course.refresh_from_db()
        self.assertEqual(self.course.status, "published")
        self.assertTrue(PlatformAuditLog.objects.filter(action_type="course.approve").exists())

    def test_lesson_editor_supports_video_and_worksheet(self):
        self.client.force_login(self.teacher)
        response = self.client.post(
            f"/admin/courses/{self.course.pk}/lessons/new/",
            {
                "title": "Video lesson 1",
                "order": 1,
                "lesson_type": "listening",
                "cefr_level": "A1",
                "skill": "listening",
                "duration_minutes": 10,
                "status": "draft",
                "is_active": "on",
                "worksheet_title": "Worksheet 1",
                "video_file": SimpleUploadedFile("lesson.mp4", b"video", content_type="video/mp4"),
                "worksheet_file": SimpleUploadedFile("worksheet.pdf", b"%PDF-1.4", content_type="application/pdf"),
            },
        )
        self.assertEqual(response.status_code, 302)
        lesson = Lesson.objects.get(title="Video lesson 1")
        self.assertEqual(lesson.course, self.course)
        self.assertTrue(LessonResource.objects.filter(lesson=lesson, resource_type="worksheet").exists())

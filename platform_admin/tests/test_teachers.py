from django.test import TestCase

from platform_admin.tests.utils import PlatformAdminTestMixin


class PlatformTeacherTests(PlatformAdminTestMixin, TestCase):
    def test_teacher_sees_only_own_courses(self):
        self.client.force_login(self.teacher)
        response = self.client.get("/control/courses/")
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, self.course.title)
        self.assertNotContains(response, self.other_course.title)

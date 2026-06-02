from django.test import TestCase, override_settings
from django.utils import timezone
from rest_framework.test import APIClient

from ai_usage import constants as C
from ai_usage.services import usage_logger

from .helpers import give_plan, make_user


def make_admin(username="admin"):
    u = make_user(username)
    u.is_staff = True
    u.save(update_fields=["is_staff"])
    return u


def make_teacher(username="teacher"):
    return make_user(username, role="teacher")


class ApiTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.student = make_user("student1")
        give_plan(self.student, 10)

    def test_anonymous_cannot_access(self):
        resp = self.client.get("/api/ai-usage/summary/today/")
        self.assertIn(resp.status_code, (401, 403))

    def test_student_can_view_own_limit(self):
        self.client.force_authenticate(self.student)
        resp = self.client.get("/api/ai-usage/limits/me/")
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(str(resp.data["allowed_minutes"]), "10.00")
        self.assertIn("remaining_minutes", resp.data)

    def test_student_cannot_view_other_user_usage(self):
        other = make_user("other")
        self.client.force_authenticate(self.student)
        resp = self.client.get(f"/api/ai-usage/users/{other.id}/")
        self.assertEqual(resp.status_code, 403)

    def test_student_can_view_own_user_detail(self):
        self.client.force_authenticate(self.student)
        resp = self.client.get(f"/api/ai-usage/users/{self.student.id}/")
        self.assertEqual(resp.status_code, 200)

    @override_settings(AI_USAGE_STUDENT_CAN_VIEW_COST=False)
    def test_student_cannot_see_cost(self):
        usage_logger.log_success(user=self.student, feature="other",
                                 model_name="gpt-4o-mini", input_tokens=10, output_tokens=10)
        self.client.force_authenticate(self.student)
        resp = self.client.get("/api/ai-usage/summary/today/")
        self.assertEqual(resp.status_code, 200)
        self.assertNotIn("estimated_cost_usd", resp.data)

    def test_admin_can_view_all_usage(self):
        usage_logger.log_success(user=self.student, feature="other",
                                 model_name="gpt-4o-mini", input_tokens=10, output_tokens=10)
        admin = make_admin()
        self.client.force_authenticate(admin)
        resp = self.client.get("/api/ai-usage/summary/today/")
        self.assertEqual(resp.status_code, 200)
        self.assertIn("estimated_cost_usd", resp.data)
        self.assertGreaterEqual(resp.data["requests"], 1)

    def test_teacher_limited_scope(self):
        # Teacher's own row + a student's row; teacher only sees their own.
        teacher = make_teacher()
        usage_logger.log_success(user=teacher, role=C.ROLE_TEACHER,
                                 feature=C.FEATURE_CONTENT_GENERATION,
                                 model_name="gpt-4o-mini", input_tokens=10, output_tokens=10)
        usage_logger.log_success(user=self.student, feature="other",
                                 model_name="gpt-4o-mini", input_tokens=99, output_tokens=99)
        self.client.force_authenticate(teacher)
        resp = self.client.get("/api/ai-usage/daily/")
        self.assertEqual(resp.status_code, 200)
        usernames = {row["user"] for row in resp.data["results"]}
        self.assertEqual(usernames, {teacher.id})

    def test_recalculate_admin_only(self):
        self.client.force_authenticate(self.student)
        self.assertEqual(self.client.post("/api/ai-usage/recalculate/").status_code, 403)
        self.client.force_authenticate(make_admin("admin2"))
        resp = self.client.post("/api/ai-usage/recalculate/", {"date": str(timezone.localdate())})
        self.assertEqual(resp.status_code, 200)
        self.assertIn("summaries_written", resp.data)

    def test_features_endpoint_admin_only(self):
        self.client.force_authenticate(self.student)
        self.assertEqual(self.client.get("/api/ai-usage/features/").status_code, 403)
        self.client.force_authenticate(make_admin("admin3"))
        self.assertEqual(self.client.get("/api/ai-usage/features/").status_code, 200)

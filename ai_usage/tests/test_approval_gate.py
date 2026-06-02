"""Pending students must not consume AI (Student Approval Gate)."""
from unittest import mock

from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings

from ai_usage import constants as C
from ai_usage.models import AIUsageLog
from ai_usage.services import ai_client

from accounts.models import APPROVAL_APPROVED, APPROVAL_PENDING_ADMIN

from .helpers import FakeResponse, chat_json

User = get_user_model()


def _student(status):
    u = User.objects.create_user(username=f"{status}@x.com", email=f"{status}@x.com",
                                 password="pw12345!")
    p = u.profile
    p.role = "student"
    p.email_verified = True
    p.approval_status = status
    p.save()
    return u


@override_settings(AI_API_KEY="sk-test", AI_USAGE_TRACKING_ENABLED=True,
                   ONLENCO_STUDENT_APPROVAL_REQUIRED=True)
class ApprovalGateAITests(TestCase):
    def test_pending_student_cannot_start_ai_tutor(self):
        u = _student(APPROVAL_PENDING_ADMIN)
        with mock.patch.object(ai_client.requests, "post") as post:
            with self.assertRaises(ai_client.AccountPendingApproval):
                ai_client.chat([{"role": "user", "content": "hi"}], user=u,
                               feature=C.FEATURE_AI_TUTOR)
        post.assert_not_called()  # provider never hit

    def test_pending_student_cannot_use_challenge_ai(self):
        u = _student(APPROVAL_PENDING_ADMIN)
        with mock.patch.object(ai_client.requests, "post") as post:
            with self.assertRaises(ai_client.AccountPendingApproval):
                ai_client.chat([{"role": "user", "content": "x"}], user=u,
                               feature=C.FEATURE_CHALLENGE_EXPLANATION)
        post.assert_not_called()

    def test_pending_student_ai_call_does_not_hit_provider_or_cost(self):
        u = _student(APPROVAL_PENDING_ADMIN)
        with mock.patch.object(ai_client.requests, "post"):
            try:
                ai_client.chat([{"role": "user", "content": "x"}], user=u,
                               feature=C.FEATURE_AI_TUTOR)
            except ai_client.AccountPendingApproval:
                pass
        log = AIUsageLog.objects.get()
        self.assertEqual(log.status, C.STATUS_CANCELLED)
        self.assertEqual(log.estimated_cost_usd, 0)
        self.assertEqual(log.total_tokens, 0)
        self.assertEqual(log.metadata.get("blocked_reason"), "account_pending_approval")

    def test_pending_student_stt_blocked(self):
        u = _student(APPROVAL_PENDING_ADMIN)
        with mock.patch.object(ai_client.requests, "post") as post:
            with self.assertRaises(ai_client.AccountPendingApproval):
                ai_client.transcribe_audio(b"x", user=u, feature=C.FEATURE_PLACEMENT_SPEAKING)
        post.assert_not_called()

    def test_approved_student_ai_call_proceeds(self):
        u = _student(APPROVAL_APPROVED)
        with mock.patch.object(ai_client.requests, "post",
                               return_value=FakeResponse(json_data=chat_json())):
            data = ai_client.chat([{"role": "user", "content": "hi"}], user=u,
                                  feature=C.FEATURE_AI_TUTOR)
        self.assertEqual(data["choices"][0]["message"]["content"], "hello")
        log = AIUsageLog.objects.get()
        self.assertEqual(log.status, C.STATUS_SUCCESS)

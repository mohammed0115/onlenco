from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from django.utils import timezone

from motivation import constants as C
from motivation.models import LearnerActivitySnapshot, MotivationMessage
from motivation.services import ai_message_generator

User = get_user_model()


class AIMessageGeneratorTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username="ai@x.com", email="ai@x.com", password="pw"
        )
        self.snap = LearnerActivitySnapshot.objects.create(
            user=self.user,
            date=timezone.localdate(),
            lessons_completed=2,
            quiz_accuracy=85.0,
            current_streak_days=3,
        )

    @override_settings(AI_API_KEY="")
    def test_no_api_key_falls_back_to_template(self):
        msg = ai_message_generator.build_message_with_ai(
            self.user, message_type=C.MSG_ENCOURAGEMENT, snap=self.snap,
        )
        self.assertIsInstance(msg, MotivationMessage)
        # Template path doesn't tag source=ai
        self.assertNotEqual(msg.metadata.get("source"), "ai")

    @override_settings(AI_API_KEY="sk-test")
    def test_failing_llm_falls_back(self):
        with patch.object(ai_message_generator.requests, "post",
                          side_effect=RuntimeError("network")):
            msg = ai_message_generator.build_message_with_ai(
                self.user, message_type=C.MSG_ENCOURAGEMENT, snap=self.snap,
            )
        self.assertIsInstance(msg, MotivationMessage)
        self.assertNotEqual(msg.metadata.get("source"), "ai")

    @override_settings(AI_API_KEY="sk-test")
    def test_successful_llm_uses_ai_body(self):
        fake = type("R", (), {})()
        fake.raise_for_status = lambda: None
        fake.json = lambda: {
            "choices": [{"message": {"content": "Nice work — you nailed 85% accuracy today!"}}]
        }
        with patch.object(ai_message_generator.requests, "post", return_value=fake):
            msg = ai_message_generator.build_message_with_ai(
                self.user, message_type=C.MSG_ENCOURAGEMENT, snap=self.snap,
            )
        self.assertEqual(msg.metadata.get("source"), "ai")
        self.assertIn("85%", msg.message)

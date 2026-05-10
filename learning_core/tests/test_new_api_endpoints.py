from io import BytesIO
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from rest_framework.authtoken.models import Token

User = get_user_model()


@override_settings(AI_API_KEY="")
class TokenAuthTests(TestCase):
    def test_token_endpoint_returns_token_for_valid_creds(self):
        User.objects.create_user(username="tk", password="pw123456")
        r = self.client.post(
            "/api/v1/auth/token/", {"username": "tk", "password": "pw123456"}
        )
        self.assertEqual(r.status_code, 200)
        self.assertIn("token", r.json())

    def test_token_endpoint_rejects_invalid_creds(self):
        r = self.client.post(
            "/api/v1/auth/token/", {"username": "x", "password": "wrong"}
        )
        self.assertEqual(r.status_code, 400)

    def test_token_authenticates_protected_endpoint(self):
        u = User.objects.create_user(username="tk2", password="pw")
        token = Token.objects.create(user=u)
        r = self.client.get(
            reverse("learning_api:profile"), HTTP_AUTHORIZATION=f"Token {token.key}"
        )
        self.assertEqual(r.status_code, 200)

    @override_settings(API_TOKEN_MAX_AGE_DAYS=30)
    def test_expired_token_is_rejected(self):
        u = User.objects.create_user(username="oldtoken", password="pw")
        token = Token.objects.create(user=u)
        Token.objects.filter(pk=token.pk).update(
            created=timezone.now() - timezone.timedelta(days=31)
        )

        r = self.client.get(
            reverse("learning_api:profile"), HTTP_AUTHORIZATION=f"Token {token.key}"
        )

        self.assertEqual(r.status_code, 401)
        self.assertFalse(Token.objects.filter(pk=token.pk).exists())


@override_settings(AI_API_KEY="")
class OpenAPISchemaTests(TestCase):
    def test_schema_endpoint_serves(self):
        u = User.objects.create_user(username="sc", password="pw")
        self.client.force_login(u)
        r = self.client.get("/api/v1/schema/")
        self.assertEqual(r.status_code, 200)
        # Default response is YAML; just check it has a recognizable header
        self.assertIn(b"openapi:", r.content[:200].lower() if isinstance(r.content, bytes) else r.content[:200].encode())


@override_settings(AI_API_KEY="")
class TutorAPITests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="t", password="pw")
        self.user.profile.subscription_status = "active"
        self.user.profile.subscription_expires_at = timezone.now() + timezone.timedelta(days=30)
        self.user.profile.save(update_fields=["subscription_status", "subscription_expires_at"])
        self.client.force_login(self.user)

    def test_tutor_chat_requires_subscription(self):
        self.user.profile.subscription_status = "inactive"
        self.user.profile.subscription_expires_at = None
        self.user.profile.save(update_fields=["subscription_status", "subscription_expires_at"])

        r = self.client.post(
            reverse("learning_api:tutor_chat"),
            data={"message": "Hello tutor", "topic": "greetings"},
            content_type="application/json",
        )

        self.assertEqual(r.status_code, 402)

    def test_tutor_chat_creates_conversation_and_returns_reply(self):
        r = self.client.post(
            reverse("learning_api:tutor_chat"),
            data={"message": "Hello tutor", "topic": "greetings"},
            content_type="application/json",
        )
        self.assertEqual(r.status_code, 200)
        body = r.json()
        self.assertIn("conversation_id", body)
        self.assertIn("reply", body)

    def test_tutor_chat_other_users_conversation_blocked(self):
        from tutor.models import TutorConversation
        other = User.objects.create_user(username="other", password="pw")
        conv = TutorConversation.objects.create(user=other, topic="x")
        r = self.client.post(
            reverse("learning_api:tutor_chat"),
            data={"message": "Hi", "conversation_id": conv.id},
            content_type="application/json",
        )
        self.assertEqual(r.status_code, 404)


@override_settings(AI_API_KEY="")
class PlacementAPITests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="p", password="pw")
        self.client.force_login(self.user)

    def test_placement_submit_returns_diagnostic(self):
        r = self.client.post(
            reverse("learning_api:placement_submit"),
            data={
                "q1": "goes",
                "q2": "If I had known, I would have helped.",
                "q3": "I like football very much",
                "q4": "Yesterday I went to the market",
                "q5": "Every morning I wake up and drink tea then go to school.",
            },
            content_type="application/json",
        )
        self.assertEqual(r.status_code, 201)
        body = r.json()
        self.assertIn("cefr_level", body)
        self.assertIn("written_score", body)


class SpeakingApiTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="s", password="pw")
        self.client.force_login(self.user)

    @override_settings(AI_API_KEY="")
    def test_speaking_endpoint_rejects_missing_audio(self):
        r = self.client.post(reverse("learning_api:placement_speaking"))
        self.assertEqual(r.status_code, 400)

    @override_settings(AI_API_KEY="")
    def test_speaking_endpoint_returns_zero_transcript_without_ai(self):
        audio = SimpleUploadedFile("a.webm", b"\x00" * 1000, content_type="audio/webm")
        r = self.client.post(
            reverse("learning_api:placement_speaking"), data={"audio": audio}
        )
        self.assertEqual(r.status_code, 200)
        body = r.json()
        self.assertIn("transcript", body)
        self.assertIn("fluency_score", body)

    @override_settings(AI_API_KEY="key", AI_API_BASE="https://x", AI_MODEL="m")
    def test_speaking_endpoint_uses_stt_when_configured(self):
        from placement.services import stt as stt_module

        class R:
            status_code = 200

            def json(self_inner):
                return {"text": "Hello world how are you", "duration": 5}

            def raise_for_status(self_inner):
                pass

        audio = SimpleUploadedFile("a.webm", b"\x00" * 1000, content_type="audio/webm")
        with patch.object(stt_module.requests, "post", return_value=R()):
            r = self.client.post(
                reverse("learning_api:placement_speaking"), data={"audio": audio}
            )
        body = r.json()
        self.assertEqual(body["transcript"], "Hello world how are you")
        self.assertEqual(body["duration_seconds"], 5)


@override_settings(AI_API_KEY="")
class SpeakingPersistenceTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="sp", password="pw")
        self.client.force_login(self.user)

    def test_speaking_then_submit_persists_audio_fields(self):
        from placement.models import PlacementResult

        # Step 1: simulate speaking upload (heuristic STT returns empty text)
        audio = SimpleUploadedFile("a.webm", b"\x00" * 1000, content_type="audio/webm")
        r = self.client.post(reverse("learning_api:placement_speaking"), data={"audio": audio})
        self.assertEqual(r.status_code, 200)
        # session has pending_speaking
        self.assertIn("pending_speaking", self.client.session)

        # Step 2: submit placement; the pending speaking metadata should attach
        r2 = self.client.post(
            reverse("learning_api:placement_submit"),
            data={
                "q1": "goes",
                "q2": "If I had known, I would have helped.",
                "q3": "I like reading books in the evenings.",
                "q4": "Yesterday I went to the market and bought apples.",
                "q5": "Every morning I wake up at six.",
            },
            content_type="application/json",
        )
        self.assertEqual(r2.status_code, 201)
        body = r2.json()
        self.assertIn("placement_id", body)
        placement = PlacementResult.objects.get(pk=body["placement_id"])
        # duration was buffered (>=0); transcript may be empty without AI
        self.assertGreaterEqual(placement.audio_duration_seconds, 0)
        # session was consumed
        self.assertNotIn("pending_speaking", self.client.session)


@override_settings(AI_API_KEY="")
class TutorVoiceApiTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="tv", password="pw")
        self.user.profile.subscription_status = "active"
        self.user.profile.subscription_expires_at = timezone.now() + timezone.timedelta(days=30)
        self.user.profile.save(update_fields=["subscription_status", "subscription_expires_at"])
        self.client.force_login(self.user)

    def test_voice_endpoint_requires_subscription(self):
        self.user.profile.subscription_status = "inactive"
        self.user.profile.subscription_expires_at = None
        self.user.profile.save(update_fields=["subscription_status", "subscription_expires_at"])

        r = self.client.post(reverse("learning_api:tutor_voice"))

        self.assertEqual(r.status_code, 402)

    def test_voice_endpoint_rejects_missing_audio(self):
        r = self.client.post(reverse("learning_api:tutor_voice"))
        self.assertEqual(r.status_code, 400)

    def test_voice_endpoint_422_on_empty_transcription(self):
        audio = SimpleUploadedFile("a.webm", b"\x00" * 100, content_type="audio/webm")
        r = self.client.post(
            reverse("learning_api:tutor_voice"), data={"audio": audio}
        )
        # Without AI_API_KEY, transcript is empty → 422
        self.assertEqual(r.status_code, 422)

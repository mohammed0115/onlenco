from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone

from motivation import constants as C
from motivation.models import (
    Achievement,
    LearnerActivitySnapshot,
    MotivationMessage,
)
from motivation.services import message_generator

User = get_user_model()


class MessageGeneratorTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username="msguser", email="msg@x.com", password="pw"
        )

    def test_arabic_user_gets_arabic_message(self):
        self.user.profile.preferred_language = "ar"
        self.user.profile.save()
        snap = LearnerActivitySnapshot.objects.create(
            user=self.user,
            date=timezone.localdate(),
            current_streak_days=7,
        )
        msg = message_generator.build_message(
            self.user, message_type=C.MSG_STREAK, snap=snap
        )
        self.assertEqual(msg.language, "ar")
        # Title should contain the Arabic word for streak
        self.assertIn("سلسلة", msg.title)

    def test_english_default(self):
        # Profile defaults to Arabic now; flip to English for this case.
        self.user.profile.preferred_language = "en"
        self.user.profile.save(update_fields=["preferred_language"])
        snap = LearnerActivitySnapshot.objects.create(
            user=self.user,
            date=timezone.localdate(),
        )
        msg = message_generator.build_message(
            self.user, message_type=C.MSG_ENCOURAGEMENT, snap=snap
        )
        self.assertEqual(msg.language, "en")
        self.assertEqual(msg.message_type, C.MSG_ENCOURAGEMENT)

    def test_achievement_message_uses_achievement_name(self):
        # Force English so the assertion uses the EN name verbatim.
        self.user.profile.preferred_language = "en"
        self.user.profile.save(update_fields=["preferred_language"])
        ach = Achievement.objects.create(
            code="x", name="Top Learner", description="Did the thing.",
            name_ar="متعلم متفوق", description_ar="فعلت الأمر.",
            category=C.CAT_LESSON, threshold_value=1, xp_reward=10,
        )
        msg = message_generator.build_message(
            self.user, message_type=C.MSG_ACHIEVEMENT, achievement=ach
        )
        self.assertEqual(msg.title, "Top Learner")

    def test_tone_shifts_for_inactive(self):
        snap = LearnerActivitySnapshot.objects.create(
            user=self.user,
            date=timezone.localdate(),
            inactive_days=5,
        )
        tone = message_generator.select_tone(self.user, snap)
        self.assertEqual(tone, C.TONE_GENTLE)

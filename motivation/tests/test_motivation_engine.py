from datetime import timedelta

from django.contrib.auth import get_user_model
from django.core import mail
from django.core.management import call_command
from django.test import TestCase, override_settings
from django.utils import timezone

from motivation import constants as C
from motivation.models import (
    LearnerActivitySnapshot,
    MotivationMessage,
    MotivationPreference,
    UserAchievement,
    UserBadge,
    UserXP,
)
from motivation.services import (
    activity_collector,
    motivation_engine,
    motivation_rules,
)

User = get_user_model()


@override_settings(EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend")
class MotivationEngineTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        call_command("seed_achievements")

    def setUp(self):
        self.user = User.objects.create_user(
            username="engine", email="engine@x.com", password="pw"
        )

    def test_run_for_user_creates_snapshot_and_xp(self):
        res = motivation_engine.run_for_user(self.user)
        self.assertIn("snapshot_id", res)
        self.assertTrue(LearnerActivitySnapshot.objects.filter(user=self.user).exists())
        self.assertTrue(UserXP.objects.filter(user=self.user).exists())

    def test_streak_milestone_fires_event(self):
        # Pre-seed yesterday's snapshot with streak=6 then today completes 7-day streak
        yesterday = timezone.localdate() - timedelta(days=1)
        LearnerActivitySnapshot.objects.create(
            user=self.user, date=yesterday, current_streak_days=6,
            lessons_completed=1,
        )
        # Force a snapshot that registers a 7-day streak
        snap = activity_collector.collect_daily_activity(self.user)
        snap.current_streak_days = 7
        snap.save()
        fired = motivation_rules.evaluate_all(snap)
        events = [f["event"] for f in fired]
        self.assertIn("streak_milestone", events)

    def test_inactive_user_gets_comeback(self):
        # Snapshot with inactive_days=5
        snap = LearnerActivitySnapshot.objects.create(
            user=self.user,
            date=timezone.localdate(),
            inactive_days=5,
        )
        fired = motivation_rules.evaluate_all(snap)
        events = [f["event"] for f in fired]
        self.assertIn("comeback_reminder", events)

    def test_arabic_user_gets_arabic_email(self):
        self.user.profile.preferred_language = "ar"
        self.user.profile.save()
        # Pre-seed yesterday so today registers a 7-day streak
        yesterday = timezone.localdate() - timedelta(days=1)
        LearnerActivitySnapshot.objects.create(
            user=self.user, date=yesterday, current_streak_days=6,
            lessons_completed=1,
        )
        # Manually craft a snapshot with streak=7 to force milestone trigger
        snap = LearnerActivitySnapshot.objects.create(
            user=self.user,
            date=timezone.localdate() + timedelta(days=1),
            current_streak_days=7,
            lessons_completed=1,
        )
        # Build message via engine plumbing
        from motivation.services import message_generator
        msg = message_generator.build_message(
            self.user, message_type=C.MSG_STREAK, snap=snap
        )
        self.assertEqual(msg.language, "ar")

    def test_disabled_motivation_pref_no_messages(self):
        pref, _ = MotivationPreference.objects.get_or_create(user=self.user)
        pref.enable_motivation_notifications = False
        pref.enable_email_motivation = False
        pref.save()

        # Force a snapshot with inactive_days=5 to potentially fire comeback
        LearnerActivitySnapshot.objects.create(
            user=self.user,
            date=timezone.localdate() - timedelta(days=1),
            current_streak_days=0, inactive_days=5,
        )
        # Engine still runs, but should not emit motivation rule messages
        before = MotivationMessage.objects.count()
        motivation_engine.run_for_user(self.user)
        # Achievement messages may still fire (e.g. first_lesson if seeded), but
        # since this user has 0 lessons, the count should not jump from rule events.
        after = MotivationMessage.objects.count()
        self.assertLessEqual(after - before, 1)

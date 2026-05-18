"""Sprint 5 tests: gamification audio + recent-rewards feed."""
from __future__ import annotations

from datetime import timedelta

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from motivation.models import (
    Achievement,
    GameEventSound,
    UserAchievement,
    UserBadge,
    UserXP,
)
from motivation.services import sound_service


User = get_user_model()


class GameEventSoundSeedTests(TestCase):
    def test_five_event_sounds_seeded(self):
        codes = set(GameEventSound.objects.values_list("code", flat=True))
        self.assertSetEqual(
            codes,
            {"success", "level_up", "bonus", "streak", "achievement_unlocked"},
        )

    def test_seeded_sounds_have_messages_in_both_langs(self):
        for sound in GameEventSound.objects.all():
            self.assertTrue(sound.message_en)
            self.assertTrue(sound.message_ar)


class EventSoundsForUserTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="snd@example.com", email="snd@example.com", password="pw")

    def test_returns_all_active_sounds_keyed_by_code(self):
        sounds = sound_service.event_sounds_for_user(self.user)
        self.assertIn("success", sounds)
        self.assertIn("level_up", sounds)
        self.assertEqual(sounds["success"]["animation"], "sparkle")

    def test_muted_user_loses_audio_src(self):
        # Give "success" a URL so we have something to strip.
        GameEventSound.objects.filter(code="success").update(audio_url="https://x/y.mp3")
        # Set the user's sound preference off.
        from subscriptions.services import preference_service
        preference_service.set_preference(self.user, sound_effects_enabled=False)
        sounds = sound_service.event_sounds_for_user(self.user)
        self.assertEqual(sounds["success"]["audio_src"], "")
        # Message + animation still present so we can show a silent toast.
        self.assertTrue(sounds["success"]["message_en"])

    def test_unmuted_user_gets_audio_src(self):
        GameEventSound.objects.filter(code="success").update(audio_url="https://x/y.mp3")
        sounds = sound_service.event_sounds_for_user(self.user)
        self.assertEqual(sounds["success"]["audio_src"], "https://x/y.mp3")

    def test_inactive_sound_omitted(self):
        GameEventSound.objects.filter(code="streak").update(is_active=False)
        sounds = sound_service.event_sounds_for_user(self.user)
        self.assertNotIn("streak", sounds)


class RecentRewardsTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="rr@example.com", email="rr@example.com", password="pw")

    def test_empty_when_nothing_recent(self):
        rewards = sound_service.recent_rewards_for(self.user)
        self.assertEqual(rewards, [])

    def test_recent_achievement_appears(self):
        ach = Achievement.objects.create(code="first_lesson", name="First Lesson", xp_reward=50)
        UserAchievement.objects.create(user=self.user, achievement=ach)
        rewards = sound_service.recent_rewards_for(self.user, window_seconds=60)
        self.assertEqual(len(rewards), 1)
        self.assertEqual(rewards[0]["event_code"], "achievement_unlocked")
        self.assertIn("First Lesson", rewards[0]["message_en"])

    def test_old_achievement_excluded(self):
        ach = Achievement.objects.create(code="old", name="Old", xp_reward=10)
        ua = UserAchievement.objects.create(user=self.user, achievement=ach)
        UserAchievement.objects.filter(pk=ua.pk).update(earned_at=timezone.now() - timedelta(minutes=5))
        rewards = sound_service.recent_rewards_for(self.user, window_seconds=60)
        self.assertEqual(rewards, [])

    def test_badge_appears(self):
        UserBadge.objects.create(user=self.user, badge_code="b1", badge_name="Star Learner")
        rewards = sound_service.recent_rewards_for(self.user)
        self.assertTrue(any(r["event_code"] == "bonus" for r in rewards))

    def test_level_up_inferred_from_userxp(self):
        UserXP.objects.create(user=self.user, total_xp=500, level_number=3)
        rewards = sound_service.recent_rewards_for(self.user)
        lvl = [r for r in rewards if r["event_code"] == "level_up"]
        self.assertEqual(len(lvl), 1)
        self.assertIn("level", lvl[0]["payload"])
        self.assertEqual(lvl[0]["payload"]["level"], 3)

    def test_no_level_up_at_level_one(self):
        UserXP.objects.create(user=self.user, total_xp=0, level_number=1)
        rewards = sound_service.recent_rewards_for(self.user)
        self.assertFalse(any(r["event_code"] == "level_up" for r in rewards))

    def test_muted_user_keeps_toast_but_no_audio(self):
        from subscriptions.services import preference_service
        preference_service.set_preference(self.user, sound_effects_enabled=False)
        GameEventSound.objects.filter(code="achievement_unlocked").update(audio_url="https://x/y.mp3")
        ach = Achievement.objects.create(code="muted_test", name="X", xp_reward=10)
        UserAchievement.objects.create(user=self.user, achievement=ach)
        rewards = sound_service.recent_rewards_for(self.user)
        self.assertEqual(len(rewards), 1)
        self.assertEqual(rewards[0]["audio_src"], "")

    def test_unauthenticated_user_returns_empty(self):
        from django.contrib.auth.models import AnonymousUser
        rewards = sound_service.recent_rewards_for(AnonymousUser())
        self.assertEqual(rewards, [])


class RecentRewardsApiTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="api@example.com", email="api@example.com", password="pw")
        self.client.force_login(self.user)

    def test_endpoint_returns_rewards_list(self):
        response = self.client.get(reverse("motivation_api:recent_rewards"))
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertIn("rewards", data)
        self.assertEqual(data["rewards"], [])

    def test_endpoint_returns_recent_achievement(self):
        ach = Achievement.objects.create(code="ep", name="Endpoint", xp_reward=20)
        UserAchievement.objects.create(user=self.user, achievement=ach)
        response = self.client.get(reverse("motivation_api:recent_rewards"))
        data = response.json()
        self.assertEqual(len(data["rewards"]), 1)

    def test_event_sounds_endpoint(self):
        response = self.client.get(reverse("motivation_api:event_sounds"))
        self.assertEqual(response.status_code, 200)
        sounds = response.json()["sounds"]
        self.assertIn("success", sounds)
        self.assertIn("achievement_unlocked", sounds)

    def test_window_param_clamped(self):
        # Out-of-range window must not crash — clamp to [1, 600].
        response = self.client.get(reverse("motivation_api:recent_rewards") + "?window=999999")
        self.assertEqual(response.status_code, 200)

    def test_anonymous_blocked(self):
        self.client.logout()
        response = self.client.get(reverse("motivation_api:recent_rewards"))
        self.assertIn(response.status_code, (401, 403))


class GamificationSoundsAdminTests(TestCase):
    def setUp(self):
        from django.core.management import call_command
        call_command("seed_platform_roles", verbosity=0)
        self.admin = User.objects.create_user(
            username="admin@example.com", email="admin@example.com",
            password="pw", is_staff=True, is_superuser=True,
        )

    def test_admin_can_view_sounds_page(self):
        self.client.force_login(self.admin)
        response = self.client.get(reverse("platform_admin:gamification_sounds"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "success")
        self.assertContains(response, "achievement_unlocked")

    def test_admin_can_update_sound_url(self):
        self.client.force_login(self.admin)
        sound = GameEventSound.objects.get(code="success")
        response = self.client.post(
            reverse("platform_admin:gamification_sounds"),
            {
                "sound_id": sound.pk,
                "code": sound.code,
                "audio_url": "https://cdn.example.com/win.mp3",
                "fallback_audio_path": sound.fallback_audio_path,
                "message_en": sound.message_en,
                "message_ar": sound.message_ar,
                "animation": sound.animation,
                "xp_callout_template_en": sound.xp_callout_template_en,
                "xp_callout_template_ar": sound.xp_callout_template_ar,
                "is_active": "on",
            },
        )
        self.assertEqual(response.status_code, 302)
        sound.refresh_from_db()
        self.assertEqual(sound.audio_url, "https://cdn.example.com/win.mp3")

    def test_non_admin_cannot_view(self):
        plain = User.objects.create_user(username="p@example.com", email="p@example.com", password="pw")
        self.client.force_login(plain)
        response = self.client.get(reverse("platform_admin:gamification_sounds"))
        self.assertIn(response.status_code, (302, 403))

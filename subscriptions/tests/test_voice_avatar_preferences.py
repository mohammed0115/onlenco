"""Sprint 3 tests: voice + avatar catalogue, user preferences, session pickup."""
from __future__ import annotations

import json

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.core.management import call_command
from django.test import TestCase, override_settings
from django.urls import reverse

from platform_admin import permissions as control_perms
from subscriptions.models import (
    AITutorSession, AvatarProfile, UserAIPreference, VoiceProfile,
)
from subscriptions.services import preference_service, session_service


User = get_user_model()


class VoiceCatalogSeedTests(TestCase):
    def test_six_voices_seeded(self):
        self.assertEqual(VoiceProfile.objects.filter(is_active=True).count(), 6)

    def test_each_voice_has_provider_id(self):
        provider_ids = set(VoiceProfile.objects.values_list("provider_voice_id", flat=True))
        # Post-GA remap (migration 0009): retired voices (nova/onyx/fable)
        # were swapped to GA equivalents (shimmer/ash/ballad). Every
        # seeded ID must now be accepted by /v1/realtime/client_secrets.
        from tutor.services.realtime_session import REALTIME_GA_VOICES
        non_ga = provider_ids - REALTIME_GA_VOICES
        self.assertFalse(non_ga, f"Non-GA voices in DB: {non_ga}")

    def test_five_avatars_seeded(self):
        # Migration 0006 seeded 4 avatars; 0010 added "Hassabu" as a 5th
        # active avatar. Update this count whenever a new avatar seed
        # migration ships.
        self.assertEqual(AvatarProfile.objects.filter(is_active=True).count(), 5)


class ResolveDefaultsTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="r@example.com", email="r@example.com", password="pw")

    def test_no_preference_returns_first_active_voice(self):
        voice = preference_service.resolve_voice_for(self.user)
        self.assertIsNotNone(voice)
        # Lowest sort_order wins (alloy_friendly with sort_order=10)
        self.assertEqual(voice.code, "alloy_friendly")

    def test_no_preference_returns_first_active_avatar(self):
        avatar = preference_service.resolve_avatar_for(self.user)
        self.assertIsNotNone(avatar)
        self.assertEqual(avatar.code, "layla_female_teacher")

    def test_inactive_voice_falls_back_to_default(self):
        chosen = VoiceProfile.objects.get(code="nova_calm")
        preference_service.set_preference(self.user, voice_code="nova_calm")
        # Now deactivate it
        chosen.is_active = False
        chosen.save(update_fields=["is_active"])
        # The fallback kicks in.
        voice = preference_service.resolve_voice_for(self.user)
        self.assertNotEqual(voice.code, "nova_calm")
        self.assertTrue(voice.is_active)


class SetPreferenceTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="sp@example.com", email="sp@example.com", password="pw")

    def test_set_voice_creates_row(self):
        pref = preference_service.set_preference(self.user, voice_code="nova_calm")
        self.assertEqual(pref.voice_profile.code, "nova_calm")
        self.assertEqual(UserAIPreference.objects.filter(user=self.user).count(), 1)

    def test_invalid_voice_code_silently_ignored(self):
        # Pre-set a valid voice
        preference_service.set_preference(self.user, voice_code="onyx_professional")
        # Then send a typo — must NOT overwrite the valid one.
        preference_service.set_preference(self.user, voice_code="notarealcode")
        pref = UserAIPreference.objects.get(user=self.user)
        self.assertEqual(pref.voice_profile.code, "onyx_professional")

    def test_set_speed_and_pitch(self):
        pref = preference_service.set_preference(
            self.user, speed="fast", pitch="low",
        )
        self.assertEqual(pref.speed, "fast")
        self.assertEqual(pref.pitch, "low")

    def test_invalid_speed_silently_ignored(self):
        preference_service.set_preference(self.user, speed="ultrafast")
        pref = preference_service.get_or_create_preference(self.user)
        self.assertEqual(pref.speed, "normal")

    def test_avatar_can_be_set(self):
        pref = preference_service.set_preference(self.user, avatar_code="omar_male_teacher")
        self.assertEqual(pref.avatar_profile.code, "omar_male_teacher")


class SessionPickupTests(TestCase):
    """The tutor session must persist the resolved voice + avatar."""

    def setUp(self):
        self.user = User.objects.create_user(username="sk@example.com", email="sk@example.com", password="pw")

    def test_session_records_default_voice(self):
        voice = preference_service.resolve_voice_for(self.user)
        avatar = preference_service.resolve_avatar_for(self.user)
        session = session_service.start_session(
            self.user,
            voice=voice.provider_voice_id,
            voice_profile=voice,
            avatar_profile=avatar,
        )
        self.assertEqual(session.voice, "alloy")
        self.assertEqual(session.voice_profile_id, voice.pk)
        self.assertEqual(session.avatar_profile_id, avatar.pk)

    def test_session_records_user_preferred_voice(self):
        preference_service.set_preference(
            self.user, voice_code="shimmer_energetic", avatar_code="sara_energetic",
        )
        v = preference_service.resolve_voice_for(self.user)
        a = preference_service.resolve_avatar_for(self.user)
        session = session_service.start_session(
            self.user, voice=v.provider_voice_id, voice_profile=v, avatar_profile=a,
        )
        self.assertEqual(session.voice, "shimmer")
        self.assertEqual(session.voice_profile.code, "shimmer_energetic")
        self.assertEqual(session.avatar_profile.code, "sara_energetic")


class PreferencePageTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="pp@example.com", email="pp@example.com", password="pw")
        self.client.force_login(self.user)

    def test_preferences_page_renders_with_choices(self):
        response = self.client.get(reverse("subscriptions:preferences"))
        self.assertEqual(response.status_code, 200)
        # Every active voice + avatar code appears in the rendered radio list.
        self.assertContains(response, "nova_calm")
        self.assertContains(response, "onyx_professional")
        self.assertContains(response, "omar_male_teacher")

    def test_post_saves_preference(self):
        # Use a gender-compatible pair (male avatar + male voice); a male
        # avatar + female voice is now rejected by the compatibility rule.
        response = self.client.post(
            reverse("subscriptions:preferences"),
            {
                "voice_code": "onyx_professional",
                "avatar_code": "omar_male_teacher",
                "speed": "fast",
                "pitch": "low",
            },
        )
        self.assertEqual(response.status_code, 302)
        pref = UserAIPreference.objects.get(user=self.user)
        self.assertEqual(pref.voice_profile.code, "onyx_professional")
        self.assertEqual(pref.avatar_profile.code, "omar_male_teacher")
        self.assertEqual(pref.speed, "fast")
        self.assertEqual(pref.pitch, "low")

    def test_api_get_returns_snapshot(self):
        response = self.client.get(reverse("subscriptions:preference_api"))
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertIn("voice", data)
        self.assertIn("avatar", data)
        self.assertIn("speed", data)
        self.assertEqual(data["voice"]["provider_voice_id"], "alloy")

    def test_api_post_updates_preference(self):
        response = self.client.post(
            reverse("subscriptions:preference_api"),
            data=json.dumps({"voice_code": "fable_soft", "speed": "slow"}),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["voice"]["code"], "fable_soft")
        self.assertEqual(data["speed"], "slow")


class GenderCompatibilityTests(TestCase):
    """Voice↔avatar gender compatibility (single source of truth + UI + auto-fix).

    Seeded genders: voices alloy_friendly=neutral, nova_calm=female,
    onyx_professional=male; avatars omar_male_teacher=male,
    layla_female_teacher=female, anonymous=neutral.
    """

    def setUp(self):
        self.user = User.objects.create_user(
            username="gc@example.com", email="gc@example.com", password="pw")

    def _set(self, **kw):
        return preference_service.set_preference(self.user, **kw)

    # 1
    def test_male_avatar_female_voice_rejected(self):
        with self.assertRaises(preference_service.IncompatibleVoiceError):
            self._set(avatar_code="omar_male_teacher", voice_code="nova_calm")

    # 2
    def test_female_avatar_male_voice_rejected(self):
        with self.assertRaises(preference_service.IncompatibleVoiceError):
            self._set(avatar_code="layla_female_teacher", voice_code="onyx_professional")

    # 3
    def test_male_avatar_male_voice_accepted(self):
        pref = self._set(avatar_code="omar_male_teacher", voice_code="onyx_professional")
        self.assertEqual(pref.voice_profile.code, "onyx_professional")

    # 4
    def test_female_avatar_female_voice_accepted(self):
        pref = self._set(avatar_code="layla_female_teacher", voice_code="nova_calm")
        self.assertEqual(pref.voice_profile.code, "nova_calm")

    # 5
    def test_male_avatar_neutral_voice_accepted(self):
        pref = self._set(avatar_code="omar_male_teacher", voice_code="alloy_friendly")
        self.assertEqual(pref.voice_profile.code, "alloy_friendly")

    # 6
    def test_female_avatar_neutral_voice_accepted(self):
        pref = self._set(avatar_code="layla_female_teacher", voice_code="alloy_friendly")
        self.assertEqual(pref.voice_profile.code, "alloy_friendly")

    # 7
    @override_settings(PREFERENCES_NEUTRAL_AVATAR_ALLOWS_ALL_VOICES=True)
    def test_neutral_avatar_allows_all_voices(self):
        self.assertEqual(
            self._set(avatar_code="anonymous", voice_code="nova_calm").voice_profile.code,
            "nova_calm")
        self.assertEqual(
            self._set(avatar_code="anonymous", voice_code="onyx_professional").voice_profile.code,
            "onyx_professional")

    @override_settings(PREFERENCES_NEUTRAL_AVATAR_ALLOWS_ALL_VOICES=False)
    def test_neutral_avatar_restricts_when_setting_off(self):
        with self.assertRaises(preference_service.IncompatibleVoiceError):
            self._set(avatar_code="anonymous", voice_code="nova_calm")
        # Neutral voice is still fine for a neutral avatar.
        self.assertEqual(
            self._set(avatar_code="anonymous", voice_code="alloy_friendly").voice_profile.code,
            "alloy_friendly")

    # 8
    def test_existing_male_avatar_female_voice_autocorrected(self):
        omar = AvatarProfile.objects.get(code="omar_male_teacher")
        nova = VoiceProfile.objects.get(code="nova_calm")
        UserAIPreference.objects.create(user=self.user, avatar_profile=omar, voice_profile=nova)
        snap = preference_service.preference_snapshot(self.user)
        pref = UserAIPreference.objects.get(user=self.user)
        self.assertNotEqual(pref.voice_profile.code, "nova_calm")
        self.assertEqual(pref.avatar_profile.code, "omar_male_teacher")  # avatar untouched
        self.assertTrue(preference_service.is_voice_compatible_with_avatar(
            pref.voice_profile, pref.avatar_profile))
        self.assertEqual(snap["voice"]["code"], pref.voice_profile.code)

    # 9
    def test_existing_female_avatar_male_voice_autocorrected(self):
        layla = AvatarProfile.objects.get(code="layla_female_teacher")
        onyx = VoiceProfile.objects.get(code="onyx_professional")
        UserAIPreference.objects.create(user=self.user, avatar_profile=layla, voice_profile=onyx)
        preference_service.preference_snapshot(self.user)
        pref = UserAIPreference.objects.get(user=self.user)
        self.assertNotEqual(pref.voice_profile.code, "onyx_professional")
        self.assertEqual(pref.avatar_profile.code, "layla_female_teacher")
        self.assertTrue(preference_service.is_voice_compatible_with_avatar(
            pref.voice_profile, pref.avatar_profile))

    def test_avatar_only_change_autoswitches_voice(self):
        # Valid female avatar + female voice, then change ONLY the avatar to
        # male (no voice_code) → the voice auto-switches to a compatible one.
        self._set(avatar_code="layla_female_teacher", voice_code="nova_calm")
        pref = self._set(avatar_code="omar_male_teacher")
        self.assertNotEqual(pref.voice_profile.code, "nova_calm")
        self.assertTrue(preference_service.is_voice_compatible_with_avatar(
            pref.voice_profile, pref.avatar_profile))

    # 10 (UI)
    def test_template_exposes_gender_data_attributes(self):
        self.client.force_login(self.user)
        body = self.client.get(reverse("subscriptions:preferences")).content.decode()
        self.assertIn("data-voice-gender", body)
        self.assertIn("data-avatar-gender", body)

    # 11 (valid save via form + API)
    def test_valid_pair_saves_via_form_and_api(self):
        self.client.force_login(self.user)
        r = self.client.post(reverse("subscriptions:preferences"), {
            "avatar_code": "omar_male_teacher", "voice_code": "onyx_professional",
            "speed": "normal", "pitch": "normal"})
        self.assertEqual(r.status_code, 302)
        self.assertEqual(
            UserAIPreference.objects.get(user=self.user).voice_profile.code, "onyx_professional")
        r2 = self.client.post(
            reverse("subscriptions:preference_api"),
            data=json.dumps({"avatar_code": "layla_female_teacher", "voice_code": "nova_calm"}),
            content_type="application/json")
        self.assertEqual(r2.status_code, 200)
        self.assertEqual(r2.json()["voice"]["code"], "nova_calm")

    def test_api_rejects_incompatible_pair(self):
        self.client.force_login(self.user)
        r = self.client.post(
            reverse("subscriptions:preference_api"),
            data=json.dumps({"avatar_code": "omar_male_teacher", "voice_code": "nova_calm"}),
            content_type="application/json")
        self.assertEqual(r.status_code, 400)
        self.assertEqual(r.json()["error"], "voice_incompatible_with_avatar")

    def test_form_rejects_incompatible_pair(self):
        self.client.force_login(self.user)
        r = self.client.post(reverse("subscriptions:preferences"), {
            "avatar_code": "omar_male_teacher", "voice_code": "nova_calm"})
        self.assertEqual(r.status_code, 302)  # redirect with an error message
        pref = UserAIPreference.objects.filter(user=self.user).first()
        self.assertFalse(pref and pref.voice_profile and pref.voice_profile.code == "nova_calm")


class ControlCenterVoicesPageTests(TestCase):
    def setUp(self):
        call_command("seed_platform_roles", verbosity=0)
        self.admin = User.objects.create_user(
            username="ctl@example.com", email="ctl@example.com",
            password="pw", is_staff=True, is_superuser=True,
        )

    def test_admin_can_view_voices_catalog(self):
        self.client.force_login(self.admin)
        response = self.client.get(reverse("platform_admin:voices"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "alloy_friendly")
        self.assertContains(response, "layla_female_teacher")

    def test_toggle_voice_active(self):
        self.client.force_login(self.admin)
        voice = VoiceProfile.objects.get(code="nova_calm")
        self.assertTrue(voice.is_active)
        response = self.client.post(reverse("platform_admin:voice_toggle", args=[voice.pk]))
        self.assertEqual(response.status_code, 302)
        voice.refresh_from_db()
        self.assertFalse(voice.is_active)

    def test_non_admin_cannot_view(self):
        plain = User.objects.create_user(username="plain@example.com", email="plain@example.com", password="pw")
        self.client.force_login(plain)
        response = self.client.get(reverse("platform_admin:voices"))
        self.assertIn(response.status_code, (302, 403))

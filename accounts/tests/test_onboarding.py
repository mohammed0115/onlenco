"""Tests for the onboarding choice flow.

Each test isolates one rule the redirect-helper or the views must
guarantee. The shared `setUp` mints a fresh user with a verified email
so the redirect rule does not get distracted by the email-OTP gate."""
from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from django.urls import reverse

from accounts import onboarding as onboarding_lib
from lessons.models import Lesson

User = get_user_model()


@override_settings(AXES_ENABLED=False)
class OnboardingChoiceTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username="ob@x.com", email="ob@x.com", password="pw",
        )
        self.user.profile.email_verified = True
        self.user.profile.save(update_fields=["email_verified"])

    # 1. New user sees onboarding choice ----------------------------------

    def test_new_user_redirected_to_onboarding_after_login(self):
        self.client.force_login(self.user)
        # Hitting the dashboard logic: the auth_view honours the
        # next_url_for helper, but the dashboard itself is reachable —
        # the redirect rule kicks in via auth_view + middleware. Here
        # we test the helper directly to keep the contract tight.
        self.assertEqual(
            onboarding_lib.next_url_for(self.user),
            reverse("onboarding_choice"),
        )

    def test_onboarding_choice_page_renders_for_new_user(self):
        # Flip profile to English so t_either emits the English copy.
        self.user.profile.preferred_language = "en"
        self.user.profile.save(update_fields=["preferred_language"])
        self.client.force_login(self.user)
        resp = self.client.get(reverse("onboarding_choice"))
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, "Take Placement Test")
        self.assertContains(resp, "Start From Beginner")

    # 2. Placement choice redirects to placement --------------------------

    def test_placement_choice_redirects_to_placement(self):
        # The "Take Placement Test" card now drops the student into the
        # dynamic-bank flow which creates a PlacementAttempt and walks
        # them through written → speaking → result.
        self.client.force_login(self.user)
        resp = self.client.post(reverse("onboarding_placement"))
        self.assertEqual(resp.status_code, 302)
        self.assertEqual(resp.url, reverse("placement_start"))

    # 3. Beginner choice creates profile + redirects to dashboard --------

    def test_beginner_choice_creates_profile_and_redirects(self):
        self.client.force_login(self.user)
        resp = self.client.post(reverse("onboarding_beginner"))
        self.assertRedirects(resp, reverse("dashboard"),
                             fetch_redirect_response=False)
        self.user.profile.refresh_from_db()
        self.assertTrue(self.user.profile.onboarding_completed)
        self.assertEqual(self.user.profile.onboarding_path, "beginner_start")
        self.assertEqual(self.user.profile.cefr_level, "A0")
        self.assertEqual(self.user.profile.initial_cefr_level, "A0")
        self.assertIsNotNone(self.user.profile.onboarding_completed_at)

    def test_beginner_creates_student_learning_profile(self):
        self.client.force_login(self.user)
        self.client.post(reverse("onboarding_beginner"))
        from learning_core.models import StudentLearningProfile
        self.assertTrue(
            StudentLearningProfile.objects.filter(user=self.user).exists()
        )

    def test_beginner_first_lesson_lookup_returns_lowest_level(self):
        Lesson.objects.create(
            title="A1 starter", skill="grammar", level="A1", sort_order=10,
        )
        first_a0 = Lesson.objects.create(
            title="A0 starter", skill="grammar", level="A0", sort_order=1,
        )
        # Helper picks the lowest-level / lowest-sort-order lesson.
        self.assertEqual(onboarding_lib.first_beginner_lesson(), first_a0)

    # 4. Completed onboarding does not show again ------------------------

    def test_completed_user_redirects_away_from_onboarding(self):
        onboarding_lib.complete_beginner_onboarding(self.user)
        self.client.force_login(self.user)
        resp = self.client.get(reverse("onboarding_choice"))
        self.assertEqual(resp.status_code, 302)
        self.assertEqual(resp.url, reverse("dashboard"))

    def test_completed_user_next_url_is_none(self):
        onboarding_lib.complete_beginner_onboarding(self.user)
        self.assertIsNone(onboarding_lib.next_url_for(self.user))

    # 5. Admin reset allows onboarding again ----------------------------

    def test_admin_reset_allows_onboarding_again(self):
        onboarding_lib.complete_beginner_onboarding(self.user)
        # Admin flips the flag back (simulating the bulk action).
        self.user.profile.onboarding_completed = False
        self.user.profile.onboarding_path = ""
        self.user.profile.preferred_language = "en"
        self.user.profile.save(update_fields=[
            "onboarding_completed", "onboarding_path", "preferred_language",
        ])
        self.client.force_login(self.user)
        resp = self.client.get(reverse("onboarding_choice"))
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, "How would you like to start?")

    # 6. Localisation (English + Arabic strings present) ----------------

    def test_english_text_present_when_language_is_english(self):
        self.user.profile.preferred_language = "en"
        self.user.profile.save(update_fields=["preferred_language"])
        self.client.force_login(self.user)
        resp = self.client.get(reverse("onboarding_choice"))
        self.assertContains(resp, "How would you like to start?")
        self.assertContains(resp, "Start Placement Test")
        self.assertContains(resp, "Start From Beginner")
        # Arabic should NOT leak into the EN render.
        self.assertNotContains(resp, "كيف تريد أن تبدأ؟")

    def test_arabic_text_present_when_language_is_arabic(self):
        self.user.profile.preferred_language = "ar"
        self.user.profile.save(update_fields=["preferred_language"])
        self.client.force_login(self.user)
        resp = self.client.get(reverse("onboarding_choice"))
        self.assertContains(resp, "كيف تريد أن تبدأ؟")
        self.assertContains(resp, "ابدأ من البداية")
        self.assertNotContains(resp, "How would you like to start?")

    # 7. Placement completion marks onboarding complete -----------------

    def test_complete_placement_helper_marks_onboarding(self):
        onboarding_lib.complete_placement_onboarding(self.user.profile, level="B1")
        self.user.profile.refresh_from_db()
        self.assertTrue(self.user.profile.onboarding_completed)
        self.assertEqual(self.user.profile.onboarding_path, "placement_test")
        self.assertEqual(self.user.profile.initial_cefr_level, "B1")
        self.assertIsNotNone(self.user.profile.onboarding_completed_at)

    def test_complete_placement_helper_is_idempotent(self):
        onboarding_lib.complete_placement_onboarding(self.user.profile, level="B1")
        first_ts = self.user.profile.onboarding_completed_at
        onboarding_lib.complete_placement_onboarding(self.user.profile, level="C1")
        self.user.profile.refresh_from_db()
        # initial_cefr_level locked at first completion (the rerun is a retake).
        self.assertEqual(self.user.profile.initial_cefr_level, "B1")
        self.assertEqual(self.user.profile.onboarding_completed_at, first_ts)

    # 8. Unverified-email user is sent to OTP, not onboarding ----------

    def test_unverified_user_goes_to_otp_first(self):
        self.user.profile.email_verified = False
        self.user.profile.save(update_fields=["email_verified"])
        self.assertEqual(
            onboarding_lib.next_url_for(self.user),
            reverse("verify_email_otp"),
        )

    # 9. Anonymous user → no redirect from helper -----------------------

    def test_anonymous_user_helper_returns_none(self):
        from django.contrib.auth.models import AnonymousUser
        self.assertIsNone(onboarding_lib.next_url_for(AnonymousUser()))

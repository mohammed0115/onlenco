"""Coverage for the AI Tutor learning sidebar payload.

The sidebar reads from several adaptive subsystems (StudentLearningProfile,
UserWeakness, UserError, LearningRecommendation, motivation.UserXP). We
need:

1. A fully-populated user → all sections render.
2. A brand-new user (no learning data yet) → page still renders with safe
   defaults (level falls back to B1, lists empty, motivation values None).
3. The sidebar payload is wired into the tutor detail view and renders
   into the page body.
4. The system prompt picks up the student's CEFR level + weaknesses (the
   level adaptation rule the spec requires).
"""
from __future__ import annotations

from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from tutor.models import TutorConversation
from tutor.services.sidebar_context import build_sidebar_payload
from tutor.services._chat import _system_prompt
from tutor.services.context_builder import build_tutor_context

User = get_user_model()


def _activate_subscription(user):
    prof = user.profile
    prof.subscription_status = "active"
    prof.subscription_expires_at = timezone.now() + timezone.timedelta(days=30)
    prof.save()


@override_settings(AXES_ENABLED=False)
class SidebarPayloadTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="sb@x.com", password="pw")
        _activate_subscription(self.user)

    def test_blank_user_returns_safe_defaults(self):
        # No StudentLearningProfile, no weaknesses, no errors → the
        # sidebar must still produce a renderable payload.
        payload = build_sidebar_payload(self.user)
        self.assertIn("level", payload)
        self.assertEqual(payload["level"], "B1")  # default fallback
        self.assertEqual(payload["weaknesses"], [])
        self.assertEqual(payload["recent_mistakes"], [])
        self.assertEqual(payload["recommendations"], [])
        self.assertIn("motivation", payload)
        # All motivation fields default to None when no XP/snapshot row exists.
        self.assertIn("xp", payload["motivation"])
        self.assertIn("streak_days", payload["motivation"])

    def test_with_profile_level(self):
        from learning_core.models import StudentLearningProfile
        StudentLearningProfile.objects.create(user=self.user, current_cefr_level="A2")
        payload = build_sidebar_payload(self.user)
        self.assertEqual(payload["level"], "A2")

    def test_with_recent_mistake(self):
        from learning_core.models import UserError
        UserError.objects.create(
            user=self.user,
            original_text="He go to school",
            corrected_text="He goes to school",
            explanation="Subject-verb agreement",
            error_type="grammar",
        )
        payload = build_sidebar_payload(self.user)
        self.assertEqual(len(payload["recent_mistakes"]), 1)
        self.assertEqual(payload["recent_mistakes"][0]["fragment"], "He go to school")
        self.assertEqual(payload["recent_mistakes"][0]["type"], "grammar")

    def test_with_xp_and_streak(self):
        from motivation.models import UserXP, LearnerActivitySnapshot
        UserXP.objects.create(user=self.user, total_xp=1234, level_number=4)
        LearnerActivitySnapshot.objects.create(
            user=self.user, date=timezone.now().date(),
            current_streak_days=7,
        )
        payload = build_sidebar_payload(self.user)
        self.assertEqual(payload["motivation"]["xp"], 1234)
        self.assertEqual(payload["motivation"]["level_number"], 4)
        self.assertEqual(payload["motivation"]["streak_days"], 7)


@override_settings(AXES_ENABLED=False)
class SidebarRendersInDetailViewTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="sb2@x.com", password="pw")
        _activate_subscription(self.user)
        self.client.login(username="sb2@x.com", password="pw")
        self.conv = TutorConversation.objects.create(user=self.user)

    def test_sidebar_section_present_with_level(self):
        r = self.client.get(reverse("tutor_detail", args=[self.conv.pk]))
        body = r.content.decode()
        # Default level chip is rendered into the sidebar card.
        self.assertIn("onlenco-tutor-sidebar", body)
        self.assertIn("onlenco-level-pill", body)
        self.assertIn("B1", body)


@override_settings(AXES_ENABLED=False)
class SystemPromptUsesLevelAndWeaknessesTests(TestCase):
    """The level + weakness data the sidebar surfaces must also reach the
    system prompt — that's how the AI actually adapts. Sidebar without
    prompt-side adaptation would be cosmetic only."""

    def setUp(self):
        self.user = User.objects.create_user(username="sb3@x.com", password="pw")
        _activate_subscription(self.user)
        self.conv = TutorConversation.objects.create(user=self.user)

    def test_a1_band_triggers_simple_english_rule(self):
        from learning_core.models import StudentLearningProfile
        StudentLearningProfile.objects.create(user=self.user, current_cefr_level="A1")
        ctx = build_tutor_context(self.user, "")
        prompt = _system_prompt(ctx, voice=False)
        # A1 has its own branch (separate from A0 since the A0 spec
        # mandates 3-5 word sentences vs A1's 6-8). Lock both signals.
        self.assertIn("student is at A1", prompt)
        self.assertIn("simple English", prompt)
        self.assertIn("A1", prompt)

    def test_a0_band_has_dedicated_beginner_rule(self):
        """A0 must NOT collapse into the A1 prompt — A0 needs 3-5 word
        sentences, no grammar theory, no 'Quick fix:' labels, no
        technical tokens, and gentle echo-style correction."""
        from learning_core.models import StudentLearningProfile
        StudentLearningProfile.objects.create(user=self.user, current_cefr_level="A0")
        ctx = build_tutor_context(self.user, "")
        prompt = _system_prompt(ctx, voice=False)
        self.assertIn("absolute beginner", prompt)
        self.assertIn("No grammar theory", prompt)
        self.assertIn("3 to 5 words", prompt)
        # Gentle correction style — no "Quick fix:" label for A0.
        self.assertIn("GENTLE CORRECTION (A0 style)", prompt)
        self.assertIn("do NOT label it", prompt)
        # The literal phrase "Quick fix:" must be explicitly forbidden
        # for A0 (the rule mentions it only to ban it).
        self.assertIn("No 'Quick fix:'", prompt)
        # Explicit "never speak technical tokens" rule.
        self.assertIn("NEVER speak technical tokens", prompt)
        # And the universal one-question-per-turn rule still applies.
        self.assertIn("one short follow-up question", prompt)
        # Praise-first encouragement is locked.
        self.assertIn("praise first", prompt.lower())

    def test_c1_band_pushes_fluency(self):
        from learning_core.models import StudentLearningProfile
        StudentLearningProfile.objects.create(user=self.user, current_cefr_level="C1")
        ctx = build_tutor_context(self.user, "")
        prompt = _system_prompt(ctx, voice=False)
        self.assertIn("C1/C2", prompt)
        self.assertTrue(
            "fluent" in prompt.lower() or "fluency" in prompt.lower(),
            "C1/C2 prompt should push fluency / professional vocabulary",
        )

    def test_one_question_rule_present(self):
        ctx = build_tutor_context(self.user, "")
        prompt = _system_prompt(ctx, voice=False)
        # Spec rule: ask one question at a time. Lock the wording so the
        # constraint can't quietly weaken in a future edit.
        self.assertIn("one short follow-up question", prompt)
        self.assertIn("ONE", prompt)

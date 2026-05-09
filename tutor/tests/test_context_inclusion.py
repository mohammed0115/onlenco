"""Lock-in test for tutor context inclusion (audit item #25).

Asserts that:
  1. `build_tutor_context` actually pulls CEFR level + weaknesses from
     the canonical sources (`StudentLearningProfile` first, falling back
     to `Profile.cefr_level`).
  2. `render_context_block` produces a string that includes both signals
     so when the tutor system prompt is assembled, the student's level
     and weak topics are present in the LLM call.
  3. Anonymous / under-built profiles fall back to a sane default
     ("B1") rather than crashing.
"""
from django.contrib.auth import get_user_model
from django.test import TestCase

from learning_core.models import (
    GrammarTopic, Skill, StudentLearningProfile, UserWeakness,
)
from tutor.services.context_builder import (
    build_tutor_context, render_context_block,
)

User = get_user_model()


class TutorContextBuildTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username="tutor-ctx@x.com",
            email="tutor-ctx@x.com",
            password="pw",
        )
        self.user.profile.cefr_level = "B2"
        self.user.profile.preferred_language = "ar"
        self.user.profile.save(update_fields=[
            "cefr_level", "preferred_language",
        ])

    def _add_weakness(self, *, skill_name="Grammar", topic_slug=None,
                      topic_name=None, priority=85.0):
        skill = Skill.objects.create(
            name=skill_name, category="grammar", cefr_level="B1",
        )
        topic = None
        if topic_slug:
            topic = GrammarTopic.objects.create(
                name=topic_name or topic_slug.replace("-", " ").title(),
                slug=topic_slug, cefr_level="B1",
            )
        return UserWeakness.objects.create(
            user=self.user, skill=skill, grammar_topic=topic,
            priority_score=priority,
        )

    # --- CEFR sourcing ----------------------------------------------

    def test_context_uses_student_learning_profile_cefr_first(self):
        # SLP says C1, Profile says B2 — SLP must win.
        StudentLearningProfile.objects.create(
            user=self.user, current_cefr_level="C1", theta_score=1.5,
        )
        ctx = build_tutor_context(self.user)
        self.assertEqual(ctx["cefr_level"], "C1")

    def test_context_falls_back_to_profile_cefr_when_no_slp(self):
        # No SLP row → uses profile.cefr_level (B2 from setUp).
        ctx = build_tutor_context(self.user)
        self.assertEqual(ctx["cefr_level"], "B2")

    def test_context_default_when_no_level_anywhere(self):
        self.user.profile.cefr_level = None
        self.user.profile.save(update_fields=["cefr_level"])
        ctx = build_tutor_context(self.user)
        self.assertEqual(ctx["cefr_level"], "B1")  # documented default

    # --- Weakness inclusion -----------------------------------------

    def test_top_weaknesses_carried_into_context(self):
        self._add_weakness(skill_name="Grammar A1",
                           topic_slug="present-perfect",
                           topic_name="Present perfect", priority=92.0)
        self._add_weakness(skill_name="Grammar A2",
                           topic_slug="conditionals",
                           topic_name="Conditionals", priority=80.0)
        ctx = build_tutor_context(self.user)
        labels = {(w.get("skill"), w.get("grammar_topic"))
                  for w in ctx["top_weaknesses"]}
        self.assertIn(("Grammar A1", "Present perfect"), labels)
        self.assertIn(("Grammar A2", "Conditionals"), labels)

    def test_weaknesses_capped_at_three(self):
        for i, slug in enumerate(["a", "b", "c", "d", "e"]):
            self._add_weakness(skill_name=f"Skill-{slug}",
                               topic_slug=f"topic-{slug}",
                               priority=float(90 - i))
        ctx = build_tutor_context(self.user)
        # MAX_WEAKNESSES = 3
        self.assertEqual(len(ctx["top_weaknesses"]), 3)

    # --- Render-block assertions ------------------------------------

    def test_render_includes_cefr_and_weaknesses_for_llm(self):
        StudentLearningProfile.objects.create(
            user=self.user, current_cefr_level="B1", theta_score=0.4,
        )
        self._add_weakness(skill_name="Grammar B1",
                           topic_slug="reported-speech",
                           topic_name="Reported speech", priority=88.0)
        ctx = build_tutor_context(self.user, conversation_topic="travel")
        block = render_context_block(ctx)
        # Both signals must reach the system prompt.
        self.assertIn("Student CEFR level: B1", block)
        self.assertIn("Top weaknesses:", block)
        self.assertIn("Reported speech", block)
        # Topic carried through too.
        self.assertIn("Topic: travel", block)

    def test_render_handles_empty_context_gracefully(self):
        ctx = build_tutor_context(self.user)
        block = render_context_block(ctx)
        # Even with no weaknesses + no topic, the block is non-empty
        # and well-formed.
        self.assertIn("Student CEFR level:", block)
        self.assertNotIn("Top weaknesses:", block)

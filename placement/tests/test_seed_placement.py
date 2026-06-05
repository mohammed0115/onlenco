"""The curated placement seed: 10 questions, corrected keys, idempotent."""
from io import StringIO

from django.core.management import call_command
from django.test import TestCase

from placement.models import PlacementQuestion
from placement.services import answer_key


class SeedPlacementTests(TestCase):
    def setUp(self):
        call_command("seed_placement_questions", stdout=StringIO())

    def _q(self, code):
        return PlacementQuestion.objects.get(code=code)

    def test_creates_5_written_mcq_and_5_speaking(self):
        self.assertEqual(PlacementQuestion.objects.filter(code__startswith="wr.v2.").count(), 5)
        self.assertEqual(PlacementQuestion.objects.filter(code__startswith="sp.v2.").count(), 5)
        for q in PlacementQuestion.objects.filter(code__startswith="wr.v2."):
            self.assertEqual(q.expected_answer_type, "mcq")
            self.assertTrue(q.is_active)

    def test_corrected_answer_keys(self):
        # Q1: "goes" (not "go"); Q3: "come" (not "came").
        self.assertEqual(answer_key.correct_answer_for(options=self._q("wr.v2.001").options, expected_type="mcq"), "goes")
        self.assertEqual(answer_key.correct_answer_for(options=self._q("wr.v2.003").options, expected_type="mcq"), "come")
        self.assertEqual(answer_key.correct_answer_for(options=self._q("wr.v2.002").options, expected_type="mcq"), "am")
        self.assertEqual(answer_key.correct_answer_for(options=self._q("wr.v2.004").options, expected_type="mcq"), "are")
        self.assertEqual(answer_key.correct_answer_for(options=self._q("wr.v2.005").options, expected_type="mcq"), "played")

    def test_speaking_has_expected_answers(self):
        for code in ["sp.v2.001", "sp.v2.002", "sp.v2.003", "sp.v2.004", "sp.v2.005"]:
            q = self._q(code)
            self.assertEqual(q.expected_answer_type, "voice")
            self.assertTrue(q.scoring_rubric.get("expected_answer"))
            self.assertTrue(q.scoring_rubric.get("voice_keywords"))

    def test_idempotent(self):
        call_command("seed_placement_questions", stdout=StringIO())
        self.assertEqual(PlacementQuestion.objects.filter(code__startswith="wr.v2.").count(), 5)
        self.assertEqual(PlacementQuestion.objects.filter(code__startswith="sp.v2.").count(), 5)

    def test_seed_is_non_destructive_and_admin_managed(self):
        # The admin panel is the source of truth: the bootstrap seed must
        # NOT change the active state of pre-existing questions, and must
        # NOT overwrite admin edits to the curated questions.
        old = PlacementQuestion.objects.create(
            code="sp.age.001", question_text="How old are you?", question_type="speaking",
            skill="speaking", topic="age_country", expected_answer_type="voice", is_active=True,
        )
        # Admin edited a curated question's text + deactivated it.
        q = PlacementQuestion.objects.get(code="wr.v2.001")
        q.question_text = "ADMIN EDITED TEXT"
        q.is_active = False
        q.save(update_fields=["question_text", "is_active"])

        call_command("seed_placement_questions", stdout=StringIO())

        old.refresh_from_db()
        q.refresh_from_db()
        self.assertTrue(old.is_active)                      # not deactivated
        self.assertEqual(q.question_text, "ADMIN EDITED TEXT")  # not overwritten
        self.assertFalse(q.is_active)                       # admin choice kept

    def test_mcq_graded_against_key(self):
        opts = self._q("wr.v2.001").options
        self.assertTrue(answer_key.is_answer_correct("goes", options=opts, expected_type="mcq"))
        self.assertFalse(answer_key.is_answer_correct("go", options=opts, expected_type="mcq"))


class CuratedExactSelectionTests(TestCase):
    """With only the curated 5+5 active, the attempt must serve EXACTLY
    those questions, in their code order — not a shuffled / backfilled
    subset (the bug: 'the selected questions don't appear as they are')."""

    def setUp(self):
        from django.contrib.auth import get_user_model
        call_command("seed_placement_questions", stdout=StringIO())
        self.user = get_user_model().objects.create_user("ex@x.com", "ex@x.com", "pw12345!")

    def _codes(self, attempt, section):
        return list(
            attempt.questions.filter(section=section).order_by("order")
            .values_list("question__code", flat=True)
        )

    def test_attempt_serves_exactly_curated_in_order(self):
        from placement.services.placement_question_selector import create_placement_attempt
        attempt = create_placement_attempt(self.user)
        self.assertEqual(
            self._codes(attempt, "written"),
            ["wr.v2.001", "wr.v2.002", "wr.v2.003", "wr.v2.004", "wr.v2.005"],
        )
        self.assertEqual(
            self._codes(attempt, "speaking"),
            ["sp.v2.001", "sp.v2.002", "sp.v2.003", "sp.v2.004", "sp.v2.005"],
        )

    def test_selection_is_stable_across_attempts(self):
        from placement.services.placement_question_selector import create_placement_attempt
        a1 = create_placement_attempt(self.user)
        a2 = create_placement_attempt(self.user)
        self.assertEqual(self._codes(a1, "written"), self._codes(a2, "written"))
        self.assertEqual(self._codes(a1, "speaking"), self._codes(a2, "speaking"))


class WrittenPageRenderTests(TestCase):
    """The written test page must show option TEXT only — never the raw dict
    or the is_correct answer key (which would tell the student the answer)."""

    def setUp(self):
        from django.contrib.auth import get_user_model
        call_command("seed_placement_questions", stdout=StringIO())
        self.user = get_user_model().objects.create_user("wr@x.com", "wr@x.com", "pw12345!")

    def test_options_render_as_text_without_leaking_answer_key(self):
        from placement.services.placement_question_selector import create_placement_attempt
        attempt = create_placement_attempt(self.user)
        self.client.force_login(self.user)
        html = self.client.get(f"/placement/{attempt.id}/written/").content.decode()
        self.assertEqual(self.client.get(f"/placement/{attempt.id}/written/").status_code, 200)
        self.assertIn("played", html)            # option text is shown
        self.assertNotIn("is_correct", html)     # answer key must NOT leak
        self.assertNotIn("'text':", html)        # no raw python dict

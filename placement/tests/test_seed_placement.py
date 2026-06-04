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

    def test_deactivates_other_questions_so_only_curated_are_active(self):
        # An old question that existed before the seed must end up inactive,
        # so the placement selector only ever draws the curated 10.
        old = PlacementQuestion.objects.create(
            code="sp.age.001", question_text="How old are you?", question_type="speaking",
            skill="speaking", topic="age_country", expected_answer_type="voice", is_active=True,
        )
        call_command("seed_placement_questions", stdout=StringIO())
        old.refresh_from_db()
        self.assertFalse(old.is_active)
        self.assertEqual(PlacementQuestion.objects.filter(is_active=True).count(), 10)

    def test_mcq_graded_against_key(self):
        opts = self._q("wr.v2.001").options
        self.assertTrue(answer_key.is_answer_correct("goes", options=opts, expected_type="mcq"))
        self.assertFalse(answer_key.is_answer_correct("go", options=opts, expected_type="mcq"))


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

from django.test import TestCase
from django.utils import translation

from placement.models import PlacementQuestion

from .utils import PlatformAdminTestMixin


class PlacementQuestionBuilderTests(PlatformAdminTestMixin, TestCase):
    def test_placement_question_builder_no_json_for_normal_admin(self):
        self.client.force_login(self.platform_admin)
        response = self.client.get("/admin/placement-questions/new/")
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "pq-builder")
        self.assertNotContains(response, "Options JSON")
        self.assertNotContains(response, "Rubric JSON")

    def test_advanced_json_visible_only_to_superadmin(self):
        self.client.force_login(self.super_admin)
        response = self.client.get("/admin/placement-questions/new/")
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "JSON متقدم للمطور")

    def test_multiple_choice_visual_builder_adds_options(self):
        self.client.force_login(self.platform_admin)
        response = self.client.post(
            "/admin/placement-questions/new/",
            {
                "question_type": "written",
                "skill": "grammar",
                "topic": "intro",
                "question_text": "Choose the correct answer",
                "question_text_ar": "اختر الإجابة الصحيحة",
                "cefr_min_level": "A0",
                "cefr_max_level": "A1",
                "difficulty_score": "0.3",
                "expected_answer_type": "mcq",
                "option_1": "go",
                "option_2": "goes",
                "option_3": "went",
                "correct_option": "2",
                "grammar_weight": "40",
                "vocabulary_weight": "20",
                "minimum_passing_score": "60",
            },
        )
        self.assertEqual(response.status_code, 302)
        question = PlacementQuestion.objects.get(question_text="Choose the correct answer")
        self.assertEqual(question.options[1]["text"], "goes")
        self.assertTrue(question.options[1]["is_correct"])
        self.assertEqual(question.scoring_rubric["grammar_weight"], 40)

    def test_existing_json_parses_into_visual_builder(self):
        question = PlacementQuestion.objects.create(
            question_text="Pick one",
            question_type="written",
            skill="grammar",
            topic="intro",
            expected_answer_type="mcq",
            options=[
                {"text": "am", "is_correct": False},
                {"text": "is", "is_correct": True},
            ],
            scoring_rubric={"grammar_weight": 50, "minimum_passing_score": 70},
        )
        self.client.force_login(self.platform_admin)
        response = self.client.get(f"/admin/placement-questions/{question.pk}/edit/")
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'value="am"')
        self.assertContains(response, 'value="is"')
        self.assertContains(response, 'value="2"', html=False)

    def test_question_validation_friendly_errors(self):
        from platform_admin.forms import PlacementQuestionForm
        form = PlacementQuestionForm(
            data={
                "question_type": "written", "skill": "grammar", "topic": "intro",
                "question_text": "", "question_text_ar": "",
                "cefr_min_level": "A0", "cefr_max_level": "A1",
                "difficulty_score": "0.2", "expected_answer_type": "mcq",
                "option_1": "Only one", "correct_option": "",
            },
            user=self.platform_admin,
        )
        self.assertFalse(form.is_valid())  # empty question is rejected
        self.assertIn("Add the question in Arabic or English.", " ".join(form.non_field_errors()))

from io import StringIO

from django.core.management import call_command
from django.test import TestCase

from learning_core.models import AdaptiveExercise, GrammarTopic, Skill


class SeedLearningCoreTests(TestCase):
    def test_seed_creates_records(self):
        out = StringIO()
        call_command("seed_learning_core", stdout=out)
        self.assertGreaterEqual(Skill.objects.count(), 7)
        self.assertGreaterEqual(GrammarTopic.objects.count(), 20)
        self.assertGreaterEqual(AdaptiveExercise.objects.count(), 5)
        self.assertIn("Seed complete", out.getvalue())

    def test_seed_is_idempotent(self):
        call_command("seed_learning_core")
        s1 = Skill.objects.count()
        t1 = GrammarTopic.objects.count()
        e1 = AdaptiveExercise.objects.count()
        call_command("seed_learning_core")
        self.assertEqual(Skill.objects.count(), s1)
        self.assertEqual(GrammarTopic.objects.count(), t1)
        self.assertEqual(AdaptiveExercise.objects.count(), e1)

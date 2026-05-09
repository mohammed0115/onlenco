from django.test import TestCase

from exams.models import ExamBlueprint
from exams.services.exam_blueprint_service import (
    for_signature,
    seed_default_blueprints,
)


class BlueprintSeedTests(TestCase):
    def test_seed_creates_many(self):
        created, updated = seed_default_blueprints()
        self.assertGreater(created, 50)   # 7 levels × ~10 exam types

    def test_seed_is_idempotent(self):
        seed_default_blueprints()
        n1 = ExamBlueprint.objects.count()
        seed_default_blueprints()
        n2 = ExamBlueprint.objects.count()
        self.assertEqual(n1, n2)

    def test_for_signature_lookup(self):
        seed_default_blueprints()
        bp = for_signature(exam_type="placement", cefr_level="A1")
        self.assertIsNotNone(bp)
        self.assertEqual(bp.cefr_level, "A1")

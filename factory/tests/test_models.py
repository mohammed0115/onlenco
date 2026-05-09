from django.db import IntegrityError
from django.test import TestCase

from factory.models import (
    DatasetExportJob, QuestionTemplate, SubstitutionBank, Topic, TrainingDataset,
)


class FactoryModelTests(TestCase):
    def test_topic_unique_slug(self):
        Topic.objects.create(name="Present simple", slug="grammar-a1-ps",
                             kind="grammar", cefr_level="A1")
        with self.assertRaises(IntegrityError):
            Topic.objects.create(name="dup", slug="grammar-a1-ps",
                                 kind="grammar", cefr_level="A1")

    def test_topic_path_walks_parents(self):
        a = Topic.objects.create(name="Tenses", slug="tenses", kind="grammar")
        b = Topic.objects.create(name="Present", slug="present", kind="grammar", parent=a)
        c = Topic.objects.create(name="Simple",  slug="simple",  kind="grammar", parent=b)
        self.assertEqual(c.path, "tenses/present/simple")

    def test_substitution_bank_size(self):
        b = SubstitutionBank.objects.create(name="x", kind="subject",
                                            items=["a", "b", "c"])
        self.assertEqual(b.size, 3)

    def test_question_template_code_unique(self):
        t = Topic.objects.create(name="t", slug="t", kind="grammar")
        QuestionTemplate.objects.create(
            code="t1", name="t1", topic=t, question_type="multiple_choice",
            pattern="x ___ y", correct_answer_expression="'foo'",
            variables={},
        )
        with self.assertRaises(IntegrityError):
            QuestionTemplate.objects.create(
                code="t1", name="dup", topic=t, question_type="multiple_choice",
                pattern="x", correct_answer_expression="'bar'", variables={},
            )

    def test_dataset_export_job_status_default(self):
        ds = TrainingDataset.objects.create(name="ds1", kind="question_generation")
        job = DatasetExportJob.objects.create(dataset=ds)
        self.assertEqual(job.status, "pending")

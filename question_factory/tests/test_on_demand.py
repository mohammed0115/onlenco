from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings

from question_factory import constants as C
from question_factory.models import (
    QuestionBlueprint, QuestionSeed, UserSeedHistory,
)
from question_factory.services.on_demand_service import (
    OnDemandQuestionService, decode_seed_key, encode_seed_key,
)

User = get_user_model()


def _seed_blueprints():
    """A minimal blueprint set covering 2 levels × 2 skills so the
    user-receives-different-questions test can actually vary."""
    QuestionBlueprint.objects.create(
        code="od-A1-grammar", title="Present simple",
        cefr_level="A1", skill=C.SKILL_GRAMMAR,
        question_type="multiple_choice",
        template_pattern="{subject} ___ to school every day.",
        expected_answer_pattern="verb.0 + 's'",
        explanation_pattern="",
        variables_schema={
            "subject": ["she", "he", "the cat", "Sara", "Ali"],
            "verb": [["walk", "walked"], ["play", "played"], ["cook", "cooked"]],
        },
        metadata={"distractor_config": {"strategy": "morph"}},
    )
    QuestionBlueprint.objects.create(
        code="od-A1-vocab", title="Word meanings",
        cefr_level="A1", skill=C.SKILL_VOCABULARY,
        question_type="multiple_choice",
        template_pattern="What does '{word.0}' mean?",
        expected_answer_pattern="word.1",
        explanation_pattern="",
        variables_schema={
            "word": [["happy", "feeling joy"], ["brave", "showing courage"],
                     ["clever", "intelligent"], ["kind", "friendly"],
                     ["tiny", "very small"]],
        },
        metadata={"distractor_config": {
            "strategy": "from_pool",
            "pool": ["unhappy", "tired", "lazy", "rude", "huge"],
        }},
    )
    QuestionBlueprint.objects.create(
        code="od-B1-grammar", title="Past simple irregular",
        cefr_level="B1", skill=C.SKILL_GRAMMAR,
        question_type="multiple_choice",
        template_pattern="{subject} ___ a sandwich.",
        expected_answer_pattern="verb.1",
        explanation_pattern="",
        variables_schema={
            "subject": ["she", "he", "they", "we"],
            "verb": [["go", "went"], ["eat", "ate"], ["see", "saw"]],
        },
        metadata={"distractor_config": {"strategy": "morph"}},
    )


@override_settings(AXES_ENABLED=False)
class OnDemandSpecTests(TestCase):
    """One test per spec line."""

    @classmethod
    def setUpTestData(cls):
        _seed_blueprints()

    def setUp(self):
        self.user = User.objects.create_user(
            username="od@x.com", email="od@x.com", password="pw",
        )

    # 1. Same seed reproduces same question -----------------------------

    def test_same_seed_reproduces_same_question(self):
        items = OnDemandQuestionService.generate_for_user(
            self.user, cefr_level="A1", count=1,
        )
        self.assertEqual(len(items), 1)
        seed_key = items[0]["seed_key"]
        again = OnDemandQuestionService.replay(seed_key)
        self.assertIsNotNone(again)
        self.assertEqual(items[0]["question_text"], again["question_text"])
        self.assertEqual(items[0]["correct_answer"], again["correct_answer"])
        self.assertEqual(items[0]["options"], again["options"])
        self.assertEqual(items[0]["content_hash"], again["content_hash"])

    def test_replay_works_without_seed_row(self):
        # Replay must succeed even though no QuestionSeed row exists yet.
        items = OnDemandQuestionService.generate_for_user(
            self.user, cefr_level="A1", count=1,
        )
        seed_key = items[0]["seed_key"]
        self.assertEqual(QuestionSeed.objects.count(), 0)
        again = OnDemandQuestionService.replay(seed_key)
        self.assertIsNotNone(again)
        self.assertEqual(QuestionSeed.objects.count(), 0)  # still nothing stored

    # 2. User receives different questions ------------------------------

    def test_user_receives_different_questions_within_one_call(self):
        items = OnDemandQuestionService.generate_for_user(
            self.user, cefr_level="A1", count=8,
        )
        self.assertEqual(len(items), 8)
        seeds = {it["seed_key"] for it in items}
        self.assertEqual(len(seeds), 8)
        # Distinct content within the batch as well.
        hashes = {it["content_hash"] for it in items}
        self.assertEqual(len(hashes), 8)

    def test_user_receives_different_questions_across_calls(self):
        a = OnDemandQuestionService.generate_for_user(
            self.user, cefr_level="A1", count=5,
        )
        b = OnDemandQuestionService.generate_for_user(
            self.user, cefr_level="A1", count=5,
        )
        # Random variants per call → vanishingly unlikely to overlap fully.
        a_seeds = {it["seed_key"] for it in a}
        b_seeds = {it["seed_key"] for it in b}
        self.assertNotEqual(a_seeds, b_seeds)

    # 3. Duplicate user question avoided --------------------------------

    def test_duplicate_user_question_avoided_after_record_view(self):
        first = OnDemandQuestionService.generate_for_user(
            self.user, cefr_level="A1", count=3,
        )
        # Record all 3 as seen-but-not-answered.
        for it in first:
            OnDemandQuestionService.record_view(self.user, it["seed_key"])
        # The user now has 3 hashes in their history. Any new generation
        # must avoid all 3.
        seen_hashes = {it["content_hash"] for it in first}
        more = OnDemandQuestionService.generate_for_user(
            self.user, cefr_level="A1", count=10,
        )
        for it in more:
            self.assertNotIn(it["content_hash"], seen_hashes)

    # 4. Question saved only when used ----------------------------------

    def test_no_seeds_persisted_until_record_view(self):
        before_seeds = QuestionSeed.objects.count()
        before_hist = UserSeedHistory.objects.count()
        items = OnDemandQuestionService.generate_for_user(
            self.user, cefr_level="A1", count=10,
        )
        # generate_for_user must NEVER write.
        self.assertEqual(QuestionSeed.objects.count(), before_seeds)
        self.assertEqual(UserSeedHistory.objects.count(), before_hist)

        # Recording a view writes exactly one seed + one history row.
        OnDemandQuestionService.record_view(
            self.user, items[0]["seed_key"], answered=True, is_correct=True,
        )
        self.assertEqual(QuestionSeed.objects.count(), before_seeds + 1)
        self.assertEqual(UserSeedHistory.objects.count(), before_hist + 1)

    def test_record_view_is_idempotent(self):
        items = OnDemandQuestionService.generate_for_user(
            self.user, cefr_level="A1", count=1,
        )
        sk = items[0]["seed_key"]
        OnDemandQuestionService.record_view(self.user, sk, answered=True, is_correct=False)
        OnDemandQuestionService.record_view(self.user, sk, answered=True, is_correct=True)
        # Same seed_key + same user → still 1 seed and 1 history row,
        # but generated_count incremented and is_correct updated.
        self.assertEqual(QuestionSeed.objects.count(), 1)
        self.assertEqual(UserSeedHistory.objects.count(), 1)
        seed = QuestionSeed.objects.get()
        self.assertEqual(seed.generated_count, 2)
        history = UserSeedHistory.objects.get()
        self.assertTrue(history.is_correct)

    # 5. Generated question matches CEFR and skill ---------------------

    def test_generated_questions_match_filters(self):
        items = OnDemandQuestionService.generate_for_user(
            self.user, cefr_level="A1", skill=C.SKILL_VOCABULARY, count=5,
        )
        self.assertEqual(len(items), 5)
        for it in items:
            self.assertEqual(it["cefr_level"], "A1")
            self.assertEqual(it["skill"], C.SKILL_VOCABULARY)

    def test_filter_yields_empty_when_no_matching_blueprint(self):
        # No C2 blueprint in this fixture → service returns []
        items = OnDemandQuestionService.generate_for_user(
            self.user, cefr_level="C2", count=5,
        )
        self.assertEqual(items, [])


@override_settings(AXES_ENABLED=False)
class SeedKeyEncodingTests(TestCase):
    def test_round_trip(self):
        sk = encode_seed_key("bp-foo", 12345)
        bp_code, variant = decode_seed_key(sk)
        self.assertEqual(bp_code, "bp-foo")
        self.assertEqual(variant, 12345)

    def test_decode_handles_bad_input(self):
        self.assertIsNone(decode_seed_key(""))
        self.assertIsNone(decode_seed_key("not-a-seed"))
        self.assertIsNone(decode_seed_key("sd:bp"))            # missing variant
        self.assertIsNone(decode_seed_key("sd:bp:not-int"))    # variant not int

    def test_replay_returns_none_for_unknown_blueprint(self):
        self.assertIsNone(OnDemandQuestionService.replay("sd:nope:1"))

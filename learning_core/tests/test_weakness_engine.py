from datetime import timedelta

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone

from learning_core.models import GrammarTopic, Skill, UserError, UserWeakness
from learning_core.services import weakness_engine

User = get_user_model()


class WeaknessEngineTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="kim", password="pw")
        self.grammar = Skill.objects.create(
            name="Grammar core", category="grammar", cefr_level="A2"
        )
        self.vocab = Skill.objects.create(
            name="Vocab core", category="vocabulary", cefr_level="A2"
        )
        self.topic_svagree = GrammarTopic.objects.create(
            name="Subject-verb agreement",
            slug="sva",
            cefr_level="A2",
        )
        self.topic_articles = GrammarTopic.objects.create(
            name="Articles", slug="articles", cefr_level="A1"
        )

    def _make_error(self, *, skill, topic, severity=5, days_ago=0):
        err = UserError.objects.create(
            user=self.user,
            source_type="quiz",
            error_type="grammar" if skill == self.grammar else "vocabulary",
            skill=skill,
            grammar_topic=topic,
            severity=severity,
        )
        if days_ago:
            past = timezone.now() - timedelta(days=days_ago)
            UserError.objects.filter(pk=err.pk).update(created_at=past)
        return err

    def test_top_weaknesses_priority_order(self):
        for _ in range(6):
            self._make_error(skill=self.grammar, topic=self.topic_svagree, severity=8)
        for _ in range(2):
            self._make_error(skill=self.vocab, topic=self.topic_articles, severity=3)

        weakness_engine.update_user_weaknesses(self.user)
        top = weakness_engine.get_top_weaknesses(self.user, limit=2)

        self.assertEqual(len(top), 2)
        self.assertEqual(top[0].skill, self.grammar)
        self.assertGreater(top[0].priority_score, top[1].priority_score)
        self.assertGreaterEqual(top[0].frequency, 6)

    def test_resolved_when_no_recent_errors(self):
        # Seed a stale weakness manually
        UserWeakness.objects.create(
            user=self.user,
            skill=self.grammar,
            grammar_topic=self.topic_svagree,
            priority_score=40.0,
            weakness_score=40.0,
            status="active",
        )
        # Add one tiny error to a different bucket so the run does work
        self._make_error(skill=self.vocab, topic=self.topic_articles, severity=2)

        weakness_engine.update_user_weaknesses(self.user)

        stale = UserWeakness.objects.get(skill=self.grammar, grammar_topic=self.topic_svagree)
        # First decay (factor 0.4): 40 -> 16 → still "improving" (5 ≤ 16 < 25)
        self.assertEqual(stale.status, "improving")
        # Run again twice more: 16 → 6.4 → 2.56 (resolved)
        weakness_engine.update_user_weaknesses(self.user)
        weakness_engine.update_user_weaknesses(self.user)
        stale.refresh_from_db()
        self.assertEqual(stale.status, "resolved")

    def test_improving_status_for_low_priority(self):
        # 1 mild error → low priority but above resolved threshold
        self._make_error(skill=self.grammar, topic=self.topic_svagree, severity=2)
        weakness_engine.update_user_weaknesses(self.user)
        w = UserWeakness.objects.get(skill=self.grammar, grammar_topic=self.topic_svagree)
        self.assertIn(w.status, ("active", "improving"))
        self.assertLess(w.priority_score, 50.0)

    def test_old_errors_outside_window_are_ignored(self):
        self._make_error(skill=self.grammar, topic=self.topic_svagree, days_ago=120)
        result = weakness_engine.update_user_weaknesses(self.user)
        # No bucket created from out-of-window errors → no active weakness
        self.assertEqual(result, [])

    def test_untyped_errors_do_not_create_weakness(self):
        UserError.objects.create(
            user=self.user, source_type="quiz", error_type="grammar", severity=5
        )  # no skill/topic
        result = weakness_engine.update_user_weaknesses(self.user)
        self.assertEqual(result, [])

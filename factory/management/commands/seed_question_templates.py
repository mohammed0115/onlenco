"""Seed the starter QuestionTemplate rows. Each one binds banks and
defines a pattern. Tiny set on purpose — see SRS / docs for the growth
plan. Combinatorial reach is high even from these few rows."""
from django.core.management.base import BaseCommand
from django.utils.text import slugify

from factory.models import QuestionTemplate, Topic

SEED = [
    # Present simple (subject ___ verb)
    {
        "code": "tpl-grammar-A1-presimple-3sg",
        "name": "Present simple — 3rd-person singular",
        "topic_slug": "grammar-a1-present-simple",
        "question_type": "multiple_choice",
        "cefr_level": "A1",
        "pattern": "{subject} ___ to the office every day.",
        "variables": {"subject": "subjects_singular", "verb": "verbs_regular"},
        "correct_answer_expression": "verb.0 + 's'",
        "distractor_strategy": "morph",
        "distractor_config": {},
        "explanation_pattern": "Use the third-person singular form '{verb.0}s' with '{subject}'.",
        "difficulty_score": 0.20,
        "estimated_time_seconds": 25,
    },
    # Past simple irregular
    {
        "code": "tpl-grammar-A2-pastsimple-irregular",
        "name": "Past simple — irregular verbs",
        "topic_slug": "grammar-a2-past-simple",
        "question_type": "multiple_choice",
        "cefr_level": "A2",
        "pattern": "{subject} ___ {object} {time}.",
        "variables": {
            "subject": "subjects_singular",
            "verb":    "verbs_irregular",
            "object":  "objects_common",
            "time":    "times_past",
        },
        "correct_answer_expression": "verb.1",
        "distractor_strategy": "morph",
        "explanation_pattern": "The past form of '{verb.0}' is '{verb.1}'.",
        "difficulty_score": 0.40,
        "estimated_time_seconds": 30,
    },
    # Articles
    {
        "code": "tpl-grammar-A1-articles",
        "name": "Articles a/an",
        "topic_slug": "grammar-a1-articles-aanthe",
        "question_type": "multiple_choice",
        "cefr_level": "A1",
        "pattern": "I have ___ {noun.0}.",
        "variables": {"noun": "articles_nouns"},
        "correct_answer_expression": "noun.1",
        "distractor_strategy": "static",
        "distractor_config": {"options": ["a", "an", "the", "—"]},
        "explanation_pattern": "Use '{noun.1}' before '{noun.0}'.",
        "difficulty_score": 0.20,
    },
    # Comparatives
    {
        "code": "tpl-grammar-A2-comparatives",
        "name": "Comparatives",
        "topic_slug": "grammar-a2-comparatives",
        "question_type": "multiple_choice",
        "cefr_level": "A2",
        "pattern": "My brother is ___ than me.",
        "variables": {"adj": "adj_pairs"},
        "correct_answer_expression": "adj.1",
        "distractor_strategy": "morph",
        "explanation_pattern": "Comparative of '{adj.0}' is '{adj.1}'.",
        "difficulty_score": 0.35,
    },
    # Superlatives
    {
        "code": "tpl-grammar-A2-superlatives",
        "name": "Superlatives",
        "topic_slug": "grammar-a2-superlatives",
        "question_type": "multiple_choice",
        "cefr_level": "A2",
        "pattern": "She is the ___ student in class.",
        "variables": {"adj": "adj_pairs"},
        "correct_answer_expression": "adj.2",
        "distractor_strategy": "morph",
        "explanation_pattern": "Superlative of '{adj.0}' is '{adj.2}'.",
        "difficulty_score": 0.40,
    },
    # Vocabulary definitions
    {
        "code": "tpl-vocab-A1-definitions",
        "name": "Vocabulary — definitions",
        "topic_slug": "vocabulary-a1-common-adjectives",
        "question_type": "multiple_choice",
        "cefr_level": "A1",
        "pattern": "What does '{word.0}' mean?",
        "variables": {"word": "vocab_def_pairs"},
        "correct_answer_expression": "word.1",
        "distractor_strategy": "from_bank",
        "distractor_config": {"bank": "vocab_def_pairs"},
        "explanation_pattern": "'{word.0}' means '{word.1}'.",
        "difficulty_score": 0.25,
    },
]


class Command(BaseCommand):
    help = "Seed/refresh starter QuestionTemplate rows."

    def handle(self, *args, **opts):
        created = updated = missing_topic = 0
        for s in SEED:
            topic = Topic.objects.filter(slug=s["topic_slug"]).first()
            if not topic:
                missing_topic += 1
                self.stdout.write(self.style.WARNING(
                    f"Skipped: topic missing for {s['code']} (slug={s['topic_slug']})"
                ))
                continue
            defaults = {k: v for k, v in s.items() if k not in ("topic_slug",)}
            defaults["topic"] = topic
            defaults["is_active"] = True
            obj, was_created = QuestionTemplate.objects.update_or_create(
                code=s["code"], defaults=defaults,
            )
            if was_created:
                created += 1
            else:
                updated += 1
        self.stdout.write(self.style.SUCCESS(
            f"QuestionTemplate: created={created} updated={updated} "
            f"missing_topic={missing_topic} total_active="
            f"{QuestionTemplate.objects.filter(is_active=True).count()}"
        ))

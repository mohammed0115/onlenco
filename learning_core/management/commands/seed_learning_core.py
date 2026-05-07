"""Seed initial Skill, GrammarTopic, and AdaptiveExercise rows.

Idempotent: safe to run repeatedly. Uses get_or_create / update_or_create
keyed on natural identifiers (slug, name+category+cefr_level).
"""
from __future__ import annotations

from django.core.management.base import BaseCommand
from django.db import transaction

from learning_core.models import AdaptiveExercise, GrammarTopic, Skill


SKILLS = [
    ("grammar", "Grammar core"),
    ("vocabulary", "Vocabulary core"),
    ("reading", "Reading core"),
    ("listening", "Listening core"),
    ("speaking", "Speaking core"),
    ("writing", "Writing core"),
    ("pronunciation", "Pronunciation core"),
]

# (cefr_level, name, slug)
TOPICS = [
    ("A1", "Verb to be", "verb-to-be"),
    ("A1", "Present Simple", "present-simple"),
    ("A1", "Articles", "articles"),
    ("A1", "Basic Pronouns", "basic-pronouns"),
    ("A1", "Singular and Plural", "singular-and-plural"),
    ("A2", "Past Simple", "past-simple"),
    ("A2", "Future with going to", "future-going-to"),
    ("A2", "Comparatives", "comparatives"),
    ("A2", "Prepositions of place and time", "prepositions-place-time"),
    ("A2", "Countable and uncountable nouns", "countable-uncountable"),
    ("B1", "Present Perfect", "present-perfect"),
    ("B1", "Modals", "modals"),
    ("B1", "Conditionals type 1 and 2", "conditionals-1-2"),
    ("B1", "Passive voice basics", "passive-voice-basics"),
    ("B1", "Relative clauses", "relative-clauses"),
    ("B2", "Advanced conditionals", "advanced-conditionals"),
    ("B2", "Reported speech", "reported-speech"),
    ("B2", "Complex sentence structure", "complex-sentences"),
    ("B2", "Gerunds and infinitives", "gerunds-infinitives"),
    ("B2", "Discourse markers", "discourse-markers"),
    ("C1", "Inversion", "inversion"),
    ("C1", "Cleft sentences", "cleft-sentences"),
    ("C1", "Mixed conditionals", "mixed-conditionals"),
    ("C2", "Hedging and stance", "hedging-stance"),
    ("C2", "Nominalisation", "nominalisation"),
    ("C3", "Diplomatic and persuasive register", "diplomatic-register"),
    ("C3", "Domain-specific discourse strategies", "domain-discourse"),
]


# A handful of fallback exercises per topic (only seed if topic has zero)
FALLBACK_EXERCISES_BY_TOPIC = {
    "verb-to-be": [
        ("multiple_choice", "She ___ a teacher.", ["am", "is", "are", "be"], "is"),
    ],
    "present-simple": [
        ("multiple_choice", "He ___ to school every day.", ["go", "goes", "going", "went"], "goes"),
    ],
    "past-simple": [
        ("fill_blank", "Yesterday I ___ (eat) breakfast.", [], "ate"),
    ],
    "present-perfect": [
        ("multiple_choice", "I ___ never been to Paris.", ["have", "has", "had", "was"], "have"),
    ],
    "articles": [
        ("fill_blank", "I saw ___ elephant at ___ zoo.", [], "an, the"),
    ],
}


class Command(BaseCommand):
    help = "Seed Skill, GrammarTopic, and fallback AdaptiveExercise rows."

    def handle(self, *args, **options):
        skills_created = 0
        topics_created = 0
        exercises_created = 0

        with transaction.atomic():
            for category, name in SKILLS:
                _, created = Skill.objects.get_or_create(
                    name=name, category=category, cefr_level="",
                    defaults={"is_active": True},
                )
                skills_created += int(created)

            for cefr, name, slug in TOPICS:
                _, created = GrammarTopic.objects.update_or_create(
                    slug=slug,
                    defaults={"name": name, "cefr_level": cefr, "is_active": True},
                )
                topics_created += int(created)

            for slug, items in FALLBACK_EXERCISES_BY_TOPIC.items():
                topic = GrammarTopic.objects.filter(slug=slug).first()
                if not topic:
                    continue
                if AdaptiveExercise.objects.filter(topic=topic).exists():
                    continue
                for qt, question, options, correct in items:
                    AdaptiveExercise.objects.create(
                        topic=topic,
                        cefr_level=topic.cefr_level,
                        difficulty_score=0.4,
                        question_type=qt,
                        question=question,
                        options=options,
                        correct_answer=correct,
                        explanation="Seeded fallback exercise.",
                        generated_by_ai=False,
                        metadata={"source": "seed_learning_core"},
                    )
                    exercises_created += 1

        self.stdout.write(self.style.SUCCESS(
            f"Seed complete: skills={skills_created}, topics={topics_created}, exercises={exercises_created}"
        ))

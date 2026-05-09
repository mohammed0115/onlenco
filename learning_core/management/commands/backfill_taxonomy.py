"""One-shot backfill: seed `Skill` + `GrammarTopic` and link the
existing question-bank rows to them.

Why this exists
---------------
The bulk generators (factory + question_factory) historically did not
populate `AdaptiveExercise.skill_id` / `topic_id`. As a result, every
RAG query that filtered by skill returned nothing, and no GrammarTopic
rows existed at all. This command:

1. Creates one canonical `Skill` per category (cefr_level="" so it
   matches any level).
2. Creates the canonical `GrammarTopic` rows referenced by the seeded
   blueprints + factory templates.
3. Walks every existing `AdaptiveExercise` and populates `skill_id` and
   `topic_id` from `metadata.template_code` or `metadata.bank_code`.
4. Walks every `QuestionBlueprint` and links `grammar_topic` to the
   matching topic when its code carries one.

Idempotent: re-running adopts existing rows and only updates the rows
that are still missing FKs.
"""
from __future__ import annotations

import re
from typing import Dict

from django.core.management.base import BaseCommand
from django.db import transaction

from learning_core.models import AdaptiveExercise, GrammarTopic, Skill
from question_factory.models import QuestionBlueprint


# Canonical Skill categories (one row per category, cefr-agnostic).
SKILL_CATEGORIES = [
    ("grammar",       "General grammar"),
    ("vocabulary",    "General vocabulary"),
    ("reading",       "General reading"),
    ("listening",     "General listening"),
    ("writing",       "General writing"),
    ("speaking",      "General speaking"),
    ("pronunciation", "General pronunciation"),
    ("comprehension", "General comprehension"),
]


# Topics referenced by the seeded blueprints and the factory templates.
# Format: (slug, name, cefr_level)
TOPIC_SEED = [
    # Grammar
    ("present-simple",        "Present simple",         "A1"),
    ("past-simple",           "Past simple",            "A2"),
    ("present-continuous",    "Present continuous",     "A2"),
    ("articles",              "Articles a/an/the",      "A1"),
    ("comparatives",          "Comparatives",           "A2"),
    ("superlatives",          "Superlatives",           "A2"),
    ("present-perfect",       "Present perfect",        "B1"),
    ("conditionals",          "Conditionals",           "B1"),
    ("passive-voice",         "Passive voice",          "B2"),
    ("modals",                "Modals",                 "B1"),
    ("gerund-infinitive",     "Gerund vs infinitive",   "B1"),
    # Vocabulary pseudo-topics
    ("vocab-definitions",     "Vocabulary definitions", ""),
    ("antonyms",              "Antonyms",               ""),
    ("synonyms",              "Synonyms",               ""),
    ("phrasal-verbs",         "Phrasal verbs",          ""),
    ("collocations",          "Collocations",           ""),
    ("idioms",                "Idioms",                 ""),
    ("vocab-in-context",      "Vocabulary in context",  ""),
    # Reading / writing / speaking pseudo-topics (anchor for FK queries)
    ("reading-comprehension", "Reading comprehension",  ""),
    ("writing-prompt",        "Writing prompt",         ""),
    ("speaking-prompt",       "Speaking prompt",        ""),
]


# Map metadata fragments → topic slug. The fragment can appear in
# `template_code`, `bank_code`, `blueprint_code`, or `code`.
TOPIC_FRAGMENT_MAP = {
    # explicit topic names from question_factory templates
    "presimple":         "present-simple",
    "psimple":           "present-simple",
    "ps_":               "present-simple",
    "fb-presimple":      "present-simple",
    "transform-pastsimple": "past-simple",
    "pastsimple":        "past-simple",
    "psimple_past":      "past-simple",
    "presentcont":       "present-continuous",
    "articles":          "articles",
    "comparatives":      "comparatives",
    "comparative":       "comparatives",
    "superlatives":      "superlatives",
    "superlative":       "superlatives",
    "ppct":              "present-perfect",
    "perfect":           "present-perfect",
    "conditional":       "conditionals",
    "passive":           "passive-voice",
    "modal":             "modals",
    "gerund":            "gerund-infinitive",
    "infinitive":        "gerund-infinitive",
    # vocab
    "definition":        "vocab-definitions",
    "def":               "vocab-definitions",
    "vocab_definition":  "vocab-definitions",
    "antonyms":          "antonyms",
    "antonym":           "antonyms",
    "synonyms":          "synonyms",
    "synonym":           "synonyms",
    "phrasal":           "phrasal-verbs",
    "collocation":       "collocations",
    "idiom":             "idioms",
    "vocab_inference":   "vocab-in-context",
    "context":           "vocab-in-context",
    # reading / writing / speaking
    "comprehension":     "reading-comprehension",
    "prompt":            "writing-prompt",   # speaking-prompt overrides below
}


# Map metadata fragments → skill category. Order matters: more specific
# fragments first.
SKILL_FRAGMENT_MAP = {
    "grammar":      "grammar",
    "gram":         "grammar",
    "vocabulary":   "vocabulary",
    "vocab":        "vocabulary",
    "reading":      "reading",
    "listening":    "listening",
    "writing":      "writing",
    "speaking":     "speaking",
    "pronunciation":"pronunciation",
    "comprehension":"comprehension",
}


def _extract_skill(text: str) -> str | None:
    if not text:
        return None
    text = text.lower()
    for fragment, skill in SKILL_FRAGMENT_MAP.items():
        if fragment in text:
            return skill
    return None


def _extract_topic_slug(text: str) -> str | None:
    if not text:
        return None
    text = text.lower()
    # Speaking prompts must be detected before the generic 'prompt' rule.
    if "speak" in text and "prompt" in text:
        return "speaking-prompt"
    if "speaking" in text:
        return "speaking-prompt"
    if "writing" in text and "prompt" in text:
        return "writing-prompt"
    for fragment, slug in TOPIC_FRAGMENT_MAP.items():
        if fragment in text:
            return slug
    return None


def _candidate_strings(ex: AdaptiveExercise) -> list[str]:
    md = ex.metadata or {}
    return [
        md.get("template_code") or "",
        md.get("blueprint_code") or "",
        md.get("bank_code") or "",
        ex.code or "",
    ]


class Command(BaseCommand):
    help = "Seed canonical Skill / GrammarTopic and backfill FK links."

    def add_arguments(self, parser):
        parser.add_argument("--limit", type=int, default=0,
                            help="Cap the number of AdaptiveExercise rows scanned (0 = all).")
        parser.add_argument("--blueprints-only", action="store_true",
                            default=False,
                            help="Only backfill QuestionBlueprint.grammar_topic, skip AE rows.")

    @transaction.atomic
    def handle(self, *args, **opts):
        skills_by_cat = self._seed_skills()
        topics_by_slug = self._seed_topics()

        bp_updated = self._backfill_blueprints(topics_by_slug)
        self.stdout.write(self.style.SUCCESS(
            f"QuestionBlueprint.grammar_topic linked: {bp_updated}"
        ))

        if opts["blueprints_only"]:
            return

        ae_skill, ae_topic = self._backfill_adaptive_exercise(
            skills_by_cat, topics_by_slug, limit=opts["limit"],
        )
        self.stdout.write(self.style.SUCCESS(
            f"AdaptiveExercise: skill linked={ae_skill}, topic linked={ae_topic}"
        ))

    # -- seeding -----------------------------------------------------

    def _seed_skills(self) -> Dict[str, Skill]:
        out: Dict[str, Skill] = {}
        for cat, name in SKILL_CATEGORIES:
            obj, _ = Skill.objects.get_or_create(
                name=name, category=cat, cefr_level="",
                defaults={"is_active": True},
            )
            out[cat] = obj
        self.stdout.write(self.style.NOTICE(f"Skills present: {len(out)}"))
        return out

    def _seed_topics(self) -> Dict[str, GrammarTopic]:
        out: Dict[str, GrammarTopic] = {}
        for slug, name, cefr in TOPIC_SEED:
            obj, _ = GrammarTopic.objects.get_or_create(
                slug=slug,
                defaults={"name": name, "cefr_level": cefr, "is_active": True},
            )
            out[slug] = obj
        self.stdout.write(self.style.NOTICE(f"GrammarTopic rows present: {len(out)}"))
        return out

    # -- backfill ----------------------------------------------------

    def _backfill_blueprints(self, topics: Dict[str, GrammarTopic]) -> int:
        n = 0
        qs = QuestionBlueprint.objects.filter(grammar_topic__isnull=True)
        for bp in qs.iterator(chunk_size=500):
            slug = _extract_topic_slug(bp.code) or _extract_topic_slug(bp.title)
            if slug and slug in topics:
                QuestionBlueprint.objects.filter(pk=bp.pk).update(
                    grammar_topic=topics[slug],
                )
                n += 1
        return n

    def _backfill_adaptive_exercise(
        self,
        skills: Dict[str, Skill],
        topics: Dict[str, GrammarTopic],
        *,
        limit: int = 0,
    ) -> tuple[int, int]:
        skill_n, topic_n = 0, 0
        qs = AdaptiveExercise.objects.filter(skill__isnull=True) | \
             AdaptiveExercise.objects.filter(topic__isnull=True)
        qs = qs.distinct()
        if limit:
            qs = qs[:limit]
        for ex in qs.iterator(chunk_size=500):
            tokens = _candidate_strings(ex)
            joined = " ".join(t for t in tokens if t)

            # Skill
            new_skill_id = ex.skill_id
            if not new_skill_id:
                cat = _extract_skill(joined)
                if cat and cat in skills:
                    new_skill_id = skills[cat].id

            # Topic
            new_topic_id = ex.topic_id
            if not new_topic_id:
                slug = _extract_topic_slug(joined)
                if slug and slug in topics:
                    new_topic_id = topics[slug].id

            if (new_skill_id != ex.skill_id) or (new_topic_id != ex.topic_id):
                AdaptiveExercise.objects.filter(pk=ex.pk).update(
                    skill_id=new_skill_id, topic_id=new_topic_id,
                )
                if new_skill_id and not ex.skill_id:
                    skill_n += 1
                if new_topic_id and not ex.topic_id:
                    topic_n += 1
        return skill_n, topic_n

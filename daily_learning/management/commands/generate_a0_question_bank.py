"""Generate an AdaptiveExercise bank for A0 from the in-code catalog.

For each A0 topic, produce 4 question variants:
  1. The topic's own multiple-choice quiz (1 per topic).
  2. A "fill in the blank" variant of the same sentence.
  3. A translation question (AR → EN target sentence).
  4. A short-answer prompt asking the student to write the sentence.

For 60 topics this seeds ~240 exercises into `learning_core.AdaptiveExercise`
with `code` set so reruns are idempotent and the daily-learning content
selector can pull from this bank instead of always falling back to
templates.

Usage:
    python manage.py generate_a0_question_bank
    python manage.py generate_a0_question_bank --dry-run
    python manage.py generate_a0_question_bank --reset
"""
from __future__ import annotations

import hashlib
import logging

from django.core.management.base import BaseCommand

from daily_learning.services import a0_templates

logger = logging.getLogger(__name__)


def _text_hash(text: str) -> str:
    """Stable hash for AdaptiveExercise.text_hash dedup."""
    return hashlib.sha1((text or "").strip().lower().encode()).hexdigest()


class Command(BaseCommand):
    help = "Seed AdaptiveExercise rows for A0 from the daily-learning catalog."

    def add_arguments(self, parser):
        parser.add_argument(
            "--dry-run", action="store_true",
            help="Print intended changes without writing.",
        )
        parser.add_argument(
            "--reset", action="store_true",
            help="Delete existing A0 catalog-derived AdaptiveExercises first.",
        )
        parser.add_argument(
            "--include-extras", action="store_true",
            help="Also emit word-order + true/false variants. Roughly doubles the bank.",
        )

    def handle(self, *args, **opts):
        dry_run = bool(opts.get("dry_run"))
        reset = bool(opts.get("reset"))
        include_extras = bool(opts.get("include_extras"))

        from learning_core.models import AdaptiveExercise

        if reset and not dry_run:
            n = AdaptiveExercise.objects.filter(
                code__startswith="a0-topic-",
            ).count()
            AdaptiveExercise.objects.filter(
                code__startswith="a0-topic-",
            ).delete()
            self.stdout.write(self.style.WARNING(
                f"[RESET] deleted {n} pre-existing A0 catalog exercises"
            ))

        created = 0
        updated = 0
        skipped = 0

        for topic in a0_templates.A0_TOPICS:
            variants = _build_variants(topic, include_extras=include_extras)
            for idx, variant in enumerate(variants, start=1):
                code = f"a0-topic-{topic.slug}-v{idx}"
                text_hash = _text_hash(variant["question"])
                if dry_run:
                    self.stdout.write(
                        f"[DRY] {code}: {variant['question_type']} — "
                        f"{variant['question'][:60]!r}"
                    )
                    continue
                defaults = {
                    "cefr_level": "A0",
                    "difficulty_score": variant["difficulty_score"],
                    "question_type": variant["question_type"],
                    "question": variant["question"],
                    "options": variant["options"],
                    "correct_answer": variant["correct_answer"],
                    "explanation": variant["explanation"],
                    "text_hash": text_hash,
                    "is_active": True,
                    "is_reviewed": True,        # hand-curated source
                    "generated_by": "template",
                    "quality_score": 90,
                    "estimated_time_seconds": 25,
                    "points": 1,
                    "metadata": {
                        "source": "a0_catalog",
                        "topic_slug": topic.slug,
                        "unit": topic.unit,
                        "variant": idx,
                    },
                }
                obj, was_created = AdaptiveExercise.objects.update_or_create(
                    code=code, defaults=defaults,
                )
                if was_created:
                    created += 1
                else:
                    updated += 1

        self.stdout.write(self.style.SUCCESS(
            f"Done. created={created} updated={updated} skipped={skipped} "
            f"(over {len(a0_templates.A0_TOPICS)} topics)"
        ))


def _build_variants(topic, *, include_extras: bool = False) -> list[dict]:
    """Produce 4 question variants for one A0 topic (6 with --include-extras)."""
    word = topic.target_word
    sentence = topic.target_sentence
    quiz_item = next(
        (it for it in topic.items if it.item_type == "quiz"),
        None,
    )
    variants: list[dict] = []

    # Variant 1 — mirror the topic's quiz (MCQ).
    if quiz_item and quiz_item.question_en and quiz_item.options:
        variants.append({
            "question_type": "multiple_choice",
            "question": quiz_item.question_en,
            "options": list(quiz_item.options),
            "correct_answer": quiz_item.correct_answer,
            "explanation": quiz_item.explanation_en or "",
            "difficulty_score": 0.10,
        })

    # Variant 2 — fill in the blank on the target sentence.
    fill_question, fill_correct = _make_fill_blank(sentence, word)
    if fill_question:
        variants.append({
            "question_type": "fill_blank",
            "question": fill_question,
            "options": [],
            "correct_answer": fill_correct,
            "explanation": f"The full sentence is: {sentence}",
            "difficulty_score": 0.15,
        })

    # Variant 3 — translation EN → student says the sentence.
    variants.append({
        "question_type": "translation",
        "question": f"Say in English: {topic.target_sentence}",
        "options": [],
        "correct_answer": sentence,
        "explanation": "Practise saying the full sentence aloud.",
        "difficulty_score": 0.20,
    })

    # Variant 4 — short-answer write the sentence.
    variants.append({
        "question_type": "short_answer",
        "question": f"Write the sentence about: {word}",
        "options": [],
        "correct_answer": sentence,
        "explanation": f"Target sentence: {sentence}",
        "difficulty_score": 0.20,
    })

    if include_extras:
        # Variant 5 — word-order (rearrange scrambled words).
        words = sentence.rstrip(".!?").split()
        if len(words) >= 2:
            scrambled = list(reversed(words))
            if len(scrambled) >= 3:
                scrambled.append(scrambled.pop(0))   # rotate first → last
            variants.append({
                "question_type": "sentence_building",
                "question": (
                    "Put the words in the correct order: "
                    + " / ".join(scrambled)
                ),
                "options": scrambled,
                "correct_answer": sentence.rstrip(".!?"),
                "explanation": f"The correct sentence is: {sentence}",
                "difficulty_score": 0.20,
            })

        # Variant 6 — true/false on the target sentence.
        true_statement = f"This is a correct English sentence: \"{sentence}\""
        variants.append({
            "question_type": "multiple_choice",
            "question": true_statement,
            "options": ["True", "False"],
            "correct_answer": "True",
            "explanation": "This is the canonical example sentence for this lesson.",
            "difficulty_score": 0.10,
        })

    return variants


def _make_fill_blank(sentence: str, target_word: str) -> tuple[str, str]:
    """Replace target_word in the sentence with a blank.

    Returns (question_text, correct_answer). Returns ("", "") when the
    target word isn't present in the sentence (so the variant is skipped).
    """
    if not target_word or target_word.lower() not in sentence.lower():
        return "", ""
    # Case-insensitive replace, keep punctuation.
    low = sentence.lower()
    idx = low.find(target_word.lower())
    blanked = sentence[:idx] + "____" + sentence[idx + len(target_word):]
    return blanked, target_word

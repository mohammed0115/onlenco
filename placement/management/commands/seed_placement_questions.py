"""Seed the curated placement question bank (5 written MCQ + 5 spoken).

Idempotent and NON-destructive: each row is keyed by ``code`` and upserted,
so re-running (on every deploy via update.sh) keeps the curated set correct
without creating duplicates. It does NOT delete or deactivate other questions
— old questions are removed manually from the admin.

Answer keys reviewed/corrected from the source list:
- Q1 "She ___ to school every day." → **goes** (was "go" — subject-verb agreement).
- Q3 "We ___ from Sudan." → **come** (was "came" — present-simple for origin).
- Q4 wording fixed to "for a living".
Spoken questions get an expected answer + keywords (used for transparency on
the result page and rubric scoring).
"""
from __future__ import annotations

from django.core.management.base import BaseCommand

from placement.models import PlacementQuestion


# (code, en, ar, difficulty, [(option_text, is_correct), ...])
WRITTEN = [
    ("wr.v2.001", "She ___ to school every day.", "هي ___ إلى المدرسة كل يوم.", 0.10,
     [("go", False), ("goes", True), ("went", False), ("gone", False)]),
    ("wr.v2.002", "I ___ 20 years old.", "أنا ___ عشرين عامًا.", 0.10,
     [("is", False), ("am", True), ("are", False), ("were", False)]),
    ("wr.v2.003", "We ___ from Sudan.", "نحن ___ من السودان.", 0.10,
     [("come", True), ("came", False), ("be", False), ("were", False)]),
    ("wr.v2.004", "How old ___ you?", "كم عمرك؟", 0.10,
     [("is", False), ("have", False), ("has", False), ("are", True)]),
    ("wr.v2.005", "They ___ football yesterday.", "هم ___ كرة القدم أمس.", 0.20,
     [("play", False), ("playing", False), ("player", False), ("played", True)]),
]

# (code, en, ar, difficulty, topic, rubric{expected_answer, voice_keywords})
SPEAKING = [
    ("sp.v2.001", "What is your name?", "ما اسمك؟", 0.10, "name",
     {"expected_answer": "My name is …", "voice_keywords": ["my name is", "name", "i am"]}),
    ("sp.v2.002", "How old are you?", "كم عمرك؟", 0.10, "age_country",
     {"expected_answer": "I am … years old.", "voice_keywords": ["i am", "years old", "old"]}),
    ("sp.v2.003", "Where are you from?", "من أين أنت؟", 0.10, "age_country",
     {"expected_answer": "I am from … / I come from ….",
      "voice_keywords": ["i am from", "i come from", "from"]}),
    ("sp.v2.004", "What do you do for a living?", "ماذا تعمل؟", 0.25, "work_study",
     {"expected_answer": "I am a … / I work as ….",
      "voice_keywords": ["i am a", "i work", "work as", "student", "job"]}),
    ("sp.v2.005", "Why do you want to learn English?", "لماذا تريد تعلّم الإنجليزية؟", 0.30, "reason",
     {"expected_answer": "I want to learn English to … / because ….",
      "voice_keywords": ["i want to learn", "to learn english", "because", "to get", "for"]}),
]


class Command(BaseCommand):
    help = "Upsert the curated placement question bank (5 written MCQ + 5 spoken)."

    def handle(self, *args, **opts):
        for code, en, ar, diff, opts_list in WRITTEN:
            PlacementQuestion.objects.update_or_create(
                code=code,
                defaults={
                    "question_text": en, "question_text_ar": ar,
                    "question_type": "written", "skill": "grammar", "topic": "grammar_fix",
                    "cefr_min_level": "A0", "cefr_max_level": "A2",
                    "difficulty_score": diff, "expected_answer_type": "mcq",
                    "options": [{"text": t, "is_correct": c} for t, c in opts_list],
                    "scoring_rubric": {}, "is_active": True,
                },
            )

        for code, en, ar, diff, topic, rubric in SPEAKING:
            PlacementQuestion.objects.update_or_create(
                code=code,
                defaults={
                    "question_text": en, "question_text_ar": ar,
                    "question_type": "speaking", "skill": "speaking", "topic": topic,
                    "cefr_min_level": "A0", "cefr_max_level": "A2",
                    "difficulty_score": diff, "expected_answer_type": "voice",
                    "options": [], "scoring_rubric": rubric, "is_active": True,
                },
            )

        self.stdout.write(self.style.SUCCESS(
            f"Placement bank upserted: written={len(WRITTEN)}, speaking={len(SPEAKING)}. "
            "Old questions are not touched — remove them from the admin."
        ))

"""Seed the 6 cluster reviews for the Onlenco Beginner course.

Depends on `seed_onlenco_beginner_48_units` having run first. Idempotent
by `(course, start_unit_number, end_unit_number)`.

Each Review carries 9 original questions (3 vocab, 3 grammar, 1 reading,
1 listening placeholder, 1 speaking) sampled from the cluster's units.
"""
from __future__ import annotations

from django.core.management.base import BaseCommand
from django.db import transaction

from courses.models import Course, CourseReview, CourseReviewQuestion
from courses.services.onlenco_beginner_quiz_builder import build_questions_for_unit
from courses.services.onlenco_beginner_seed_data import UNITS


COURSE_SLUG = "onlenco-beginner"

REVIEW_RANGES = [
    ("R1", "Review 1 — Identity & Relationships", "مراجعة 1 — الهوية والعلاقات", 1, 8),
    ("R2", "Review 2 — Daily Life & Routines",    "مراجعة 2 — الحياة اليومية",   9, 19),
    ("R3", "Review 3 — Places & Directions",      "مراجعة 3 — الأماكن والاتجاهات", 20, 26),
    ("R4", "Review 4 — Possessions & Home",       "مراجعة 4 — المُلكية والمنزل",  27, 34),
    ("R5", "Review 5 — Preferences & Free Time",  "مراجعة 5 — التفضيلات ووقت الفراغ", 35, 42),
    ("R6", "Review 6 — Ability & Ambition",       "مراجعة 6 — القدرة والطموح",     43, 48),
]


class Command(BaseCommand):
    help = "Create the 6 cluster reviews for the Onlenco Beginner course."

    def add_arguments(self, parser):
        parser.add_argument(
            "--course-slug", default=COURSE_SLUG,
            help=f"Course slug (default: {COURSE_SLUG}).",
        )
        parser.add_argument(
            "--level", default=None,
            choices=["A1", "A2", "B1", "B2", "C1", "C2"],
            help="Use level descriptors instead of A0 UNITS list.",
        )
        parser.add_argument("--quiet", action="store_true")

    @transaction.atomic
    def handle(self, *args, **options):
        quiet = options["quiet"]
        slug = options["course_slug"]
        try:
            course = Course.objects.get(slug=slug)
        except Course.DoesNotExist:
            self.stderr.write(self.style.ERROR(
                "Course not found — run seed_onlenco_beginner_48_units first."
            ))
            return

        # Pick unit-dict source: UNITS for A0, descriptors for any other level.
        if options["level"]:
            from courses.services.onlenco_level_descriptors import LEVELS
            from courses.services.onlenco_level_unit_builder import (
                build_all_units_for_level,
            )
            level_dict = next(lv for lv in LEVELS if lv["code"] == options["level"])
            unit_source = build_all_units_for_level(level_dict)
        else:
            unit_source = UNITS
        units_by_n = {u["n"]: u for u in unit_source}

        total_q = 0
        for tag, title_en, title_ar, start, end in REVIEW_RANGES:
            review, _ = CourseReview.objects.update_or_create(
                course=course,
                start_unit_number=start, end_unit_number=end,
                defaults={
                    "title": title_en,
                    "title_ar": title_ar,
                    "instructions": (
                        f"Review what you learned in Units {start:02d}–{end:02d}. "
                        "Answer 9 questions and self-check your skills."
                    ),
                    "instructions_ar": (
                        f"راجع ما تعلّمته في الوحدات من {start:02d} إلى {end:02d}. "
                        "أجب عن 9 أسئلة وقيّم مهاراتك."
                    ),
                    "is_active": True,
                },
            )

            # Build questions from a sample of cluster units.
            CourseReviewQuestion.objects.filter(review=review).delete()
            picked_units = self._pick_cluster_units(units_by_n, start, end)
            order = 1
            for skill_target, unit in picked_units:
                qs = build_questions_for_unit(unit)
                # Pick one question for each skill bucket.
                matched = next(
                    (q for q in qs if q.get("skill") == skill_target), qs[0],
                )
                CourseReviewQuestion.objects.create(
                    review=review,
                    question_type=matched["question_type"],
                    question_text=matched["question_text"],
                    question_text_ar=matched["question_text_ar"],
                    options=matched.get("options", []),
                    correct_answer=matched.get("correct_answer", ""),
                    explanation=matched.get("explanation", ""),
                    explanation_ar=matched.get("explanation_ar", ""),
                    skill=skill_target,
                    points=matched.get("points", 1),
                    order=order,
                )
                order += 1
                total_q += 1

            if not quiet:
                self.stdout.write(
                    f"  {tag} {title_en} → {review.questions.count()} questions"
                )

        self.stdout.write(self.style.SUCCESS(
            f"Reviews seeded — {len(REVIEW_RANGES)} reviews, {total_q} questions."
        ))

    def _pick_cluster_units(
        self, units_by_n: dict, start: int, end: int,
    ) -> list[tuple[str, dict]]:
        """Pick 9 (skill, unit) pairs covering the cluster.

        Order: 3 vocab, 3 grammar, 1 reading, 1 listening, 1 speaking.
        Cycles through cluster units if there are fewer than 9 of any type.
        """
        cluster = [units_by_n[n] for n in range(start, end + 1) if n in units_by_n]
        if not cluster:
            return []
        plan = (
            ["vocabulary"] * 3
            + ["grammar"] * 3
            + ["reading", "listening", "speaking"]
        )
        return [(skill, cluster[i % len(cluster)]) for i, skill in enumerate(plan)]

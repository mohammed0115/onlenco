"""Re-run the quality validator across the whole bank and (optionally)
flip low-scoring items to is_active=False or is_reviewed=False."""
from django.core.management.base import BaseCommand

from learning_core.models import AdaptiveExercise

from exams.services.question_quality import evaluate as eval_quality


class Command(BaseCommand):
    help = "Validate every AdaptiveExercise; report + optionally deactivate."

    def add_arguments(self, parser):
        parser.add_argument("--threshold", type=int, default=60)
        parser.add_argument("--deactivate-below", action="store_true", default=False)
        parser.add_argument("--limit", type=int, default=0,
                            help="Stop after N items (0 = scan all).")

    def handle(self, *args, threshold: int = 60, deactivate_below: bool = False,
               limit: int = 0, **opts):
        scanned = passed = flagged = deactivated = 0
        qs = AdaptiveExercise.objects.all().iterator(chunk_size=2000)
        for ex in qs:
            scanned += 1
            item = {
                "question": ex.question,
                "correct_answer": ex.correct_answer,
                "options": ex.options or [],
                "question_type": ex.question_type,
                "difficulty_score": ex.difficulty_score,
                "cefr_level": ex.cefr_level,
                "language": ex.language,
            }
            score, failures = eval_quality(item)
            if score >= threshold:
                passed += 1
                if ex.quality_score != score:
                    AdaptiveExercise.objects.filter(pk=ex.pk).update(quality_score=score)
            else:
                flagged += 1
                if deactivate_below and ex.is_active:
                    AdaptiveExercise.objects.filter(pk=ex.pk).update(
                        quality_score=score, is_active=False, is_reviewed=False,
                    )
                    deactivated += 1
                else:
                    AdaptiveExercise.objects.filter(pk=ex.pk).update(quality_score=score)
            if limit and scanned >= limit:
                break
        self.stdout.write(self.style.SUCCESS(
            f"validate: scanned={scanned:,} passed={passed:,} "
            f"flagged={flagged:,} deactivated={deactivated:,}"
        ))

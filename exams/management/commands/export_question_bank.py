"""Stream-export the question bank as JSON-Lines (one JSON object per
line). Memory-safe — does not load the whole bank into RAM."""
import json
import sys

from django.core.management.base import BaseCommand

from learning_core.models import AdaptiveExercise


class Command(BaseCommand):
    help = "Export AdaptiveExercise rows as JSON-Lines (stdout by default)."

    def add_arguments(self, parser):
        parser.add_argument("--cefr-level", type=str, default="")
        parser.add_argument("--skill", type=str, default="")
        parser.add_argument("--limit", type=int, default=0)
        parser.add_argument("--out", type=str, default="-",
                            help="File path or '-' for stdout.")
        parser.add_argument("--active-only", action="store_true", default=False)

    def handle(self, *args, **opts):
        qs = AdaptiveExercise.objects.all()
        if opts["cefr_level"]:
            qs = qs.filter(cefr_level=opts["cefr_level"])
        if opts["skill"]:
            qs = qs.filter(skill__category=opts["skill"])
        if opts["active_only"]:
            qs = qs.filter(is_active=True)
        if opts["limit"]:
            qs = qs[: opts["limit"]]
        qs = qs.iterator(chunk_size=1000)

        sink = sys.stdout if opts["out"] == "-" else open(opts["out"], "w", encoding="utf-8")
        try:
            n = 0
            for ex in qs:
                row = {
                    "code": ex.code,
                    "cefr_level": ex.cefr_level,
                    "skill": ex.skill.category if ex.skill_id else "",
                    "question_type": ex.question_type,
                    "question": ex.question,
                    "options": ex.options or [],
                    "correct_answer": ex.correct_answer,
                    "explanation": ex.explanation,
                    "difficulty_score": ex.difficulty_score,
                    "quality_score": ex.quality_score,
                    "generated_by": ex.generated_by,
                    "language": ex.language,
                }
                sink.write(json.dumps(row, ensure_ascii=False) + "\n")
                n += 1
            self.stdout.write(self.style.SUCCESS(f"exported {n} rows"))
        finally:
            if sink is not sys.stdout:
                sink.close()

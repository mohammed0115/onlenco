"""Bulk-generate question-bank items into AdaptiveExercise.

Examples:
    python manage.py generate_question_bank --target-count 1000 --batch-size 100
    python manage.py generate_question_bank --target-count 300000 --batch-size 1000 --resume
    python manage.py generate_question_bank --cefr-level B1 --skill grammar --target-count 5000
    python manage.py generate_question_bank --dry-run --target-count 100
"""
import time

from django.core.management.base import BaseCommand

from exams.services.bulk_generation_service import generate_to_target


class Command(BaseCommand):
    help = "Generate question-bank items in resumable, deduping batches."

    def add_arguments(self, parser):
        parser.add_argument("--target-count", type=int, default=300_000)
        parser.add_argument("--cefr-level", type=str, default="")
        parser.add_argument("--skill", type=str, default="")
        parser.add_argument("--batch-size", type=int, default=1000)
        parser.add_argument("--use-ai", action="store_true", default=False)
        parser.add_argument("--max-ai-per-batch", type=int, default=0)
        parser.add_argument("--quality-threshold", type=int, default=60)
        parser.add_argument("--resume", action="store_true", default=False)
        parser.add_argument("--dry-run", action="store_true", default=False)

    def handle(self, *args, **opts):
        t0 = time.time()
        cefr = opts["cefr_level"] or None
        skill = opts["skill"] or None
        self.stdout.write(self.style.NOTICE(
            f"target={opts['target_count']:,} cefr={cefr or 'ALL'} skill={skill or 'ALL'} "
            f"batch={opts['batch_size']} ai={opts['use_ai']} resume={opts['resume']} "
            f"dry_run={opts['dry_run']}"
        ))

        def progress(batch, stats, *, level, variant):
            self.stdout.write(
                f"  L={level} v={variant:>3}  "
                f"+{stats['written']:>5} new={stats['new']} "
                f"dups={stats['duplicates']} qOK={stats['passed_quality']}/{stats['candidates']}  "
                f"total={batch.generated_count:,}/{batch.target_count:,}"
            )

        batch = generate_to_target(
            target_count=opts["target_count"],
            cefr_level=cefr,
            skill=skill,
            chunk_size=opts["batch_size"],
            use_ai=opts["use_ai"],
            max_ai_per_batch=opts["max_ai_per_batch"],
            quality_threshold=opts["quality_threshold"],
            resume=opts["resume"],
            dry_run=opts["dry_run"],
            progress_cb=progress,
        )
        secs = time.time() - t0
        self.stdout.write(self.style.SUCCESS(
            f"batch {batch.batch_id}: status={batch.status} "
            f"written={batch.generated_count:,}/{batch.target_count:,} "
            f"duplicates={batch.duplicate_count:,} "
            f"in {secs:.1f}s"
        ))
        if batch.error_message:
            self.stdout.write(self.style.ERROR(f"error: {batch.error_message}"))

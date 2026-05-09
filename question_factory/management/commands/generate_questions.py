"""Bulk Q&A generation pipeline.

Resumable, idempotent, memory-safe, cost-aware. Drives `bulk_generation_service`.

Examples
--------

# Sample 100 candidates (no DB writes, no AI cost) — for previewing distribution
python manage.py generate_questions --dry-run --target-count 100

# Generate the first 10k via templates only
python manage.py generate_questions --target-count 10000 \
    --batch-size 500 --strategy template

# Generate 100k items in hybrid mode, resumable, with an AI budget of 200 calls
python manage.py generate_questions --target-count 100000 \
    --batch-size 1000 --strategy hybrid --resume --max-ai-calls 200

# Generate 5k B1 grammar items via AI, with a hard AI cost cap
python manage.py generate_questions --target-count 5000 \
    --cefr-level B1 --skill grammar --strategy ai --max-ai-calls 50

# Treat low-quality items as review-required instead of rejecting
python manage.py generate_questions --target-count 1000 --review-required
"""
from __future__ import annotations

import time

from django.core.management.base import BaseCommand

from question_factory import constants as C
from question_factory.services.bulk_generation_service import run_generation


class Command(BaseCommand):
    help = "Bulk-generate Q&A items using blueprints + chosen strategy."

    def add_arguments(self, parser):
        parser.add_argument("--target-count", type=int, default=100_000)
        parser.add_argument("--cefr-level", type=str, default="",
                            help='Restrict to a single level (A0..C2). Empty = all levels per default distribution.')
        parser.add_argument("--skill", type=str, default="",
                            help='Restrict to a single skill. Empty = all skills per default ratio.')
        parser.add_argument("--question-type", type=str, default="",
                            help='Restrict to a single question_type (multiple_choice, fill_blank, ...).')
        parser.add_argument("--strategy", type=str, default=C.GEN_TEMPLATE,
                            choices=[C.GEN_TEMPLATE, C.GEN_AI, C.GEN_HYBRID],
                            help='Generation strategy. AI/hybrid fall back to template on failure.')
        parser.add_argument("--batch-size", type=int, default=500)
        parser.add_argument("--resume", action="store_true", default=False,
                            help='Reuse the most recent matching running/paused/failed batch.')
        parser.add_argument("--dry-run", action="store_true", default=False,
                            help='Render + validate only — no DB writes, no AI calls.')
        parser.add_argument("--review-required", action="store_true", default=False,
                            help='Mark borderline items review_required instead of rejecting.')
        parser.add_argument("--max-ai-calls", type=int, default=0,
                            help='Hard cap on AI calls in this run. 0 = no AI; -1 = unlimited.')
        parser.add_argument("--quality-threshold", type=int, default=60,
                            help='Items below this quality_score are rejected (or marked review_required).')

    def handle(self, *args, **opts):
        t0 = time.time()
        target = opts["target_count"]
        cefr = opts["cefr_level"] or None
        skill = opts["skill"] or None
        qtype = opts["question_type"] or None

        # In dry-run mode AI is meaningless (we don't persist) and is
        # disabled to avoid surprise spend.
        if opts["dry_run"] and opts["max_ai_calls"] != 0:
            self.stdout.write(self.style.WARNING(
                "Dry-run forces AI off; ignoring --max-ai-calls."
            ))
            opts["max_ai_calls"] = 0

        self.stdout.write(self.style.NOTICE(
            f"target={target:,} batch={opts['batch_size']} "
            f"strategy={opts['strategy']} cefr={cefr or 'ALL'} "
            f"skill={skill or 'ALL'} qtype={qtype or 'ALL'} "
            f"quality>={opts['quality_threshold']} "
            f"max_ai_calls={opts['max_ai_calls']} "
            f"resume={opts['resume']} dry_run={opts['dry_run']} "
            f"review_required={opts['review_required']}"
        ))

        def progress(p: dict):
            if p.get("skipped"):
                self.stdout.write(
                    f"  [skip] L={p['level']} S={p['skill']} "
                    f"target={p.get('cell_target','-')} already={p.get('already','-')} "
                    f"blueprints={p.get('blueprints','-')}"
                )
                return
            stats = p["stats"]
            self.stdout.write(
                f"  L={p['level']} S={p['skill']} bp={p['blueprint_code']} "
                f"v={p['variant']:>3}  +{stats.get('accepted',0):>4} "
                f"rej={stats.get('rejected',0)} dups={stats.get('duplicates',0)} "
                f"cand={stats.get('candidates',0)} "
                f"strat={stats.get('effective_strategy','-')}  "
                f"cell {p['cell_accepted']:,}/{p['cell_target']:,}  "
                f"ai={p['ai_spent']}/{p['ai_cap']}"
            )

        batch = run_generation(
            target_count=target,
            batch_size=opts["batch_size"],
            strategy=opts["strategy"],
            cefr_level=cefr,
            skill=skill,
            question_type=qtype,
            quality_threshold=opts["quality_threshold"],
            max_ai_calls=opts["max_ai_calls"],
            review_required=opts["review_required"],
            resume=opts["resume"],
            dry_run=opts["dry_run"],
            progress_cb=progress,
        )

        secs = time.time() - t0
        line = (
            f"batch {batch.batch_id} status={batch.status} "
            f"accepted={batch.accepted_count:,} "
            f"target={batch.target_count:,} "
            f"rejected={batch.rejected_count:,} "
            f"duplicates={batch.duplicate_count:,} "
            f"in {secs:.1f}s"
        )
        if batch.status == C.BATCH_COMPLETED:
            self.stdout.write(self.style.SUCCESS(line))
        else:
            self.stdout.write(self.style.ERROR(line))
            if batch.error_message:
                self.stdout.write(self.style.ERROR(f"error: {batch.error_message}"))

"""Score a build's test split through the model router.

Examples
--------
    # Score the latest exercise_generation build (any provider)
    python manage.py eval_local_model --task-type exercise_generation

    # Lock to a specific provider for A/B comparison
    python manage.py eval_local_model --task-type exercise_generation \
        --forced-provider rules

    # Compare provider performance head-to-head
    python manage.py eval_local_model --task-type exercise_generation \
        --forced-provider openai --name openai_baseline
    python manage.py eval_local_model --task-type exercise_generation \
        --forced-provider local_llm --name local_baseline
"""
from __future__ import annotations

import uuid

from django.core.management.base import BaseCommand, CommandError

from ai_training import constants as C
from ai_training.models import DatasetBuild
from ai_training.services.evaluator import evaluate_build


class Command(BaseCommand):
    help = "Run an evaluation pass over a build's test split."

    def add_arguments(self, parser):
        parser.add_argument("--build", type=str, default="",
                            help="Build name. Latest completed build for "
                                 "the task is used if omitted.")
        parser.add_argument("--task-type", type=str, default="")
        parser.add_argument("--name", type=str, default="",
                            help="Eval-run name. Auto-generated if omitted.")
        parser.add_argument("--forced-provider", type=str, default="",
                            help="Lock the router to this single provider "
                                 "(rules / local_classifier / local_llm / rag / openai).")
        parser.add_argument("--limit", type=int, default=0)

    def handle(self, *args, **opts):
        build = self._resolve_build(opts)
        name = opts["name"] or f"eval_{build.task_type}_{uuid.uuid4().hex[:8]}"
        forced = opts["forced_provider"] or None

        self.stdout.write(self.style.NOTICE(
            f"Evaluating build={build.name} task={build.task_type} "
            f"forced_provider={forced or '(router default)'}"
        ))

        run = evaluate_build(
            build, name=name, forced_provider=forced, limit=opts["limit"],
        )
        line = (
            f"eval={run.name} status={run.status} "
            f"total={run.total_examples} correct={run.correct_count} "
            f"incorrect={run.incorrect_count} skipped={run.skipped_count} "
            f"accuracy={run.accuracy:.3f} avg_latency={run.avg_latency_ms}ms"
        )
        if run.mean_absolute_error is not None:
            line += f" mae={run.mean_absolute_error:.4f}"
        if run.status == C.BUILD_COMPLETED:
            self.stdout.write(self.style.SUCCESS(line))
        else:
            self.stdout.write(self.style.ERROR(line))
            if run.error_message:
                self.stdout.write(self.style.ERROR(run.error_message))
        self.stdout.write(f"  providers_used: {run.metadata.get('providers_used') or {}}")

    def _resolve_build(self, opts) -> DatasetBuild:
        if opts["build"]:
            b = DatasetBuild.objects.filter(name=opts["build"]).first()
            if not b:
                raise CommandError(f"Build not found: {opts['build']}")
            return b
        if opts["task_type"]:
            b = (
                DatasetBuild.objects
                .filter(task_type=opts["task_type"], status=C.BUILD_COMPLETED)
                .order_by("-completed_at")
                .first()
            )
            if not b:
                raise CommandError(
                    f"No completed build for task_type={opts['task_type']}"
                )
            return b
        raise CommandError("Provide --build or --task-type.")

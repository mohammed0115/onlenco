"""Build a training dataset from the live data.

Examples
--------
    python manage.py build_training_dataset \
        --task-type error_analysis --min-quality 80

    python manage.py build_training_dataset \
        --task-type exercise_generation --filter cefr_level=B1 --filter min_quality_score=70

    python manage.py build_training_dataset \
        --name eg_v2 --task-type exercise_generation
"""
from __future__ import annotations

import time
import uuid

from django.core.management.base import BaseCommand, CommandError

from ai_training import constants as C
from ai_training.models import DatasetBuild
from ai_training.services import dispatch
from ai_training.services.dataset_exporter import assign_splits


def _parse_filters(raw: list[str]) -> dict:
    out = {}
    for r in raw or []:
        if "=" not in r:
            continue
        k, v = r.split("=", 1)
        v = v.strip()
        # Coerce numerics where obvious.
        if v.isdigit():
            v = int(v)
        out[k.strip()] = v
    return out


class Command(BaseCommand):
    help = "Build a training dataset for a given task type."

    def add_arguments(self, parser):
        parser.add_argument("--name", type=str, default="",
                            help="Name for the build. Auto-generated if omitted.")
        parser.add_argument("--task-type", type=str, required=True,
                            choices=[t for t, _ in C.TASK_TYPE_CHOICES])
        parser.add_argument("--min-quality", type=int, default=60)
        parser.add_argument("--filter", action="append", default=[],
                            help="Source filter as key=value. Repeatable.")
        parser.add_argument("--no-splits", action="store_true", default=False,
                            help="Skip the train/val/test split assignment.")

    def handle(self, *args, **opts):
        t0 = time.time()
        name = opts["name"] or f"{opts['task_type']}_{uuid.uuid4().hex[:8]}"
        build = DatasetBuild.objects.create(
            name=name, task_type=opts["task_type"],
            filters=_parse_filters(opts["filter"]),
            status=C.BUILD_PENDING,
        )
        self.stdout.write(self.style.NOTICE(
            f"Build {name} task={opts['task_type']} filters={build.filters} "
            f"min_quality={opts['min_quality']}"
        ))
        stats = dispatch.run(build, min_quality=opts["min_quality"])

        # Refresh status post-dispatch.
        build.refresh_from_db()
        line = (
            f"build={build.name} status={build.status} "
            f"accepted={build.example_count} "
            f"rejected={build.rejected_count} "
            f"duplicates={build.duplicate_count} "
            f"in {time.time() - t0:.1f}s"
        )
        if build.status == C.BUILD_COMPLETED:
            self.stdout.write(self.style.SUCCESS(line))
        else:
            self.stdout.write(self.style.ERROR(line))
            if build.error_message:
                self.stdout.write(self.style.ERROR(build.error_message))

        # Assign deterministic splits unless skipped.
        if build.status == C.BUILD_COMPLETED and not opts["no_splits"]:
            counts = assign_splits(build)
            self.stdout.write(self.style.NOTICE(
                f"splits: train={counts.get(C.SPLIT_TRAIN, 0)} "
                f"val={counts.get(C.SPLIT_VALIDATION, 0)} "
                f"test={counts.get(C.SPLIT_TEST, 0)}"
            ))

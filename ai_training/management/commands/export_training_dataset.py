"""Export a previously-built training dataset to disk.

Examples
--------
    python manage.py export_training_dataset \
        --task-type error_analysis --format jsonl

    python manage.py export_training_dataset \
        --build eg_v2 --format csv --split test

    # Export every split for a build, one file each:
    python manage.py export_training_dataset --build eg_v2 --format jsonl --all-splits
"""
from __future__ import annotations

from django.core.management.base import BaseCommand, CommandError

from ai_training import constants as C
from ai_training.models import DatasetBuild
from ai_training.services.dataset_exporter import export


class Command(BaseCommand):
    help = "Export an AITrainingExample build to JSONL or CSV."

    def add_arguments(self, parser):
        parser.add_argument("--build", type=str, default="",
                            help="Build name. Mutually exclusive with --task-type.")
        parser.add_argument("--task-type", type=str, default="",
                            help="Export the most recent completed build for this task.")
        parser.add_argument("--format", type=str, default=C.FORMAT_JSONL,
                            choices=[C.FORMAT_JSONL, C.FORMAT_CSV])
        parser.add_argument("--split", type=str, default=C.SPLIT_ALL,
                            choices=[C.SPLIT_ALL, C.SPLIT_TRAIN,
                                     C.SPLIT_VALIDATION, C.SPLIT_TEST])
        parser.add_argument("--all-splits", action="store_true", default=False,
                            help="Export train, validation, and test as separate files.")

    def handle(self, *args, **opts):
        build = self._resolve_build(opts)

        splits = (
            [C.SPLIT_TRAIN, C.SPLIT_VALIDATION, C.SPLIT_TEST]
            if opts["all_splits"] else [opts["split"]]
        )
        for sp in splits:
            job = export(build, fmt=opts["format"], split=sp)
            line = (
                f"build={build.name} fmt={opts['format']} split={sp} "
                f"rows={job.row_count} bytes={job.bytes_written} "
                f"path={job.file_path or '(stream)'} status={job.status}"
            )
            if job.status == C.BUILD_COMPLETED:
                self.stdout.write(self.style.SUCCESS(line))
            else:
                self.stdout.write(self.style.ERROR(line))
                if job.error_message:
                    self.stdout.write(self.style.ERROR(job.error_message))

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
        raise CommandError("Provide either --build or --task-type.")

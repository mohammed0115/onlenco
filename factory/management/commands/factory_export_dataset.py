"""Stream-export a TrainingDataset to JSONL on disk.

Examples:
    # 1. Define the dataset header (one-shot)
    python manage.py export_training_dataset \
        --create question_gen_v1 --kind question_generation \
        --filter cefr_level=B1 --filter min_quality_score=70

    # 2. Export it
    python manage.py export_training_dataset --name question_gen_v1
"""
from __future__ import annotations

from django.core.management.base import BaseCommand, CommandError

from factory.models import TrainingDataset
from factory.services.dataset_builder import export


def _parse_filters(raw: list[str]) -> dict:
    out = {}
    for r in raw or []:
        if "=" not in r:
            continue
        k, v = r.split("=", 1)
        out[k.strip()] = v.strip()
    return out


class Command(BaseCommand):
    help = "Export a TrainingDataset to JSONL."

    def add_arguments(self, parser):
        parser.add_argument("--name", type=str, default="",
                            help="Dataset name to export.")
        parser.add_argument("--create", type=str, default="",
                            help="Create a dataset header with this name and exit.")
        parser.add_argument("--kind", type=str, default="question_generation")
        parser.add_argument("--filter", action="append", default=[],
                            help="key=value filters (repeatable).")
        parser.add_argument("--limit", type=int, default=0)

    def handle(self, *args, **opts):
        if opts["create"]:
            ds, created = TrainingDataset.objects.update_or_create(
                name=opts["create"],
                defaults={
                    "kind": opts["kind"],
                    "filters": _parse_filters(opts["filter"]),
                    "status": "draft",
                },
            )
            self.stdout.write(self.style.SUCCESS(
                f"Dataset {'created' if created else 'updated'}: "
                f"{ds.name} kind={ds.kind} filters={ds.filters}"
            ))
            return

        if not opts["name"]:
            raise CommandError("--name (or --create) is required.")
        ds = TrainingDataset.objects.filter(name=opts["name"]).first()
        if not ds:
            raise CommandError(f"Dataset not found: {opts['name']}")
        job = export(ds, limit=opts["limit"] or None)
        self.stdout.write(self.style.SUCCESS(
            f"Exported {job.row_count} rows to {job.file_path or '(stream)'} "
            f"({job.bytes_written} bytes) — status={job.status}"
        ))
        if job.error_message:
            self.stdout.write(self.style.ERROR(job.error_message))

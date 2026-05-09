"""Print a human-readable summary of a build's quality report.

Examples
--------
    python manage.py generate_dataset_report --build eg_v2
    python manage.py generate_dataset_report --task-type error_analysis  # latest
    python manage.py generate_dataset_report --all                       # all builds
"""
from __future__ import annotations

import json

from django.core.management.base import BaseCommand, CommandError

from ai_training import constants as C
from ai_training.models import DatasetBuild, DatasetQualityReport


class Command(BaseCommand):
    help = "Print the quality report for one or more builds."

    def add_arguments(self, parser):
        parser.add_argument("--build", type=str, default="")
        parser.add_argument("--task-type", type=str, default="",
                            choices=[""] + [t for t, _ in C.TASK_TYPE_CHOICES])
        parser.add_argument("--all", action="store_true", default=False)
        parser.add_argument("--json", action="store_true", default=False,
                            help="Emit raw JSON instead of pretty text.")

    def handle(self, *args, **opts):
        builds = self._select_builds(opts)
        if not builds:
            raise CommandError("No builds match the filter.")

        if opts["json"]:
            self.stdout.write(json.dumps(
                [self._serialise(b) for b in builds],
                ensure_ascii=False, indent=2,
            ))
            return

        for b in builds:
            self._print_text(b)

    def _select_builds(self, opts) -> list[DatasetBuild]:
        if opts["build"]:
            b = DatasetBuild.objects.filter(name=opts["build"]).first()
            return [b] if b else []
        if opts["task_type"]:
            return list(
                DatasetBuild.objects
                .filter(task_type=opts["task_type"])
                .order_by("-started_at")[:1]
            )
        if opts["all"]:
            return list(DatasetBuild.objects.order_by("-started_at"))
        # Default: latest build only.
        return list(DatasetBuild.objects.order_by("-started_at")[:1])

    def _serialise(self, build: DatasetBuild) -> dict:
        report = getattr(build, "quality_report", None)
        return {
            "name": build.name,
            "task_type": build.task_type,
            "status": build.status,
            "started_at": build.started_at.isoformat(),
            "completed_at": build.completed_at.isoformat() if build.completed_at else None,
            "example_count": build.example_count,
            "rejected_count": build.rejected_count,
            "duplicate_count": build.duplicate_count,
            "private_data_count": build.private_data_count,
            "report": (
                {
                    "total_examples":            report.total_examples,
                    "avg_quality_score":         report.avg_quality_score,
                    "distribution_by_cefr":      report.distribution_by_cefr,
                    "distribution_by_skill":     report.distribution_by_skill,
                    "distribution_by_task_type": report.distribution_by_task_type,
                    "duplicates_removed":        report.duplicates_removed,
                    "private_data_filtered":     report.private_data_filtered,
                    "low_quality_filtered":      report.low_quality_filtered,
                    "issues":                    report.issues,
                }
                if report else None
            ),
        }

    def _print_text(self, build: DatasetBuild):
        self.stdout.write(self.style.NOTICE(
            f"\n=== {build.name} ({build.task_type}) — {build.status} ===\n"
        ))
        self.stdout.write(
            f"  examples : {build.example_count:,}\n"
            f"  rejected : {build.rejected_count:,}\n"
            f"  duplicates : {build.duplicate_count:,}\n"
            f"  private_data : {build.private_data_count:,}\n"
        )
        report = getattr(build, "quality_report", None)
        if report is None:
            self.stdout.write("  (no quality report)")
            return
        self.stdout.write(
            f"  avg quality : {report.avg_quality_score}\n"
            f"  by CEFR     : {dict(report.distribution_by_cefr)}\n"
            f"  by skill    : {dict(report.distribution_by_skill)}\n"
            f"  PII filtered: {report.private_data_filtered}\n"
            f"  low-quality : {report.low_quality_filtered}\n"
            f"  duplicates  : {report.duplicates_removed}\n"
        )

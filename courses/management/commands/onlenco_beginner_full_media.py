"""One-shot rollout: generate images + audio for the whole Beginner pack.

Wraps `onlenco_beginner_image_batch` and `onlenco_beginner_audio_batch`
so a single command kicks off the full P13 rollout.

Default behaviour:
  - All 48 units
  - `--prompt-type cover` for images (1 image per Lesson; cheapest)
  - All script types for audio

Cost (est., default invocation):
  - 48 covers × $0.04   = $1.92
  - ≈ 288 short clips   = $0.86
  - Total               ≈ $2.78

Use `--include-all-prompt-types` to also generate the vocabulary /
grammar / quiz images (4 per Lesson — total ~$7.68 for images alone).
"""
from __future__ import annotations

from django.core.management import call_command
from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = (
        "Run the full Beginner-pack media rollout: 48 cover images via "
        "DALL-E + ~288 audio clips via TTS. Cost-bounded."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--include-all-prompt-types", action="store_true",
            help="Also generate vocabulary/grammar/quiz images (~$5.76 more).",
        )
        parser.add_argument(
            "--skip-images", action="store_true",
            help="Only run audio; useful when images are already done.",
        )
        parser.add_argument(
            "--skip-audio", action="store_true",
            help="Only run images.",
        )
        parser.add_argument(
            "--dry-run", action="store_true",
            help="Plan + cost estimate only — no API calls.",
        )
        parser.add_argument(
            "--range", dest="range_", default=None,
            help="Restrict to a unit range, e.g. 1-8.",
        )

    def handle(self, *args, **options):
        self.stdout.write(self.style.MIGRATE_HEADING(
            "=== Onlenco Beginner — Full Media Rollout (P13) ==="
        ))

        common = {}
        if options["range_"]:
            common["range"] = options["range_"]
        if options["dry_run"]:
            common["dry_run"] = True

        if not options["skip_images"]:
            self.stdout.write(self.style.HTTP_INFO("\n[1/2] Image batch…"))
            call_command(
                "onlenco_beginner_image_batch",
                prompt_type=("all" if options["include_all_prompt_types"] else "cover"),
                **common,
            )
        else:
            self.stdout.write("Skipping image batch (--skip-images).")

        if not options["skip_audio"]:
            self.stdout.write(self.style.HTTP_INFO("\n[2/2] Audio batch…"))
            call_command(
                "onlenco_beginner_audio_batch",
                script_type="all",
                **common,
            )
        else:
            self.stdout.write("Skipping audio batch (--skip-audio).")

        self.stdout.write(self.style.SUCCESS(
            "\n=== Full media rollout complete ==="
        ))

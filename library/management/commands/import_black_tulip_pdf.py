"""Import the full Black Tulip novel from a LOCAL source for admin review.

Safety:
  * The source file lives OUTSIDE Git — pass --source /abs/path/file.pdf
    (or a .txt source). Missing source → clean error, no traceback.
  * Default is a DRY-RUN (writes nothing). --apply writes Book/Chapters/
    NovelSegments, all NON-student-visible (is_published=False,
    is_copyright_cleared=False). There is intentionally NO --publish.

Examples:
  python manage.py import_black_tulip_pdf --source The_Black_Tulip-Alexandre_Dumas_pere.pdf --dry-run --max-chapters 2
  python manage.py import_black_tulip_pdf --source /abs/path/file.pdf --apply
"""
from django.core.management.base import BaseCommand, CommandError

from library.services import novel_importer


class Command(BaseCommand):
    help = "Import the full Black Tulip from a local PDF/TXT source for admin review (never auto-published)."

    def add_arguments(self, parser):
        parser.add_argument("--source", required=True, help="Absolute/relative path to the local source PDF or TXT.")
        parser.add_argument("--dry-run", action="store_true", help="Preview only — writes nothing (default).")
        parser.add_argument("--apply", action="store_true", help="Write Book/Chapters/Segments (review-only, unpublished).")
        parser.add_argument("--max-chapters", type=int, default=None, help="Limit to the first N chapters (testing).")
        parser.add_argument("--replace", action="store_true", help="Delete a previous import of this title first.")

    def handle(self, *args, **opts):
        source = opts["source"]
        apply = opts["apply"]
        max_chapters = opts["max_chapters"]
        replace = opts["replace"]

        try:
            if not apply:
                # Default + explicit --dry-run both land here.
                preview = novel_importer.build_preview(source, max_chapters=max_chapters)
                self._print_preview(preview)
                self.stdout.write(self.style.WARNING(
                    "DRY-RUN — nothing written. Re-run with --apply to import for review."
                ))
                return

            if replace:
                self.stdout.write(self.style.WARNING(
                    "--replace: deleting any previous import of "
                    f"'{novel_importer.BOOK_TITLE}' before re-importing."
                ))
            result = novel_importer.apply_import(
                source, max_chapters=max_chapters, replace=replace,
            )
            self._print_apply(result)

        except novel_importer.PdfSourceMissing as exc:
            raise CommandError(str(exc))
        except novel_importer.PdfExtractionUnavailable as exc:
            raise CommandError(str(exc))

    def _print_preview(self, p):
        self.stdout.write(self.style.MIGRATE_HEADING("Black Tulip import — DRY RUN"))
        self.stdout.write(f"  source readable     : {p.file_exists}")
        self.stdout.write(f"  PDF pages           : {p.page_count}")
        self.stdout.write(f"  cleaned word count  : {p.word_count}")
        self.stdout.write(f"  chapters detected   : {p.chapter_count}")
        self.stdout.write(f"  segments expected   : {p.segment_count}")
        self.stdout.write(f"  first chapters      : {', '.join(p.first_chapter_titles) or '(none)'}")
        self.stdout.write(f"  first segment preview:\n    {p.first_segment_preview[:200]}")
        if p.warnings:
            self.stdout.write(self.style.WARNING("  warnings:"))
            for w in p.warnings:
                self.stdout.write(self.style.WARNING(f"    - {w}"))

    def _print_apply(self, r):
        self.stdout.write(self.style.SUCCESS(
            f"[OK] Imported '{r['book_title']}' for review — "
            f"chapters={r['chapters_created']}, segments={r['segments_created']}."
        ))
        self.stdout.write(
            f"     is_published={r['is_published']} · "
            f"is_copyright_cleared={r['is_copyright_cleared']} "
            f"(NOT student-visible). No illustrations/vocabulary auto-created."
        )

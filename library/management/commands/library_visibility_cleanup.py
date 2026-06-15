"""Hide library books from students without deleting them (Phase 19.0H).

Keeps ONE book (e.g. the full Black Tulip import) and sets every other
book to ``is_published=False`` so it disappears from the student library
but stays fully visible/reviewable in Platform Admin.

Safety:
  * Default is a DRY-RUN (writes nothing). Pass ``--apply`` to write.
  * NEVER hard-deletes — there is intentionally no ``--delete``.
  * NEVER changes copyright clearance or content; only ``is_published``.
  * Does NOT publish the kept book — publishing stays a manual gated step.

Examples:
  python manage.py library_visibility_cleanup --keep-book "The Black Tulip — Full Import Review" --hide-others --dry-run
  python manage.py library_visibility_cleanup --keep-book-id 16 --hide-others --apply
"""
from django.core.management.base import BaseCommand, CommandError

from library.models import Book


class Command(BaseCommand):
    help = (
        "Hide all library books except one from students (is_published=False). "
        "Dry-run by default. Never deletes, never changes copyright/content."
    )

    def add_arguments(self, parser):
        parser.add_argument("--keep-book", default=None, help="Exact title of the book to keep.")
        parser.add_argument("--keep-book-id", type=int, default=None, help="ID of the book to keep.")
        parser.add_argument(
            "--hide-others", action="store_true",
            help="Hide every OTHER book (is_published=False). Required to take effect.",
        )
        parser.add_argument("--dry-run", action="store_true", help="Preview only — writes nothing (default).")
        parser.add_argument("--apply", action="store_true", help="Actually write is_published=False on others.")

    def handle(self, *args, **opts):
        keep_id = opts.get("keep_book_id")
        keep_title = opts.get("keep_book")
        hide_others = opts.get("hide_others")
        apply = opts.get("apply")

        if not keep_id and not keep_title:
            raise CommandError("Provide --keep-book <title> or --keep-book-id <id>.")

        # Resolve the kept book — id wins when both are given.
        if keep_id:
            kept = Book.objects.filter(pk=keep_id).first()
        else:
            kept = Book.objects.filter(title=keep_title).first()
        if kept is None:
            raise CommandError(
                f"Keep-book not found ({'id=%s' % keep_id if keep_id else 'title=%r' % keep_title})."
            )

        others = Book.objects.exclude(pk=kept.pk).order_by("id")
        currently_visible = list(Book.objects.filter(is_published=True).order_by("id"))
        to_hide = list(others.filter(is_published=True).order_by("id"))

        self.stdout.write(self.style.MIGRATE_HEADING("Library visibility cleanup"))
        self.stdout.write(f"  keep book           : #{kept.pk} {kept.title!r} (is_published={kept.is_published})")
        self.stdout.write(f"  total books         : {Book.objects.count()}")
        self.stdout.write(f"  currently visible   : {len(currently_visible)}")
        for b in currently_visible:
            self.stdout.write(f"      visible: #{b.pk} {b.title!r}")
        self.stdout.write(f"  other books         : {others.count()}")
        self.stdout.write(f"  would be hidden now : {len(to_hide)}")
        for b in to_hide:
            self.stdout.write(f"      hide: #{b.pk} {b.title!r}")

        if not hide_others:
            self.stdout.write(self.style.WARNING(
                "  --hide-others not set — nothing to do. Re-run with --hide-others."
            ))
            return

        if not apply:
            self.stdout.write(self.style.WARNING(
                "DRY-RUN — nothing written. Expected after --apply: "
                f"only kept book unchanged; {len(to_hide)} other published book(s) → is_published=False. "
                "No deletes, no copyright/content changes."
            ))
            return

        # Apply: hide only — never delete, never touch copyright/content.
        hidden = others.filter(is_published=True).update(is_published=False)
        self.stdout.write(self.style.SUCCESS(
            f"[OK] Hidden {hidden} other book(s) from students. "
            f"Kept #{kept.pk} {kept.title!r} unchanged. No deletes."
        ))

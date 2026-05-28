"""Add a stable ``code`` field to ``Book`` and ``Chapter``.

Same pattern as courses 0008: add blank → backfill → make unique.
"""
from django.db import migrations, models


def _populate(apps, schema_editor):
    from courses.services.code_generator import (
        generate_book_code,
        generate_chapter_code,
        next_book_sequence,
    )

    Book = apps.get_model("library", "Book")
    Chapter = apps.get_model("library", "Chapter")

    # Per-CEFR-level book sequence.
    seen_codes_by_level: dict[str, list[str]] = {}
    for b in Book.objects.order_by("pk"):
        if b.code:
            seen_codes_by_level.setdefault(b.level, []).append(b.code)
            continue
        bucket = seen_codes_by_level.setdefault(b.level, [])
        seq = next_book_sequence(bucket)
        b.code = generate_book_code(b.level, seq)
        bucket.append(b.code)
        b.save(update_fields=["code"])

    # Chapter code := <book.code>-CHnn. If a chapter has no book code
    # (shouldn't happen now), fall back to a pk-anchored value.
    for ch in Chapter.objects.select_related("book").order_by("pk"):
        if ch.code:
            continue
        if ch.book_id and ch.book.code:
            ch.code = generate_chapter_code(ch.book.code, ch.sort_order)
        else:
            ch.code = f"ONL-XX-BOOK-000-CH{ch.sort_order:02d}-{ch.pk:06d}"
        ch.save(update_fields=["code"])


def _depopulate(apps, schema_editor):
    apps.get_model("library", "Book").objects.update(code="")
    apps.get_model("library", "Chapter").objects.update(code="")


class Migration(migrations.Migration):
    dependencies = [
        ("library", "0006_chapter_audio_file_chapter_audio_url_and_more"),
        # The book code generator lives in the courses app; the
        # migration imports it, so make sure courses' code-field
        # migration has run first.
        ("courses", "0008_auto_codes"),
    ]

    operations = [
        migrations.AddField(
            model_name="book",
            name="code",
            field=models.CharField(
                blank=True, db_index=True, default="", max_length=50,
                verbose_name="Auto code",
            ),
            preserve_default=False,
        ),
        migrations.AddField(
            model_name="chapter",
            name="code",
            field=models.CharField(
                blank=True, db_index=True, default="", max_length=60,
                verbose_name="Auto code",
            ),
            preserve_default=False,
        ),
        migrations.RunPython(_populate, reverse_code=_depopulate),
        migrations.AlterField(
            model_name="book",
            name="code",
            field=models.CharField(
                blank=True, db_index=True, max_length=50, unique=True,
                verbose_name="Auto code",
            ),
        ),
        migrations.AlterField(
            model_name="chapter",
            name="code",
            field=models.CharField(
                blank=True, db_index=True, max_length=60, unique=True,
                verbose_name="Auto code",
            ),
        ),
    ]

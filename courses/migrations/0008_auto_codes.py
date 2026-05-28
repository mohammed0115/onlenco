"""Add a stable, human-readable ``code`` to Course / Unit / Lesson / Quiz.

Strategy:
  1. Add the field as blank/non-unique with empty default — safe on a
     table with existing rows.
  2. Backfill every row with a generated code (parents first, so
     children can derive from them).
  3. Alter the field to ``unique=True`` once every row holds a value.
"""
from django.db import migrations, models


def _populate(apps, schema_editor):
    from courses.services.code_generator import (
        fallback_lesson_code,
        fallback_quiz_code,
        generate_course_code,
        generate_lesson_code,
        generate_quiz_code,
        generate_unit_code,
        next_course_sequence,
        parse_course_sequence,
    )

    Course = apps.get_model("courses", "Course")
    CourseUnit = apps.get_model("courses", "CourseUnit")
    Lesson = apps.get_model("courses", "Lesson")
    LessonQuiz = apps.get_model("courses", "LessonQuiz")

    # --- Courses: per-CEFR-level sequence ---
    seen_codes_by_level: dict[str, list[str]] = {}
    for c in Course.objects.select_related("level").order_by("pk"):
        if c.code:
            seen_codes_by_level.setdefault(c.level.code, []).append(c.code)
            continue
        level = c.level.code if c.level_id else "XX"
        bucket = seen_codes_by_level.setdefault(level, [])
        seq = next_course_sequence(bucket)
        c.code = generate_course_code(level, seq)
        bucket.append(c.code)
        c.save(update_fields=["code"])

    # --- Units: derive from course code + unit order ---
    for u in CourseUnit.objects.select_related("course", "course__level").order_by("pk"):
        if u.code:
            continue
        if not u.course_id or not u.course.level_id:
            u.code = f"ONL-XX-C000-U{u.order:02d}-{u.pk:06d}"
        else:
            course_seq = parse_course_sequence(u.course.code or "")
            u.code = generate_unit_code(u.course.level.code, course_seq, u.order)
        u.save(update_fields=["code"])

    # --- Lessons: derive from course code + unit order + lesson order ---
    for l in Lesson.objects.select_related("course", "course__level", "unit").order_by("pk"):
        if l.code:
            continue
        level = l.course.level.code if (l.course_id and l.course.level_id) else ""
        if l.unit_id and l.course.code:
            course_seq = parse_course_sequence(l.course.code)
            l.code = generate_lesson_code(level, course_seq, l.unit.order, l.order)
        else:
            l.code = fallback_lesson_code(l.pk, level)
        l.save(update_fields=["code"])

    # --- Quizzes: <lesson.code>-QZ ---
    for q in LessonQuiz.objects.select_related("lesson").order_by("pk"):
        if q.code:
            continue
        if q.lesson_id and q.lesson.code:
            q.code = generate_quiz_code(q.lesson.code)
        else:
            q.code = fallback_quiz_code(q.pk)
        q.save(update_fields=["code"])


def _depopulate(apps, schema_editor):
    """Reverse: clear codes back to empty string."""
    for name in ("Course", "CourseUnit", "Lesson", "LessonQuiz"):
        apps.get_model("courses", name).objects.update(code="")


class Migration(migrations.Migration):
    dependencies = [
        ("courses", "0007_course_drip_enabled"),
    ]

    operations = [
        # 1) Add the field as blank + non-unique (default empty string).
        migrations.AddField(
            model_name="course",
            name="code",
            field=models.CharField(
                blank=True, db_index=True, default="", max_length=50,
                verbose_name="Auto code",
            ),
            preserve_default=False,
        ),
        migrations.AddField(
            model_name="courseunit",
            name="code",
            field=models.CharField(
                blank=True, db_index=True, default="", max_length=50,
                verbose_name="Auto code",
            ),
            preserve_default=False,
        ),
        migrations.AddField(
            model_name="lesson",
            name="code",
            field=models.CharField(
                blank=True, db_index=True, default="", max_length=50,
                verbose_name="Auto code",
            ),
            preserve_default=False,
        ),
        migrations.AddField(
            model_name="lessonquiz",
            name="code",
            field=models.CharField(
                blank=True, db_index=True, default="", max_length=60,
                verbose_name="Auto code",
            ),
            preserve_default=False,
        ),

        # 2) Back-fill every row.
        migrations.RunPython(_populate, reverse_code=_depopulate),

        # 3) Promote to unique now that every row has a value.
        migrations.AlterField(
            model_name="course",
            name="code",
            field=models.CharField(
                blank=True, db_index=True, max_length=50, unique=True,
                verbose_name="Auto code",
            ),
        ),
        migrations.AlterField(
            model_name="courseunit",
            name="code",
            field=models.CharField(
                blank=True, db_index=True, max_length=50, unique=True,
                verbose_name="Auto code",
            ),
        ),
        migrations.AlterField(
            model_name="lesson",
            name="code",
            field=models.CharField(
                blank=True, db_index=True, max_length=50, unique=True,
                verbose_name="Auto code",
            ),
        ),
        migrations.AlterField(
            model_name="lessonquiz",
            name="code",
            field=models.CharField(
                blank=True, db_index=True, max_length=60, unique=True,
                verbose_name="Auto code",
            ),
        ),
    ]

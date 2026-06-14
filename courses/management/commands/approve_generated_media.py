"""Bulk-approve AI-generated lesson media (images / audio).

The batch generator (``generate_lesson_media_batch``) lands media at
``needs_review`` — hidden from students until approved. Approving ~1000 items
one-by-one in the review UI is impractical, so this command approves, in one
shot, every generated row that actually HAS a file (it never approves an empty
placeholder, so missing media keeps its clean "coming soon" card).

Dry-run by default. Examples::

    python manage.py approve_generated_media --course onlenco-elementary --media images
    python manage.py approve_generated_media --course onlenco-elementary --media images --confirm
    python manage.py approve_generated_media --all --media all --confirm
    python manage.py approve_generated_media --course onlenco-advanced --topics 1-24 --media images --confirm
"""
from __future__ import annotations

from django.core.management.base import BaseCommand, CommandError
from django.db.models import Q
from django.utils import timezone

from courses.models import (
    Course, Lesson, LessonAudioScript, LessonImagePrompt,
)


def _parse_topics(spec):
    spec = (spec or "").strip()
    if not spec:
        return None
    if "-" in spec:
        lo, hi = spec.split("-", 1)
        return list(range(int(lo), int(hi) + 1))
    return [int(x) for x in spec.split(",") if x.strip()]


class Command(BaseCommand):
    help = "Bulk-approve generated lesson media (images/audio) that have a file."

    def add_arguments(self, parser):
        parser.add_argument("--course", default=None, help="Course slug.")
        parser.add_argument("--all", action="store_true",
                            help="Apply across every non-archived course.")
        parser.add_argument("--media", choices=["images", "audio", "all"], default="all")
        parser.add_argument("--topics", default=None,
                            help="Lesson-order range/list, e.g. 1-24 or 1,2,5.")
        parser.add_argument("--confirm", action="store_true",
                            help="Apply (default is a dry-run preview).")

    def handle(self, *args, **opts):
        if not opts["course"] and not opts["all"]:
            raise CommandError("Pass --course <slug> or --all.")

        courses = (
            Course.objects.exclude(status="archived")
            if opts["all"]
            else Course.objects.filter(slug=opts["course"])
        )
        courses = list(courses.select_related("level"))
        if not courses:
            raise CommandError("No matching course(s).")

        topics = _parse_topics(opts["topics"])
        do_images = opts["media"] in ("images", "all")
        do_audio = opts["media"] in ("audio", "all")
        apply = opts["confirm"]
        now = timezone.now()
        total_img = total_aud = 0

        for course in courses:
            lessons = Lesson.objects.filter(course=course)
            if topics:
                lessons = lessons.filter(order__in=topics)
            lesson_ids = list(lessons.values_list("id", flat=True))
            lvl = course.level.code if course.level_id else "?"

            n_img = n_aud = 0
            if do_images:
                qs = (
                    LessonImagePrompt.objects
                    .filter(lesson_id__in=lesson_ids)
                    .exclude(generation_status="approved")
                    .exclude(Q(generated_image="") | Q(generated_image__isnull=True))
                )
                n_img = qs.count()
                if apply and n_img:
                    qs.update(generation_status="approved", is_generated=True,
                              reviewed_at=now, updated_at=now)
            if do_audio:
                qs = (
                    LessonAudioScript.objects
                    .filter(lesson_id__in=lesson_ids)
                    .exclude(generation_status="approved")
                    .exclude(Q(generated_audio="") | Q(generated_audio__isnull=True))
                )
                n_aud = qs.count()
                if apply and n_aud:
                    qs.update(generation_status="approved", is_generated=True,
                              reviewed_at=now, updated_at=now)

            total_img += n_img
            total_aud += n_aud
            verb = "approved" if apply else "would approve"
            self.stdout.write(f"  [{lvl}] {course.slug}: {verb} images={n_img} audio={n_aud}")

        head = self.style.SUCCESS if apply else self.style.WARNING
        self.stdout.write(head(
            f"{'Approved' if apply else 'DRY-RUN — would approve'} "
            f"{total_img} image(s) + {total_aud} audio clip(s)."))
        if not apply:
            self.stdout.write("Re-run with --confirm to apply.")

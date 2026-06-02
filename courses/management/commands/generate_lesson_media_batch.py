"""Prompt 15 — Media Generation Pilot for Batch 1.

Generate images/audio for published Batch-1 topics (02-06 only) through the
ai_usage wrapper, budget-gated. Generated media lands as needs_review.

    python manage.py generate_lesson_media_batch --course=onlenco-beginner --topics=2-6 --media=all --dry-run
    python manage.py generate_lesson_media_batch --course=onlenco-beginner --topics=2-6 --media=images --confirm --budget-usd=2.00 [--allow-dev-generation] [--replace] [--fail-fast]
"""
from __future__ import annotations

from decimal import Decimal

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError

from courses.models import Lesson
from courses.services import media_generation_service as svc


def _parse_topics(spec: str) -> list[int]:
    spec = (spec or "").strip()
    if "-" in spec:
        lo, hi = spec.split("-", 1)
        return list(range(int(lo), int(hi) + 1))
    return [int(x) for x in spec.split(",") if x.strip()]


class Command(BaseCommand):
    help = "Generate AI media (image/audio) for Batch-1 topics via ai_usage (pilot)."

    def add_arguments(self, parser):
        parser.add_argument("--course", required=True)
        parser.add_argument("--topics", required=True)
        parser.add_argument("--media", choices=["images", "audio", "all"], default="all")
        parser.add_argument("--dry-run", action="store_true", dest="dry_run")
        parser.add_argument("--confirm", action="store_true")
        parser.add_argument("--budget-usd", dest="budget_usd", default=None)
        parser.add_argument("--replace", action="store_true")
        parser.add_argument("--fail-fast", action="store_true", dest="fail_fast")
        parser.add_argument("--allow-dev-generation", action="store_true",
                            dest="allow_dev", help="Bypass the enabled-flag in dev.")
        # Smoke-test selectors (Prompt 16): restrict to a single purpose and/or
        # a hard item cap so a live run generates exactly 1 image / 1 audio.
        parser.add_argument("--purpose", default=None,
                            help="Only this purpose (e.g. cover / vocabulary / intro).")
        parser.add_argument("--limit", type=int, default=0,
                            help="Hard cap on generated items per media type (0 = no cap).")

    def handle(self, *args, **opts):
        dry_run = opts["dry_run"] or not opts["confirm"]
        orders = _parse_topics(opts["topics"])
        pilot = set(_parse_topics(getattr(settings, "ONLENCO_MEDIA_PILOT_TOPICS", "2-6")))
        outside = [o for o in orders if o not in pilot]
        if outside:
            raise CommandError(
                f"Topics {outside} are outside the pilot range {sorted(pilot)}. "
                "This pilot generates media for Batch 1 only.")

        if not dry_run:
            enabled = getattr(settings, "ONLENCO_MEDIA_GENERATION_ENABLED", False)
            if not enabled and not opts["allow_dev"]:
                raise CommandError(
                    "Media generation is disabled. Set ONLENCO_MEDIA_GENERATION_ENABLED=1 "
                    "or pass --allow-dev-generation (dev only).")

        budget = (Decimal(str(opts["budget_usd"])) if opts["budget_usd"]
                  else Decimal(str(getattr(settings, "ONLENCO_MEDIA_PILOT_BUDGET_USD", "5.00"))))
        est_img = svc._est("ONLENCO_MEDIA_EST_COST_PER_IMAGE_USD", "0.02")
        est_aud = svc._est("ONLENCO_MEDIA_EST_COST_PER_AUDIO_USD", "0.05")
        max_img = getattr(settings, "ONLENCO_MEDIA_MAX_IMAGES_PER_RUN", 20)
        max_aud = getattr(settings, "ONLENCO_MEDIA_MAX_AUDIO_PER_RUN", 30)
        do_images = opts["media"] in ("images", "all")
        do_audio = opts["media"] in ("audio", "all")

        # Eligible lessons: in-range, published/approved, NOT archived/pending.
        eligible_statuses = {"published", "approved"}
        lessons = list(
            Lesson.objects.filter(course__slug=opts["course"], order__in=orders)
            .exclude(status="archived").order_by("order"))

        spent = Decimal("0")
        c = {"img_gen": 0, "img_skip": 0, "img_fail": 0,
             "aud_gen": 0, "aud_skip": 0, "aud_fail": 0,
             "img_planned": 0, "aud_planned": 0, "budget_stops": 0}
        from ai_usage.models import AIUsageLog
        log_before = AIUsageLog.objects.count()

        self.stdout.write(f"Media pilot — course={opts['course']} topics={orders} "
                          f"media={opts['media']} budget=${budget} "
                          f"mode={'DRY-RUN' if dry_run else 'CONFIRM'}")

        def budget_left(est):
            return (spent + est) <= budget

        for L in lessons:
            if L.status not in eligible_statuses:
                self.stdout.write(self.style.WARNING(
                    f"  T{L.order:02d}: SKIP — status '{L.status}' not eligible."))
                continue
            if do_images:
                iqs = L.image_prompts.all().order_by("sort_order")
                if opts["purpose"]:
                    iqs = iqs.filter(prompt_type=opts["purpose"])
                for ip in iqs:
                    c["img_planned"] += 1
                    if dry_run:
                        self.stdout.write(f"  [DRY] T{L.order:02d} image:{ip.prompt_type}")
                        continue
                    if c["img_gen"] >= max_img or (opts["limit"] and c["img_gen"] >= opts["limit"]):
                        self.stdout.write(self.style.WARNING("  image limit reached — stop."))
                        break
                    if not budget_left(est_img):
                        c["budget_stops"] += 1
                        self.stdout.write(self.style.WARNING("  budget reached — stopping images."))
                        break
                    outcome, detail = svc.generate_lesson_image(
                        ip, actor=self._actor(), replace=opts["replace"])
                    self._tally(c, "img", outcome)
                    if outcome == "generated":
                        spent += (ip.ai_usage_log.estimated_cost_usd if ip.ai_usage_log else est_img) or est_img
                    self.stdout.write(f"  T{L.order:02d} image:{ip.prompt_type} → {outcome} ({detail})")
                    if outcome == "failed" and opts["fail_fast"]:
                        raise CommandError(f"--fail-fast: image failed ({detail})")
            if do_audio:
                aqs = L.audio_scripts.all().order_by("sort_order")
                if opts["purpose"]:
                    aqs = aqs.filter(script_type=opts["purpose"])
                for sc in aqs:
                    c["aud_planned"] += 1
                    if dry_run:
                        self.stdout.write(f"  [DRY] T{L.order:02d} audio:{sc.script_type}")
                        continue
                    if c["aud_gen"] >= max_aud or (opts["limit"] and c["aud_gen"] >= opts["limit"]):
                        self.stdout.write(self.style.WARNING("  audio limit reached — stop."))
                        break
                    if not budget_left(est_aud):
                        c["budget_stops"] += 1
                        self.stdout.write(self.style.WARNING("  budget reached — stopping audio."))
                        break
                    outcome, detail = svc.generate_lesson_audio(
                        sc, actor=self._actor(), replace=opts["replace"])
                    self._tally(c, "aud", outcome)
                    if outcome == "generated":
                        spent += (sc.ai_usage_log.estimated_cost_usd if sc.ai_usage_log else est_aud) or est_aud
                    self.stdout.write(f"  T{L.order:02d} audio:{sc.script_type} → {outcome} ({detail})")
                    if outcome == "failed" and opts["fail_fast"]:
                        raise CommandError(f"--fail-fast: audio failed ({detail})")

        logged = AIUsageLog.objects.count() - log_before
        self.stdout.write(self.style.SUCCESS(
            f"\nSummary [{'DRY-RUN' if dry_run else 'WRITE'}]:"))
        self.stdout.write(
            f"  images: planned={c['img_planned']} generated={c['img_gen']} "
            f"skipped={c['img_skip']} failed={c['img_fail']}")
        self.stdout.write(
            f"  audio:  planned={c['aud_planned']} generated={c['aud_gen']} "
            f"skipped={c['aud_skip']} failed={c['aud_fail']}")
        self.stdout.write(
            f"  est_spent=${spent} budget=${budget} budget_stops={c['budget_stops']} "
            f"AIUsageLog_created={logged}")
        needs_review = (
            Lesson.objects.filter(course__slug=opts["course"], order__in=orders)
            .exclude(status="archived"))
        from courses.models import LessonImagePrompt, LessonAudioScript
        nri = LessonImagePrompt.objects.filter(lesson__in=needs_review, generation_status="needs_review").count()
        nra = LessonAudioScript.objects.filter(lesson__in=needs_review, generation_status="needs_review").count()
        self.stdout.write(f"  media awaiting review: images={nri} audio={nra}")
        self.stdout.write("  (Generated media is hidden from students until approved.)")

    def _actor(self):
        from django.contrib.auth import get_user_model
        U = get_user_model()
        return U.objects.filter(is_superuser=True).first() or U.objects.filter(is_staff=True).first()

    @staticmethod
    def _tally(c, kind, outcome):
        if outcome == "generated":
            c[f"{kind}_gen"] += 1
        elif outcome == "skipped":
            c[f"{kind}_skip"] += 1
        else:
            c[f"{kind}_fail"] += 1

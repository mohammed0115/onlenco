"""Diagnose why the placement test doesn't show the expected questions.

Read-only. Prints:
  * the ACTIVE question bank per section (written / speaking),
  * which selector topic-buckets are empty vs over-full (the usual cause
    of "the questions I activated don't appear as-is"),
  * any ACTIVE question that is NOT part of the curated v2 set (leftover
    old questions that must be deactivated), and any curated question that
    is inactive,
  * optionally, what a fresh attempt WOULD select for a user (--simulate),
  * optionally, the exact questions a past attempt served (--attempt).

The placement selector samples 5 written + 5 speaking RANDOMLY from the
ACTIVE pool, stratified across 5 topic buckets per section. So if more
than 5 questions are active in a section — or the curated bank wasn't
re-seeded — the student sees a random subset, not "exactly the set you
activated". The fix is almost always: run ``seed_placement_questions``
so the ACTIVE pool is exactly the curated 5+5.

Usage (production, inside the web container):
    docker compose exec -T web python manage.py placement_doctor
    docker compose exec -T web python manage.py placement_doctor --simulate student@example.com
    docker compose exec -T web python manage.py placement_doctor --attempt 123
"""
from __future__ import annotations

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand

from placement.models import (
    PlacementAttempt, PlacementAttemptQuestion, PlacementQuestion,
)
from placement.services import placement_question_selector as sel

try:
    from placement.management.commands.seed_placement_questions import (
        WRITTEN as CURATED_WRITTEN, SPEAKING as CURATED_SPEAKING,
    )
    CURATED_CODES = {w[0] for w in CURATED_WRITTEN} | {s[0] for s in CURATED_SPEAKING}
except Exception:  # pragma: no cover - defensive
    CURATED_CODES = set()


def _snip(text, n=48):
    text = (text or "").replace("\n", " ").strip()
    return (text[:n] + "…") if len(text) > n else text


class Command(BaseCommand):
    help = "Diagnose the placement question bank vs what the test actually serves."

    def add_arguments(self, parser):
        parser.add_argument("--simulate", metavar="EMAIL_OR_USERNAME",
                            help="Dry-run the selector for this user and print the picks.")
        parser.add_argument("--attempt", type=int, metavar="ATTEMPT_ID",
                            help="Print the exact questions a past attempt served.")

    # ------------------------------------------------------------------
    def handle(self, *args, **opts):
        self._bank_summary()
        if opts.get("simulate"):
            self._simulate(opts["simulate"])
        if opts.get("attempt"):
            self._attempt(opts["attempt"])

    # ------------------------------------------------------------------
    def _bank_summary(self):
        w("=" * 70, self)
        w("PLACEMENT BANK — ACTIVE QUESTIONS", self)
        w("=" * 70, self)
        for section, dist in (("written", sel.WRITTEN_DISTRIBUTION),
                              ("speaking", sel.SPEAKING_DISTRIBUTION)):
            active = list(
                PlacementQuestion.objects
                .filter(question_type=section, is_active=True)
                .order_by("topic", "code")
            )
            w("", self)
            w(f"### {section.upper()} — active={len(active)} (test needs 5)", self)
            if len(active) > 5:
                w(f"  ⚠ MORE THAN 5 ACTIVE → the test shows a RANDOM 5 of these, "
                  f"not all of them.", self)
            if len(active) < 5:
                w(f"  ⚠ FEWER THAN 5 ACTIVE → backfill will repeat / fall short.", self)

            # Topic-bucket coverage (the selector picks ~1 per bucket).
            w("  topic buckets the selector expects:", self)
            for topic, label in dist:
                n = sum(1 for q in active if q.topic == topic)
                flag = "·" if n == 1 else ("∅ EMPTY" if n == 0 else f"×{n}")
                w(f"    [{flag:>8}] {topic:<12} ({label})", self)

            # The actual active rows.
            w("  active rows:", self)
            for q in active:
                curated = "" if q.code in CURATED_CODES else "  ← NOT in curated v2 set"
                w(f"    {q.code:<14} topic={q.topic:<12} "
                  f"{q.expected_answer_type:<10} d={q.difficulty_score:<4} "
                  f"\"{_snip(q.question_text)}\"{curated}", self)

        # Leftover-active + inactive-curated flags.
        extra_active = list(
            PlacementQuestion.objects.filter(is_active=True)
            .exclude(code__in=CURATED_CODES).values_list("code", flat=True)
        )
        inactive_curated = sorted(
            CURATED_CODES - set(
                PlacementQuestion.objects.filter(is_active=True, code__in=CURATED_CODES)
                .values_list("code", flat=True)
            )
        )
        w("", self)
        w("-" * 70, self)
        if extra_active:
            w(f"⚠ {len(extra_active)} ACTIVE question(s) are NOT in the curated v2 set:", self)
            w("    " + ", ".join(extra_active), self)
            w("  → These leak into the test. Deactivate them by running:", self)
            w("      python manage.py seed_placement_questions", self)
        else:
            w("✓ Every active question is part of the curated v2 set.", self)
        if inactive_curated:
            w(f"⚠ {len(inactive_curated)} curated question(s) are INACTIVE "
              f"(won't appear): {', '.join(inactive_curated)}", self)
            w("  → Re-activate them by running: python manage.py seed_placement_questions", self)
        if not extra_active and not inactive_curated and CURATED_CODES:
            w("✓ Active pool == curated 5 written + 5 speaking. The test will serve "
              "exactly these.", self)
        w("-" * 70, self)

    # ------------------------------------------------------------------
    def _simulate(self, ident):
        User = get_user_model()
        user = (User.objects.filter(email=ident).first()
                or User.objects.filter(username=ident).first())
        if user is None:
            w(f"\n[simulate] no user matches '{ident}'", self)
            return
        w("", self)
        w("=" * 70, self)
        w(f"SIMULATED SELECTION for {ident} (dry-run, nothing saved)", self)
        w("=" * 70, self)
        import random
        rng = random.Random()
        written = sel.select_written_questions(user, rng=rng)
        speaking = sel.select_speaking_questions(user, rng=rng)
        for label, picks in (("WRITTEN", written), ("SPEAKING", speaking)):
            w(f"  {label} ({len(picks)} picked):", self)
            for q in picks:
                w(f"    {q.code:<14} topic={q.topic:<12} "
                  f"\"{_snip(q.question_text)}\"", self)
        if len(written) < 5 or len(speaking) < 5:
            w("  ⚠ Selector returned fewer than 5 — bank is short for this user "
              "(maybe difficulty ceiling or recent-attempt exclusion).", self)

    # ------------------------------------------------------------------
    def _attempt(self, attempt_id):
        attempt = PlacementAttempt.objects.filter(pk=attempt_id).first()
        if attempt is None:
            w(f"\n[attempt] no PlacementAttempt #{attempt_id}", self)
            return
        w("", self)
        w("=" * 70, self)
        w(f"ATTEMPT #{attempt.id} — user={attempt.user_id} status={attempt.status}", self)
        w("  (exactly what this student was served)", self)
        w("=" * 70, self)
        rows = (PlacementAttemptQuestion.objects
                .filter(attempt=attempt).select_related("question")
                .order_by("section", "order"))
        for r in rows:
            q = r.question
            live = "active" if q.is_active else "INACTIVE-now"
            ans = _snip(r.user_answer_text, 30)
            w(f"  [{r.section:<8} #{r.order}] {q.code:<14} ({live}) "
              f"\"{_snip(q.question_text)}\"  answer=\"{ans}\"", self)
        if not rows:
            w("  (no persisted questions for this attempt)", self)


def w(line, cmd):
    cmd.stdout.write(line)

"""Recompute stored placement results for PAST attempts.

Fixes attempts finalised before the result fixes shipped:
  * written_score that was left at 0,
  * speaking questions with no stored student answer,
  * overall_score / PlacementResult rows out of sync with the corrected
    written + speaking scores.

It reuses the exact same helpers the live flow now uses
(``grade_written_section`` / ``map_speaking_transcript``). It does NOT send
any email or re-run the diagnostic engine — it only corrects stored numbers.

Usage:
    # preview everything (no writes)
    docker compose exec -T web python manage.py recompute_placement_results --dry-run
    # fix one attempt
    docker compose exec -T web python manage.py recompute_placement_results --attempt 18
    # fix one student
    docker compose exec -T web python manage.py recompute_placement_results --user student@example.com
    # fix all completed attempts
    docker compose exec -T web python manage.py recompute_placement_results --all
"""
from __future__ import annotations

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError

from placement.models import PlacementAttempt
from placement.views import grade_written_section, map_speaking_transcript


class Command(BaseCommand):
    help = "Recompute written/speaking/overall scores for past placement attempts (no emails)."

    def add_arguments(self, parser):
        parser.add_argument("--attempt", type=int, help="Recompute a single attempt id.")
        parser.add_argument("--user", help="Recompute all attempts for this email/username.")
        parser.add_argument("--all", action="store_true",
                            help="Recompute every completed attempt.")
        parser.add_argument("--dry-run", action="store_true",
                            help="Show what would change without writing.")

    def handle(self, *args, **opts):
        qs = self._select(opts)
        dry = opts.get("dry_run")
        n = changed = 0
        for attempt in qs.select_related("result", "voice_conversation"):
            n += 1
            if self._recompute(attempt, dry=dry):
                changed += 1
        verb = "would change" if dry else "changed"
        self.stdout.write(self.style.SUCCESS(
            f"Processed {n} attempt(s); {verb} {changed}."
        ))

    # ------------------------------------------------------------------
    def _select(self, opts):
        if opts.get("attempt"):
            qs = PlacementAttempt.objects.filter(pk=opts["attempt"])
            if not qs.exists():
                raise CommandError(f"No PlacementAttempt #{opts['attempt']}")
            return qs
        if opts.get("user"):
            User = get_user_model()
            u = (User.objects.filter(email=opts["user"]).first()
                 or User.objects.filter(username=opts["user"]).first())
            if u is None:
                raise CommandError(f"No user matches '{opts['user']}'")
            return PlacementAttempt.objects.filter(user=u)
        if opts.get("all"):
            return PlacementAttempt.objects.filter(status="completed")
        raise CommandError("Pass one of --attempt / --user / --all (optionally --dry-run).")

    # ------------------------------------------------------------------
    def _recompute(self, attempt, *, dry: bool) -> bool:
        from tutor.models import VoiceCallEvaluation

        old_written = attempt.written_score
        old_speaking = attempt.speaking_score
        old_overall = attempt.overall_score
        old_level = attempt.recommended_cefr_level

        conv = attempt.voice_conversation
        eval_obj = (
            VoiceCallEvaluation.objects.filter(conversation=conv).first()
            if conv is not None else None
        )

        if dry:
            # Compute written WITHOUT persisting per-question scores: grade a
            # detached read so a dry run truly writes nothing.
            new_written = self._dry_written(attempt)
        else:
            new_written = grade_written_section(attempt)
        if new_written is None:
            new_written = attempt.written_score or 0

        new_speaking = attempt.speaking_score or 0
        if eval_obj is not None:
            if not dry:
                from placement.views import compute_speaking_score
                # Old attempts have no live answers → force fallback reconstruction.
                map_speaking_transcript(attempt, conv, eval_obj, use_live=False)
                new_speaking = compute_speaking_score(
                    attempt, fallback=eval_obj.overall_score or new_speaking)
            else:
                new_speaking = eval_obj.overall_score or new_speaking

        # Score-based, weighted level — IDENTICAL to the live finalise flow so
        # the dashboard stays consistent (the AI's own cefr_level estimate is
        # NOT used as the level source).
        from placement.services.level_mapping import (
            level_for_percentage, weighted_overall, cap_to_speaking,
        )
        new_overall = weighted_overall(new_written, new_speaking)
        new_level = cap_to_speaking(level_for_percentage(new_overall), new_speaking)

        line = (f"  attempt #{attempt.id} (user={attempt.user_id}): "
                f"written {old_written}->{new_written}, "
                f"speaking {old_speaking}->{new_speaking}, "
                f"overall {old_overall}->{new_overall}, "
                f"level {old_level or '-'}->{new_level or '-'}")
        self.stdout.write(line)

        unchanged = (new_written == (old_written or 0)
                     and new_overall == (old_overall or 0)
                     and (new_level or "") == (old_level or ""))
        if dry or unchanged:
            return not unchanged

        attempt.written_score = new_written
        attempt.speaking_score = new_speaking
        attempt.overall_score = new_overall
        attempt.recommended_cefr_level = new_level
        attempt.save(update_fields=[
            "written_score", "speaking_score", "overall_score", "recommended_cefr_level",
        ])
        if attempt.result_id:
            r = attempt.result
            r.written_score = new_written
            r.speaking_score = new_speaking
            r.overall_score = new_overall
            r.level = new_level or r.level
            r.save(update_fields=["written_score", "speaking_score", "overall_score", "level"])
        return True

    def _dry_written(self, attempt) -> int | None:
        from placement.services.answer_key import is_answer_correct
        rows = list(attempt.questions.filter(section="written").select_related("question"))
        correct = counted = 0
        for aq in rows:
            q = aq.question
            verdict = is_answer_correct(
                (aq.user_answer_text or "").strip(),
                options=q.options, rubric=q.scoring_rubric,
                expected_type=q.expected_answer_type,
            )
            if verdict is None:
                if aq.score is not None:
                    counted += 1
                    correct += 1 if aq.score >= 50 else 0
                continue
            counted += 1
            correct += 1 if verdict else 0
        return int(round(100 * correct / counted)) if counted else None

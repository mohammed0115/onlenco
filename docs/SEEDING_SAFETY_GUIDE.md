# Seeding Safety Guide (post-publish)

How to run the curriculum seed safely once lessons have been approved/published.

## TL;DR

`python manage.py seed_beginner_48_topics --confirm` is **safe to re-run in
production**. It will:
* **never** change the status of an `approved` / `published` / `archived` lesson,
* **never** clear `published_at` / `approved_by` / `approved_at`,
* refresh content only for `pending_review` (and other not-yet-reviewed) lessons,
* create any genuinely missing topic as `pending_review` (never auto-approve/publish),
* leave Topic 01 (Gold Reference) untouched,
* abort with a `CommandError` if any existing status would change unexpectedly.

## What `--confirm` does (safe default)

| Existing lesson status | Action |
|---|---|
| `published` | **skip** — status + `published_at` + content preserved |
| `approved` | **skip** — status + `approved_by/at` + content preserved |
| `archived` | **skip** — stays hidden, content preserved |
| `pending_review` / `draft` / `changes_requested` / `in_review` | content refreshed in place; **status kept** |
| (missing) | created as `pending_review` |

Output reports `created / updated_pending_review / skipped_published /
skipped_approved / skipped_archived / status_changes`. If
`status_changes != 0` without a dangerous flag, the command **fails**.

## `--dry-run`

Explicit no-write preview (same as omitting `--confirm`). `--dry-run` always
wins if both are passed.

## `--topic=N`

Scopes the run to a single topic. Status preservation rules still apply — a
published Topic 02 is skipped, not reset.

## Dangerous flags — do NOT use in normal workflow

* `--update-reviewed-content` (requires `--confirm`): refreshes the **content**
  of approved/published lessons but still **does not** change their status.
  Use only when you intentionally want to push a content edit to a live lesson.
* `--reset-status` (requires `--confirm` + `--topic=N` +
  `--i-understand-this-can-unpublish`): resets a single topic to
  `pending_review`. **This can unpublish a live lesson** and remove student
  access. Reserved for dev/recovery.

## When NOT to re-seed

* You normally do **not** need to re-seed after go-live. Re-seed only to push a
  corrected `pending_review` topic from the JSON source.
* Never use `--reset-status` on a published topic to "fix" it — instead use the
  workflow: `unpublish_teacher_batch` -> edit -> re-`approve` -> `publish_teacher_batch`.

## Rollback recommendations

* To take a published topic offline: `unpublish_teacher_batch --topics=N --confirm`
  (published -> approved; students lose access; no data deleted).
* Status transitions always go through `lesson_review_workflow` so a
  `LessonReviewEvent` audit row is written every time.

## Status preservation guarantee

The seed never uses `queryset.update(status=...)`, never puts `status` in an
`update_or_create` defaults for an existing lesson, and runs a before/after
status assertion inside the transaction — so a regression is impossible without
an explicit, acknowledged dangerous flag.

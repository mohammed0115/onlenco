"""Auto-build a Library course from the A0 daily-learning catalog.

Produces:
  Book   "Onlenco A0 — First Words" (level=A0, category="grammar",
         published=True)
  Chapter (per A0Topic):  audio listening unit with body text
         derived from the topic's vocabulary + sentence + simple quiz
         hint, plus an estimated duration. No audio_file is uploaded
         (we don't ship recordings yet) — the chapter template falls
         back to browser TTS via the "Play with voice" button.

The command is idempotent: re-running keeps the same Book row and
update_or_creates each Chapter by sort_order, so admins can hand-edit
chapter bodies without losing edits on re-seed.

Usage:
    python manage.py seed_a0_audio_course
    python manage.py seed_a0_audio_course --force   # overwrites bodies
"""
from __future__ import annotations

from django.core.management.base import BaseCommand
from django.utils import timezone

from daily_learning.services import a0_templates
from library.models import Book, Chapter


# Body template: bilingual A0 reference page. The English half is the
# spoken target; the Arabic half explains what the student is hearing
# so an absolute-beginner reader can self-study without a tutor.
def _build_body(topic) -> str:
    word = topic.target_word
    word_ar = _arabic_for_word(topic)
    sentence = topic.target_sentence

    quiz_hint_en = ""
    quiz_hint_ar = ""
    for item in topic.items:
        if item.item_type == "quiz" and item.question_en:
            quiz_hint_en = (
                f"\n\nQuick check: {item.question_en}\n"
                f"Answer: {item.correct_answer}"
            )
            if item.explanation_ar:
                quiz_hint_ar = (
                    f"\n\nالتحقق السريع: {item.question_ar or item.question_en}\n"
                    f"الإجابة: {item.correct_answer}\n"
                    f"{item.explanation_ar}"
                )
            break

    en_block = (
        f"Word: {word}\n\n"
        f"Sentence: {sentence}\n\n"
        f"Listen and repeat the sentence two times.\n"
        f"Then say it out loud yourself."
        f"{quiz_hint_en}"
    )
    ar_block = (
        f"\n\n— — —\n\n"
        f"الكلمة: {word} = {word_ar}\n\n"
        f"الجملة: {sentence}\n\n"
        f"اضغط زر التشغيل واستمع للجملة مرتين، ثم انطقها بنفسك.\n"
        f"بعد التكرار، حاول تكوين جملة مشابهة بكلمة جديدة."
        f"{quiz_hint_ar}"
    )
    return en_block + ar_block


def _arabic_for_word(topic) -> str:
    """Pull the Arabic gloss from the vocabulary item's content_text.

    Format inside the A0 templates is `"word — arabic"` — so we just
    split on the em-dash and return whatever is after it.
    """
    vocab = next((i for i in topic.items if i.item_type == "vocabulary"), None)
    if not vocab or not vocab.content_text_en:
        return ""
    parts = vocab.content_text_en.split("—", 1)
    return parts[1].strip() if len(parts) > 1 else ""


def _duration_seconds(topic) -> int:
    """Rough estimate: 6 seconds per sentence word, minimum 15s."""
    words = len(topic.target_sentence.split())
    return max(15, words * 6)


class Command(BaseCommand):
    help = "Build a Library audio course from the A0 daily-learning catalog."

    def add_arguments(self, parser):
        parser.add_argument(
            "--force", action="store_true",
            help="Overwrite chapter bodies even if they were edited.",
        )

    def handle(self, *args, **opts):
        force = bool(opts.get("force"))

        book, book_created = Book.objects.update_or_create(
            title="Onlenco A0 — First Words",
            defaults={
                "author": "Onlenco",
                "category": "grammar",
                "level": "A0",
                "summary": (
                    "Auto-generated audio listening course for absolute "
                    "beginners. Each chapter pairs one simple word with "
                    "one short sentence and a quick check."
                ),
                "published_at": timezone.now().date(),
                "is_published": True,
            },
        )
        self.stdout.write(self.style.SUCCESS(
            f"Book {'CREATED' if book_created else 'EXISTS'}: id={book.id}"
        ))

        created = 0
        updated = 0
        kept = 0
        for sort_order, topic in enumerate(a0_templates.A0_TOPICS, start=1):
            title = topic.title_en
            existing = Chapter.objects.filter(
                book=book, sort_order=sort_order,
            ).first()

            if existing and not force:
                # Idempotent path: don't clobber operator edits.
                # Update only the title + duration metadata.
                changed = False
                if existing.title != title:
                    existing.title = title
                    changed = True
                new_dur = _duration_seconds(topic)
                if existing.duration_seconds != new_dur:
                    existing.duration_seconds = new_dur
                    changed = True
                if changed:
                    existing.save(update_fields=["title", "duration_seconds"])
                    updated += 1
                else:
                    kept += 1
                continue

            body = _build_body(topic)
            if existing:
                existing.title = title
                existing.body = body
                existing.duration_seconds = _duration_seconds(topic)
                existing.save(update_fields=["title", "body", "duration_seconds"])
                updated += 1
            else:
                Chapter.objects.create(
                    book=book,
                    sort_order=sort_order,
                    title=title,
                    body=body,
                    duration_seconds=_duration_seconds(topic),
                )
                created += 1

        self.stdout.write(self.style.SUCCESS(
            f"Chapters — created={created} updated={updated} unchanged={kept} "
            f"(total catalog topics={len(a0_templates.A0_TOPICS)})"
        ))

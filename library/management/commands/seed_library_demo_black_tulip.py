"""Seed a short, copyright-safe demo novel for the Interactive Novel Reader.

IMPORTANT — content policy:
  * The text below is ORIGINAL, adapted/inspired prose written for Onlenco.
  * It is NOT copied from any PDF, school edition, or publisher abridgement.
  * It only borrows the *general public-domain theme* of Dumas' "The Black
    Tulip" (a rare black tulip, a young grower, hope/jealousy/prison/courage)
    — no source passages are reproduced.
  * No real images or audio are created. One illustration row is seeded in
    ``needs_review`` (no file) purely to demonstrate the approval gate; it is
    never student-visible.

Idempotent: safe to run repeatedly (``update_or_create`` on stable keys).

Run:  python manage.py seed_library_demo_black_tulip
"""
from django.core.management.base import BaseCommand
from django.db import transaction

from library.models import (
    Book,
    Chapter,
    NovelIllustration,
    NovelSegment,
    NovelVocabularyHighlight,
)


BOOK_TITLE = "The Black Tulip — Demo Reader"

# 4 very short, original segments (English) + a teaching-style Arabic
# translation, a short Arabic explanation, and a few vocabulary words each.
SEGMENTS = [
    {
        "order": 1,
        "title": "A Rare Flower",
        "text_en": (
            "In a small Dutch town, a young man named Cornelius grew flowers. "
            "He dreamed of one impossible thing: a tulip as black as night. "
            "Every morning he checked the soil with hope in his heart."
        ),
        "text_ar": (
            "في بلدة هولندية صغيرة، كان شابٌّ اسمه كورنيليوس يزرع الأزهار. "
            "كان يحلم بشيء واحد يبدو مستحيلًا: زهرة توليب سوداء كالليل. "
            "كان يتفقّد التربة كل صباح والأمل يملأ قلبه."
        ),
        "arabic_summary": (
            "يقدّم هذا المقطع كورنيليوس الشاب الذي يحلم بزراعة زهرة توليب سوداء نادرة، "
            "ويزرع فيه الأملَ والإصرار."
        ),
        "vocab": [
            {"word": "rare", "meaning_ar": "نادر", "explanation_ar": "شيء قليل الوجود ويصعب إيجاده.", "example_sentence": "A black tulip is very rare."},
            {"word": "dreamed", "meaning_ar": "حَلَمَ", "explanation_ar": "تمنّى شيئًا بقوة.", "example_sentence": "He dreamed of a black tulip."},
            {"word": "soil", "meaning_ar": "التُّربة", "explanation_ar": "الأرض التي تنمو فيها النباتات."},
        ],
    },
    {
        "order": 2,
        "title": "A Jealous Neighbor",
        "text_en": (
            "His neighbor, Isaac, also wanted to grow the black tulip. "
            "But Isaac was jealous, and jealousy made his heart cold. "
            "He watched Cornelius work and planned to take his prize."
        ),
        "text_ar": (
            "كان جاره إسحاق يريد أيضًا أن يزرع التوليب الأسود. "
            "لكنّ إسحاق كان يشعر بالغيرة، والغيرة جعلت قلبه باردًا. "
            "راقب كورنيليوس وهو يعمل، ودبّر أن يسرق جائزته."
        ),
        "arabic_summary": (
            "يظهر هنا الصراع: الجار الغيور إسحاق يخطّط لأخذ زهرة كورنيليوس، "
            "وهي عقدة القصة."
        ),
        "vocab": [
            {"word": "jealous", "meaning_ar": "غيور", "explanation_ar": "يشعر بالغيرة من نجاح غيره.", "example_sentence": "Isaac was jealous of his neighbor."},
            {"word": "neighbor", "meaning_ar": "جار", "explanation_ar": "الشخص الذي يسكن قريبًا منك."},
            {"word": "prize", "meaning_ar": "جائزة", "explanation_ar": "مكافأة تُمنح للفائز."},
        ],
    },
    {
        "order": 3,
        "title": "The Prison",
        "text_en": (
            "One night, soldiers came and took Cornelius to prison. "
            "He was afraid, but he hid three small tulip bulbs in his coat. "
            "Even behind cold walls, he did not lose hope."
        ),
        "text_ar": (
            "في إحدى الليالي جاء الجنود وأخذوا كورنيليوس إلى السجن. "
            "كان خائفًا، لكنّه أخفى ثلاث بصلات صغيرة من التوليب في معطفه. "
            "وحتى خلف الجدران الباردة، لم يفقد الأمل."
        ),
        "arabic_summary": (
            "يصل كورنيليوس إلى السجن لكنه يحافظ على بصلات الزهرة وعلى أمله، "
            "وهي لحظة المحنة والصبر."
        ),
        "vocab": [
            {"word": "prison", "meaning_ar": "سِجن", "explanation_ar": "مكان يُحبس فيه الناس."},
            {"word": "afraid", "meaning_ar": "خائف", "explanation_ar": "يشعر بالخوف.", "example_sentence": "He was afraid of the dark."},
            {"word": "hope", "meaning_ar": "أمل", "explanation_ar": "الشعور بأنّ الخير سيأتي."},
        ],
    },
    {
        "order": 4,
        "title": "Courage Wins",
        "text_en": (
            "A kind girl named Rosa helped him care for the bulbs in secret. "
            "With courage and patience, the black tulip finally bloomed. "
            "Cornelius learned that hope is stronger than any wall."
        ),
        "text_ar": (
            "ساعدته فتاة طيبة اسمها روزا على رعاية البصلات في الخفاء. "
            "وبالشجاعة والصبر، تفتّحت زهرة التوليب السوداء أخيرًا. "
            "وتعلّم كورنيليوس أنّ الأمل أقوى من أي جدار."
        ),
        "arabic_summary": (
            "تنتصر الشجاعة والصبر: تتفتّح الزهرة بمساعدة روزا، "
            "وتكون الخاتمة درسًا في قوة الأمل."
        ),
        "vocab": [
            {"word": "courage", "meaning_ar": "شجاعة", "explanation_ar": "القوة على مواجهة الخوف.", "example_sentence": "Courage helped him win."},
            {"word": "patience", "meaning_ar": "صبر", "explanation_ar": "القدرة على الانتظار بهدوء."},
            {"word": "bloomed", "meaning_ar": "تفتّحت", "explanation_ar": "فتحت الزهرة بتلاتها."},
        ],
    },
]


class Command(BaseCommand):
    help = "Seed a short, copyright-safe demo novel for the Interactive Novel Reader."

    @transaction.atomic
    def handle(self, *args, **options):
        book, _ = Book.objects.update_or_create(
            title=BOOK_TITLE,
            defaults={
                "author": "Onlenco (adapted, original demo)",
                "category": "novel",
                "level": "A2",
                "summary": (
                    "A short, original demo story inspired by the public-domain theme "
                    "of 'The Black Tulip'. Written for Onlenco — not a copy of any edition."
                ),
                "is_published": True,
                "copyright_status": "adapted_original",
                "is_copyright_cleared": True,
                "source_title": "Inspired by 'The Black Tulip' (public-domain theme only)",
                "source_url": "",
                "license_notes": (
                    "Original Onlenco-written demo text. No source passages reproduced; "
                    "no PDF or school edition imported."
                ),
                "content_language": "en",
                "target_cefr_level": "A2",
                "is_school_curriculum": True,
                "school_country": "Sudan",
                "school_stage": "Secondary",
                "curriculum_notes": "Demo title for the Interactive Novel Reader (19.0C).",
            },
        )

        chapter, _ = Chapter.objects.update_or_create(
            book=book, sort_order=1,
            defaults={"title": "Chapter One — The Black Tulip", "body": "See reader segments."},
        )

        seg_count = 0
        vocab_count = 0
        for data in SEGMENTS:
            segment, _ = NovelSegment.objects.update_or_create(
                chapter=chapter, order=data["order"],
                defaults={
                    "title": data["title"],
                    "text_en": data["text_en"],
                    "text_ar": data["text_ar"],
                    "arabic_summary": data["arabic_summary"],
                    "cefr_level": "A2",
                    "estimated_reading_seconds": 40,
                    "estimated_audio_seconds": 35,
                    "is_published": True,
                },
            )
            seg_count += 1
            for i, v in enumerate(data["vocab"], start=1):
                NovelVocabularyHighlight.objects.update_or_create(
                    segment=segment, word=v["word"],
                    defaults={
                        "meaning_ar": v["meaning_ar"],
                        "explanation_ar": v.get("explanation_ar", ""),
                        "example_sentence": v.get("example_sentence", ""),
                        "cefr_level": "A2",
                        "order": i,
                        "is_active": True,
                    },
                )
                vocab_count += 1

        # One illustration row in needs_review (NO file) — demonstrates the
        # approval gate; it must never be student-visible until approved+file.
        first_segment = NovelSegment.objects.filter(chapter=chapter, order=1).first()
        if first_segment is not None:
            NovelIllustration.objects.update_or_create(
                segment=first_segment, order=1,
                defaults={
                    "description": "A single black tulip in a Dutch garden (placeholder brief).",
                    "alt_text": "A black tulip",
                    "generation_status": "needs_review",
                },
            )

        self.stdout.write(self.style.SUCCESS(
            f"[OK] Demo novel ready — book='{book.title}', "
            f"chapter=1, segments={seg_count}, vocabulary={vocab_count}. "
            f"No PDF imported, no media generated."
        ))
        self.stdout.write(
            f"     Read it at: /library/chapters/{chapter.pk}/reader/"
        )

"""Seed a demo lesson with one question per registered question type.

The lesson lives in a dedicated "Challenge Demo" course (auto-created
on first run) so it never collides with curriculum lessons. Re-running
the command refreshes the questions in place — it's fully idempotent.

All content is **Onlenco-original** (no reuse from EFE, Duolingo or any
specific publication). Characters: Amani, Yusuf, Noor, Kareem, Salma,
Omar, Layla, Tarek, Hala, Rashid.

Usage:
    python manage.py seed_challenge_question_types_demo
    python manage.py seed_challenge_question_types_demo --clear
"""
from __future__ import annotations

from django.core.management.base import BaseCommand
from django.db import transaction

from courses.models import (
    Course, CourseLevel, CourseUnit, Lesson, LessonQuestion, LessonQuiz,
)
from courses.services import question_type_registry as registry


COURSE_SLUG = "onlenco-challenge-demo"
COURSE_TITLE_EN = "Onlenco Challenge — All Question Types Demo"
COURSE_TITLE_AR = "تجربة التحدي — كل أنواع الأسئلة"
LESSON_TITLE_EN = "Challenge Types Showcase"
LESSON_TITLE_AR = "عرض كل أنواع التحدي"
UNIT_TITLE_EN = "Question Types"
UNIT_TITLE_AR = "أنواع الأسئلة"


# ---------------------------------------------------------------------------
# Original Onlenco content — one card per launch type.
# Order matches the registry's intended flow (easy → hard → speaking).
# ---------------------------------------------------------------------------

def _build_questions() -> list[dict]:
    return [
        # 1. tap_choice
        {
            "order": 1,
            "question_type": "tap_choice",
            "question_text": "Amani says: \"This is my brother, Yusuf.\" Who is Yusuf?",
            "question_text_ar": "أماني تقول: «هذا أخي يوسف.» من يوسف؟",
            "metadata": {
                "options": [
                    {"id": "a", "text": "Amani's brother", "text_ar": "أخو أماني"},
                    {"id": "b", "text": "Amani's friend",  "text_ar": "صديق أماني"},
                    {"id": "c", "text": "Amani's father",  "text_ar": "والد أماني"},
                ],
                "correct_option_id": "a",
            },
            "correct_answer": "a",
        },
        # 2. image_choice
        {
            "order": 2,
            "question_type": "image_choice",
            "question_text": "Tap the picture that shows 'a window'.",
            "question_text_ar": "اضغط الصورة التي تعرض «نافذة».",
            "metadata": {
                "options": [
                    {"id": "a", "text": "window", "image_url": "", "text_ar": "نافذة"},
                    {"id": "b", "text": "door",   "image_url": "", "text_ar": "باب"},
                    {"id": "c", "text": "table",  "image_url": "", "text_ar": "طاولة"},
                    {"id": "d", "text": "chair",  "image_url": "", "text_ar": "كرسي"},
                ],
                "correct_option_id": "a",
            },
            "correct_answer": "a",
        },
        # 3. listen_and_choose
        {
            "order": 3,
            "question_type": "listen_and_choose",
            "question_text": "Listen. What did Noor say?",
            "question_text_ar": "استمع. ماذا قالت نور؟",
            "metadata": {
                "audio_script": "Noor: I work at a small clinic on Mondays.",
                "audio_url": "",
                "options": [
                    {"id": "a", "text": "She works on Mondays."},
                    {"id": "b", "text": "She works on Sundays."},
                    {"id": "c", "text": "She studies on Mondays."},
                ],
                "correct_option_id": "a",
            },
            "correct_answer": "a",
        },
        # 4. listen_and_type
        {
            "order": 4,
            "question_type": "listen_and_type",
            "question_text": "Listen and type what Kareem says.",
            "question_text_ar": "استمع واكتب ما يقوله كريم.",
            "metadata": {
                "audio_script": "Kareem: I drink coffee every morning.",
                "audio_url": "",
                "correct_answer": "I drink coffee every morning.",
            },
            "correct_answer": "I drink coffee every morning.",
        },
        # 5. sound_to_word
        {
            "order": 5,
            "question_type": "sound_to_word",
            "question_text": "You will hear one word. Pick it.",
            "question_text_ar": "ستسمع كلمة واحدة. اخترها.",
            "metadata": {
                "audio_script": "thirteen",
                "audio_url": "",
                "options": [
                    {"id": "a", "text": "thirty"},
                    {"id": "b", "text": "thirteen"},
                    {"id": "c", "text": "thirsty"},
                ],
                "correct_option_id": "b",
            },
            "correct_answer": "b",
        },
        # 6. picture_labeling
        {
            "order": 6,
            "question_type": "picture_labeling",
            "question_text": "Type what Salma is holding in the picture.",
            "question_text_ar": "اكتب ما تحمله سلمى في الصورة.",
            "metadata": {
                "image_prompt": "Salma at a market holding a clear glass of water with both hands.",
                "image_url": "",
                "accepted_answers": ["water", "a glass of water", "glass of water"],
            },
            "correct_answer": "water",
        },
        # 7. mini_story_choice
        {
            "order": 7,
            "question_type": "mini_story_choice",
            "question_text": "Read Omar's morning, then answer.",
            "question_text_ar": "اقرأ صباح عمر ثم أجب.",
            "metadata": {
                "story": [
                    "Omar wakes up at six.",
                    "He has bread and tea.",
                    "Then he walks to the bus stop.",
                ],
                "options": [
                    {"id": "a", "text": "What does Omar drink? — Tea."},
                    {"id": "b", "text": "What does Omar drink? — Juice."},
                    {"id": "c", "text": "What does Omar drink? — Milk."},
                ],
                "correct_option_id": "a",
            },
            "correct_answer": "a",
        },
        # 8. word_bank_sentence
        {
            "order": 8,
            "question_type": "word_bank_sentence",
            "question_text": "Build the sentence about Layla.",
            "question_text_ar": "ابنِ الجملة عن ليلى.",
            "metadata": {
                "word_bank": ["Layla", "is", "a", "teacher", "at", "the", "school"],
                "correct_order": ["Layla", "is", "a", "teacher", "at", "the", "school"],
            },
            "correct_answer": "Layla is a teacher at the school",
        },
        # 9. match_pairs
        {
            "order": 9,
            "question_type": "match_pairs",
            "question_text": "Match each person to their job.",
            "question_text_ar": "طابق كل شخص بمهنته.",
            "metadata": {
                "pairs": [
                    {"left": "Noor",   "right": "nurse"},
                    {"left": "Tarek",  "right": "driver"},
                    {"left": "Hala",   "right": "engineer"},
                    {"left": "Rashid", "right": "baker"},
                ],
            },
            "correct_answer": "see pairs",
        },
        # 10. fill_blank_card
        {
            "order": 10,
            "question_type": "fill_blank_card",
            "question_text": "Amani ___ from Cairo.",
            "question_text_ar": "أماني ___ من القاهرة.",
            "metadata": {
                "sentence_with_blank": "Amani ___ from Cairo.",
                "word_choices": ["am", "is", "are"],
            },
            "correct_answer": "is",
        },
        # 11. conversation_reply
        {
            "order": 11,
            "question_type": "conversation_reply",
            "question_text": "Pick Yusuf's natural reply.",
            "question_text_ar": "اختر رد يوسف الطبيعي.",
            "metadata": {
                "dialogue": [
                    {"side": "left",  "speaker": "Amani", "text": "Yusuf, where are you going?"},
                ],
                "options": [
                    {"id": "a", "text": "I'm going to the library."},
                    {"id": "b", "text": "Yes, please."},
                    {"id": "c", "text": "I am eleven years old."},
                ],
                "correct_option_id": "a",
            },
            "correct_answer": "a",
        },
        # 12. frequency_scale (single-target shape)
        {
            "order": 12,
            "question_type": "frequency_scale",
            "question_text": "Place the word 'often' on the frequency scale.",
            "question_text_ar": "ضع كلمة often على مقياس التكرار.",
            "metadata": {
                "scale": [
                    {"label": "never", "percent": 0},
                    {"label": "rarely", "percent": 15},
                    {"label": "sometimes", "percent": 40},
                    {"label": "often", "percent": 65},
                    {"label": "usually", "percent": 85},
                    {"label": "always", "percent": 100},
                ],
                "target": {"label": "often", "percent": 65},
                "tolerance": 10,
            },
            "correct_answer": "65",
        },
        # 13. table_sentence_builder
        {
            "order": 13,
            "question_type": "table_sentence_builder",
            "question_text": "Pick one cell from each column to build a true sentence about Hala.",
            "question_text_ar": "اختر خانة من كل عمود لتكوّن جملة صحيحة عن هالة.",
            "metadata": {
                "columns": [
                    {"label": "Subject", "values": ["Hala", "Rashid"]},
                    {"label": "Verb",    "values": ["drinks", "drink"]},
                    {"label": "Object",  "values": ["tea", "coffee"]},
                ],
                "valid_sentences": ["Hala drinks tea", "Hala drinks coffee",
                                    "Rashid drinks tea", "Rashid drinks coffee"],
            },
            "correct_answer": "Hala drinks tea",
        },
        # 14. question_transform
        {
            "order": 14,
            "question_type": "question_transform",
            "question_text": "Make a Wh-question from the sentence.",
            "question_text_ar": "حوّل الجملة إلى سؤال بأداة استفهام.",
            "metadata": {
                "statement": "Tarek drives a yellow taxi.",
                "target_qword": "What",
                "accepted_answers": [
                    "What does Tarek drive?",
                    "What does Tarek drive",
                ],
            },
            "correct_answer": "What does Tarek drive?",
        },
        # 15. mistake_correction
        {
            "order": 15,
            "question_type": "mistake_correction",
            "question_text": "Fix the sentence.",
            "question_text_ar": "صحّح الجملة.",
            "metadata": {
                "wrong_sentence": "Salma don't likes apples.",
                "corrected_sentence": "Salma doesn't like apples.",
                "hint_en": "Use 'doesn't' with he/she/it + base verb.",
                "accepted_answers": [
                    "Salma doesn't like apples.",
                    "Salma does not like apples.",
                ],
            },
            "correct_answer": "Salma doesn't like apples.",
        },
        # 16. translate_to_english
        {
            "order": 16,
            "question_type": "translate_to_english",
            "question_text": "Translate this sentence about Noor to English.",
            "question_text_ar": "ترجم هذه الجملة عن نور إلى الإنجليزية.",
            "metadata": {
                "source_ar": "نور تعمل في عيادة صغيرة.",
                "accepted_answers": [
                    "Noor works at a small clinic.",
                    "Noor works in a small clinic.",
                ],
            },
            "correct_answer": "Noor works at a small clinic.",
        },
        # 17. translate_to_arabic
        {
            "order": 17,
            "question_type": "translate_to_arabic",
            "question_text": "Pick the correct Arabic translation.",
            "question_text_ar": "اختر الترجمة العربية الصحيحة.",
            "metadata": {
                "source_en": "Kareem reads a book every night.",
                "options": [
                    {"id": "a", "text": "كريم يقرأ كتاباً كل ليلة."},
                    {"id": "b", "text": "كريم يكتب كتاباً كل ليلة."},
                    {"id": "c", "text": "كريم يحب الكتب القديمة."},
                ],
                "correct_option_id": "a",
            },
            "correct_answer": "a",
        },
        # 18. speak_this_sentence (placeholder)
        {
            "order": 18,
            "question_type": "speak_this_sentence",
            "question_text": "Read this sentence about Layla out loud.",
            "question_text_ar": "اقرأ هذه الجملة عن ليلى بصوت مرتفع.",
            "metadata": {
                "sentence": "Layla teaches English on Tuesday and Thursday.",
            },
            "correct_answer": "",
        },
        # 19. pronunciation_check (placeholder)
        {
            "order": 19,
            "question_type": "pronunciation_check",
            "question_text": "Practice the difficult sound. Say it slowly, then quickly.",
            "question_text_ar": "تدرّب على الصوت الصعب. قُلها ببطء ثم بسرعة.",
            "metadata": {
                "target_word": "thirteen",
                "ipa": "ˌθɜːrˈtiːn",
            },
            "correct_answer": "",
        },
        # 20. ai_roleplay_prompt (placeholder)
        {
            "order": 20,
            "question_type": "ai_roleplay_prompt",
            "question_text": "Roleplay: You are at a bakery. Order two loaves of bread from Rashid.",
            "question_text_ar": "تمثيل: أنت في مخبزة. اطلب من رشيد رغيفين من الخبز.",
            "metadata": {
                "scenario": "You walk into Rashid's bakery and need two loaves of bread.",
                "starter_line": "Hi Rashid, can I have ...",
                "target_phrases": ["two loaves", "please", "thank you"],
            },
            "correct_answer": "",
        },
    ]


# ---------------------------------------------------------------------------
# Seeder
# ---------------------------------------------------------------------------

class Command(BaseCommand):
    help = "Seed a demo lesson with one question per registered question type."

    def add_arguments(self, parser):
        parser.add_argument(
            "--clear", action="store_true",
            help="Delete the demo course's existing questions before seeding.",
        )

    @transaction.atomic
    def handle(self, *args, **options):
        level = CourseLevel.objects.filter(code="A0").first()
        if level is None:
            self.stderr.write(self.style.ERROR(
                "CourseLevel A0 is missing. Run `seed_course_levels` first."
            ))
            return

        course, created = Course.objects.get_or_create(
            slug=COURSE_SLUG,
            defaults={
                "title":    COURSE_TITLE_EN,
                "title_en": COURSE_TITLE_EN,
                "title_ar": COURSE_TITLE_AR,
                "level":    level,
                "language": "bilingual",
                "status":   "published",
                "is_free":  True,
                "is_active": True,
                "drip_enabled": False,
            },
        )
        if created:
            self.stdout.write(self.style.SUCCESS(f"[+] Created course '{COURSE_TITLE_EN}'"))

        unit, _ = CourseUnit.objects.get_or_create(
            course=course, order=1,
            defaults={
                "title":    UNIT_TITLE_EN,
                "title_en": UNIT_TITLE_EN,
                "title_ar": UNIT_TITLE_AR,
            },
        )

        lesson, _ = Lesson.objects.get_or_create(
            course=course, unit=unit, order=1,
            defaults={
                "title":      LESSON_TITLE_EN,
                "title_en":   LESSON_TITLE_EN,
                "title_ar":   LESSON_TITLE_AR,
                "lesson_type": "mixed",
                "cefr_level": "A0",
                "status":     "published",
                "is_active":  True,
                "content_html": "<p>A showcase of the 20 Challenge question types.</p>",
            },
        )

        quiz, _ = LessonQuiz.objects.get_or_create(
            lesson=lesson,
            defaults={
                "title":    "Challenge Types Showcase Quiz",
                "title_en": "Challenge Types Showcase Quiz",
                "title_ar": "اختبار عرض أنواع التحدي",
                "passing_score": 70,
                "is_active": True,
            },
        )

        if options["clear"]:
            deleted, _ = quiz.questions.all().delete()
            self.stdout.write(f"[-] Cleared {deleted} prior questions.")

        questions = _build_questions()
        created_count, updated_count = 0, 0
        for q in questions:
            assert registry.is_known(q["question_type"]), (
                f"{q['question_type']} is not in the registry"
            )
            obj, was_new = LessonQuestion.objects.update_or_create(
                quiz=quiz, order=q["order"],
                defaults={
                    "question_type":    q["question_type"],
                    "question_text":    q["question_text"],
                    "question_text_en": q["question_text"],
                    "question_text_ar": q.get("question_text_ar", ""),
                    "options":          q.get("options", []) or [],
                    "metadata":         q.get("metadata", {}),
                    "correct_answer":   q.get("correct_answer", ""),
                    "difficulty_score": 0.5,
                    "points":           1,
                },
            )
            created_count += int(was_new)
            updated_count += int(not was_new)

        self.stdout.write(self.style.SUCCESS(
            f"[OK] Lesson '{lesson.title}' — "
            f"{created_count} created, {updated_count} updated, "
            f"{quiz.questions.count()} total."
        ))
        self.stdout.write(
            f"     Play it at: /courses/{course.pk}/lessons/{lesson.pk}/challenge/start/"
        )

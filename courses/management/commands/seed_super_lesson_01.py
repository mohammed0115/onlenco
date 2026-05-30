"""Seed the Onlenco Beginner "Super Lesson 01 — Introducing Yourself".

This is the **gold reference** lesson — the model every other Topic
will follow once Prompt 09 reviews it. Everything below is original
Onlenco content (no copying from EFE, Duolingo, or any other source).

Includes:
  * Course (idempotent get_or_create on slug "onlenco-beginner")
  * Unit + Lesson 01 (idempotent update_or_create)
  * `content_html` (sectioned, EN) + `content_ar` (Arabic walk-through)
  * 5 LessonChecklist items (EN + AR)
  * 4 LessonImagePrompt rows (cover / vocabulary / grammar / quiz)
  * 6 LessonAudioScript rows (intro / vocabulary / examples / dialogue
    / listening / speaking)
  * LessonQuiz + 10 LessonQuestion (one per Phase-3 type) — wired with
    `metadata["skills"]` so Phase-6 mastery flows automatically.

Cast (Phase 2 spec): Amani, Yusuf, Noor, Kareem, Salma, Omar, Layla,
Tarek, Hala, Rashid. American English. Beginner-friendly.

Usage:
    python manage.py seed_super_lesson_01
    python manage.py seed_super_lesson_01 --reseed   # drop & rebuild Q's
"""
from __future__ import annotations

from django.core.management.base import BaseCommand
from django.db import transaction

from courses.models import (
    Course, CourseLevel, CourseUnit, Lesson, LessonAudioScript,
    LessonChecklist, LessonImagePrompt, LessonQuestion, LessonQuiz,
)


COURSE_SLUG  = "onlenco-beginner"
COURSE_TITLE = "Onlenco Beginner English Foundation"
COURSE_TITLE_AR = "أسس الإنجليزية للمبتدئين — Onlenco"
LESSON_TITLE    = "Introducing Yourself"
LESSON_TITLE_AR = "التعريف بنفسك"
UNIT_TITLE      = "Topic 01 — Introducing Yourself"


# ---------------------------------------------------------------------------
# Content (HTML) — sectioned, beginner-friendly, no inline styles.
# ---------------------------------------------------------------------------

CONTENT_HTML = """\
<section class="lesson-goal">
<h2>Lesson Goal</h2>
<p>By the end of this lesson, you will be able to say hello, share your name, ask for someone's name, and respond politely — in clear American English.</p>
</section>

<section class="new-language">
<h2>New Language</h2>
<ul>
  <li><strong>I am</strong> Amani.</li>
  <li><strong>I'm</strong> Amani.</li>
  <li><strong>My name is</strong> Yusuf.</li>
  <li><strong>What is your name?</strong></li>
  <li><strong>Nice to meet you.</strong></li>
</ul>
</section>

<section class="vocabulary">
<h2>Vocabulary</h2>
<ul>
  <li>hello</li>
  <li>hi</li>
  <li>name</li>
  <li>first name</li>
  <li>last name</li>
  <li>nice</li>
  <li>meet</li>
  <li>spell</li>
</ul>
</section>

<section class="key-language">
<h2>Key Language</h2>
<p>Use <strong>I am</strong> or its short form <strong>I'm</strong> to share your name.</p>
<p>Use <strong>What is your name?</strong> when you want to ask someone.</p>
</section>

<section class="how-to-form">
<h2>How to Form</h2>
<p>Subject + <strong>be</strong> + name → <em>I am Salma.</em></p>
<p>My name + <strong>is</strong> + name → <em>My name is Omar.</em></p>
<p>What + <strong>is</strong> + your + name? → <em>What is your name?</em></p>
</section>

<section class="visual-guide">
<h2>Visual Guide</h2>
<p>Picture two friendly beginners meeting for the first time. One waves, the other smiles. They each say their name slowly so the other can hear.</p>
</section>

<section class="mini-dialogue">
<h2>Mini Dialogue</h2>
<p><strong>Amani:</strong> Hello. My name is Amani.</p>
<p><strong>Yusuf:</strong> Hi Amani. I'm Yusuf.</p>
<p><strong>Amani:</strong> Nice to meet you.</p>
<p><strong>Yusuf:</strong> Nice to meet you too.</p>
</section>

<section class="listening-practice">
<h2>Listening Practice</h2>
<p>Listen carefully. The speaker says her name slowly. Can you catch it?</p>
<p><em>"Hello. My name is Sara."</em></p>
</section>

<section class="speaking-practice">
<h2>Speaking Practice</h2>
<p>Say this out loud. Once slowly, once at normal speed:</p>
<p><strong>Hello. My name is Omar. Nice to meet you.</strong></p>
</section>

<section class="ai-tutor-drill">
<h2>AI Tutor Drill</h2>
<p>Open the short roleplay inside the Challenge. The tutor will say hello and ask your name. Reply naturally — three to five short turns is enough.</p>
</section>

<section class="checklist">
<h2>Checklist</h2>
<p>Tick what you can do before you continue.</p>
</section>
"""


# Arabic walkthrough — beginner-friendly, mirrors the EN flow.
CONTENT_AR = """\
<section class="lesson-goal" dir="rtl">
<h2>هدف الدرس</h2>
<p>بنهاية هذا الدرس ستستطيع: قول مرحباً، ذكر اسمك، سؤال شخص عن اسمه، والرد بأدب — كل ذلك باللهجة الأمريكية الواضحة.</p>
</section>

<section class="new-language" dir="rtl">
<h2>اللغة الجديدة</h2>
<ul>
  <li><strong>I am</strong> Amani — اسمي أماني.</li>
  <li><strong>I'm</strong> Amani — صيغة مختصرة.</li>
  <li><strong>My name is</strong> Yusuf — اسمي يوسف.</li>
  <li><strong>What is your name?</strong> — ما اسمك؟</li>
  <li><strong>Nice to meet you.</strong> — تشرّفنا.</li>
</ul>
</section>

<section class="vocabulary" dir="rtl">
<h2>المفردات</h2>
<ul>
  <li>hello / hi — مرحباً.</li>
  <li>name — اسم.</li>
  <li>first name — الاسم الأول.</li>
  <li>last name — اسم العائلة.</li>
  <li>nice — لطيف.</li>
  <li>meet — يقابل.</li>
  <li>spell — يهجّئ.</li>
</ul>
</section>

<section class="key-language" dir="rtl">
<h2>التراكيب الأساسية</h2>
<p>استخدم <strong>I am</strong> أو الصيغة المختصرة <strong>I'm</strong> لتقول اسمك.</p>
<p>استخدم <strong>What is your name?</strong> لتسأل شخصاً.</p>
</section>

<section class="how-to-form" dir="rtl">
<h2>كيف نُكوّن الجملة</h2>
<p>الفاعل + <strong>be</strong> + الاسم → <em>I am Salma.</em></p>
<p>My name + <strong>is</strong> + الاسم → <em>My name is Omar.</em></p>
<p>What + <strong>is</strong> + your + name? → <em>What is your name?</em></p>
</section>

<section class="visual-guide" dir="rtl">
<h2>الدليل البصري</h2>
<p>ستظهر هنا صورة تعليمية تساعدك على فهم الموقف: شخصان يتعارفان ويتبادلان التحية بأسلوب لطيف.</p>
</section>

<section class="mini-dialogue" dir="rtl">
<h2>الحوار القصير</h2>
<p>أماني تقول: <em>Hello. My name is Amani.</em></p>
<p>يوسف يرد: <em>Hi Amani. I'm Yusuf.</em></p>
<p>أماني: <em>Nice to meet you.</em></p>
<p>يوسف: <em>Nice to meet you too.</em></p>
</section>

<section class="listening-practice" dir="rtl">
<h2>تدريب الاستماع</h2>
<p>استمع للجملة القصيرة وحاول تمييز الاسم. مثال: <em>«Hello. My name is Sara.»</em></p>
</section>

<section class="speaking-practice" dir="rtl">
<h2>تدريب المحادثة</h2>
<p>تدرّب على قول الجملة بصوتٍ مرتفع: <em>Hello. My name is Omar. Nice to meet you.</em></p>
<p>قُلها مرة ببطء، ومرة بسرعة طبيعية.</p>
</section>

<section class="ai-tutor-drill" dir="rtl">
<h2>تمرين مع المعلم الذكي</h2>
<p>سيتدرّب معك المعلم الذكي على التعارف: سيُلقي التحية ويسألك عن اسمك. أجبه بطريقة طبيعية، ثلاث إلى خمس دورات حوار قصيرة كافية.</p>
</section>

<section class="checklist" dir="rtl">
<h2>قائمة المراجعة</h2>
<p>ضع علامة على ما تستطيع فعله قبل أن تُكمل.</p>
</section>
"""


# ---------------------------------------------------------------------------
# Image prompts (NO image files generated — text only, ready for Phase 9).
# ---------------------------------------------------------------------------

IMAGE_PROMPTS = [
    ("cover",
     "Modern friendly educational cartoon illustration for an English beginner "
     "lesson titled 'Introducing Yourself'. Two adult learners are smiling and "
     "introducing themselves to each other. Soft blue and white background, "
     "clean vector style, simple speech bubbles with 'Hello' and 'My name "
     "is...'. No logos, no copyrighted characters, no real brand styling."),
    ("vocabulary",
     "A clean vocabulary card set for beginner English words: hello, name, "
     "first name, last name, nice to meet you. Friendly flat illustration, "
     "clear icons, soft pastel colors, white background, generous spacing. "
     "No real-world brand logos, no copyrighted mascots."),
    ("grammar",
     "A simple, supportive infographic showing the 'to be' verb with names: "
     "I am Amani, I'm Amani, My name is Yusuf, What is your name? Modern "
     "minimalist style, soft blue accent, no logos."),
    ("quiz",
     "A small supportive illustration for a language-learning challenge "
     "about introducing yourself. One learner speaks confidently with a "
     "small microphone icon, plus soft encouraging visual elements (sparkles "
     "and a checkmark). No real branded characters, no copyrighted assets."),
]


# ---------------------------------------------------------------------------
# Audio scripts (NO MP3 generation — script text only).
# ---------------------------------------------------------------------------

AUDIO_SCRIPTS = [
    ("intro", "friendly_teacher", 1,
     "Welcome. In this lesson, you will learn how to say hello and "
     "introduce yourself in clear American English."),
    ("vocabulary", "slow_beginner", 2,
     "Hello. Hi. Name. First name. Last name. Nice to meet you."),
    ("examples", "friendly_teacher", 3,
     "I am Amani. I'm Amani. My name is Yusuf. What is your name?"),
    ("dialogue", "dialogue", 4,
     "Amani: Hello. My name is Amani.\n"
     "Yusuf: Hi Amani. I'm Yusuf.\n"
     "Amani: Nice to meet you.\n"
     "Yusuf: Nice to meet you too."),
    ("listening", "slow_beginner", 5,
     "Hello. My name is Sara."),
    ("speaking", "friendly_teacher", 6,
     "Hello. My name is Omar. Nice to meet you."),
]


# ---------------------------------------------------------------------------
# Checklist (5 can-do statements).
# ---------------------------------------------------------------------------

CHECKLIST = [
    (1, "I can say hello.",                            "أستطيع قول مرحباً."),
    (2, "I can say my name.",                          "أستطيع قول اسمي."),
    (3, "I can ask 'What is your name?'",              "أستطيع سؤال شخص عن اسمه."),
    (4, "I can say 'Nice to meet you.'",               "أستطيع قول تشرّفنا."),
    (5, "I can spell my name slowly.",                 "أستطيع تهجئة اسمي ببطء."),
]


# ---------------------------------------------------------------------------
# 10-question Challenge sequence (one per Phase-3 type where it fits).
# ---------------------------------------------------------------------------

def _challenge_questions() -> list[dict]:
    return [
        # 1. tap_choice — meaning lookup
        {
            "order": 1,
            "question_type": "tap_choice",
            "question_text":    "What does \"Hello\" mean in Arabic?",
            "question_text_ar": "ما معنى كلمة Hello بالعربية؟",
            "metadata": {
                "skills": ["greetings"],
                "options": [
                    {"id": "a", "text": "مرحباً"},
                    {"id": "b", "text": "شكراً"},
                    {"id": "c", "text": "وداعاً"},
                    {"id": "d", "text": "كتاب"},
                ],
                "correct_option_id": "a",
            },
            "correct_answer": "a",
            "difficulty_score": 0.1,
        },
        # 2. listen_and_choose — listening with name extraction
        {
            "order": 2,
            "question_type": "listen_and_choose",
            "question_text":    "Listen. What name do you hear?",
            "question_text_ar": "استمع. ما الاسم الذي تسمعه؟",
            "metadata": {
                "skills": ["listening_basic", "spelling_names"],
                "audio_script": "Hello. My name is Sara.",
                "audio_url": "",                    # pending generation
                "audio_status": "pending_generation",
                "options": [
                    {"id": "a", "text": "Sara"},
                    {"id": "b", "text": "Amani"},
                    {"id": "c", "text": "Yusuf"},
                    {"id": "d", "text": "Omar"},
                ],
                "correct_option_id": "a",
            },
            "correct_answer": "a",
            "difficulty_score": 0.2,
        },
        # 3. word_bank_sentence — grammar word order
        {
            "order": 3,
            "question_type": "word_bank_sentence",
            "question_text":    "Put the words in the correct order to introduce Amani.",
            "question_text_ar": "رتّب الكلمات لتقديم أماني.",
            "metadata": {
                "skills": ["to_be_names"],
                "word_bank":     ["My", "name", "is", "Amani"],
                "correct_order": ["My", "name", "is", "Amani"],
            },
            "correct_answer": "My name is Amani",
            "difficulty_score": 0.3,
        },
        # 4. fill_blank_card — fill the verb
        {
            "order": 4,
            "question_type": "fill_blank_card",
            "question_text":    "My name ___ Yusuf.",
            "question_text_ar": "اسمي ___ يوسف.",
            "metadata": {
                "skills": ["to_be_names"],
                "sentence_with_blank": "My name ___ Yusuf.",
                "word_choices": ["am", "is", "are"],
            },
            "correct_answer": "is",
            "difficulty_score": 0.3,
        },
        # 5. match_pairs — bilingual matching
        {
            "order": 5,
            "question_type": "match_pairs",
            "question_text":    "Match each English word to its Arabic meaning.",
            "question_text_ar": "طابق كل كلمة إنجليزية بمعناها العربي.",
            "metadata": {
                "skills": ["greetings"],
                "pairs": [
                    {"left": "hello",      "right": "مرحباً"},
                    {"left": "name",       "right": "اسم"},
                    {"left": "first name", "right": "الاسم الأول"},
                    {"left": "last name",  "right": "اسم العائلة"},
                ],
            },
            "correct_answer": "see pairs",
            "difficulty_score": 0.4,
        },
        # 6. conversation_reply — pick the natural reply
        {
            "order": 6,
            "question_type": "conversation_reply",
            "question_text":    "Noor says: \"Hi. My name is Noor.\" Choose the best reply.",
            "question_text_ar": "نور تقول: «مرحباً، اسمي نور.» اختر الرد المناسب.",
            "metadata": {
                "skills": ["speaking_intro"],
                "dialogue": [
                    {"side": "left", "speaker": "Noor",
                     "text": "Hi. My name is Noor."},
                ],
                "options": [
                    {"id": "a", "text": "Nice to meet you."},
                    {"id": "b", "text": "I eat rice."},
                    {"id": "c", "text": "This is a book."},
                    {"id": "d", "text": "It is blue."},
                ],
                "correct_option_id": "a",
            },
            "correct_answer": "a",
            "difficulty_score": 0.4,
        },
        # 7. image_choice — pick the right picture for "Hello"
        #    (Phase 9.5: replaced the original translate_to_english because
        #    productive translation is too hard for absolute A0 — the
        #    picture-recognition task fits the same skill slot but stays
        #    in the recognition band.)
        {
            "order": 7,
            "question_type": "image_choice",
            "question_text":    "Choose the picture that shows \"Hello.\"",
            "question_text_ar": "اختر الصورة التي تعني «Hello».",
            "metadata": {
                "skills": ["greetings"],
                "options": [
                    {"id": "a", "text": "person waving hello",
                     "text_ar": "شخص يلوّح بالتحية", "image_url": ""},
                    {"id": "b", "text": "a book",
                     "text_ar": "كتاب", "image_url": ""},
                    {"id": "c", "text": "a chair",
                     "text_ar": "كرسي", "image_url": ""},
                    {"id": "d", "text": "a car",
                     "text_ar": "سيارة", "image_url": ""},
                ],
                "correct_option_id": "a",
            },
            "correct_answer": "a",
            "difficulty_score": 0.3,
        },
        # 8. sound_to_word — pick the phrase you hear
        #    (Phase 9.5: replaced listen_and_type so the student picks
        #    among 4 short phrases instead of typing a full sentence —
        #    matches the A0 listening "recognise" stage.)
        {
            "order": 8,
            "question_type": "sound_to_word",
            "question_text":    "Listen. Which phrase do you hear?",
            "question_text_ar": "استمع. أي جملة تسمعها؟",
            "metadata": {
                "skills": ["listening_basic"],
                "audio_script": "My name is Layla.",
                "audio_url": "",
                "audio_status": "pending_generation",
                "options": [
                    {"id": "a", "text": "My name is Layla."},
                    {"id": "b", "text": "My name is Omar."},
                    {"id": "c", "text": "I have a book."},
                    {"id": "d", "text": "This is a chair."},
                ],
                "correct_option_id": "a",
            },
            "correct_answer": "a",
            "difficulty_score": 0.4,
        },
        # 9. speak_this_sentence — speaking placeholder
        {
            "order": 9,
            "question_type": "speak_this_sentence",
            "question_text":    "Say this introduction out loud.",
            "question_text_ar": "قُل هذا التقديم بصوت مرتفع.",
            "metadata": {
                "skills": ["speaking_intro", "pronunciation_basic"],
                "sentence": "Hello. My name is Amani.",
            },
            "correct_answer": "",
            "difficulty_score": 0.4,
        },
        # 10. ai_roleplay_prompt — short AI roleplay
        {
            "order": 10,
            "question_type": "ai_roleplay_prompt",
            "question_text":    "Practice a short introduction with the AI Tutor.",
            "question_text_ar": "تدرّب على تقديم قصير مع المعلم الذكي.",
            "metadata": {
                "skills": ["speaking_intro"],
                "scenario": "The AI says hello and asks your name. Greet "
                            "back, share your name, and finish with 'Nice "
                            "to meet you.'",
                "ai_instruction": "Greet the learner. Ask their name. Ask "
                                  "them to say 'Nice to meet you.' Keep it "
                                  "under 5 turns. Correct only one mistake "
                                  "if needed.",
                "starter_line": "Hi! What's your name?",
                "target_phrases": ["My name is", "Nice to meet you"],
            },
            "correct_answer": "",
            "difficulty_score": 0.4,
        },
    ]


# ---------------------------------------------------------------------------
# Command.
# ---------------------------------------------------------------------------

class Command(BaseCommand):
    help = "Seed the gold-reference Beginner Topic 01 — Introducing Yourself."

    def add_arguments(self, parser):
        parser.add_argument(
            "--reseed", action="store_true",
            help="Delete and recreate the 10 Challenge questions before seeding.",
        )

    @transaction.atomic
    def handle(self, *args, **options):
        # 1. Course
        level, _ = CourseLevel.objects.get_or_create(
            code="A0", defaults={"name": "Beginner — Pre-A1", "order": 0},
        )
        course, course_created = Course.objects.update_or_create(
            slug=COURSE_SLUG,
            defaults={
                "title":      COURSE_TITLE,
                "title_en":   COURSE_TITLE,
                "title_ar":   COURSE_TITLE_AR,
                "level":      level,
                "language":   "bilingual",
                "status":     "published",
                "is_free":    True,
                "is_active":  True,
                "drip_enabled": False,
            },
        )
        if course_created:
            self.stdout.write(self.style.SUCCESS(f"[+] Course created: {COURSE_TITLE}"))
        else:
            self.stdout.write(f"[=] Course updated: {COURSE_TITLE}")

        # 2. Unit
        unit, _ = CourseUnit.objects.update_or_create(
            course=course, order=1,
            defaults={
                "title":    UNIT_TITLE,
                "title_en": UNIT_TITLE,
            },
        )

        # 3. Lesson
        lesson, lesson_created = Lesson.objects.update_or_create(
            course=course, unit=unit, order=1,
            defaults={
                "title":            LESSON_TITLE,
                "title_en":         LESSON_TITLE,
                "title_ar":         LESSON_TITLE_AR,
                "lesson_type":      "mixed",
                "cefr_level":       "A0",
                "skill":            "speaking",
                "grammar_topic":    "to_be_names",
                "vocabulary_topic": "greetings",
                "content_html":     CONTENT_HTML,
                "content_en":       CONTENT_HTML,
                "content_ar":       CONTENT_AR,
                "duration_minutes": 8,
                "status":           "published",
                "is_active":        True,
            },
        )
        flag = "Created" if lesson_created else "Updated"
        self.stdout.write(self.style.SUCCESS(f"[+] Lesson {flag}: {LESSON_TITLE}"))

        # 4. Checklist — wipe existing then re-create (small, manageable).
        LessonChecklist.objects.filter(lesson=lesson).delete()
        for order, text_en, text_ar in CHECKLIST:
            LessonChecklist.objects.create(
                lesson=lesson, sort_order=order,
                text_en=text_en, text_ar=text_ar, is_active=True,
            )
        self.stdout.write(f"    · {len(CHECKLIST)} checklist items written")

        # 5. Image prompts — upsert by (lesson, prompt_type).
        for prompt_type, prompt in IMAGE_PROMPTS:
            LessonImagePrompt.objects.update_or_create(
                lesson=lesson, prompt_type=prompt_type,
                defaults={"prompt": prompt, "is_generated": False, "sort_order": 0},
            )
        self.stdout.write(f"    · {len(IMAGE_PROMPTS)} image prompts written")

        # 6. Audio scripts — upsert by (lesson, script_type).
        for script_type, voice_style, sort_order, script_text in AUDIO_SCRIPTS:
            LessonAudioScript.objects.update_or_create(
                lesson=lesson, script_type=script_type,
                defaults={
                    "script_text":  script_text,
                    "voice_style":  voice_style,
                    "accent":       "american",
                    "is_generated": False,
                    "sort_order":   sort_order,
                },
            )
        self.stdout.write(f"    · {len(AUDIO_SCRIPTS)} audio scripts written")

        # 7. Quiz + Questions
        quiz, _ = LessonQuiz.objects.update_or_create(
            lesson=lesson,
            defaults={
                "title":          "Super Challenge 01 — Introducing Yourself",
                "title_en":       "Super Challenge 01 — Introducing Yourself",
                "title_ar":       "تحدّي 01 — التعريف بنفسك",
                "passing_score":  70,
                "is_active":      True,
            },
        )

        if options["reseed"]:
            deleted, _ = quiz.questions.all().delete()
            self.stdout.write(f"    · cleared {deleted} prior questions")

        created_q, updated_q = 0, 0
        for q in _challenge_questions():
            obj, was_new = LessonQuestion.objects.update_or_create(
                quiz=quiz, order=q["order"],
                defaults={
                    "question_type":      q["question_type"],
                    "question_text":      q["question_text"],
                    "question_text_en":   q["question_text"],
                    "question_text_ar":   q.get("question_text_ar", ""),
                    "options":            [],   # metadata.options is the source
                    "metadata":           q["metadata"],
                    "correct_answer":     q.get("correct_answer", ""),
                    "difficulty_score":   q.get("difficulty_score", 0.5),
                    "points":             1,
                },
            )
            created_q += int(was_new)
            updated_q += int(not was_new)

        self.stdout.write(self.style.SUCCESS(
            f"[OK] Super Lesson 01 ready — "
            f"{quiz.questions.count()} questions ({created_q} new, {updated_q} updated)"
        ))
        self.stdout.write(
            f"     Play it at: /courses/{course.pk}/lessons/{lesson.pk}/"
        )

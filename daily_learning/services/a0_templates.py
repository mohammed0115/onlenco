"""Hand-curated bilingual A0 daily-learning templates.

A0 is Onlenco-internal (pre-CEFR-A1). AI is never used for A0 — content
here is reviewed by hand because tone and difficulty matter much more
than for higher levels.

Structure
---------
The catalog is organised into **5 units** mirroring the Onlenco A0
roadmap:

    Unit 1 — Hello English        (greetings, "my name is …")
    Unit 2 — About Me             (country, job, age, nationality)
    Unit 3 — Basic Objects        (book, pen, phone, table, chair, bag)
    Unit 4 — Simple Sentences     (this is …, I have …, I like …)
    Unit 5 — Daily Life           (I wake up, I eat, I drink, I go)

Each topic is a single "day" and emits exactly **6 items** in this
order — the canonical A0 daily shape:

    1. Simple word       (vocabulary — with optional image_url + audio_url)
    2. Simple sentence   (grammar_tip — the short example sentence)
    3. Listening         (read + repeat with optional audio_url)
    4. Speaking          (say the sentence)
    5. Small question    (quiz — multiple choice, 3 options)
    6. Encouragement     (motivation closer)

The picker rotates through the catalog deterministically per (user, date)
so a student never sees the same content two days running.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Iterable


# ---------------------------------------------------------------------------
# Unit catalog
# ---------------------------------------------------------------------------

UNIT_1_HELLO            = 1
UNIT_2_ABOUT_ME         = 2
UNIT_3_BASIC_OBJECTS    = 3
UNIT_4_SIMPLE_SENTENCES = 4
UNIT_5_DAILY_LIFE       = 5

UNIT_TITLES_EN = {
    1: "Hello English",
    2: "About Me",
    3: "Basic Objects",
    4: "Simple Sentences",
    5: "Daily Life",
}
UNIT_TITLES_AR = {
    1: "أهلاً بالإنجليزية",
    2: "تعريف عن نفسي",
    3: "أشياء أساسية",
    4: "جمل بسيطة",
    5: "الحياة اليومية",
}


@dataclass(frozen=True)
class A0Item:
    """One step inside an A0 topic. Maps 1:1 to a DailyLearningItem."""
    item_type: str
    title_en: str
    title_ar: str
    instructions_en: str
    instructions_ar: str
    content_text_en: str = ""
    content_text_ar: str = ""
    question_en: str = ""
    question_ar: str = ""
    options: tuple = ()
    options_ar: tuple = ()
    correct_answer: str = ""
    explanation_en: str = ""
    explanation_ar: str = ""
    image_url: str = ""
    audio_url: str = ""
    skill: str = "mixed"
    estimated_minutes: int = 2


@dataclass(frozen=True)
class A0Topic:
    """One day's lesson. Always 6 items end-to-end."""
    slug: str
    unit: int                        # 1..5
    title_en: str
    title_ar: str
    description_en: str
    description_ar: str
    target_word: str                 # The headline vocabulary item
    target_sentence: str             # The headline sentence
    items: tuple = field(default_factory=tuple)


# ---------------------------------------------------------------------------
# Helpers — build the 6-item lesson once instead of repeating boilerplate
# ---------------------------------------------------------------------------

def _build_lesson(
    *,
    slug: str,
    unit: int,
    word: str,
    word_ar: str,
    sentence: str,
    title_en: str,
    title_ar: str,
    description_en: str,
    description_ar: str,
    quiz_question: str,
    quiz_options: tuple,
    quiz_correct: str,
    quiz_explanation_en: str,
    quiz_explanation_ar: str,
    encouragement_en: str,
    encouragement_ar: str,
    image_url: str = "",
    audio_url_word: str = "",
    audio_url_sentence: str = "",
) -> A0Topic:
    """Assemble one full A0 lesson — 6 items in the required order."""
    items = (
        # 1) Simple word
        A0Item(
            item_type="vocabulary",
            title_en=f"Word of the day: {word}",
            title_ar=f"كلمة اليوم: {word}",
            instructions_en="Read the word out loud. Listen and repeat.",
            instructions_ar="اقرأ الكلمة بصوت عالٍ. استمع وكرّر.",
            content_text_en=f"{word} — {word_ar}",
            content_text_ar=f"{word} — {word_ar}",
            image_url=image_url,
            audio_url=audio_url_word,
            skill="vocabulary",
        ),
        # 2) Simple sentence (grammar_tip carries the short example)
        A0Item(
            item_type="grammar_tip",
            title_en="A simple sentence",
            title_ar="جملة بسيطة",
            instructions_en="Read this sentence slowly.",
            instructions_ar="اقرأ هذه الجملة ببطء.",
            content_text_en=sentence,
            content_text_ar=sentence,
            skill="grammar",
        ),
        # 3) Listening
        A0Item(
            item_type="listening",
            title_en="Listen and repeat",
            title_ar="استمع وكرّر",
            instructions_en="Listen, then say it three times.",
            instructions_ar="استمع ثم ردّدها ثلاث مرات.",
            content_text_en=sentence,
            content_text_ar=sentence,
            audio_url=audio_url_sentence,
            skill="listening",
        ),
        # 4) Speaking
        A0Item(
            item_type="speaking",
            title_en="Say it out loud",
            title_ar="انطقها بصوت عالٍ",
            instructions_en="Say the sentence twice. Speak slowly.",
            instructions_ar="انطق الجملة مرتين. تكلّم ببطء.",
            content_text_en=sentence,
            content_text_ar=sentence,
            audio_url=audio_url_sentence,
            skill="speaking",
            estimated_minutes=2,
        ),
        # 5) Small question (quiz)
        A0Item(
            item_type="quiz",
            title_en="Choose the right word",
            title_ar="اختر الكلمة الصحيحة",
            instructions_en="Pick the word that completes the sentence.",
            instructions_ar="اختر الكلمة التي تكمل الجملة.",
            question_en=quiz_question,
            question_ar=quiz_question,
            options=quiz_options,
            options_ar=quiz_options,
            correct_answer=quiz_correct,
            explanation_en=quiz_explanation_en,
            explanation_ar=quiz_explanation_ar,
            skill="grammar",
        ),
        # 6) Encouragement (motivation closer)
        A0Item(
            item_type="motivation",
            title_en="Great job!",
            title_ar="عمل رائع!",
            instructions_en="",
            instructions_ar="",
            content_text_en=encouragement_en,
            content_text_ar=encouragement_ar,
            skill="mixed",
            estimated_minutes=1,
        ),
    )
    return A0Topic(
        slug=slug,
        unit=unit,
        title_en=title_en,
        title_ar=title_ar,
        description_en=description_en,
        description_ar=description_ar,
        target_word=word,
        target_sentence=sentence,
        items=items,
    )


# ---------------------------------------------------------------------------
# 5 units × hand-curated lessons
# ---------------------------------------------------------------------------

A0_TOPICS: tuple[A0Topic, ...] = (
    # --- Unit 1: Hello English ---------------------------------------
    _build_lesson(
        slug="u1_hello",
        unit=UNIT_1_HELLO,
        word="hello", word_ar="مرحبا",
        sentence="Hello! How are you?",
        title_en="Greet someone in English",
        title_ar="ألقِ التحية بالإنجليزية",
        description_en="Learn how to say hello.",
        description_ar="تعلّم كيف تلقي التحية.",
        quiz_question="A: How are you?  B: ____",
        quiz_options=("I am fine, thank you.", "My name is Sara.", "I am from Egypt."),
        quiz_correct="I am fine, thank you.",
        quiz_explanation_en="\"How are you?\" asks about your feeling.",
        quiz_explanation_ar="\"How are you?\" يسأل عن شعورك.",
        encouragement_en="Great start! You said hello in English.",
        encouragement_ar="بداية رائعة! ألقيت التحية بالإنجليزية.",
    ),
    _build_lesson(
        slug="u1_name",
        unit=UNIT_1_HELLO,
        word="name", word_ar="اسم",
        sentence="My name is Ahmed.",
        title_en="Say your name",
        title_ar="قل اسمك",
        description_en="Tell someone your name in English.",
        description_ar="قل اسمك لشخص ما بالإنجليزية.",
        quiz_question="My name ____ Ahmed.",
        quiz_options=("is", "are", "am"),
        quiz_correct="is",
        quiz_explanation_en="We use \"is\" with he / she / it / a name.",
        quiz_explanation_ar="نستخدم \"is\" مع he / she / it أو مع اسم شخص.",
        encouragement_en="Excellent! You just introduced yourself.",
        encouragement_ar="ممتاز! لقد عرّفت عن نفسك للتو.",
    ),
    _build_lesson(
        slug="u1_good_morning",
        unit=UNIT_1_HELLO,
        word="morning", word_ar="صباح",
        sentence="Good morning!",
        title_en="Say good morning",
        title_ar="قل صباح الخير",
        description_en="A friendly morning greeting.",
        description_ar="تحية صباحية ودية.",
        quiz_question="In the morning we say: ____",
        quiz_options=("Good morning!", "Good night!", "Goodbye!"),
        quiz_correct="Good morning!",
        quiz_explanation_en="\"Good morning\" is for the early part of the day.",
        quiz_explanation_ar="\"Good morning\" تُقال في الصباح.",
        encouragement_en="Lovely! You can greet your friends in English.",
        encouragement_ar="رائع! يمكنك تحية أصدقائك بالإنجليزية.",
    ),

    # --- Unit 2: About Me --------------------------------------------
    _build_lesson(
        slug="u2_country",
        unit=UNIT_2_ABOUT_ME,
        word="country", word_ar="بلد",
        sentence="I am from Sudan.",
        title_en="Say where you are from",
        title_ar="قل من أين أنت",
        description_en="Tell people your country in English.",
        description_ar="قل لمن حولك ما هو بلدك بالإنجليزية.",
        quiz_question="I ____ from Sudan.",
        quiz_options=("am", "is", "are"),
        quiz_correct="am",
        quiz_explanation_en="We use \"am\" with I.",
        quiz_explanation_ar="نستخدم \"am\" مع I.",
        encouragement_en="Well done. You can talk about your country now.",
        encouragement_ar="أحسنت. تستطيع الآن أن تتحدث عن بلدك.",
    ),
    _build_lesson(
        slug="u2_student",
        unit=UNIT_2_ABOUT_ME,
        word="student", word_ar="طالب",
        sentence="I am a student.",
        title_en="Say what you do",
        title_ar="قل ماذا تفعل",
        description_en="Tell someone your job or role.",
        description_ar="قل لشخص ما عملك أو دورك.",
        quiz_question="I am ____ student.",
        quiz_options=("a", "an", "the"),
        quiz_correct="a",
        quiz_explanation_en="We use \"a\" before a consonant sound (s in student).",
        quiz_explanation_ar="نستخدم \"a\" قبل الكلمات التي تبدأ بحرف ساكن (s في student).",
        encouragement_en="Strong work! You said what you do today.",
        encouragement_ar="عمل قوي! قلت اليوم ماذا تفعل.",
    ),
    _build_lesson(
        slug="u2_age",
        unit=UNIT_2_ABOUT_ME,
        word="age", word_ar="عمر",
        sentence="I am twenty years old.",
        title_en="Say your age",
        title_ar="قل عمرك",
        description_en="Tell someone how old you are.",
        description_ar="قل لشخص ما كم عمرك.",
        quiz_question="I ____ twenty years old.",
        quiz_options=("am", "is", "are"),
        quiz_correct="am",
        quiz_explanation_en="With I we use \"am\".",
        quiz_explanation_ar="مع I نستخدم \"am\".",
        encouragement_en="Nice. You can tell people your age now.",
        encouragement_ar="جميل. أصبحت قادراً على ذكر عمرك.",
    ),
    _build_lesson(
        slug="u2_nationality",
        unit=UNIT_2_ABOUT_ME,
        word="Sudanese", word_ar="سوداني",
        sentence="I am Sudanese.",
        title_en="Say your nationality",
        title_ar="قل جنسيتك",
        description_en="Use a nationality word.",
        description_ar="استخدم كلمة الجنسية.",
        quiz_question="I am ____.",
        quiz_options=("Sudanese", "Sudan", "Sudaneser"),
        quiz_correct="Sudanese",
        quiz_explanation_en="\"Sudanese\" is the nationality, \"Sudan\" is the country.",
        quiz_explanation_ar="\"Sudanese\" هي الجنسية و \"Sudan\" هي اسم البلد.",
        encouragement_en="Great! You said your nationality clearly.",
        encouragement_ar="ممتاز! قلت جنسيتك بوضوح.",
    ),

    # --- Unit 3: Basic Objects ---------------------------------------
    _build_lesson(
        slug="u3_book",
        unit=UNIT_3_BASIC_OBJECTS,
        word="book", word_ar="كتاب",
        sentence="This is a book.",
        title_en="Name a book",
        title_ar="سمِّ كتاباً",
        description_en="Use \"this\" with an object.",
        description_ar="استخدم \"this\" مع شيء.",
        quiz_question="This ____ a book.",
        quiz_options=("is", "are", "am"),
        quiz_correct="is",
        quiz_explanation_en="With \"this\" we use \"is\".",
        quiz_explanation_ar="مع \"this\" نستخدم \"is\".",
        encouragement_en="You can name objects in English now.",
        encouragement_ar="تستطيع الآن تسمية الأشياء بالإنجليزية.",
    ),
    _build_lesson(
        slug="u3_phone",
        unit=UNIT_3_BASIC_OBJECTS,
        word="phone", word_ar="هاتف",
        sentence="This is my phone.",
        title_en="Name your phone",
        title_ar="سمِّ هاتفك",
        description_en="Talk about something you own.",
        description_ar="تحدّث عن شيء تملكه.",
        quiz_question="This is ____ phone.",
        quiz_options=("my", "I", "me"),
        quiz_correct="my",
        quiz_explanation_en="\"my\" shows you own something.",
        quiz_explanation_ar="\"my\" تدلّ على أنك تملك شيئاً.",
        encouragement_en="Wonderful! You used a possessive word.",
        encouragement_ar="رائع! استخدمت كلمة للملكية.",
    ),
    _build_lesson(
        slug="u3_table_chair",
        unit=UNIT_3_BASIC_OBJECTS,
        word="chair", word_ar="كرسي",
        sentence="The chair is here.",
        title_en="Talk about furniture",
        title_ar="تحدّث عن الأثاث",
        description_en="Use \"the\" with a known object.",
        description_ar="استخدم \"the\" مع شيء معروف.",
        quiz_question="____ chair is here.",
        quiz_options=("The", "A", "An"),
        quiz_correct="The",
        quiz_explanation_en="\"The\" is for a specific thing we know.",
        quiz_explanation_ar="\"The\" للأشياء المعروفة.",
        encouragement_en="Nice work! You used \"the\" correctly.",
        encouragement_ar="عمل جميل! استخدمت \"the\" بشكل صحيح.",
    ),

    # --- Unit 4: Simple Sentences ------------------------------------
    _build_lesson(
        slug="u4_i_have",
        unit=UNIT_4_SIMPLE_SENTENCES,
        word="have", word_ar="يملك / لديه",
        sentence="I have a pen.",
        title_en="Say what you have",
        title_ar="قل ماذا تملك",
        description_en="Use \"have\" with I.",
        description_ar="استخدم \"have\" مع I.",
        quiz_question="I ____ a pen.",
        quiz_options=("have", "has", "having"),
        quiz_correct="have",
        quiz_explanation_en="With I we use \"have\" (not \"has\").",
        quiz_explanation_ar="مع I نستخدم \"have\" وليس \"has\".",
        encouragement_en="Great. You can say what you own.",
        encouragement_ar="ممتاز. تستطيع أن تقول ما تملكه.",
    ),
    _build_lesson(
        slug="u4_like_english",
        unit=UNIT_4_SIMPLE_SENTENCES,
        word="like", word_ar="يحب",
        sentence="I like English.",
        title_en="Say what you like",
        title_ar="قل ما الذي تحبه",
        description_en="Use \"like\" with I.",
        description_ar="استخدم \"like\" مع I.",
        quiz_question="I ____ English.",
        quiz_options=("like", "likes", "liking"),
        quiz_correct="like",
        quiz_explanation_en="With \"I\" we use the base form: like.",
        quiz_explanation_ar="مع \"I\" نستخدم الفعل في صورته الأساسية: like.",
        encouragement_en="Wonderful! You shared what you love.",
        encouragement_ar="رائع! شاركت ما تحب.",
    ),
    _build_lesson(
        slug="u4_this_is",
        unit=UNIT_4_SIMPLE_SENTENCES,
        word="this", word_ar="هذا",
        sentence="This is my friend.",
        title_en="Introduce a friend",
        title_ar="عرّف بصديق",
        description_en="Use \"this is\" to introduce a person.",
        description_ar="استخدم \"this is\" لتعرّف بشخص.",
        quiz_question="____ is my friend.",
        quiz_options=("This", "These", "Those"),
        quiz_correct="This",
        quiz_explanation_en="\"This\" is for one person or thing near you.",
        quiz_explanation_ar="\"This\" للشخص أو الشيء القريب منك.",
        encouragement_en="You can introduce a friend now.",
        encouragement_ar="أصبحت قادراً على تعريف صديق.",
    ),

    # --- Unit 5: Daily Life ------------------------------------------
    _build_lesson(
        slug="u5_wake_up",
        unit=UNIT_5_DAILY_LIFE,
        word="wake up", word_ar="يستيقظ",
        sentence="I wake up at six.",
        title_en="Talk about waking up",
        title_ar="تحدّث عن الاستيقاظ",
        description_en="Say when you start your day.",
        description_ar="قل متى تبدأ يومك.",
        quiz_question="I ____ up at six.",
        quiz_options=("wake", "wakes", "waking"),
        quiz_correct="wake",
        quiz_explanation_en="With I we use the base verb.",
        quiz_explanation_ar="مع I نستخدم الفعل في صورته الأساسية.",
        encouragement_en="Nice. You can describe your morning now.",
        encouragement_ar="جميل. تستطيع وصف صباحك الآن.",
    ),
    _build_lesson(
        slug="u5_eat",
        unit=UNIT_5_DAILY_LIFE,
        word="eat", word_ar="يأكل",
        sentence="I eat breakfast.",
        title_en="Talk about eating",
        title_ar="تحدّث عن الأكل",
        description_en="Say a daily routine sentence.",
        description_ar="قل جملة عن روتينك اليومي.",
        quiz_question="I ____ breakfast every day.",
        quiz_options=("eat", "eats", "eating"),
        quiz_correct="eat",
        quiz_explanation_en="With I we use the base verb.",
        quiz_explanation_ar="مع I نستخدم الفعل في صورته الأساسية.",
        encouragement_en="Strong work. You can talk about meals.",
        encouragement_ar="عمل قوي. تستطيع التحدث عن وجباتك.",
    ),
    _build_lesson(
        slug="u5_drink_water",
        unit=UNIT_5_DAILY_LIFE,
        word="water", word_ar="ماء",
        sentence="I drink water.",
        title_en="Talk about drinking",
        title_ar="تحدّث عن الشرب",
        description_en="A useful daily sentence.",
        description_ar="جملة يومية مفيدة.",
        quiz_question="I ____ water.",
        quiz_options=("drink", "drinks", "drinking"),
        quiz_correct="drink",
        quiz_explanation_en="With I we use the base verb.",
        quiz_explanation_ar="مع I نستخدم الفعل في صورته الأساسية.",
        encouragement_en="Excellent! You talked about a daily habit.",
        encouragement_ar="ممتاز! تحدثت عن عادة يومية.",
    ),
    _build_lesson(
        slug="u5_go_to_work",
        unit=UNIT_5_DAILY_LIFE,
        word="work", word_ar="عمل",
        sentence="I go to work.",
        title_en="Talk about going to work",
        title_ar="تحدّث عن الذهاب إلى العمل",
        description_en="Say where you go every day.",
        description_ar="قل إلى أين تذهب يومياً.",
        quiz_question="I ____ to work every day.",
        quiz_options=("go", "goes", "going"),
        quiz_correct="go",
        quiz_explanation_en="With I we use the base verb.",
        quiz_explanation_ar="مع I نستخدم الفعل في صورته الأساسية.",
        encouragement_en="Well done! You can describe your day.",
        encouragement_ar="أحسنت! تستطيع وصف يومك.",
    ),

    # --- Letters (Week 1 — alphabet) ----------------------------------
    _build_lesson(
        slug="u1l_abcd",
        unit=UNIT_1_HELLO,
        word="apple", word_ar="تفاحة",
        sentence="This is an apple.",
        title_en="Letters A B C D",
        title_ar="الحروف A B C D",
        description_en="Meet your first four English letters.",
        description_ar="تعرّف على أول 4 حروف إنجليزية.",
        quiz_question="____ is red.",
        quiz_options=("Apple", "Book", "Cat"),
        quiz_correct="Apple",
        quiz_explanation_en="An apple is usually red.",
        quiz_explanation_ar="التفاحة عادةً حمراء.",
        encouragement_en="Amazing first step. 4 letters today!",
        encouragement_ar="أول 4 حروف! بداية رائعة.",
    ),
    _build_lesson(
        slug="u1l_efgh",
        unit=UNIT_1_HELLO,
        word="fish", word_ar="سمكة",
        sentence="This is a fish.",
        title_en="Letters E F G H",
        title_ar="الحروف E F G H",
        description_en="Four more letters and four words.",
        description_ar="أربع حروف جديدة وأربع كلمات.",
        quiz_question="A fish lives in ____.",
        quiz_options=("water", "fire", "air"),
        quiz_correct="water",
        quiz_explanation_en="Fish live in water.",
        quiz_explanation_ar="السمك يعيش في الماء.",
        encouragement_en="Wonderful! 8 letters now.",
        encouragement_ar="ممتاز! 8 حروف.",
    ),
    _build_lesson(
        slug="u1l_ijklmn",
        unit=UNIT_1_HELLO,
        word="ice", word_ar="ثلج",
        sentence="This is ice.",
        title_en="Letters I J K L M N",
        title_ar="الحروف I J K L M N",
        description_en="Six new letters in your alphabet.",
        description_ar="ستة حروف جديدة في أبجديتك.",
        quiz_question="Ice is ____.",
        quiz_options=("cold", "hot", "warm"),
        quiz_correct="cold",
        quiz_explanation_en="Ice is always cold.",
        quiz_explanation_ar="الثلج بارد دائماً.",
        encouragement_en="Half the alphabet! Keep going.",
        encouragement_ar="نصف الأبجدية! واصل.",
    ),
    _build_lesson(
        slug="u1l_opqrst",
        unit=UNIT_1_HELLO,
        word="orange", word_ar="برتقالة",
        sentence="This is an orange.",
        title_en="Letters O P Q R S T",
        title_ar="الحروف O P Q R S T",
        description_en="Six letters and one juicy fruit.",
        description_ar="ستة حروف وفاكهة لذيذة.",
        quiz_question="An orange is a ____.",
        quiz_options=("fruit", "drink", "color"),
        quiz_correct="fruit",
        quiz_explanation_en="Orange (the food) is a fruit.",
        quiz_explanation_ar="البرتقال فاكهة.",
        encouragement_en="20 letters! Almost there.",
        encouragement_ar="20 حرفاً! اقتربت.",
    ),
    _build_lesson(
        slug="u1l_uvwxyz",
        unit=UNIT_1_HELLO,
        word="water", word_ar="ماء",
        sentence="I drink water.",
        title_en="Letters U V W X Y Z",
        title_ar="الحروف U V W X Y Z",
        description_en="The last 6 letters of the alphabet.",
        description_ar="آخر 6 حروف من الأبجدية.",
        quiz_question="I ____ water every day.",
        quiz_options=("drink", "eat", "read"),
        quiz_correct="drink",
        quiz_explanation_en="We drink water, not eat it.",
        quiz_explanation_ar="نشرب الماء، لا نأكله.",
        encouragement_en="🎉 All 26 letters done! You did it.",
        encouragement_ar="🎉 الـ 26 حرفاً كلها! أنجزت.",
    ),

    # --- Family (Week 7) ----------------------------------------------
    _build_lesson(
        slug="u7_mother",
        unit=UNIT_2_ABOUT_ME,
        word="mother", word_ar="أم",
        sentence="This is my mother.",
        title_en="Talk about your mother",
        title_ar="تحدّث عن أمك",
        description_en="Introduce someone in your family.",
        description_ar="عرّف بشخص من عائلتك.",
        quiz_question="This is ____ mother.",
        quiz_options=("my", "I", "me"),
        quiz_correct="my",
        quiz_explanation_en="\"my\" shows the person belongs to you.",
        quiz_explanation_ar="\"my\" تدلّ على أنّ الشخص يخصّك.",
        encouragement_en="Beautiful. Family words are important.",
        encouragement_ar="رائع. كلمات العائلة مهمة.",
    ),
    _build_lesson(
        slug="u7_father",
        unit=UNIT_2_ABOUT_ME,
        word="father", word_ar="أب",
        sentence="My father is a teacher.",
        title_en="Talk about your father",
        title_ar="تحدّث عن أبيك",
        description_en="Say what your father does.",
        description_ar="قل ماذا يعمل أبوك.",
        quiz_question="My father ____ a teacher.",
        quiz_options=("is", "are", "am"),
        quiz_correct="is",
        quiz_explanation_en="With \"my father\" we use \"is\".",
        quiz_explanation_ar="مع \"my father\" نستخدم \"is\".",
        encouragement_en="Strong work. You can talk about him now.",
        encouragement_ar="عمل قوي. تستطيع التحدث عنه الآن.",
    ),
    _build_lesson(
        slug="u7_brother",
        unit=UNIT_2_ABOUT_ME,
        word="brother", word_ar="أخ",
        sentence="I have a brother.",
        title_en="Talk about your brother",
        title_ar="تحدّث عن أخيك",
        description_en="Use \"I have\" with a family member.",
        description_ar="استخدم \"I have\" مع فرد من العائلة.",
        quiz_question="I ____ a brother.",
        quiz_options=("have", "has", "having"),
        quiz_correct="have",
        quiz_explanation_en="With I we use \"have\" (not has).",
        quiz_explanation_ar="مع I نستخدم \"have\" (لا has).",
        encouragement_en="Nice! You used a new verb today.",
        encouragement_ar="جميل! استخدمت فعلاً جديداً.",
    ),
    _build_lesson(
        slug="u7_sister",
        unit=UNIT_2_ABOUT_ME,
        word="sister", word_ar="أخت",
        sentence="My sister is kind.",
        title_en="Talk about your sister",
        title_ar="تحدّث عن أختك",
        description_en="Describe a family member.",
        description_ar="صف فرداً من عائلتك.",
        quiz_question="My sister is ____.",
        quiz_options=("kind", "kinds", "kindly"),
        quiz_correct="kind",
        quiz_explanation_en="After \"is\" we use the adjective form.",
        quiz_explanation_ar="بعد \"is\" نستخدم الصفة في صورتها الأساسية.",
        encouragement_en="You described a person. Strong step.",
        encouragement_ar="وصفت شخصاً. خطوة قوية.",
    ),
    _build_lesson(
        slug="u7_family",
        unit=UNIT_2_ABOUT_ME,
        word="family", word_ar="عائلة",
        sentence="I love my family.",
        title_en="Talk about your family",
        title_ar="تحدّث عن عائلتك",
        description_en="One short sentence about your family.",
        description_ar="جملة قصيرة عن عائلتك.",
        quiz_question="I ____ my family.",
        quiz_options=("love", "loves", "loving"),
        quiz_correct="love",
        quiz_explanation_en="With I we use the base verb: love.",
        quiz_explanation_ar="مع I نستخدم الفعل الأساسي: love.",
        encouragement_en="Wonderful. Family is the heart of everything.",
        encouragement_ar="رائع. العائلة هي قلب كل شيء.",
    ),

    # --- Food & Drink (Week 8) ----------------------------------------
    _build_lesson(
        slug="u8_bread",
        unit=UNIT_5_DAILY_LIFE,
        word="bread", word_ar="خبز",
        sentence="I eat bread.",
        title_en="Talk about bread",
        title_ar="تحدّث عن الخبز",
        description_en="A daily food word.",
        description_ar="كلمة طعام يومية.",
        quiz_question="I ____ bread.",
        quiz_options=("eat", "drink", "read"),
        quiz_correct="eat",
        quiz_explanation_en="We eat bread, we don't drink it.",
        quiz_explanation_ar="نأكل الخبز، لا نشربه.",
        encouragement_en="Useful word for every day.",
        encouragement_ar="كلمة مفيدة كل يوم.",
    ),
    _build_lesson(
        slug="u8_tea",
        unit=UNIT_5_DAILY_LIFE,
        word="tea", word_ar="شاي",
        sentence="I like tea.",
        title_en="Talk about tea",
        title_ar="تحدّث عن الشاي",
        description_en="Talk about a hot drink.",
        description_ar="تحدّث عن مشروب ساخن.",
        quiz_question="I ____ tea.",
        quiz_options=("like", "likes", "liking"),
        quiz_correct="like",
        quiz_explanation_en="With I we use \"like\".",
        quiz_explanation_ar="مع I نستخدم \"like\".",
        encouragement_en="Nice. Now you can order tea in English.",
        encouragement_ar="جميل. الآن تستطيع طلب الشاي بالإنجليزية.",
    ),
    _build_lesson(
        slug="u8_coffee",
        unit=UNIT_5_DAILY_LIFE,
        word="coffee", word_ar="قهوة",
        sentence="I drink coffee in the morning.",
        title_en="Talk about coffee",
        title_ar="تحدّث عن القهوة",
        description_en="Add the time of day to a drink sentence.",
        description_ar="أضف وقت اليوم إلى جملة شراب.",
        quiz_question="I drink coffee in the ____.",
        quiz_options=("morning", "evening", "night"),
        quiz_correct="morning",
        quiz_explanation_en="Most people drink coffee in the morning.",
        quiz_explanation_ar="معظم الناس يشربون القهوة في الصباح.",
        encouragement_en="Great. You added time to the sentence.",
        encouragement_ar="رائع. أضفت الوقت للجملة.",
    ),
    _build_lesson(
        slug="u8_breakfast",
        unit=UNIT_5_DAILY_LIFE,
        word="breakfast", word_ar="إفطار",
        sentence="I have breakfast at seven.",
        title_en="Talk about breakfast",
        title_ar="تحدّث عن الإفطار",
        description_en="Say when you eat breakfast.",
        description_ar="قل متى تأكل الإفطار.",
        quiz_question="I have breakfast ____ seven.",
        quiz_options=("at", "in", "on"),
        quiz_correct="at",
        quiz_explanation_en="With a clock time we use \"at\".",
        quiz_explanation_ar="مع وقت محدد بالساعة نستخدم \"at\".",
        encouragement_en="Time words are useful every day.",
        encouragement_ar="كلمات الوقت مفيدة يومياً.",
    ),
    _build_lesson(
        slug="u8_apple",
        unit=UNIT_5_DAILY_LIFE,
        word="apple", word_ar="تفاحة",
        sentence="I eat an apple every day.",
        title_en="Eat fruit every day",
        title_ar="تناول الفاكهة يومياً",
        description_en="Talk about a habit with \"every day\".",
        description_ar="تحدّث عن عادة بـ \"every day\".",
        quiz_question="I eat ____ apple every day.",
        quiz_options=("an", "a", "the"),
        quiz_correct="an",
        quiz_explanation_en="Before a vowel sound (a in apple) use \"an\".",
        quiz_explanation_ar="قبل صوت متحرّك (a في apple) استخدم \"an\".",
        encouragement_en="Healthy habit. Good for your English too!",
        encouragement_ar="عادة صحية. جيدة لإنجليزيتك أيضاً!",
    ),

    # --- Daily Routine extras (Week 9) --------------------------------
    _build_lesson(
        slug="u9_sleep",
        unit=UNIT_5_DAILY_LIFE,
        word="sleep", word_ar="ينام",
        sentence="I sleep at ten.",
        title_en="Talk about sleeping",
        title_ar="تحدّث عن النوم",
        description_en="End of the day routine.",
        description_ar="نهاية روتين اليوم.",
        quiz_question="I ____ at ten.",
        quiz_options=("sleep", "sleeps", "sleeping"),
        quiz_correct="sleep",
        quiz_explanation_en="With I we use the base verb.",
        quiz_explanation_ar="مع I نستخدم الفعل الأساسي.",
        encouragement_en="A good night brings a strong morning.",
        encouragement_ar="ليلة طيبة تعني صباحاً قوياً.",
    ),
    _build_lesson(
        slug="u9_every_day",
        unit=UNIT_5_DAILY_LIFE,
        word="every day", word_ar="كل يوم",
        sentence="Every day I learn English.",
        title_en="Make it a habit",
        title_ar="اجعلها عادة",
        description_en="Use \"every day\" to talk about routine.",
        description_ar="استخدم \"every day\" للحديث عن الروتين.",
        quiz_question="____ I learn English.",
        quiz_options=("Every day", "Yesterday", "Tomorrow"),
        quiz_correct="Every day",
        quiz_explanation_en="A routine sentence starts with \"Every day\".",
        quiz_explanation_ar="جملة الروتين تبدأ بـ \"Every day\".",
        encouragement_en="Consistency beats talent. Keep going.",
        encouragement_ar="الاستمرار يفوق الموهبة. واصل.",
    ),

    # --- Basic verbs (Week 10) ----------------------------------------
    _build_lesson(
        slug="u10_want",
        unit=UNIT_4_SIMPLE_SENTENCES,
        word="want", word_ar="يريد",
        sentence="I want water.",
        title_en="Say what you want",
        title_ar="قل ماذا تريد",
        description_en="Useful for shops and restaurants.",
        description_ar="مفيد للمحلات والمطاعم.",
        quiz_question="I ____ water, please.",
        quiz_options=("want", "wants", "wanting"),
        quiz_correct="want",
        quiz_explanation_en="With I we use \"want\" (not wants).",
        quiz_explanation_ar="مع I نستخدم \"want\" (لا wants).",
        encouragement_en="You can ask for things now. Useful!",
        encouragement_ar="تستطيع طلب الأشياء الآن. مفيد!",
    ),
    _build_lesson(
        slug="u10_need",
        unit=UNIT_4_SIMPLE_SENTENCES,
        word="need", word_ar="يحتاج",
        sentence="I need a pen.",
        title_en="Say what you need",
        title_ar="قل ماذا تحتاج",
        description_en="\"Need\" is stronger than \"want\".",
        description_ar="\"need\" أقوى من \"want\".",
        quiz_question="I ____ a pen.",
        quiz_options=("need", "needs", "needing"),
        quiz_correct="need",
        quiz_explanation_en="With I we use \"need\".",
        quiz_explanation_ar="مع I نستخدم \"need\".",
        encouragement_en="Two useful verbs today.",
        encouragement_ar="فعلان مفيدان اليوم.",
    ),
    _build_lesson(
        slug="u10_speak",
        unit=UNIT_4_SIMPLE_SENTENCES,
        word="speak", word_ar="يتكلم",
        sentence="I speak Arabic.",
        title_en="Talk about languages",
        title_ar="تحدّث عن اللغات",
        description_en="Say what languages you speak.",
        description_ar="قل اللغات التي تتكلمها.",
        quiz_question="I ____ Arabic and English.",
        quiz_options=("speak", "speaks", "speaking"),
        quiz_correct="speak",
        quiz_explanation_en="With I we use \"speak\".",
        quiz_explanation_ar="مع I نستخدم \"speak\".",
        encouragement_en="Bilingual! That's a great skill.",
        encouragement_ar="ثنائي اللغة! مهارة رائعة.",
    ),
    _build_lesson(
        slug="u10_learn",
        unit=UNIT_4_SIMPLE_SENTENCES,
        word="learn", word_ar="يتعلم",
        sentence="I learn English every day.",
        title_en="Talk about learning",
        title_ar="تحدّث عن التعلم",
        description_en="Describe your current journey.",
        description_ar="صف رحلتك الحالية.",
        quiz_question="I ____ English every day.",
        quiz_options=("learn", "learns", "learning"),
        quiz_correct="learn",
        quiz_explanation_en="With I we use \"learn\".",
        quiz_explanation_ar="مع I نستخدم \"learn\".",
        encouragement_en="That's exactly what you're doing right now!",
        encouragement_ar="هذا بالضبط ما تفعله الآن!",
    ),

    # --- Short conversations (Week 11) --------------------------------
    _build_lesson(
        slug="u11_how_are_you",
        unit=UNIT_1_HELLO,
        word="fine", word_ar="بخير",
        sentence="I am fine, thank you.",
        title_en="Reply: How are you?",
        title_ar="ردّك على: How are you?",
        description_en="The most-asked English question.",
        description_ar="السؤال الإنجليزي الأكثر شيوعاً.",
        quiz_question="A: How are you?  B: ____",
        quiz_options=("I am fine, thank you.", "My name is Ali.", "I am from Sudan."),
        quiz_correct="I am fine, thank you.",
        quiz_explanation_en="\"How are you?\" asks about feeling.",
        quiz_explanation_ar="\"How are you?\" يسأل عن الشعور.",
        encouragement_en="Now you can answer the most common question.",
        encouragement_ar="الآن تردّ على السؤال الأكثر شيوعاً.",
    ),
    _build_lesson(
        slug="u11_thank_you",
        unit=UNIT_1_HELLO,
        word="thank you", word_ar="شكراً",
        sentence="Thank you very much.",
        title_en="Say thank you",
        title_ar="قل شكراً",
        description_en="Two of the most important English words.",
        description_ar="من أهم كلمتين في الإنجليزية.",
        quiz_question="Someone helps you. You say: ____",
        quiz_options=("Thank you.", "Sorry.", "Goodbye."),
        quiz_correct="Thank you.",
        quiz_explanation_en="We say \"thank you\" when someone helps.",
        quiz_explanation_ar="نقول \"thank you\" حين يساعدنا أحد.",
        encouragement_en="Politeness opens many doors.",
        encouragement_ar="الأدب يفتح أبواباً كثيرة.",
    ),
    _build_lesson(
        slug="u11_sorry",
        unit=UNIT_1_HELLO,
        word="sorry", word_ar="آسف",
        sentence="I am sorry. I am late.",
        title_en="Apologise gently",
        title_ar="اعتذر بلطف",
        description_en="When you make a small mistake.",
        description_ar="حين تخطئ خطأً صغيراً.",
        quiz_question="You arrived late. You say: ____",
        quiz_options=("I am sorry.", "Thank you.", "Hello."),
        quiz_correct="I am sorry.",
        quiz_explanation_en="We say \"sorry\" when we're late or wrong.",
        quiz_explanation_ar="نقول \"sorry\" حين نتأخر أو نخطئ.",
        encouragement_en="A small word that fixes many problems.",
        encouragement_ar="كلمة صغيرة تُصلح أموراً كثيرة.",
    ),
    _build_lesson(
        slug="u11_excuse_me",
        unit=UNIT_1_HELLO,
        word="excuse me", word_ar="عذراً",
        sentence="Excuse me. Where is the door?",
        title_en="Ask a stranger politely",
        title_ar="اسأل غريباً بأدب",
        description_en="Use \"excuse me\" to start a polite question.",
        description_ar="استخدم \"excuse me\" لبدء سؤال مهذّب.",
        quiz_question="You ask a stranger for directions. Start with: ____",
        quiz_options=("Excuse me", "Hello there", "Hey you"),
        quiz_correct="Excuse me",
        quiz_explanation_en="\"Excuse me\" is the polite opener.",
        quiz_explanation_ar="\"Excuse me\" هي الفاتحة المهذّبة.",
        encouragement_en="Politeness is a superpower in English.",
        encouragement_ar="الأدب قوة خارقة في الإنجليزية.",
    ),
    _build_lesson(
        slug="u11_see_you",
        unit=UNIT_1_HELLO,
        word="see you", word_ar="إلى اللقاء",
        sentence="See you tomorrow.",
        title_en="Friendly goodbye",
        title_ar="وداع ودود",
        description_en="A warm way to end a chat.",
        description_ar="طريقة ودودة لإنهاء محادثة.",
        quiz_question="A friendly goodbye is: ____",
        quiz_options=("See you tomorrow.", "I am sorry.", "Thank you."),
        quiz_correct="See you tomorrow.",
        quiz_explanation_en="\"See you tomorrow\" is friendlier than \"Goodbye\".",
        quiz_explanation_ar="\"See you tomorrow\" أودّ من \"Goodbye\".",
        encouragement_en="You can end a real conversation now.",
        encouragement_ar="تستطيع إنهاء محادثة حقيقية الآن.",
    ),

    # --- Review week (Week 12 mix) ------------------------------------
    _build_lesson(
        slug="u12_review_intro",
        unit=UNIT_2_ABOUT_ME,
        word="introduce", word_ar="يعرّف",
        sentence="My name is Ali. I am from Sudan.",
        title_en="Introduce yourself in two sentences",
        title_ar="عرّف بنفسك في جملتين",
        description_en="Combine name + country in one go.",
        description_ar="اجمع الاسم والبلد في مرّة واحدة.",
        quiz_question="A complete intro is: ____",
        quiz_options=(
            "My name is Ali. I am from Sudan.",
            "Ali Sudan.",
            "I Ali I Sudan.",
        ),
        quiz_correct="My name is Ali. I am from Sudan.",
        quiz_explanation_en="Two short sentences make a clean intro.",
        quiz_explanation_ar="جملتان قصيرتان تكوّنان تعريفاً جيداً.",
        encouragement_en="You can introduce yourself fully!",
        encouragement_ar="تستطيع تعريف نفسك كاملاً!",
    ),
    _build_lesson(
        slug="u12_review_routine",
        unit=UNIT_5_DAILY_LIFE,
        word="routine", word_ar="روتين",
        sentence="I wake up, eat breakfast, and go to work.",
        title_en="Describe your day",
        title_ar="صف يومك",
        description_en="Combine three actions with \"and\".",
        description_ar="اجمع ثلاثة أفعال بـ \"and\".",
        quiz_question="Join: \"I wake up\" + \"I eat\" + \"I go\" → ____",
        quiz_options=(
            "I wake up, eat, and go.",
            "I wake up. I eat. I go.",
            "Wake up eat go.",
        ),
        quiz_correct="I wake up, eat, and go.",
        quiz_explanation_en="\"and\" links the last action; commas join the rest.",
        quiz_explanation_ar="\"and\" تربط آخر فعل؛ والفواصل تربط البقية.",
        encouragement_en="You're using English like a longer sentence now.",
        encouragement_ar="بدأت تستخدم الإنجليزية بجملة أطول.",
    ),
    _build_lesson(
        slug="u12_review_food",
        unit=UNIT_5_DAILY_LIFE,
        word="meal", word_ar="وجبة",
        sentence="I have three meals a day.",
        title_en="Count meals in a day",
        title_ar="عُدّ الوجبات في اليوم",
        description_en="Use a number with \"meals\".",
        description_ar="استخدم عدداً مع \"meals\".",
        quiz_question="I have ____ meals a day.",
        quiz_options=("three", "third", "thirty"),
        quiz_correct="three",
        quiz_explanation_en="\"three meals\" means breakfast + lunch + dinner.",
        quiz_explanation_ar="\"three meals\" تعني الإفطار والغداء والعشاء.",
        encouragement_en="Numbers in real sentences. Big step.",
        encouragement_ar="الأرقام في جمل حقيقية. خطوة كبيرة.",
    ),
    _build_lesson(
        slug="u12_review_family",
        unit=UNIT_2_ABOUT_ME,
        word="together", word_ar="معاً",
        sentence="We eat dinner together.",
        title_en="Talk about your family together",
        title_ar="تحدّث عن عائلتك معاً",
        description_en="Use \"we\" for the family.",
        description_ar="استخدم \"we\" للعائلة.",
        quiz_question="My family eats together. ____ are happy.",
        quiz_options=("We", "I", "They"),
        quiz_correct="We",
        quiz_explanation_en="\"We\" includes the speaker + family.",
        quiz_explanation_ar="\"We\" تشمل المتكلم وعائلته.",
        encouragement_en="A new pronoun: \"we\". Strong.",
        encouragement_ar="ضمير جديد: \"we\". قوي.",
    ),
    _build_lesson(
        slug="u12_review_ready_for_a1",
        unit=UNIT_4_SIMPLE_SENTENCES,
        word="ready", word_ar="جاهز",
        sentence="I am ready for A1.",
        title_en="You are ready for A1",
        title_ar="أنت جاهز للمستوى A1",
        description_en="The final A0 lesson — celebrating readiness.",
        description_ar="آخر درس في A0 — احتفال بالجاهزية.",
        quiz_question="I am ____ for A1.",
        quiz_options=("ready", "readies", "readying"),
        quiz_correct="ready",
        quiz_explanation_en="After \"am\" we use the adjective: ready.",
        quiz_explanation_ar="بعد \"am\" نستخدم الصفة: ready.",
        encouragement_en="🎓 You completed A0! See you in A1.",
        encouragement_ar="🎓 أكملت A0! نلتقي في A1.",
    ),

    # --- Numbers detail (Week 3) -------------------------------------
    _build_lesson(
        slug="u3_one_to_five",
        unit=UNIT_2_ABOUT_ME,
        word="five", word_ar="خمسة",
        sentence="I have five books.",
        title_en="Numbers one to five",
        title_ar="الأرقام من واحد إلى خمسة",
        description_en="Count one, two, three, four, five.",
        description_ar="عد واحد، اثنين، ثلاثة، أربعة، خمسة.",
        quiz_question="How many books? (5)",
        quiz_options=("five", "four", "six"),
        quiz_correct="five",
        quiz_explanation_en="5 = five.",
        quiz_explanation_ar="5 = five.",
        encouragement_en="Counting in English. Big step.",
        encouragement_ar="العد بالإنجليزية. خطوة كبيرة.",
    ),
    _build_lesson(
        slug="u3_six_to_ten",
        unit=UNIT_2_ABOUT_ME,
        word="ten", word_ar="عشرة",
        sentence="I have ten fingers.",
        title_en="Numbers six to ten",
        title_ar="الأرقام من ستة إلى عشرة",
        description_en="Count six through ten.",
        description_ar="عد من ستة إلى عشرة.",
        quiz_question="How many fingers? (10)",
        quiz_options=("ten", "nine", "eleven"),
        quiz_correct="ten",
        quiz_explanation_en="10 = ten.",
        quiz_explanation_ar="10 = ten.",
        encouragement_en="You can count to 10!",
        encouragement_ar="تستطيع العد حتى 10!",
    ),
    _build_lesson(
        slug="u3_eleven_to_twenty",
        unit=UNIT_2_ABOUT_ME,
        word="twenty", word_ar="عشرون",
        sentence="I am twenty years old.",
        title_en="Numbers eleven to twenty",
        title_ar="الأرقام من 11 إلى 20",
        description_en="Bigger numbers to talk about age.",
        description_ar="أرقام أكبر للحديث عن العمر.",
        quiz_question="20 in English is ____.",
        quiz_options=("twenty", "twelve", "two"),
        quiz_correct="twenty",
        quiz_explanation_en="20 = twenty. Different from 12 (twelve).",
        quiz_explanation_ar="20 = twenty. تختلف عن 12 (twelve).",
        encouragement_en="Now you can say your age.",
        encouragement_ar="الآن تستطيع قول عمرك.",
    ),

    # --- Countries detail (Week 4) -----------------------------------
    _build_lesson(
        slug="u4_egypt",
        unit=UNIT_2_ABOUT_ME,
        word="Egypt", word_ar="مصر",
        sentence="I am from Egypt.",
        title_en="Talk about Egypt",
        title_ar="تحدّث عن مصر",
        description_en="One of the largest Arab countries.",
        description_ar="من أكبر الدول العربية.",
        quiz_question="Capital of Egypt: ____",
        quiz_options=("Cairo", "Riyadh", "Khartoum"),
        quiz_correct="Cairo",
        quiz_explanation_en="Cairo is the capital of Egypt.",
        quiz_explanation_ar="القاهرة عاصمة مصر.",
        encouragement_en="Geography in English. Useful skill.",
        encouragement_ar="الجغرافيا بالإنجليزية. مهارة مفيدة.",
    ),
    _build_lesson(
        slug="u4_saudi_arabia",
        unit=UNIT_2_ABOUT_ME,
        word="Saudi", word_ar="سعودي",
        sentence="He is from Saudi Arabia.",
        title_en="Talk about Saudi Arabia",
        title_ar="تحدّث عن السعودية",
        description_en="Use \"he\" for a male speaker.",
        description_ar="استخدم \"he\" للمتحدث الذكر.",
        quiz_question="A man from Saudi Arabia is: ____",
        quiz_options=("Saudi", "Saudia", "Sauder"),
        quiz_correct="Saudi",
        quiz_explanation_en="The nationality is \"Saudi\".",
        quiz_explanation_ar="الجنسية هي \"Saudi\".",
        encouragement_en="A new pronoun: he. Strong.",
        encouragement_ar="ضمير جديد: he. قوي.",
    ),

    # --- More jobs (Week 5) ------------------------------------------
    _build_lesson(
        slug="u5_doctor",
        unit=UNIT_2_ABOUT_ME,
        word="doctor", word_ar="طبيب",
        sentence="My mother is a doctor.",
        title_en="Talk about a doctor",
        title_ar="تحدّث عن الطبيب",
        description_en="Doctors help us when we are sick.",
        description_ar="الأطباء يساعدوننا حين نمرض.",
        quiz_question="My mother is a ____.",
        quiz_options=("doctor", "doctors", "doctoring"),
        quiz_correct="doctor",
        quiz_explanation_en="After 'a' we use the singular: doctor.",
        quiz_explanation_ar="بعد 'a' نستخدم المفرد: doctor.",
        encouragement_en="Two professions you can name now.",
        encouragement_ar="مهنتان تستطيع تسميتهما الآن.",
    ),
    _build_lesson(
        slug="u5_engineer",
        unit=UNIT_2_ABOUT_ME,
        word="engineer", word_ar="مهندس",
        sentence="He is an engineer.",
        title_en="Talk about an engineer",
        title_ar="تحدّث عن المهندس",
        description_en="Engineers build and design things.",
        description_ar="المهندسون يبنون ويصممون الأشياء.",
        quiz_question="He is ____ engineer.",
        quiz_options=("an", "a", "the"),
        quiz_correct="an",
        quiz_explanation_en="Before a vowel sound (e in engineer) use 'an'.",
        quiz_explanation_ar="قبل صوت متحرك (e في engineer) نستخدم 'an'.",
        encouragement_en="Three professions! Strong vocabulary.",
        encouragement_ar="ثلاث مهن! مفردات قوية.",
    ),

    # --- More objects (Week 6) ---------------------------------------
    _build_lesson(
        slug="u6_pen",
        unit=UNIT_3_BASIC_OBJECTS,
        word="pen", word_ar="قلم",
        sentence="This is a pen.",
        title_en="Pen, pencil, paper",
        title_ar="قلم وقلم رصاص وورقة",
        description_en="School supplies you use every day.",
        description_ar="أدوات مدرسية تستخدمها يومياً.",
        quiz_question="This is ____ pen.",
        quiz_options=("a", "an", "the"),
        quiz_correct="a",
        quiz_explanation_en="Before a consonant (p) use 'a'.",
        quiz_explanation_ar="قبل حرف ساكن (p) نستخدم 'a'.",
        encouragement_en="Useful classroom words.",
        encouragement_ar="كلمات مفيدة في الفصل.",
    ),
    _build_lesson(
        slug="u6_window_door",
        unit=UNIT_3_BASIC_OBJECTS,
        word="window", word_ar="نافذة",
        sentence="The window is open.",
        title_en="Window and door",
        title_ar="النافذة والباب",
        description_en="Parts of a room.",
        description_ar="أجزاء من الغرفة.",
        quiz_question="____ window is open.",
        quiz_options=("The", "A", "An"),
        quiz_correct="The",
        quiz_explanation_en="Specific window (the one nearby) → 'The'.",
        quiz_explanation_ar="نافذة معروفة (القريبة منا) → 'The'.",
        encouragement_en="The vs A — a small word, a big difference.",
        encouragement_ar="The مقابل A — كلمة صغيرة، فارق كبير.",
    ),

    # --- More routine times (Week 9) ---------------------------------
    _build_lesson(
        slug="u9_lunch_dinner",
        unit=UNIT_5_DAILY_LIFE,
        word="lunch", word_ar="غداء",
        sentence="I have lunch at one.",
        title_en="Lunch and dinner",
        title_ar="الغداء والعشاء",
        description_en="Talk about lunch and dinner times.",
        description_ar="تحدّث عن وقت الغداء والعشاء.",
        quiz_question="I have lunch ____ one.",
        quiz_options=("at", "in", "on"),
        quiz_correct="at",
        quiz_explanation_en="Use 'at' with clock time.",
        quiz_explanation_ar="نستخدم 'at' مع الوقت بالساعة.",
        encouragement_en="Three meal times mastered.",
        encouragement_ar="ثلاثة أوقات وجبات أتقنتها.",
    ),

    # --- Evening + night greetings (Week 2 detail) -------------------
    _build_lesson(
        slug="u2_good_evening",
        unit=UNIT_1_HELLO,
        word="evening", word_ar="مساء",
        sentence="Good evening.",
        title_en="Greet in the evening",
        title_ar="ألقِ التحية في المساء",
        description_en="A greeting for the second half of the day.",
        description_ar="تحية للنصف الثاني من اليوم.",
        quiz_question="In the evening we say: ____",
        quiz_options=("Good evening", "Good morning", "Good night"),
        quiz_correct="Good evening",
        quiz_explanation_en="\"Good evening\" is for the afternoon and evening.",
        quiz_explanation_ar="\"Good evening\" تُقال بعد الظهر وفي المساء.",
        encouragement_en="Two greetings now: morning and evening.",
        encouragement_ar="تحيتان الآن: صباح ومساء.",
    ),
    _build_lesson(
        slug="u2_good_night",
        unit=UNIT_1_HELLO,
        word="night", word_ar="ليل",
        sentence="Good night.",
        title_en="Say good night",
        title_ar="قل تصبح على خير",
        description_en="When someone is going to sleep.",
        description_ar="حين يذهب أحدٌ للنوم.",
        quiz_question="Before sleeping we say: ____",
        quiz_options=("Good night", "Good morning", "Goodbye"),
        quiz_correct="Good night",
        quiz_explanation_en="\"Good night\" is for going to sleep.",
        quiz_explanation_ar="\"Good night\" قبل النوم.",
        encouragement_en="Now you can say goodnight in English!",
        encouragement_ar="الآن تستطيع قول تصبح على خير بالإنجليزية!",
    ),
)


# ---------------------------------------------------------------------------
# Selection — deterministic per (user, date) so refreshes are stable
# ---------------------------------------------------------------------------

def pick_topic_for_date(date_ordinal: int, user_id: int) -> A0Topic:
    """Legacy hash-based picker — kept for any caller that doesn't have
    access to a User object. Prefer `pick_next_topic_for_user`."""
    idx = (date_ordinal + (user_id or 0)) % len(A0_TOPICS)
    return A0_TOPICS[idx]


def pick_next_topic_for_user(user, *, on_date) -> A0Topic:
    """Sequential A0 topic selection.

    A0 learners have zero English knowledge by definition — they MUST
    start at Unit 1 (Hello) on day 1, then progress Unit 1 → Unit 5
    in order. The previous hash-based picker randomised the unit and
    could land a brand-new beginner on Unit 4 ("I like English") on
    their very first day, which is exactly the bug Scenario B was
    flagging in production.

    Strategy:
      * Count this user's completed A0 daily plans BEFORE `on_date`
        (status="completed"). That count is the next topic index.
      * Wrap modulo `len(A0_TOPICS)` so a learner who completes all
        17 topics cycles back through them (the A0→A1 promotion
        service should fire long before then).
    """
    completed = 0
    try:
        # Local import to avoid a circular dependency with models.py
        from ..models import DailyLearningPlan
        completed = (
            DailyLearningPlan.objects
            .filter(
                user=user,
                cefr_level="A0",
                status="completed",
                date__lt=on_date,
            )
            .count()
        )
    except Exception:
        completed = 0
    if not A0_TOPICS:
        raise RuntimeError("A0_TOPICS catalog is empty")
    return A0_TOPICS[completed % len(A0_TOPICS)]


def topics_for_unit(unit_number: int) -> tuple[A0Topic, ...]:
    return tuple(t for t in A0_TOPICS if t.unit == unit_number)


# ---------------------------------------------------------------------------
# Motivation fallbacks (used when a topic doesn't carry its own line)
# ---------------------------------------------------------------------------

A0_MOTIVATIONS_EN: tuple[str, ...] = (
    "Great start! You are building your English step by step.",
    "Excellent! You completed your first English step today.",
    "Well done — one small lesson is a real step forward.",
    "Keep going. Small steps every day make a big difference.",
    "Wonderful! You are learning faster than you think.",
)

A0_MOTIVATIONS_AR: tuple[str, ...] = (
    "بداية رائعة! أنت تبني لغتك الإنجليزية خطوة بخطوة.",
    "ممتاز! أكملت خطوتك الإنجليزية الأولى اليوم.",
    "أحسنت — درس صغير هو خطوة حقيقية إلى الأمام.",
    "واصل التعلم. الخطوات الصغيرة كل يوم تُحدث فرقاً كبيراً.",
    "رائع! أنت تتعلم أسرع مما تظن.",
)

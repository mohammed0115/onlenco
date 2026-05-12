# صيغة قاعدة البيانات للاستيراد إلى Onlenco

> هذه الوثيقة تربط بين محتوى المنهج (الأسابيع، الكورسات، الدروس، الأسئلة) وبين جداول Onlenco الفعلية (`courses`, `library`, `daily_learning`, جداول الأسئلة).

## مخطّط البيانات الكامل

```yaml
# ----- COURSE LEVEL -----
# Ensure CourseLevel "A0" exists. Onlenco already supports A0 via
# accounts.models.CEFR_CHOICES; CourseLevel must have a row.
course_levels:
  - code: A0
    name: "A0 — Absolute beginner"
    order: 0
    is_active: true

# ----- COURSES (12 total — one per week) -----
courses:
  - title_ar: "الحروف والأصوات الأساسية"
    title_en: "Letters & Basic Sounds"
    slug: "a0-c01-letters"
    level: A0
    order: 1
    is_free: true
    summary_ar: "تعرّف على 26 حرفاً وأصواتها الأساسية — التأسيس قبل القراءة."
    summary_en: "Meet 26 letters and their basic sounds — your foundation before reading."
    status: published
    estimated_minutes: 70
    week: 1     # cross-ref for daily_learning sequencing
  # ... courses 2..12 follow the same shape; see 03_courses.md

# ----- LESSONS — exemplar Week 1 -----
lessons:
  - course_slug: "a0-c01-letters"
    sort_order: 1
    day: 1
    title_ar: "اليوم 1 — الحروف A B C D"
    title_en: "Day 1 — Letters A B C D"
    lesson_type: vocabulary
    status: published
    duration_minutes: 10
    objective_ar: "يميّز الطالب 4 حروف ويربطها بكلمات يومية."
    objective_en: "Recognise 4 letters and link each to a daily-life word."
    content_ar: |
      اليوم نتعلم 4 حروف: A و B و C و D.
      كل حرف نربطه بكلمة سهلة.
      A = apple (تفاحة)
      B = book (كتاب)
      C = cat (قط)
      D = dog (كلب)
    content_en: |
      Today we learn 4 letters: A, B, C, D.
      Each letter links to a simple word.
      A = apple, B = book, C = cat, D = dog.
    audio_url: ""   # operator uploads .mp3 via admin OR `Lesson.audio_file`
    vocabulary:
      - { term: apple, translation: "تفاحة", pronunciation_ar: "أَبِل" }
      - { term: book,  translation: "كتاب",  pronunciation_ar: "بُك" }
      - { term: cat,   translation: "قط",   pronunciation_ar: "كات" }
      - { term: dog,   translation: "كلب",  pronunciation_ar: "دُوغ" }
    sentences:
      - "This is an apple."
      - "This is a book."
      - "This is a cat."
      - "This is a dog."
    speaking_prompts:
      - "Say: A."
      - "Say: This is a book."
    listening_prompts:
      - audio_key: "a0_w1_d1_letter_a"
      - audio_key: "a0_w1_d1_word_apple"
    writing_prompts:
      - "Write: apple"
      - "Write: A B C D"
    ai_tutor_intro: |
      Hello! Today we learn 4 letters. Are you ready?

# ----- LESSON QUIZ (end of every lesson + every Day 7) -----
lesson_quizzes:
  - lesson_slug: "a0-c01-letters-day-1"
    title: "Quick check — Letters A B C D"
    passing_score: 60
    questions:
      - question_type: multiple_choice
        question_text: "Which letter does 'apple' start with?"
        options: [A, B, C, D]
        correct_answer: A
        difficulty_score: 0.05
      # ... questions from question_bank/week_01.yaml mc_w1_001 through mc_w1_005

# ----- AI TUTOR PROMPTS (per lesson) -----
ai_tutor_prompts:
  - lesson_slug: "a0-c01-letters-day-1"
    prompt_ar: "قل: A."
    prompt_en: "Say: A."
    expected_student_answer: "A"
    correction_strategy: "echo-and-encourage"
    difficulty_score: 0.05

# ----- DAILY LEARNING TEMPLATES (per topic, drives daily_learning app) -----
# These already exist in daily_learning/services/a0_templates.py as
# A0Topic dataclasses. The 12-week curriculum extends the catalog:
daily_learning_topics:
  - slug: "u1_hello"          # already in code
  - slug: "u1_name"
  - slug: "u1_good_morning"
  # ... 17 existing topics
  # NEW topics for weeks 3-12 (catalog extension):
  - slug: "u3_age_ten"
    unit: 3
    target_word: "ten"
    target_sentence: "I am ten years old."
    quiz_question: "I ____ ten years old."
    quiz_options: ["am", "is", "are"]
    correct_answer: "am"
  # ... ~40 more topics one per (week, day) to reach 60-day catalog
```

## جداول Onlenco الفعلية المعنية

| ملف المنهج | جدول Onlenco | عملية الاستيراد |
|---|---|---|
| `03_courses.md` | `courses.Course` | `update_or_create` بـ `slug` |
| `weeks/week_XX.md` | `courses.Lesson` | `update_or_create` بـ (`course`, `sort_order`) |
| `question_bank/week_XX.yaml` | `courses.LessonQuestion` و/أو `learning_core.AdaptiveExercise` | `bulk_create` بعد فلترة بـ `text_hash` |
| `tutor/week_XX.md` | جدول جديد `tutor.AITutorPrompt` (يحتاج إنشاء) | يُستهلَك في `tutor/services/_chat.py` لاحقاً |
| `tests/end_of_a0.md` | `learning_core.WeeklyAssessment` (بـ `kind="milestone"`) | يُولَّد عند إكمال الأسبوع 12 |

## أمر إدارة مقترح

```bash
python manage.py import_a0_curriculum \
    --source Docs/curriculum/A0/ \
    --dry-run            # طباعة ما سيُستورد بدون كتابة
python manage.py import_a0_curriculum --source Docs/curriculum/A0/
```

**ما يفعله الأمر** (مقترح، غير منفَّذ بعد):

1. يقرأ `03_courses.md` ويُنشئ/يُحدِّث Course (12 مدخل).
2. لكل أسبوع، يقرأ ملف `weeks/week_XX.md` ويُنشئ 7 Lessons داخل Course.
3. يقرأ `question_bank/week_XX.yaml` ويُنشئ LessonQuestion لكل سؤال.
4. يقرأ `tutor/week_XX.md` ويملأ AITutorPrompt.
5. يقرأ `tests/end_of_a0.md` ويُنشئ WeeklyAssessment بـ `kind="milestone"`.

التنفيذ يحتاج بضع مئات من الأسطر — أستطيع بناءه عند الطلب.

## امتداد catalog `daily_learning`

`daily_learning/services/a0_templates.py` يحتوي اليوم على 17 موضوعاً (Unit 1-5). لتغطية 12 أسبوعاً × 5 أيام = 60 يوماً، يحتاج Onlenco إلى توسيع الـ catalog إلى ~60 موضوعاً.

**خطة التوسيع**:

```python
# في daily_learning/services/a0_templates.py
A0_TOPICS_EXTENDED = (
    *A0_TOPICS,  # الـ 17 الموجودة (الأسابيع 1-2)
    # أسبوع 3 — الأرقام والعمر
    _build_lesson(slug="u3_one_two_three", unit=3, ..., target_word="one"),
    _build_lesson(slug="u3_age", unit=3, ..., target_word="age"),
    # ... ~40 lesson definitions one per day for weeks 3-12
)
```

كل lesson في كل أسبوع يصبح موضوعاً واحداً، فيحصل الطالب على درس A0 جديد كل يوم لمدة 60 يوماً.

## أمثلة على البيانات الجاهزة للإدخال

ملفان جاهزان فوراً:

- `question_bank/week_01.yaml` — 82 سؤالاً مفصَّلاً (50 يبقى توليدها بالنمط)
- `tests/end_of_a0.md` — 50 سؤالاً للاختبار النهائي

## ملاحظة على الترقيم

- العدد المطلوب 230 سؤالاً × 12 أسبوعاً = **2,760 سؤالاً** لكل المنهج.
- ما هو مكتمل يدوياً الآن: 82 (أسبوع 1) + 50 (اختبار نهاية A0) = **132 سؤال**.
- المتبقي (~2,630 سؤالاً): يُنتج عبر `question_factory` app الموجود في Onlenco (`question_factory/services/bulk_generation_service.py`)، الذي يأخذ `QuestionBlueprint` ويولّد متغيرات. الـ blueprints الموجودة للحرف/الكلمة قابلة لإعادة الاستخدام.

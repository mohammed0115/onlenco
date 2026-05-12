# المرحلة 3 — قائمة الكورسات (12 كورس)

كل كورس يطابق أسبوعاً واحداً من خريطة الأسابيع. هذا يجعل البنية بسيطة لـ Onlenco — كورس واحد يمثّل وحدة تعليمية متكاملة، مع 7 دروس داخله (5 تعلم + 1 مراجعة + 1 اختبار).

| # | عنوان الكورس (AR / EN) | المستوى | المدة | الموضوع | الكلمات الجديدة |
|---|---|---|---|---|---|
| 1 | الحروف والأصوات الأساسية / Letters & Basic Sounds | A0 | أسبوع | تعرف الحروف 26 + 10 كلمات | 15 |
| 2 | التحيات والتعريف بالنفس / Greetings & Introductions | A0 | أسبوع | Hello, my name is, nice to meet you | 12 |
| 3 | الأرقام والعمر / Numbers & Age | A0 | أسبوع | 1-20 + "I am 20 years old" | 22 |
| 4 | البلد والجنسية / Country & Nationality | A0 | أسبوع | I am from..., I am Sudanese | 18 |
| 5 | العمل والدراسة / Work & Study | A0 | أسبوع | student, teacher, work, study | 15 |
| 6 | الأشياء اليومية / Everyday Objects | A0 | أسبوع | book, pen, phone, table, chair | 18 |
| 7 | الأسرة / Family | A0 | أسبوع | mother, father, brother, sister | 14 |
| 8 | الطعام والشراب / Food & Drink | A0 | أسبوع | bread, water, tea, coffee, food | 18 |
| 9 | الروتين اليومي / Daily Routine | A0 | أسبوع | wake up, eat, go, sleep | 15 |
| 10 | الأفعال الأساسية / Basic Verbs | A0 | أسبوع | go, eat, drink, work, like, have | 12 |
| 11 | محادثات قصيرة / Short Conversations | A0 | أسبوع | تبادل أسئلة وأجوبة | 10 |
| 12 | مراجعة A0 والاستعداد لـ A1 / A0 Review & A1 Prep | A0 | أسبوع | مراجعة شاملة | (مراجعة) |

## بنية الكورس داخل Onlenco

كل كورس يحوي **7 دروس** (مطابق لمدة أسبوع):

```
Course 1: "الحروف والأصوات الأساسية"
├── Lesson 1: A B C D — Day 1
├── Lesson 2: E F G H — Day 2
├── Lesson 3: I J K L M N — Day 3
├── Lesson 4: O P Q R S T — Day 4
├── Lesson 5: U V W X Y Z — Day 5
├── Lesson 6: مراجعة الحروف — Day 6 (Review)
└── Lesson 7: اختبار الحروف — Day 7 (Test)
```

كل درس يحوي:
- محتوى تعليمي (`Lesson.content_html`)
- صوت (`Lesson.audio_file` أو `audio_url`)
- مفردات (`LessonResource` من نوع `vocabulary`)
- اختبار قصير (`LessonQuiz` + 5-10 `LessonQuestion`)
- نشاط معلم (`AITutorPrompt` خاص بالدرس)

## ربط الكورس بـ `daily_learning`

كل يوم في `daily_learning`:
1. يقرأ الكورس المناسب لمستوى الطالب وعدد الأيام المُكتمَلة.
2. يفتح Lesson اليوم الحالي.
3. يبني `DailyLearningPlan` بـ 6 عناصر من Lesson + (اختياري) مراجعة كلمة سابقة.

نقطة الاتصال في الكود: `daily_learning/services/daily_plan_generator.py`. الكلمات والجمل التي يستخدمها مولّد A0 حالياً ستُحدَّث لتقرأ من `Lesson.vocabulary` و `Lesson.sentences` بدلاً من القائمة الثابتة في `a0_templates.py`.

## مخطّط Course (للاستيراد)

```yaml
courses:
  - title_ar: "الحروف والأصوات الأساسية"
    title_en: "Letters & Basic Sounds"
    slug: "a0-c1-letters"
    level: "A0"
    order: 1
    is_free: true
    summary_ar: "تعرّف على 26 حرفاً وأصواتها — تأسيس قبل القراءة."
    summary_en: "Meet 26 letters and their sounds — your foundation before reading."
    estimated_minutes: 70  # 7 lessons × 10 minutes
    lessons:
      - { sort_order: 1, day: 1, type: "vocabulary", title_ar: "A B C D",  audio: true }
      - { sort_order: 2, day: 2, type: "vocabulary", title_ar: "E F G H",  audio: true }
      # ...
      - { sort_order: 6, day: 6, type: "review",     title_ar: "مراجعة الأسبوع", audio: true }
      - { sort_order: 7, day: 7, type: "mixed",      title_ar: "اختبار الأسبوع 1", quiz: true }
```

البنية الكاملة في كل كورس مفصّلة في الملف الخاص بكل أسبوع تحت `weeks/week_XX.md`.

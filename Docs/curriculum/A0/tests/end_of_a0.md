# اختبار نهاية A0 (الأسبوع 12، اليوم 7)

50 سؤالاً عبر 6 مهارات. الوقت 30-40 دقيقة. علامة النجاح 70% (35 من 50).

## التوزيع

| المهارة | عدد الأسئلة | الوزن |
|---|---|---|
| الحروف والأصوات | 8 | 16% |
| التحيات والتعريف | 6 | 12% |
| الأرقام والعمر | 6 | 12% |
| البلد والجنسية | 5 | 10% |
| الأشياء اليومية والأسرة | 8 | 16% |
| الأفعال والروتين | 6 | 12% |
| الاستماع | 4 | 8% |
| التحدث | 4 | 8% |
| الكتابة | 3 | 6% |
| **المجموع** | **50** | **100%** |

---

## القسم 1 — الحروف والأصوات (8 أسئلة)

```yaml
- id: e0_test_q01
  type: mcq
  question: "Which letter does 'apple' start with?"
  options: [A, B, C, D]
  correct: A
  points: 1

- id: e0_test_q02
  type: mcq
  question: "Which letter does 'water' start with?"
  options: [V, W, F, U]
  correct: W
  points: 1

- id: e0_test_q03
  type: fill_blank
  question: "____ook is on the desk."
  correct: B
  points: 1

- id: e0_test_q04
  type: true_false
  statement: "There are 26 letters in English"
  correct: true
  points: 1

- id: e0_test_q05
  type: listening
  audio_key: a0_test_letter_p_vs_b
  prompt: "Which letter do you hear?"
  options: [P, B]
  correct: P
  points: 2   # listening discrimination is weighted higher

- id: e0_test_q06
  type: word_match
  prompt: "Match each letter to a word that starts with it"
  pairs:
    - { left: A, right: apple }
    - { left: B, right: book }
    - { left: C, right: cat }
    - { left: D, right: dog }
  points: 4   # 1 per correct pairing

- id: e0_test_q07
  type: speaking
  prompt_ar: "قل بصوت عال: A B C D"
  target_text: "A B C D"
  points: 2

- id: e0_test_q08
  type: writing
  prompt_ar: "اكتب الكلمة: 'تفاحة'"
  correct: apple
  points: 1
```

## القسم 2 — التحيات والتعريف (6 أسئلة)

```yaml
- id: e0_test_q09
  type: mcq
  question: "In the morning we say:"
  options: ["Good morning", "Good night", "Goodbye"]
  correct: "Good morning"
  points: 1

- id: e0_test_q10
  type: word_order
  scrambled: ["is", "Ahmed", "My", "name"]
  correct: "My name is Ahmed"
  points: 2

- id: e0_test_q11
  type: fill_blank
  question: "____ name is Sara."
  correct: My
  options: [My, I, Me]
  points: 1

- id: e0_test_q12
  type: mcq
  question: "Reply to 'Nice to meet you.'"
  options: ["Nice to meet you too.", "Goodbye.", "I am five."]
  correct: "Nice to meet you too."
  points: 1

- id: e0_test_q13
  type: speaking
  prompt_ar: "قدّم نفسك بالإنجليزية: قل اسمك وعمرك وبلدك"
  target_text: "My name is ___. I am ___. I am from ___."
  rubric:
    - 2 points: 3 complete sentences with no major missing words
    - 1 point: 2 of the 3 sentences complete
    - 0 points: less than 2 sentences
  points: 2

- id: e0_test_q14
  type: writing
  prompt_ar: "اكتب: 'اسمي ساره'"
  correct: "My name is Sara"
  points: 1
```

## القسم 3 — الأرقام والعمر (6 أسئلة)

```yaml
- id: e0_test_q15
  type: match_pairs
  pairs:
    - { left: 1, right: one }
    - { left: 5, right: five }
    - { left: 10, right: ten }
  points: 3

- id: e0_test_q16
  type: fill_blank
  question: "I ____ twenty years old."
  options: [am, is, are]
  correct: am
  points: 1

- id: e0_test_q17
  type: mcq
  question: "How do you say '15' in English?"
  options: [fifteen, fifty, five-teen]
  correct: fifteen
  points: 1

- id: e0_test_q18
  type: word_order
  scrambled: ["years", "ten", "I", "am", "old"]
  correct: "I am ten years old"
  points: 2

- id: e0_test_q19
  type: speaking
  prompt_ar: "قل عمرك بالإنجليزية"
  target_text: "I am ___ years old"
  points: 1
```

## القسم 4 — البلد والجنسية (5 أسئلة)

```yaml
- id: e0_test_q20
  type: mcq
  question: "I am from Sudan. I am:"
  options: [Sudanese, Sudaner, Sudany]
  correct: Sudanese
  points: 1

- id: e0_test_q21
  type: match_pairs
  pairs:
    - { left: Egypt, right: Egyptian }
    - { left: Saudi Arabia, right: Saudi }
    - { left: Yemen, right: Yemeni }
  points: 3

- id: e0_test_q22
  type: word_order
  scrambled: ["from", "I", "Sudan", "am"]
  correct: "I am from Sudan"
  points: 1
```

## القسم 5 — الأشياء اليومية والأسرة (8 أسئلة)

```yaml
- id: e0_test_q23
  type: mcq
  question: "What is this 📱?"
  options: [phone, book, pen, cat]
  correct: phone
  points: 1

- id: e0_test_q24
  type: mcq
  question: "This is my mother's husband. He is my:"
  options: [father, brother, son]
  correct: father
  points: 1

- id: e0_test_q25
  type: fill_blank
  question: "This is ____ book. It is mine."
  options: [my, your, his]
  correct: my
  points: 1

- id: e0_test_q26
  type: word_order
  scrambled: ["a", "have", "I", "phone"]
  correct: "I have a phone"
  points: 1

- id: e0_test_q27
  type: true_false
  statement: "We say 'an apple' (not 'a apple')"
  correct: true
  points: 1

- id: e0_test_q28
  type: match_pairs
  pairs:
    - { left: 📕, right: book }
    - { left: ✏️, right: pencil }
    - { left: 🪑, right: chair }
  points: 3
```

## القسم 6 — الأفعال والروتين (6 أسئلة)

```yaml
- id: e0_test_q29
  type: mcq
  question: "____ I wake up at 6."
  options: ["Every day", "Yesterday", "Tomorrow"]
  correct: "Every day"
  points: 1

- id: e0_test_q30
  type: fill_blank
  question: "I ____ water every day."
  options: [drink, eat, read]
  correct: drink
  points: 1

- id: e0_test_q31
  type: word_order
  scrambled: ["work", "I", "to", "go"]
  correct: "I go to work"
  points: 1

- id: e0_test_q32
  type: mcq
  question: "I ____ English."
  options: [speak, hear, write]
  correct: speak
  points: 1

- id: e0_test_q33
  type: speaking
  prompt_ar: "صف يومك في 3 جمل"
  target_text: "I wake up at ___. I eat ___. I go to ___."
  points: 2
```

## القسم 7 — الاستماع (4 أسئلة)

```yaml
- id: e0_test_q34
  type: listening
  audio_key: a0_test_word_chair
  options: [chair, share, cheer]
  correct: chair
  points: 1

- id: e0_test_q35
  type: listening
  audio_key: a0_test_sentence_morning
  prompt: "What did you hear?"
  options:
    - "Good morning."
    - "Good evening."
    - "Goodbye."
  correct: "Good morning."
  points: 2

- id: e0_test_q36
  type: listening_dictation
  audio_key: a0_test_sentence_my_name
  prompt: "Write what you hear"
  correct: "My name is Sara"
  points: 2

- id: e0_test_q37
  type: listening
  audio_key: a0_test_age
  prompt: "How old is the speaker?"
  options: [10, 15, 20]
  correct: 20
  points: 1
```

## القسم 8 — التحدث (4 أسئلة، STT-scored)

```yaml
- id: e0_test_q38
  type: speaking
  prompt_ar: "ألقِ التحية واسأل عن اسمي"
  target_text: "Hello. What is your name?"
  points: 2

- id: e0_test_q39
  type: speaking
  prompt_ar: "قل من أين أنت"
  target_text: "I am from ___"
  points: 1

- id: e0_test_q40
  type: speaking
  prompt_ar: "اطلب الماء"
  target_text: "Water, please"
  accepted_variants: ["I want water please", "Can I have water"]
  points: 1

- id: e0_test_q41
  type: speaking
  prompt_ar: "ودّع المعلم"
  target_text: "Goodbye"
  accepted_variants: ["Good night", "See you tomorrow"]
  points: 1
```

## القسم 9 — الكتابة (3 أسئلة)

```yaml
- id: e0_test_q42
  type: writing
  prompt_ar: "اكتب 3 جمل عن نفسك"
  rubric:
    - 3 points: 3 complete correct sentences
    - 2 points: 2 complete sentences
    - 1 point: 1 complete sentence
    - 0 points: nothing usable
  example_answer: "My name is Sara. I am from Sudan. I am a student."
  points: 3

- id: e0_test_q43
  type: writing_short
  prompt_ar: "اكتب جملة بسيطة عن طعامك المفضل"
  example_answer: "I like rice"
  points: 1

- id: e0_test_q44
  type: writing_letters
  prompt_ar: "اكتب الأبجدية الإنجليزية"
  correct: "A B C D E F G H I J K L M N O P Q R S T U V W X Y Z"
  case_sensitive: false
  points: 2
```

## القسم 10 — ست محادثات قصيرة (6 أسئلة)

```yaml
- id: e0_test_q45_to_50
  type: conversation_scoring
  scenarios:
    - { prompt: "AI says 'Hello.' You say:", expected: ["Hello.", "Hi."] }
    - { prompt: "AI says 'What is your name?' You say:", expected: ["My name is ___."] }
    - { prompt: "AI says 'How are you?' You say:", expected: ["I am fine, thank you.", "Good, thank you."] }
    - { prompt: "AI says 'Where are you from?' You say:", expected: ["I am from ___."] }
    - { prompt: "AI says 'Nice to meet you.' You say:", expected: ["Nice to meet you too."] }
    - { prompt: "AI says 'Goodbye.' You say:", expected: ["Goodbye.", "See you tomorrow.", "Good night."] }
  points_per_scenario: 1
```

---

## التصحيح وعتبات النجاح

| الفئة | الطريقة |
|---|---|
| MCQ / true-false / matching / word-order | آلي |
| Listening | آلي (مقارنة الإجابة المختارة) |
| Listening dictation | مقارنة نصية مع تجاهل المسافات والحالة |
| Speaking | STT (Whisper) ثم مقارنة نصية وأخذ أعلى تطابق من الـ `accepted_variants` |
| Writing | مقارنة نصية + AI scoring للجمل الحرّة |

**درجة النجاح**: 35 من 50 (70%).

**درجة الامتياز**: 45+ من 50 (90%) — يحصل الطالب على شارة "A0 Graduate Excellence".

**عند النجاح**: تُفعَّل خدمة `a0_progression_service.maybe_promote_a0_to_a1` يدوياً عند نهاية الاختبار وترقّى الطالب إلى A1.

**عند الرسوب**:
- إذا 30-34: يُعاد اختبار قصير بعد أسبوع من المراجعة (10 أسئلة فقط).
- إذا أقل من 30: يُعاد الأسبوع 12 كاملاً.

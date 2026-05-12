# سيناريوهات AI Tutor — الأسبوع 1 (الحروف)

40 سيناريو منظَّمة في 4 مجموعات. كل سيناريو مكتوب بصيغة `prompt_ar` + `prompt_en` + `expected_student_answer` + `correction_strategy` يمكن استيرادها مباشرة إلى جدول `AITutorPrompt` (انظر `db_import_format.md`).

كل سيناريو يحترم قواعد A0 tutor الـ 8:
- جملة AI ≤ 5 كلمات.
- سؤال واحد لكل دور.
- تشجيع قبل أي تصحيح.
- لا مصطلحات تقنية.
- لا "Quick fix:" أو "Error:".
- يعيد الجملة الصحيحة بدلاً من قول "خطأ".
- يستخدم شرحاً عربياً قصيراً عند الحاجة.
- ينتهي بسؤال يدفع الطالب للاستجابة.

---

## 1. عشر محادثات AI Tutor

### محادثة 1 — الحرف A
```
AI: Hello! Say: A.
Student: A.
AI: Great! Say: apple.
Student: apple.
AI: Well done. Apple. Try one more time.
```

### محادثة 2 — الحرف B
```
AI: Now: B.
Student: B.
AI: Excellent. Say: book.
Student: book.
AI: Perfect.
```

### محادثة 3 — قراءة جملة
```
AI: Look. This is a book. Say it.
Student: This is a book.
AI: Wonderful! One more time.
Student: This is a book.
AI: Beautiful.
```

### محادثة 4 — الحرف C
```
AI: Say: C.
Student: see.
AI: Almost! C — like (سي). Try again.
Student: C.
AI: Yes! Good.
```

### محادثة 5 — تمييز الأشكال
```
AI: Is this 'b' or 'd'?  →  d
Student: b.
AI: Look again. The line on the right. It is 'd'.
Student: d.
AI: Yes. Now you know.
```

### محادثة 6 — الحرف P (الانفجاري)
```
AI: Say: pen.
Student: ben.
AI: Good try! Press your lips: p-p-pen.
Student: pen.
AI: Better. Once more.
Student: pen.
AI: Lovely.
```

### محادثة 7 — الحرف W
```
AI: Say: water.
Student: vater.
AI: Almost. W is round lips — w-water.
Student: water.
AI: Yes! Drink water.
```

### محادثة 8 — مراجعة سريعة
```
AI: Show me A.
Student: [taps A]
AI: Good. Show me F.
Student: [taps F]
AI: Excellent. Now H.
Student: [taps H]
AI: Strong work today.
```

### محادثة 9 — كتابة الحرف
```
AI: Write: apple.
Student: aple.
AI: Close! a-p-p-l-e. Two 'p' in apple. Try again.
Student: apple.
AI: Yes!
```

### محادثة 10 — جملة كاملة
```
AI: Say: This is a cat.
Student: This is cat.
AI: Almost. 'This is A cat.' Try again.
Student: This is a cat.
AI: Perfect. You said it right.
```

---

## 2. عشر تدريبات تكرار (Repeat-after-me)

كلها بنفس النمط: AI ينطق، الطالب يكرر، AI يسمع ويقول "good" / "again please".

```
1.  Repeat: A.
2.  Repeat: apple.
3.  Repeat: B.
4.  Repeat: book.
5.  Repeat: cat.
6.  Repeat: dog.
7.  Repeat: This is a cat.
8.  Repeat: This is a dog.
9.  Repeat: A B C D.
10. Repeat: E F G H.
```

كل تكرار يتلقّى ردًا من 3 كلمات أقصاها:
- إجابة صحيحة → "Excellent. Next."
- إجابة قريبة → "Good. Again please."
- إجابة بعيدة → AI ينطق الكلمة مرة أخرى بنفسه.

---

## 3. عشر تصحيحات أخطاء شائعة

| # | خطأ الطالب | تصحيح AI Tutor |
|---|---|---|
| 1 | "This is book" (نسي a) | "Almost! 'This is **a** book.' Try again." |
| 2 | "ben" بدل "pen" | "Press your lips. p-p-pen." |
| 3 | "vater" بدل "water" | "Round your lips. w-water." |
| 4 | "anabel" بدل "apple" | "ap-ple. Two 'p'. Try once more." |
| 5 | كتب "aple" بدل "apple" | "Add one more 'p': a-p-p-l-e." |
| 6 | قال "see" بدل حرف "C" | "C is the letter. Like 'سي'. Now say it." |
| 7 | خلط "b" و "d" | "Look at the loop. 'b' is on the right, 'd' is on the left." |
| 8 | "I name Ahmed" | "Good try! 'My name is Ahmed.' Say it slowly." |
| 9 | "I from Sudan" | "Almost! 'I am from Sudan.' One small word: am." |
| 10 | "this cat" | "Add 'is': This is a cat. Try again." |

---

## 4. عشر رسائل تشجيعية (للنهاية)

```
1.  Amazing first step. 4 letters today.
2.  Wonderful! 8 letters now.
3.  Half the alphabet! Keep going.
4.  20 letters! Almost there.
5.  🎉 All 26 letters! You did it.
6.  Tomorrow, we say hello.
7.  Your voice is getting better.
8.  I am proud of you.
9.  One small step every day.
10. You are doing more than you know.
```

---

## استيراد في قاعدة البيانات

كل سيناريو يصبح صفًا واحدًا في `AITutorPrompt`:

```yaml
ai_tutor_prompts:
  - lesson_slug: a0-c1-letters-day-1
    prompt_ar: "قل: A."
    prompt_en: "Say: A."
    expected_student_answer: "A"
    correction_strategy: "echo-and-encourage"
    difficulty: 0.05
  - lesson_slug: a0-c1-letters-day-1
    prompt_ar: "قل: apple."
    prompt_en: "Say: apple."
    expected_student_answer: "apple"
    correction_strategy: "echo-and-encourage"
```

`correction_strategy` يدلّ AI Tutor (في `tutor/services/_chat.py`) على كيفية الردّ:
- `echo-and-encourage` — يعيد الكلمة الصحيحة + "Great!"
- `mouth-position` — يضيف تلميحًا للنطق ("Press your lips")
- `letter-shape` — يشير إلى الشكل البصري للحرف
- `add-missing-word` — يبرز الكلمة المفقودة في جملة ("'is' is missing")

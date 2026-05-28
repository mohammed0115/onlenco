## Prompt 14 — Master Execution Checklist

استخدم هذه القائمة بعد كل Prompt للتأكد من أنك لا تنتقل قبل اكتمال المرحلة.

### المرحلة 1 — Methodology
- [ ] تم إنشاء ONLENCO_BEGINNER_METHOD_SPEC.md
- [ ] لم يتم نسخ نصوص من الكتاب
- [ ] تم تحديد lesson structure
- [ ] تم تحديد quiz structure
- [ ] تم تحديد media/audio structure

### المرحلة 2 — Database
- [ ] LessonMedia موجود أو تم اقتراحه
- [ ] QuestionMedia موجود أو تم اقتراحه
- [ ] LessonAudioScript موجود
- [ ] LessonImagePrompt موجود
- [ ] LessonChecklist موجود
- [ ] صفحة الدرس تعمل بدون media

### المرحلة 3 — Blueprint
- [ ] تم إنشاء 48 Learning Units
- [ ] كل Unit لها New Language
- [ ] كل Unit لها Vocabulary
- [ ] كل Unit لها New Skill
- [ ] كل Unit لها AI Tutor goal
- [ ] كل Unit لها image/audio ideas

### المرحلة 4 — Seed
- [ ] Course تم إنشاؤه
- [ ] 48 Units تم إنشاؤها
- [ ] content_html موجود
- [ ] content_ar موجود
- [ ] image prompts موجودة
- [ ] audio scripts موجودة
- [ ] checklist موجود
- [ ] seed idempotent

### المرحلة 5 — Quiz Bank
- [ ] 48 Quizzes
- [ ] كل Quiz فيه 8 إلى 12 سؤال
- [ ] أسئلة Vocabulary
- [ ] أسئلة Grammar
- [ ] Speaking Prompt
- [ ] Listening Placeholder
- [ ] الأسئلة أصلية

### المرحلة 6 — UI
- [ ] Lesson page تعرض learning points
- [ ] تعرض visual guide
- [ ] تعرض vocabulary
- [ ] تعرض mini dialogue
- [ ] تعرض quiz
- [ ] تعرض AI Tutor button
- [ ] تدعم RTL/LTR
- [ ] لا يوجد 500 error

### المرحلة 7 — AI Images
- [ ] command موجود
- [ ] dry-run
- [ ] unit/range/all
- [ ] no duplicate
- [ ] media saved
- [ ] cost logs

### المرحلة 8 — AI Audio
- [ ] command موجود
- [ ] text cleaner
- [ ] لا يقرأ HTML/underscores
- [ ] unit/range/all
- [ ] no duplicate
- [ ] audio saved
- [ ] cost logs

### المرحلة 9 — AI Tutor
- [ ] lesson context
- [ ] beginner style
- [ ] American English
- [ ] one correction at a time
- [ ] progress saved

### المرحلة 10 — Reviews
- [ ] Reviews created
- [ ] unlock rules
- [ ] score saved
- [ ] feedback saved

### المرحلة 11 — QA
- [ ] Register flow
- [ ] Beginner selection
- [ ] Dashboard
- [ ] Unit page
- [ ] Quiz
- [ ] AI Tutor
- [ ] Review
- [ ] Logout/Login
- [ ] Placement not repeated

### المرحلة 12 — Fix
- [ ] P0 fixed
- [ ] P1 fixed
- [ ] tests passed
- [ ] check passed

### القرار النهائي
لا تعتبر الكورس جاهزًا إلا إذا:
- [ ] 48 Learning Units تعمل
- [ ] كل Unit لها Quiz
- [ ] صفحة الدرس لا تكسر
- [ ] AI Tutor مرتبط بالدرس
- [ ] الصور والصوت يمكن توليدها batch
- [ ] الطالب يستطيع إكمال الرحلة

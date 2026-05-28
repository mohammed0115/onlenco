# سلسلة برمتات Onlenco Beginner — 48 وحدة/موضوع

## Prompt 01 — تحليل منهجية الكتاب وتحويلها إلى مواصفة Onlenco

أنت خبير EdTech ومصمم مناهج لغة إنجليزية CEFR ومهندس Django كبير.

المشروع: Onlenco Academy

لدينا PDF مرجعي:
English for Everyone - Level 1 Beginner - Course Book

المطلوب:
حلل منهجية الكتاب فقط، ولا تنسخ منه النصوص أو الصور أو الصوت أو الأسئلة.

الهدف:
استخراج نمط تعليمي نطبقه داخل Onlenco بمحتوى أصلي.

مهم جدًا:
- لا تنسخ أي نص من الكتاب.
- لا تنسخ أي تمرين من الكتاب.
- لا تستخدم صور الكتاب.
- لا تستخدم صوت الكتاب.
- لا تقلد هوية DK أو ألوانها أو رسوماتها حرفيًا.
- استخدم الكتاب كمرجع للمنهجية والحجم والترتيب فقط.
- المطلوب American English.
- يجب أن تكون النتيجة قابلة للتحويل إلى Django models وseed commands.

استخرج من الكتاب:
1. كيف يبدأ الدرس؟
2. كيف يعرض New Language؟
3. كيف يعرض Vocabulary؟
4. كيف يشرح Grammar؟
5. كيف يستخدم الصور والرسومات؟
6. كيف يبني Practice؟
7. كيف يضيف Listening؟
8. كيف يضيف Speaking؟
9. كيف يستخدم Checklist؟
10. كيف يعمل Review بعد مجموعة دروس؟
11. كيف يربط الصوت بالدرس والتمرين؟
12. كيف يعرض التدرج من السهل إلى الأصعب؟

أنشئ ملف:
ONLENCO_BEGINNER_METHOD_SPEC.md

يجب أن يحتوي:
- Lesson Structure
- Quiz Structure
- Media Structure
- Audio Structure
- Review Structure
- AI Tutor Drill Structure
- Copyright Safety Rules
- American English Rules
- Arabic Support Rules
- Student Experience Flow

التقرير النهائي بالعربي:
- ماذا استنتجت من الكتاب؟
- ما النمط الذي سنطبقه في Onlenco؟
- كيف سنتجنب حقوق الملكية؟
- هل نحتاج تعديل database؟
- ما الملفات التي أنشأتها؟
- ما الخطوة التالية؟

---

## Prompt 02 — تجهيز قاعدة البيانات للدرس البصري والصوتي

أنت مهندس Django Production كبير.

المشروع: Onlenco Academy

قبل بناء المنهج، افحص قاعدة البيانات الحالية وتأكد أنها تستطيع دعم درس تعليمي مثل الكتب الاحترافية.

كل Topic Unit / Lesson يجب أن يدعم:
- محتوى إنجليزي
- محتوى عربي
- صور مولدة أو مرفوعة
- صوت مولد أو مرفوع
- فيديو اختياري
- quiz
- listening placeholder
- speaking prompt
- AI Tutor drill
- checklist
- review بعد مجموعة وحدات

افحص models الحالية:
- Course
- CourseLevel
- CourseUnit
- Lesson
- LessonQuiz
- LessonQuestion
- StudentProgress
- LessonProgress
- Exam / Assessment إن وجدت
- AI Tutor models إن وجدت
- أي Media models موجودة

المطلوب:
1. لا تبني المنهج الآن.
2. فقط افحص هل النظام جاهز.
3. إذا يوجد نقص، أضف models آمنة بدون كسر البيانات القديمة.
4. لا تجعل media مطلوبة.
5. صفحة الدرس يجب أن تعمل حتى بدون media.

Models المقترحة إذا غير موجودة:

LessonMedia:
- lesson = ForeignKey(Lesson)
- media_type = image/audio/video/document
- title
- title_ar
- file
- external_url
- language = en/ar
- alt_text
- transcript
- duration_seconds
- sort_order
- is_active
- generated_by_ai
- generation_prompt
- created_at
- updated_at

QuestionMedia:
- question = ForeignKey(LessonQuestion)
- media_type = image/audio/video
- file
- external_url
- alt_text
- transcript
- language
- sort_order
- is_active
- generation_prompt

LessonChecklist:
- lesson = ForeignKey(Lesson)
- text_en
- text_ar
- sort_order
- is_active

LessonAudioScript:
- lesson = ForeignKey(Lesson)
- script_type = intro/vocabulary/examples/dialogue/listening/quiz/speaking
- script_text
- voice_style = friendly_teacher/slow_beginner/dialogue
- accent = american
- generated_audio = FileField optional
- is_generated
- created_at
- updated_at

LessonImagePrompt:
- lesson = ForeignKey(Lesson)
- prompt_type = cover/vocabulary/grammar/quiz
- prompt
- generated_image = ImageField optional
- is_generated
- created_at
- updated_at

مهم:
- migrations آمنة.
- استخدم blank=True و null=True عند الحاجة.
- لا تكسر seed data القديمة.
- لا تكسر dashboard.
- لا تكسر teacher portal.
- لا تجعل code مطلوبًا يدويًا.
- إن كان code مطلوبًا، استخدم auto code generator.

أضف اختبارات:
- test_lesson_page_works_without_media
- test_lesson_can_have_image_media
- test_lesson_can_have_audio_media
- test_lesson_can_have_video_media
- test_lesson_checklist_items
- test_question_can_have_media
- test_lesson_audio_script_saved
- test_lesson_image_prompt_saved
- test_media_optional_not_required
- test_existing_lessons_still_render

شغّل:
DJANGO_SETTINGS_MODULE=config.settings.test python manage.py test courses
DJANGO_SETTINGS_MODULE=config.settings.test python manage.py test student_portal
DJANGO_SETTINGS_MODULE=config.settings.test python manage.py check

التقرير النهائي بالعربي:
- هل النظام جاهز لدروس بصور وصوت؟
- ما النماذج التي أضيفت؟
- هل صفحة الدرس تعمل بدون وسائط؟
- هل توجد migrations؟
- هل توجد مشاكل متبقية؟
- هل ننتقل لبناء Blueprint؟

---

## Prompt 03 — بناء Blueprint للكورس المبتدئ من الصفر: 48 وحدة / موضوع

أنت خبير CEFR ومصمم مناهج إنجليزية ومهندس Django.

المشروع: Onlenco Academy

المطلوب:
بناء Blueprint كامل لكورس مبتدئ من الصفر بنفس حجم ومنهجية الكتاب المرجعي، لكن بمحتوى Onlenco أصلي.

اسم الكورس:
Onlenco Beginner English Foundation — American English

المستوى:
A0/A1 Beginner

الهيكل المطلوب:
- 1 Course
- 48 Learning Units / Topics
- كل Topic Unit عبارة عن درس كامل مستقل
- كل Topic Unit له Quiz
- كل Topic Unit له Listening + Speaking
- كل Topic Unit له Image Prompts + Audio Scripts
- Reviews بعد مجموعات من الوحدات

مهم:
- لا تنسخ أسماء الجمل من الكتاب.
- لا تنسخ التمارين.
- لا تستخدم صور الكتاب.
- لا تستخدم صوت الكتاب.
- استخدم نفس التدرج التعليمي فقط.
- المحتوى مناسب لطالب عربي يبدأ من الصفر.
- American English فقط.

اقترح خريطة 48 Learning Units / Topics بالترتيب التالي:

01. Introducing Yourself
02. Countries
03. Talking About Yourself
04. Family and Pets
05. Things You Have
06. Using Apostrophes
07. Everyday Things
08. Talking About Your Things
09. Jobs
10. Talking About Your Job
11. Telling the Time
12. Daily Routines
13. Describing Your Day
14. Describing Your Week
15. Negatives with To Be
16. More Negatives
17. Simple Questions
18. Answering Questions
19. Asking Questions
20. Around Town
21. Talking About Your Town
22. Using A, An, and The
23. Orders and Directions
24. Joining Sentences
25. Describing Places
26. Giving Reasons
27. Around the House
28. The Things I Have
29. What Do You Have?
30. Food and Drink
31. Counting
32. Measuring
33. Clothes
34. At the Store
35. Describing Things
36. Sports
37. Talking About Sports
38. Hobbies and Pastimes
39. Free Time
40. Likes and Dislikes
41. Music
42. Expressing Preference
43. Abilities
44. What You Can and Can’t Do
45. Describing Actions
46. Describing Ability
47. Wishes and Desires
48. Studying

لكل Topic Unit في الـ blueprint اكتب:
- unit_number
- title_en
- title_ar
- cefr_level
- estimated_minutes
- new_language
- vocabulary_focus
- new_skill
- grammar_focus
- pronunciation_focus إن وجد
- speaking_goal
- listening_goal
- image_idea
- audio_idea
- quiz_goal
- ai_tutor_goal
- checklist_items
- review_group

أنشئ ملف:
ONLENCO_BEGINNER_48_UNITS_BLUEPRINT.md

لا تكتب seed data الآن.
فقط Blueprint.

يجب أن توضح كيف سيتم تنفيذها في النظام:
الخيار A:
Course → 48 Lessons وتعرض في الواجهة باسم Learning Units

الخيار B:
إضافة LearningModule model إن كان النظام يحتاج فصلًا أوضح

قرر الأفضل حسب بنية المشروع الحالية.

التقرير النهائي بالعربي:
- عدد الوحدات
- هل الترتيب منطقي؟
- هل كل Topic له هدف تعليمي واضح؟
- هل مناسب للمبتدئ من الصفر؟
- هل النظام يحتاج LearningModule model؟
- ما الخطوة التالية؟

---

## Prompt 04 — إنشاء Seed للكورس و48 وحدة بدون صور وصوت فعلي

أنت مهندس Django كبير.

اعتمد على:
ONLENCO_BEGINNER_48_UNITS_BLUEPRINT.md

المطلوب:
إنشاء management command يبني كورس Onlenco Beginner داخل قاعدة البيانات.

اسم الأمر:
courses/management/commands/seed_onlenco_beginner_48_units.py

الهدف:
إنشاء:
- 1 Course
- 48 Learning Units / Lessons
- Lesson content
- Lesson checklist
- Lesson image prompts
- Lesson audio scripts
- Review placeholders بعد مجموعات الوحدات

مهم:
- لا تستخدم ملف seed_data القديم.
- لا تعتمد على PDF كمصدر نصوص.
- لا تنسخ محتوى الكتاب.
- كل المحتوى أصلي.
- American English.
- دعم شرح عربي داخل content_ar.
- الكود idempotent.
- تشغيله مرتين لا يكرر البيانات.
- لا تحتاج لإدخال code يدويًا؛ استخدم auto code generator إن موجود.

كل Topic Unit / Lesson يجب أن يحتوي داخل content_html:
1. Lesson Goal
2. New Language
3. Key Vocabulary
4. Grammar Focus
5. Visual Guide Description
6. Examples
7. Mini Dialogue
8. Practice Activity
9. Listening Task Placeholder
10. Speaking Practice
11. AI Tutor Drill
12. Checklist

داخل content_ar:
- شرح هدف الدرس بالعربي
- شرح القاعدة بالعربي
- ترجمة الأمثلة
- تعليمات التحدث
- ملاحظة للطالب العربي
- تنبيه على النطق أو الخطأ الشائع

أضف لكل Lesson:
- lesson_cover_image_prompt
- vocabulary_image_prompt
- grammar_visual_prompt
- quiz_image_prompt
- lesson_intro_audio_script
- vocabulary_audio_script
- examples_audio_script
- mini_dialogue_audio_script
- listening_audio_script
- speaking_model_audio_script

لا تولد ملفات media الآن.
فقط خزّن prompts/scripts.

مفاتيح منع التكرار:
- course slug
- lesson order / unit number
- lesson code
- checklist lesson + order
- image prompt lesson + prompt_type
- audio script lesson + script_type

أضف اختبارات:
- test_seed_onlenco_beginner_48_units_runs
- test_course_created
- test_course_has_48_learning_units
- test_each_unit_has_content_html_and_content_ar
- test_each_unit_has_checklist
- test_each_unit_has_image_prompts
- test_each_unit_has_audio_scripts
- test_each_unit_has_ai_tutor_drill
- test_content_is_original_not_copied
- test_seed_is_idempotent

شغّل:
DJANGO_SETTINGS_MODULE=config.settings.test python manage.py test courses
DJANGO_SETTINGS_MODULE=config.settings.test python manage.py check

التقرير النهائي بالعربي:
- ماذا تم إنشاؤه؟
- عدد الوحدات
- هل كل Topic فيه محتوى عربي/إنجليزي؟
- هل كل Topic فيه image prompts؟
- هل كل Topic فيه audio scripts؟
- هل كل Topic فيه AI Tutor Drill؟
- هل seed آمن للتشغيل أكثر من مرة؟
- ما المشاكل المتبقية؟

---

## Prompt 05 — بناء Quiz Bank لكل وحدة بنفس نمط التمارين

أنت خبير اختبارات لغة إنجليزية ومهندس Django.

المشروع: Onlenco Academy

اعتمد على الكورس الذي تم إنشاؤه:
Onlenco Beginner English Foundation — American English

المطلوب:
بناء Quiz لكل واحدة من 48 Learning Units بنفس منهجية تمارين الكتاب، لكن بأسئلة Onlenco أصلية بالكامل.

مهم:
- لا تنسخ أسئلة الكتاب.
- لا تنسخ الجمل من الكتاب.
- لا تستخدم صور الكتاب.
- لا تستخدم الصوت.
- الأسئلة يجب أن تكون أصلية ومناسبة للمبتدئ.
- American English.

لكل Learning Unit:
أنشئ Quiz واحد.

كل Quiz يحتوي 8 إلى 12 سؤال:
- 3 Vocabulary
- 3 Grammar
- 1 Reading / Mini Dialogue
- 1 Speaking Prompt
- 1 Listening Placeholder
- سؤال إضافي matching أو sentence_order إن كان مدعومًا

أنواع الأسئلة:
- multiple_choice
- fill_blank
- true_false
- sentence_order
- matching إذا مدعوم
- short_answer
- speaking_prompt
- listening_placeholder

كل سؤال يجب أن يحتوي:
- question_text
- question_text_ar
- question_type
- options
- correct_answer
- explanation إن كان مدعومًا
- skill: grammar/vocabulary/reading/listening/speaking
- difficulty: easy/medium
- cefr_level: A0/A1
- is_active=True

Listening Placeholder:
لا تضع ملف صوت.
ضع:
- audio_required=True
- audio_status="pending_generation"
- listening_script أصلي مناسب للسؤال

Speaking Prompt:
يجب أن يحتوي:
- student_prompt
- ai_tutor_instruction
- expected_keywords
- correction_style="gentle"
- accent="american"

لا تجعل أسئلة A0/A1 صعبة.
اجعلها قصيرة وواضحة ومناسبة لطالب عربي مبتدئ.

أضف اختبارات:
- test_each_learning_unit_has_quiz
- test_each_quiz_has_8_to_12_questions
- test_each_quiz_has_vocabulary_questions
- test_each_quiz_has_grammar_questions
- test_each_quiz_has_speaking_prompt
- test_each_quiz_has_listening_placeholder
- test_questions_have_arabic_and_english
- test_seed_quiz_is_idempotent
- test_no_copied_pdf_questions

شغّل:
DJANGO_SETTINGS_MODULE=config.settings.test python manage.py test courses exams
DJANGO_SETTINGS_MODULE=config.settings.test python manage.py check

التقرير النهائي بالعربي:
- عدد quizzes
- عدد questions
- أنواع الأسئلة
- هل كل Learning Unit له quiz؟
- هل الأسئلة أصلية؟
- هل يوجد speaking/listening؟
- ما المشاكل المتبقية؟

---

## Prompt 06 — تصميم صفحة الدرس بنفس فلسفة الكتاب لكن بهوية Onlenco

أنت UX Engineer ومهندس Django/Tailwind.

المشروع: Onlenco Academy

المطلوب:
إعادة تصميم صفحة Learning Unit / Lesson Detail للطالب بحيث تعرض الدرس بنفس فلسفة الكتب التعليمية الاحترافية:
- شرح بصري
- بطاقات ملونة
- Vocabulary
- Grammar
- Visual Guide
- Examples
- Practice
- Listening
- Speaking
- Quiz
- Checklist

لكن:
- لا تقلد تصميم DK حرفيًا.
- لا تستخدم نفس الألوان أو الرسومات.
- استخدم هوية Onlenco.
- التصميم responsive للموبايل والكمبيوتر.
- يدعم LTR للإنجليزية و RTL للعربية.
- يعمل حتى إذا لا توجد صورة أو صوت.

أقسام الصفحة:
1. Lesson Header
   - unit number من 01 إلى 48
   - title
   - cefr level
   - estimated time
   - progress

2. Learning Points
   - New Language
   - Vocabulary
   - New Skill

3. Visual Lesson Card
   - image إن وجدت
   - fallback illustration placeholder إن لم توجد

4. Key Language
   - شرح بسيط
   - أمثلة ملوّنة

5. How to Form
   - جدول/بلوك يوضح تركيب الجملة

6. Vocabulary Grid
   - كلمات + ترجمة + زر صوت إن وجد

7. Mini Dialogue
   - حوار قصير
   - زر تشغيل صوت إن وجد

8. Practice
   - تمارين صغيرة

9. Listening
   - يظهر pending إذا الصوت غير موجود
   - يظهر player إذا الصوت موجود

10. Speaking Practice
   - زر Practice with AI Tutor

11. Quiz
   - Start Quiz button

12. Checklist
   - I can...
   - checkboxes

13. Next Unit CTA

ألوان مقترحة لهوية Onlenco:
- Primary: #2563EB
- Soft Blue: #DBEAFE
- Soft Green: #DCFCE7
- Soft Yellow: #FEF9C3
- Soft Orange: #FFEDD5
- Text: #111827
- Surface: #FFFFFF

مهم:
- لا تجعل الصفحة تعطي Internal Server Error إذا لا توجد media.
- استخدم fallbacks.
- حافظ على المحتوى الإنجليزي LTR حتى داخل الواجهة العربية.
- اجعل شكل الصفحة احترافي وجذاب كأنه منتج حقيقي وليس seed demo.

أضف اختبارات:
- test_lesson_page_renders
- test_lesson_page_no_internal_server_error
- test_lesson_page_works_without_media
- test_lesson_page_shows_learning_points
- test_lesson_page_shows_checklist
- test_lesson_page_shows_quiz_button
- test_lesson_page_shows_ai_tutor_button
- test_lesson_page_supports_arabic_rtl
- test_english_examples_remain_ltr_in_arabic_ui

شغّل:
DJANGO_SETTINGS_MODULE=config.settings.test python manage.py test courses student_portal
DJANGO_SETTINGS_MODULE=config.settings.test python manage.py check

التقرير النهائي بالعربي:
- ماذا تغير في صفحة الدرس؟
- هل الصفحة تشبه فلسفة الكتاب؟
- هل هي أصلية لهوية Onlenco؟
- هل تعمل بدون media؟
- هل تدعم العربي والإنجليزي؟
- ما المشاكل المتبقية؟

---

## Prompt 07 — توليد الصور بالذكاء الاصطناعي لكل 48 وحدة عبر Batch آمن

أنت مهندس AI Integration ومصمم وسائط تعليمية.

المشروع: Onlenco Academy

المطلوب:
إضافة command لتوليد صور تعليمية أصلية بالذكاء الاصطناعي لكل 48 Learning Units، لكن بطريقة Batch آمنة.

مهم:
- لا تستخدم صور الكتاب.
- لا تقلد رسومات DK.
- الصور أصلية لهوية Onlenco.
- لا تحتوي شعارات أو علامات تجارية.
- مناسبة للكبار والصغار.
- كرتونية حديثة، تعليمية، واضحة.
- خلفية ناعمة وواضحة.
- لا تولد كل شيء دفعة واحدة بدون خيار batch.
- يجب دعم dry-run ومعرفة التكلفة التقريبية.

أنشئ command:
courses/management/commands/generate_lesson_images.py

Options:
- --unit=1 لتوليد وحدة واحدة
- --from-unit=1 --to-unit=48
- --all لتوليد كل الوحدات
- --dry-run
- --confirm
- --overwrite=False افتراضيًا

الشروط:
- لا يعمل إلا إذا IMAGE_GENERATION_ENABLED=True
- لا يعمل في production إلا مع --confirm
- لا يكرر الصورة إذا موجودة
- يقرأ LessonImagePrompt
- يولد image
- يحفظها في LessonMedia
- يسجل logs واضحة
- يحفظ generation metadata

لكل Learning Unit ولد:
- cover image
- vocabulary image
- grammar visual image
- quiz support image إن أمكن

أضف اختبارات:
- test_generate_lesson_images_requires_flag
- test_generate_lesson_images_does_not_duplicate
- test_generated_image_saved_as_lesson_media
- test_command_can_target_single_unit
- test_command_supports_batch_range
- test_command_supports_dry_run
- test_lesson_page_shows_generated_image
- test_generation_fails_safely_if_api_unavailable

التقرير النهائي بالعربي:
- هل تم إنشاء command؟
- هل الصور أصلية؟
- هل يمكن توليد unit واحدة؟
- هل يمكن توليد كل 48 وحدة؟
- أين تحفظ الصور؟
- كيف يتم منع التكرار؟
- كيف يتم تقدير التكلفة؟

---

## Prompt 08 — توليد الصوت الأمريكي لكل 48 وحدة عبر Batch آمن

أنت مهندس AI Voice/TTS ومهندس Django.

المشروع: Onlenco Academy

المطلوب:
إضافة command لتوليد صوت أمريكي طبيعي لكل 48 Learning Units بطريقة Batch آمنة.

مهم:
- لا تستخدم صوت الكتاب.
- لا تستخدم أي audio من PDF.
- الصوت مولد من scripts الأصلية داخل Onlenco.
- American English.
- لا يقرأ الرموز مثل underscore أو HTML أو tags.
- لا يقرأ علامات الترقيم بطريقة مزعجة.
- الصوت واضح وبطيء قليلًا مناسب للمبتدئين.
- لا تولد كل شيء دفعة واحدة بدون خيار batch.
- يدعم dry-run وتقدير تكلفة.

أنشئ command:
courses/management/commands/generate_lesson_audio.py

Options:
- --unit=1
- --from-unit=1 --to-unit=48
- --all
- --dry-run
- --confirm
- --voice=friendly_teacher
- --overwrite=False افتراضيًا

الوظيفة:
- يقرأ LessonAudioScript
- ينظف النص من HTML والرموز
- يولد mp3
- يحفظه في LessonMedia
- يربطه بالدرس
- لا يكرر إذا الصوت موجود
- يدعم voice style:
  - friendly_teacher
  - slow_beginner
  - dialogue_male_female إن أمكن

لكل Learning Unit ولد:
- intro audio
- vocabulary audio
- examples audio
- mini dialogue audio
- listening task audio
- speaking model answer audio

أضف audio cleaner:
- remove_html_tags
- normalize_punctuation
- remove_underscores
- remove_markdown
- avoid_reading_symbols
- convert lists to natural speech

أضف اختبارات:
- test_generate_audio_requires_flag
- test_audio_script_cleaner_removes_html
- test_audio_does_not_read_underscores
- test_audio_media_saved
- test_command_does_not_duplicate_audio
- test_command_can_target_single_unit
- test_command_supports_batch_range
- test_lesson_page_shows_audio_player
- test_generation_fails_safely_if_tts_api_unavailable

التقرير النهائي بالعربي:
- هل تم إنشاء command؟
- هل الصوت أمريكي؟
- هل يعمل لكل 48 وحدة عبر batch؟
- كيف يتم تنظيف النص؟
- أين تحفظ ملفات الصوت؟
- كيف نراقب التكلفة؟

---

## Prompt 09 — ربط AI Tutor بكل Learning Unit

أنت مهندس AI Tutor ومصمم تجربة تعليمية.

المشروع: Onlenco Academy

المطلوب:
ربط AI Tutor بكل Learning Unit بحيث لا يكون محادثة عامة، بل تدريب مرتبط بالدرس الحالي.

عند ضغط الطالب:
Practice with AI Tutor

يجب أن ينتقل AI Tutor بسياق الدرس:
- unit number
- lesson title
- cefr level
- new language
- vocabulary
- grammar focus
- speaking goal
- expected answers
- correction style
- student progress
- quiz performance إن وجد

قواعد AI Tutor:
- American English
- Beginner-friendly
- short sentences
- one correction at a time
- encourage student
- لا يخرج خارج موضوع الدرس
- لا يعطي إجابات طويلة
- لا يتكلم بسرعة
- يدعم الطالب العربي بشرح بسيط عند الحاجة
- لا يقول رموز أو underscores
- لا يقرأ placeholders بشكل مزعج

أضف service:
lesson_ai_context_builder.py

يبني prompt داخلي للـ AI Tutor من بيانات الدرس.

Prompt يجب أن يحتوي:
- System instruction
- Lesson context
- Allowed vocabulary
- Grammar focus
- Speaking task
- Correction rules
- Safety fallback
- Arabic support instruction
- Completion criteria

أضف tracking:
- started_at
- completed_at
- attempts
- tutor_feedback
- pronunciation_notes إن وجدت
- score إن وجد

أضف اختبارات:
- test_ai_tutor_receives_lesson_context
- test_ai_tutor_prompt_contains_vocabulary
- test_ai_tutor_prompt_contains_grammar_focus
- test_ai_tutor_uses_beginner_style
- test_ai_tutor_does_not_start_general_chat
- test_ai_tutor_tracks_lesson_practice_completion
- test_ai_tutor_supports_arabic_explanation_when_needed

التقرير النهائي بالعربي:
- كيف تم ربط AI Tutor بالدرس؟
- هل التدريب مرتبط بموضوع الدرس؟
- هل مناسب للمبتدئ؟
- هل يحفظ progress؟
- ما المشاكل المتبقية؟

---

## Prompt 10 — بناء Reviews بعد مجموعات الوحدات

أنت خبير Assessment ومهندس Django.

المشروع: Onlenco Academy

المطلوب:
بناء Reviews داخل كورس Beginner بنفس فلسفة المراجعات في الكتب التعليمية.

الكورس يحتوي على 48 Learning Units.

أنشئ Reviews بعد مجموعات من الوحدات، مثل:
- Review 1 بعد Units 01–08
- Review 2 بعد Units 09–14
- Review 3 بعد Units 15–19
- Review 4 بعد Units 20–26
- Review 5 بعد Units 27–35
- Review 6 بعد Units 36–42
- Review 7 بعد Units 43–48

كل Review يحتوي:
1. Vocabulary Review
2. Grammar Review
3. Reading short task
4. Listening placeholder
5. Speaking task
6. Short writing task
7. Score
8. Encouragement message
9. Checklist summary

مهم:
- لا يستخدم أسئلة الكتاب.
- أسئلة أصلية.
- American English.
- شرح عربي مختصر.
- لا يفتح Review إلا بعد إكمال الوحدات المطلوبة.
- يحفظ النتيجة والتقدم.

إذا يوجد Exam/Assessment model استخدمه.
إذا لا يوجد، أنشئ model آمن:

CourseReview:
- course
- title
- title_ar
- start_unit_number
- end_unit_number
- instructions
- instructions_ar
- is_active

CourseReviewQuestion:
- review
- question_type
- question_text
- question_text_ar
- options
- correct_answer
- skill
- order

CourseReviewAttempt:
- review
- student
- score
- completed_at
- feedback

أضف اختبارات:
- test_reviews_created_for_beginner_course
- test_review_has_vocabulary_questions
- test_review_has_grammar_questions
- test_review_has_speaking_task
- test_review_has_listening_placeholder
- test_review_available_after_required_units_completed
- test_review_not_available_before_required_units_completed
- test_review_score_saved
- test_review_feedback_generated

التقرير النهائي بالعربي:
- عدد Reviews
- ماذا يحتوي كل Review؟
- هل يظهر بعد إكمال الوحدات المطلوبة؟
- هل يحفظ النتيجة؟
- ما المشاكل المتبقية؟

---

## Prompt 11 — اختبار رحلة الطالب كاملة

أنت QA Engineer محترف تختبر كأنك طالب حقيقي.

المشروع: Onlenco Academy

المطلوب:
اختبار رحلة الطالب الكاملة لكورس Beginner المكون من 48 Learning Units.

اختبر السيناريو:

Flow 1:
Register
→ Verify Email
→ Choose Start from Beginner
→ Dashboard
→ Beginner Course appears
→ Open Unit 1
→ View learning content
→ Play image/audio if available
→ Start Quiz
→ Submit Quiz
→ Practice with AI Tutor
→ Complete Unit 1
→ Move Unit 2
→ Continue until first Review opens

Flow 2:
Logout
→ Login again
→ لا يظهر Placement إجباريًا
→ يرجع الطالب للكورس والتقدم الصحيح

Flow 3:
Open Learning Unit without media
→ يجب ألا يحدث Internal Server Error

Flow 4:
Open Learning Unit with generated media
→ image appears
→ audio player works
→ quiz works

Flow 5:
Arabic UI
→ RTL works
→ Arabic content appears
→ English content remains LTR

Flow 6:
Quiz
→ questions appear
→ answer validation works
→ score saved
→ progress updated

Flow 7:
AI Tutor
→ receives lesson context
→ does not start generic chat
→ asks lesson-based questions
→ saves attempt/progress

Flow 8:
Review
→ locked before required units
→ unlocks after required units
→ saves score

افحص:
- 500 errors
- missing template variables
- wrong queryset
- missing media fallback
- quiz not linked
- AI tutor not linked
- progress not saved
- placement showing incorrectly
- RTL/LTR issues
- audio player errors
- image fallback errors
- duplicate seed data

اكتب تقرير بالعربي:
# تقرير QA رحلة الطالب — Onlenco Beginner 48 Units

جدول:
| Flow | النتيجة | المشاكل | الأولوية | الحل المقترح |

رتب المشاكل:
P0 = يكسر الرحلة
P1 = مهم جدًا
P2 = تحسين
P3 = لاحقًا

لا تصلح الكود إلا إذا طلبت منك.
فقط افحص واكتب التقرير.

---

## Prompt 12 — إصلاح مشاكل QA فقط

أنت مهندس Django كبير.

اعتمد على تقرير QA السابق.

المطلوب:
إصلاح مشاكل رحلة الطالب فقط، بدون إضافة features جديدة.

الأولويات:
1. P0
2. P1
3. P2 إذا لا تؤثر على الاستقرار

لا تعمل:
- لا تضف كورسات جديدة.
- لا تولد صور جديدة.
- لا تولد صوت جديد.
- لا تغير نظام الاشتراك.
- لا تغير placement إلا إذا المشكلة مرتبطة بتكرار ظهوره.
- لا تغير AI Tutor خارج ربط الدرس.
- لا تغير بنية 48 Learning Units إلا إذا يوجد خطأ واضح.

أصلح:
- Internal Server Error في lesson page
- missing media fallback
- quiz linking
- progress saving
- placement appearing after completion
- dashboard course redirect
- AI Tutor lesson context
- Review unlock logic
- RTL/LTR issues
- image/audio player fallback
- duplicated seed data issues

بعد الإصلاح شغّل:
DJANGO_SETTINGS_MODULE=config.settings.test python manage.py test
DJANGO_SETTINGS_MODULE=config.settings.test python manage.py check

التقرير النهائي بالعربي:
- المشاكل التي تم إصلاحها
- الملفات المعدلة
- الاختبارات
- المشاكل المتبقية
- هل الرحلة أصبحت جاهزة؟
- هل يمكن الانتقال لتعميم الصور والصوت؟

---

## Prompt 13 — تعميم الصور والصوت على 48 وحدة بطريقة Batch آمنة

أنت مهندس EdTech وAI Media Pipeline.

المشروع: Onlenco Academy

بعد نجاح أول batch من الصور والصوت، المطلوب تعميم توليد الوسائط على كورس Beginner كاملًا.

لكن نفذها Batch آمن:
- يمكن توليد وحدة واحدة
- يمكن توليد range من الوحدات
- يمكن توليد كل 48 وحدة بعد التأكيد
- لا تكرر الملفات
- يدعم dry-run
- يسجل تكلفة تقديرية
- يسجل failures
- لا يكسر صفحة الدرس إذا فشل API

Commands:
generate_lesson_images --unit=1 --confirm
generate_lesson_images --from-unit=1 --to-unit=10 --confirm
generate_lesson_images --all --confirm

generate_lesson_audio --unit=1 --confirm
generate_lesson_audio --from-unit=1 --to-unit=10 --confirm
generate_lesson_audio --all --confirm

قواعد:
- لا يكرر media
- يدعم dry-run
- يسجل تكلفة تقديرية
- يسجل عدد الصور والصوتيات
- يفشل بأمان إذا API غير متاح
- لا يكسر صفحة الدرس
- يمكن إعادة تشغيله بعد الفشل
- يحفظ generation status لكل media

أضف report لكل batch:
- Unit number
- Lessons / Topics processed
- Images generated
- Audio generated
- Failures
- Estimated cost
- Duration
- Next recommended batch

أضف اختبارات:
- test_batch_generation_by_unit
- test_batch_generation_by_range
- test_dry_run
- test_no_duplicate_media
- test_failure_does_not_break_lesson_page
- test_generation_status_saved
- test_can_resume_failed_batch

التقرير النهائي بالعربي:
- هل التعميم آمن؟
- كيف أشغل Unit واحدة؟
- كيف أشغل كل 48 وحدة؟
- كيف أوقف العملية؟
- كيف أراقب التكلفة؟
- كيف أعيد تشغيل batch فشل؟

---

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

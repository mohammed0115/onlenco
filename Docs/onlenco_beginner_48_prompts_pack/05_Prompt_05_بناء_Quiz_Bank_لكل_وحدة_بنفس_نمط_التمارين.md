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

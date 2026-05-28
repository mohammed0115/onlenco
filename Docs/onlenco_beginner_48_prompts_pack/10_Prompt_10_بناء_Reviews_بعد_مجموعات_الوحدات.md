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

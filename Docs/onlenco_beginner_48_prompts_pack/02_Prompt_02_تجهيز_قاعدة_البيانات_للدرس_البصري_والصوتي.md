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

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

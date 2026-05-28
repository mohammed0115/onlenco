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

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

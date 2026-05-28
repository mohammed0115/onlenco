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

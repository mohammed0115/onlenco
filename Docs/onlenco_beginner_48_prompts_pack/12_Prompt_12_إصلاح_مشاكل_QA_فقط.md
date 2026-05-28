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

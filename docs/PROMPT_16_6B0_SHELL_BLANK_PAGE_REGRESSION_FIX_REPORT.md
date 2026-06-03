# تقرير Prompt 16.6B.0 — إصلاح انهيار واجهة الإدارة وظهور صفحة فارغة

## 1. الملخص التنفيذي

تم تحديد سبب الانهيار في صفحة:

`/admin/courses/<id>/lessons/new/`

وكان السبب المباشر أن قالب محرر الدرس الإداري كان يعيد تعريف بلوك `extra_head` بدون `{{ block.super }}`، وهذا أدى إلى حذف تحميل ملف:

`platform_admin/css/control.css`

من الصفحة بالكامل. النتيجة كانت ظهور الشريط الجانبي بشكل خام أو غير منسق، واختفاء تنسيق المحتوى الرئيسي، وهو ما ظهر للمستخدم كصفحة شبه فارغة.

تم تطبيق إصلاح آمن وسريع يعيد تحميل CSS الأساسي للـ admin shell، مع رفع نسخة الأصول الثابتة لتجاوز الكاش القديم.

## 2. السبب الجذري

السبب الجذري كان في القالب:

`platform_admin/templates/platform_admin/courses/lesson_editor.html`

حيث كان يحتوي على:

`{% block extra_head %}`

بدون تضمين:

`{{ block.super }}`

وبالتالي تم استبدال محتوى البلوك القادم من:

`platform_admin/templates/platform_admin/base.html`

بدلًا من توسيعه. هذا منع تحميل `control.css` الخاصة بالـ shell.

## 3. الأثر على الواجهة

الأثر الناتج كان:

- غياب تنسيق shell الرئيسي في صفحة إنشاء/تعديل الدرس الإداري
- ظهور القائمة الجانبية بشكل خام
- اختفاء أو انهيار المساحة الرئيسية بصريًا
- زيادة احتمال ظهور الصفحة كأنها فارغة خاصة مع RTL أو العرض الضيق

## 4. الإصلاح المنفذ

تم تنفيذ الإصلاحات التالية:

- إعادة `{{ block.super }}` داخل `extra_head` في قالب `lesson_editor.html`
- رفع نسخة أصول admin shell إلى:
  `p166b0-shellfix-20260603`
- رفع نسخة أصول teacher shell إلى:
  `p166b0-shellfix-20260603`
- إضافة اختبارات regression خاصة بصفحة إنشاء الدرس الإداري
- إضافة اختبارات استمرار تحميل صفحات teacher/course/lesson بعد إصلاح shell

## 5. الملفات المعدلة

- `platform_admin/templates/platform_admin/courses/lesson_editor.html`
- `platform_admin/templates/platform_admin/base.html`
- `teacher_portal/templates/teacher_portal/base.html`
- `platform_admin/tests/test_dashboard_shell.py`
- `platform_admin/tests/test_courses.py`
- `teacher_portal/tests/test_teacher_portal.py`

## 6. الاختبارات المضافة

تمت إضافة أو تحديث اختبارات تغطي:

- ظهور محتوى صفحة إنشاء الدرس الإداري
- وجود الفورم داخل الصفحة
- تحميل `control.css` بالنسخة الجديدة
- عدم تكرار الشريط الجانبي
- بقاء `control-main` و `control-content` ظاهرين
- استمرار صفحات teacher course/lesson create في الرندر
- استمرار صفحة admin course detail في الرندر
- عدم اختفاء المحتوى في وضع RTL

## 7. التحقق الفني

تم التحقق من:

- سلامة ملفات Python المعدلة عبر `py_compile`
- صحة السبب الجذري من خلال مراجعة inheritance بين `lesson_editor.html` و `platform_admin/base.html`

ملاحظة: تشغيل حزمة اختبارات Django الكاملة داخل هذا الـ sandbox لم يعطِ مخرجات نهائية موثوقة، لذلك التحقق الكامل يجب أن يُستكمل داخل بيئة التشغيل المعتادة للمشروع.

## 8. ملاحظات النشر

بعد النشر يجب تنفيذ:

`sudo bash /opt/onlenco/scripts/update.sh`

ثم عمل hard refresh:

`Ctrl + Shift + R`

وإذا استمرت ملفات static القديمة:

- تحقق من `collectstatic`
- تحقق من الكاش في Nginx أو Whitenoise
- تحقق أن HTML النهائي يحمل:
  `control.css?v=p166b0-shellfix-20260603`

## 9. الخلاصة

الانهيار لم يكن سببه نموذج الدرس أو صلاحيات الإدارة أو منطق الحفظ، بل سببه regression في template inheritance أدى إلى إسقاط CSS الأساسي للواجهة الإدارية. تم إصلاحه بأقل تغيير ممكن مع إضافة حواجز اختبار لمنع تكراره.

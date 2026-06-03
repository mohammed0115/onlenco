# تقرير Prompt 16.6B.0.1 — إصلاح الغلاف العام ولوحات الإدارة/المعلم ومعالجة overflow الجداول

## 1. الملخص التنفيذي

تم تحديد أن المشكلة لم تكن في صفحة واحدة فقط، بل في الغلاف العام `shell` المستخدم في صفحات الإدارة ولوحة المعلم، مع وجود overflow أفقي ناتج عن الجداول العريضة وصفوف الفلاتر وبعض العناصر التي لم يكن مسموحًا لها بالانكماش داخل الـ grid/flex.

تم تنفيذ إصلاح عام يشمل:

- تقوية CSS الخاص بالغلاف الإداري وغلاف المعلم
- منع ظهور horizontal scroll على مستوى الصفحة
- حصر التمرير الأفقي داخل بطاقات الجداول فقط
- إضافة `table-wrap` حول الجداول الأساسية
- رفع نسخة ملفات static إلى:
  `p166b01-global-shell-20260603`

## 2. السبب الجذري

تم العثور على سببين رئيسيين:

1. جداول الإدارة كانت تُرسم مباشرة داخل `control-panel` أو `control-card` بدون wrapper مخصص للتمرير الأفقي.
   هذا كان يسمح للجدول أن يوسّع الحاوية ثم الصفحة نفسها، بدل أن يبقى التمرير داخل البطاقة فقط.

2. بعض عناصر الغلاف المشترك مثل:

- `control-main`
- `control-content`
- `filters`
- `toolbar`
- `teacher-content`
- `teacher-filters`

لم تكن كلها محمية بشكل كافٍ عبر `min-width: 0` و `max-width: 100%`، لذلك كانت بعض الصفوف أو الجداول أو الحقول ترفض الانكماش وتدفع الواجهة خارج viewport، خصوصًا في RTL أو المقاسات المتوسطة.

## 3. الأثر الظاهر في الإنتاج

الأعراض التي سبّبها هذا الخلل:

- horizontal scrollbar على مستوى المتصفح
- انضغاط أو قص الشريط الجانبي
- تمدد المحتوى الرئيسي خارج العرض المتاح
- ظهور بعض الصفحات وكأنها فارغة أو غير مستقرة بصريًا
- تسرب عرض الجداول إلى خارج البطاقة بدل بقائه داخلها

## 4. الإصلاحات المنفذة

### أ. تقوية الغلاف الإداري

في:

- `platform_admin/static/platform_admin/css/control.css`

تمت إضافة أو تثبيت:

- `html, body { max-width: 100%; overflow-x: hidden; }`
- قواعد `box-sizing: border-box`
- حواجز `min-width: 0` و `max-width: 100%` على عناصر الغلاف
- حماية `control-panel` و `table-wrap` لتصبح scroll containers محلية
- ضبط أفضل لحالة drawer في الشاشات الصغيرة

### ب. تقوية غلاف لوحة المعلم

في:

- `teacher_portal/static/teacher_portal/css/teacher.css`

تمت إضافة:

- منع overflow الأفقي على مستوى الصفحة
- حماية `teacher-main`, `teacher-content`, `teacher-filters`, `teacher-panel`
- تثبيت سلوك الجداول داخل `table-wrap`
- حصر overflow داخل اللوحة بدل الصفحة

### ج. تغليف الجداول الأساسية

تمت إضافة `table-wrap` لصفحات أساسية مثل:

- `platform_admin/templates/platform_admin/students/list.html`
- `platform_admin/templates/platform_admin/courses/list.html`
- `platform_admin/templates/platform_admin/teachers/list.html`
- `platform_admin/templates/platform_admin/payments/list.html`
- `platform_admin/templates/platform_admin/plans/list.html`
- `platform_admin/templates/platform_admin/payment_methods/list.html`
- `platform_admin/templates/platform_admin/voices/list.html`
- `platform_admin/templates/platform_admin/placement/questions_list.html`
- `teacher_portal/templates/teacher_portal/courses/list.html`

## 5. تحديث نسخة الأصول الثابتة

تم تحديث مراجع static في:

- `platform_admin/templates/platform_admin/base.html`
- `teacher_portal/templates/teacher_portal/base.html`

إلى:

- `p166b01-global-shell-20260603`

وذلك لكسر الكاش القديم والتأكد من تحميل CSS/JS الجديد بعد النشر.

## 6. الاختبارات المضافة أو المحدثة

تم تحديث اختبارات shell والصفحات الحرجة للتأكد من:

- وجود `table-wrap` في صفحات الإدارة الأساسية
- عدم وجود duplicate sidebar
- وجود `control-main` و `control-content`
- استمرار صفحات الإنشاء وعدم ظهورها كصفحات فارغة
- تحميل نسخة CSS الجديدة
- وجود حواجز CSS مثل `min-width: 0` و `overflow-x: hidden/clip`

الملفات:

- `platform_admin/tests/test_dashboard_shell.py`
- `platform_admin/tests/test_courses.py`
- `teacher_portal/tests/test_teacher_portal.py`

## 7. التحقق الفني

تم التحقق من سلامة ملفات Python المعدلة عبر:

- `python3 -m py_compile`

أما تشغيل مجموعة اختبارات Django الكاملة داخل هذا الـ sandbox فما زال غير موثوق من ناحية المخرجات النهائية، لذلك يجب إعادة تشغيل:

- `DJANGO_SETTINGS_MODULE=config.settings.test python manage.py test platform_admin`
- `DJANGO_SETTINGS_MODULE=config.settings.test python manage.py test teacher_portal`
- `DJANGO_SETTINGS_MODULE=config.settings.test python manage.py test courses`
- `DJANGO_SETTINGS_MODULE=config.settings.test python manage.py check`

داخل بيئة التطوير/النشر المعتادة.

## 8. ملاحظات النشر

بعد الدمج أو النشر شغّل:

`sudo bash /opt/onlenco/scripts/update.sh`

ثم:

`Ctrl + Shift + R`

وتأكد من أن HTML النهائي يحتوي على:

`p166b01-global-shell-20260603`

إذا لم يظهر:

- فشل `collectstatic`
- أو أن القالب ما زال يشير إلى النسخة القديمة
- أو أن المتصفح/الخادم ما زال يقدّم cache قديمًا

## 9. الخلاصة

الخلل كان global shell regression وليس عطلًا محصورًا في صفحة إنشاء درس أو placement فقط. السبب الحقيقي كان مزيجًا من:

- جداول عريضة بدون wrapper محلي للتمرير
- عناصر shell لم تكن shrink-safe بشكل كافٍ
- قواعد overflow غير موحدة بين الشاشات العادية والموبايل

تم تنفيذ إصلاح عام محافظ على منطق النظام الحالي بدون المساس بنماذج البيانات أو الصلاحيات أو تدفق الحفظ.

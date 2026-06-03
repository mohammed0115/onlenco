# تقرير Prompt 16.6B.0.2 — إصلاح حاسم للـ browser-level horizontal overflow في جداول الإدارة ولوحة المعلم

## 1. الملخص التنفيذي

تم التأكد أن مشكلة الـ horizontal overflow لم تكن منتهية بعد الإصلاحات السابقة، وكان المسار المؤكد هذه المرة:

`/teacher/students/`

السبب المباشر في هذا المسار كان أن الجدول ما زال مرسومًا مباشرة داخل `teacher-panel` بدون `table-wrap`، لذلك كان عرض الجدول يتسرب إلى مستوى الصفحة بدل أن يبقى داخل منطقة scroll محلية.

تم إصلاح هذا المسار، مع تقوية contract الجداول المشتركة في CSS لكل من admin وteacher، ورفع نسخة الأصول الثابتة إلى:

`p166b02-overflow-fix-20260603`

## 2. السبب الجذري

### أ. خطأ قالب مباشر

في:

`teacher_portal/templates/teacher_portal/students/list.html`

كان الجدول موجودًا مباشرة داخل:

`<section class="teacher-panel">`

بدون:

`<div class="table-wrap">`

وهذا يعني أن الجدول لم يكن داخل scroll container مخصص.

### ب. Contract الجداول لم يكن صارمًا بما يكفي

رغم وجود `table-wrap` في بعض الصفحات، إلا أن CSS العام لم يكن يضمن دائمًا:

- `width: max-content`
- `min-inline-size: 100%`
- `white-space: nowrap` لخلايا الإجراءات
- `min-width` مناسب لعمود الأزرار

وبالتالي كان آخر عمود أحيانًا يُقص بصريًا حتى مع وجود scroll داخلي.

## 3. الأثر الظاهر

الأعراض التي أكدت استمرار الخلل:

- browser-level horizontal scrollbar
- قص زر "فتح" في جدول طلاب المعلم
- خروج الجدول خارج البطاقة
- عدم بقاء overflow داخل الحاوية المخصصة

## 4. الإصلاحات المنفذة

### أ. إصلاح صفحة طلاب المعلم

في:

`teacher_portal/templates/teacher_portal/students/list.html`

تم:

- إضافة `table-wrap` حول الجدول
- وضع عمود الإجراء داخل `row-actions`

### ب. تقوية CSS لجداول teacher

في:

`teacher_portal/static/teacher_portal/css/teacher.css`

تمت إضافة:

- `width: max-content`
- `min-inline-size: 100%`
- حماية عمود الإجراءات عبر `white-space: nowrap`
- `min-width` مناسب لخلايا الأزرار

### ج. تقوية CSS لجداول admin

في:

`platform_admin/static/platform_admin/css/control.css`

تمت إضافة نفس contract تقريبًا لجدول الإدارة:

- `width: max-content`
- `min-inline-size: 100%`
- حماية عمود الإجراءات

## 5. تحديث نسخة static

تم تحديث النسخة في:

- `platform_admin/templates/platform_admin/base.html`
- `teacher_portal/templates/teacher_portal/base.html`

إلى:

`p166b02-overflow-fix-20260603`

## 6. الاختبارات المضافة أو المحدثة

تم تحديث الاختبارات لتغطية:

- وجود `table-wrap` في صفحة `/teacher/students/`
- التأكد أن الجدول ليس direct child لمساحة المحتوى الرئيسية
- التأكد أن أزرار الإجراءات داخل بنية الجدول المغلف
- التأكد أن صفحات admin الأساسية تستخدم `table-wrap`
- التأكد من عدم وجود `100vw` في CSS الخاص بالـ main shell
- التأكد من نسخة CSS الجديدة

الملفات:

- `teacher_portal/tests/test_teacher_portal.py`
- `platform_admin/tests/test_dashboard_shell.py`

## 7. التحقق الفني

تم التحقق من سلامة ملفات Python المعدلة عبر:

- `python3 -m py_compile`

أما فحص Playwright / real browser المطلوب في البرومبت فلم يكن متاحًا داخل هذه الجلسة بالأدوات الحالية، لذلك ما زال مطلوبًا تنفيذه داخل بيئة التطوير أو CI التي تدعم المتصفح.

## 8. ما يجب التحقق منه بعد النشر

بعد تشغيل:

`sudo bash /opt/onlenco/scripts/update.sh`

ثم hard refresh:

`Ctrl + Shift + R`

يجب التأكد من:

- عدم وجود browser-level horizontal scrollbar
- ظهور الجدول داخل card فقط
- بقاء زر "فتح" ظاهرًا بالكامل
- تحميل:
  `p166b02-overflow-fix-20260603`

## 9. الخلاصة

هذا الإصلاح هو متابعة مباشرة لإصلاح shell السابق، لكنه هذه المرة استهدف overflow مثبتًا بصريًا في `/teacher/students/`. السبب كان خليطًا من:

- missing `table-wrap` في الصفحة نفسها
- وعدم كفاية contract CSS للجداول وعمود الإجراءات

تم إصلاح ذلك بدون المساس بمنطق النظام أو الصلاحيات أو نماذج البيانات.

# تقرير Prompt 16.6A.1 — Dashboard Shell Layout Fix

## 1. الملخص التنفيذي

* **ما المشكلة؟** بعد الدفعة الأولى (16.6)، لوحة `/teacher/dashboard/` ظهرت مكسورة على
  الديسكتوب: الشريط الجانبي يضغط المحتوى، مساحة فارغة ضخمة، كروت مقصوصة، و**hamburger
  يظهر على الديسكتوب**، وتخطيط RTL مختلّ.
* **ماذا أُصلح؟** السبب الجذري = **الـ CSS المخزّن (cache)**: عُدِّل `control.css` و
  `teacher.css` في الدفعة 1 دون تغيير معامل النسخة `?v=`، والتخزين `whitenoise` غير
  المُجزّأ (non-manifest) يعتمد على `?v=` لكسر الـ cache. فحُمِّل القالب الجديد مع
  CSS قديم لا يعرف `.ds-overlay`/`.ds-drawer-toggle` → الـ overlay دخل كـ grid item
  وبوّظ الأعمدة، وزر القائمة ظهر على كل المقاسات.
* **هل أصبح مقبولًا؟** نعم — bump النسخة + فرض تخطيط الديسكتوب صراحةً + drawer ≤768px
  فقط + كروت auto-fit + نقل الـ overlay خارج صدارة الـ grid. 119 اختبار أخضر، `check` نظيف.

## 2. السبب الجذري

1. **Cache (الأساسي):** `STATICFILES_STORAGE = whitenoise.CompressedStaticFilesStorage`
   (بلا hashing) → كسر الـ cache يعتمد على `?v=`. الدفعة 1 عدّلت الـ CSS وأبقت
   `?v=figma-20260522`، فخدم المتصفح CSS قديم مع القالب الجديد.
2. **أثر ذلك:** `.ds-overlay` (بلا `display:none` في الـ CSS القديم) أصبح **grid item**
   داخل `.teacher-shell` وسرق العمود الأول → إزاحة الشريط/المحتوى ومساحة فارغة. و
   `.ds-drawer-toggle` (بلا `display:none`) ظهر على الديسكتوب.
3. **عامل ثانوي:** breakpoint الـ drawer كان 980px (teacher) فاللابتوب الصغير يدخل وضع
   الموبايل.

## 3. الملفات المعدّلة

| File | Change | Reason |
|---|---|---|
| `teacher_portal/.../base.html` | bump `teacher.css?v=` + `dashboard-shell.js?v=`؛ نقل `.ds-overlay` لآخر الـ shell | كسر الـ cache + إخراج overlay من صدارة الـ grid |
| `platform_admin/.../base.html` | bump `control.css?v=` + `dashboard-shell.js?v=` | كسر الـ cache |
| `teacher_portal/.../teacher.css` | `@media (min-width:769px)` يفرض الديسكتوب؛ drawer `@media (max-width:768px)`؛ metrics `auto-fit` | sidebar ثابت + إخفاء hamburger/overlay على الديسكتوب + كروت متجاوبة |
| `platform_admin/.../control.css` | `@media (min-width:769px)` يفرض الديسكتوب؛ drawer `@media (max-width:768px)` | نفس السبب للأدمن |
| `*/tests/test_dashboard_shell.py` | 6 اختبارات regression جديدة | حراسة ضد تكرار العطل |

## 4. Desktop Layout (≥769px)

* `@media (min-width:769px)` (مُعلَن أخيرًا + min-width) **يتغلّب على أي media query
  قديمة** ويضمن:
  * `grid-template-columns: 16rem minmax(0,1fr)` — الشريط داخل الـ grid، المحتوى يأخذ الباقي.
  * `.control-sidebar/.teacher-sidebar { position: sticky; transform: none }` — لا overlay.
  * `.ds-drawer-toggle { display: none }` — **لا hamburger على الديسكتوب**.
  * `.ds-overlay { display: none }` — لا طبقة تغطية.
* الكروت: `.teacher-metrics { grid-template-columns: repeat(auto-fit, minmax(150px,1fr)) }`
  — تملأ الصف وتلتفّ طبيعيًا بلا قصّ ولا فراغ.

## 5. Mobile Layout (≤768px)

* `@media (max-width:768px)`: الشريط `position: fixed` off-canvas، hamburger يظهر،
  overlay يعمل، `100dvh`، `max-width:84vw`، main بعرض كامل.
* `dashboard-shell.js`: فتح/إغلاق بالـ toggle، إغلاق بالخلفية/Escape/عند اختيار رابط،
  وإعادة ضبط الحالة لو كبر العرض للديسكتوب. لا فتح تلقائي إطلاقًا.

## 6. RTL Verification

* الـ drawer ينزلق من **اليمين** في العربية: `[dir=rtl] … { transform: translateX(100%) }`.
* خصائص منطقية: `inset-inline-start`، `inset-block`، `border-inline-end`، `100dvh`.
* الشبكة `16rem minmax(0,1fr)` تنعكس تلقائيًا (الشريط يمين، المحتوى يسار) في RTL.
* اختبار `test_…_rtl_safe` يؤكّد `dir="rtl"` + وجود زر القائمة.

## 7. Screenshots

* لا توجد أدوات Playwright/متصفّح في المستودع (تم التحقق) — لم تُلتقط لقطات آليًا.
  التحقق تمّ عبر تحليل CSS + اختبارات بنية HTML + فحص قواعد الـ media queries. يُوصى
  بفحص بصري يدوي بعد النشر (القسم 10).

## 8. Tests

| Test | Result |
|---|---|
| test_teacher_dashboard_desktop_shell_not_drawer | ✅ |
| test_teacher_dashboard_overlay_not_first_grid_child | ✅ |
| test_teacher_css_version_bumped | ✅ |
| test_dashboard_shell_js_does_not_force_drawer_on_desktop | ✅ |
| test_admin_dashboard_desktop_shell_not_drawer | ✅ |
| test_admin_css_version_bumped | ✅ |
| اختبارات shell السابقة (drawer/RTL/منع الطالب) | ✅ (8) |
| regression: `platform_admin` + `teacher_portal` | ✅ **119 OK** |
| `manage.py check` | ✅ نظيف |

## 9. Commands Run

```
DJANGO_SETTINGS_MODULE=config.settings.test python manage.py test platform_admin.tests.test_dashboard_shell teacher_portal.tests.test_dashboard_shell   # 14 OK
DJANGO_SETTINGS_MODULE=config.settings.test python manage.py test platform_admin teacher_portal   # 119 OK
DJANGO_SETTINGS_MODULE=config.settings.test python manage.py check   # clean
```

## 10. Remaining Issues

* **P0/P1:** لا يوجد.
* **P2:** فحص بصري يدوي بعد النشر على 1440/1024/768/390/360 مُوصى به (لا أدوات متصفّح
  آلية). **مهم عند النشر:** شغّل `update.sh` (يعمل `collectstatic`) ليصل الـ CSS الجديد
  بالنسخة الجديدة؛ امسح cache المتصفّح إن لزم.
* **P3:** الـ media queries القديمة (980/860/560/1100) ما زالت موجودة لكن صار سلوك الـ
  shell محسومًا بكتلتَي min-width:769 / max-width:768؛ يمكن تنظيفها لاحقًا (تجميلي).

## 11. Final Decision

**Dashboard Shell Fixed — proceed to Quiz Builder.** السبب الجذري (cache) عولِج،
الديسكتوب مفروض صراحةً (شريط ثابت، لا hamburger)، الموبايل drawer فقط ≤768، الكروت
متجاوبة، RTL سليم، 119 اختبار أخضر و`check` نظيف.

> ملاحظة: لن أبدأ Quiz Builder تلقائيًا — بانتظار تأكيدك بعد الفحص البصري على الإنتاج.

# تقرير Prompt 16.6A.3 — إصلاح أزرار وإجراءات صفحة تفاصيل المعلم

## 1. الملخص التنفيذي

* **ما المشكلة؟** صفحة `/admin/teachers/<id>/` أظهرت أزرار إجراءات **ضخمة** (كتل زرقاء/حمراء
  بطول كامل) تستهلك العمود الجانبي وتبدو غير احترافية.
* **ماذا أُصلح؟** أُعيد تصميم العمود الجانبي إلى **لوحة إجراءات احترافية من 4 كروت مدمجة**
  (بطاقة الحالة + دور المعلّم + إسناد كورس + منطقة الخطر) بأزرار عادية 46px. وأُصلح أيضًا
  **طفح أفقي على الموبايل** سببه الـ drawer المخفي (عبر `overflow-x: clip` + `min-width:0`).
* **هل أصبحت احترافية؟** نعم — **مُثبَت بلقطات حقيقية** (headless Chrome على الـ CSS
  الفعلي) لديسكتوب 1440 وموبايل 390. 225 اختبار أخضر و`check` نظيف.

## 2. السبب الجذري

1. **الأزرار الضخمة:** التصميم الأصلي استخدم `.action-box { display: grid }` لأربعة
   نماذج منفصلة، فتمدّد كل زر `.btn-control` لكامل عرض الكارت بطول كبير = كتل ضخمة.
2. **الطفح الأفقي على الموبايل (اكتُشف بالـ debug البصري):** الشريط الجانبي يصبح
   `position: fixed; transform: translateX(100%)` (RTL) وهو مغلق، فيمتد خارج الحافة
   اليمنى ويخلق scroll أفقيًا يزيح كل المحتوى. كما أن عناصر `.detail-grid` بـ
   `min-width:auto` كانت تتمدّد مع الجدول.
3. **cache:** التغييرات السابقة لم تُرَ حيًّا بسبب الـ `?v=` القديم (whitenoise بلا hashing).

## 3. الملفات المعدّلة

| File | Change | Reason |
|---|---|---|
| `platform_admin/.../teachers/detail.html` | إعادة تصميم العمود الجانبي إلى 4 كروت (status/role/course/danger) + bilingual + `table-wrap` حول الجداول + تأكيد الحذف | لوحة إجراءات مدمجة احترافية |
| `platform_admin/.../control.css` | استبدال كتلة `.ta-*` بتصميم الكروت (`.ta-aside/.ta-status/.ta-avatar/.ta-mini/.ta-btn/.ta-danger`)؛ `.detail-grid > * { min-width:0 }`؛ `.control-shell { overflow-x: clip }` على ≤1023 | أزرار طبيعية + منع الطفح الأفقي |
| `teacher_portal/.../teacher.css` | `.teacher-shell { overflow-x: clip }` على ≤1023 | نفس إصلاح طفح الـ drawer للوحة المعلّم |
| `*/base.html` | bump `?v=p166a3` | كسر الـ cache |
| `platform_admin/tests/test_teacher_detail_ux.py` | 10 اختبارات جديدة | حراسة UX + عدم وجود طفح |

## 4. Before / After

* **قبل:** 4 صناديق إجراءات عملاقة ملوّنة بطول كامل تملأ العمود الجانبي؛ على الموبايل طفح
  أفقي يقصّ المحتوى.
* **بعد:** عمود من 4 كروت صغيرة مرتّبة (حالة المعلّم بـ avatar وbadges، دور، إسناد كورس،
  منطقة خطر حمراء خفيفة)، أزرار 46px بعرض الكارت فقط؛ موبايل بلا طفح، كل شيء عمودي.
* **اللقطات:**
  * `docs/screenshots/dashboard-shell/teacher_detail_desktop_1440.png`
  * `docs/screenshots/dashboard-shell/teacher_detail_mobile_390.png`

## 5. Action Panel

* **Role:** يعرض الحالة؛ زر **Primary "تعيين دور المعلّم"** لو بلا دور، أو **Secondary
  "إزالة دور المعلّم"** لو معلّم (شرطي عبر `teacher.profile.is_teacher`).
* **Course assignment:** select مدمج + زر Primary "إسناد الكورس" (بلا صندوق فارغ ضخم).
* **Danger zone:** كارت بإطار/خلفية حمراء خفيفة + زر Danger "تعطيل المعلّم" **مع تأكيد**.

## 6. Desktop QA

* مُثبَت بلقطة 1440 (RTL): الشريط ثابت يمين، المحتوى (ملخص + كورسات) يملأ الوسط، لوحة
  الإجراءات عمود يسار مرتّب، **لا كتل ضخمة، لا فراغ، لا تداخل topbar**.
* `.detail-grid: minmax(0,2fr) minmax(280px,1fr)` — اللوحة الجانبية 280–340px.

## 7. Mobile QA

* مُثبَت بلقطة 390: hamburger ظاهر، الملخص/الكورسات/الكروت الأربعة كلها بعرض كامل عمودية،
  **لا طفح أفقي، لا قص**، منطقة الخطر واضحة.
* `overflow-x: clip` يمنع الـ drawer المغلق من خلق scroll؛ `min-width:0` يمنع تمدّد الجدول.

## 8. Tests

| Test | Result |
|---|---|
| test_teacher_detail_action_panel_renders_compact | ✅ |
| test_teacher_detail_no_giant_action_blocks (لا `.action-box`) | ✅ |
| test_teacher_detail_danger_zone_present | ✅ |
| test_teacher_detail_remove_role_action_present_when_teacher | ✅ |
| test_teacher_detail_assign_course_action_present | ✅ |
| test_teacher_detail_destructive_action_requires_confirmation | ✅ |
| test_teacher_detail_rtl_safe | ✅ |
| test_teacher_detail_shell_still_fixed | ✅ |
| test_student_cannot_access_admin_teacher_detail | ✅ |
| test_teacher_detail_css_no_horizontal_overflow_guards | ✅ |
| regression: `platform_admin` + `teacher_portal` + `accounts` | ✅ **225 OK** |
| `manage.py check` | ✅ نظيف |

## 9. Commands Run

```
google-chrome --headless=new --window-size=1440,1000 --screenshot=... file://tdetail_preview.html   # + 390 + debug
DJANGO_SETTINGS_MODULE=config.settings.test python manage.py test platform_admin.tests.test_teacher_detail_ux   # 10 OK
DJANGO_SETTINGS_MODULE=config.settings.test python manage.py test platform_admin teacher_portal accounts   # 225 OK
DJANGO_SETTINGS_MODULE=config.settings.test python manage.py check   # clean
```

## 10. Remaining Issues

* **P0/P1:** لا يوجد — مُصلَح ومُثبَت بصريًا.
* **P2:** عند النشر يجب `update.sh` (collectstatic) + hard-refresh؛ السبب المتكرر هو الـ
  cache، فالنسخة `?v=p166a3` تضمن تحميل الجديد.
* **P3:** عرض شريط التمرير الأفقي للجدول داخل `.table-wrap` على شاشات ضيقة جدًا (مقصود —
  scroll داخل الكارت لا الصفحة). لا منطق backend تغيّر إطلاقًا.

## 11. Final Decision

**Teacher Detail UX fixed; proceed to Quiz Builder** — الأزرار صارت بحجم طبيعي في 4 كروت
احترافية، لا طفح على الموبايل، RTL سليم، لا تغيير في أي منطق/صلاحيات/نقاط نهاية، 225
اختبار أخضر و`check` نظيف، ومُثبَت بلقطات حقيقية.

> **مهم:** لن أبدأ Quiz Builder تلقائيًا. بعد النشر (`update.sh` + hard-refresh) وموافقتك
> البصرية على `/admin/teachers/<id>/`، نكمل من فحص الكويز المحفوظ.

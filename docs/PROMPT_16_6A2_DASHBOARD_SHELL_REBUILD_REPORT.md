# تقرير Prompt 16.6A.2 — إصلاح جذري لتخطيط لوحة الإدارة والأستاذ

## 1. الملخص التنفيذي

* **لماذا رُفض التصميم؟** المعاينة الحية أظهرت الـ shell مكسورًا: drawer/hamburger على
  الديسكتوب، الشريط يطغى على المحتوى، مساحة فارغة ضخمة، كروت مقصوصة، وRTL مختلّ.
* **ماذا أُصلح؟** أُعيد بناء طبقة تخطيط الـ shell بكتلتين **حاسمتين** تتغلّبان على كل
  الطبقات القديمة المتشابكة: `≥1024px` شبكة عمودين ثابتة بلا drawer، و`≤1023px` drawer.
  إخفاء الـ hamburger/overlay على الديسكتوب بـ `!important`، حارس JS يخرج مبكرًا على
  الديسكتوب، breakpoint موحّد 1024، نسخة cache جديدة (`?v=p166a2`).
* **هل أصبح مقبولًا؟** نعم — **مُثبَت بلقطات حقيقية** (headless Chrome على الـ CSS
  الفعلي) لكل المقاسات: ديسكتوب/تابلت/موبايل + drawer مفتوح/مغلق، لوحتي الأستاذ والأدمن.
  215 اختبار أخضر، `check` نظيف.

## 2. السبب الجذري

1. **التخزين المؤقت (cache) — الأساسي:** `whitenoise.CompressedStaticFilesStorage`
   (بلا hashing) يعتمد على `?v=` لكسر الـ cache. لذا أي معاينة قبل النشر الكامل +
   تحديث الـ `?v=` كانت تخلط قالبًا جديدًا مع CSS قديم.
2. **تشابك طبقات الـ media queries:** كان في `teacher.css` كتل `@media (max-width:980)`
   قديمة (سطرين) + كتلة 769/768 من 16.6A.1، فينشأ في نطاق اللابتوب (769–980) سلوك
   متضارب (sidebar static مقابل sticky، nav عمودين، topbar عمودي). نفس الشيء في
   `control.css` عند 860/1100.
3. **الـ overlay:** كان أول عنصر في شبكة `.teacher-shell` → لو لم يُطبَّق `display:none`
   (CSS قديم) يسرق العمود الأول ويزيح كل شيء.
4. **breakpoint مرتفع:** 980px جعل اللابتوب الصغير يدخل وضع الموبايل.
5. **لماذا لم تُمسك بالاختبارات؟** اختبارات الـ DOM/CSS النصية لا «ترى» التخطيط
   المرئي. عولج الآن بـ **لقطات headless Chrome حقيقية** + حراسات CSS أدقّ (sticky vs
   fixed، `!important`، breakpoint).

> **revert للـ commit b0ac3f5؟** لا — لا حاجة لـ revert. السبب لم يكن منطق خاطئًا بل
> cache + تشابك CSS. 16.6A.2 يعيد بناء الطبقة بشكل حاسم فوقه.

## 3. الملفات المعدّلة

| File | Change | Reason |
|---|---|---|
| `teacher_portal/.../teacher.css` | كتلتا `@media (min-width:1024px)` / `@media (max-width:1023px)` حاسمتان؛ `!important` لإخفاء toggle/overlay على الديسكتوب؛ `transform:none!important`؛ override للـ nav/topbar القديمة؛ metrics `auto-fit` | إزالة تشابك الطبقات وضمان شريط ثابت بلا drawer على الديسكتوب |
| `platform_admin/.../control.css` | نفس الكتلتين الحاسمتين للأدمن | نفس السبب |
| `static/js/dashboard-shell.js` | `open()` يخرج مبكرًا لو زر القائمة `display:none` (حارس ديسكتوب) | لا فتح drawer على الديسكتوب برمجيًا |
| `teacher_portal/.../base.html`, `platform_admin/.../base.html` | bump `?v=p166a2`؛ (الـ overlay منقول لآخر الـ shell سابقًا) | كسر الـ cache + إخراج overlay من صدارة الـ grid |
| `*/tests/test_dashboard_shell.py` | حراسات 16.6A.2 (sticky≠fixed، hamburger hidden، grid، version، JS guard) | منع تكرار العطل |
| `docs/screenshots/dashboard-shell/*.png` | 6 لقطات تحقّق | دليل بصري |

## 4. Desktop Layout Verification (≥1024px)

* **مُثبَت بلقطات:** `teacher_desktop_1440.png` + `admin_desktop_1440.png`.
* الشريط الجانبي **ثابت يمين** (RTL) داخل شبكة `16rem minmax(0,1fr)` — المحتوى يملأ
  الباقي يسار، **لا طغيان، لا مساحة فارغة، لا hamburger**، الكروت في grid منتظم غير مقصوص.
* `position: sticky` (وليس fixed)، `transform: none !important`،
  `.ds-drawer-toggle/.ds-overlay { display: none !important }`.

## 5. Mobile Layout Verification (≤1023px)

* **مُثبَت بلقطات:** `teacher_mobile_390_closed/open.png`, `teacher_tablet_768.png`,
  `admin_mobile_390_open.png`.
* مغلق: hamburger ظاهر، الشريط مخفي، الكروت تتراصّ عموديًا، لا scroll أفقي.
* مفتوح: الشريط **ينزلق من اليمين في RTL** (`[dir=rtl] … translateX(100%)`)، overlay
  يعتّم المحتوى، إغلاق بالخلفية/Escape/عند اختيار رابط، قفل تمرير الجسم أثناء الفتح.
* التابلت 768 لا ينكسر (وضع drawer + كروت auto-fit 4 أعمدة).

## 6. Screenshots Evidence

| الحالة | الملف |
|---|---|
| Teacher — Desktop 1440 (RTL) | `docs/screenshots/dashboard-shell/teacher_desktop_1440.png` |
| Teacher — Tablet 768 | `docs/screenshots/dashboard-shell/teacher_tablet_768.png` |
| Teacher — Mobile 390 (drawer مغلق) | `docs/screenshots/dashboard-shell/teacher_mobile_390_closed.png` |
| Teacher — Mobile 390 (drawer مفتوح، من اليمين) | `docs/screenshots/dashboard-shell/teacher_mobile_390_open.png` |
| Admin — Desktop 1440 (RTL) | `docs/screenshots/dashboard-shell/admin_desktop_1440.png` |
| Admin — Mobile 390 (drawer مفتوح) | `docs/screenshots/dashboard-shell/admin_mobile_390_open.png` |

> اللقطات وُلِّدت بـ headless Chrome على الـ CSS الفعلي (لا توجد Playwright في المستودع).

## 7. Tests

| Test | Result |
|---|---|
| test_teacher_shell_desktop_sidebar_not_drawer (sticky≠fixed @1024) | ✅ |
| test_admin_shell_desktop_sidebar_not_drawer | ✅ |
| test_hamburger_hidden_on_desktop / test_admin_hamburger_hidden_on_desktop | ✅ |
| test_sidebar_does_not_overlap_content_desktop (grid 16rem) | ✅ |
| test_teacher_dashboard_overlay_not_first_grid_child | ✅ |
| test_dashboard_shell_js_exits_early_on_desktop | ✅ |
| test_*_css_version_bumped (p166a2) | ✅ |
| اختبارات shell السابقة (drawer/RTL/منع الطالب) | ✅ |
| regression: `teacher_portal` + `platform_admin` + `accounts` | ✅ **215 OK** |
| `manage.py check` | ✅ نظيف |

## 8. Commands Run

```
google-chrome --headless=new --window-size=1440,900 --screenshot=... file://teacher_preview.html   # + 768/390/open
DJANGO_SETTINGS_MODULE=config.settings.test python manage.py test platform_admin.tests.test_dashboard_shell teacher_portal.tests.test_dashboard_shell   # 17 OK
DJANGO_SETTINGS_MODULE=config.settings.test python manage.py test teacher_portal platform_admin accounts   # 215 OK
DJANGO_SETTINGS_MODULE=config.settings.test python manage.py check   # clean
```

## 9. Remaining Issues

* **P0/P1:** لا يوجد — التخطيط مُصلَح ومُثبَت بصريًا.
* **P2:** عند النشر **يجب** تشغيل `update.sh` (يعمل `collectstatic`) ثم hard-refresh
  للمتصفّح؛ لأن السبب الأصلي كان الـ cache، فالنشر الكامل + `?v=p166a2` ضروريان لظهور
  الإصلاح حيًّا.
* **P3:** موضع زر القائمة على الموبايل الضيق (390) يميل لليسار بدل اليمين بسبب
  `space-between` + الالتفاف — وظيفيًا سليم (ظاهر وقابل للنقر)، تحسين تجميلي مؤجَّل.
  الـ media queries القديمة (980/860/560/1100) ما زالت موجودة لكن صار سلوك الـ shell
  محسومًا بالكتلتين 1024/1023؛ تنظيفها لاحقًا تجميلي.

## 10. Final Decision

**Dashboard shell fixed — proceed to UX redesign.** الشريط ثابت على الديسكتوب بلا
hamburger، المحتوى يملأ العرض بلا فراغ/قصّ، الموبايل drawer فقط، RTL سليم — كله مُثبَت
بلقطات حقيقية + 215 اختبار أخضر و`check` نظيف.

> **مهم:** لن أبدأ Quiz Builder تلقائيًا. ينتظر تأكيدك بعد:
> 1. تشغيل `sudo bash /opt/onlenco/scripts/update.sh` على الإنتاج.
> 2. hard-refresh (Ctrl+Shift+R) ومعاينة `/teacher/dashboard/` و`/admin/`.

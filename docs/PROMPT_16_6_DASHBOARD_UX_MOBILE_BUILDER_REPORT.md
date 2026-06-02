# تقرير Prompt 16.6 — Admin/Teacher Dashboard UX + Mobile Course/Quiz Builder

> **الحالة:** المرحلة 0 (الفحص) اكتملت. التنفيذ مُتدرّج وآمن — هذا التقرير يُحدَّث مع كل
> دفعة. لم تُكسر أي flows، ولم تُولَّد وسائط، ولم تتغيّر حالة أي موضوع منشور.

## 1. الملخص التنفيذي

* **ماذا تم حتى الآن؟** فحص شامل (12 منطقة عبر workflow متوازي للقراءة فقط) لكل قوالب
  الأدمن/المعلّم، الـ CSS، الموبايل، الـ RTL، النماذج، والبنّائين.
* **الاكتشاف المحوري:** المنصّة **تمتلك Design System ناضجًا بالفعل**
  (`onlenco-tokens.css` + `onlenco-components.css`): ألوان دلالية (teal/green/amber/red)،
  خطوط Inter + Cairo، مسافات بقاعدة 4px، مكوّنات (`.btn-*`، `.input-base`، `.table-base`،
  `.badge-*`، `.modal-*`، `.empty-state`)، و logical properties صديقة للـ RTL.
* **المشكلة الحقيقية:** لوحتا الأدمن (`control.css`) والمعلّم (`teacher.css`) **لا
  تستخدمان هذا النظام بالكامل** — توكنات مكرّرة، ألوان ثابتة، **لا drawer للموبايل**،
  وجداول كثيفة (7–11 عمود) بلا بديل بطاقات على الموبايل.
* **الخلاصة:** الهدف = **توحيد + إكمال** فوق النظام الموجود (آمن، تدريجي)، وليس إعادة بناء.

## 2. Inspection Findings (نتائج الفحص)

### 2.1 الإطار/الستايل الحالي
Tailwind (Play CDN، بدون build) فوق CSS مكتوب يدويًا في تتالٍ ثلاثي:
`onlenco-tokens.css` → `onlenco-components.css` → `onlenco.css`، ثم CSS لكل ميزة. القيم
كلها HSL CSS variables. اللوحات لها CSS منفصل: `platform_admin/.../control.css` (نطاق
`.control-*`، توكنات `--cc-*`) و `teacher_portal/.../teacher.css` (نطاق `.teacher-*`،
توكنات `--tp-*`) — يتبنّيان النظام الموحّد جزئيًا فقط.

### 2.2 أصعب/أقبح الصفحات
* قوائم الطلاب (admin 11 عمود / teacher 9 عمود) — بلا بديل بطاقات، تطفح تحت ~1200px.
* بنّاء الكويز (`teacher_portal/quizzes/questions.html`) — لوحتان، textarea خام لـ
  `options_text` (JSON/أسطر)، بلا معاينة، بلا إعادة ترتيب، بلا UI حسب نوع السؤال.
* `quizzes/question_edit.html` — `form.as_p` عارٍ، بلا UI خاص بالنوع.
* مراجعة المحتوى/الوسائط (`content_review/*`, `media/review.html`) — جداول كثيفة + نماذج
  POST متعددة inline في صف واحد + inline styles، بلا سلوك متجاوب.
* `challenge_session.html` — 380+ سطر CSS inline يستضيف كل أنماط الـ 20+ نوع سؤال.
* لوحات `dashboards/readonly.html` — ألوان ثابتة (FEF9C3/FCD34D)، 8 بطاقات مكدّسة.
* `lessons/form.html` — 4 أقسام، بلا تحرير خطوات الدرس، رفع ملفات بدائي.

### 2.3 مشاكل الموبايل
* **لا drawer/hamburger** في أيٍّ من الـ shells؛ الشريط الجانبي لا يختفي (يتحوّل لشبكة
  عمودين). الـ topbar بـ 5 أزرار + بحث 220px يزدحم/يطفح على الهواتف.
* الجداول (7–11 عمود) بلا overflow wrapper ولا بديل بطاقات → scroll أفقي.
* شبكات الإحصائيات `repeat(4,1fr)` تنهار مباشرة لعمود واحد بلا بديل عمودين للتابلت.
* أشرطة الفلاتر `minmax(220px)…` تنكسر لأربعة أسطر+ على التابلت.

### 2.4 أصعب النماذج
* بنّاء الكويز/السؤال — نموذج عام واحد لكل الـ 32 نوع، JSON خام، بلا معاينة/ترتيب.
* نموذج سؤال تحديد المستوى — JSON خام لـ options و scoring_rubric، بلا تحقق.
* بنّاء الدرس — حقول ثنائية اللغة + Quill، بلا تحرير خطوات/سكربت صوت/برومبت صورة.
* إنشاء الكورس — 12 حقلًا في نموذج مسطّح، بلا wizard، بلا تمييز إجباري/اختياري،
  بلا فصل "حفظ مسودة / إرسال للمراجعة".

### 2.5 حالة الـ RTL
الأساس صلب (lang/dir عبر context processor + middleware، Cairo للعربية، logical
properties في الطبقات المشتركة). **الضعف في اللوحات:** `control.css`/`teacher.css`
يعتمدان على `grid-template-columns: 280px 1fr` فيزيائي (الشريط لا ينعكس يمينًا في RTL)،
صفوف flex لا تنعكس، وألوان hex ثابتة. **لا يوجد اختبار RTL آلي.**

## 3. Design System (الموجود + ما سنضيفه)

* **القائم (نُعيد استخدامه):** التوكنات الدلالية، الخطوط، المسافات، `.btn-*`،
  `.input-base/.select-base/.textarea-base`، `.table-base`، `.badge-*/.pill-*`،
  `.card-*`، `.modal-*`، `.alert-*`، `.empty-state`، `.skeleton/.spinner`،
  `.pagination-base`، `[dir=rtl] .rtl-flip`، سجلّ `QUESTION_TYPE_REGISTRY` (32 نوع).
* **ما سيُنشأ:** غلاف جدول متجاوب (table→cards)، نمط drawer/hamburger للـ shells،
  مُنتقي أنواع الأسئلة المرئي، محرّر metadata حسب النوع، معاينة كطالب + drag-reorder،
  modal تأكيد للإجراءات الخطرة، شريط إجراءات لاصق (حفظ/إرسال)، مساعد JSON، شريط فلاتر
  متجاوب، شبكة بطاقات KPI ببديل عمودين، استخراج CSS مشترك لمُصيِّري الأسئلة.

## ✅ الدفعة 1 — الأساسات الآمنة (المراحل 1–3) — مُنفَّذة

> CSS وقوالب shell فقط (additive)، بلا لمس أي backend/flow. تخدم **كل** صفحة داخلية.

### ما تم
* **drawer/hamburger للموبايل** للوحتي الأدمن والمعلّم: الشريط الجانبي يتحوّل إلى
  off-canvas drawer ينزلق من الحافة، مع زر hamburger في الـ topbar، و overlay، وإغلاق
  بالضغط على الخلفية / Escape / عند اختيار رابط. (`static/js/dashboard-shell.js` —
  progressive enhancement، يُحمّل في الـ shellين.)
* **انعكاس RTL:** الـ drawer ينزلق من اليمين في العربية (`[dir=rtl]` + logical
  properties `inset-inline-start` + `100dvh`).
* **إمكانية الوصول:** `:focus-visible` rings على روابط/أزرار اللوحتين + أهداف لمس
  `min-height:44px` على `@media (pointer: coarse)` (WCAG 2.5.5)، و `aria-controls` /
  `aria-expanded` على زر الـ hamburger.
* **غلاف جدول متجاوب:** فئة `.table-wrap` (overflow-x + لمس) جاهزة لصفحات القوائم،
  و `.control-panel` يمرّر الجداول الكثيفة أفقيًا على الموبايل.
* **التوكنات:** مؤكَّد أنها موحّدة بالفعل (Phase 7/8) — اكتُفي بإضافة a11y فوقها.

### الملفات
* جديد: `static/js/dashboard-shell.js`.
* مُعدّل: `platform_admin/.../control.css`، `teacher_portal/.../teacher.css`
  (كتلة مُلحقة في النهاية، override آمن للـ media query القديمة).
* مُعدّل: `platform_admin/.../base.html`، `teacher_portal/.../base.html`
  (زر hamburger + `id` للـ sidebar + `ds-drawer` + overlay + ربط الـ JS).

### الاختبارات (الدفعة 1)
| Test | Result |
|---|---|
| test_dashboard_shell_renders_desktop (admin) | ✅ |
| test_dashboard_shell_has_mobile_drawer (admin) | ✅ |
| test_dashboard_shell_rtl_safe (admin) | ✅ |
| test_student_cannot_access_admin_dashboard | ✅ |
| test_teacher_dashboard_renders | ✅ |
| test_teacher_dashboard_has_mobile_drawer | ✅ |
| test_teacher_dashboard_rtl_safe | ✅ |
| test_student_cannot_access_teacher_dashboard | ✅ |
| regression: `platform_admin` + `teacher_portal` (113 اختبار) | ✅ OK |
| `manage.py check` | ✅ نظيف |

### الأوامر
```
DJANGO_SETTINGS_MODULE=config.settings.test python manage.py test platform_admin.tests.test_dashboard_shell teacher_portal.tests.test_dashboard_shell   # 8 OK
DJANGO_SETTINGS_MODULE=config.settings.test python manage.py test platform_admin teacher_portal   # 113 OK
DJANGO_SETTINGS_MODULE=config.settings.test python manage.py check   # clean
```

### ملاحظات أمان (الدفعة 1)
* لم تتغيّر أي views/نماذج/منطق؛ تعديلات تقديمية + JS تحسيني فقط.
* مطابقة active-nav لم تُمَس؛ نماذج المراجعة inline لم تُمَس؛ دروس 01–06 لم تُمَس.
* كل وسوم Django على سطر واحد (التزامًا بقيد المشروع).

## 4–11. (باقي الأقسام تُملأ مع الدفعات التالية)

## 12. خطة التنفيذ المرحلية (الأقل خطورة أولًا)

> مرتّبة من توليفة الفحص: الأساسات الآمنة (CSS بحتة) أولًا، النماذج الحسّاسة أخيرًا.

1. **توكنات اللوحات** — مزامنة `--cc-*`/`--tp-*` مع التوكنات الدلالية + focus rings +
   أهداف لمس 44px. (CSS بحتة، بلا تغيير markup/flow.)
2. **غلاف جدول متجاوب** — `overflow-x:auto` + إشارة scroll + بديل بطاقات على الموبايل،
   يُطبَّق على `.control-table`/`.teacher-table`. (يحل أسوأ كسر موبايل بلا تغيير بيانات.)
3. **إصلاح الـ shells** — drawer/hamburger + topbar متجاوب + انعكاس RTL للشبكة + 100dvh.
4. **إعادة تصميم لوحات الـ dashboard** — بطاقات/إحصائيات + بديل عمودين، تقديمي غالبًا.
5. **صفحات القوائم** — طلاب/كورسات/دروس/كويزات على المكوّنات الجديدة.
6. **النماذج الصعبة (أخيرًا)** — بنّاء الكويز/السؤال، تحديد المستوى، الدرس، الكورس wizard.
7. **مراجعة الوسائط/المحتوى + `challenge_session.html`** — استخراج CSS مشترك ثم إعادة تنسيق.

## 13. Tests / 14. Commands / 15. Final Decision / 16. Next Phase
(تُملأ مع التنفيذ.)

## أهم مخاطر يجب الحذر منها أثناء التنفيذ
* مطابقة active-nav بالـ substring هشّة (`student` يطابق `students` و `student_approvals`).
* نماذج المراجعة inline متعددة في صف واحد — إعادة هيكلتها قد تُسقط hidden fields وتكسر
  آلة حالة المراجعة (backend-only، بلا تحقق client).
* A0 World ودروس 01–06 منشورة فعلًا — أي refactor للتوكنات/الـ CSS يتطلّب فحص بصري.
* قيد سطر-واحد لوسوم Django (ذاكرة المشروع) أثناء إعادة تنسيق القوالب.
* لا اختبارات RTL آلية — التحويل لـ logical properties قد يكسر تخطيط العربية بصمت.

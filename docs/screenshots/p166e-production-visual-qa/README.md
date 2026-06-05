# لقطات شاشة الفحص البصري للإنتاج — Prompt 16.6E

> هذه اللقطات تُلتقَط **من الإنتاج** (`https://<prod-host>`) بعد تشغيل `update.sh`،
> بمتصفح حقيقي + hard-refresh (Ctrl+Shift+R) أو نافذة Incognito.
> لا يمكن التقاطها من صندوق التطوير (لا متصفح/لا وصول للإنتاج) — لذا هذا المجلد
> يحتوي قائمة المطلوب فقط، ويملؤها المالك بالصور.

## Desktop
- [ ] `admin-dashboard-desktop.png` — `/admin/`
- [ ] `admin-students-list-desktop.png` — `/admin/students/`
- [ ] `admin-student-detail-top-desktop.png` — `/admin/students/<id>/` (أعلى الصفحة)
- [ ] `admin-student-detail-actions-desktop.png` — لوحة الإجراءات (أزرار طبيعية + زر «إعادة فتح اختبار التحدث»)
- [ ] `admin-student-detail-learning-progress-desktop.png` — كارت Learning Progress
- [ ] `admin-teachers-desktop.png` — `/admin/teachers/`
- [ ] `teacher-dashboard-desktop.png` — `/teacher/dashboard/`
- [ ] `teacher-students-desktop.png` — `/teacher/students/`
- [ ] `teacher-course-create-desktop.png` — `/teacher/courses/create/`
- [ ] `teacher-lesson-create-desktop.png` — `/teacher/courses/<id>/lessons/create/`
- [ ] `placement-question-new-desktop.png` — `/admin/placement-questions/new/`
- [ ] `lesson-intro-no-phase95.png` — `/courses/<c>/lessons/<l>/step/intro/` (لا Phase 9.5)
- [ ] `lesson-vocabulary-no-phase95.png` — `/courses/<c>/lessons/<l>/step/vocabulary/`

## Mobile 390
- [ ] `admin-students-mobile.png`
- [ ] `admin-student-detail-mobile.png`
- [ ] `teacher-students-mobile.png`
- [ ] `teacher-course-create-mobile.png`
- [ ] `lesson-intro-mobile.png`

## معايير كل لقطة
- لا sidebar مقصوص / مكرر / يغطي المحتوى.
- لا horizontal browser scroll (تحقّق بسكربت الـoffenders).
- أزرار تفاصيل الطالب طبيعية (ليست ضخمة) + تبويبات عربية.
- صفحات إنشاء الكورس/الدرس ليست فارغة والفورم ظاهر.
- صفحة الدرس: لا Phase 9.5 / لا raw prompt/script، والصوت placeholder نظيف بلا player مكسور.

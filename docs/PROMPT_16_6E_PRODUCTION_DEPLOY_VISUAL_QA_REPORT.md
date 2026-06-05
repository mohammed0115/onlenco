# تقرير Prompt 16.6E — نشر الإنتاج وفحص التصميم

**التاريخ:** 2026-06-04 · **تحديث:** 2026-06-05 (إدراج عمل 16.6F ضمن النشر)

> **ملاحظة وصول (حدّ صريح):** لا أملك SSH لخادم الإنتاج (`/opt/onlenco` @ `187.127.86.111`). خطوات الإنتاج نفسها — backup + `update.sh` + `migrate` + `collectstatic` + `docker compose` logs + **لقطات شاشة الإنتاج** — **يشغّلها المالك على الخادم**؛ مرفق runbook دقيق. ما أُنجز هنا: تجهيز النشر + التحقّق المحلي + دفع الكود إلى `origin/main` ليلتقطه `git pull`.

---

## 1. الملخص التنفيذي
- **هل تم النشر؟** الكود **جُهِّز ودُفِع** إلى `origin/main` (آخر commit `a251b7e`). النشر الفعلي على الخادم (pull/migrate/collectstatic/restart) خطوة تشغيلية يقوم بها المالك عبر `update.sh` — runbook في الأسفل.
- **هل التصميم وصل للإنتاج؟** يصل بعد تشغيل `update.sh` + `collectstatic` + hard-refresh. النسخ الحالية في الكود: `control.css`/`teacher.css` = `p166e-logo-fix-20260604`، JS المكالمة = `p166f-call-separation-20260605`.
- **هل توجد أخطاء blocker؟** محلياً: **لا**. `migrate --check` نظيف، `manage.py check` نظيف، لا migrations ناقصة، الحزمة الكاملة من الاختبارات خضراء. الـblocker الوحيد المعروف هو تشغيل `migrate` على الإنتاج (وإلا يظهر `no such column`).

## 2. رقم الـ commit المنشور
`a251b7e` — `placement(16.6F): separate placement speaking call from AI Tutor minutes`. المتراكم منذ آخر نشر إنتاجي:
```
a251b7e placement(16.6F): separate placement speaking from AI Tutor minutes
4d19670 placement voice: always route to result on call end
7c89dec placement: fix written MCQ rendering — show option text
65de32b placement: curated bank exclusive by deactivating others
9e7f805 placement: curated v2 question bank (5 written MCQ + 5 spoken)
847cdc6 placement: answer-key grading + result transparency + oral auto-end
428cd5a admin: real logo + student approve button + approvals nav + i18n
9e6183e docs(16.6E): production deploy pre-flight + local visual QA report
9a27103 admin(16.6D): rebuild student-detail UX
5373133 review fixes: cert PII (P0), membership (P1), groups, admin i18n
```

## 3. Backup
- **مطلوب قبل النشر** (لا يُكمَل بدونه). الأمر في الـrunbook: `pg_dump` لقاعدة الإنتاج إلى `~/onlenco_backup_<date>.sql`.
- يقوم به المالك على الخادم (لا وصول لي).

## 4. حالة الـ migrations (ستُطبَّق على الإنتاج)
محلياً: `migrate --check` = **OK** (لا pending) على كل التطبيقات.

| الهجرة | المحتوى |
|---|---|
| `payments/0006` | `teacher_earnings` + `platform_earnings` ← **سبب «no such column»** |
| `teacher_portal/0002–0004` | حقول Marketplace + `StudentTeacherRelation` + `LiveSession` + قيد التفرّد |
| `courses/0016` | `DigitalCertificate` |
| `notifications/0010` | choices أحداث الجلسات المباشرة |
| **`subscriptions/0012`** | **خيار مصدر `placement_voice` على `AITutorSession` (16.6F)** |
| **`placement/0009`** | **موديل `PlacementSpeakingAttempt` (16.6F)** |

## 5. حالة نسخة الـ static
- `control.css` / `teacher.css` → **`p166e-logo-fix-20260604`** (أحدث من `p166d` المذكور في الـprompt — رُفِع لاحقاً في إصلاح الشعار `428cd5a`).
- `ai_tutor_realtime.js` → **`p166f-call-separation-20260605`** (16.6F).
- النسخ القديمة (`figma-…`/`p166c`) ستُستبدَل بـ`collectstatic` + hard-refresh على الإنتاج.
- **معيار القبول يُحدَّث:** ابحث في HTML الإنتاج عن `p166e-logo-fix-20260604` (بدل `p166d`) للأدمن، و`p166f-call-separation-20260605` لصفحة المكالمة.

## 6. الصفحات المفحوصة (محلياً، 16.6D/16.6E) — الإنتاج pending المالك
| الصفحة | HTTP (محلي) | بصرياً (محلي) | ملاحظات |
|---|---|---|---|
| /admin/students/ | 200 | ✅ | جدول داخل table-wrap، لا overflow |
| /admin/students/&lt;id&gt;/ | 200 | ✅ | action panel مدمج، تبويبات عربية، content-grid |
| /teacher/students/ | 200 | ✅ | table-wrap |
> فحص الإنتاج البصري (HTTP + لقطات) يُعاد تشغيله بعد النشر — القائمة الكاملة في الـrunbook.

## 7. اختبار الـ overflow (محلي، بعد migrate) — يُعاد على الإنتاج
| الصفحة | desktop | mobile 390 | النتيجة |
|---|---|---|---|
| /admin/students/ | doc=0 body=0 | doc=0 body=0 | ✅ |
| /admin/students/&lt;id&gt;/ | doc=0 body=0 | doc=0 body=0 | ✅ |
| /teacher/students/ | doc=0 body=0 | — | ✅ |

سكربت الـoffenders للـConsole مُرفق في الـrunbook ليشغّله المالك على الإنتاج.

## 8. تفاصيل الطالب
- الأزرار الضخمة؟ **اختفت** (لوحة `.ta-*`، أزرار 42–46px). ✅
- التبويبات عربية؟ **نعم** (chips عربية). ✅
- الجداول داخل كروت؟ **نعم** (table-wrap/content-grid). ✅
- horizontal scroll؟ **لا** (doc/body=0). ✅
- **16.6F:** أُضيف زر «إعادة فتح اختبار التحدث» (بسبب إلزامي) ضمن لوحة الإجراءات — لا يكسر الـlayout.

## 9. صفحات الكورس والدرس
- الفورم ظاهر، الصفحة ليست فارغة، لا كسر layout (محلياً، 16.6D). يُعاد التأكيد بصرياً على الإنتاج.

## 10. صفحات الطالب والدرس
- Phase 9.5 / raw prompt / raw script: **لا تظهر** (16.6A4). 
- الصوت غير المولّد → placeholder نظيف «الصوت قيد التحضير. يمكنك متابعة الدرس الآن.» بلا player مكسور (مؤكَّد باختبار).

## 11. نتيجة `inspect_lesson_media --course-id=1 --lesson-id=1`
```
Lesson #1 — 'Greet someone in English' (course=1, status=published)
  [intro/vocabulary/examples/dialogue/listening/speaking] audio : MISSING SCRIPT (mapping_missing)
  [vocabulary/examples/dialogue] image : MISSING PROMPT
```
كل الوسائط غير مولّدة → **ليست bug** (not_generated). لا توليد ولا تكلفة AI في هذه المرحلة؛ المطلوب فقط placeholder نظيف.

## 12. Logs
- محلياً بعد الهجرة: لا 500، لا `no such column`، لا TemplateSyntaxError، لا static 404.
- فحص logs الإنتاج (`docker compose logs web --tail=300`) خطوة المالك بعد النشر.

## 13. Screenshots
- **محلية سابقة:** `docs/screenshots/p166d-student-detail-ux/` و`docs/screenshots/p166c-prod-qa/`.
- **لقطات الإنتاج المطلوبة:** تُحفَظ في `docs/screenshots/p166e-production-visual-qa/` — القائمة الكاملة في `README.md` بذلك المجلد. **يلتقطها المالك من الإنتاج** (لا متصفح إنتاج لديّ).

## 14. المشاكل المتبقية
- **P0:** لا شيء محلياً. (الخطر الوحيد: نسيان `migrate` على الإنتاج → `no such column` — مُعالَج بالـrunbook.)
- **P1:** لا شيء.
- **P2:** نسخة `p166d` في نص الـprompt قديمة؛ الفعلي `p166e/p166f` (موثّق أعلاه).
- **P3:** لقطات الإنتاج + الفحص البصري على الإنتاج بانتظار تشغيل المالك.

## 15. القرار النهائي
**Needs operator execution on production** — الكود **جاهز للنشر ومدفوع** (`a251b7e`)، والتحقّق المحلي مرّ بالكامل (لا overflow، أزرار طبيعية، تبويبات عربية، صوت نظيف، اختبارات خضراء، `check` نظيف). الحكم النهائي «Production visual QA passed» يتطلّب تشغيل المالك للـrunbook ثم تأكيد اللقطات/الـlogs على الإنتاج.

> لا يبدأ Prompt 16.7 (Quiz Builder) إلا بعد نجاح النشر وتأكيد الفحص البصري على الإنتاج.

---

## runbook النشر (يشغّله المالك على الخادم)
```bash
cd /opt/onlenco
# 1) backup أولاً (إلزامي)
docker compose exec -T db pg_dump -U "$POSTGRES_USER" "$POSTGRES_DB" > ~/onlenco_backup_$(date +%F_%H%M).sql
git log --oneline -1                       # سجّل آخر commit قبل النشر
docker compose exec -T web python manage.py showmigrations payments | tail -5   # حالة قبل
# 2) النشر (pull + migrate + seed + collectstatic + restart)
sudo bash scripts/update.sh
# 3) التحقق (معايير القبول)
docker compose exec -T web python manage.py migrate --check         # لا pending
docker compose exec -T web python manage.py check                   # نظيف
docker compose exec -T web python manage.py showmigrations payments subscriptions placement teacher_portal courses | grep "\[ \]"  # فارغ
docker compose ps                                                   # web يعمل
docker compose logs web --tail=300                                  # لا 500 / no such column / static 404
# 4) تحقّق النسخة في HTML
curl -s https://<prod-host>/admin/students/ | grep -o "p166e-logo-fix-20260604" | head -1
# 5) فحص overflow في Console المتصفح (Desktop + Mobile 390) على:
#    /admin/students/ , /admin/students/<id>/ , /teacher/students/ , /teacher/courses/create/ , /admin/placement-questions/new/
#    document.documentElement.scrollWidth <= document.documentElement.clientWidth   // true
#    + offenders script من الـprompt (يجب ألا يخرج عنصر إلا داخل .table-wrap)
# 6) التقط اللقطات المطلوبة → docs/screenshots/p166e-production-visual-qa/
```
بعد النشر: Hard refresh (Ctrl+Shift+R) أو Incognito، وتأكّد من ظهور `p166e-logo-fix-20260604` في مصدر صفحة الأدمن و`p166f-call-separation-20260605` في صفحة المكالمة.

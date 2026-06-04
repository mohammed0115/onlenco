# تقرير Prompt 16.6E — نشر الإنتاج وفحص التصميم

**التاريخ:** 2026-06-04

> **ملاحظة وصول:** لا أملك SSH لخادم الإنتاج (`/opt/onlenco` @ `187.127.86.111`). خطوات النشر نفسها (backup + `update.sh` + migrate + collectstatic) **يشغّلها المالك على الخادم** — مرفق runbook دقيق. ما أُنجز آلياً: الفحص قبل النشر + تحقّق بصري **محلي** بمتصفح حقيقي.

---

## 1. الملخص
- **الكود جاهز للنشر:** working tree نظيف، كله مدفوع، لا migrations ناقصة، `manage.py check` نظيف.
- **تحقّق محلي بمتصفح حقيقي** (بعد `migrate` على الـ dev DB): صفحة تفاصيل الطالب المعاد بناؤها + القوائم بلا تمرير أفقي (`doc=0, body=0`).
- **الاكتشاف الحرج مؤكَّد ومُعالَج محلياً:** قبل الهجرة ظهر `no such column: payments_paymentsubmission.teacher_earnings`؛ بعد `migrate` اختفى. **هذا يثبت ضرورة `migrate` على الإنتاج.**

## 2. رقم الـ commit المُراد نشره
`9a27103` — `admin(16.6D): rebuild student-detail UX`. آخر 6 commits متراكمة منذ آخر نشر:
```
9a27103 admin(16.6D): student-detail UX
5373133 review fixes: cert PII (P0), membership (P1), groups, admin i18n
61b85a6 auth: honor safe ?next=
d235cf0 marketplace(5): digital certificates
d9162a3 marketplace(3): student groups + dashboard
96b649b fix: bug audit (relation/refund/reminder/question)
```

## 3. حالة الـ migrations (ستُطبَّق على الإنتاج)
| الهجرة | المحتوى |
|---|---|
| `payments/0006` | `teacher_earnings` + `platform_earnings` ← **سبب «no such column»** |
| `teacher_portal/0002` | حقول Marketplace + `StudentTeacherRelation` |
| `teacher_portal/0003` | `LiveSession` |
| `teacher_portal/0004` | قيد تفرّد علاقة الطالب-المعلم |
| `courses/0016` | `DigitalCertificate` |
| `notifications/0010` | choices أحداث الجلسات المباشرة |

محلياً: `migrate --check` = OK (لا pending)، وعمود `teacher_earnings` موجود.

## 4. حالة نسخة الـ static
- `control.css` رُفِع إلى **`p166d-student-detail-ux-20260604`** (مؤكَّد في HTML المحلي).
- ⚠️ الإنتاج حالياً يخدم نسخاً قديمة (`figma-20260521`/`p166c`) — **النشر + collectstatic + hard-refresh يحدّثها**.

## 5. الصفحات المفحوصة (محلياً، متصفح حقيقي — 16.6D)
| الصفحة | الحالة | ملاحظات |
|---|---|---|
| /admin/students/ | ✅ | جدول داخل table-wrap، لا overflow |
| /admin/students/&lt;id&gt;/ | ✅ | action panel مدمج، تبويبات عربية، content-grid |
| /teacher/students/ | ✅ | table-wrap |

## 6. اختبار الـ overflow (16.6D، بعد migrate محلي)
| الصفحة | desktop | mobile | النتيجة |
|---|---|---|---|
| /admin/students/ | doc=0 body=0 | doc=0 body=0 | ✅ |
| /admin/students/&lt;id&gt;/ | doc=0 body=0 | doc=0 body=0 | ✅ |
| /teacher/students/ | doc=0 body=0 | — | ✅ |

## 7. فحص تفاصيل الطالب
- الأزرار الضخمة؟ **اختفت** (لوحة `.ta-*` مدمجة، أزرار 42–46px). ✅
- التبويبات الإنجليزية؟ **اختفت** (chips عربية). ✅
- الكروت الفارغة الضخمة؟ **اختفت** (content-grid متوازن + empty states). ✅
- horizontal scroll؟ **لا** (doc/body=0). ✅
- اللقطات: `docs/screenshots/p166d-student-detail-ux/` (desktop + mobile).

## 8. فحص صوت الدرس (`inspect_lesson_media --course-id=24 --lesson-id=465`)
```
Lesson #465 'Challenge Types Showcase' (course=24, status=published)
  [intro/vocabulary/examples/dialogue/listening/speaking] audio : MISSING SCRIPT (mapping_missing)
  images : MISSING PROMPT
```
كل الصوت/الصور غير موجودة → **يجب أن تظهر رسالة «الصوت قيد التحضير. يمكنك متابعة الدرس الآن.» بلا player مكسور** (مؤكَّد باختبار `test_lesson_media_rendering`). ليست bug — لا توليد ولا تكلفة AI.

## 9. الأخطاء
- محلياً بعد الهجرة: لا 500، لا `no such column`. (قبل الهجرة: الخطأ يظهر — لذا الهجرة إلزامية على الإنتاج.)
- **الاختبارات:** 2294+ خضراء، `check` نظيف.

## 10. اللقطات
- `docs/screenshots/p166d-student-detail-ux/` — التصميم الجديد محلياً (desktop + mobile).
- `docs/screenshots/p166c-prod-qa/` — حالة الإنتاج قبل النشر (baseline، overflow=0 للـ shell، تصميم قديم).

## 11. القرار النهائي
**التحقّق المحلي مرّ** — التصميم الجديد يعمل (لا overflow، أزرار طبيعية، تبويبات عربية، صوت نظيف). الكود **جاهز للنشر**.
> الحالة النهائية للإنتاج تتطلّب تشغيل المالك لـ runbook النشر أدناه (لا أملك SSH)، ثم إعادة الفحص البصري على الإنتاج للتأكيد.

---

## runbook النشر (يشغّله المالك على الخادم)
```bash
cd /opt/onlenco
# 1) backup أولاً
docker compose exec -T db pg_dump -U "$POSTGRES_USER" "$POSTGRES_DB" > ~/onlenco_backup_$(date +%F_%H%M).sql
git log --oneline -1          # سجّل آخر commit قبل النشر
# 2) النشر (pull + migrate + seed + collectstatic + restart + healthcheck)
sudo bash scripts/update.sh
# 3) التحقق
docker compose exec -T web python manage.py migrate --check
docker compose exec -T web python manage.py check
docker compose exec -T web python manage.py showmigrations payments teacher_portal courses | grep "\[ \]"   # يجب أن يكون فارغاً
docker compose ps
docker compose logs web --tail=150     # لا 500، لا "no such column"
# 4) cron التذكيرات (للجلسات المباشرة)
# */5 * * * * cd /opt/onlenco && docker compose exec -T web python manage.py send_live_session_reminders
```
بعد النشر: Hard refresh (Ctrl+Shift+R) وتأكّد من ظهور `p166d-student-detail-ux-20260604` في مصدر صفحة الأدمن. ثم أعِد فحص `/admin/students/<id>/` بصرياً.

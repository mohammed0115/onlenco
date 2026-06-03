# تقرير البرومبت 2 — الجدولة التلقائية وجلسات Google Meet

**التاريخ:** 2026-06-03
**النطاق:** البرومبت الثاني من خريطة Marketplace

---

## 1. الملخص التنفيذي

أُضيف نظام **الحصص المباشرة (Live Sessions)** بالكامل فوق بوابة المعلم دون كسر أي سلوك:
- المعلم يجدول حصصاً مباشرة لكورساته، بحدّ **لقاءين لكل كورس أسبوعياً**.
- يُولَّد رابط **Google Meet تلقائياً** (خدمة مرنة: حقيقية عند توفّر المفاتيح، وإلا Mock واقعي).
- عند الجدولة، تُرسَل إشعارات (بريد + داخلي) لكل طلاب الكورس النشطين بالعربية والإنجليزية.
- أمر إداري يذكّر الطلاب **قبل 30 دقيقة** من بدء الحصة (مرة واحدة فقط).
- **203 اختبار خضراء** (teacher_portal + notifications + payments)، منها 12 جديدة، و`check` نظيف.

---

## 2. الموديل والهجرة

`teacher_portal.LiveSession` (هجرة `0003`):
| الحقل | النوع | ملاحظات |
|---|---|---|
| `teacher` | FK User | related_name="live_sessions" |
| `course` | FK Course | related_name="live_sessions" |
| `title` / `description` | Char / Text | — |
| `scheduled_at` | DateTime | يجب أن يكون مستقبلاً |
| `duration_minutes` | PositiveInteger | افتراضي 60 |
| `meet_link` | URLField | يُملأ تلقائياً عند الإنشاء |
| `status` | Char | scheduled / completed / cancelled |
| `reminder_sent_at` | DateTime null | يضمن إرسال التذكير مرة واحدة |

دوال: `weekly_count(teacher, course, when)` (نطاق أسبوع ISO صحيح من الاثنين للأحد، يستثني الملغاة)، و`ends_at`.

---

## 3. خدمة Google Meet (مرنة)

`teacher_portal/services/meet_service.py` — `generate_meet_link(title, start, duration_minutes)`:
- إن كان `GOOGLE_MEET_ENABLED=1` ومفاتيح Calendar متوفرة → ينشئ حدث Calendar برابط Meet حقيقي عبر `google-api-python-client`.
- خلاف ذلك (تطوير، بلا مفاتيح، المكتبة غير مثبّتة، أو أي خطأ) → **Mock واقعي** بصيغة `https://meet.google.com/abc-defg-hij` فريد لكل جلسة.
- **لا يفشل أبداً** — أي خطأ في المسار الحقيقي يسقط على الـ Mock.

إعدادات بيئة جديدة (فارغة افتراضياً): `GOOGLE_MEET_ENABLED`, `GOOGLE_MEET_CREDENTIALS_FILE`, `GOOGLE_MEET_CALENDAR_ID`.

---

## 4. الواجهة والقيد الأسبوعي

- مسارات: `‎/teacher/live-sessions/‎` (قائمة) · `‎/create/‎` (جدولة) · `‎/<id>/cancel/‎` (إلغاء).
- `LiveSessionForm`: خيارات الكورس **مقيّدة بكورسات المعلم**؛ يرفض الموعد الماضي؛ يرفض اللقاء الثالث في نفس الأسبوع لنفس الكورس برسالة ثنائية اللغة.
- عنصر تنقّل جديد **«الحصص المباشرة»** في الشريط الجانبي.
- القوالب على نمط بوابة المعلم (جداول داخل بطاقات، RTL، ثنائية اللغة).

---

## 5. الإشعارات

نوعان جديدان في `notifications`: `LIVE_SESSION_SCHEDULED` و`LIVE_SESSION_REMINDER` — مسجّلان في القوائم والعناوين (عربي/إنجليزي) وقالبَي إيميل جذّابين يرثان `base_email.html`.

`live_session_service.notify_students_scheduled(session)` يرسل لكل طلاب الكورس النشطين عند الجدولة (best-effort، لا يوقف الحفظ).

---

## 6. التذكير قبل 30 دقيقة

- `live_session_service.send_reminders()` يجد الحصص المجدولة التي تبدأ خلال 30 دقيقة ولم تُذكَّر، يُشعِر طلابها، ويضبط `reminder_sent_at` (**Idempotent**).
- أمر إداري: `python manage.py send_live_session_reminders` — يُشغَّل من المجدول كل ~5 دقائق.

**للنشر:** أضف إلى الـ cron على الإنتاج:
```
*/5 * * * * cd /opt/onlenco && docker compose exec -T web python manage.py send_live_session_reminders
```

---

## 7. الاختبارات (12 جديدة)

| المجموعة | يغطّي |
|---|---|
| `MeetServiceTests` | صيغة رابط Mock · تفرّد الروابط |
| `WeeklyLimitTests` | رفض الثالث/الأسبوع · الملغاة لا تُحسب · رفض الماضي · تقييد الكورسات بالمعلم |
| `ScheduleViewTests` | توليد الرابط + إشعار الطلاب · عرض القائمة · الإلغاء |
| `ReminderTests` | إرسال + Idempotent · تجاهل البعيد · الأمر الإداري |

**203 اختبار خضراء** بلا انحدار، `check` نظيف.

---

## 8. القيود المحترمة

✅ توافق رجعي كامل. ✅ بلا توليد وسائط. ✅ بلا مساس بـ ai_usage. ✅ الإشعارات best-effort لا توقف الجدولة. ✅ كل البيانات والصلاحيات محفوظة.

---

## 9. ملاحظات النشر

- هجرة جديدة: `teacher_portal/0003_livesession` — آمنة (إنشاء جدول جديد). `update.sh` ينفّذها.
- لتفعيل Meet الحقيقي لاحقاً: ثبّت `google-api-python-client` + `google-auth`، واضبط متغيرات البيئة الثلاثة.
- لتفعيل التذكيرات: أضف cron job أعلاه.

## 10. المتبقي من الخريطة
البرومبت 3 (لوحة المعلم والمجموعات) · 4 (المهارات الأربع والرقابة) · 5 (AI Tutor السياقي + الشهادات).

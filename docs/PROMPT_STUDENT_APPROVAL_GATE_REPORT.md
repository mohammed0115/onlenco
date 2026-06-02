# تقرير Student Approval Gate / Anti-Bot Protection

## 1. الملخص التنفيذي

* **ماذا تم بناؤه؟** بوابة موافقة على تسجيل الطلاب: لا يصل الطالب الجديد إلى لوحة
  التحكم أو الدورات أو الدروس أو التحديات أو المعلّم الذكي أو الاختبار التحديدي أو
  المكتبة أو واجهات الطالب البرمجية حتى يوافق عليه الأدمن — مع حماية anti-bot وسجلّ
  تدقيق كامل.
* **هل الطالب الجديد ممنوع من dashboard قبل موافقة الإدارة؟** نعم. التسجيل يؤدي إلى
  «بانتظار الموافقة» وليس لوحة التحكم؛ middleware يعيد توجيه HTML إلى صفحة الانتظار،
  ويُرجع 403 JSON لواجهات API.
* **هل تم حماية AI Tutor من الحسابات غير المعتمدة؟** نعم. كل مكالمات الطالب تمرّ
  عبر `ai_client` الذي يرفض الطالب غير المعتمد **قبل** أي اتصال بالمزوّد وبلا استهلاك
  أي دقائق، ويسجّل محاولة «cancelled» بتكلفة 0.

## 2. الملفات المعدلة أو المنشأة

| الملف | التعديل | السبب |
|---|---|---|
| `accounts/models.py` | تعديل | حقول الموافقة على `Profile` + نموذج `StudentApprovalEvent` |
| `accounts/migrations/0008_*`, `0009_initialize_approval_status` | إنشاء | الـ schema + تهيئة المستخدمين الحاليين بأمان |
| `accounts/approval.py` | إنشاء | انتقالات الحالة + كتابة سجلّ التدقيق |
| `accounts/middleware.py` | تعديل | `StudentApprovalRequiredMiddleware` |
| `accounts/forms.py` | تعديل | honeypot آمن + حجب البريد المؤقت |
| `accounts/views.py` | تعديل | تسجيل الموافقة + إشارات anti-bot + صفحة الانتظار + التوجيه |
| `accounts/onboarding.py` | تعديل | توجيه الطالب المعلّق قبل onboarding |
| `accounts/templates/accounts/pending_approval.html` | إنشاء | صفحة الانتظار (عربي/إنجليزي) |
| `accounts/management/commands/initialize_student_approval_status.py` | إنشاء | أمر ترحيل المستخدمين الحاليين |
| `accounts/admin.py` | تعديل | تسجيل `StudentApprovalEvent` + حقل الحالة |
| `templates/accounts/auth.html` | تعديل | حقل honeypot مخفي |
| `platform_admin/views_student_approval.py` + `urls.py` + `templates/.../approvals.html` | إنشاء | لوحة موافقات الأدمن |
| `ai_usage/services/ai_client.py` | تعديل | بوابة الموافقة لمكالمات الطالب |
| `config/settings/base.py` | تعديل | تسجيل الـ middleware + إعدادات anti-bot |
| `config/settings/test.py` | تعديل | تعطيل البوابة افتراضيًا في الاختبارات |
| `accounts/tests/test_student_approval.py`, `ai_usage/tests/test_approval_gate.py` | إنشاء | الاختبارات |
| `docs/STUDENT_APPROVAL_GATE.md` | إنشاء | التوثيق |

## 3. Registration Flow

```
register → email OTP verification → pending_admin_approval (صفحة الانتظار) → موافقة الأدمن → dashboard
```

* عند التسجيل: يُنشأ الطالب `pending_email_verification`، وتُسجَّل IP/User-Agent
  وإشارات anti-bot، وتُكتب حادثة `registered`. لا يُوجَّه للوحة التحكم أبدًا.
* بعد تأكيد البريد: تنتقل الحالة إلى `pending_admin_approval` (حادثة `email_verified`).
* رسالة ودّية ثنائية اللغة (عربي/إنجليزي) على صفحة الانتظار، دون كشف تفاصيل anti-bot.
* الموظّفون/المعلّمون/الأدمن مُعتمدون تلقائيًا ومستثنون من البوابة.

## 4. Approval Status

| الحالة | المعنى | الوصول |
|---|---|---|
| `pending_email_verification` | لم يؤكّد البريد | محجوب → صفحة التأكيد |
| `pending_admin_approval` | بانتظار الأدمن | محجوب → صفحة الانتظار |
| `approved` | معتمد | وصول كامل |
| `rejected` | مرفوض (ملاحظة إلزامية) | محجوب |
| `suspended` | موقوف (ملاحظة إلزامية) | محجوب |

`is_active` و`email_verified` منفصلان ولم يُمسّا — الموافقة محور مستقل.

## 5. Access Guard

`StudentApprovalRequiredMiddleware` (مفعّل بعلم `ONLENCO_STUDENT_APPROVAL_REQUIRED`،
True في الإنتاج):

* HTML → 302 إلى `/account/pending-approval/`.
* API/JSON → `403 {"code":"account_pending_approval", ...}`.
* مسموح أثناء الانتظار: تسجيل الدخول/الخروج، تأكيد البريد، إعادة تعيين/تغيير كلمة
  المرور، صفحة الانتظار، تبديل اللغة، الملفات الثابتة.
* محجوب: dashboard، courses، lessons، challenge، AI Tutor، onboarding/placement،
  library، واجهات الطالب البرمجية.

## 6. Admin Approval Dashboard

`/control/student-approvals/` (و`/admin/student-approvals/`)، بصلاحية
`students.view` للعرض و`students.manage` للإجراءات:

* قائمة الطلاب المعلّقين: الاسم، البريد، تاريخ التسجيل، تأكيد البريد، IP،
  User-Agent، الإشارات المشبوهة، الحالة.
* إجراءات: approve / reject (ملاحظة) / suspend (ملاحظة) / note / **bulk approve/reject**.
* كل إجراء يكتب `StudentApprovalEvent`. لا يُحذف أي مستخدم.

## 7. Anti-Bot Protection

* **Rate limit:** تسجيل/دخول (django-axes)/إعادة تعيين كلمة المرور — لكل IP.
  `ONLENCO_REGISTRATION_RATE_LIMIT_PER_HOUR` (افتراضي 10).
* **Honeypot:** حقل مخفي `ol_contact_url` (تجنّبنا `website` التي يملؤها الـ autofill —
  سبب إزالة honeypot القديم). إن مُلئ → خطأ عام بلا إنشاء حساب.
* **CAPTCHA readiness:** `ONLENCO_REGISTRATION_CAPTCHA_ENABLED` (False) +
  `ONLENCO_CAPTCHA_PROVIDER`؛ hCaptcha مدعوم ويتخطّى تلقائيًا عند غياب المفاتيح.
* **Disposable emails:** `ONLENCO_BLOCK_DISPOSABLE_EMAILS` (False) + قائمة نطاقات.
* **Suspicious flags:** `suspicious_user_agent`، `disposable_email`، `repeated_ip`،
  `honeypot_filled`… تُسجَّل على الملف وتظهر في الطابور، ولا تُعتمد تلقائيًا.

## 8. AI Protection

`_enforce_student_approval` في `ai_client` على بداية `chat`/`stream_chat`/
`transcribe_audio`/`synthesize_speech`:

* يرفع `AccountPendingApproval` **قبل** أي اتصال بالمزوّد.
* لا يستهلك أي دقائق AI Tutor.
* يسجّل `AIUsageLog` بحالة `cancelled` وتكلفة 0 و`blocked_reason=account_pending_approval`.
* لا يُحجب المعلّم/الأدمن/النظام.

## 9. Existing Users Migration

migration `0009` + الأمر `initialize_student_approval_status`:

```
python manage.py initialize_student_approval_status --dry-run
python manage.py initialize_student_approval_status --confirm
```

* مُوظّف/أدمن/معلّم → `approved` (مستثنى).
* طالب مؤكَّد البريد → `approved`.
* غير مؤكَّد → `pending_email_verification`.
* لا يقلب أبدًا حسابًا `rejected`/`suspended` يدويًا.
* تشغيل تجريبي على dev: approved=19، pending=4، privileged_exempt=9.

## 10. Tests

| المجموعة | النتيجة |
|---|---|
| خدمة الموافقة (record/verify/approve/reject/suspend/staff-exempt) | OK |
| Access guard (dashboard redirect, API 403, admin/teacher غير محجوبين, صفحة الانتظار) | OK |
| Registration (pending وليس dashboard, honeypot يحجب البوت, disposable, flags) | OK |
| Approval dashboard (عرض/approve/reject+ملاحظة/audit/صلاحيات) | OK |
| Migration command (dry-run/confirm/verified→approved/staff exempt) | OK |
| AI protection (pending لا يبدأ AI/challenge/STT, لا مزوّد, لا تكلفة, approved يمر) | OK |
| Regression (login/logout/onboarding journeys/teacher dual-role) | OK |
| الإجمالي للميزة | 33 اختبارًا، OK |

## 11. Commands Run

```
python manage.py makemigrations accounts        # 0008 schema
python manage.py migrate accounts                # 0008 + 0009 (init)
python manage.py initialize_student_approval_status --dry-run | --confirm
DJANGO_SETTINGS_MODULE=config.settings.test python manage.py test accounts ai_usage tutor courses teacher_portal
DJANGO_SETTINGS_MODULE=config.settings.test python manage.py check   → no issues
```
> ملاحظة أسماء التطبيقات: لا يوجد تطبيق `users` ولا `student_portal`؛ لوحة الطالب
> في تطبيق `lessons`. الأوامر الفعلية تستخدم: accounts / ai_usage / tutor / courses / teacher_portal.

## 12. Remaining Issues

* **P0:** لا يوجد.
* **P1:** لا يوجد.
* **P2:** البريد (OTP) يُرسَل off-thread وSMTP غير متاح على dev (سلوك معروف) — لا يؤثر
  على البوابة لكن قد يبطئ تأكيد البريد فعليًا؛ يُنصح بمزوّد SMTP موثوق في الإنتاج.
* **P3:** تفعيل CAPTCHA/حجب البريد المؤقت اختياري (جاهز ومعطّل افتراضيًا)؛ يمكن لاحقًا
  إضافة إشعار للأدمن عند تراكم طلبات الموافقة.

## 13. Final Decision

**Ready for production** — مع إبقاء `ONLENCO_STUDENT_APPROVAL_REQUIRED=True` (الافتراضي).
البوابة تمنع الحسابات غير المعتمدة من لوحة التحكم وAI، توجد لوحة موافقة مع سجلّ تدقيق،
المستخدمون الحاليون لم يُحجبوا، والموظّفون/المعلّمون مستثنون، والاختبارات خضراء و`check`
نظيف. (يُنصح بتشغيل `initialize_student_approval_status --confirm` بعد النشر للتأكيد.)

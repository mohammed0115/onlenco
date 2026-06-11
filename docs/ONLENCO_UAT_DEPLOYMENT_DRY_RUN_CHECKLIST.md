# Onlenco — UAT Deployment Dry-Run Checklist
# قائمة التحقّق التجريبية لنشر UAT — Onlenco

_آخر تحديث: مرحلة 18.4F._ مرجع:
[Final UAT Readiness](ONLENCO_UAT_READINESS_FINAL.md) ·
[Media Sync](ONLENCO_PRODUCTION_MEDIA_SYNC_RUNBOOK.md) ·
[Deployment Readiness](ONLENCO_DEPLOYMENT_READINESS_RUNBOOK.md) ·
[Browser/Mobile QA](ONLENCO_BROWSER_MOBILE_MANUAL_QA_RUNBOOK.md).

> **هذه خطوة وسيطة** بين جاهزية UAT والنشر الفعلي للإنتاج. الغرض: **مراجعة
> وتجربة** خطوات النشر بأمان (dry-run) **دون تنفيذ على الإنتاج**، لاكتشاف الفجوات
> قبل الالتزام بنشر حقيقي.

---

## 1. Purpose / الغرض
التحقّق التجريبي من سلسلة النشر كاملة (كود، migrations، static، media، env، صحّة،
smoke، rollback) **بلا أثر على الإنتاج**، وإصدار قرار Go/No-Go موثّق قبل أي نشر فعلي.

## 2. Scope / النطاق
- **داخل النطاق:** مراجعة الأوامر، تجربتها على staging/UAT إن وُجدت، `rsync --dry-run`
  للوسائط، التحقّق من env/secrets (أسماء فقط)، جدولة QA المتصفّح/الصوت، نموذج القرار.
- **خارج النطاق:** أي تنفيذ على الإنتاج، SSH للإنتاج، نسخ media فعلي، تعديل DB الإنتاج،
  استدعاء OpenAI حقيقي.

## 3. Assumptions / الافتراضات
- الفرع المُراد: `feat/beginner-media-and-tutor-usage` (آخر commit موثّق).
- الاختبارات خضراء: check نظيف، tutor 261، daily_learning 130، courses 729.
- audit الوسائط نظيف: 192 صورة + 288 صوت، 0 مفقود/مكرّر/noncanonical.
- التخزين filesystem (`media_data:/app/media`)، DB إنتاج Postgres، Redis/Celery، صحّة `/healthz/`.
- **لا migrations جديدة** في مراحل الـsmoke الأخيرة.

## 4. Pre-dry-run requirements / متطلّبات ما قبل التجربة
- [ ] بيئة staging/UAT متاحة (أو الإقرار بغيابها كـrisk).
- [ ] صلاحيات مشغّل مخوّل (بلا مشاركة أسرار في القنوات).
- [ ] نسخة من `.env` للإنتاج جاهزة ومراجَعة (بلا قيم في git).
- [ ] مالك backup ومالك rollback معيّنان.

## 5. Dry-run environment checklist / بيئة التجربة
- [ ] `DJANGO_SETTINGS_MODULE=config.settings.production` (في staging/dry-run).
- [ ] `DEBUG=False`.
- [ ] `ALLOWED_HOSTS` و`CSRF_TRUSTED_ORIGINS` يطابقان دومين staging.
- [ ] Postgres + Redis متاحان في بيئة التجربة.

## 6. Code deploy dry-run / تجربة نشر الكود
- [ ] مراجعة `git log`/diff للفرع المُراد (بلا مفاجآت).
- [ ] `docker build -t onlenco-web:latest .` ينجح (أو سحب صورة جاهزة).
- [ ] **مراجعة** أوامر `docker compose -f docker-compose.prod.yml ...` دون تشغيل على الإنتاج.

## 7. Database migration dry-run / تجربة الترحيل
- [ ] `python manage.py makemigrations --check --dry-run` ⇒ **لا migrations معلّقة**.
- [ ] `migrate --plan` يُراجَع (يُتوقّع لا migrations جديدة من 18.3/18.4).
- [ ] لا تنفيذ migrate على DB الإنتاج في هذه المرحلة.

## 8. Static files dry-run / الأصول الثابتة
- [ ] `collectstatic --dry-run --noinput` يُراجَع.
- [ ] `STATIC_ROOT=staticfiles`، `DJANGO_STATIC_URL` صحيح.

## 9. Media sync dry-run / تجربة مزامنة الوسائط
- [ ] manifest جاهز (480 ملفًا معتمَدًا، 0 مفقود، ~284 MB).
- [ ] **`rsync --dry-run`** يُراجَع قبل أي نسخ فعلي:
```
rsync -av --dry-run \
  --exclude 'db.sqlite3' --exclude 'test_db.sqlite3' --exclude 'tmp' \
  media/ user@server:/path/to/onlenco/media/
```
- [ ] **لا `--delete` في أول مزامنة**.
- [ ] لا نسخ `db.sqlite3`/`test_db.sqlite3`/`tmp`/`staticfiles`.
- [ ] خطة التحقّق من العدّ والملكية بعد المزامنة جاهزة (انظر Media Sync Runbook).

## 10. Environment variables checklist / متغيّرات البيئة (أسماء فقط)
- [ ] `DJANGO_SECRET_KEY`, `DJANGO_DEBUG=False`, `DJANGO_ALLOWED_HOSTS`, `DJANGO_CSRF_TRUSTED_ORIGINS`.
- [ ] `POSTGRES_*`, `DJANGO_DB_SSL_REQUIRE`.
- [ ] `DJANGO_SECURE_SSL_REDIRECT`, `DJANGO_SECURE_HSTS_*`.
- [ ] `EMAIL_*`, `DEFAULT_FROM_EMAIL`, `ONLENCO_BASE_URL`.
- [ ] `CELERY_BROKER_URL`, `CELERY_RESULT_BACKEND`.
- [ ] `DJANGO_STATIC_URL`, `DJANGO_MEDIA_URL`.
- [ ] `AI_API_KEY`, `AI_API_BASE`, `AI_MODEL` (في **بيئة آمنة**).

## 11. AI Tutor safe runtime checklist / تشغيل المساعد بأمان
- [ ] مفاتيح AI موجودة في بيئة آمنة (بلا تسريب في git/لوجات).
- [ ] HTTPS فعّال (المايك يتطلّب secure context).
- [ ] اختبار رسالة صوتية واحدة + مكالمة واحدة في بيئة آمنة (لا حمل إنتاج).
- [ ] تأكيد **خصم الدقائق الصحيح + لا double-bill + فصل placement** (مراقبة).

## 12. Browser / mobile manual QA references / مراجع QA اليدوي
- [ ] تنفيذ [Browser/Mobile Manual QA Runbook](ONLENCO_BROWSER_MOBILE_MANUAL_QA_RUNBOOK.md)
      على Chrome + Safari iPhone + Android Chrome + عرض ~360px.
- [ ] RTL/عربي سليم، أهداف لمس، لا نص قالب خام.

## 13. Smoke test checklist / اختبار الدخان
- [ ] طالب: login → dashboard → beginner course → lesson media → progress → Daily → Weekly → AI نص.
- [ ] إدارة: admin، وسائط معتمَدة مرئية، **لا وسائط معلّقة للطالب**، سجلّات AI، تقدّم.
- [ ] نظام: `/healthz/`=200، لا 500، static/media يُحمّلان، لا صور/أصوات مكسورة.

## 14. Rollback dry-run / تجربة التراجع
- [ ] مراجعة أوامر استرجاع media (tar من النسخة) و DB (psql من dump).
- [ ] مالك rollback ومدّة التراجع المتوقّعة موثّقان.
- [ ] العودة للـrelease السابق `git checkout <prev>` + `compose up -d` مُجرَّبة ذهنيًا.

---

## 15. Go/No-Go Decision Form / نموذج القرار
| البند | الحالة |
|---|---|
| Code ready? | ☐ نعم ☐ لا |
| DB migration plan reviewed? | ☐ نعم ☐ لا |
| Media manifest ready? | ☐ نعم ☐ لا |
| Media sync dry-run passed? | ☐ نعم ☐ لا |
| Static files ready? | ☐ نعم ☐ لا |
| Env vars confirmed? | ☐ نعم ☐ لا |
| AI keys present in safe env? | ☐ نعم ☐ لا |
| Browser/mobile QA scheduled? | ☐ نعم ☐ لا |
| Voice QA scheduled? | ☐ نعم ☐ لا |
| Backup owner assigned? | ☐ نعم ☐ لا |
| Rollback owner assigned? | ☐ نعم ☐ لا |
| **Final decision** | ☐ **GO** ☐ **HOLD** |

## 16. Required approvals before real deployment / الموافقات المطلوبة
- [ ] **Product** sign-off: ________________  التاريخ: ______
- [ ] **Tech** sign-off: ________________  التاريخ: ______
- [ ] **QA** sign-off: ________________  التاريخ: ______

> لا نشر فعلي إلا بعد **GO** + توقيع الثلاثة + إتمام backups.

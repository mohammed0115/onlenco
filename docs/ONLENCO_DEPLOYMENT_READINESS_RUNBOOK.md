# Onlenco — Deployment Readiness Runbook
# دليل جاهزية النشر — Onlenco

_آخر تحديث: مرحلة 18.4E._ مرجع:
[Final UAT Readiness](ONLENCO_UAT_READINESS_FINAL.md) ·
[Media Sync](ONLENCO_PRODUCTION_MEDIA_SYNC_RUNBOOK.md) ·
[Browser/Mobile QA](ONLENCO_BROWSER_MOBILE_MANUAL_QA_RUNBOOK.md).

> دليل نشر يدوي خطوة بخطوة. **لا أسرار/مفاتيح حقيقية هنا.** ينفّذه مشغّل مخوّل في
> بيئة الإنتاج. هذه المرحلة **لا تنشر** — توثيق فقط.

---

## حقائق البنية (مؤكَّدة من الكود)
- إعدادات الإنتاج: `config.settings.production` (`DEBUG=False`، `ALLOWED_HOSTS`
  إلزامي، Postgres بـSSL، secure cookies، `SECURE_SSL_REDIRECT`, HSTS).
- Compose: `web` (replicas=3) + `worker` (Celery) + `cron` + `db` (Postgres 16) +
  `redis`. الوسائط على حجم `media_data:/app/media`؛ `postgres_data` للـDB.
- Health endpoint: **`/healthz/`** (مُعفى من SSL redirect).
- الأصول الثابتة: `STATIC_ROOT=staticfiles` عبر `collectstatic`.

---

## 1. Pre-deployment checklist
- [ ] الاختبارات خضراء محليًا: check، tutor 261، daily_learning 130، courses 729.
- [ ] audit الوسائط نظيف (192/192 صور، 288 صوت، 0 missing).
- [ ] الفرع/الـtag المراد نشره محدّد ومراجَع (PR merged).
- [ ] متغيّرات البيئة مهيّأة (القسم التالي).
- [ ] نسخ احتياطية حديثة (DB + media).
- [ ] نافذة صيانة/إشعار مستخدمين عند الحاجة.

## 2. Environment variables checklist (أسماء فقط — بلا قيم)
من `.env.example`:
- جوهر Django: `DJANGO_SETTINGS_MODULE`(=config.settings.production)، `DJANGO_SECRET_KEY`، `DJANGO_DEBUG`(=False)، `DJANGO_ALLOWED_HOSTS`، `DJANGO_CSRF_TRUSTED_ORIGINS`، `DJANGO_LOG_LEVEL`.
- قاعدة البيانات: `POSTGRES_DB`، `POSTGRES_USER`، `POSTGRES_PASSWORD`، `POSTGRES_HOST`، `POSTGRES_PORT`، `DJANGO_DB_CONN_MAX_AGE`، `DJANGO_DB_SSL_REQUIRE`.
- الأمان/HTTPS: `DJANGO_SECURE_SSL_REDIRECT`، `DJANGO_SECURE_HSTS_SECONDS`، `DJANGO_SECURE_HSTS_INCLUDE_SUBDOMAINS`، `DJANGO_SECURE_HSTS_PRELOAD`، `API_TOKEN_MAX_AGE_DAYS`.
- البريد: `EMAIL_BACKEND`، `EMAIL_HOST`، `EMAIL_PORT`، `EMAIL_HOST_USER`، `EMAIL_HOST_PASSWORD`، `EMAIL_USE_TLS`، `DEFAULT_FROM_EMAIL`، `EMAIL_BRAND_NAME`، `EMAIL_REPLY_TO`.
- المهام: `CELERY_BROKER_URL`، `CELERY_RESULT_BACKEND`.
- الأصول/الوسائط: `DJANGO_STATIC_URL`، `DJANGO_MEDIA_URL`.
- الذكاء الاصطناعي: `AI_API_KEY`، `AI_API_BASE`، `AI_MODEL`، `ONLENCO_BASE_URL`.

> تحقّق: `DEBUG=False`، `ALLOWED_HOSTS` غير فارغ، `CSRF_TRUSTED_ORIGINS` يطابق الدومين،
> مفاتيح AI صالحة، بريد إنتاج فعّال.

## 3. Backup steps
```
# DB
docker compose -f docker-compose.prod.yml exec db \
  pg_dump -U "$POSTGRES_USER" "$POSTGRES_DB" > db_backup_$(date +%F).sql
# Media (انظر Media Sync Runbook §1)
docker run --rm -v onlenco_media_data:/data -v "$PWD":/backup alpine \
  tar czf /backup/media_backup_$(date +%F).tgz -C /data .
```

## 4. Code deploy steps
```
git fetch --all && git checkout <release-tag-or-sha>
docker build -t onlenco-web:latest .
# أو سحب صورة مبنية من السجلّ
docker compose -f docker-compose.prod.yml pull
```

## 5. Migration steps
```
docker compose -f docker-compose.prod.yml run --rm web \
  python manage.py migrate --noinput
```
> ملاحظة: مراحل الـsmoke الأخيرة **بلا migrations جديدة**؛ migrate يطبّق ما هو موجود.

## 6. collectstatic
```
docker compose -f docker-compose.prod.yml run --rm web \
  python manage.py collectstatic --noinput
```

## 7. media sync
- نفّذ [Media Sync Runbook](ONLENCO_PRODUCTION_MEDIA_SYNC_RUNBOOK.md) بالكامل
  (backup → sync → verify counts → permissions → audit).

## 8. service restart
```
docker compose -f docker-compose.prod.yml up -d
docker compose -f docker-compose.prod.yml --profile worker up -d worker
```

## 9. health checks
```
curl -fsS https://<domain>/healthz/        # 200
docker compose -f docker-compose.prod.yml ps   # كل الخدمات up
```

## 10. smoke tests
- نفّذ "Production Smoke Test Checklist" أدناه + رحلة المتصفّح اليدوية.

## 11. rollback steps
```
git checkout <previous-release> && docker compose -f docker-compose.prod.yml up -d
# DB/media rollback: انظر Media Sync Runbook §11
```

## 12. post-deploy monitoring
- راقب اللوجات: لا أخطاء 500، لا استثناءات متكرّرة.
- راقب `/healthz/` والخدمات (web×3، worker، cron، db، redis).
- **راقب خصم دقائق AI Tutor** (صوت/مكالمة) — لا double-bill، لا تسرّب free-trial.
- راقب أزمنة الاستجابة وأخطاء الطرف الأمامي.

---

## Production Smoke Test Checklist (بعد النشر)

### الطالب
- [ ] login.
- [ ] dashboard.
- [ ] beginner course.
- [ ] lesson media: صورة + صوت يعملان.
- [ ] lesson complete / progress يُسجَّل.
- [ ] Daily Quiz: إجابة صحيحة/خاطئة + درجة.
- [ ] Weekly card بعد 3 دروس.
- [ ] AI Tutor نصّي يردّ.
- [ ] AI Tutor رسالة صوتية (بيئة آمنة).
- [ ] AI Tutor مكالمة (بيئة آمنة).

### الإدارة
- [ ] admin login.
- [ ] الوسائط المعتمَدة مرئية.
- [ ] **لا وسائط معلّقة/فاشلة تظهر للطالب.**
- [ ] سجلّات استخدام AI مرئية.
- [ ] تقدّم الطالب مرئي.

### النظام
- [ ] `/healthz/` = 200.
- [ ] اللوجات بلا 500.
- [ ] static يُحمّل.
- [ ] media يُحمّل.
- [ ] لا صور مكسورة.
- [ ] لا أصوات مكسورة.

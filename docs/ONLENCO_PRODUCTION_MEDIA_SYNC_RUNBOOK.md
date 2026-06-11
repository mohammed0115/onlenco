# Onlenco — Production Media Sync Runbook
# دليل مزامنة وسائط الإنتاج — Onlenco

_آخر تحديث: مرحلة 18.4E._ مرجع:
[Final UAT Readiness](ONLENCO_UAT_READINESS_FINAL.md) ·
[Deployment Readiness](ONLENCO_DEPLOYMENT_READINESS_RUNBOOK.md).

> دليل **تشغيل يدوي للنقل الآمن** لوسائط كورس المبتدئين المعتمَدة من البيئة المحلية
> إلى تخزين الإنتاج. **لا تنفيذ هنا** — أوامر نموذجية فقط. نفّذها مشغّل مخوّل بعد
> أخذ النسخ الاحتياطية.

---

## 0. حقائق البنية (مؤكَّدة من الكود)
- التخزين: **نظام ملفات** — `MEDIA_ROOT = BASE_DIR/media`، `MEDIA_URL=/media/`.
  **لا object storage** (`STORAGES`/`DEFAULT_FILE_STORAGE` غير مُعرَّف).
- الإنتاج (Docker): مجلّد محمول مُسمّى **`media_data` مربوط على `/app/media`**،
  مُشترَك بين خدمتَي `web` و`cron` (انظر `docker-compose.yml`).
- الـentrypoint يبدأ كـroot ليضبط ملكية مجلّد media ثم يُسقط الصلاحية لمستخدم `onlenco`.
- قاعدة بيانات الإنتاج **Postgres** (المحلي/الاختبار sqlite) — صفوف `LessonImagePrompt`/
  `LessonAudioScript` تحمل **مسارات نسبية** للملفات + `generation_status`.

> **حرج:** الملفات وحدها لا تكفي — صفوف قاعدة بيانات الإنتاج يجب أن تشير لنفس
> المسارات النسبية وبحالة `approved`. زامِن الملفات **و** تأكّد من تطابق صفوف DB
> (عبر تشغيل seeds الإنتاج أو استرجاع DB)، وإلا ستظهر صور/أصوات مكسورة.

## 1. جرد المصدر (محلي، معتمَد ومرئي للطالب)
| النوع | العدد | الحجم التقريبي |
|---|---|---|
| Covers | 48 | ~73 MB |
| Illustrations | 144 | ~180 MB |
| Audio | 288 | ~31 MB |
| **الإجمالي** | **480 ملفًا** | **~284 MB** |

مفقود: **0**. (مصدر: audit + manifest read-only في `tmp/beginner_media_manifest.json`.)
الوسائط **غير المعتمَدة/غير المرئية للطالب لا تدخل** في المزامنة.

---

## خطوات المزامنة (نفّذها مشغّل مخوّل)

### 1) Backup current production media
```
# داخل خادم/مضيف الإنتاج — انسخ الحجم الحالي قبل أي تغيير
docker run --rm -v onlenco_media_data:/data -v "$PWD":/backup alpine \
  tar czf /backup/media_backup_$(date +%F).tgz -C /data .
```

### 2) Backup production database
```
# Postgres dump (عدّل الأسماء حسب env)
docker compose -f docker-compose.prod.yml exec db \
  pg_dump -U "$POSTGRES_USER" "$POSTGRES_DB" > db_backup_$(date +%F).sql
```

### 3) Identify local approved media source
- المصدر: `media/` المحلي (480 ملفًا معتمَدًا، 0 مفقود).
- تأكيد قبل النقل:
```
python manage.py audit_beginner_media --course-slug onlenco-beginner --format text
```

### 4) Build media manifest (read-only)
- استخدم الـmanifest المُولَّد في `tmp/beginner_media_manifest.json` (مسارات نسبية + أحجام + exists).
- تحقّق محلي من الإجمالي:
```
find media -type f \( -name '*.png' -o -name '*.jpg' -o -name '*.jpeg' -o -name '*.mp3' \) | wc -l
du -sh media
```

### 5) Copy/sync media safely
```
# جرّب أولًا بلا كتابة:
rsync -av --dry-run \
  --exclude 'db.sqlite3' --exclude 'test_db.sqlite3' --exclude 'tmp' \
  media/ user@server:/path/to/onlenco/media/

# بعد مراجعة قائمة --dry-run:
rsync -av \
  --exclude 'db.sqlite3' --exclude 'test_db.sqlite3' --exclude 'tmp' \
  media/ user@server:/path/to/onlenco/media/
```
**تحذيرات:**
- استخدم `--dry-run` أولًا دائمًا.
- **لا تستخدم `--delete` في أول مزامنة** إلا بعد backup ومراجعة كاملة.
- لا تنسخ `db.sqlite3` / `test_db.sqlite3` / `tmp/` / `staticfiles/`.
- إن كان التخزين داخل Docker volume، انسخ إلى مسار المضيف المربوط أو استخدم:
  `docker cp ./media/. <web_container>:/app/media/`.

### 6) Verify file counts after sync
```
# على الإنتاج
find /path/to/onlenco/media -type f | wc -l       # يطابق المحلي
docker compose exec web sh -c 'find /app/media -type f | wc -l'
```

### 7) Verify permissions / ownership
```
# يجب أن يملك مستخدم التطبيق (onlenco / www-data) القراءة
docker compose exec web sh -c 'ls -la /app/media | head; id'
docker compose exec web sh -c 'chown -R onlenco:onlenco /app/media'   # عند الحاجة
```
راجع mapping الـvolume في `docker-compose.prod.yml` (`media_data:/app/media`).

### 8) Verify MEDIA_URL serving
- افتح عيّنة URL `/media/<rel_path>` عبر المتصفّح → 200 وصورة/صوت صحيح.
- تأكّد أن الخادم الأمامي (nginx/الـapp) يخدم `/media/` ويملك صلاحية القراءة.

### 9) Run media audit after sync
```
docker compose exec web python manage.py audit_beginner_media \
  --course-slug onlenco-beginner --format text
# مطلوب: 192/192 صور، 288 صوت، 0 missing/duplicate/noncanonical
```

### 10) Browser smoke after sync
- نفّذ رحلة الطالب من [Browser/Mobile Manual QA Runbook](ONLENCO_BROWSER_MOBILE_MANUAL_QA_RUNBOOK.md):
  درس → ظهور الغلاف/الرسوم → تشغيل الصوت → **لا صور/أصوات مكسورة**.

### 11) Rollback plan
```
# استرجاع الوسائط من النسخة:
docker run --rm -v onlenco_media_data:/data -v "$PWD":/backup alpine \
  sh -c 'rm -rf /data/* && tar xzf /backup/media_backup_YYYY-MM-DD.tgz -C /data'
# استرجاع DB:
docker compose -f docker-compose.prod.yml exec -T db \
  psql -U "$POSTGRES_USER" "$POSTGRES_DB" < db_backup_YYYY-MM-DD.sql
```

---

## ملاحظات مخاطر
- **حجم محمول مُسمّى يبقى** عبر عمليات النشر؛ لكن حذف الحجم (`docker volume rm`) أو
  أول نشر على بيئة جديدة = **media فارغة → صور مكسورة**. أول نشر يحتاج هذه المزامنة.
- تطابق صفوف DB ↔ المسارات النسبية إلزامي (راجع §0).
- **لا تُعِد توليد** الصور/الصوت في الإنتاج (تكلفة OpenAI + تغيّر المسارات) — انقل المعتمَد كما هو.

# Onlenco — Test Login Accounts

Demo accounts seeded by `python manage.py seed_teacher_demo`.
**Development / seed data only — do not use in production.**

- **Login page:** http://localhost:8080/auth/
- **Password (all accounts):** `onlenco123`

---

## Primary accounts

| Role | Email | Dashboard |
|------|-------|-----------|
| 🛠️ **Admin** | `super@onlenco.local` | http://localhost:8080/admin/ |
| 👨‍🏫 **Teacher** | `sara.teacher@onlenco.local` | http://localhost:8080/teacher/dashboard/ |
| 🎓 **Student** | `lina.student@onlenco.local` | http://localhost:8080/dashboard/ |

All three verified: login works and the dashboard returns HTTP 200.

---

## All seeded accounts

| Label | Email | Notes |
|-------|-------|-------|
| Super Admin | `super@onlenco.local` | Full Control Center access (superuser) |
| Platform Admin | `platform@onlenco.local` | Platform administration |
| Academic Admin | `academic@onlenco.local` | Courses & content |
| Finance Admin | `finance@onlenco.local` | Payments, plans, refunds |
| Support Admin | `support@onlenco.local` | Student support |
| AI Admin | `ai@onlenco.local` | AI monitoring |
| Ahmed (Student + Teacher) | `ahmed@onlenco.local` | Has both roles |
| Sara (Teacher) | `sara.teacher@onlenco.local` | Teacher portal |
| Lina (Student) | `lina.student@onlenco.local` | Student dashboard |
| Omar (Student) | `omar.student@onlenco.local` | Student dashboard |

---

## Re-seed

```bash
python manage.py seed_teacher_demo            # users + courses + demo data
# optional content seeds:
python manage.py seed_books seed_dictionary seed_placement_questions
```

The seeder is idempotent — re-running updates existing rows, never duplicates.

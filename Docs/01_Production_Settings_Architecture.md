# 1. Prompt — إصلاح الأساس المعماري والإعدادات

```text
You are a senior Django production architect.

Analyze and refactor the project settings and structure to make the system production-ready without changing business behavior.

Current problem:
The project is a working MVP but needs better production architecture, secure settings, environment separation, and maintainable configuration.

Tasks:
1. Inspect the current Django settings.
2. Split settings into:
   - config/settings/base.py
   - config/settings/development.py
   - config/settings/production.py
   - config/settings/test.py
3. Move all secrets to environment variables.
4. Remove unsafe defaults such as:
   - DEBUG=True by default
   - ALLOWED_HOSTS=["*"]
   - hardcoded SECRET_KEY
5. Configure:
   - PostgreSQL support
   - Static files
   - Media files
   - Logging
   - Email backend
   - CSRF trusted origins
   - Secure cookies for production
6. Keep SQLite allowed only for local development.
7. Add .env.example.
8. Make sure manage.py still works.
9. Add documentation in README for local setup.

Constraints:
- Do not remove current apps.
- Do not change business logic.
- Do not break templates.
- Use environment variables cleanly.
- Keep development simple.

Expected output:
- Modified files list
- New settings structure
- .env.example
- README setup section
- Validation commands:
  python manage.py check
  python manage.py makemigrations --check
  python manage.py migrate
  python manage.py test
```

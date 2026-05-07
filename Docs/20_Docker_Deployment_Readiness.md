# 20. Prompt — Docker + Deployment Readiness

```text
You are a senior DevOps engineer for Django SaaS applications.

Prepare the Onlenco project for production deployment.

Tasks:
1. Add Dockerfile.
2. Add docker-compose.yml for:
   - web
   - PostgreSQL
   - Redis
3. Add gunicorn.
4. Add whitenoise or static file serving strategy.
5. Add environment variable support.
6. Add health check endpoint.
7. Add production run commands.
8. Add deployment README.
9. Add backup notes for database and media.
10. Add Celery placeholder if future async AI tasks are needed.
11. Ensure collectstatic works.
12. Ensure migrations run.

Validation:
docker compose build
docker compose up
python manage.py check --deploy

Output:
- Deployment files created
- Environment variables needed
- Production checklist
```

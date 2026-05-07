# 14. Prompt — تحسين الأمن والصلاحيات

```text
You are a senior Django security engineer.

Audit and harden the Onlenco platform security.

Tasks:
1. Check settings for production security.
2. Review authentication and authorization.
3. Ensure users cannot access other users':
   - profile
   - placement results
   - tutor conversations
   - learning profile
   - errors
   - weaknesses
   - payments
4. Add object-level permission checks where needed.
5. Protect file uploads for payment screenshots.
6. Validate uploaded file types and size.
7. Add rate limiting plan for:
   - login
   - AI tutor
   - text analysis
   - exercise generation
8. Check CSRF usage.
9. Check admin access.
10. Check sensitive data exposure in templates and APIs.
11. Add security tests.

Expected improvements:
- Secure settings
- Permission checks
- Safer uploads
- API authorization
- No cross-user data leak

Validation:
python manage.py test
python manage.py check --deploy

Output:
- Security issues found
- Fixes applied
- Remaining risks
```

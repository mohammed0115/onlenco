# Prompt 05 — User Isolation and Security Tests

```text
You are a senior Django security engineer.

Perform a strict user data isolation audit.

Create or use two test users:
- user_a
- user_b

Verify user_a cannot access user_b:
- profile
- placement result
- tutor conversation
- tutor messages
- learning profile
- skill mastery
- errors
- weaknesses
- exercises assigned to user_b if user-specific
- attempts
- recommendations
- payments
- subscription data
- dashboard data
- uploaded payment screenshots

Test both:
1. Django template views
2. REST APIs
3. direct object IDs in URLs
4. admin-only views
5. form submissions
6. file/media URLs where applicable

Also check:
- DEBUG is not enabled in production
- SECRET_KEY is not hardcoded
- ALLOWED_HOSTS is restricted
- CSRF is enabled
- secure cookies are configured for production
- uploaded files have validation
- API permissions use object-level filtering
- admin routes require staff/superuser
- no .env or secrets are committed

Add permission tests.

Any cross-user data leak is Critical severity.

Output:
- Security findings table
- Cross-user access test results
- Critical issues
- Required fixes
- Tests added or required
- Validation commands:
  python manage.py test
  python manage.py check --deploy
```

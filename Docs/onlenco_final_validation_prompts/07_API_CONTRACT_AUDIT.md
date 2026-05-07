# Prompt 07 — REST API Contract Audit

```text
You are a senior Django REST Framework API architect.

Audit all REST APIs in Onlenco.

For each API endpoint, verify:
1. URL
2. HTTP method
3. Authentication required
4. Permission rules
5. Object-level access control
6. Request schema
7. Response schema
8. Error responses
9. Validation rules
10. Tests
11. OpenAPI/Swagger documentation
12. Rate limiting where needed
13. Whether it is safe for mobile/frontend use

Required endpoint groups:
- auth/profile
- placement
- learning profile
- weaknesses
- skill mastery
- errors
- exercises
- attempts
- recommendations
- tutor
- dictionary
- library
- payments
- analytics
- AI usage if admin-accessible

Output:
- API table
- Missing endpoints
- Unsafe endpoints
- Undocumented endpoints
- Endpoints missing tests
- Permission risks
- Recommended API fixes
- Example request/response for core APIs

Do not mark the platform API-ready unless:
- endpoints exist
- authentication works
- users cannot access other users' data
- validation is clear
- tests exist
- docs exist or are planned
```

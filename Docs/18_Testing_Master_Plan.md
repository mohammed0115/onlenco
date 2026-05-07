# 18. Prompt — Testing Master Plan + تنفيذ اختبارات

```text
You are a senior QA automation engineer for Django applications.

The current Onlenco project has very limited test coverage. Build a serious testing foundation.

Tasks:
1. Inspect existing tests.
2. Create a test plan covering:
   - accounts
   - lessons
   - placement
   - tutor
   - dictionary
   - library
   - club
   - payments
   - analytics
   - learning_core
   - APIs
3. Add tests for:
   - model behavior
   - service logic
   - permissions
   - views
   - forms
   - API endpoints
   - AI fallback behavior
4. Mock external AI calls.
5. Add factories or fixtures for users, lessons, quizzes, exercises, attempts.
6. Add coverage configuration.
7. Ensure tests are deterministic and fast.

Minimum required test cases:
- user registration and login
- placement submission
- lesson progress
- quiz answer submission
- wrong answer creates UserError
- weaknesses update after errors
- adaptive difficulty updates theta
- personalized exercises generated
- AI tutor fallback
- dictionary fallback
- payment submission and approval
- dashboard analytics empty state
- user cannot access another user's data

Validation:
python manage.py test
coverage run manage.py test
coverage report

Output:
- Tests added
- Coverage summary
- Critical flows covered
- Remaining testing gaps
```

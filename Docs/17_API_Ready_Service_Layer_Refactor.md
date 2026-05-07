# 17. Prompt — تحويل النظام إلى API-ready Product بدون كسر Templates

```text
You are a senior full-stack Django architect.

Refactor the system so every major user action has a service layer that can be reused by both Django templates and REST APIs.

Target actions:
1. Register user
2. Start placement test
3. Submit placement test
4. Start lesson
5. Submit quiz
6. Analyze writing text
7. Generate exercises
8. Submit exercise attempt
9. Chat with AI tutor
10. Submit payment
11. Approve payment
12. Load dashboard analytics

Tasks:
1. Inspect current views.
2. Identify business logic inside views.
3. Move business logic into service files.
4. Keep views thin.
5. Make services reusable from API views.
6. Add tests for services.
7. Ensure templates still work.

Expected service structure:
accounts/services/
placement/services/
lessons/services/
learning_core/services/
tutor/services/
payments/services/
analytics/services/

Constraints:
- Do not rewrite the whole system at once.
- Refactor incrementally.
- Keep behavior unchanged unless explicitly improved.

Validation:
python manage.py test
python manage.py check

Output:
- Views refactored
- Services created
- Before/after explanation
```

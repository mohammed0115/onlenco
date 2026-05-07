# 0. Master Prompt — فحص شامل للنظام وتثبيت الخطة

```text
You are a senior Python/Django software architect and AI product engineer.

I have a Django project called Onlenco. It is an English learning platform with apps such as accounts, lessons, placement, tutor, dictionary, library, club, payments, and analytics.

The target product is an advanced AI-powered adaptive English learning system. It must learn from user mistakes, classify errors, predict weaknesses, adapt exercise difficulty, generate personalized exercises, and continuously update the student learning profile.

Your task:
1. Read the full codebase carefully.
2. Do not modify code yet.
3. Analyze the current architecture, apps, models, views, templates, services, settings, and tests.
4. Compare the current system with the target adaptive learning system.
5. Identify all missing gaps in:
   - Learning data model
   - Error analysis
   - Weakness prediction
   - Adaptive difficulty
   - Personalized exercise generation
   - AI tutor logic
   - Placement test
   - REST APIs
   - Analytics
   - Security
   - Testing
   - Deployment
   - UI/UX
   - i18n Arabic/English support
6. Create a phased implementation plan.
7. For each phase, list:
   - Files to create
   - Files to modify
   - Models to add
   - Services to add
   - APIs to add
   - Tests to add
   - Expected validation commands

Important constraints:
- Do not break existing pages.
- Do not remove existing apps unless necessary.
- Preserve current functionality.
- Use clean architecture, SOLID, DRY, service layer, and clear separation of concerns.
- Prefer incremental migration.
- Every implementation step must be testable.

Output:
- Current system summary
- Gap analysis table
- Priority ranking
- Phase-by-phase execution plan
- Risk assessment
- Recommended first implementation phase
```

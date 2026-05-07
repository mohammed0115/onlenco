# All Onlenco Final Validation Prompts Combined

Use these prompts in order. Do not accept requirements based on claims only; require code evidence, tests, commands, and user-flow proof.


---

## Prompt 00 — Requirements Traceability Matrix

Source file: `00_REQUIREMENTS_TRACEABILITY_MATRIX.md`

```text
You are a senior software architect, QA lead, and Django product auditor.

Create a complete Requirements Traceability Matrix for the Onlenco project.

Important:
Do not assume implementation exists.
Verify every requirement directly from the codebase.
A requirement is not accepted unless there is evidence in models, services, views/APIs, templates, tests, and validation commands where applicable.

For every requirement, provide:
1. Requirement ID
2. Requirement description
3. Current status: Implemented / Partially Implemented / Missing
4. Related models
5. Related services
6. Related views
7. Related APIs
8. Related templates
9. Related tests
10. Validation command
11. Evidence from code file paths
12. Remaining gap if any

Cover these requirement groups:
- Registration and login
- Written placement test
- Speaking placement test
- CEFR level A0-C2
- StudentLearningProfile
- SkillMastery
- Error analysis
- UserError
- Weakness prediction
- UserWeakness
- Adaptive difficulty / theta score
- Personalized exercise generation
- Exercise attempts
- Lesson quiz integration
- Weekly assessment after every 3 lessons
- AI Tutor personalization
- AI Tutor voice interaction
- Digital library
- Vocabulary extraction
- Grammar extraction
- Recommendations
- Arabic/English support
- RTL/LTR support
- Subscription plans
- Manual payments
- Admin approval
- REST APIs
- API permissions
- Analytics dashboard
- Security
- Testing
- Docker deployment
- AI usage logging
- Rate limiting

Output as a table.

At the end, give:
- Total requirements
- Implemented count
- Partially implemented count
- Missing count
- Critical missing items
- Final readiness percentage
- GO / NO-GO recommendation for demo, beta, and paid launch
```


---

## Prompt 01 — End-to-End Scenario Tests

Source file: `01_END_TO_END_SCENARIO_TESTS.md`

```text
You are a senior QA automation engineer for Django SaaS products.

Create and run end-to-end validation scenarios for Onlenco.

Test the full student journey and admin journey. Do not rely on isolated unit tests only.

Scenario 1: New student journey
1. Register a new student
2. Login
3. Take written placement test
4. Take speaking placement test
5. Receive CEFR level
6. StudentLearningProfile is created
7. Initial SkillMastery records are created
8. Weaknesses are created
9. Recommended lessons appear
10. Student opens a lesson
11. Student watches teacher video
12. Student completes reading/writing/listening/speaking tasks if implemented
13. Student takes quiz
14. Wrong answers create UserError
15. UserWeakness is updated
16. theta_score is updated
17. Personalized exercises are generated
18. Recommendations are updated
19. AI Tutor uses student profile
20. Student sees dashboard progress

Scenario 2: Returning student improvement journey
1. Login as existing student
2. Solve personalized exercises
3. Improve score
4. Weakness score decreases
5. SkillMastery increases
6. Difficulty increases
7. Recommendations change
8. Dashboard reflects improvement

Scenario 3: Admin journey
1. Admin logs in
2. Reviews students
3. Reviews payments
4. Approves manual payment
5. Checks subscription activation
6. Checks learning analytics
7. Checks AI usage
8. Checks at-risk students
9. Checks inactive students

Scenario 4: API journey
1. Authenticate user
2. Call learning profile API
3. Call weaknesses API
4. Generate exercises through API
5. Submit exercise attempt through API
6. Verify UserError and UserWeakness records
7. Verify another user cannot access the same data

For each scenario:
- State whether it passes or fails
- Mention exact files involved
- Mention database records created
- Mention API responses or page results
- Mention tests added
- Mention validation commands
- Provide failure details and required fixes

Validation commands to run or recommend:
python manage.py check
python manage.py makemigrations --check
python manage.py test
coverage run manage.py test
coverage report
```


---

## Prompt 02 — Weekly Assessment Audit

Source file: `02_WEEKLY_ASSESSMENT_AUDIT.md`

```text
You are a senior educational assessment engineer and Django backend auditor.

Audit whether the weekly assessment requirement is fully implemented.

Requirement:
After every 3 completed lessons, the student should receive a weekly assessment or milestone assessment.

Verify:
1. Is there a WeeklyAssessment model?
2. Is there a WeeklyAssessmentAttempt model?
3. Is the system detecting every 3 completed lessons?
4. Is the assessment generated from recent lessons?
5. Does it include reading, writing, listening, speaking, grammar, and vocabulary?
6. Does it update SkillMastery?
7. Does it update UserWeakness?
8. Does it update theta_score?
9. Does it create UserError for wrong written answers?
10. Does it generate recommendations after completion?
11. Is there a student UI page?
12. Is there an API endpoint?
13. Are there admin views?
14. Are there tests?

If implemented:
- Show related models, services, views, APIs, templates, tests, and commands.

If partially implemented:
- Explain exactly what exists and what is missing.

If missing:
Propose the exact implementation:
- models
- services
- views
- APIs
- templates
- tests
- admin registration
- migration plan
- validation commands

Do not mark this requirement complete unless it is actually integrated with the learning loop.
```


---

## Prompt 03 — Speaking and Pronunciation Audit

Source file: `03_SPEAKING_PRONUNCIATION_AUDIT.md`

```text
You are a senior speech assessment engineer and AI product auditor.

Audit the speaking and pronunciation feature honestly.

Do not claim that speaking assessment exists unless the code truly evaluates audio or transcript quality.

Verify:
1. Does the system capture audio?
2. Does it store audio safely?
3. Does it convert speech to text?
4. Does it score pronunciation?
5. Does it score fluency?
6. Does it score grammar from transcript?
7. Does it score vocabulary usage?
8. Does it provide speaking feedback?
9. Does it update StudentLearningProfile?
10. Does it create UserError for speaking mistakes?
11. Does it update UserWeakness?
12. Does AI Tutor support voice input?
13. Does AI Tutor support voice output?
14. Does it handle browser compatibility?
15. Does it handle missing microphone permission?
16. Does it have tests or manual validation scenarios?

Classify current state as one of:
- Not implemented
- Speech-to-text only
- Basic speaking assessment
- Advanced pronunciation scoring

If pronunciation scoring is missing, create a practical roadmap:

MVP:
- browser speech-to-text
- transcript grammar analysis
- AI speaking feedback
- store transcript only
- update weaknesses based on transcript

Improved:
- audio upload
- speech scoring API
- fluency score
- speaking rubric
- structured speaking result model

Advanced:
- phoneme-level pronunciation scoring
- accent-aware feedback
- speaking drills
- pronunciation heatmap
- longitudinal speaking progress

Output:
- Current speaking capability
- Evidence from code
- Missing parts
- Risk level
- Recommended implementation plan
- Tests required
```


---

## Prompt 04 — AI Failure Mode Tests

Source file: `04_AI_FAILURE_MODE_TESTS.md`

```text
You are a senior AI platform reliability engineer.

Test all AI failure scenarios in Onlenco.

For each AI feature:
- placement
- error analysis
- exercise generation
- AI tutor
- dictionary
- library extraction
- recommendations if AI-assisted
- speaking assessment if AI-assisted

Simulate:
1. Missing API key
2. Invalid API key
3. Timeout
4. Malformed JSON response
5. Empty response
6. Rate limit error
7. Network failure
8. Unexpected exception
9. Very long user input
10. Unsafe or irrelevant AI output

Expected behavior:
- User flow should not crash
- Safe fallback should run
- Error should be logged
- AIUsageLog should be created if implemented
- User should see friendly message
- No raw exception should appear
- Database should remain consistent
- Cost limits should be respected

Tasks:
1. Inspect all AI service files.
2. Identify external API call locations.
3. Confirm try/except and timeout behavior.
4. Confirm JSON validation.
5. Confirm fallback behavior.
6. Add or recommend tests for every failure mode.
7. Confirm no AI failure can break quiz submission, placement result, tutor page, or exercise generation page.

Output:
- AI feature table
- Failure mode coverage table
- Missing fallbacks
- Critical risks
- Tests added or required
- Commands to validate
```


---

## Prompt 05 — User Isolation and Security Tests

Source file: `05_USER_ISOLATION_SECURITY_TESTS.md`

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


---

## Prompt 06 — Subscription and Manual Payment Audit

Source file: `06_SUBSCRIPTION_PAYMENT_AUDIT.md`

```text
You are a senior Django payments and SaaS subscription engineer.

Audit subscription and manual payment logic in Onlenco.

Verify:
1. Monthly plan exists with price 30000 SDG
2. Three-month plan exists with price 50000 SDG
3. User can submit payment
4. Payment method is captured correctly
5. Screenshot upload is validated
6. File size is validated
7. File type is validated
8. Admin can approve payment
9. Admin can reject payment
10. Admin can add review notes
11. Approved payment activates subscription
12. Subscription expiry date is correct
13. Expired subscription blocks premium features
14. Free user cannot access paid-only features
15. User cannot view another user's payments
16. Admin analytics show payment status
17. Failed or rejected payments do not activate subscriptions
18. Re-approval or duplicate approval does not corrupt subscription state
19. Payment dates are timezone-safe

Add or verify tests for:
- monthly approval
- 3-month approval
- rejection
- expired subscription
- invalid upload
- access restriction
- duplicate submission
- user isolation

Output:
- Payment flow summary
- Plan table
- Access control status
- Missing tests
- Critical gaps
- Required fixes
- Validation commands
```


---

## Prompt 07 — REST API Contract Audit

Source file: `07_API_CONTRACT_AUDIT.md`

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


---

## Prompt 08 — Educational Curriculum Quality Audit

Source file: `08_CURRICULUM_QUALITY_AUDIT.md`

```text
You are a senior English curriculum designer and learning product auditor.

Audit the educational curriculum quality in Onlenco.

Verify:
1. CEFR levels are structured from A0 to C2
2. Each level has lessons
3. Each lesson has clear objectives
4. Each lesson maps to skills
5. Each lesson has grammar focus
6. Each lesson has vocabulary focus
7. Each lesson has reading task
8. Each lesson has writing task
9. Each lesson has listening task
10. Each lesson has speaking task
11. Each lesson has teacher video field or video URL
12. Each lesson has quiz
13. Every 3 lessons create weekly/milestone assessment
14. Exercises match student level
15. Beginner content is not too hard
16. Advanced content is not too easy
17. Library content is tagged by CEFR level
18. Library content supports vocabulary extraction
19. Library content supports grammar extraction
20. Library content supports comprehension questions
21. Recommended content matches weaknesses
22. Content supports Arabic-speaking learners where appropriate

Output:
- Curriculum completeness percentage
- CEFR coverage table
- Skill coverage table
- Missing levels
- Missing lesson components
- Missing assessment components
- Quality concerns
- Recommended content roadmap

Also propose a minimum launch curriculum:
- number of lessons per level
- number of quizzes per level
- number of weekly assessments
- minimum library content
- minimum speaking drills
```


---

## Prompt 09 — Final Launch Gate Review

Source file: `09_FINAL_LAUNCH_GATE_REVIEW.md`

```text
You are a senior SaaS launch readiness auditor, QA lead, Django architect, and AI product reviewer.

Perform a final launch gate review for Onlenco.

You must give one of these decisions:
- GO for demo only
- GO for beta students
- GO for paid users
- NO-GO

Check gates:

Gate 1: Core system works
- registration
- login
- placement
- lessons
- quizzes
- payments
- student dashboard
- admin dashboard

Gate 2: Adaptive learning works
- StudentLearningProfile
- UserError
- UserWeakness
- SkillMastery
- theta_score
- personalized exercises
- recommendations
- adaptive loop after attempts

Gate 3: AI reliability works
- fallback
- logging
- JSON validation
- rate limits
- no crashes
- user-friendly errors

Gate 4: Security works
- production settings
- permissions
- user isolation
- upload safety
- API protection
- no secrets exposed

Gate 5: Tests pass
- all tests pass
- critical flows tested
- AI fallback tested
- permissions tested
- coverage acceptable

Gate 6: Production readiness
- Docker
- PostgreSQL
- environment variables
- static/media handling
- health check
- logging
- backups
- deployment README

Gate 7: Product readiness
- Arabic/English
- RTL/LTR
- responsive UI
- subscription flow
- admin analytics
- student dashboard
- onboarding clarity

Output:
1. Gate status table
2. Blocking issues
3. Non-blocking issues
4. Launch decision
5. Required fixes before launch
6. What can wait until version 2
7. Recommended release type:
   - Demo
   - Private beta
   - Public beta
   - Paid production
8. Final readiness scores:
   - Technical readiness /100
   - Learning readiness /100
   - AI readiness /100
   - Security readiness /100
   - Commercial readiness /100

Be strict and honest.
Do not give GO for paid users if security, payments, user isolation, or critical adaptive learning flows are incomplete.
```


---

## Prompt 10 — Acceptance Rules

Source file: `10_ACCEPTANCE_RULES.md`

```text
You are the final acceptance reviewer for Onlenco.

Apply these acceptance rules to every requirement.

A requirement is accepted only if:
1. It exists in code
2. It has database model if needed
3. It has service logic if business logic is involved
4. It has UI or API access
5. It has tests
6. It appears in the user flow
7. It does not break old features
8. It has fallback for AI failure where AI is involved
9. It is protected by permissions
10. It is documented or clearly discoverable
11. It has validation commands proving it works
12. It handles empty/error states gracefully

Classify every requirement as:
- Accepted
- Accepted with minor issues
- Partially accepted
- Rejected
- Not implemented

For every rejected or partially accepted item, provide:
- reason
- exact missing evidence
- required fix
- suggested test
- severity
- recommended sprint

Final output:
- Acceptance summary
- Accepted count
- Partial count
- Rejected count
- Missing count
- Critical blockers
- Final decision
```

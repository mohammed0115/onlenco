# Prompt 06 — Subscription and Manual Payment Audit

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

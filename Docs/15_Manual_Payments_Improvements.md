# 15. Prompt — تحسين نظام المدفوعات اليدوي

```text
You are a senior Django payments engineer.

Audit and improve the current manual payments system.

Current payment methods include Bankak, Fawry, and O-Cash with screenshot upload and admin approval.

Tasks:
1. Inspect payments app models, forms, views, admin, and tests.
2. Ensure payment flow is reliable:
   - user submits payment
   - screenshot uploaded safely
   - admin reviews
   - admin approves or rejects
   - subscription status updates correctly
3. Add validations:
   - amount required
   - transaction reference optional/required depending on method
   - screenshot file type
   - screenshot size
4. Add payment statuses:
   - pending
   - approved
   - rejected
   - needs_review
5. Add admin notes.
6. Add timestamps:
   - submitted_at
   - reviewed_at
7. Add tests for:
   - submit payment
   - approve payment
   - reject payment
   - invalid upload
   - subscription update
8. Ensure users cannot see other users' payments.

Validation:
python manage.py test payments
python manage.py check

Output:
- Payment flow summary
- Files modified
- Tests added
```

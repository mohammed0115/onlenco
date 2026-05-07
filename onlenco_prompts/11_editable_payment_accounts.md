# 11 — Editable Payment Method Accounts

## Context

The **Onlenco** payment flow currently shows three hardcoded payment methods
(Bankak / Fawry / O-Cash) with hardcoded account numbers. The data lives in
`payments/views.py`:

```python
ACCOUNT_INFO = {
    "bankak": {"label": "Bankak", "account": "1234 5678 9012", "name": "Onlenco Sudan"},
    "fawry":  {"label": "Fawry",  "account": "+249 91 234 5678", "name": "Onlenco Sudan"},
    "ocash":  {"label": "O-Cash", "account": "+249 92 876 5432", "name": "Onlenco Sudan"},
}
```

This means changing an account number requires a code deploy. This prompt
moves it into a model so admins can edit account details from `/admin/`
without redeploying.

Project conventions:
- Use Django's built-in `/admin/`. No custom admin pages.
- The existing `PAYMENT_METHODS` choices list lives in `payments/models.py`
  — reuse it.

## Goal

Replace the hardcoded `ACCOUNT_INFO` dict with a `PaymentMethodAccount`
model. Migrate seed data into it. Update the subscribe view to read from
the DB.

## Spec

### Model — `payments/models.py`

Add to the existing models file:

```python
class PaymentMethodAccount(models.Model):
    """Bank/wallet account details shown to students for offline transfer.

    Editable by admins via /admin/ so account numbers can change without
    a code deploy. Each method (Bankak/Fawry/O-Cash) has at most one
    active row at a time.
    """
    method = models.CharField(max_length=10, choices=PAYMENT_METHODS, unique=True)
    label = models.CharField(max_length=80, help_text="Display name, e.g. 'Bankak'")
    account_number = models.CharField(max_length=80,
        help_text="Account number, IBAN, or phone number to send to.")
    account_holder = models.CharField(max_length=120, default="Onlenco Sudan",
        help_text="Name on the account.")
    instructions = models.TextField(blank=True,
        help_text="Optional extra instructions shown under the account info.")
    is_active = models.BooleanField(default=True)
    sort_order = models.PositiveSmallIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["sort_order", "method"]
        verbose_name = "Payment method account"
        verbose_name_plural = "Payment method accounts"

    def __str__(self):
        return f"{self.label} — {self.account_number}"
```

### Migration — data migration

Generate a migration with `python manage.py makemigrations payments`. Then
add a **data migration** in the same migration file (or a follow-up one)
that seeds the three existing methods:

```python
def seed_methods(apps, schema_editor):
    PMA = apps.get_model("payments", "PaymentMethodAccount")
    PMA.objects.get_or_create(
        method="bankak",
        defaults=dict(label="Bankak", account_number="1234 5678 9012",
                      account_holder="Onlenco Sudan", sort_order=10),
    )
    PMA.objects.get_or_create(
        method="fawry",
        defaults=dict(label="Fawry", account_number="+249 91 234 5678",
                      account_holder="Onlenco Sudan", sort_order=20),
    )
    PMA.objects.get_or_create(
        method="ocash",
        defaults=dict(label="O-Cash", account_number="+249 92 876 5432",
                      account_holder="Onlenco Sudan", sort_order=30),
    )

operations = [
    # ... model creation ...
    migrations.RunPython(seed_methods, reverse_code=migrations.RunPython.noop),
]
```

This way, anyone running the migration on a fresh DB gets the same default
data the old hardcoded dict provided.

### View changes — `payments/views.py`

Remove the `ACCOUNT_INFO` dict at the top of the file. Update `subscribe(request)`:

```python
from .models import PaymentMethodAccount

def subscribe(request):
    profile = request.user.profile
    accounts_qs = PaymentMethodAccount.objects.filter(is_active=True)
    # Build the dict shape the template expects: {code: {label, account, name}}
    accounts = {
        a.method: {
            "label": a.label,
            "account": a.account_number,
            "name": a.account_holder,
            "instructions": a.instructions,
        }
        for a in accounts_qs
    }
    # ... rest of the existing view, passing `accounts` to the template
```

The template already iterates `accounts.items` so this drop-in works. The
extra `instructions` key gives admins a place to add per-method notes —
update the template to show it under the account number when present.

### Template changes — `templates/payments/subscribe.html`

Two small additions:

1. In the method picker, only render methods that exist in `accounts` (the
   current `{% for code, info in accounts.items %}` already does this if
   the dict comes from the DB).

2. In the "Payment instructions" card, show each method's `instructions`
   field if non-empty:

```html
<ul class="text-sm mt-3 space-y-2">
  {% for code, info in accounts.items %}
  <li>
    <strong>{{ info.label }}:</strong> {{ info.name }} — <code>{{ info.account }}</code>
    {% if info.instructions %}
      <div class="text-xs text-muted-foreground mt-1">{{ info.instructions }}</div>
    {% endif %}
  </li>
  {% endfor %}
</ul>
```

### Admin — `payments/admin.py`

Register the new model:

```python
from .models import PaymentMethodAccount

@admin.register(PaymentMethodAccount)
class PaymentMethodAccountAdmin(admin.ModelAdmin):
    list_display = ("method", "label", "account_number", "account_holder",
                    "is_active", "sort_order")
    list_filter = ("is_active",)
    list_editable = ("is_active", "sort_order")
    search_fields = ("label", "account_number", "account_holder")
    ordering = ("sort_order", "method")
```

### Form-side validation — `payments/forms.py`

The form already has a `method` field driven by the `PAYMENT_METHODS`
choices tuple. Add a small validation step: reject submissions whose
chosen method has no active `PaymentMethodAccount` row. This prevents a
race where an admin deactivates a method between a user loading the form
and submitting:

```python
def clean_method(self):
    method = self.cleaned_data["method"]
    if not PaymentMethodAccount.objects.filter(method=method, is_active=True).exists():
        raise forms.ValidationError("This payment method is not currently available.")
    return method
```

### Tests (optional)

In `payments/tests.py`, a quick sanity test:

```python
from django.test import TestCase
from payments.models import PaymentMethodAccount

class PaymentMethodAccountSeedTest(TestCase):
    def test_three_methods_seeded(self):
        # data migration should have created 3 rows
        codes = set(PaymentMethodAccount.objects.values_list("method", flat=True))
        self.assertEqual(codes, {"bankak", "fawry", "ocash"})
```

## Acceptance criteria

A reviewer should be able to:

1. Run `python manage.py migrate` on a fresh DB → 3 `PaymentMethodAccount`
   rows are seeded (Bankak / Fawry / O-Cash) with the same numbers as before.
2. Visit `/payments/` while logged in → see the same three method cards as
   before, with the same account numbers.
3. In `/admin/payments/paymentmethodaccount/`, edit the Bankak row's
   `account_number` to "9999 8888 7777" and save.
4. Refresh `/payments/` → see "9999 8888 7777" displayed without restarting
   the server.
5. In `/admin/`, set the Fawry row's `is_active` to False.
6. Refresh `/payments/` → only Bankak and O-Cash now appear in the method
   picker. The "Payment instructions" list also drops Fawry.
7. Try to submit the form with `method=fawry` (e.g. via a stale browser tab)
   → form rejects it with the "not currently available" error.
8. Add an `instructions` value to the O-Cash row ("Send via the merchant
   tab, not personal transfer.") → see that line below the O-Cash entry on
   `/payments/`.

`python manage.py check`, `python manage.py migrate`, all clean.

## Out of scope

- No multi-currency: amounts are still always SDG.
- No payment-gateway integration. Still manual transfer + screenshot upload.
- No country-based filtering of methods.
- No QR codes for the account numbers.

## Style guide

- Match the existing model patterns in `payments/models.py`: HelpText on
  fields admins will edit, `Meta.ordering`, descriptive `__str__`.
- Don't add a `verbose_name` for fields unless it'd be misleading without one.
- Keep the data migration self-contained in the same `0002_*.py` file as
  the schema migration. Don't split.

## What to deliver

A patched `onlenco_django.zip` with:

- `payments/models.py`: new `PaymentMethodAccount` model
- New migration file (schema + data) that seeds Bankak/Fawry/O-Cash
- `payments/views.py`: `ACCOUNT_INFO` removed, replaced with DB query
- `payments/forms.py`: `clean_method()` validation added
- `payments/admin.py`: `PaymentMethodAccountAdmin` registered
- `templates/payments/subscribe.html`: `instructions` rendered when present
- (Optional) test in `payments/tests.py`

`python manage.py check`, `python manage.py migrate`, and `python manage.py
seed_demo` all run clean. Existing payment submissions still work.

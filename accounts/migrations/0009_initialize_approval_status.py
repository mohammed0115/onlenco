"""Initialize approval_status for EXISTING accounts so the new student gate
does not lock out current real users.

Rules:
  * staff / superuser / admin-role / Teacher-group  -> approved (exempt)
  * email-verified students                         -> approved
  * everyone else (unverified)                      -> pending_email_verification

Idempotent and safe: the management command `initialize_student_approval_status`
re-runs the same logic with reporting.
"""
from django.db import migrations


def init_status(apps, schema_editor):
    Profile = apps.get_model("accounts", "Profile")
    Group = apps.get_model("auth", "Group")
    teacher_ids = set()
    tg = Group.objects.filter(name="Teacher").first()
    if tg:
        teacher_ids = set(tg.user_set.values_list("id", flat=True))

    for p in Profile.objects.select_related("user").iterator():
        u = p.user
        privileged = (
            u.is_staff or u.is_superuser
            or p.role == "admin"
            or u.id in teacher_ids
        )
        if privileged or p.email_verified:
            p.approval_status = "approved"
        else:
            p.approval_status = "pending_email_verification"
        p.save(update_fields=["approval_status"])


def noop(apps, schema_editor):
    # Reverse: leave statuses as-is (no destructive rollback).
    pass


class Migration(migrations.Migration):
    dependencies = [
        ("accounts", "0008_profile_admin_approved_at_profile_admin_approved_by_and_more"),
    ]
    operations = [migrations.RunPython(init_status, noop)]

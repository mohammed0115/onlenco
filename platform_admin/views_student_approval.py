"""Student registration approval queue (anti-bot gate) — control panel.

Admins (and teacher-admins with the capability) review pending students and
approve / reject / suspend them. All actions go through
``accounts.approval`` so the audit trail is always written.
"""
from __future__ import annotations

from django.contrib import messages
from django.contrib.auth import get_user_model
from django.core.paginator import Paginator
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from accounts import approval as approval_service
from accounts.models import (
    APPROVAL_PENDING_ADMIN, APPROVAL_STATUS_CHOICES, Profile,
)

from . import permissions as perms
from .decorators import control_permission_required

User = get_user_model()


@control_permission_required(perms.CAP_STUDENTS_VIEW)
def student_approvals(request):
    """List students filtered by approval_status (default: pending admin)."""
    status = request.GET.get("status", APPROVAL_PENDING_ADMIN)
    qs = (Profile.objects.select_related("user")
          .filter(role="student")
          .exclude(user__is_staff=True)
          .order_by("-created_at"))
    if status:
        qs = qs.filter(approval_status=status)
    page = Paginator(qs, 50).get_page(request.GET.get("page"))
    rows = [{
        "id": p.user_id,
        "name": p.full_name or p.user.get_username(),
        "email": p.user.email or p.user.username,
        "registered": p.created_at,
        "email_verified": p.email_verified,
        "ip": p.registration_ip,
        "user_agent": p.registration_user_agent,
        "suspicious_flags": p.suspicious_flags,
        "approval_status": p.approval_status,
    } for p in page.object_list]
    return render(request, "platform_admin/students/approvals.html", {
        "page_obj": page, "rows": rows, "status": status,
        "status_choices": APPROVAL_STATUS_CHOICES, "section": "student_approvals",
    })


@require_POST
@control_permission_required(perms.CAP_STUDENTS_MANAGE)
def student_approval_action(request, pk, action):
    student = get_object_or_404(User.objects.select_related("profile"), pk=pk)
    note = (request.POST.get("note") or "").strip()
    try:
        if action == "approve":
            approval_service.approve(student, actor=request.user, note=note)
            messages.success(request, "Student approved.")
        elif action == "reject":
            approval_service.reject(student, actor=request.user, note=note)
            messages.success(request, "Student rejected.")
        elif action == "suspend":
            approval_service.suspend(student, actor=request.user, note=note)
            messages.success(request, "Student suspended.")
        elif action == "note":
            approval_service.add_note(student, actor=request.user, note=note)
            messages.success(request, "Note added.")
        else:
            messages.error(request, "Unknown action.")
    except approval_service.ApprovalError as exc:
        messages.error(request, str(exc))
    return redirect(request.META.get("HTTP_REFERER") or "platform_admin:student_approvals")


@require_POST
@control_permission_required(perms.CAP_STUDENTS_MANAGE)
def student_approval_bulk(request):
    ids = request.POST.getlist("student_ids")
    action = request.POST.get("bulk_action")
    note = (request.POST.get("note") or "").strip()
    done = 0
    for sid in ids:
        student = User.objects.filter(pk=sid).select_related("profile").first()
        if not student:
            continue
        try:
            if action == "approve":
                approval_service.approve(student, actor=request.user, note=note or "Bulk approve.")
                done += 1
            elif action == "reject":
                approval_service.reject(student, actor=request.user,
                                        note=note or "Bulk reject.")
                done += 1
        except approval_service.ApprovalError:
            continue
    messages.success(request, f"Bulk {action}: {done} student(s).")
    return redirect("platform_admin:student_approvals")

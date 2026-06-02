"""Student registration approval gate — state transitions + audit trail.

Every status change goes through here so a ``StudentApprovalEvent`` is always
written. Admin/teacher/staff accounts are exempt (never blocked).
"""
from __future__ import annotations

from django.db import transaction
from django.utils import timezone

from .models import (
    APPROVAL_APPROVED,
    APPROVAL_PENDING_ADMIN,
    APPROVAL_PENDING_EMAIL,
    APPROVAL_REJECTED,
    APPROVAL_SUSPENDED,
    Profile,
    StudentApprovalEvent,
)


class ApprovalError(Exception):
    pass


def _profile(user) -> Profile | None:
    return getattr(user, "profile", None)


def is_approved(user) -> bool:
    if user is None or not getattr(user, "is_authenticated", False):
        return False
    p = _profile(user)
    return bool(p and p.is_approved_student)


def needs_admin_approval(user) -> bool:
    """True for an authenticated student currently blocked by the gate."""
    if user is None or not getattr(user, "is_authenticated", False):
        return False
    p = _profile(user)
    return bool(p and p.needs_admin_approval)


def _event(*, user, actor, old, new, action, note="", ip=None, ua="", metadata=None):
    return StudentApprovalEvent.objects.create(
        user=user, actor=actor, old_status=old or "", new_status=new or "",
        action=action, note=note or "", ip_address=ip,
        user_agent=(ua or "")[:400], metadata=metadata or {},
    )


@transaction.atomic
def record_registration(user, *, ip=None, user_agent="", suspicious_flags=None,
                        suspicious_score=0):
    """Set a freshly-registered student to pending and write the audit row.

    Staff/teacher/admin are auto-approved (never gated)."""
    p = _profile(user)
    if p is None:
        return None
    old = p.approval_status
    p.registration_ip = ip
    p.registration_user_agent = (user_agent or "")[:400]
    p.suspicious_flags = list(suspicious_flags or [])
    p.suspicious_score = int(suspicious_score or 0)
    if p.is_staff_or_privileged:
        p.approval_status = APPROVAL_APPROVED
    else:
        p.approval_status = APPROVAL_PENDING_EMAIL
    p.save(update_fields=[
        "approval_status", "registration_ip", "registration_user_agent",
        "suspicious_flags", "suspicious_score", "updated_at",
    ])
    _event(user=user, actor=None, old=old, new=p.approval_status,
           action="registered", ip=ip, ua=user_agent,
           metadata={"suspicious_flags": p.suspicious_flags})
    return p


@transaction.atomic
def mark_email_verified(user):
    """Advance pending_email_verification → pending_admin_approval."""
    p = _profile(user)
    if p is None or p.is_staff_or_privileged:
        return p
    if p.approval_status == APPROVAL_PENDING_EMAIL:
        old = p.approval_status
        p.approval_status = APPROVAL_PENDING_ADMIN
        p.save(update_fields=["approval_status", "updated_at"])
        _event(user=user, actor=None, old=old, new=p.approval_status,
               action="email_verified")
    return p


@transaction.atomic
def approve(user, *, actor, note=""):
    p = _profile(user)
    if p is None:
        raise ApprovalError("No profile.")
    old = p.approval_status
    p.approval_status = APPROVAL_APPROVED
    p.admin_approved_by = actor
    p.admin_approved_at = timezone.now()
    if note:
        p.approval_note = note
    p.save(update_fields=[
        "approval_status", "admin_approved_by", "admin_approved_at",
        "approval_note", "updated_at",
    ])
    action = "reactivated" if old in (APPROVAL_SUSPENDED, APPROVAL_REJECTED) else "approved"
    _event(user=user, actor=actor, old=old, new=p.approval_status, action=action, note=note)
    return p


@transaction.atomic
def reject(user, *, actor, note):
    if not (note or "").strip():
        raise ApprovalError("A note is required when rejecting.")
    p = _profile(user)
    if p is None:
        raise ApprovalError("No profile.")
    old = p.approval_status
    p.approval_status = APPROVAL_REJECTED
    p.admin_rejected_by = actor
    p.admin_rejected_at = timezone.now()
    p.approval_note = note
    p.save(update_fields=[
        "approval_status", "admin_rejected_by", "admin_rejected_at",
        "approval_note", "updated_at",
    ])
    _event(user=user, actor=actor, old=old, new=p.approval_status, action="rejected", note=note)
    return p


@transaction.atomic
def suspend(user, *, actor, note):
    if not (note or "").strip():
        raise ApprovalError("A note is required when suspending.")
    p = _profile(user)
    if p is None:
        raise ApprovalError("No profile.")
    old = p.approval_status
    p.approval_status = APPROVAL_SUSPENDED
    p.approval_note = note
    p.save(update_fields=["approval_status", "approval_note", "updated_at"])
    _event(user=user, actor=actor, old=old, new=p.approval_status, action="suspended", note=note)
    return p


@transaction.atomic
def add_note(user, *, actor, note):
    if not (note or "").strip():
        raise ApprovalError("Note text cannot be empty.")
    p = _profile(user)
    if p is None:
        raise ApprovalError("No profile.")
    _event(user=user, actor=actor, old=p.approval_status, new=p.approval_status,
           action="note_added", note=note)
    return p

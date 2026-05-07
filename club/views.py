from datetime import timedelta

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db.models import Count
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST

from .models import ClubEvent, ClubRSVP


@login_required
def event_list(request):
    tab = (request.GET.get("tab") or "upcoming").strip().lower()
    now = timezone.now()

    qs = ClubEvent.objects.filter(is_published=True)
    if tab == "past":
        qs = qs.filter(starts_at__lt=now).order_by("-starts_at")
    else:
        tab = "upcoming"
        qs = qs.filter(starts_at__gte=now).order_by("starts_at")

    events = list(qs)
    going_counts = {
        row["event_id"]: row["c"]
        for row in (
            ClubRSVP.objects.filter(event__in=events, status="going")
            .values("event_id")
            .annotate(c=Count("id"))
        )
    }
    rsvps = {
        r.event_id: r
        for r in ClubRSVP.objects.filter(user=request.user, event__in=events)
    }
    for e in events:
        e.my_rsvp = rsvps.get(e.id)
        e.going_count = going_counts.get(e.id, 0)

    return render(request, "club/list.html", {
        "events": events,
        "tab": tab,
        "is_subscribed": request.user.profile.is_subscribed,
    })


@login_required
def event_detail(request, pk):
    if not request.user.profile.is_subscribed:
        messages.warning(request, "Subscribe to join the English Club.")
        return redirect("subscribe")

    event = get_object_or_404(ClubEvent, pk=pk, is_published=True)
    my_rsvp = ClubRSVP.objects.filter(event=event, user=request.user).first()

    can_see_link = False
    if my_rsvp and my_rsvp.status == "going":
        can_see_link = timezone.now() >= (event.starts_at - timedelta(hours=24))

    return render(request, "club/detail.html", {
        "event": event,
        "my_rsvp": my_rsvp,
        "can_see_link": can_see_link,
        "now_utc": timezone.now(),
    })


@login_required
@require_POST
def rsvp(request, pk):
    if not request.user.profile.is_subscribed:
        messages.warning(request, "Subscribe to join the English Club.")
        return redirect("subscribe")

    event = get_object_or_404(ClubEvent, pk=pk, is_published=True)
    status = (request.POST.get("status") or "going").strip().lower()
    if status not in ("going", "maybe", "cancelled"):
        status = "going"

    existing = ClubRSVP.objects.filter(event=event, user=request.user).first()
    already_going = bool(existing and existing.status == "going")

    if status == "going" and event.is_full and not already_going:
        messages.error(request, "This event is full.")
        return redirect("club_event", pk=event.pk)

    rsvp_obj, _ = ClubRSVP.objects.get_or_create(event=event, user=request.user)
    rsvp_obj.status = status
    rsvp_obj.save(update_fields=["status", "updated_at"])

    messages.success(request, "RSVP updated.")
    return redirect("club_event", pk=event.pk)

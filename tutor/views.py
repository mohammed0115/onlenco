from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from .models import TutorConversation, TutorMessage
from .services import chat


def _require_subscription(request):
    if request.user.profile.is_subscribed:
        return None
    messages.warning(request, "Subscribe to chat with the AI tutor.")
    return redirect("subscribe")


@login_required
def conversation_list(request):
    locked = _require_subscription(request)
    if locked:
        return locked

    conversations = TutorConversation.objects.filter(user=request.user)
    return render(request, "tutor/list.html", {"conversations": conversations})


@login_required
@require_POST
def new_conversation(request):
    locked = _require_subscription(request)
    if locked:
        return locked

    topic = (request.POST.get("topic") or "").strip()
    conv = TutorConversation.objects.create(user=request.user, topic=topic)
    return redirect("tutor_detail", pk=conv.pk)


@login_required
def conversation_detail(request, pk):
    locked = _require_subscription(request)
    if locked:
        return locked

    conv = get_object_or_404(TutorConversation, pk=pk, user=request.user)
    return render(request, "tutor/detail.html", {"conversation": conv})


@login_required
@require_POST
def send_message(request, pk):
    locked = _require_subscription(request)
    if locked:
        return locked

    conv = get_object_or_404(TutorConversation, pk=pk, user=request.user)
    text = (request.POST.get("message") or "").strip()
    if not text:
        messages.error(request, "Message cannot be empty.")
        return redirect("tutor_detail", pk=conv.pk)

    TutorMessage.objects.create(conversation=conv, role="user", content=text)

    if not conv.title:
        conv.title = " ".join(text.split()[:8])[:200]
        conv.save(update_fields=["title"])

    reply = chat(conv, text)
    TutorMessage.objects.create(conversation=conv, role="assistant", content=reply)

    return redirect("tutor_detail", pk=conv.pk)

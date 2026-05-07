from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.http import Http404
from django.shortcuts import get_object_or_404, redirect, render

from accounts.models import CEFR_CHOICES

from .models import CATEGORY_CHOICES, Book


@login_required
def book_list(request):
    level = (request.GET.get("level") or "").strip()
    category = (request.GET.get("category") or "").strip()

    qs = Book.objects.filter(is_published=True)
    if level:
        qs = qs.filter(level=level)
    if category:
        qs = qs.filter(category=category)

    paginator = Paginator(qs, 12)
    page_obj = paginator.get_page(request.GET.get("page") or 1)

    return render(request, "library/list.html", {
        "page_obj": page_obj,
        "level": level,
        "category": category,
        "levels": [c[0] for c in CEFR_CHOICES],
        "categories": CATEGORY_CHOICES,
        "is_subscribed": request.user.profile.is_subscribed,
    })


@login_required
def book_detail(request, pk):
    if not request.user.profile.is_subscribed:
        messages.warning(request, "Subscribe to read from the library.")
        return redirect("subscribe")

    book = get_object_or_404(Book, pk=pk, is_published=True)

    chapter = None
    if not book.pdf:
        chapters = list(book.chapters.all())
        if not chapters:
            raise Http404("Book has no content")
        chapter_id = (request.GET.get("chapter") or "").strip()
        if chapter_id:
            chapter = next((c for c in chapters if str(c.id) == chapter_id), None)
        chapter = chapter or chapters[0]
    else:
        chapters = []

    return render(request, "library/detail.html", {
        "book": book,
        "chapters": chapters,
        "chapter": chapter,
    })


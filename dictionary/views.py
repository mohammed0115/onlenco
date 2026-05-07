from django.contrib.auth.decorators import login_required
from django.shortcuts import render

from .models import DictionaryEntry
from .services import _detect_lang, ai_lookup, search


@login_required
def dictionary_view(request):
    q = (request.GET.get("q") or "").strip()
    ai_entry = None
    results = []

    if not q:
        popular = DictionaryEntry.objects.order_by("-lookup_count", "english")[:12]
        return render(request, "dictionary/dictionary.html", {"q": q, "popular": popular})

    results = search(q, "auto")
    if not results:
        lang_hint = _detect_lang(q)
        ai_entry = ai_lookup(q, lang_hint)
        if ai_entry:
            results = [ai_entry]

    return render(request, "dictionary/dictionary.html", {
        "q": q,
        "results": results,
        "ai_entry": ai_entry,
    })


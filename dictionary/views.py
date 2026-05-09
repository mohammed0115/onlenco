from django.contrib.auth.decorators import login_required
from django.shortcuts import render

from .models import DictionaryEntry
from .services import _detect_lang, ai_lookup, search


def _credit_vocabulary(user) -> None:
    """Credit one vocabulary lookup to today's snapshot. Best-effort."""
    try:
        from motivation.services import activity_collector
        snap = activity_collector.collect_daily_activity(user)
        snap.vocabulary_words_learned = (snap.vocabulary_words_learned or 0) + 1
        snap.save(update_fields=["vocabulary_words_learned", "updated_at"])
    except Exception:
        import logging
        logging.getLogger(__name__).exception("dictionary: vocab credit failed")


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

    if results and request.user.is_authenticated:
        _credit_vocabulary(request.user)

    return render(request, "dictionary/dictionary.html", {
        "q": q,
        "results": results,
        "ai_entry": ai_entry,
    })


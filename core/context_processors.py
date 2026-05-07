from django.utils import translation

from .translations import DICT


def site_context(request):
    """Adds language helpers and the translation dictionary to every template.

    We use a flat dict keyed by tokens like `hero.title1` with `en` / `ar`
    values. Exposes a `t(key)` helper plus `lang` / `dir` flags for
    templates.
    """
    lang = translation.get_language() or "en"
    if lang.startswith("ar"):
        lang = "ar"
    else:
        lang = "en"

    def t(key):
        entry = DICT.get(key)
        if not entry:
            return key
        return entry.get(lang) or entry.get("en") or key

    return {
        "lang": lang,
        "dir": "rtl" if lang == "ar" else "ltr",
        "t": t,
        "T": DICT,  # raw dict for advanced lookups in templates
    }

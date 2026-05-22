"""Core middleware."""
from django.utils import translation


class QueryStringLanguageMiddleware:
    """Honour ``?hl=ar`` / ``?hl=en`` so each language is reachable at a
    stable, crawlable URL — this is exactly what the per-page ``hreflang``
    tags point at.

    The site otherwise switches language via a cookie (set-language POST);
    there are no ``/ar/`` ``/en/`` URL prefixes. This middleware runs
    after ``LocaleMiddleware`` so an explicit ``?hl=`` wins over the
    cookie for that request.
    """

    SUPPORTED = {"ar", "en"}

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        hl = (request.GET.get("hl") or "").strip().lower()
        if hl in self.SUPPORTED:
            translation.activate(hl)
            request.LANGUAGE_CODE = hl
        return self.get_response(request)

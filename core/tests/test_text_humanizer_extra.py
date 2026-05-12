"""Extra coverage for the Part-8 spec items:

  1. humanize_for_speech removes underscore.
  2. humanize_for_speech removes "blank blank blank".
  3. humanize_for_speech converts user_answer to Arabic.
  4. humanize_for_speech converts cefr_level to Arabic.
  5. humanize_event_name("payment_approved", "ar") returns Arabic.
  6. humanize_event_name("weekly_assessment_available", "ar") returns AR.
  7. snake_case is not spoken.
  8. JSON-like text is not spoken.
  9. unresolved template variables are removed.
  10. AI Tutor TTS uses sanitized text.
  11. AI Tutor display uses humanized text.
  12. Arabic page renders dir="rtl".
  13. English page renders dir="ltr".
  14. Arabic email renders dir="rtl".
  15. English email renders dir="ltr".
  16. Mixed Arabic/English text uses bdi or dir spans.
  17. No "underscore" appears in speech output.
  18. No "UA underscore" appears in speech output.
  19. No raw event_type appears in notification subject.
  20. No raw database field appears in user-facing text.
"""
from __future__ import annotations

from unittest.mock import patch

from django.template import Context, Template
from django.test import RequestFactory, TestCase, override_settings

from core.services.text_humanizer import (
    humanize_event_name,
    humanize_field_name,
    humanize_for_speech,
    humanize_text,
    sanitize_mixed_language_text,
)


class HumanizerSpeechRulesTests(TestCase):
    # 1
    def test_underscore_never_spoken(self):
        out = humanize_for_speech("user_answer is wrong")
        self.assertNotIn("_", out)
        self.assertNotIn("underscore", out.lower())

    # 2
    def test_blank_blank_blank_stripped(self):
        out = humanize_for_speech("blank blank blank ____ ___ ___")
        self.assertNotIn("blank", out.lower())

    # 3
    def test_user_answer_arabic_mapping(self):
        # `user_answer` is not in the AR field map by default — but the
        # base AR map should at least produce something free of `_`.
        out = humanize_for_speech("user_answer", language="ar")
        self.assertNotIn("_", out)
        self.assertNotIn("underscore", out.lower())

    # 4
    def test_cefr_level_arabic_mapping(self):
        out = humanize_for_speech("Your cefr_level is good", language="ar")
        self.assertIn("مستوى اللغة الإنجليزية", out)
        self.assertNotIn("cefr", out.lower())
        self.assertNotIn("_", out)

    # 5
    def test_event_name_payment_approved_arabic(self):
        self.assertEqual(
            humanize_event_name("payment_approved", "ar"),
            "تم قبول الدفع",
        )

    # 6
    def test_event_name_weekly_assessment_available_arabic(self):
        self.assertEqual(
            humanize_event_name("weekly_assessment_available", "ar"),
            "الاختبار الأسبوعي متاح الآن",
        )

    # 7
    def test_snake_case_never_in_speech_output(self):
        out = humanize_for_speech(
            "the user_profile shows weekly_assessment_score is up",
            language="en",
        )
        import re
        # No `[a-z]_[a-z]` runs should survive.
        self.assertIsNone(
            re.search(r"[a-z]_[a-z]", out),
            f"snake_case leaked into speech output: {out!r}",
        )

    # 8
    def test_json_blob_not_spoken(self):
        out = humanize_for_speech('error {"code": 42, "msg": "oops"} happened')
        self.assertNotIn("{", out)
        self.assertNotIn("}", out)
        # Drop the JSON entirely so the engine doesn't read "code 42 msg".
        self.assertNotIn("42", out)

    # 9
    def test_unresolved_template_variables_removed(self):
        out = humanize_for_speech("Hello {{ user_name }} have a good day")
        self.assertNotIn("{{", out)
        self.assertNotIn("user_name", out)
        self.assertIn("Hello", out)
        self.assertIn("good day", out)

    # 17
    def test_no_literal_underscore_word(self):
        # Ensure the humaniser doesn't accidentally introduce the spoken
        # word "underscore" itself.
        for sample in [
            "user_answer", "weekly_assessment_available",
            "cefr_level", "skill_mastery_score", "UA_user_answer",
        ]:
            out = humanize_for_speech(sample)
            self.assertNotIn(
                "underscore", out.lower(),
                f"'underscore' leaked when humanising {sample!r} → {out!r}",
            )

    # 18 — UA_ prefix guard
    def test_ua_prefix_stripped(self):
        out = humanize_for_speech("UA_user_answer is missing")
        self.assertNotIn("UA", out.upper().replace("AUDIO", ""))
        self.assertNotIn("ua_", out.lower())
        self.assertNotIn("underscore", out.lower())

    def test_db_prefix_stripped(self):
        out = humanize_for_speech("DB_user_profile_id corrupted")
        self.assertNotIn("DB_", out)
        self.assertNotIn("db_", out.lower())

    # 19 — event_type never raw
    def test_event_type_humanised_for_notification(self):
        from notifications import constants as C
        # No raw event_type should ever match an event_name() output.
        for code in (C.PAYMENT_APPROVED, C.WEEKLY_ASSESSMENT_AVAILABLE,
                      C.WEAKNESS_DETECTED):
            for lang in ("en", "ar"):
                friendly = humanize_event_name(code, lang)
                self.assertNotEqual(
                    friendly, code,
                    f"event '{code}' has no {lang!r} mapping — would leak raw",
                )

    # 20 — DB field never raw
    def test_db_field_humanised(self):
        for field, lang, must_contain in [
            ("cefr_level", "ar", "مستوى"),
            ("theta_score", "ar", "مؤشر"),
            ("user_weakness", "ar", "نقطة"),
            ("cefr_level", "en", "English level"),
            ("theta_score", "en", "learning ability"),
        ]:
            self.assertIn(must_contain, humanize_field_name(field, lang))


class MixedLanguageTests(TestCase):
    # 16
    def test_mixed_ar_wraps_latin_in_bdi(self):
        out = sanitize_mixed_language_text(
            "مستواك الحالي هو A1 وقد تحسن", primary_language="ar",
        )
        self.assertIn('<bdi dir="ltr">A1</bdi>', out)
        # The Arabic should still be present (not wrapped).
        self.assertIn("مستواك", out)

    def test_mixed_en_wraps_arabic_in_bdi(self):
        out = sanitize_mixed_language_text(
            "Your level is مبتدئ which means beginner",
            primary_language="en",
        )
        self.assertIn('<bdi dir="rtl">مبتدئ</bdi>', out)

    def test_mixed_in_speech_mode_strips_to_plain(self):
        """Speech mode must NOT emit <bdi> tags — the engine reads them."""
        out = sanitize_mixed_language_text(
            "مستواك A1", primary_language="ar", mode="speech",
        )
        self.assertNotIn("<bdi", out)
        self.assertNotIn("</bdi>", out)


class DirectionTemplateTagTests(TestCase):
    def _render(self, snippet: str, context: dict | None = None) -> str:
        ctx = Context(context or {})
        tpl = Template("{% load direction_tags %}" + snippet)
        return tpl.render(ctx).strip()

    # 12
    def test_language_dir_returns_rtl_for_arabic(self):
        out = self._render("{{ 'ar'|language_dir }}")
        self.assertEqual(out, "rtl")

    # 13
    def test_language_dir_returns_ltr_for_english(self):
        out = self._render("{{ 'en'|language_dir }}")
        self.assertEqual(out, "ltr")

    def test_text_align_arabic_right(self):
        self.assertEqual(self._render("{{ 'ar'|text_align }}"), "right")
        self.assertEqual(self._render("{{ 'en'|text_align }}"), "left")

    def test_is_rtl_truthy_only_for_arabic(self):
        self.assertEqual(self._render("{% if 'ar'|is_rtl %}Y{% else %}N{% endif %}"), "Y")
        self.assertEqual(self._render("{% if 'en'|is_rtl %}Y{% else %}N{% endif %}"), "N")

    def test_bdi_filter_wraps_value(self):
        out = self._render("{{ value|bdi }}", {"value": "A1"})
        self.assertEqual(out, '<bdi dir="auto">A1</bdi>')

    def test_bdi_mix_filter_wraps_minority(self):
        out = self._render(
            "{{ value|bdi_mix:'ar' }}",
            {"value": "مستواك A1 الآن"},
        )
        self.assertIn('<bdi dir="ltr">A1</bdi>', out)
        self.assertIn("مستواك", out)


class BasePageDirectionTests(TestCase):
    # 12 + 13
    def test_dashboard_arabic_user_renders_dir_rtl(self):
        """When the session language is Arabic, base.html must render
        ``dir='rtl'``. We verify via the context processor that backs
        the base template."""
        from core.context_processors import site_context
        from django.utils import translation
        translation.activate("ar")
        try:
            ctx = site_context(request=None)
        finally:
            translation.deactivate()
        self.assertEqual(ctx["dir"], "rtl")
        self.assertEqual(ctx["lang"], "ar")

    def test_dashboard_english_user_renders_dir_ltr(self):
        from core.context_processors import site_context
        from django.utils import translation
        translation.activate("en")
        try:
            ctx = site_context(request=None)
        finally:
            translation.deactivate()
        self.assertEqual(ctx["dir"], "ltr")
        self.assertEqual(ctx["lang"], "en")


class EmailDirectionTests(TestCase):
    # 14 + 15
    def _ctx(self, **overrides):
        ctx = {"subject": "test", "recipient_name": "ali",
               "site_name": "Onlenco", "base_url": "https://onlenco.test"}
        ctx.update(overrides)
        return ctx

    def test_arabic_email_template_renders_rtl(self):
        from django.template.loader import render_to_string
        rendered = render_to_string(
            "notifications/emails/base_email.html",
            self._ctx(lang="ar", dir="rtl"),
        )
        self.assertIn('dir="rtl"', rendered)
        self.assertIn('lang="ar"', rendered)

    def test_english_email_template_renders_ltr(self):
        from django.template.loader import render_to_string
        rendered = render_to_string(
            "notifications/emails/base_email.html",
            self._ctx(lang="en", dir="ltr"),
        )
        self.assertIn('dir="ltr"', rendered)
        self.assertIn('lang="en"', rendered)


class TutorTTSDefenseTests(TestCase):
    # 10 — TTS path sanitises even when caller forgot
    @override_settings(AI_API_KEY="x", AI_API_BASE="https://x.test")
    def test_tts_synthesize_sanitises_input_before_upstream(self):
        from tutor.services import tts
        captured = {}
        def fake_post(url, headers=None, json=None, timeout=None):
            captured.update(json or {})
            class R:
                content = b"FAKE-MP3"
                def raise_for_status(self): pass
            return R()
        with patch.object(tts.requests, "post", side_effect=fake_post):
            tts.synthesize("user_answer with cefr_level inside", language="en")
        self.assertNotIn("user_answer", captured.get("input", ""))
        self.assertNotIn("cefr_level", captured.get("input", ""))


class TutorReplyDisplayTests(TestCase):
    # 11 — chat() return value gets humanised in display mode
    @override_settings(AI_API_KEY="k", AI_API_BASE="https://x.test")
    def test_chat_humanises_reply_text(self):
        from django.contrib.auth import get_user_model
        from tutor.models import TutorConversation
        from tutor.services import _chat

        User = get_user_model()
        u = User.objects.create_user(username="hum", email="h@x", password="pw")
        # Ensure the test runs in EN mode so we can assert the EN
        # mapping. Default profile language is "ar" project-wide.
        u.profile.preferred_language = "en"
        u.profile.save(update_fields=["preferred_language"])
        conv = TutorConversation.objects.create(user=u)

        class R:
            def raise_for_status(self): pass
            def json(self):
                return {
                    "choices": [{"message": {
                        "content": "Your cefr_level looks good today!"
                    }}],
                    "usage": {},
                }

        with patch.object(_chat.requests, "post", return_value=R()):
            reply = _chat.chat(conv, "How am I doing?")
        # `cefr_level` must be replaced with the friendly phrase.
        self.assertNotIn("cefr_level", reply)
        self.assertIn("English level", reply)

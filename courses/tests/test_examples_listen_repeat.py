"""Examples "listen and repeat": natural per-item TTS clips + 3s gap.

Covers the cached TTS endpoint (provider mocked) and the shared template
markup/JS that drives the behavior for EVERY course/lesson (no hardcoded IDs).
"""
from unittest import mock

from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.template.loader import get_template
from django.test import TestCase, override_settings
from django.urls import reverse


User = get_user_model()


def _src() -> str:
    return open(get_template("courses/lesson_step.html").origin.name, encoding="utf-8").read()


class ExamplesSettingsTests(TestCase):
    def test_gap_default_is_1_5_seconds(self):
        self.assertEqual(getattr(settings, "EXAMPLES_PAUSE_SECONDS", None), 1.5)

    def test_rate_default_is_0_8(self):
        self.assertEqual(getattr(settings, "EXAMPLES_AUDIO_PLAYBACK_RATE", None), 0.8)


class ExamplesTemplateTests(TestCase):
    def setUp(self):
        self.src = _src()

    def test_examples_and_vocab_share_one_sequencer(self):
        # Both steps mark their container/items with the same unified hooks.
        self.assertIn("data-listen-repeat", self.src)
        self.assertIn("data-lr-item", self.src)
        self.assertIn('data-pause="{{ examples_pause_seconds|default:1.5 }}"', self.src)
        self.assertIn('data-rate="{{ examples_audio_rate|default:0.8 }}"', self.src)
        self.assertIn("data-tts-url=", self.src)

    def test_plays_natural_clips_per_item_with_gap(self):
        self.assertIn("new Audio(url)", self.src)           # natural clip played
        self.assertIn("playbackRate = rate", self.src)      # slowed, natural voice

    def test_no_repeat_now_indicator(self):
        # The "Next… (repeat now)" transition chip was removed across all courses.
        self.assertNotIn("repeat now", self.src)
        self.assertNotIn("كرّر الآن", self.src)

    def test_vocabulary_words_are_tappable_items(self):
        self.assertIn("onlenco-vocab__word", self.src)
        self.assertIn("listen_repeat_groups", self.src)

    def test_intro_step_also_uses_word_by_word(self):
        # Intro and Vocabulary share the listen_repeat branch (word-by-word).
        self.assertIn("vocabulary", "intro vocabulary")
        self.assertIn('group.kind == "words"', self.src)

    def test_no_hardcoded_course_or_lesson_ids(self):
        for needle in ("lessons/130", "courses/17", "lesson == 130"):
            self.assertNotIn(needle, self.src)


class ListeningSpeakingHaveAudioTests(TestCase):
    """Regression: the listening + speaking steps used to render silent
    (no Listen button) because the view only built audio items for
    intro/vocabulary/examples/dialogue. Every step with script text must
    now offer a playable clip. Reuses the seeded beginner course/lesson 1
    so the drip gate / A0 world allow the first lesson to open."""

    @classmethod
    def setUpTestData(cls):
        from courses.models import CourseEnrollment
        from courses.tests.test_super_lesson_01 import (
            _get_lesson_quiz, _make_student, _seed_all,
        )
        _seed_all()
        cls.course, cls.lesson, _ = _get_lesson_quiz()
        cls.student = _make_student("snd-listen")
        CourseEnrollment.objects.get_or_create(user=cls.student, course=cls.course)

    def _body(self, step):
        from courses.tests.test_super_lesson_01 import _login
        r = _login(self.student).get(
            reverse("courses:lesson_step", args=[self.course.pk, self.lesson.pk, step]),
            HTTP_HOST="127.0.0.1")
        self.assertEqual(r.status_code, 200, step)
        return r.content.decode()

    def test_listening_step_offers_audio(self):
        # The Listen button only renders when the step produced playable
        # audio items (example_lines or listen_repeat_groups).
        body = self._body("listening")
        self.assertIn("data-lr-start", body)
        self.assertIn("data-listen-repeat", body)

    def test_speaking_step_offers_audio(self):
        body = self._body("speaking")
        self.assertIn("data-lr-start", body)
        self.assertIn("data-listen-repeat", body)


class VocabularyParserTests(TestCase):
    def test_splits_topics_by_semicolon_and_pulls_words(self):
        from courses.views import _parse_vocabulary
        groups = _parse_vocabulary(
            "Today's vocabulary: Family (mother, father, sister); "
            "10 pets (cat, dog, fish). Listen and repeat each word."
        )
        self.assertEqual(len(groups), 2)
        self.assertEqual(groups[0]["kind"], "words")
        self.assertIn("Family", groups[0]["label"])
        self.assertEqual(groups[0]["words"], ["mother", "father", "sister"])
        self.assertEqual(groups[1]["words"], ["cat", "dog", "fish"])

    def test_comma_list_after_colon_without_parens(self):
        from courses.views import _parse_vocabulary
        groups = _parse_vocabulary(
            "Today's vocabulary: 16 daily objects: laptop, charger, glasses, "
            "water bottle, ID, sneakers. Listen and repeat each word."
        )
        self.assertEqual(len(groups), 1)
        self.assertEqual(
            groups[0]["words"],
            ["laptop", "charger", "glasses", "water bottle", "ID", "sneakers"],
        )

    def test_intro_words_in_parens_and_closing_sentence(self):
        from courses.views import _parse_vocabulary
        groups = _parse_vocabulary(
            "In this lesson, you will learn Possessive adjectives "
            "(my, your, his, her, its, our, their); this / that. Let's begin."
        )
        self.assertEqual(groups[0]["kind"], "words")
        self.assertEqual(groups[0]["words"],
                         ["my", "your", "his", "her", "its", "our", "their"])
        # The closing sentence stays whole (a spoken line, not chopped into words).
        self.assertEqual(groups[1]["kind"], "line")

    def test_plain_sentence_without_list_is_one_line(self):
        from courses.views import _parse_vocabulary
        groups = _parse_vocabulary("Just a plain sentence")
        self.assertEqual(groups[0]["kind"], "line")
        self.assertEqual(groups[0]["text"], "Just a plain sentence")


@override_settings(AXES_ENABLED=False)
class TtsClipEndpointTests(TestCase):
    def setUp(self):
        cache.clear()
        self.user = User.objects.create_user(username="tts@x.com", email="tts@x.com", password="pw")
        self.client.force_login(self.user)
        self.url = reverse("courses:lesson_tts_clip")

    def test_rejects_empty_text(self):
        resp = self.client.post(self.url, data="{}", content_type="application/json")
        self.assertEqual(resp.status_code, 400)

    def test_returns_natural_clip_url_and_reuses_file(self):
        import base64
        import tempfile
        fake = {"audio_b64": base64.b64encode(b"MP3DATA").decode(), "format": "mp3", "voice": "alloy"}
        with tempfile.TemporaryDirectory() as media, override_settings(MEDIA_ROOT=media):
            with mock.patch(
                "subscriptions.services.library_audio_service.synthesize_chunk",
                return_value=fake,
            ) as synth:
                r1 = self.client.post(self.url, data='{"text": "Sudanese"}',
                                      content_type="application/json")
                self.assertEqual(r1.status_code, 200)
                self.assertTrue(r1.json()["url"].endswith(".mp3"))
                # Second identical request reuses the stored file — no 2nd synth.
                r2 = self.client.post(self.url, data='{"text": "Sudanese"}',
                                      content_type="application/json")
                self.assertEqual(r2.status_code, 200)
            self.assertEqual(synth.call_count, 1)

    def test_handles_tts_unavailable(self):
        with mock.patch(
            "subscriptions.services.library_audio_service.synthesize_chunk",
            return_value={"audio_b64": "", "format": "", "voice": ""},
        ):
            resp = self.client.post(self.url, data='{"text": "Hi there."}',
                                    content_type="application/json")
        self.assertEqual(resp.status_code, 502)

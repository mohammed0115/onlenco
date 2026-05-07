from django.test import TestCase

from dictionary.models import DictionaryEntry
from dictionary.services import _detect_lang, search


class DictionaryServiceTests(TestCase):
    def test_lang_detect_arabic(self):
        self.assertEqual(_detect_lang("مرحبا"), "ar")

    def test_lang_detect_english(self):
        self.assertEqual(_detect_lang("hello"), "en")

    def test_search_with_no_entries_returns_empty(self):
        result = search("nonexistentword")
        self.assertEqual(list(result), [])

    def test_search_finds_entry(self):
        DictionaryEntry.objects.create(english="apple", arabic="تفاحة")
        result = search("apple")
        self.assertEqual(list(result)[0].english, "apple")

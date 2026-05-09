from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from dictionary.models import DictionaryEntry
from motivation.models import LearnerActivitySnapshot

User = get_user_model()


@override_settings(AXES_ENABLED=False)
class DictionaryVocabularyCreditTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username="d@x.com", email="d@x.com", password="pw"
        )
        self.client.login(username="d@x.com", password="pw")
        DictionaryEntry.objects.create(
            english="cat", arabic="قطة", pos="noun", source="curated",
        )

    def test_lookup_credits_vocab_word(self):
        self.client.get(reverse("dictionary"), {"q": "cat"})
        snap = LearnerActivitySnapshot.objects.get(
            user=self.user, date=timezone.localdate()
        )
        self.assertEqual(snap.vocabulary_words_learned, 1)

    def test_empty_query_does_not_credit(self):
        self.client.get(reverse("dictionary"))
        self.assertFalse(
            LearnerActivitySnapshot.objects
            .filter(user=self.user)
            .exists()
            and LearnerActivitySnapshot.objects.get(user=self.user).vocabulary_words_learned > 0
        )

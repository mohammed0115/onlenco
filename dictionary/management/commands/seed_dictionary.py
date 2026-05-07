from django.core.management.base import BaseCommand

from dictionary.models import DictionaryEntry


class Command(BaseCommand):
    help = "Seed the dictionary with common Arabic/English words."

    def handle(self, *args, **opts):
        words = [
            ("hello", "مرحبا", "phrase", "Hello! How are you?", "مرحبا! كيف حالك؟"),
            ("goodbye", "وداعا", "phrase", "Goodbye! See you later.", "وداعا! أراك لاحقا."),
            ("please", "من فضلك", "phrase", "Please help me.", "من فضلك ساعدني."),
            ("thank you", "شكرا", "phrase", "Thank you very much.", "شكرا جزيلا."),
            ("you're welcome", "على الرحب والسعة", "phrase", "You're welcome!", "على الرحب والسعة!"),
            ("sorry", "آسف", "phrase", "I'm sorry.", "أنا آسف."),
            ("excuse me", "عفوا", "phrase", "Excuse me, can I ask a question?", "عفوا، هل يمكنني أن أسأل سؤالا؟"),
            ("good morning", "صباح الخير", "phrase", "Good morning!", "صباح الخير!"),
            ("good evening", "مساء الخير", "phrase", "Good evening!", "مساء الخير!"),
            ("good night", "تصبح على خير", "phrase", "Good night!", "تصبح على خير!"),
            ("how are you", "كيف حالك", "phrase", "How are you today?", "كيف حالك اليوم؟"),
            ("I don't understand", "لا أفهم", "phrase", "I don't understand, please repeat.", "لا أفهم، من فضلك أعد."),

            ("water", "ماء", "noun", "I need water.", "أحتاج ماء."),
            ("food", "طعام", "noun", "The food is delicious.", "الطعام لذيذ."),
            ("bread", "خبز", "noun", "I bought bread.", "اشتريت خبزا."),
            ("tea", "شاي", "noun", "I like tea.", "أحب الشاي."),
            ("coffee", "قهوة", "noun", "This coffee is hot.", "هذه القهوة ساخنة."),
            ("book", "كتاب", "noun", "This book is interesting.", "هذا الكتاب ممتع."),
            ("pen", "قلم", "noun", "I need a pen.", "أحتاج قلما."),
            ("table", "طاولة", "noun", "The table is clean.", "الطاولة نظيفة."),
            ("chair", "كرسي", "noun", "Sit on the chair.", "اجلس على الكرسي."),
            ("room", "غرفة", "noun", "My room is small.", "غرفتي صغيرة."),
            ("school", "مدرسة", "noun", "The school is near.", "المدرسة قريبة."),
            ("teacher", "معلم", "noun", "The teacher is kind.", "المعلم لطيف."),
            ("student", "طالب", "noun", "The student is ready.", "الطالب مستعد."),
            ("question", "سؤال", "noun", "I have a question.", "لدي سؤال."),
            ("answer", "جواب", "noun", "The answer is correct.", "الجواب صحيح."),

            ("read", "يقرأ", "verb", "I read every day.", "أنا أقرأ كل يوم."),
            ("write", "يكتب", "verb", "I write in my notebook.", "أنا أكتب في دفتري."),
            ("speak", "يتحدث", "verb", "I speak English.", "أنا أتحدث الإنجليزية."),
            ("listen", "يستمع", "verb", "Listen to the lesson.", "استمع إلى الدرس."),
            ("learn", "يتعلم", "verb", "We learn new words.", "نحن نتعلم كلمات جديدة."),
            ("understand", "يفهم", "verb", "I understand the idea.", "أنا أفهم الفكرة."),
            ("help", "يساعد", "verb", "Can you help me?", "هل يمكنك مساعدتي؟"),
            ("go", "يذهب", "verb", "I go to school.", "أنا أذهب إلى المدرسة."),
            ("come", "يأتي", "verb", "Please come here.", "من فضلك تعال هنا."),
            ("want", "يريد", "verb", "I want to practice.", "أريد أن أتدرب."),
            ("need", "يحتاج", "verb", "I need time.", "أحتاج وقتا."),
            ("like", "يحب", "verb", "I like this book.", "أنا أحب هذا الكتاب."),
            ("study", "يدرس", "verb", "I study at night.", "أنا أدرس في الليل."),
            ("eat", "يأكل", "verb", "I eat breakfast.", "أنا آكل الفطور."),
            ("drink", "يشرب", "verb", "I drink water.", "أنا أشرب الماء."),

            ("good", "جيد", "adj", "Good job!", "عمل جيد!"),
            ("bad", "سيئ", "adj", "This is a bad idea.", "هذه فكرة سيئة."),
            ("big", "كبير", "adj", "This room is big.", "هذه الغرفة كبيرة."),
            ("small", "صغير", "adj", "This book is small.", "هذا الكتاب صغير."),
            ("new", "جديد", "adj", "This is a new lesson.", "هذا درس جديد."),
            ("old", "قديم", "adj", "This is an old book.", "هذا كتاب قديم."),
            ("fast", "سريع", "adj", "He is fast.", "هو سريع."),
            ("slow", "بطيء", "adj", "The internet is slow.", "الإنترنت بطيء."),
            ("easy", "سهل", "adj", "This is easy.", "هذا سهل."),
            ("difficult", "صعب", "adj", "This is difficult.", "هذا صعب."),

            ("slowly", "ببطء", "adv", "Please speak slowly.", "من فضلك تحدث ببطء."),
            ("quickly", "بسرعة", "adv", "Walk quickly.", "امش بسرعة."),
            ("always", "دائما", "adv", "I always practice.", "أنا دائما أتدرب."),
            ("sometimes", "أحيانا", "adv", "I sometimes read at night.", "أحيانا أقرأ في الليل."),
            ("today", "اليوم", "adv", "Today I study.", "اليوم أدرس."),

            ("on", "على", "prep", "The book is on the table.", "الكتاب على الطاولة."),
            ("in", "في", "prep", "She is in the room.", "هي في الغرفة."),
            ("between", "بين", "prep", "The chair is between the table and the door.", "الكرسي بين الطاولة والباب."),
        ]

        created = 0
        for en, ar, pos, ex_en, ex_ar in words:
            obj, was_created = DictionaryEntry.objects.get_or_create(
                english=en,
                arabic=ar,
                defaults={
                    "pos": pos,
                    "example_en": ex_en,
                    "example_ar": ex_ar,
                    "source": "curated",
                },
            )
            if was_created:
                created += 1

        self.stdout.write(self.style.SUCCESS(
            f"Dictionary: {created} entry(s) added, {DictionaryEntry.objects.count()} total."
        ))

"""Bilingual content for the public SEO landing pages.

These pages exist purely so the platform is indexable for its target
keywords (AI English tutor, English placement test, English for
beginners, English speaking practice, pricing). They are public — no
login wall — and all share ``templates/core/seo_landing.html``.

Each page is a plain dict so the views stay thin and the copy lives in
one reviewable place. Strings are kept as ``{"en": ..., "ar": ...}`` so
the template can render whichever the active language selects.
"""


def _b(en: str, ar: str) -> dict:
    """Tiny helper — a bilingual string pair."""
    return {"en": en, "ar": ar}


SEO_PAGES = {
    # ------------------------------------------------------------------
    "ai-english-tutor": {
        "key": "ai-english-tutor",
        "url_name": "seo_ai_english_tutor",
        "seo_title": _b(
            "AI English Tutor — Practice Speaking Anytime | Onlenco Academy",
            "معلّم إنجليزي بالذكاء الاصطناعي — تدرّب على المحادثة في أي وقت | أكاديمية Onlenco",
        ),
        "seo_description": _b(
            "Talk to an AI English tutor on Onlenco Academy. The AI tutor "
            "corrects your mistakes, builds your confidence and is available "
            "24/7 — designed for Sudanese students learning English.",
            "تحدّث مع معلّم إنجليزي بالذكاء الاصطناعي على أكاديمية Onlenco. "
            "يصحّح المعلّم الذكي أخطاءك ويبني ثقتك ومتاح طوال اليوم — "
            "مصمّم للطلاب السودانيين الذين يتعلّمون الإنجليزية.",
        ),
        "h1": _b(
            "Your AI English tutor, available any time",
            "معلّمك للإنجليزية بالذكاء الاصطناعي، متاح في أي وقت",
        ),
        "intro": _b(
            "Onlenco Academy gives every learner a personal AI English tutor. "
            "Hold a real conversation by voice, get instant correction on "
            "grammar and pronunciation, and practise English without fear of "
            "judgement — at your own pace, in Arabic and English.",
            "تمنحك أكاديمية Onlenco معلّماً شخصياً للإنجليزية بالذكاء "
            "الاصطناعي. أجرِ محادثة حقيقية بالصوت، واحصل على تصحيح فوري "
            "للقواعد والنطق، وتدرّب على الإنجليزية دون خوف — بالسرعة التي "
            "تناسبك، بالعربية والإنجليزية.",
        ),
        "sections": [
            {
                "icon": "mic",
                "title": _b("Real voice conversations", "محادثات صوتية حقيقية"),
                "body": _b(
                    "Speak naturally with the AI tutor and hear it reply. "
                    "Every session is a safe place to practise English out loud.",
                    "تحدّث بشكل طبيعي مع المعلّم الذكي واستمع إلى ردّه. كل "
                    "جلسة مكان آمن للتدرّب على الإنجليزية بصوت عالٍ.",
                ),
            },
            {
                "icon": "spell-check",
                "title": _b("Instant mistake correction", "تصحيح فوري للأخطاء"),
                "body": _b(
                    "The AI tutor catches grammar and pronunciation mistakes "
                    "the moment you make them and explains the fix simply.",
                    "يلتقط المعلّم الذكي أخطاء القواعد والنطق فور حدوثها "
                    "ويشرح التصحيح ببساطة.",
                ),
            },
            {
                "icon": "clock",
                "title": _b("Available 24/7", "متاح طوال اليوم"),
                "body": _b(
                    "No appointments, no waiting. Open Onlenco and practise "
                    "English whenever it suits you — morning or night.",
                    "لا مواعيد ولا انتظار. افتح Onlenco وتدرّب على الإنجليزية "
                    "متى ما يناسبك — صباحاً أو مساءً.",
                ),
            },
            {
                "icon": "trending-up",
                "title": _b("Tracks your progress", "يتابع تقدّمك"),
                "body": _b(
                    "Your tutor remembers your weak points and feeds them "
                    "back into your daily learning plan.",
                    "يتذكّر معلّمك نقاط ضعفك ويعيدها إلى خطة تعلّمك اليومية.",
                ),
            },
        ],
        "faq": [
            {
                "q": _b(
                    "What is an AI English tutor?",
                    "ما هو المعلّم الإنجليزي بالذكاء الاصطناعي؟",
                ),
                "a": _b(
                    "It is an AI-powered teacher you can talk to in English. "
                    "On Onlenco Academy it listens, replies by voice, corrects "
                    "your mistakes and adapts to your level.",
                    "هو معلّم مدعوم بالذكاء الاصطناعي يمكنك التحدّث معه "
                    "بالإنجليزية. في أكاديمية Onlenco يستمع ويردّ بالصوت "
                    "ويصحّح أخطاءك ويتكيّف مع مستواك.",
                ),
            },
            {
                "q": _b(
                    "Is the AI tutor good for Sudanese students?",
                    "هل المعلّم الذكي مناسب للطلاب السودانيين؟",
                ),
                "a": _b(
                    "Yes. Onlenco Academy explains everything in Arabic and "
                    "English and supports local payment in Sudanese pounds.",
                    "نعم. تشرح أكاديمية Onlenco كل شيء بالعربية والإنجليزية "
                    "وتدعم الدفع المحلي بالجنيه السوداني.",
                ),
            },
        ],
        "show_plans": False,
    },
    # ------------------------------------------------------------------
    "english-for-beginners": {
        "key": "english-for-beginners",
        "url_name": "seo_english_for_beginners",
        "seo_title": _b(
            "English for Beginners — Start from Zero | Onlenco Academy",
            "الإنجليزية للمبتدئين — ابدأ من الصفر | أكاديمية Onlenco",
        ),
        "seo_description": _b(
            "Learn English for beginners on Onlenco Academy. An A0 path that "
            "starts from zero — letters, words and first sentences — explained "
            "in Arabic for Sudanese students.",
            "تعلّم الإنجليزية للمبتدئين على أكاديمية Onlenco. مسار A0 يبدأ "
            "من الصفر — الحروف والكلمات والجمل الأولى — مشروح بالعربية "
            "للطلاب السودانيين.",
        ),
        "h1": _b(
            "Learn English from zero — built for absolute beginners",
            "تعلّم الإنجليزية من الصفر — مصمّم للمبتدئين تماماً",
        ),
        "intro": _b(
            "Never studied English before? Onlenco Academy has a dedicated A0 "
            "path that starts with the alphabet and your first words, all "
            "explained in Arabic. Step by step, you move from zero towards "
            "real conversation with an AI tutor at your side.",
            "لم تدرس الإنجليزية من قبل؟ تمتلك أكاديمية Onlenco مساراً "
            "مخصّصاً A0 يبدأ بالحروف الأبجدية وكلماتك الأولى، مشروحاً "
            "بالكامل بالعربية. خطوة بخطوة تنتقل من الصفر نحو محادثة حقيقية "
            "ومعلّم ذكي بجانبك.",
        ),
        "sections": [
            {
                "icon": "sprout",
                "title": _b("A true A0 start", "بداية A0 حقيقية"),
                "body": _b(
                    "Begin with letters, sounds and everyday words — no prior "
                    "English needed.",
                    "ابدأ بالحروف والأصوات والكلمات اليومية — دون أي معرفة "
                    "سابقة بالإنجليزية.",
                ),
            },
            {
                "icon": "languages",
                "title": _b("Explained in Arabic", "مشروح بالعربية"),
                "body": _b(
                    "Every new idea is introduced in Arabic first, so nothing "
                    "feels confusing.",
                    "تُقدَّم كل فكرة جديدة بالعربية أولاً، حتى لا يبدو أي "
                    "شيء مربكاً.",
                ),
            },
            {
                "icon": "calendar-check",
                "title": _b("A small daily plan", "خطة يومية صغيرة"),
                "body": _b(
                    "Short daily lessons keep you consistent without feeling "
                    "overwhelmed.",
                    "دروس يومية قصيرة تحافظ على انتظامك دون الشعور بالإرهاق.",
                ),
            },
            {
                "icon": "graduation-cap",
                "title": _b("A clear path A0 → C2", "مسار واضح من A0 إلى C2"),
                "body": _b(
                    "When you are ready, the same platform carries you all the "
                    "way to advanced English.",
                    "عندما تصبح جاهزاً، تأخذك المنصة نفسها حتى المستوى "
                    "المتقدّم في الإنجليزية.",
                ),
            },
        ],
        "faq": [
            {
                "q": _b(
                    "Can I learn English if I know nothing at all?",
                    "هل أستطيع تعلّم الإنجليزية إذا كنت لا أعرف شيئاً؟",
                ),
                "a": _b(
                    "Yes. The Onlenco Academy A0 path is made for complete "
                    "beginners and starts from the alphabet.",
                    "نعم. مسار A0 في أكاديمية Onlenco مصمّم للمبتدئين تماماً "
                    "ويبدأ من الحروف الأبجدية.",
                ),
            },
            {
                "q": _b(
                    "Do I need to take the placement test first?",
                    "هل يجب أن أؤدّي اختبار تحديد المستوى أولاً؟",
                ),
                "a": _b(
                    "No. Beginners can skip the test and start directly on the "
                    "A0 path.",
                    "لا. يمكن للمبتدئين تخطّي الاختبار والبدء مباشرة في مسار "
                    "A0.",
                ),
            },
        ],
        "show_plans": False,
    },
    # ------------------------------------------------------------------
    "english-speaking-practice": {
        "key": "english-speaking-practice",
        "url_name": "seo_english_speaking_practice",
        "seo_title": _b(
            "English Speaking Practice — Talk with AI | Onlenco Academy",
            "تدريب المحادثة بالإنجليزية — تحدّث مع الذكاء الاصطناعي | أكاديمية Onlenco",
        ),
        "seo_description": _b(
            "Practise English speaking on Onlenco Academy. Hold real voice "
            "conversations with an AI tutor, fix your pronunciation and gain "
            "confidence — speaking practice for Sudanese students.",
            "تدرّب على المحادثة بالإنجليزية على أكاديمية Onlenco. أجرِ "
            "محادثات صوتية حقيقية مع معلّم ذكي، وحسّن نطقك واكتسب الثقة — "
            "تدريب محادثة للطلاب السودانيين.",
        ),
        "h1": _b(
            "English speaking practice that builds real confidence",
            "تدريب على المحادثة بالإنجليزية يبني ثقة حقيقية",
        ),
        "intro": _b(
            "The fastest way to speak English is to speak it. Onlenco Academy "
            "lets you practise speaking out loud every day with an AI tutor "
            "that listens, replies and corrects your pronunciation — without "
            "the fear of making mistakes in front of people.",
            "أسرع طريقة للتحدّث بالإنجليزية هي أن تتحدّثها. تتيح لك أكاديمية "
            "Onlenco التدرّب على التحدّث بصوت عالٍ كل يوم مع معلّم ذكي "
            "يستمع ويردّ ويصحّح نطقك — دون الخوف من الخطأ أمام الناس.",
        ),
        "sections": [
            {
                "icon": "messages-square",
                "title": _b("Daily conversation topics", "مواضيع محادثة يومية"),
                "body": _b(
                    "Practise real-life topics — work, travel, study — at your "
                    "level.",
                    "تدرّب على مواضيع من الحياة الواقعية — العمل والسفر "
                    "والدراسة — بحسب مستواك.",
                ),
            },
            {
                "icon": "volume-2",
                "title": _b("Pronunciation feedback", "ملاحظات على النطق"),
                "body": _b(
                    "Hear how words should sound and get feedback on your own "
                    "pronunciation.",
                    "استمع إلى الطريقة الصحيحة لنطق الكلمات واحصل على "
                    "ملاحظات حول نطقك.",
                ),
            },
            {
                "icon": "shield-check",
                "title": _b("A judgement-free space", "مساحة خالية من الإحراج"),
                "body": _b(
                    "No classroom pressure — make mistakes freely and learn "
                    "from each one.",
                    "لا ضغط الفصل الدراسي — أخطئ بحرّية وتعلّم من كل خطأ.",
                ),
            },
            {
                "icon": "flame",
                "title": _b("Build a speaking streak", "حافظ على سلسلة التحدّث"),
                "body": _b(
                    "Short daily speaking sessions turn practice into a habit.",
                    "جلسات تحدّث يومية قصيرة تحوّل التدريب إلى عادة.",
                ),
            },
        ],
        "faq": [
            {
                "q": _b(
                    "How do I practise speaking English alone?",
                    "كيف أتدرّب على التحدّث بالإنجليزية بمفردي؟",
                ),
                "a": _b(
                    "With Onlenco Academy you practise speaking with an AI "
                    "tutor — it replies by voice so you are never practising "
                    "in silence.",
                    "مع أكاديمية Onlenco تتدرّب على التحدّث مع معلّم ذكي "
                    "يردّ بالصوت، فلا تتدرّب في صمت أبداً.",
                ),
            },
            {
                "q": _b(
                    "Will it help my pronunciation?",
                    "هل سيساعد ذلك في تحسين نطقي؟",
                ),
                "a": _b(
                    "Yes. The AI tutor gives feedback on pronunciation so you "
                    "improve a little every session.",
                    "نعم. يقدّم المعلّم الذكي ملاحظات على النطق لتتحسّن "
                    "قليلاً في كل جلسة.",
                ),
            },
        ],
        "show_plans": False,
    },
    # ------------------------------------------------------------------
    "placement-test": {
        "key": "placement-test",
        "url_name": "seo_placement_test",
        "seo_title": _b(
            "Free English Placement Test — Find Your Level | Onlenco Academy",
            "اختبار تحديد مستوى الإنجليزية المجاني — اعرف مستواك | أكاديمية Onlenco",
        ),
        "seo_description": _b(
            "Take a free English placement test on Onlenco Academy. Our AI "
            "test finds your CEFR level from A0 to C2 and builds a daily plan "
            "that fits you — for Sudanese students.",
            "أدِّ اختبار تحديد مستوى الإنجليزية مجاناً على أكاديمية Onlenco. "
            "يحدّد اختبارنا الذكي مستواك على سلّم CEFR من A0 إلى C2 ويبني "
            "خطة يومية تناسبك — للطلاب السودانيين.",
        ),
        "h1": _b(
            "Find your English level with a free placement test",
            "اعرف مستواك في الإنجليزية باختبار تحديد مستوى مجاني",
        ),
        "intro": _b(
            "Before you study, know exactly where you stand. The Onlenco "
            "Academy placement test uses AI-supported written and speaking "
            "questions to find your CEFR level — A0 to C2 — then turns the "
            "result into a personalised daily learning plan.",
            "قبل أن تبدأ الدراسة، اعرف موقعك بالضبط. يستخدم اختبار تحديد "
            "المستوى في أكاديمية Onlenco أسئلة كتابية وتحدّث مدعومة "
            "بالذكاء الاصطناعي لتحديد مستواك على سلّم CEFR — من A0 إلى C2 — "
            "ثم يحوّل النتيجة إلى خطة تعلّم يومية مخصّصة.",
        ),
        "sections": [
            {
                "icon": "brain",
                "title": _b("AI-supported questions", "أسئلة مدعومة بالذكاء الاصطناعي"),
                "body": _b(
                    "Written and speaking questions measure your real level "
                    "accurately.",
                    "أسئلة كتابية وتحدّث تقيس مستواك الحقيقي بدقّة.",
                ),
            },
            {
                "icon": "bar-chart-3",
                "title": _b("Clear CEFR result", "نتيجة CEFR واضحة"),
                "body": _b(
                    "Get a placement from A0 to C2 so you know exactly where "
                    "to start.",
                    "احصل على تحديد للمستوى من A0 إلى C2 لتعرف من أين تبدأ "
                    "بالضبط.",
                ),
            },
            {
                "icon": "calendar-check",
                "title": _b("A daily plan from your result", "خطة يومية من نتيجتك"),
                "body": _b(
                    "Your test result becomes a learning plan tailored to "
                    "your gaps.",
                    "تتحوّل نتيجة اختبارك إلى خطة تعلّم مفصّلة على ثغراتك.",
                ),
            },
            {
                "icon": "gift",
                "title": _b("Free to start", "ابدأ مجاناً"),
                "body": _b(
                    "Create an account and take the placement test at no cost.",
                    "أنشئ حساباً وأدِّ اختبار تحديد المستوى دون أي تكلفة.",
                ),
            },
        ],
        "faq": [
            {
                "q": _b(
                    "Is the placement test free?",
                    "هل اختبار تحديد المستوى مجاني؟",
                ),
                "a": _b(
                    "Yes. The Onlenco Academy placement test is free — just "
                    "create an account to begin.",
                    "نعم. اختبار تحديد المستوى في أكاديمية Onlenco مجاني — "
                    "ما عليك سوى إنشاء حساب للبدء.",
                ),
            },
            {
                "q": _b(
                    "What if I am a complete beginner?",
                    "ماذا لو كنت مبتدئاً تماماً؟",
                ),
                "a": _b(
                    "You can skip the test and start directly on the A0 "
                    "beginner path.",
                    "يمكنك تخطّي الاختبار والبدء مباشرة في مسار المبتدئين A0.",
                ),
            },
        ],
        "show_plans": False,
    },
    # ------------------------------------------------------------------
    "pricing": {
        "key": "pricing",
        "url_name": "seo_pricing",
        "seo_title": _b(
            "Pricing & Subscriptions — Affordable Plans | Onlenco Academy",
            "الأسعار والاشتراكات — خطط ميسورة | أكاديمية Onlenco",
        ),
        "seo_description": _b(
            "See Onlenco Academy pricing. Affordable English learning plans "
            "with an AI tutor, daily plan and full lessons — pay locally in "
            "Sudanese pounds with Bankak, Fawry or O-Cash.",
            "اطّلع على أسعار أكاديمية Onlenco. خطط ميسورة لتعلّم الإنجليزية "
            "مع معلّم ذكي وخطة يومية ودروس كاملة — ادفع محلياً بالجنيه "
            "السوداني عبر بنكك أو فوري أو أوكاش.",
        ),
        "h1": _b(
            "Simple, affordable plans for learning English",
            "خطط بسيطة وميسورة لتعلّم الإنجليزية",
        ),
        "intro": _b(
            "Onlenco Academy keeps pricing simple and affordable for Sudanese "
            "learners. Every plan includes the AI tutor, full lessons and "
            "quizzes, and a personalised daily plan — and you pay locally in "
            "Sudanese pounds.",
            "تُبقي أكاديمية Onlenco الأسعار بسيطة وميسورة للمتعلّمين "
            "السودانيين. تشمل كل خطة المعلّم الذكي والدروس والاختبارات "
            "الكاملة وخطة يومية مخصّصة — وتدفع محلياً بالجنيه السوداني.",
        ),
        "sections": [
            {
                "icon": "wallet",
                "title": _b("Local payment in SDG", "دفع محلي بالجنيه"),
                "body": _b(
                    "Pay with Bankak, Fawry or O-Cash — no international card "
                    "needed.",
                    "ادفع عبر بنكك أو فوري أو أوكاش — دون الحاجة إلى بطاقة "
                    "دولية.",
                ),
            },
            {
                "icon": "gift",
                "title": _b("Start free", "ابدأ مجاناً"),
                "body": _b(
                    "Begin with the free placement test before you choose a "
                    "plan.",
                    "ابدأ باختبار تحديد المستوى المجاني قبل اختيار خطة.",
                ),
            },
            {
                "icon": "check-circle",
                "title": _b("Everything included", "كل شيء مشمول"),
                "body": _b(
                    "Every paid plan unlocks all lessons, quizzes and the "
                    "daily plan.",
                    "تفتح كل خطة مدفوعة جميع الدروس والاختبارات والخطة "
                    "اليومية.",
                ),
            },
        ],
        "faq": [
            {
                "q": _b(
                    "How can I pay for Onlenco Academy in Sudan?",
                    "كيف أدفع لأكاديمية Onlenco في السودان؟",
                ),
                "a": _b(
                    "You can pay locally in Sudanese pounds using Bankak, "
                    "Fawry or O-Cash.",
                    "يمكنك الدفع محلياً بالجنيه السوداني عبر بنكك أو فوري أو "
                    "أوكاش.",
                ),
            },
            {
                "q": _b(
                    "Is there a free option?",
                    "هل يوجد خيار مجاني؟",
                ),
                "a": _b(
                    "Yes. You can create an account and take the placement "
                    "test for free before subscribing.",
                    "نعم. يمكنك إنشاء حساب وأداء اختبار تحديد المستوى مجاناً "
                    "قبل الاشتراك.",
                ),
            },
        ],
        "show_plans": True,
    },
}


def get_seo_page(key: str):
    """Return the page dict for ``key`` or ``None`` if unknown."""
    return SEO_PAGES.get(key)

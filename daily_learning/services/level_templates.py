"""Fallback bilingual daily-plan templates for A1, A2, B1, B2, C1, C2.

These are used when the content selector cannot find suitable
AdaptiveExercise rows in the question bank AND AI is unavailable / capped.
They are intentionally short and skill-focused (vocabulary +
grammar tip + speaking + quiz + writing/reading). The plan generator
picks one template per (user, date) deterministically.

Each TopicTemplate carries 5–7 items so the resulting plan satisfies
the 5–8 item spec.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable


@dataclass(frozen=True)
class TopicItem:
    item_type: str
    title_en: str
    title_ar: str
    instructions_en: str
    instructions_ar: str
    content_text: str = ""
    question: str = ""
    options: tuple = ()
    correct_answer: str = ""
    explanation_en: str = ""
    explanation_ar: str = ""
    skill: str = "mixed"
    difficulty_score: float = 0.3
    estimated_minutes: int = 2


@dataclass(frozen=True)
class TopicTemplate:
    slug: str
    cefr_level: str
    title_en: str
    title_ar: str
    description_en: str
    description_ar: str
    items: tuple


# --------------------- A1 -----------------------
A1_TOPICS = (
    TopicTemplate(
        slug="daily_routine",
        cefr_level="A1",
        title_en="Talk about your daily routine",
        title_ar="تحدث عن روتينك اليومي",
        description_en="Use simple verbs to describe your day.",
        description_ar="استخدم أفعالاً بسيطة لوصف يومك.",
        items=(
            TopicItem(
                item_type="vocabulary",
                title_en="Today's words",
                title_ar="كلمات اليوم",
                instructions_en="Read each word and the example sentence.",
                instructions_ar="اقرأ كل كلمة والجملة المثال.",
                content_text="wake up — يستيقظ\nwork — يعمل\nstudy — يدرس\nExample: I wake up at 6.",
                skill="vocabulary",
                difficulty_score=0.2,
            ),
            TopicItem(
                item_type="grammar_tip",
                title_en="Grammar: I go / She goes",
                title_ar="قواعد: I go / She goes",
                instructions_en="With he/she/it we add -s to the verb.",
                instructions_ar="مع he/she/it نضيف -s إلى الفعل.",
                content_text="I work. → She works.\nI study. → He studies.",
                skill="grammar",
                difficulty_score=0.3,
            ),
            TopicItem(
                item_type="reading",
                title_en="Read about Sara's morning",
                title_ar="اقرأ عن صباح سارة",
                instructions_en="Read the short paragraph slowly.",
                instructions_ar="اقرأ الفقرة القصيرة ببطء.",
                content_text="Sara wakes up at 6. She drinks tea. Then she goes to work. She likes her job.",
                skill="reading",
                difficulty_score=0.3,
            ),
            TopicItem(
                item_type="quiz",
                title_en="Choose the right verb",
                title_ar="اختر الفعل الصحيح",
                instructions_en="Pick the form that fits.",
                instructions_ar="اختر التصريف المناسب.",
                question="She ____ at 6.",
                options=("wake up", "wakes up", "waking up"),
                correct_answer="wakes up",
                explanation_en="With \"she\" we add -s.",
                explanation_ar="مع \"she\" نضيف -s.",
                skill="grammar",
                difficulty_score=0.3,
            ),
            TopicItem(
                item_type="speaking",
                title_en="Speak about your morning",
                title_ar="تحدث عن صباحك",
                instructions_en="Say two sentences about what you do every morning.",
                instructions_ar="قل جملتين عما تفعله كل صباح.",
                content_text="Start with: \"Every morning, I …\"",
                skill="speaking",
                difficulty_score=0.4,
                estimated_minutes=3,
            ),
        ),
    ),
    TopicTemplate(
        slug="family",
        cefr_level="A1",
        title_en="Talk about your family",
        title_ar="تحدث عن عائلتك",
        description_en="Learn family words and simple sentences.",
        description_ar="تعلم كلمات العائلة وجمل بسيطة.",
        items=(
            TopicItem(
                item_type="vocabulary",
                title_en="Family words",
                title_ar="كلمات العائلة",
                instructions_en="Read each word with its translation.",
                instructions_ar="اقرأ كل كلمة مع ترجمتها.",
                content_text="mother — أم\nfather — أب\nbrother — أخ\nsister — أخت",
                skill="vocabulary",
                difficulty_score=0.2,
            ),
            TopicItem(
                item_type="grammar_tip",
                title_en="Possessive: my, your, his, her",
                title_ar="ضمائر الملكية: my, your, his, her",
                instructions_en="Use \"my\" to talk about your own family.",
                instructions_ar="استخدم \"my\" للحديث عن عائلتك.",
                content_text="This is my mother. This is my brother.",
                skill="grammar",
                difficulty_score=0.3,
            ),
            TopicItem(
                item_type="quiz",
                title_en="Choose the right word",
                title_ar="اختر الكلمة الصحيحة",
                instructions_en="Pick the missing word.",
                instructions_ar="اختر الكلمة الناقصة.",
                question="This is ____ sister.",
                options=("my", "I", "me"),
                correct_answer="my",
                explanation_en="\"my\" shows possession.",
                explanation_ar="\"my\" تعبر عن الملكية.",
                skill="grammar",
                difficulty_score=0.3,
            ),
            TopicItem(
                item_type="speaking",
                title_en="Talk about your family",
                title_ar="تحدث عن عائلتك",
                instructions_en="Say two sentences about people in your family.",
                instructions_ar="قل جملتين عن أفراد عائلتك.",
                content_text="Use: \"I have …\" or \"This is my …\"",
                skill="speaking",
                difficulty_score=0.4,
                estimated_minutes=3,
            ),
            TopicItem(
                item_type="writing",
                title_en="Write one sentence",
                title_ar="اكتب جملة واحدة",
                instructions_en="Write one sentence about one family member.",
                instructions_ar="اكتب جملة واحدة عن أحد أفراد عائلتك.",
                content_text="Example: My brother is a doctor.",
                skill="writing",
                difficulty_score=0.4,
            ),
        ),
    ),
)

# --------------------- A2 -----------------------
A2_TOPICS = (
    TopicTemplate(
        slug="weekend_plans",
        cefr_level="A2",
        title_en="Talk about your weekend plans",
        title_ar="تحدث عن خططك في عطلة الأسبوع",
        description_en="Use simple future to talk about plans.",
        description_ar="استخدم المستقبل البسيط للحديث عن الخطط.",
        items=(
            TopicItem(
                item_type="vocabulary",
                title_en="Useful words",
                title_ar="كلمات مفيدة",
                instructions_en="Read each word and its meaning.",
                instructions_ar="اقرأ كل كلمة ومعناها.",
                content_text="visit — يزور\nplan — يخطط\nweekend — عطلة الأسبوع\nfriend — صديق",
                skill="vocabulary",
                difficulty_score=0.3,
            ),
            TopicItem(
                item_type="grammar_tip",
                title_en="Grammar: going to (plans)",
                title_ar="قواعد: going to (للخطط)",
                instructions_en="Use \"going to\" + verb for future plans.",
                instructions_ar="استخدم \"going to\" + فعل للحديث عن خطط مستقبلية.",
                content_text="I am going to visit my friend. She is going to study.",
                skill="grammar",
                difficulty_score=0.4,
            ),
            TopicItem(
                item_type="reading",
                title_en="Sara's weekend",
                title_ar="عطلة أسبوع سارة",
                instructions_en="Read the short text.",
                instructions_ar="اقرأ النص القصير.",
                content_text="This weekend Sara is going to visit her grandmother. They are going to cook together. On Sunday she is going to study English.",
                skill="reading",
                difficulty_score=0.4,
            ),
            TopicItem(
                item_type="quiz",
                title_en="Pick the correct verb",
                title_ar="اختر الفعل الصحيح",
                instructions_en="Choose the right form.",
                instructions_ar="اختر التصريف الصحيح.",
                question="I ____ going to study tonight.",
                options=("am", "is", "are"),
                correct_answer="am",
                explanation_en="With \"I\" we use \"am\".",
                explanation_ar="مع \"I\" نستخدم \"am\".",
                skill="grammar",
                difficulty_score=0.4,
            ),
            TopicItem(
                item_type="speaking",
                title_en="Your weekend plan",
                title_ar="خطتك للعطلة",
                instructions_en="Say two things you are going to do this weekend.",
                instructions_ar="قل شيئين ستفعلهما في هذه العطلة.",
                content_text="Start with: \"This weekend I am going to …\"",
                skill="speaking",
                difficulty_score=0.5,
                estimated_minutes=3,
            ),
        ),
    ),
)

# --------------------- B1 -----------------------
B1_TOPICS = (
    TopicTemplate(
        slug="learning_goals",
        cefr_level="B1",
        title_en="Practice talking about your goals",
        title_ar="تدرّب على الحديث عن أهدافك",
        description_en="Use intermediate vocabulary about learning.",
        description_ar="استخدم مفردات متوسطة للحديث عن التعلم.",
        items=(
            TopicItem(
                item_type="vocabulary",
                title_en="Useful words",
                title_ar="كلمات مفيدة",
                instructions_en="Read the words and their meanings.",
                instructions_ar="اقرأ الكلمات ومعانيها.",
                content_text="improve — يحسّن\npractice — يتدرّب\ngoal — هدف\nachieve — يحقق",
                skill="vocabulary",
                difficulty_score=0.5,
            ),
            TopicItem(
                item_type="reading",
                title_en="Why learning English matters",
                title_ar="لماذا يهم تعلم الإنجليزية",
                instructions_en="Read the paragraph and think about the main idea.",
                instructions_ar="اقرأ الفقرة وفكر في الفكرة الرئيسية.",
                content_text="Many people learn English to improve their careers. Others practice every day to achieve a personal goal — to travel, to read books, or to talk with friends online.",
                skill="reading",
                difficulty_score=0.5,
            ),
            TopicItem(
                item_type="writing",
                title_en="Write about your goal",
                title_ar="اكتب عن هدفك",
                instructions_en="Write three sentences about your goal in English.",
                instructions_ar="اكتب ثلاث جمل عن هدفك في الإنجليزية.",
                content_text="Try to use: improve, practice, goal.",
                skill="writing",
                difficulty_score=0.5,
                estimated_minutes=4,
            ),
            TopicItem(
                item_type="speaking",
                title_en="Why are you learning English?",
                title_ar="لماذا تتعلم الإنجليزية؟",
                instructions_en="Speak for 30 seconds about your reason.",
                instructions_ar="تحدث 30 ثانية عن سببك.",
                content_text="Use full sentences.",
                skill="speaking",
                difficulty_score=0.5,
                estimated_minutes=3,
            ),
            TopicItem(
                item_type="quiz",
                title_en="Choose the best word",
                title_ar="اختر الكلمة الأنسب",
                instructions_en="Fill the gap.",
                instructions_ar="املأ الفراغ.",
                question="I practice every day to ____ my English.",
                options=("improve", "improving", "improvement"),
                correct_answer="improve",
                explanation_en="After \"to\" we use the base verb.",
                explanation_ar="بعد \"to\" نستخدم الفعل في صورته الأساسية.",
                skill="grammar",
                difficulty_score=0.5,
            ),
        ),
    ),
)

# --------------------- B2 -----------------------
B2_TOPICS = (
    TopicTemplate(
        slug="opinion_remote_work",
        cefr_level="B2",
        title_en="Give an opinion about remote work",
        title_ar="أبدِ رأيك حول العمل عن بُعد",
        description_en="Use opinion phrases and conditional sentences.",
        description_ar="استخدم عبارات الرأي والجمل الشرطية.",
        items=(
            TopicItem(
                item_type="vocabulary",
                title_en="Opinion vocabulary",
                title_ar="مفردات الرأي",
                instructions_en="Learn phrases to express opinions.",
                instructions_ar="تعلم عبارات للتعبير عن الرأي.",
                content_text="in my opinion — في رأيي\nhowever — لكن\nas a result — نتيجةً لذلك\nargue — يجادل",
                skill="vocabulary",
                difficulty_score=0.6,
            ),
            TopicItem(
                item_type="reading",
                title_en="Remote work and productivity",
                title_ar="العمل عن بُعد والإنتاجية",
                instructions_en="Read and identify the writer's opinion.",
                instructions_ar="اقرأ وحدّد رأي الكاتب.",
                content_text="Many companies argue that remote work increases productivity. However, others believe that face-to-face meetings are essential. In my opinion, a balanced approach works best for most teams.",
                skill="reading",
                difficulty_score=0.6,
            ),
            TopicItem(
                item_type="writing",
                title_en="Express your opinion",
                title_ar="عبّر عن رأيك",
                instructions_en="Write 4–5 sentences. Use \"in my opinion\" and \"however\".",
                instructions_ar="اكتب 4-5 جمل. استخدم \"in my opinion\" و \"however\".",
                content_text="Topic: Is remote work good for everyone?",
                skill="writing",
                difficulty_score=0.6,
                estimated_minutes=5,
            ),
            TopicItem(
                item_type="speaking",
                title_en="Talk for one minute",
                title_ar="تحدث لمدة دقيقة",
                instructions_en="Speak for ~1 minute giving your view on remote work.",
                instructions_ar="تحدث حوالي دقيقة معبراً عن رأيك في العمل عن بُعد.",
                content_text="Try to use linking words.",
                skill="speaking",
                difficulty_score=0.6,
                estimated_minutes=3,
            ),
        ),
    ),
)

# --------------------- C1 -----------------------
C1_TOPICS = (
    TopicTemplate(
        slug="c1_professional_writing",
        cefr_level="C1",
        title_en="Refine your professional writing",
        title_ar="حسّن كتابتك المهنية",
        description_en="Use precise vocabulary and complex structures.",
        description_ar="استخدم مفردات دقيقة وتراكيب مركبة.",
        items=(
            TopicItem(
                item_type="vocabulary",
                title_en="Advanced vocabulary",
                title_ar="مفردات متقدمة",
                instructions_en="Study these high-register words.",
                instructions_ar="ادرس هذه الكلمات ذات المستوى العالي.",
                content_text="leverage — يستفيد من\nmitigate — يخفّف من\nstreamline — يبسّط\nstakeholder — صاحب مصلحة",
                skill="vocabulary",
                difficulty_score=0.8,
            ),
            TopicItem(
                item_type="reading",
                title_en="Article excerpt",
                title_ar="مقتطف من مقال",
                instructions_en="Read and note the connectors.",
                instructions_ar="اقرأ ولاحظ أدوات الربط.",
                content_text="Although the new policy was designed to streamline operations, several stakeholders raised concerns. To mitigate these, the team will leverage feedback from the pilot before full rollout.",
                skill="reading",
                difficulty_score=0.8,
            ),
            TopicItem(
                item_type="writing",
                title_en="Rewrite for clarity",
                title_ar="أعد الصياغة من أجل الوضوح",
                instructions_en="Rewrite this sentence in a clearer, more concise way.",
                instructions_ar="أعد كتابة هذه الجملة بشكل أوضح وأكثر اختصاراً.",
                content_text="\"Due to the fact that there were issues, the launch was delayed.\"",
                skill="writing",
                difficulty_score=0.8,
                estimated_minutes=5,
            ),
            TopicItem(
                item_type="speaking",
                title_en="Two-minute presentation",
                title_ar="عرض من دقيقتين",
                instructions_en="Talk for two minutes about a project you led.",
                instructions_ar="تحدث لمدة دقيقتين عن مشروع قُدته.",
                content_text="Aim for fluency, accuracy, and clear structure.",
                skill="speaking",
                difficulty_score=0.8,
                estimated_minutes=4,
            ),
        ),
    ),
    TopicTemplate(
        slug="c1_academic_argument",
        cefr_level="C1",
        title_en="Build an academic argument",
        title_ar="ابنِ حجّة أكاديمية",
        description_en="Practise hedged claims and evidence-based reasoning.",
        description_ar="تدرّب على ادعاءات محايدة ومبنية على الأدلة.",
        items=(
            TopicItem(
                item_type="vocabulary",
                title_en="Hedging language",
                title_ar="لغة التحفّظ",
                instructions_en="Learn phrases that soften claims in academic writing.",
                instructions_ar="تعلم عبارات تخفّف ادعاءاتك في الكتابة الأكاديمية.",
                content_text="arguably — قد يُقال\ntends to — يميل إلى\nlargely — إلى حد كبير\nconsiderable — كبير / ملحوظ",
                skill="vocabulary",
                difficulty_score=0.8,
            ),
            TopicItem(
                item_type="reading",
                title_en="Identify the thesis",
                title_ar="حدّد الأطروحة",
                instructions_en="Read and find the writer's main claim.",
                instructions_ar="اقرأ وحدّد الادعاء الرئيسي للكاتب.",
                content_text="The shift toward remote work, arguably the most significant labour-market change of the past decade, tends to favour workers with reliable infrastructure. While productivity has held up, considerable disparities have emerged between sectors.",
                skill="reading",
                difficulty_score=0.8,
            ),
            TopicItem(
                item_type="writing",
                title_en="Hedge an absolute claim",
                title_ar="خفّف ادعاءً قاطعاً",
                instructions_en="Rewrite the sentence using two hedging phrases.",
                instructions_ar="أعد كتابة الجملة باستخدام عبارتي تحفّظ.",
                content_text="\"Remote work is always better than office work.\"",
                skill="writing",
                difficulty_score=0.8,
                estimated_minutes=5,
            ),
            TopicItem(
                item_type="speaking",
                title_en="Argue both sides",
                title_ar="ناقش كلا الجانبين",
                instructions_en="Spend 90 seconds arguing one side, then 90 seconds the other.",
                instructions_ar="جادل لمدة 90 ثانية مع طرف ثم 90 ثانية مع الطرف الآخر.",
                content_text="Topic: Should universities prioritise online or in-person teaching?",
                skill="speaking",
                difficulty_score=0.8,
                estimated_minutes=5,
            ),
            TopicItem(
                item_type="quiz",
                title_en="Pick the most natural hedge",
                title_ar="اختر التعبير المحايد الأنسب",
                instructions_en="Choose the option a native academic writer would use.",
                instructions_ar="اختر التعبير الذي يستخدمه كاتب أكاديمي.",
                question="____ workers prefer flexible schedules.",
                options=("Largely", "Very much", "Totally"),
                correct_answer="Largely",
                explanation_en="\"Largely\" is the hedged academic choice; \"totally\" is too absolute.",
                explanation_ar="\"Largely\" خيار أكاديمي محايد؛ \"totally\" قاطع جداً.",
                skill="grammar",
                difficulty_score=0.8,
            ),
        ),
    ),
    TopicTemplate(
        slug="c1_meeting_register",
        cefr_level="C1",
        title_en="Switch register in meetings",
        title_ar="بدّل المستوى اللغوي في الاجتماعات",
        description_en="Move between formal and conversational tones.",
        description_ar="تنقّل بين الأسلوب الرسمي والمحادثة العادية.",
        items=(
            TopicItem(
                item_type="vocabulary",
                title_en="Formal ↔ informal pairs",
                title_ar="ثنائيات رسمي / غير رسمي",
                instructions_en="Match the formal version to its everyday equivalent.",
                instructions_ar="طابق الصيغة الرسمية بمقابلها اليومي.",
                content_text="formal — informal\ncommence — start\nendeavour — try\nrequire — need\nassist — help",
                skill="vocabulary",
                difficulty_score=0.8,
            ),
            TopicItem(
                item_type="reading",
                title_en="Email vs Slack",
                title_ar="بريد رسمي مقابل سلاك",
                instructions_en="Same message, two registers. Notice the differences.",
                instructions_ar="نفس الرسالة بمستويين. لاحظ الفروقات.",
                content_text="EMAIL: I would like to request a brief meeting to discuss the proposal.\nSLACK: Got time for a quick chat on the proposal?",
                skill="reading",
                difficulty_score=0.7,
            ),
            TopicItem(
                item_type="writing",
                title_en="Translate informal to formal",
                title_ar="حوّل من غير رسمي إلى رسمي",
                instructions_en="Rewrite for a formal email.",
                instructions_ar="أعد الكتابة لرسالة رسمية.",
                content_text="\"Hey, can you take a look and let me know what you think?\"",
                skill="writing",
                difficulty_score=0.8,
                estimated_minutes=4,
            ),
            TopicItem(
                item_type="speaking",
                title_en="Open a formal meeting",
                title_ar="افتتح اجتماعاً رسمياً",
                instructions_en="Speak the first 30 seconds of a formal meeting opening.",
                instructions_ar="انطق أول 30 ثانية من افتتاح اجتماع رسمي.",
                content_text="Use: \"Thank you all for joining today …\"",
                skill="speaking",
                difficulty_score=0.7,
                estimated_minutes=3,
            ),
        ),
    ),
    TopicTemplate(
        slug="c1_inversion_emphasis",
        cefr_level="C1",
        title_en="Use inversion for emphasis",
        title_ar="استخدم القلب للتأكيد",
        description_en="Practise structures like 'Not only …, but also …'.",
        description_ar="تدرّب على تراكيب مثل 'Not only …, but also …'.",
        items=(
            TopicItem(
                item_type="grammar_tip",
                title_en="Inversion patterns",
                title_ar="أنماط القلب",
                instructions_en="Notice how the auxiliary moves before the subject.",
                instructions_ar="لاحظ كيف ينتقل الفعل المساعد قبل الفاعل.",
                content_text="Not only does this approach save time, it also reduces cost.\nRarely have we seen such a strong response.",
                skill="grammar",
                difficulty_score=0.8,
            ),
            TopicItem(
                item_type="quiz",
                title_en="Choose the inverted form",
                title_ar="اختر صيغة القلب الصحيحة",
                instructions_en="Pick the structure that fits a formal speech.",
                instructions_ar="اختر التركيب الذي يناسب خطاباً رسمياً.",
                question="Not only ____ early, but he also volunteered to lead.",
                options=("did he arrive", "he arrived", "he did arrive"),
                correct_answer="did he arrive",
                explanation_en="After \"Not only\" we invert auxiliary + subject: did he arrive.",
                explanation_ar="بعد \"Not only\" نقلب الفعل المساعد والفاعل: did he arrive.",
                skill="grammar",
                difficulty_score=0.8,
            ),
            TopicItem(
                item_type="writing",
                title_en="Open a paragraph with inversion",
                title_ar="افتح فقرة بالقلب",
                instructions_en="Write one sentence starting with \"Rarely …\" or \"Not only …\".",
                instructions_ar="اكتب جملة تبدأ بـ \"Rarely …\" أو \"Not only …\".",
                content_text="Aim for a sentence you might find in an editorial.",
                skill="writing",
                difficulty_score=0.8,
                estimated_minutes=4,
            ),
            TopicItem(
                item_type="speaking",
                title_en="Deliver with emphasis",
                title_ar="انطق مع التشديد",
                instructions_en="Read your inverted sentence aloud twice — with rising stress on the inverted clause.",
                instructions_ar="اقرأ جملتك المقلوبة بصوت عالٍ مرتين — مع تشديد على الجزء المقلوب.",
                content_text="Inversion + stress = formal emphasis.",
                skill="speaking",
                difficulty_score=0.7,
                estimated_minutes=2,
            ),
        ),
    ),
)


# --------------------- C2 (distinct from C1) -----------------------
# C2 is "mastery" — content stretches register, idiom, and nuance
# rather than introducing new grammar. C2_TOPICS therefore curates
# its OWN topics rather than aliasing C1; otherwise an advanced
# learner would see Day-1 content again on Day-N.
C2_TOPICS = (
    TopicTemplate(
        slug="c2_nuance_synonyms",
        cefr_level="C2",
        title_en="Pick the right synonym",
        title_ar="اختر المرادف الأدق",
        description_en="Distinguish near-synonyms by connotation and register.",
        description_ar="ميّز بين المرادفات القريبة من حيث الدلالة والمستوى.",
        items=(
            TopicItem(
                item_type="vocabulary",
                title_en="Shades of \"important\"",
                title_ar="ظلال كلمة \"مهم\"",
                instructions_en="Notice how connotation shifts.",
                instructions_ar="لاحظ كيف يتغيّر المعنى الدلالي.",
                content_text="critical — يخصّ قراراً عاجلاً\npivotal — يشكّل نقطة تحوّل\nseminal — مؤسِّس فكرياً\nconsequential — كبير الأثر",
                skill="vocabulary",
                difficulty_score=0.9,
            ),
            TopicItem(
                item_type="quiz",
                title_en="Most precise word",
                title_ar="الكلمة الأدق",
                instructions_en="Which word fits a description of a foundational paper?",
                instructions_ar="ما الكلمة التي تصف بحثاً مؤسِّساً؟",
                question="Her 1972 paper is considered ____ in the field.",
                options=("seminal", "critical", "consequential"),
                correct_answer="seminal",
                explanation_en="\"Seminal\" is used for foundational works that influence a field.",
                explanation_ar="\"Seminal\" تُستخدم للأعمال المؤسِّسة التي تؤثّر في مجالها.",
                skill="vocabulary",
                difficulty_score=0.9,
            ),
            TopicItem(
                item_type="writing",
                title_en="Match the register",
                title_ar="طابق المستوى اللغوي",
                instructions_en="Replace each generic adjective with a precise synonym.",
                instructions_ar="استبدل كل صفة عامة بمرادف دقيق.",
                content_text="\"His important work changed everything.\"",
                skill="writing",
                difficulty_score=0.9,
                estimated_minutes=4,
            ),
            TopicItem(
                item_type="speaking",
                title_en="Recommend a book",
                title_ar="ارشِّح كتاباً",
                instructions_en="Speak for 90 seconds — pick a book and justify with three precise adjectives.",
                instructions_ar="تحدث 90 ثانية — اختر كتاباً وبرّر بثلاث صفات دقيقة.",
                content_text="Aim for variety; avoid repeating \"good\" or \"interesting\".",
                skill="speaking",
                difficulty_score=0.9,
                estimated_minutes=3,
            ),
        ),
    ),
    TopicTemplate(
        slug="c2_idioms_in_use",
        cefr_level="C2",
        title_en="Idioms that sound native",
        title_ar="تعابير تجعلك تبدو كأنك ناطق أصلي",
        description_en="Deploy idiomatic phrases without sounding clichéd.",
        description_ar="استخدم التعابير الاصطلاحية دون أن تبدو مبتذلاً.",
        items=(
            TopicItem(
                item_type="vocabulary",
                title_en="High-utility idioms",
                title_ar="تعابير عالية الفائدة",
                instructions_en="Pair each idiom with the situation it fits.",
                instructions_ar="طابق كل تعبير بالموقف المناسب له.",
                content_text="on the back foot — في موقف دفاعي\nat a crossroads — أمام مفترق طرق\ncut corners — يأخذ طرقاً مختصرة\nmove the needle — يُحدث فرقاً ملموساً",
                skill="vocabulary",
                difficulty_score=0.9,
            ),
            TopicItem(
                item_type="reading",
                title_en="Idioms in context",
                title_ar="التعابير في السياق",
                instructions_en="Read and underline three idioms you could reuse.",
                instructions_ar="اقرأ وحدّد ثلاث تعابير يمكنك استخدامها.",
                content_text="The team had been on the back foot since the funding round, but rather than cut corners, they decided they were at a crossroads — and the next release had to move the needle.",
                skill="reading",
                difficulty_score=0.9,
            ),
            TopicItem(
                item_type="writing",
                title_en="Use two idioms naturally",
                title_ar="استخدم تعبيرين بشكل طبيعي",
                instructions_en="Write 3-4 sentences about a project, using two idioms above without forcing them.",
                instructions_ar="اكتب 3-4 جمل عن مشروع، مستخدماً تعبيرين أعلاه بشكل طبيعي.",
                content_text="If an idiom feels forced, swap it for a plain phrase.",
                skill="writing",
                difficulty_score=0.9,
                estimated_minutes=5,
            ),
            TopicItem(
                item_type="speaking",
                title_en="Tell a 2-minute story",
                title_ar="احكِ قصة من دقيقتين",
                instructions_en="A short story about a decision — work in two idioms.",
                instructions_ar="قصة قصيرة عن قرار اتخذته — مع تضمين تعبيرين.",
                content_text="Story arc: setup → turning point → outcome.",
                skill="speaking",
                difficulty_score=0.9,
                estimated_minutes=4,
            ),
        ),
    ),
    TopicTemplate(
        slug="c2_speech_to_audience",
        cefr_level="C2",
        title_en="Adjust a speech to your audience",
        title_ar="عدّل خطابك حسب الجمهور",
        description_en="Same content, three audiences — board, team, public.",
        description_ar="نفس المحتوى، ثلاثة جماهير — مجلس إدارة، فريق، جمهور عام.",
        items=(
            TopicItem(
                item_type="reading",
                title_en="Three versions, one message",
                title_ar="ثلاث صياغات لرسالة واحدة",
                instructions_en="Read and note which words shift between versions.",
                instructions_ar="اقرأ ولاحظ الكلمات التي تتغيّر بين الصياغات.",
                content_text="BOARD: We are reorienting the portfolio toward higher-margin segments.\nTEAM: We're shifting where we focus so we can win bigger deals.\nPUBLIC: We're updating our product line to better serve our customers.",
                skill="reading",
                difficulty_score=0.9,
            ),
            TopicItem(
                item_type="writing",
                title_en="Three audiences, one update",
                title_ar="ثلاثة جماهير، تحديث واحد",
                instructions_en="Write the same announcement three ways — for a board, a team, a customer email.",
                instructions_ar="اكتب نفس الإعلان بثلاث صياغات — لمجلس، لفريق، لعميل.",
                content_text="Topic: a one-week delay on a launch.",
                skill="writing",
                difficulty_score=0.9,
                estimated_minutes=6,
            ),
            TopicItem(
                item_type="speaking",
                title_en="Deliver the public version",
                title_ar="ألقِ النسخة العامة",
                instructions_en="Speak your customer-facing version aloud — natural pace, warm tone.",
                instructions_ar="انطق نسختك الموجّهة للعميل — بسرعة طبيعية ونبرة دافئة.",
                content_text="Warmth comes from short sentences and concrete words.",
                skill="speaking",
                difficulty_score=0.9,
                estimated_minutes=3,
            ),
            TopicItem(
                item_type="quiz",
                title_en="Pick the right register",
                title_ar="اختر المستوى المناسب",
                instructions_en="Which sentence belongs in a board memo, not a customer email?",
                instructions_ar="أيّ جملة تنتمي لمذكرة مجلس إدارة لا لرسالة لعميل؟",
                question="Pick the board-memo sentence.",
                options=(
                    "We are reorienting the portfolio toward higher-margin segments.",
                    "We're making some changes to serve you better.",
                    "Sorry for the delay — thanks for sticking with us!",
                ),
                correct_answer="We are reorienting the portfolio toward higher-margin segments.",
                explanation_en="High-register, jargon-heavy, third-person — board language.",
                explanation_ar="مستوى رسمي عالي، اصطلاحي، بصيغة الغائب — لغة مجلس إدارة.",
                skill="vocabulary",
                difficulty_score=0.9,
            ),
        ),
    ),
)

# Index by level for fast lookup
TOPICS_BY_LEVEL = {
    "A1": A1_TOPICS,
    "A2": A2_TOPICS,
    "B1": B1_TOPICS,
    "B2": B2_TOPICS,
    "C1": C1_TOPICS,
    "C2": C2_TOPICS,
    "C3": C2_TOPICS,
}


def pick_topic_for_level(cefr_level: str, date_ordinal: int, user_id: int) -> TopicTemplate | None:
    """Deterministic topic selection.

    Falls back to A1 if level is unknown or has no templates.
    """
    pool = TOPICS_BY_LEVEL.get((cefr_level or "").upper()) or A1_TOPICS
    if not pool:
        return None
    idx = (date_ordinal + (user_id or 0)) % len(pool)
    return pool[idx]


# Motivation lines indexed by level family
MOTIVATIONS_EN = {
    "A1": (
        "Keep going — every short lesson moves you forward.",
        "Great job today. Tomorrow we will go one step further.",
        "You are doing well. Small steps, real progress.",
    ),
    "A2": (
        "Strong work today. You are building real fluency.",
        "Well done — your sentences are getting longer.",
        "Excellent. Practice every day and you will see big changes.",
    ),
    "B1": (
        "Solid effort today. Keep pushing your boundaries.",
        "You are reading and writing more clearly each day.",
        "Great work — your fluency is steady.",
    ),
    "B2": (
        "Excellent work. Your arguments are clearer every day.",
        "Strong session today. Keep stretching for richer vocabulary.",
        "Great progress — your English is becoming more natural.",
    ),
    "C1": (
        "Polished work today. Your precision is improving.",
        "Excellent effort. Keep refining your style.",
        "Great session — you are using sophisticated language well.",
    ),
    "C2": (
        "Excellent. Your command of nuance is impressive.",
        "Outstanding work — keep stretching your range.",
        "Polished. Aim for elegance and conciseness next.",
    ),
}

MOTIVATIONS_AR = {
    "A1": (
        "واصل التعلم — كل درس قصير يدفعك للأمام.",
        "أحسنت اليوم. غداً سنخطو خطوة أبعد.",
        "أداؤك جيد. خطوات صغيرة، وتقدم حقيقي.",
    ),
    "A2": (
        "عمل جيد اليوم. أنت تبني طلاقة حقيقية.",
        "أحسنت — جملك تصبح أطول.",
        "ممتاز. تدرّب يومياً وسترى تغيراً كبيراً.",
    ),
    "B1": (
        "جهد قوي اليوم. واصل دفع حدودك.",
        "كتابتك وقراءتك تتحسنان كل يوم.",
        "عمل رائع — طلاقتك ثابتة.",
    ),
    "B2": (
        "ممتاز. حججك تزداد وضوحاً كل يوم.",
        "جلسة قوية. واصل توسيع مفرداتك.",
        "تقدم رائع — لغتك تصبح أكثر طبيعية.",
    ),
    "C1": (
        "عمل مصقول. دقتك تتحسن.",
        "جهد ممتاز. واصل صقل أسلوبك.",
        "جلسة رائعة — تستخدم لغة راقية.",
    ),
    "C2": (
        "ممتاز. تمكنك من الفروق الدقيقة مذهل.",
        "عمل متميز — واصل توسيع نطاقك.",
        "مصقول. اسعَ للأناقة والاختصار في المرة القادمة.",
    ),
}


def motivation_line(cefr_level: str, language: str, index: int) -> str:
    """Pick a motivation line by level and language."""
    level = (cefr_level or "A1").upper()
    pool = (MOTIVATIONS_AR if language == "ar" else MOTIVATIONS_EN).get(level)
    if not pool:
        pool = (MOTIVATIONS_AR if language == "ar" else MOTIVATIONS_EN)["A1"]
    return pool[index % len(pool)]

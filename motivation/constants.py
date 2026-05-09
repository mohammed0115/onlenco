"""Constants and policy maps for the motivation engine."""

# --- Tones ---
TONE_ENERGETIC    = "energetic"
TONE_GENTLE       = "gentle"
TONE_PROFESSIONAL = "professional"
TONE_CHALLENGING  = "challenging"
TONE_SUPPORTIVE   = "supportive"

TONE_CHOICES = [
    (TONE_ENERGETIC, "Energetic"),
    (TONE_GENTLE, "Gentle"),
    (TONE_PROFESSIONAL, "Professional"),
    (TONE_CHALLENGING, "Challenging"),
    (TONE_SUPPORTIVE, "Supportive"),
]

# --- Frequency ---
FREQ_LOW    = "low"
FREQ_NORMAL = "normal"
FREQ_HIGH   = "high"

FREQUENCY_CHOICES = [
    (FREQ_LOW, "Low"),
    (FREQ_NORMAL, "Normal"),
    (FREQ_HIGH, "High"),
]

# --- Message types ---
MSG_ACHIEVEMENT       = "achievement"
MSG_ENCOURAGEMENT     = "encouragement"
MSG_STREAK            = "streak"
MSG_COMEBACK          = "comeback"
MSG_GOAL              = "goal"
MSG_WARNING           = "warning"
MSG_CHALLENGE         = "challenge"
MSG_WEEKLY_SUMMARY    = "weekly_summary"

MESSAGE_TYPE_CHOICES = [
    (MSG_ACHIEVEMENT, "Achievement"),
    (MSG_ENCOURAGEMENT, "Encouragement"),
    (MSG_STREAK, "Streak"),
    (MSG_COMEBACK, "Comeback"),
    (MSG_GOAL, "Goal"),
    (MSG_WARNING, "Warning"),
    (MSG_CHALLENGE, "Challenge"),
    (MSG_WEEKLY_SUMMARY, "Weekly summary"),
]

# --- Status ---
STATUS_GENERATED = "generated"
STATUS_SENT      = "sent"
STATUS_DISMISSED = "dismissed"
STATUS_CLICKED   = "clicked"

STATUS_CHOICES = [
    (STATUS_GENERATED, "Generated"),
    (STATUS_SENT, "Sent"),
    (STATUS_DISMISSED, "Dismissed"),
    (STATUS_CLICKED, "Clicked"),
]

# --- Sent via ---
VIA_IN_APP = "in_app"
VIA_EMAIL  = "email"
VIA_BOTH   = "both"
VIA_NONE   = "none"

SENT_VIA_CHOICES = [
    (VIA_IN_APP, "In-app"),
    (VIA_EMAIL, "Email"),
    (VIA_BOTH, "Both"),
    (VIA_NONE, "Not sent"),
]

# --- Achievement categories ---
CAT_LESSON       = "lesson"
CAT_QUIZ         = "quiz"
CAT_READING      = "reading"
CAT_SPEAKING     = "speaking"
CAT_AI_TUTOR     = "ai_tutor"
CAT_STREAK       = "streak"
CAT_VOCABULARY   = "vocabulary"
CAT_LEVEL        = "level"
CAT_SUBSCRIPTION = "subscription"

ACHIEVEMENT_CATEGORY_CHOICES = [
    (CAT_LESSON, "Lesson"),
    (CAT_QUIZ, "Quiz"),
    (CAT_READING, "Reading"),
    (CAT_SPEAKING, "Speaking"),
    (CAT_AI_TUTOR, "AI Tutor"),
    (CAT_STREAK, "Streak"),
    (CAT_VOCABULARY, "Vocabulary"),
    (CAT_LEVEL, "Level"),
    (CAT_SUBSCRIPTION, "Subscription"),
]

# --- XP rules ---
XP_LESSON_COMPLETE       = 20
XP_QUIZ_COMPLETE         = 10
XP_QUIZ_HIGH_ACCURACY    = 15
XP_SPEAKING_10_MIN       = 15
XP_AI_CHAT_20_MIN        = 20
XP_READ_500_WORDS        = 10
XP_WEEKLY_ASSESSMENT     = 30
XP_DAILY_STREAK          = 10
XP_LEVEL_IMPROVED        = 50
XP_PER_LEVEL             = 100  # XP per gameified level (separate from CEFR)

# --- Streak milestones (days) that fire badges + messages ---
STREAK_MILESTONES = [3, 7, 14, 30, 60, 100]

# --- Frequency caps ---
MAX_EMAILS_PER_DAY      = 1   # for non-achievement motivation emails
MAX_WEEKLY_SUMMARY      = 1   # per week per user
INACTIVITY_COMEBACK_MIN = 3   # days
INACTIVITY_COMEBACK_MAX = 30  # don't ping ghosts forever

# --- Default achievement seed (used by `seed_achievements` command) ---
DEFAULT_ACHIEVEMENTS = [
    # code, category, threshold, xp, name(en), description(en), name(ar), description(ar), badge_icon
    ("first_lesson_completed", CAT_LESSON, 1, 50,
     "First step", "Completed your first lesson.",
     "الخطوة الأولى", "أكملت أول درس لك.", "trophy"),
    ("five_lessons_completed", CAT_LESSON, 5, 75,
     "On a roll", "Completed 5 lessons.",
     "تتقدم بثبات", "أكملت 5 دروس.", "rocket"),
    ("twenty_lessons_completed", CAT_LESSON, 20, 200,
     "Consistent learner", "Completed 20 lessons.",
     "متعلم مثابر", "أكملت 20 درساً.", "graduation-cap"),

    ("first_ai_conversation", CAT_AI_TUTOR, 1, 30,
     "AI Talker", "Had your first AI tutor conversation.",
     "متحدث الذكاء", "أجريت أول محادثة مع المعلم الذكي.", "message-square"),
    ("ten_ai_conversations", CAT_AI_TUTOR, 10, 150,
     "Confident speaker", "Had 10 AI tutor conversations.",
     "متحدث واثق", "أجريت 10 محادثات مع المعلم الذكي.", "mic"),

    ("twenty_minutes_speaking", CAT_SPEAKING, 20, 50,
     "Voice unlocked", "Practiced speaking for 20 minutes total.",
     "صوتك مفتاحك", "تدربت على المحادثة 20 دقيقة بالمجمل.", "mic"),

    ("fifty_questions_answered", CAT_QUIZ, 50, 100,
     "Grammar fighter", "Answered 50 quiz questions.",
     "محارب القواعد", "أجبت على 50 سؤالاً.", "swords"),
    ("quiz_master_high_accuracy", CAT_QUIZ, 85, 150,
     "Quiz master", "Hit 85%+ accuracy with at least 20 questions.",
     "خبير الاختبارات", "حققت دقة 85% على الأقل في 20 سؤالاً.", "target"),

    ("read_500_words", CAT_READING, 500, 50,
     "Reading explorer", "Read 500 words.",
     "مستكشف القراءة", "قرأت 500 كلمة.", "book-open"),
    ("read_5000_words", CAT_READING, 5000, 200,
     "Bookworm", "Read 5,000 words.",
     "عاشق الكتب", "قرأت 5,000 كلمة.", "library"),

    ("seven_day_streak", CAT_STREAK, 7, 100,
     "7-day streak", "Studied 7 days in a row.",
     "سلسلة 7 أيام", "تعلمت 7 أيام متتالية.", "flame"),
    ("thirty_day_streak", CAT_STREAK, 30, 500,
     "30-day streak", "Studied 30 days in a row.",
     "سلسلة 30 يوماً", "تعلمت 30 يوماً متتالياً.", "flame"),

    ("vocabulary_growth_100", CAT_VOCABULARY, 100, 100,
     "Vocabulary builder", "Encountered 100 vocabulary items.",
     "بنّاء المفردات", "تعرفت على 100 كلمة جديدة.", "book"),

    ("level_up_a2", CAT_LEVEL, 0, 100, "Level A2", "Reached CEFR A2.",   "مستوى A2",  "وصلت إلى مستوى A2.", "award"),
    ("level_up_b1", CAT_LEVEL, 0, 150, "Level B1", "Reached CEFR B1.",   "مستوى B1",  "وصلت إلى مستوى B1.", "award"),
    ("level_up_b2", CAT_LEVEL, 0, 200, "Level B2", "Reached CEFR B2.",   "مستوى B2",  "وصلت إلى مستوى B2.", "award"),
    ("level_up_c1", CAT_LEVEL, 0, 300, "Level C1", "Reached CEFR C1.",   "مستوى C1",  "وصلت إلى مستوى C1.", "award"),

    ("first_weekly_assessment", CAT_QUIZ, 1, 60,
     "Weekly check-in",
     "Completed your first weekly assessment.",
     "تقييمك الأول",
     "أكملت أول تقييم أسبوعي.",
     "clipboard-check"),

    ("comeback_learner", CAT_STREAK, 0, 30,
     "Comeback learner",
     "Returned after a break — welcome back!",
     "العودة الجميلة",
     "عُدت بعد فترة انقطاع — أهلاً بك مجدداً!",
     "heart"),

    ("active_subscription", CAT_SUBSCRIPTION, 0, 50,
     "Premium learner", "Activated your subscription.",
     "متعلم مشترك", "فعّلت اشتراكك.", "crown"),
]

# --- Tone selection thresholds (used by message_generator) ---
TONE_FOR_INACTIVE_DAYS_MIN = 3   # ≥ 3 inactive days → gentle/supportive
TONE_FOR_HIGH_ACTIVITY_XP  = 100  # ≥ 100 XP today → energetic/challenging

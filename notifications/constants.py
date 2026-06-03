"""Event types, priority/status enums, and policy maps for notifications."""

# --- Event types ---

# Student-facing events
USER_REGISTERED = "user_registered"
EMAIL_VERIFICATION = "email_verification"
PASSWORD_RESET = "password_reset"
PLACEMENT_COMPLETED = "placement_completed"
WEAKNESS_DETECTED = "weakness_detected"
EXERCISES_GENERATED = "exercises_generated"
LESSON_COMPLETED = "lesson_completed"
WEEKLY_ASSESSMENT_AVAILABLE = "weekly_assessment_available"
WEEKLY_ASSESSMENT_RESULT = "weekly_assessment_result"
LEVEL_IMPROVED = "level_improved"
SUBSCRIPTION_EXPIRING = "subscription_expiring"
PAYMENT_SUBMITTED = "payment_submitted"
PAYMENT_APPROVED = "payment_approved"
PAYMENT_REJECTED = "payment_rejected"
INACTIVE_STUDENT_REMINDER = "inactive_student_reminder"

# Daily learning engine events (delivered to students)
DAILY_PLAN_READY = "daily_plan_ready"
DAILY_PLAN_COMEBACK = "daily_plan_comeback"
DAILY_PLAN_STREAK_REMINDER = "daily_plan_streak_reminder"

# Admin-facing events
NEW_STUDENT_REGISTERED = "new_student_registered"
NEW_PAYMENT_PENDING = "new_payment_pending"
AI_USAGE_HIGH = "ai_usage_high"
AI_FAILURE = "ai_failure"
AT_RISK_STUDENT = "at_risk_student"
DAILY_ADMIN_SUMMARY = "daily_admin_summary"
WEEKLY_ADMIN_SUMMARY = "weekly_admin_summary"

# Teacher-facing portal events
TEACHER_COURSE_APPROVED = "teacher_course_approved"
TEACHER_COURSE_REJECTED = "teacher_course_rejected"
TEACHER_ASSIGNMENT_SUBMITTED = "teacher_assignment_submitted"
TEACHER_STUDENT_LOW_PERFORMANCE = "teacher_student_low_performance"
TEACHER_CONTENT_NEEDS_REVISION = "teacher_content_needs_revision"
TEACHER_DAILY_DIGEST = "teacher_daily_digest"

# Live sessions (Marketplace prompt 2)
LIVE_SESSION_SCHEDULED = "live_session_scheduled"
LIVE_SESSION_REMINDER = "live_session_reminder"

# Motivation engine events (delivered to students)
MOTIVATION_MESSAGE_GENERATED = "motivation_message_generated"
ACHIEVEMENT_UNLOCKED         = "achievement_unlocked"
BADGE_EARNED                 = "badge_earned"
XP_AWARDED                   = "xp_awarded"
STREAK_MILESTONE             = "streak_milestone"
COMEBACK_REMINDER            = "comeback_reminder"
WEEKLY_MOTIVATION_SUMMARY    = "weekly_motivation_summary"

ALL_STUDENT_EVENTS = [
    USER_REGISTERED,
    EMAIL_VERIFICATION,
    PASSWORD_RESET,
    PLACEMENT_COMPLETED,
    WEAKNESS_DETECTED,
    EXERCISES_GENERATED,
    LESSON_COMPLETED,
    WEEKLY_ASSESSMENT_AVAILABLE,
    WEEKLY_ASSESSMENT_RESULT,
    LEVEL_IMPROVED,
    SUBSCRIPTION_EXPIRING,
    PAYMENT_SUBMITTED,
    PAYMENT_APPROVED,
    PAYMENT_REJECTED,
    INACTIVE_STUDENT_REMINDER,
    DAILY_PLAN_READY,
    DAILY_PLAN_COMEBACK,
    DAILY_PLAN_STREAK_REMINDER,
]

ALL_ADMIN_EVENTS = [
    NEW_STUDENT_REGISTERED,
    NEW_PAYMENT_PENDING,
    AI_USAGE_HIGH,
    AI_FAILURE,
    AT_RISK_STUDENT,
    DAILY_ADMIN_SUMMARY,
    WEEKLY_ADMIN_SUMMARY,
]

ALL_TEACHER_EVENTS = [
    TEACHER_COURSE_APPROVED,
    TEACHER_COURSE_REJECTED,
    TEACHER_ASSIGNMENT_SUBMITTED,
    TEACHER_STUDENT_LOW_PERFORMANCE,
    TEACHER_CONTENT_NEEDS_REVISION,
    TEACHER_DAILY_DIGEST,
    LIVE_SESSION_SCHEDULED,
    LIVE_SESSION_REMINDER,
]

ALL_MOTIVATION_EVENTS = [
    MOTIVATION_MESSAGE_GENERATED,
    ACHIEVEMENT_UNLOCKED,
    BADGE_EARNED,
    XP_AWARDED,
    STREAK_MILESTONE,
    COMEBACK_REMINDER,
    WEEKLY_MOTIVATION_SUMMARY,
]

ALL_EVENT_TYPES = ALL_STUDENT_EVENTS + ALL_ADMIN_EVENTS + ALL_TEACHER_EVENTS + ALL_MOTIVATION_EVENTS

EVENT_TYPE_CHOICES = [(e, e) for e in ALL_EVENT_TYPES]

# --- Status / priority enums ---

STATUS_PENDING = "pending"
STATUS_PROCESSED = "processed"
STATUS_SENT = "sent"
STATUS_FAILED = "failed"
STATUS_SKIPPED = "skipped"

EVENT_STATUS_CHOICES = [
    (STATUS_PENDING, "Pending"),
    (STATUS_PROCESSED, "Processed"),
    (STATUS_FAILED, "Failed"),
    (STATUS_SKIPPED, "Skipped"),
]

EMAIL_STATUS_CHOICES = [
    (STATUS_PENDING, "Pending"),
    (STATUS_SENT, "Sent"),
    (STATUS_FAILED, "Failed"),
    (STATUS_SKIPPED, "Skipped"),
]

PRIORITY_LOW = "low"
PRIORITY_NORMAL = "normal"
PRIORITY_HIGH = "high"
PRIORITY_CRITICAL = "critical"

PRIORITY_CHOICES = [
    (PRIORITY_LOW, "Low"),
    (PRIORITY_NORMAL, "Normal"),
    (PRIORITY_HIGH, "High"),
    (PRIORITY_CRITICAL, "Critical"),
]

# --- Policy maps used by PreferenceService ---

# Transactional/security events that bypass user preference toggles.
TRANSACTIONAL_EVENTS = {
    EMAIL_VERIFICATION,
    PASSWORD_RESET,
    PAYMENT_APPROVED,
    PAYMENT_REJECTED,
    SUBSCRIPTION_EXPIRING,
    USER_REGISTERED,            # account-confirmation-style
    PAYMENT_SUBMITTED,          # receipt
    WEEKLY_ASSESSMENT_AVAILABLE,  # part of the core learning loop
}

# Events controlled by `learning_updates`
LEARNING_EVENTS = {
    WEAKNESS_DETECTED,
    EXERCISES_GENERATED,
    LESSON_COMPLETED,
    WEEKLY_ASSESSMENT_RESULT,
    LEVEL_IMPROVED,
    INACTIVE_STUDENT_REMINDER,
    MOTIVATION_MESSAGE_GENERATED,
    ACHIEVEMENT_UNLOCKED,
    BADGE_EARNED,
    XP_AWARDED,
    STREAK_MILESTONE,
    COMEBACK_REMINDER,
    DAILY_PLAN_READY,
    DAILY_PLAN_COMEBACK,
    DAILY_PLAN_STREAK_REMINDER,
}

# Events controlled by `payment_updates`
PAYMENT_EVENTS = {
    PAYMENT_SUBMITTED,
    PAYMENT_APPROVED,
    PAYMENT_REJECTED,
    SUBSCRIPTION_EXPIRING,
}

# Events controlled by `weekly_summary`
WEEKLY_SUMMARY_EVENTS = {
    WEEKLY_ASSESSMENT_AVAILABLE,
    WEEKLY_ADMIN_SUMMARY,
    WEEKLY_MOTIVATION_SUMMARY,
}

# Motivation events governed by MotivationPreference + a learning_updates fallback
MOTIVATION_LEARNING_EVENTS = {
    MOTIVATION_MESSAGE_GENERATED,
    ACHIEVEMENT_UNLOCKED,
    BADGE_EARNED,
    XP_AWARDED,
    STREAK_MILESTONE,
    COMEBACK_REMINDER,
}

# Events controlled by `admin_alerts` (recipient must be staff/admin)
ADMIN_ONLY_EVENTS = set(ALL_ADMIN_EVENTS)

# Marketing-style events (require explicit opt-in)
MARKETING_EVENTS = set()  # none today; reserved for future campaigns

# Default subject lines (English) — also used as the i18n fallback.
DEFAULT_SUBJECTS = {
    USER_REGISTERED: "Welcome to Onlenco",
    EMAIL_VERIFICATION: "Verify your Onlenco email",
    PASSWORD_RESET: "Reset your Onlenco password",
    PLACEMENT_COMPLETED: "Your Onlenco placement results",
    WEAKNESS_DETECTED: "We spotted a learning focus area",
    EXERCISES_GENERATED: "Your personalized exercises are ready",
    LESSON_COMPLETED: "Lesson completed — well done!",
    WEEKLY_ASSESSMENT_AVAILABLE: "Onlenco — your weekly assessment is ready",
    WEEKLY_ASSESSMENT_RESULT: "Your weekly assessment result",
    LEVEL_IMPROVED: "Congratulations — your level just improved",
    SUBSCRIPTION_EXPIRING: "Your Onlenco subscription is expiring soon",
    PAYMENT_SUBMITTED: "We received your payment",
    PAYMENT_APPROVED: "Your Onlenco subscription is active",
    PAYMENT_REJECTED: "Your payment needs attention",
    INACTIVE_STUDENT_REMINDER: "We miss you on Onlenco",
    DAILY_PLAN_READY: "Your Onlenco daily plan is ready",
    DAILY_PLAN_COMEBACK: "We missed you — your short comeback plan is ready",
    DAILY_PLAN_STREAK_REMINDER: "Don't break your Onlenco streak",
    NEW_STUDENT_REGISTERED: "[Onlenco admin] New student registered",
    NEW_PAYMENT_PENDING: "[Onlenco admin] New payment pending review",
    AI_USAGE_HIGH: "[Onlenco admin] AI usage threshold crossed",
    AI_FAILURE: "[Onlenco admin] AI failure detected",
    AT_RISK_STUDENT: "[Onlenco admin] At-risk student",
    DAILY_ADMIN_SUMMARY: "[Onlenco admin] Daily summary",
    WEEKLY_ADMIN_SUMMARY: "[Onlenco admin] Weekly summary",
    TEACHER_COURSE_APPROVED: "Your Onlenco course was approved",
    TEACHER_COURSE_REJECTED: "Your Onlenco course needs revision",
    TEACHER_ASSIGNMENT_SUBMITTED: "A student submitted an assignment",
    TEACHER_STUDENT_LOW_PERFORMANCE: "A student needs support",
    TEACHER_CONTENT_NEEDS_REVISION: "Content needs revision",
    TEACHER_DAILY_DIGEST: "Your Onlenco teaching summary",
    LIVE_SESSION_SCHEDULED: "A new live class has been scheduled",
    LIVE_SESSION_REMINDER: "Your live class starts soon",
    MOTIVATION_MESSAGE_GENERATED: "Onlenco — keep going",
    ACHIEVEMENT_UNLOCKED: "Achievement unlocked!",
    BADGE_EARNED: "You earned a new badge",
    XP_AWARDED: "XP earned",
    STREAK_MILESTONE: "Your streak is on fire",
    COMEBACK_REMINDER: "We miss you — pick up where you left off",
    WEEKLY_MOTIVATION_SUMMARY: "Your week on Onlenco",
}

# Subject line in Arabic (used when language='ar').
SUBJECTS_AR = {
    USER_REGISTERED: "مرحبًا بك في Onlenco",
    EMAIL_VERIFICATION: "تأكيد بريدك الإلكتروني في Onlenco",
    PASSWORD_RESET: "إعادة تعيين كلمة المرور",
    PLACEMENT_COMPLETED: "نتيجة اختبار تحديد المستوى",
    WEAKNESS_DETECTED: "تم تحديد نقطة تحتاج إلى تدريب",
    EXERCISES_GENERATED: "تم تجهيز تمارين جديدة لك",
    LESSON_COMPLETED: "أحسنت — اكتمل الدرس",
    WEEKLY_ASSESSMENT_AVAILABLE: "اختبارك الأسبوعي جاهز",
    WEEKLY_ASSESSMENT_RESULT: "نتيجة الاختبار الأسبوعي",
    LEVEL_IMPROVED: "تهانينا — مستواك تحسن",
    SUBSCRIPTION_EXPIRING: "اشتراكك على وشك الانتهاء",
    PAYMENT_SUBMITTED: "تم استلام طلب الدفع",
    PAYMENT_APPROVED: "تم قبول الدفع وتفعيل اشتراكك",
    PAYMENT_REJECTED: "تم رفض طلب الدفع",
    INACTIVE_STUDENT_REMINDER: "نفتقدك في Onlenco",
    DAILY_PLAN_READY: "خطة اليوم جاهزة في Onlenco",
    DAILY_PLAN_COMEBACK: "اشتقنا لك — خطة عودة قصيرة بانتظارك",
    DAILY_PLAN_STREAK_REMINDER: "لا تكسر سلسلتك في Onlenco",
    MOTIVATION_MESSAGE_GENERATED: "Onlenco — استمر، أنت تتقدم!",
    ACHIEVEMENT_UNLOCKED: "إنجاز جديد!",
    BADGE_EARNED: "حصلت على شارة جديدة",
    XP_AWARDED: "حصلت على نقاط XP",
    STREAK_MILESTONE: "سلسلتك مشتعلة!",
    COMEBACK_REMINDER: "نفتقدك — أكمل من حيث توقفت",
    WEEKLY_MOTIVATION_SUMMARY: "ملخص تقدمك الأسبوعي",
    TEACHER_COURSE_APPROVED: "تم قبول كورسك ونشره بنجاح",
    TEACHER_COURSE_REJECTED: "تم رفض الكورس، يرجى مراجعة الملاحظات",
    TEACHER_ASSIGNMENT_SUBMITTED: "قام طالب جديد بإرسال واجب",
    TEACHER_STUDENT_LOW_PERFORMANCE: "يوجد طالب يحتاج إلى متابعة في كورسك",
    TEACHER_CONTENT_NEEDS_REVISION: "يوجد محتوى يحتاج إلى تعديل",
    TEACHER_DAILY_DIGEST: "ملخّص يومك التدريسي في Onlenco",
    LIVE_SESSION_SCHEDULED: "تم تحديد موعد حصة مباشرة جديدة",
    LIVE_SESSION_REMINDER: "حصتك المباشرة تبدأ قريباً",
}

# Map event_type → template filename (relative to templates/notifications/emails/)
TEMPLATE_NAMES = {
    USER_REGISTERED: "welcome.html",
    EMAIL_VERIFICATION: "email_verification.html",
    PASSWORD_RESET: "password_reset.html",
    PLACEMENT_COMPLETED: "placement_result.html",
    WEAKNESS_DETECTED: "weakness_detected.html",
    EXERCISES_GENERATED: "exercises_generated.html",
    LESSON_COMPLETED: "lesson_completed.html",
    WEEKLY_ASSESSMENT_AVAILABLE: "weekly_assessment_available.html",
    WEEKLY_ASSESSMENT_RESULT: "weekly_assessment_result.html",
    LEVEL_IMPROVED: "level_improved.html",
    SUBSCRIPTION_EXPIRING: "subscription_expiring.html",
    PAYMENT_SUBMITTED: "payment_submitted.html",
    PAYMENT_APPROVED: "payment_approved.html",
    PAYMENT_REJECTED: "payment_rejected.html",
    INACTIVE_STUDENT_REMINDER: "inactive_student_reminder.html",
    DAILY_PLAN_READY: "daily_plan_ready.html",
    DAILY_PLAN_COMEBACK: "daily_plan_comeback.html",
    DAILY_PLAN_STREAK_REMINDER: "daily_plan_streak_reminder.html",
    MOTIVATION_MESSAGE_GENERATED: "motivation_message.html",
    ACHIEVEMENT_UNLOCKED: "achievement_unlocked.html",
    BADGE_EARNED: "badge_earned.html",
    XP_AWARDED: "xp_awarded.html",
    STREAK_MILESTONE: "streak_milestone.html",
    COMEBACK_REMINDER: "comeback_reminder.html",
    WEEKLY_MOTIVATION_SUMMARY: "weekly_motivation_summary.html",
    NEW_STUDENT_REGISTERED: "admin_new_student.html",
    NEW_PAYMENT_PENDING: "admin_new_payment_pending.html",
    AI_USAGE_HIGH: "admin_ai_usage_high.html",
    AI_FAILURE: "admin_ai_failure.html",
    AT_RISK_STUDENT: "admin_at_risk_student.html",
    DAILY_ADMIN_SUMMARY: "admin_daily_summary.html",
    WEEKLY_ADMIN_SUMMARY: "admin_weekly_summary.html",
    LIVE_SESSION_SCHEDULED: "live_session_scheduled.html",
    LIVE_SESSION_REMINDER: "live_session_reminder.html",
}

# DATABASE_MODEL_BLUEPRINT.md

## 1. Accounts

```text
User
- id
- email
- password
- full_name
- role
- preferred_language
- is_active
- created_at
- updated_at

Role choices:
- student
- academic_admin
- finance_admin
- super_admin
- content_manager
```

## 2. Curriculum

```text
CEFRLevel
- id
- code: A0/A1/A2/B1/B2/C1/C2
- name_ar
- name_en
- description_ar
- description_en
- order

Unit
- id
- cefr_level
- title_ar
- title_en
- description_ar
- description_en
- order
- is_active

Lesson
- id
- unit
- cefr_level
- title_ar
- title_en
- description_ar
- description_en
- short_video_url
- grammar_focus
- vocabulary_focus
- speaking_goal
- listening_goal
- reading_goal
- writing_goal
- order
- is_active
```

قاعدة مهمة:

```text
كل Unit لا تتجاوز 3 Lessons.
```

## 3. Placement

```text
PlacementTest
PlacementQuestion
PlacementChoice
PlacementAttempt
PlacementAnswer
PlacementResult

SpeakingPlacementSession
SpeakingQuestion
SpeakingAnswer
SpeakingAssessmentResult
```

## 4. Learning Profiles

```text
StudentLearningProfile
- user
- final_cefr_level
- written_score
- speaking_score
- grammar_score
- vocabulary_score
- reading_score
- writing_score
- pronunciation_score
- fluency_score
- theta_score
- confidence_score
- recommended_start_level
- recommended_first_unit
- recommended_first_lesson

StudentSkillMastery
StudentWeakness
StudentStrength
StudentLearningRecommendation
```

## 5. Adaptive Learning

```text
UserError
UserWeakness
SkillMastery
AdaptiveRecommendation
DifficultyAdjustmentLog
```

## 6. AI Tutor

```text
AITutorSession
AITutorMessage
AITutorVoiceMessage
AIUsageLog
MicroExercise
```

## 7. Speech Assessment

```text
SpeechAttempt
PronunciationIssue
SpeakingFeedback
```

## 8. Gamification

```text
XPTransaction
Badge
UserBadge
DailyStreak
Challenge
ChallengeProgress
```

## 9. Motivation

```text
MotivationMessageTemplate
UserMotivationMessage
MotivationTrigger
```

## 10. Behavioral Analytics

```text
StudentActivityLog
EngagementSnapshot
ChurnRiskSnapshot
LearningProgressSnapshot
```

## 11. Weekly Club

```text
WeeklyClubSession
ClubRegistration
ClubAttendance
ClubFeedback
```

## 12. Payments

```text
SubscriptionPlan
UserSubscription
PaymentReceipt
PaymentReview
ClubPayment
```

## 13. Notifications

```text
Notification
EmailTemplate
NotificationPreference
NotificationLog
```

## 14. Academic Admin

```text
AcademicNote
AssignedExercise
TeacherStudentMessage
```

## 15. Digital Library

```text
LibraryCategory
LibraryItem
ExtractedVocabulary
ExtractedGrammarPoint
ComprehensionQuestion
UserLibraryProgress
```

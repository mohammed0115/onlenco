# API_CONTRACTS_OVERVIEW.md

## Accounts

```text
POST /api/v1/auth/register/
POST /api/v1/auth/login/
POST /api/v1/auth/logout/
GET  /api/v1/auth/me/
PATCH /api/v1/auth/me/
```

## Curriculum

```text
GET  /api/v1/cefr-levels/
GET  /api/v1/curriculum/
GET  /api/v1/curriculum/levels/{level}/units/
GET  /api/v1/units/{id}/
GET  /api/v1/units/{id}/lessons/
GET  /api/v1/lessons/{id}/
POST /api/v1/lessons/{id}/start/
POST /api/v1/lessons/{id}/complete/
GET  /api/v1/units/{id}/progress/
```

## Placement

```text
POST /api/v1/placement/written/start/
GET  /api/v1/placement/written/{attempt_id}/question/
POST /api/v1/placement/written/{attempt_id}/answer/
POST /api/v1/placement/written/{attempt_id}/finish/

POST /api/v1/placement/speaking/start/
GET  /api/v1/placement/speaking/{session_id}/next-question/
POST /api/v1/placement/speaking/{session_id}/upload-audio/
GET  /api/v1/placement/speaking/{session_id}/feedback/
POST /api/v1/placement/speaking/{session_id}/finish/

GET  /api/v1/placement/result/
```

## Learning Profile

```text
GET   /api/v1/me/learning-profile/
PATCH /api/v1/me/learning-profile/goals/
GET   /api/v1/me/recommended-next-lesson/
GET   /api/v1/me/weaknesses/
GET   /api/v1/me/strengths/
```

## AI Tutor

```text
POST /api/v1/ai-tutor/sessions/
POST /api/v1/ai-tutor/sessions/{id}/messages/
POST /api/v1/ai-tutor/sessions/{id}/voice/
GET  /api/v1/ai-tutor/sessions/{id}/
POST /api/v1/ai-tutor/sessions/{id}/micro-exercise/
```

## Speech Assessment

```text
POST /api/v1/speech/attempts/
GET  /api/v1/speech/attempts/{id}/feedback/
```

## Gamification

```text
GET /api/v1/me/xp/
GET /api/v1/me/badges/
GET /api/v1/me/streak/
GET /api/v1/me/challenges/
```

## Motivation

```text
GET  /api/v1/me/motivation-messages/
POST /api/v1/me/motivation-messages/{id}/read/
```

## Behavioral Analytics

```text
GET /api/v1/admin/analytics/engagement/
GET /api/v1/admin/analytics/churn-risk/
GET /api/v1/admin/analytics/students-at-risk/
```

## Academic Admin

```text
GET  /api/v1/academic/students/
GET  /api/v1/academic/students/{id}/profile/
POST /api/v1/academic/students/{id}/assign-exercise/
POST /api/v1/academic/students/{id}/notes/
POST /api/v1/academic/students/{id}/message/
GET  /api/v1/academic/students-at-risk/
```

## Finance Admin

```text
GET  /api/v1/finance/payments/pending/
GET  /api/v1/finance/payments/{id}/
POST /api/v1/finance/payments/{id}/approve/
POST /api/v1/finance/payments/{id}/reject/
```

## Payments & Subscriptions

```text
GET  /api/v1/subscriptions/plans/
POST /api/v1/subscriptions/subscribe/
POST /api/v1/payments/upload-receipt/
GET  /api/v1/payments/my-status/
```

## Weekly Club

```text
GET  /api/v1/weekly-club/sessions/
POST /api/v1/weekly-club/sessions/{id}/register/
POST /api/v1/weekly-club/registrations/{id}/upload-payment/
GET  /api/v1/weekly-club/my-registrations/
POST /api/v1/weekly-club/admin/registrations/{id}/approve/
POST /api/v1/weekly-club/admin/attendance/
POST /api/v1/weekly-club/teacher/feedback/
```

## Digital Library

```text
GET  /api/v1/library/
GET  /api/v1/library/{id}/
POST /api/v1/library/{id}/progress/
GET  /api/v1/library/{id}/vocabulary/
POST /api/v1/library/{id}/questions/{question_id}/answer/
```

## Notifications

```text
GET  /api/v1/notifications/
POST /api/v1/notifications/{id}/read/
PATCH /api/v1/notifications/preferences/
```

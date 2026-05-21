from __future__ import annotations

from datetime import timedelta

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.core.files.base import ContentFile
from django.core.management import call_command
from django.core.management.base import BaseCommand
from django.utils import timezone

from courses.models import (
    Course,
    CourseEnrollment,
    CourseLessonProgress,
    CourseLevel,
    Lesson,
    LessonQuestion,
    LessonQuiz,
    LessonResource,
)
from notifications import constants as C
from notifications.models import NotificationEvent
from payments.models import PaymentSubmission
from platform_admin import permissions as platform_perms
from platform_admin.models import PlatformAuditLog, PlatformStudentFlag, PlatformStudentNote
from teacher_portal.models import (
    StudentAssignmentSubmission,
    TeacherAssignment,
    TeacherProfile,
    TeacherStudentNote,
)


PNG_1X1 = (
    b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01"
    b"\x00\x00\x00\x01\x08\x02\x00\x00\x00\x90wS\xde\x00"
    b"\x00\x00\x0cIDATx\x9cc\xf8\xff\xff?\x00\x05\xfe"
    b"\x02\xfeA\x8d\xe5\x9b\x00\x00\x00\x00IEND\xaeB`\x82"
)


class Command(BaseCommand):
    help = "Seed demo users, courses, teacher portal data, payments, and audit logs."

    def add_arguments(self, parser):
        parser.add_argument("--password", default="onlenco123")

    def handle(self, *args, **options):
        password = options["password"]

        call_command("seed_platform_roles", verbosity=0)
        call_command("seed_role_groups", verbosity=0)
        call_command("seed_course_levels", verbosity=0)

        users = self._seed_users(password)
        courses = self._seed_courses(users)
        lessons = self._seed_lessons(courses, users)
        self._seed_enrollments(users, courses, lessons)
        self._seed_assignments(users, courses, lessons)
        self._seed_payments(users)
        self._seed_platform_context(users, courses)
        self._seed_notifications(users, courses)

        self.stdout.write(self.style.SUCCESS("Demo data seeded."))
        self.stdout.write("Login accounts:")
        for label, email in [
            ("Super Admin", "super@onlenco.local"),
            ("Platform Admin", "platform@onlenco.local"),
            ("Academic Admin", "academic@onlenco.local"),
            ("Finance Admin", "finance@onlenco.local"),
            ("Support Admin", "support@onlenco.local"),
            ("AI Admin", "ai@onlenco.local"),
            ("Ahmed Student+Teacher", "ahmed@onlenco.local"),
            ("Sara Teacher", "sara.teacher@onlenco.local"),
            ("Lina Student", "lina.student@onlenco.local"),
            ("Omar Student", "omar.student@onlenco.local"),
        ]:
            self.stdout.write(f"  - {label}: {email} / {password}")

    def _seed_users(self, password: str) -> dict[str, object]:
        User = get_user_model()

        def user(email, *, full_name, role="student", groups=(), is_staff=False, is_superuser=False, level="A1"):
            obj, _created = User.objects.get_or_create(
                username=email,
                defaults={"email": email, "is_staff": is_staff, "is_superuser": is_superuser},
            )
            obj.email = email
            obj.is_staff = is_staff or is_superuser
            obj.is_superuser = is_superuser
            obj.set_password(password)
            obj.save()
            profile = obj.profile
            profile.full_name = full_name
            profile.role = role
            profile.preferred_language = "ar" if email != "sara.teacher@onlenco.local" else "en"
            profile.email_verified = True
            profile.onboarding_completed = True
            profile.onboarding_path = "placement_test"
            profile.cefr_level = level
            profile.initial_cefr_level = level
            profile.subscription_status = "active"
            profile.subscription_expires_at = timezone.now() + timedelta(days=60)
            profile.save()
            for group_name in groups:
                group, _ = Group.objects.get_or_create(name=group_name)
                obj.groups.add(group)
            return obj

        users = {
            "super": user(
                "super@onlenco.local",
                full_name="Onlenco Super Admin",
                role="admin",
                groups=[platform_perms.GROUP_SUPER_ADMIN],
                is_staff=True,
                is_superuser=True,
                level="C2",
            ),
            "platform": user(
                "platform@onlenco.local",
                full_name="Platform Admin",
                role="admin",
                groups=[platform_perms.GROUP_PLATFORM_ADMIN],
                is_staff=True,
                level="C1",
            ),
            "academic": user(
                "academic@onlenco.local",
                full_name="Academic Admin",
                role="admin",
                groups=[platform_perms.GROUP_ACADEMIC_ADMIN],
                is_staff=True,
                level="C1",
            ),
            "finance": user(
                "finance@onlenco.local",
                full_name="Finance Admin",
                role="admin",
                groups=[platform_perms.GROUP_FINANCE_ADMIN],
                is_staff=True,
            ),
            "support": user(
                "support@onlenco.local",
                full_name="Support Admin",
                role="admin",
                groups=[platform_perms.GROUP_SUPPORT_ADMIN],
                is_staff=True,
            ),
            "ai": user(
                "ai@onlenco.local",
                full_name="AI Admin",
                role="admin",
                groups=[platform_perms.GROUP_AI_ADMIN],
                is_staff=True,
            ),
            "ahmed": user(
                "ahmed@onlenco.local",
                full_name="Ahmed Hassan",
                role="student",
                groups=[platform_perms.GROUP_TEACHER],
                is_staff=True,
                level="B1",
            ),
            "sara": user(
                "sara.teacher@onlenco.local",
                full_name="Sara Osman",
                role="admin",
                groups=[platform_perms.GROUP_TEACHER],
                is_staff=True,
                level="C1",
            ),
            "lina": user("lina.student@onlenco.local", full_name="Lina Mahdi", level="A1"),
            "omar": user("omar.student@onlenco.local", full_name="Omar Ali", level="A2"),
        }

        TeacherProfile.objects.update_or_create(
            user=users["ahmed"],
            defaults={
                "bio_ar": "أستاذ محادثة يركز على النطق والجمل القصيرة.",
                "bio_en": "Conversation instructor focused on pronunciation and short sentences.",
                "specialization": "Speaking and pronunciation",
                "is_active": True,
                "approved_at": timezone.now(),
            },
        )
        TeacherProfile.objects.update_or_create(
            user=users["sara"],
            defaults={
                "bio_ar": "أستاذة كتابة وقواعد للكبار.",
                "bio_en": "Writing and grammar instructor for adults.",
                "specialization": "Writing and grammar",
                "is_active": True,
                "approved_at": timezone.now(),
            },
        )
        return users

    def _level(self, code: str):
        return CourseLevel.objects.get(code=code)

    def _seed_courses(self, users):
        rows = [
            {
                "slug": "demo-speaking-a1-short-sentences",
                "teacher": users["ahmed"],
                "level": "A1",
                "status": "published",
                "title_ar": "المحادثة A1: جمل قصيرة بثقة",
                "title_en": "A1 Speaking: Short Sentences with Confidence",
                "description_ar": "كورس فيديو عملي لبناء الجمل القصيرة والتدرب على النطق.",
                "description_en": "A practical video course for short sentences and pronunciation.",
            },
            {
                "slug": "demo-listening-a2-everyday-dialogues",
                "teacher": users["ahmed"],
                "level": "A2",
                "status": "pending_review",
                "title_ar": "الاستماع A2: حوارات يومية",
                "title_en": "A2 Listening: Everyday Dialogues",
                "description_ar": "كورس قيد المراجعة مع ملفات صوتية وأوراق عمل.",
                "description_en": "Pending review course with audio files and worksheets.",
            },
            {
                "slug": "demo-grammar-b1-workplace",
                "teacher": users["sara"],
                "level": "B1",
                "status": "draft",
                "title_ar": "قواعد B1 للعمل",
                "title_en": "B1 Grammar for Work",
                "description_ar": "مسودة كورس للكتابة المهنية.",
                "description_en": "Draft course for professional writing.",
            },
            {
                "slug": "demo-writing-a2-revision",
                "teacher": users["ahmed"],
                "level": "A2",
                "status": "rejected",
                "title_ar": "كتابة A2: يحتاج تعديل",
                "title_en": "A2 Writing: Needs Revision",
                "description_ar": "كورس مرفوض ليظهر سيناريو مراجعة المحتوى.",
                "description_en": "Rejected course to demonstrate review feedback.",
                "review_notes": "Add clearer examples and one worksheet per unit.",
            },
        ]
        courses = {}
        for row in rows:
            course, _ = Course.objects.update_or_create(
                slug=row["slug"],
                defaults={
                    "title": row["title_en"],
                    "title_ar": row["title_ar"],
                    "title_en": row["title_en"],
                    "description": row["description_en"],
                    "description_ar": row["description_ar"],
                    "description_en": row["description_en"],
                    "level": self._level(row["level"]),
                    "teacher": row["teacher"],
                    "created_by": row["teacher"],
                    "language": "bilingual",
                    "status": row["status"],
                    "learning_objectives": "Watch, practice, submit worksheet, receive teacher feedback.",
                    "objectives_ar": "مشاهدة الفيديو، التدريب، إرسال ورقة العمل، واستلام ملاحظات الأستاذ.",
                    "objectives_en": "Watch, practice, submit worksheet, receive teacher feedback.",
                    "estimated_duration_hours": 6,
                    "is_active": row["status"] == "published",
                    "review_notes": row.get("review_notes", ""),
                },
            )
            courses[row["slug"]] = course
        return courses

    def _seed_lessons(self, courses, users):
        lesson_specs = [
            (courses["demo-speaking-a1-short-sentences"], 1, "published", "التحية والتعريف", "Greetings and Introductions", "speaking"),
            (courses["demo-speaking-a1-short-sentences"], 2, "published", "جمل قصيرة عن اليوم", "Short Sentences About Your Day", "speaking"),
            (courses["demo-listening-a2-everyday-dialogues"], 1, "pending_review", "في المقهى", "At the Cafe", "listening"),
            (courses["demo-grammar-b1-workplace"], 1, "draft", "Present Perfect في العمل", "Present Perfect at Work", "grammar"),
            (courses["demo-writing-a2-revision"], 1, "rejected", "رسالة قصيرة", "A Short Message", "writing"),
        ]
        lessons = {}
        for course, order, status, title_ar, title_en, skill in lesson_specs:
            lesson, _ = Lesson.objects.update_or_create(
                course=course,
                order=order,
                defaults={
                    "title": title_en,
                    "title_ar": title_ar,
                    "title_en": title_en,
                    "lesson_type": skill,
                    "cefr_level": course.level.code,
                    "skill": skill,
                    "grammar_topic": "present perfect" if skill == "grammar" else "",
                    "vocabulary_topic": "daily life" if skill in {"speaking", "listening"} else "",
                    "content_html": f"<p>{title_en}</p>",
                    "content_ar": f"شرح عربي مختصر: {title_ar}",
                    "content_en": f"English lesson content: {title_en}",
                    "video_url": "https://example.com/demo-video.mp4",
                    "transcript": "Hello. My name is Ahmed. I study English every day.",
                    "duration_minutes": 12,
                    "status": status,
                    "created_by": course.teacher,
                    "is_active": True,
                },
            )
            LessonResource.objects.update_or_create(
                lesson=lesson,
                resource_type="worksheet",
                title="Worksheet",
                defaults={"url": "https://example.com/demo-worksheet.pdf", "order": 1},
            )
            quiz, _ = LessonQuiz.objects.update_or_create(
                lesson=lesson,
                defaults={
                    "title": f"{title_en} Quiz",
                    "title_ar": f"اختبار {title_ar}",
                    "title_en": f"{title_en} Quiz",
                    "passing_score": 70,
                    "time_limit_minutes": 10,
                    "is_active": True,
                },
            )
            LessonQuestion.objects.update_or_create(
                quiz=quiz,
                order=1,
                defaults={
                    "question_type": "multiple_choice",
                    "question_text": "Choose the correct answer.",
                    "question_text_ar": "اختر الإجابة الصحيحة.",
                    "question_text_en": "Choose the correct answer.",
                    "options": ["Hello", "Yesterday", "Blue"],
                    "correct_answer": "Hello",
                    "explanation": "Hello is a greeting.",
                    "explanation_ar": "Hello تستخدم للتحية.",
                    "explanation_en": "Hello is a greeting.",
                    "difficulty_score": 0.3,
                    "points": 2,
                },
            )
            lessons[(course.slug, order)] = lesson
        return lessons

    def _seed_enrollments(self, users, courses, lessons):
        for student_key, progress in [("lina", 72), ("omar", 38), ("ahmed", 55)]:
            CourseEnrollment.objects.update_or_create(
                user=users[student_key],
                course=courses["demo-speaking-a1-short-sentences"],
                defaults={"status": "active", "progress_percentage": progress},
            )
        CourseEnrollment.objects.update_or_create(
            user=users["omar"],
            course=courses["demo-listening-a2-everyday-dialogues"],
            defaults={"status": "active", "progress_percentage": 18},
        )
        for student_key, score in [("lina", 88), ("omar", 61), ("ahmed", 76)]:
            for lesson in [
                lessons[("demo-speaking-a1-short-sentences", 1)],
                lessons[("demo-speaking-a1-short-sentences", 2)],
            ]:
                CourseLessonProgress.objects.update_or_create(
                    user=users[student_key],
                    lesson=lesson,
                    defaults={
                        "video_completed": score >= 70,
                        "quiz_score": score,
                        "quiz_passed": score >= 70,
                        "completed_at": timezone.now() - timedelta(days=1) if score >= 70 else None,
                    },
                )

    def _seed_assignments(self, users, courses, lessons):
        assignment, _ = TeacherAssignment.objects.update_or_create(
            teacher=users["ahmed"],
            course=courses["demo-speaking-a1-short-sentences"],
            lesson=lessons[("demo-speaking-a1-short-sentences", 2)],
            title_en="Record five short sentences",
            defaults={
                "title_ar": "سجل خمس جمل قصيرة",
                "instructions_ar": "سجل خمس جمل عن يومك وارفع الملف الصوتي أو اكتب النص.",
                "instructions_en": "Record five short sentences about your day or write the text.",
                "assignment_type": "speaking",
                "due_date": timezone.now() + timedelta(days=5),
                "xp_reward": 20,
                "is_active": True,
            },
        )
        StudentAssignmentSubmission.objects.update_or_create(
            assignment=assignment,
            student=users["lina"],
            defaults={
                "text_answer": "I wake up early. I drink tea. I go to class. I read English. I sleep at ten.",
                "score": 90,
                "feedback": "Excellent rhythm. Keep practicing final sounds.",
                "status": "reviewed",
                "reviewed_at": timezone.now(),
            },
        )
        TeacherStudentNote.objects.update_or_create(
            teacher=users["ahmed"],
            student=users["omar"],
            course=courses["demo-speaking-a1-short-sentences"],
            defaults={
                "note": "Needs support with pronunciation and daily plan consistency.",
                "visibility": "academic_admin_visible",
                "needs_support": True,
            },
        )

    def _seed_payments(self, users):
        specs = [
            ("lina", "monthly", "approved", 30000, "DEMO-APPROVED-001"),
            ("omar", "monthly", "pending", 30000, "DEMO-PENDING-001"),
            ("ahmed", "quarterly", "rejected", 50000, "DEMO-REJECTED-001"),
        ]
        for key, plan, status, amount, ref in specs:
            payment, _ = PaymentSubmission.objects.update_or_create(
                transaction_reference=ref,
                defaults={
                    "user": users[key],
                    "plan": plan,
                    "method": "bankak",
                    "amount_sdg": amount,
                    "status": status,
                    "reviewed_by": users["finance"] if status != "pending" else None,
                    "reviewed_at": timezone.now() - timedelta(days=2) if status != "pending" else None,
                    "admin_note": "Demo payment proof.",
                },
            )
            if not payment.screenshot:
                payment.screenshot.save(f"{ref.lower()}.png", ContentFile(PNG_1X1), save=True)

    def _seed_platform_context(self, users, courses):
        PlatformStudentFlag.objects.update_or_create(
            user=users["omar"],
            defaults={"risk_status": "at_risk", "support_status": "Needs teacher follow-up"},
        )
        PlatformStudentNote.objects.get_or_create(
            student=users["omar"],
            author=users["support"],
            note="Student asked for help with speaking homework.",
            defaults={"is_private": False},
        )
        PlatformAuditLog.objects.get_or_create(
            actor=users["academic"],
            target_user=users["ahmed"],
            action_type="course.approve",
            object_type="Course",
            object_id=str(courses["demo-speaking-a1-short-sentences"].pk),
            defaults={
                "description": "Demo approval audit log.",
                "metadata": {"source": "seed_teacher_demo"},
            },
        )

    def _seed_notifications(self, users, courses):
        NotificationEvent.objects.get_or_create(
            event_type=C.TEACHER_COURSE_APPROVED,
            user=users["ahmed"],
            actor=users["academic"],
            defaults={
                "payload": {"course_id": courses["demo-speaking-a1-short-sentences"].pk},
                "status": C.STATUS_PROCESSED,
            },
        )
        NotificationEvent.objects.get_or_create(
            event_type=C.TEACHER_ASSIGNMENT_SUBMITTED,
            user=users["ahmed"],
            actor=users["lina"],
            defaults={
                "payload": {"student": "Lina Mahdi", "assignment": "Record five short sentences"},
                "status": C.STATUS_PROCESSED,
            },
        )

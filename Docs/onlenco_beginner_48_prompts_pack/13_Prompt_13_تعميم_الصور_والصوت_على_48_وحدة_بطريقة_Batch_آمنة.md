## Prompt 13 — تعميم الصور والصوت على 48 وحدة بطريقة Batch آمنة

أنت مهندس EdTech وAI Media Pipeline.

المشروع: Onlenco Academy

بعد نجاح أول batch من الصور والصوت، المطلوب تعميم توليد الوسائط على كورس Beginner كاملًا.

لكن نفذها Batch آمن:
- يمكن توليد وحدة واحدة
- يمكن توليد range من الوحدات
- يمكن توليد كل 48 وحدة بعد التأكيد
- لا تكرر الملفات
- يدعم dry-run
- يسجل تكلفة تقديرية
- يسجل failures
- لا يكسر صفحة الدرس إذا فشل API

Commands:
generate_lesson_images --unit=1 --confirm
generate_lesson_images --from-unit=1 --to-unit=10 --confirm
generate_lesson_images --all --confirm

generate_lesson_audio --unit=1 --confirm
generate_lesson_audio --from-unit=1 --to-unit=10 --confirm
generate_lesson_audio --all --confirm

قواعد:
- لا يكرر media
- يدعم dry-run
- يسجل تكلفة تقديرية
- يسجل عدد الصور والصوتيات
- يفشل بأمان إذا API غير متاح
- لا يكسر صفحة الدرس
- يمكن إعادة تشغيله بعد الفشل
- يحفظ generation status لكل media

أضف report لكل batch:
- Unit number
- Lessons / Topics processed
- Images generated
- Audio generated
- Failures
- Estimated cost
- Duration
- Next recommended batch

أضف اختبارات:
- test_batch_generation_by_unit
- test_batch_generation_by_range
- test_dry_run
- test_no_duplicate_media
- test_failure_does_not_break_lesson_page
- test_generation_status_saved
- test_can_resume_failed_batch

التقرير النهائي بالعربي:
- هل التعميم آمن؟
- كيف أشغل Unit واحدة؟
- كيف أشغل كل 48 وحدة؟
- كيف أوقف العملية؟
- كيف أراقب التكلفة؟
- كيف أعيد تشغيل batch فشل؟

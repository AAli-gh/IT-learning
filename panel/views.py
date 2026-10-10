import os

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import FileResponse, Http404
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST

from courses.models import ClassSession, Enrollment, Lesson, LessonProgress

from .access import confirmed_enrollments, course_for_student, my_announcements, my_courses


def _progress(user, course):
    lessons = list(course.lessons.filter(is_published=True))
    done_ids = set(LessonProgress.objects.filter(user=user, lesson__in=lessons).values_list("lesson_id", flat=True))
    percent = round(100 * len(done_ids) / len(lessons)) if lessons else 0
    return lessons, done_ids, percent


def _my_sessions(user):
    batch_ids = confirmed_enrollments(user).exclude(batch=None).values_list("batch_id", flat=True)
    return ClassSession.objects.filter(batch_id__in=batch_ids).select_related("batch__course")


@login_required
def dashboard(request):
    user = request.user
    courses = []
    for course in my_courses(user):
        _, done, percent = _progress(user, course)
        courses.append({"course": course, "done": len(done), "percent": percent})
    upcoming = _my_sessions(user).filter(starts_at__gte=timezone.now())[:3]
    return render(request, "panel/dashboard.html", {
        "section": "dashboard", "courses": courses, "upcoming": upcoming,
        "announcements": my_announcements(user)[:4],
        "pending": Enrollment.objects.filter(user=user, status=Enrollment.Status.PENDING).select_related("course"),
        "done_lessons": LessonProgress.objects.filter(user=user).count(),
    })


@login_required
def courses(request):
    items = []
    for course in my_courses(request.user):
        lessons, done, percent = _progress(request.user, course)
        items.append({"course": course, "total": len(lessons), "done": len(done), "percent": percent})
    return render(request, "panel/courses.html", {"section": "courses", "items": items})


@login_required
def course_home(request, slug):
    course = course_for_student(request.user, slug)
    lessons, done, percent = _progress(request.user, course)
    return render(request, "panel/course.html", {
        "section": "courses", "course": course, "lessons": lessons, "done": done, "percent": percent,
        "announcements": my_announcements(request.user).filter(course=course)[:5],
        "sessions": _my_sessions(request.user).filter(batch__course=course),
    })


@login_required
def lesson(request, slug, pk):
    course = course_for_student(request.user, slug)
    obj = get_object_or_404(Lesson, pk=pk, course=course, is_published=True)
    lessons, done, percent = _progress(request.user, course)
    index = lessons.index(obj)
    return render(request, "panel/lesson.html", {
        "section": "courses", "course": course, "lesson": obj, "lessons": lessons, "done": done,
        "percent": percent, "completed": obj.pk in done,
        "prev_lesson": lessons[index - 1] if index else None,
        "next_lesson": lessons[index + 1] if index + 1 < len(lessons) else None,
    })


@login_required
@require_POST
def toggle_lesson(request, slug, pk):
    course = course_for_student(request.user, slug)
    obj = get_object_or_404(Lesson, pk=pk, course=course, is_published=True)
    progress, created = LessonProgress.objects.get_or_create(user=request.user, lesson=obj)
    if not created:
        progress.delete()
    if request.headers.get("HX-Request"):
        _, _, percent = _progress(request.user, course)
        return render(request, "panel/partials/lesson_toggle.html", {
            "course": course, "lesson": obj, "completed": created, "percent": percent})
    return redirect("panel:lesson", slug=slug, pk=pk)


@login_required
def lesson_file(request, slug, pk):
    course = course_for_student(request.user, slug)
    obj = get_object_or_404(Lesson, pk=pk, course=course, is_published=True)
    if not obj.attachment:
        raise Http404
    response = FileResponse(obj.attachment.open("rb"), as_attachment=True,
                            filename=os.path.basename(obj.attachment.name))
    response["Cache-Control"] = "private, no-store"
    return response


@login_required
def schedule(request):
    sessions = _my_sessions(request.user)
    now = timezone.now()
    return render(request, "panel/schedule.html", {
        "section": "schedule", "upcoming": sessions.filter(starts_at__gte=now),
        "past": sessions.filter(starts_at__lt=now).order_by("-starts_at")[:20]})


@login_required
def announcements(request):
    return render(request, "panel/announcements.html", {"section": "announcements", "items": my_announcements(request.user)})


@login_required
def enrollments(request):
    items = Enrollment.objects.filter(user=request.user).select_related("course", "batch")
    return render(request, "panel/enrollments.html", {"section": "enrollments", "items": items})


@login_required
@require_POST
def cancel_enrollment(request, pk):
    enrollment = get_object_or_404(Enrollment, pk=pk, user=request.user)
    if enrollment.status == Enrollment.Status.PENDING:
        enrollment.status = Enrollment.Status.CANCELLED
        enrollment.save(update_fields=["status"])
        messages.success(request, "ثبت‌نام لغو شد.")
    else:
        messages.error(request, "فقط ثبت‌نام‌های در انتظار را می‌توان لغو کرد؛ برای بقیه با آموزشگاه تماس بگیرید.")
    return redirect("panel:enrollments")

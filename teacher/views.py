from django.contrib import messages
from django.db.models import Count, Q
from django.http import Http404
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST

from accounts.models import User
from courses.grading import grade_submission
from courses.models import (Announcement, Assignment, Attendance, ClassSession, Enrollment, Lesson, LessonProgress,
                            Submission)
from courses.reports import attendance_summary, student_report

from .access import instructor_required, teacher_course, teaching_courses
from .forms import AnnouncementForm, AssignmentForm, GradeForm, LessonForm, SessionForm


def _confirmed_students(course, batch=None):
    qs = Enrollment.objects.filter(course=course, status=Enrollment.Status.CONFIRMED, user__isnull=False
                                   ).select_related("user", "batch")
    return qs.filter(batch=batch) if batch else qs


def _page(request, template, course, tab, **context):
    return render(request, template, {"course": course, "tab": tab, **context})


@instructor_required
def dashboard(request):
    courses = teaching_courses(request.user).annotate(
        student_count=Count("enrollments", filter=Q(enrollments__status=Enrollment.Status.CONFIRMED), distinct=True))
    ungraded = (Submission.objects.filter(assignment__course__in=courses, score__isnull=True)
                .select_related("user", "assignment__course").order_by("submitted_at"))
    upcoming = (ClassSession.objects.filter(batch__course__in=courses, starts_at__gte=timezone.now())
                .select_related("batch__course")[:6])
    return render(request, "teacher/dashboard.html", {"courses": courses, "ungraded": ungraded[:10],
                                                      "ungraded_count": ungraded.count(), "upcoming": upcoming})


@instructor_required
def course_home(request, slug):
    course = teacher_course(request.user, slug)
    return _page(request, "teacher/course.html", course, "home",
                 student_count=_confirmed_students(course).count(), lesson_count=course.lessons.count(),
                 ungraded=Submission.objects.filter(assignment__course=course, score__isnull=True).count())


# ------------------------------------------------------------------ lessons

@instructor_required
def lessons(request, slug):
    course = teacher_course(request.user, slug)
    return _page(request, "teacher/lessons.html", course, "lessons", lessons=course.lessons.all())


@instructor_required
def lesson_edit(request, slug, pk=None):
    course = teacher_course(request.user, slug)
    lesson = get_object_or_404(Lesson, pk=pk, course=course) if pk else None
    form = LessonForm(request.POST or None, request.FILES or None, instance=lesson)
    if request.method == "POST" and form.is_valid():
        obj = form.save(commit=False)
        obj.course = course
        obj.save()
        messages.success(request, "درس ذخیره شد.")
        return redirect("teacher:lessons", slug=slug)
    return _page(request, "teacher/form.html", course, "lessons", form=form, multipart=True,
                 title="ویرایش درس" if lesson else "درس جدید", back="teacher:lessons")


@instructor_required
@require_POST
def lesson_delete(request, slug, pk):
    course = teacher_course(request.user, slug)
    lesson = get_object_or_404(Lesson, pk=pk, course=course)
    for field in (lesson.video_file, lesson.attachment):
        if field:
            field.delete(save=False)
    lesson.delete()
    messages.success(request, "درس حذف شد.")
    return redirect("teacher:lessons", slug=slug)


# ------------------------------------------------------------ announcements

@instructor_required
def announcements(request, slug):
    course = teacher_course(request.user, slug)
    form = AnnouncementForm(request.POST or None, course=course)
    if request.method == "POST" and form.is_valid():
        obj = form.save(commit=False)
        obj.course = course
        obj.save()  # the signal notifies the students
        messages.success(request, "اطلاعیه ثبت و برای دانشجویان ارسال شد.")
        return redirect("teacher:announcements", slug=slug)
    return _page(request, "teacher/announcements.html", course, "announcements", form=form,
                 items=course.announcements.select_related("batch"))


@instructor_required
@require_POST
def announcement_delete(request, slug, pk):
    course = teacher_course(request.user, slug)
    get_object_or_404(Announcement, pk=pk, course=course).delete()
    return redirect("teacher:announcements", slug=slug)


# -------------------------------------------------------------- assignments

@instructor_required
def assignments(request, slug):
    course = teacher_course(request.user, slug)
    rows = course.assignments.annotate(
        total=Count("submissions"), ungraded=Count("submissions", filter=Q(submissions__score__isnull=True)))
    return _page(request, "teacher/assignments.html", course, "assignments", rows=rows)


@instructor_required
def assignment_edit(request, slug, pk=None):
    course = teacher_course(request.user, slug)
    assignment = get_object_or_404(Assignment, pk=pk, course=course) if pk else None
    form = AssignmentForm(request.POST or None, instance=assignment)
    if request.method == "POST" and form.is_valid():
        obj = form.save(commit=False)
        obj.course = course
        obj.save()
        messages.success(request, "تکلیف ذخیره شد.")
        return redirect("teacher:assignments", slug=slug)
    return _page(request, "teacher/form.html", course, "assignments", form=form,
                 title="ویرایش تکلیف" if assignment else "تکلیف جدید", back="teacher:assignments")


@instructor_required
def assignment(request, slug, pk):
    course = teacher_course(request.user, slug)
    obj = get_object_or_404(Assignment, pk=pk, course=course)
    return _page(request, "teacher/assignment.html", course, "assignments", assignment=obj,
                 submissions=obj.submissions.select_related("user").order_by("score", "submitted_at"))


@instructor_required
def grade(request, slug, pk, submission_id):
    course = teacher_course(request.user, slug)
    obj = get_object_or_404(Assignment, pk=pk, course=course)
    submission = get_object_or_404(Submission.objects.select_related("user"), pk=submission_id, assignment=obj)
    form = GradeForm(request.POST or None, assignment=obj,
                     initial={"score": submission.score, "feedback": submission.feedback})
    if request.method == "POST" and form.is_valid():
        grade_submission(submission, form.cleaned_data["score"], form.cleaned_data["feedback"])
        messages.success(request, "نمره ثبت شد و دانشجو مطلع شد.")
        return redirect("teacher:assignment", slug=slug, pk=pk)
    return _page(request, "teacher/grade.html", course, "assignments", assignment=obj, submission=submission, form=form)


# ----------------------------------------------------------------- sessions

@instructor_required
def sessions(request, slug):
    course = teacher_course(request.user, slug)
    return _page(request, "teacher/sessions.html", course, "sessions",
                 sessions=ClassSession.objects.filter(batch__course=course).select_related("batch"))


@instructor_required
def session_edit(request, slug, pk=None):
    course = teacher_course(request.user, slug)
    session = get_object_or_404(ClassSession, pk=pk, batch__course=course) if pk else None
    form = SessionForm(request.POST or None, instance=session, course=course)
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, "جلسه ذخیره شد.")
        return redirect("teacher:sessions", slug=slug)
    return _page(request, "teacher/form.html", course, "sessions", form=form,
                 title="ویرایش جلسه" if session else "جلسهٔ جدید", back="teacher:sessions")


@instructor_required
@require_POST
def session_delete(request, slug, pk):
    course = teacher_course(request.user, slug)
    get_object_or_404(ClassSession, pk=pk, batch__course=course).delete()
    return redirect("teacher:sessions", slug=slug)


@instructor_required
def attendance(request, slug, pk):
    course = teacher_course(request.user, slug)
    session = get_object_or_404(ClassSession.objects.select_related("batch"), pk=pk, batch__course=course)
    students = [e.user for e in _confirmed_students(course, session.batch).order_by("user__last_name", "user__username")]
    marked = {a.user_id: a for a in Attendance.objects.filter(session=session)}
    valid = {s.value for s in Attendance.Status}
    if request.method == "POST":
        for student in students:  # only students of this batch can be marked
            status = request.POST.get(f"status_{student.pk}")
            if status in valid:
                Attendance.objects.update_or_create(session=session, user=student, defaults={
                    "status": status, "note": request.POST.get(f"note_{student.pk}", "")[:200]})
        messages.success(request, "حضور و غیاب ثبت شد.")
        return redirect("teacher:attendance", slug=slug, pk=pk)
    rows = [{"user": s, "record": marked.get(s.pk)} for s in students]
    return _page(request, "teacher/attendance.html", course, "sessions", session=session, rows=rows,
                 statuses=Attendance.Status.choices)


# ----------------------------------------------------------------- students

@instructor_required
def students(request, slug):
    course = teacher_course(request.user, slug)
    lessons_total = course.lessons.filter(is_published=True).count()
    rows = []
    for enrollment in _confirmed_students(course):
        user = enrollment.user
        done = LessonProgress.objects.filter(user=user, lesson__course=course, lesson__is_published=True).count()
        grades = list(Submission.objects.filter(user=user, assignment__course=course, score__isnull=False
                                                ).values_list("score", flat=True))
        rows.append({"enrollment": enrollment, "user": user,
                     "progress": round(100 * done / lessons_total) if lessons_total else 0,
                     "attendance": attendance_summary(user, course)["rate"],
                     "average": round(sum(grades) / len(grades)) if grades else None})
    return _page(request, "teacher/students.html", course, "students", rows=rows)


@instructor_required
def student_detail(request, slug, user_id):
    course = teacher_course(request.user, slug)
    if not _confirmed_students(course).filter(user_id=user_id).exists():
        raise Http404
    student = get_object_or_404(User, pk=user_id)
    return _page(request, "teacher/student.html", course, "students", student=student,
                 r=student_report(student, course))

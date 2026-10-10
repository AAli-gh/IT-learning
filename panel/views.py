import os

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import FileResponse, Http404
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST

from django.conf import settings
from django.core.exceptions import ValidationError
from django.http import HttpResponseForbidden

from courses.certificates import issue_certificate, requirements
from courses.models import (Assignment, Certificate, ClassSession, Enrollment, Lesson, LessonProgress, Quiz, QuizAttempt,
                            Submission)

from .access import confirmed_enrollments, course_for_student, my_announcements, my_courses


def _progress(user, course):
    lessons = list(course.lessons.filter(is_published=True))
    done_ids = set(LessonProgress.objects.filter(user=user, lesson__in=lessons).values_list("lesson_id", flat=True))
    percent = round(100 * len(done_ids) / len(lessons)) if lessons else 0
    return lessons, done_ids, percent


def _my_sessions(user):
    batch_ids = confirmed_enrollments(user).exclude(batch=None).values_list("batch_id", flat=True)
    return ClassSession.objects.filter(batch_id__in=batch_ids).select_related("batch__course")


def _todo_assignments(user):
    """Published assignments of my courses that I haven't submitted yet (nearest deadline first)."""
    course_ids = confirmed_enrollments(user).values_list("course_id", flat=True)
    submitted = Submission.objects.filter(user=user).values_list("assignment_id", flat=True)
    return (Assignment.objects.filter(course_id__in=course_ids, is_published=True).exclude(pk__in=submitted)
            .select_related("course").order_by("due_at", "id"))


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
        "todo": _todo_assignments(user)[:4],
        "certificate_count": Certificate.objects.filter(user=user, is_revoked=False).count(),
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
        "quizzes": _quiz_rows(request.user, course),
        "assignments": _assignment_rows(request.user, course),
        "checklist": requirements(request.user, course),
        "certificate": Certificate.objects.filter(user=request.user, course=course).first(),
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


# ---------------------------------------------------------------- quizzes

def _quiz_rows(user, course):
    attempts = QuizAttempt.objects.filter(user=user, quiz__course=course, submitted_at__isnull=False)
    best = {}
    for a in attempts:
        if a.quiz_id not in best or a.score_percent > best[a.quiz_id].score_percent:
            best[a.quiz_id] = a
    return [{"quiz": q, "best": best.get(q.pk)} for q in course.quizzes.filter(is_published=True)]


def _quiz_for(user, slug, pk):
    course = course_for_student(user, slug)
    return course, get_object_or_404(Quiz, pk=pk, course=course, is_published=True)


@login_required
def quiz_detail(request, slug, pk):
    course, quiz = _quiz_for(request.user, slug, pk)
    attempts = QuizAttempt.objects.filter(user=request.user, quiz=quiz)
    finished = attempts.filter(submitted_at__isnull=False)
    out_of_attempts = bool(quiz.max_attempts) and finished.count() >= quiz.max_attempts
    return render(request, "panel/quiz.html", {
        "section": "courses", "course": course, "quiz": quiz, "attempts": finished,
        "open_attempt": attempts.filter(submitted_at__isnull=True).first(),
        "out_of_attempts": out_of_attempts, "question_count": quiz.questions.count(),
    })


@login_required
@require_POST
def quiz_start(request, slug, pk):
    course, quiz = _quiz_for(request.user, slug, pk)
    attempt = QuizAttempt.objects.filter(user=request.user, quiz=quiz, submitted_at__isnull=True).first()
    if attempt is None:
        finished = QuizAttempt.objects.filter(user=request.user, quiz=quiz, submitted_at__isnull=False).count()
        if quiz.max_attempts and finished >= quiz.max_attempts:
            messages.error(request, "تعداد دفعات مجاز شرکت در این آزمون تمام شده است.")
            return redirect("panel:quiz", slug=slug, pk=pk)
        if not quiz.questions.exists():
            messages.error(request, "این آزمون هنوز سؤالی ندارد.")
            return redirect("panel:quiz", slug=slug, pk=pk)
        attempt = QuizAttempt.objects.create(user=request.user, quiz=quiz)
    return redirect("panel:quiz_attempt", slug=slug, pk=pk, attempt_id=attempt.pk)


@login_required
def quiz_attempt(request, slug, pk, attempt_id):
    course, quiz = _quiz_for(request.user, slug, pk)
    attempt = get_object_or_404(QuizAttempt, pk=attempt_id, quiz=quiz, user=request.user)
    if not attempt.is_open:
        return redirect("panel:quiz_result", slug=slug, pk=pk, attempt_id=attempt.pk)
    if request.method == "POST":
        answers = {}
        for key, value in request.POST.items():
            if key.startswith("q") and key[1:].isdigit() and value.isdigit():
                answers[int(key[1:])] = int(value)
        attempt.grade(answers)
        if attempt.timed_out:
            messages.error(request, "زمان آزمون تمام شده بود؛ پاسخ‌ها ثبت نشد.")
        return redirect("panel:quiz_result", slug=slug, pk=pk, attempt_id=attempt.pk)
    # Choices are listed without ``is_correct`` so the answer key never reaches the browser.
    questions = quiz.questions.prefetch_related("choices")
    return render(request, "panel/quiz_attempt.html", {
        "section": "courses", "course": course, "quiz": quiz, "attempt": attempt, "questions": questions})


@login_required
def quiz_result(request, slug, pk, attempt_id):
    course, quiz = _quiz_for(request.user, slug, pk)
    attempt = get_object_or_404(QuizAttempt, pk=attempt_id, quiz=quiz, user=request.user)
    if attempt.is_open:
        return redirect("panel:quiz_attempt", slug=slug, pk=pk, attempt_id=attempt.pk)
    rows = []
    for q in quiz.questions.prefetch_related("choices"):
        chosen = attempt.answers.get(str(q.pk))
        correct = next((c for c in q.choices.all() if c.is_correct), None)
        rows.append({"question": q, "chosen": next((c for c in q.choices.all() if c.pk == chosen), None),
                     "correct": correct, "is_right": bool(correct and correct.pk == chosen)})
    return render(request, "panel/quiz_result.html", {
        "section": "courses", "course": course, "quiz": quiz, "attempt": attempt, "rows": rows,
        "can_retry": not quiz.max_attempts or QuizAttempt.objects.filter(
            user=request.user, quiz=quiz, submitted_at__isnull=False).count() < quiz.max_attempts})


# ------------------------------------------------------------ assignments

def _assignment_rows(user, course):
    subs = {s.assignment_id: s for s in Submission.objects.filter(user=user, assignment__course=course)}
    return [{"assignment": a, "submission": subs.get(a.pk)} for a in course.assignments.filter(is_published=True)]


def _validate_upload(upload):
    if upload.size > settings.MAX_SUBMISSION_MB * 1024 * 1024:
        raise ValidationError(f"حجم فایل نباید بیشتر از {settings.MAX_SUBMISSION_MB} مگابایت باشد.")
    from django.core.validators import FileExtensionValidator

    FileExtensionValidator(Submission.ALLOWED_EXTENSIONS)(upload)


@login_required
def assignment_detail(request, slug, pk):
    course = course_for_student(request.user, slug)
    assignment = get_object_or_404(Assignment, pk=pk, course=course, is_published=True)
    submission = Submission.objects.filter(assignment=assignment, user=request.user).first()
    error = None
    if request.method == "POST":
        text = request.POST.get("text", "").strip()
        upload = request.FILES.get("file")
        if submission and submission.is_graded:
            error = "این تکلیف نمره‌گذاری شده و قابل ویرایش نیست."
        elif assignment.is_past_due and not assignment.allow_late:
            error = "مهلت تحویل این تکلیف تمام شده است."
        elif not text and not upload and not (submission and submission.file):
            error = "متن یا فایل پاسخ را وارد کنید."
        else:
            try:
                if upload:
                    _validate_upload(upload)
            except ValidationError as exc:
                error = " ".join(exc.messages)
        if error is None:
            submission = submission or Submission(assignment=assignment, user=request.user)
            submission.text = text
            if upload:
                submission.file = upload
            submission.submitted_at = timezone.now()
            submission.save()
            messages.success(request, "پاسخ شما ثبت شد.")
            return redirect("panel:assignment", slug=slug, pk=pk)
    return render(request, "panel/assignment.html", {
        "section": "courses", "course": course, "assignment": assignment, "submission": submission,
        "error": error, "max_mb": settings.MAX_SUBMISSION_MB,
        "locked": bool(submission and submission.is_graded) or (assignment.is_past_due and not assignment.allow_late)})


@login_required
def submission_file(request, pk):
    """Owner or grading staff only."""
    submission = get_object_or_404(Submission.objects.select_related("assignment"), pk=pk)
    is_grader = request.user.is_active and request.user.has_perm("courses.change_submission")
    if submission.user_id != request.user.pk and not is_grader:
        raise Http404
    if not submission.file:
        raise Http404
    response = FileResponse(submission.file.open("rb"), as_attachment=True, filename=os.path.basename(submission.file.name))
    response["Cache-Control"] = "private, no-store"
    return response


# ----------------------------------------------------------- certificates

@login_required
def certificates(request):
    return render(request, "panel/certificates.html", {
        "section": "certificates",
        "items": Certificate.objects.filter(user=request.user, is_revoked=False).select_related("course")})


@login_required
@require_POST
def certificate_issue(request, slug):
    course = course_for_student(request.user, slug)
    certificate = issue_certificate(request.user, course)
    if certificate is None:
        messages.error(request, "هنوز همهٔ شرایط دریافت گواهی را تکمیل نکرده‌اید.")
        return redirect("panel:course", slug=slug)
    messages.success(request, "گواهی شما صادر شد.")
    return redirect("courses:certificate", code=certificate.code)

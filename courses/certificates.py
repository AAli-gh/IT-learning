"""Certificate rules: what a student must finish, and issuing the certificate."""

from notifications.services import notify

from .models import Certificate, Enrollment, LessonProgress, QuizAttempt, Submission


def requirements(user, course):
    """Checklist of everything required for the certificate: ``[{"label", "done", "kind"}]``."""
    items = []
    lessons = list(course.lessons.filter(is_published=True))
    if lessons:
        done = LessonProgress.objects.filter(user=user, lesson__in=lessons).count()
        items.append({"kind": "lessons", "label": f"انجام همهٔ درس‌ها ({done} از {len(lessons)})",
                      "done": done == len(lessons)})
    passed_quizzes = set(QuizAttempt.objects.filter(user=user, quiz__course=course, passed=True)
                         .values_list("quiz_id", flat=True))
    for quiz in course.quizzes.filter(is_published=True):
        items.append({"kind": "quiz", "label": f"قبولی در آزمون «{quiz.title}»", "done": quiz.pk in passed_quizzes})
    submissions = {s.assignment_id: s for s in Submission.objects.filter(user=user, assignment__course=course)
                   .select_related("assignment")}
    for assignment in course.assignments.filter(is_published=True):
        sub = submissions.get(assignment.pk)
        items.append({"kind": "assignment", "label": f"قبولی در تکلیف «{assignment.title}»",
                      "done": bool(sub and sub.passed)})
    return items


def is_eligible(user, course):
    items = requirements(user, course)
    return bool(items) and all(i["done"] for i in items)


def issue_certificate(user, course):
    """The user's certificate for ``course``, issued now if they qualify; ``None`` otherwise."""
    existing = Certificate.objects.filter(user=user, course=course).first()
    if existing:
        return existing
    enrollment = Enrollment.objects.filter(user=user, course=course, status=Enrollment.Status.CONFIRMED).first()
    if not enrollment or not is_eligible(user, course):
        return None
    cert = Certificate.objects.create(user=user, course=course, holder_name=enrollment.full_name or user.display_name)
    notify(user, f"گواهی «{course.title}» صادر شد", "تبریک! گواهی پایان دورهٔ شما آماده است.", cert.get_absolute_url())
    return cert

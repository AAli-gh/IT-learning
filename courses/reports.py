"""Student report card: progress, quiz and assignment results, attendance and certificate status."""

from django.utils import timezone

from .certificates import requirements
from .models import Attendance, Certificate, ClassSession, Enrollment, LessonProgress, QuizAttempt, Submission


def attendance_summary(user, course):
    """Counts over the past sessions of the batches the student is confirmed in; excused absences don't count against."""
    batch_ids = Enrollment.objects.filter(user=user, course=course, status=Enrollment.Status.CONFIRMED
                                          ).exclude(batch=None).values_list("batch_id", flat=True)
    sessions = list(ClassSession.objects.filter(batch_id__in=batch_ids, starts_at__lte=timezone.now()))
    records = {a.session_id: a.status for a in Attendance.objects.filter(user=user, session__in=sessions)}
    counts = {s.value: 0 for s in Attendance.Status}
    for session in sessions:
        counts[records.get(session.pk, Attendance.Status.ABSENT)] += 1  # unmarked past sessions count as absent
    attended = counts["present"] + counts["late"]
    counted = len(sessions) - counts["excused"]
    return {**counts, "total": len(sessions), "attended": attended,
            "rate": round(100 * attended / counted) if counted else None}


def student_report(user, course):
    lessons = list(course.lessons.filter(is_published=True))
    done = LessonProgress.objects.filter(user=user, lesson__in=lessons).count()
    best = {}
    for attempt in QuizAttempt.objects.filter(user=user, quiz__course=course, submitted_at__isnull=False):
        if attempt.quiz_id not in best or attempt.score_percent > best[attempt.quiz_id].score_percent:
            best[attempt.quiz_id] = attempt
    submissions = {s.assignment_id: s for s in Submission.objects.filter(user=user, assignment__course=course)}
    return {
        "lessons_done": done, "lessons_total": len(lessons),
        "lessons_percent": round(100 * done / len(lessons)) if lessons else 0,
        "quizzes": [{"quiz": q, "best": best.get(q.pk)} for q in course.quizzes.filter(is_published=True)],
        "assignments": [{"assignment": a, "submission": submissions.get(a.pk)}
                        for a in course.assignments.filter(is_published=True)],
        "attendance": attendance_summary(user, course),
        "checklist": requirements(user, course),
        "certificate": Certificate.objects.filter(user=user, course=course, is_revoked=False).first(),
    }

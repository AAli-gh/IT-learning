from django.urls import reverse
from django.utils import timezone

from notifications.services import notify


def grade_submission(submission, score, feedback=""):
    """Store a grade (capped to the assignment's maximum) and tell the student. Used by the admin and teacher panel."""
    assignment = submission.assignment
    submission.score = max(0, min(int(score), assignment.max_score))
    submission.feedback = feedback
    submission.graded_at = timezone.now()
    submission.save()
    notify(submission.user, f"نمرهٔ تکلیف «{assignment.title}»",
           f"نمرهٔ شما: {submission.score} از {assignment.max_score}\n\n{feedback}".strip(),
           reverse("panel:assignment", args=[assignment.course.slug, assignment.pk]))
    return submission

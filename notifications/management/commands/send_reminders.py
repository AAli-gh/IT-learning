"""Remind students about classes starting soon and assignment deadlines. Run it daily (cron / scheduled task).

    python manage.py send_reminders [--hours 24]

Safe to run repeatedly: every reminder is de-duplicated per person.
"""

import datetime

from django.core.management.base import BaseCommand
from django.urls import reverse
from django.utils import timezone

from courses.models import Assignment, ClassSession, Enrollment, Submission
from notifications.services import notify


class Command(BaseCommand):
    help = "Send class and assignment-deadline reminders."

    def add_arguments(self, parser):
        parser.add_argument("--hours", type=int, default=24, help="look-ahead window (default 24)")

    def handle(self, *args, **options):
        now = timezone.now()
        horizon = now + datetime.timedelta(hours=options["hours"])
        sent = 0

        sessions = ClassSession.objects.filter(starts_at__gt=now, starts_at__lte=horizon, reminded_at__isnull=True
                                               ).select_related("batch__course")
        for session in sessions:
            students = Enrollment.objects.filter(batch=session.batch, status=Enrollment.Status.CONFIRMED,
                                                 user__isnull=False).select_related("user")
            when = timezone.localtime(session.starts_at).strftime("%H:%M")
            for enrollment in students:
                sent += bool(notify(enrollment.user, f"یادآوری کلاس: {session.title}",
                                    f"{session.batch.course.title} — امروز/فردا ساعت {when}"
                                    + (f" — {session.place}" if session.place else ""),
                                    reverse("panel:schedule"), dedupe_key=f"session:{session.pk}"))
            session.reminded_at = now
            session.save(update_fields=["reminded_at"])

        due = Assignment.objects.filter(is_published=True, due_at__gt=now, due_at__lte=horizon).select_related("course")
        for assignment in due:
            submitted = Submission.objects.filter(assignment=assignment).values_list("user_id", flat=True)
            students = Enrollment.objects.filter(course=assignment.course, status=Enrollment.Status.CONFIRMED,
                                                 user__isnull=False).exclude(user_id__in=submitted).select_related("user")
            for enrollment in students:
                sent += bool(notify(enrollment.user, f"مهلت تحویل تکلیف: {assignment.title}",
                                    f"{assignment.course.title} — مهلت تحویل نزدیک است.",
                                    reverse("panel:assignment", args=[assignment.course.slug, assignment.pk]),
                                    dedupe_key=f"due:{assignment.pk}"))
        self.stdout.write(self.style.SUCCESS(f"{sent} reminder(s) sent."))

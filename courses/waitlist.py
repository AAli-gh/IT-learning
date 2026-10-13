"""Waiting list for full batches: offer a freed seat to the next person, hold it for HOLD_HOURS."""

import datetime

from django.urls import reverse
from django.utils import timezone

from core.notify import notify_student
from notifications.services import notify

from .models import WaitlistEntry


def release_seats(batch):
    """Expire stale offers, then offer every free, un-held seat of ``batch`` to the first people waiting."""
    now = timezone.now()
    batch.waitlist.filter(status=WaitlistEntry.Status.NOTIFIED,
                          notified_at__lt=now - datetime.timedelta(hours=WaitlistEntry.HOLD_HOURS)
                          ).update(status=WaitlistEntry.Status.EXPIRED)
    if not batch.is_open:
        return []
    free = batch.seats_left - batch.held_seats
    if free <= 0:
        return []
    offered = []
    for entry in batch.waitlist.filter(status=WaitlistEntry.Status.WAITING).order_by("created_at")[:free]:
        entry.status = WaitlistEntry.Status.NOTIFIED
        entry.notified_at = now
        entry.save(update_fields=["status", "notified_at"])
        title = f"جای خالی در «{batch.course.title}»"
        body = (f"{entry.full_name} عزیز، یک جای خالی در {batch.title or 'دوره'} باز شد. "
                f"تا {WaitlistEntry.HOLD_HOURS} ساعت فرصت دارید با همین شماره ثبت‌نام کنید.")
        url = reverse("courses:detail", args=[batch.course.slug])
        if entry.user:
            notify(entry.user, title, body, url, dedupe_key=f"waitlist:{entry.pk}")
        else:
            notify_student(entry.email, title, body)
        offered.append(entry)
    return offered

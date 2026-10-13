from django.db import transaction
from django.db.models.signals import post_delete, post_save, pre_save
from django.urls import reverse

from core.notify import notify_student
from notifications.services import notify, notify_many

from .models import Announcement, Batch, Enrollment, WaitlistEntry
from .waitlist import release_seats


def _release_later(batch):
    if batch is not None:
        transaction.on_commit(lambda: release_seats(Batch.objects.select_related("course").get(pk=batch.pk)))


def enrollment_pre_save(sender, instance, **kwargs):
    instance._old_status = (Enrollment.objects.filter(pk=instance.pk).values_list("status", flat=True).first()
                            if instance.pk else None)


def enrollment_post_save(sender, instance, created, **kwargs):
    if instance.batch_id and created:
        # The person registered: close their waiting-list entry.
        WaitlistEntry.objects.filter(batch_id=instance.batch_id, phone=instance.phone,
                                     status__in=[WaitlistEntry.Status.WAITING, WaitlistEntry.Status.NOTIFIED]
                                     ).update(status=WaitlistEntry.Status.ENROLLED)
    if instance.status == Enrollment.Status.CANCELLED:
        _release_later(instance.batch)
    if instance.status == Enrollment.Status.CONFIRMED and getattr(instance, "_old_status", None) != instance.status:
        title = f"ثبت‌نام شما در «{instance.course.title}» تأیید شد"
        body = f"{instance.full_name} عزیز، ثبت‌نام شما تأیید شد. از پنل دانشجو می‌توانید محتوا و برنامهٔ کلاس‌ها را ببینید."
        if instance.user:
            notify(instance.user, title, body, reverse("panel:course", args=[instance.course.slug]))
        else:
            notify_student(instance.email, title, body)


def enrollment_post_delete(sender, instance, **kwargs):
    _release_later(instance.batch)


def batch_post_save(sender, instance, **kwargs):
    _release_later(instance)  # capacity raised or batch reopened


def announcement_post_save(sender, instance, **kwargs):
    if not instance.is_published:
        return
    from panel.access import announcement_audience  # local import: panel imports courses

    notify_many(announcement_audience(instance), instance.title, instance.body,
                reverse("panel:announcements"), dedupe_key=f"announcement:{instance.pk}")


def connect():
    pre_save.connect(enrollment_pre_save, sender=Enrollment, dispatch_uid="enr_pre")
    post_save.connect(enrollment_post_save, sender=Enrollment, dispatch_uid="enr_post")
    post_delete.connect(enrollment_post_delete, sender=Enrollment, dispatch_uid="enr_del")
    post_save.connect(batch_post_save, sender=Batch, dispatch_uid="batch_post")
    post_save.connect(announcement_post_save, sender=Announcement, dispatch_uid="ann_post")

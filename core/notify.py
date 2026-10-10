"""Email notifications. Failures never break the request (fail_silently)."""

from django.conf import settings
from django.core.mail import send_mail

from .models import SiteSettings


def _staff_address():
    return SiteSettings.load().contact_email or (settings.ADMINS[0][1] if settings.ADMINS else "")


def notify_staff(subject, body):
    to = _staff_address()
    if to:
        send_mail(subject, body, settings.DEFAULT_FROM_EMAIL, [to], fail_silently=True)


def notify_student(email, subject, body):
    if email:
        send_mail(subject, body, settings.DEFAULT_FROM_EMAIL, [email], fail_silently=True)

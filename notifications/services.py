"""Create in-panel notifications and (optionally) mirror them by email. Never raises into the request."""

import logging

from django.conf import settings
from django.core.mail import send_mail
from django.db import IntegrityError, transaction

from .models import Notification

logger = logging.getLogger(__name__)


def _safe_path(url):
    """Notification links are internal paths only (guards the redirect in the panel against open redirects)."""
    return url if url.startswith("/") and not url.startswith("//") else ""


def notify(user, title, body="", url="", dedupe_key="", email=True):
    """Notify ``user``. Returns the Notification, or ``None`` if ``dedupe_key`` was already used for this user."""
    try:
        with transaction.atomic():
            note = Notification.objects.create(user=user, title=title[:200], body=body, url=_safe_path(url),
                                               dedupe_key=dedupe_key)
    except IntegrityError:
        return None
    if email and user.email and getattr(user, "email_notifications", True):
        link = f"\n\n{settings.SITE_URL.rstrip('/')}{note.url}" if note.url else ""
        send_mail(title, f"{body}{link}".strip(), settings.DEFAULT_FROM_EMAIL, [user.email], fail_silently=True)
    return note


def notify_many(users, title, body="", url="", dedupe_key="", email=True):
    return [n for n in (notify(u, title, body, url, dedupe_key, email) for u in users) if n]

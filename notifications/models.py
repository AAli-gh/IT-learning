from django.conf import settings
from django.db import models
from django.db.models import Q


class Notification(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="notifications")
    title = models.CharField("عنوان", max_length=200)
    body = models.TextField("متن", blank=True)
    url = models.CharField("لینک", max_length=300, blank=True, help_text="فقط مسیر داخلی سایت، مثل /panel/")
    is_read = models.BooleanField("خوانده شده", default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    # Prevents sending the same reminder twice (e.g. "session:12"); empty for ordinary notifications.
    dedupe_key = models.CharField(max_length=80, blank=True)

    class Meta:
        ordering = ["-created_at", "-id"]
        constraints = [models.UniqueConstraint(fields=["user", "dedupe_key"], condition=~Q(dedupe_key=""),
                                               name="unique_notification_dedupe")]
        verbose_name = "اعلان"
        verbose_name_plural = "اعلان‌ها"

    def __str__(self):
        return f"{self.user}: {self.title}"

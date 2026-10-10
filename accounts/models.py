from django.contrib.auth.models import AbstractUser
from django.db import models


class User(AbstractUser):
    """Site user. Instructors are users with ``is_instructor=True``."""

    bio = models.TextField("درباره من", blank=True)
    avatar = models.ImageField("آواتار", upload_to="avatars/", blank=True)
    phone = models.CharField("شماره تماس", max_length=20, blank=True)
    website = models.URLField("وب‌سایت", blank=True)
    github = models.CharField("گیت‌هاب", max_length=100, blank=True)
    is_instructor = models.BooleanField("مدرس", default=False)

    class Meta:
        verbose_name = "کاربر"
        verbose_name_plural = "کاربران"

    def __str__(self):
        return self.display_name

    @property
    def display_name(self):
        return self.get_full_name() or self.username

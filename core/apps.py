from django.apps import AppConfig


class CoreConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "core"
    verbose_name = "تنظیمات سایت"

    def ready(self):
        from courses.models import Batch, Category, Course

        from .models import Page, SiteSettings
        from .signals import connect

        connect(Page, SiteSettings, Category, Course, Batch)

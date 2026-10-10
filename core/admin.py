from django.contrib import admin
from django.shortcuts import redirect
from django.urls import reverse

from .models import Page, SiteSettings


@admin.register(Page)
class PageAdmin(admin.ModelAdmin):
    list_display = ("title", "slug", "is_published", "show_in_footer", "order")
    list_editable = ("is_published", "show_in_footer", "order")
    prepopulated_fields = {"slug": ("title",)}
    search_fields = ("title", "body")
    fieldsets = (
        (None, {"fields": ("title", "slug", "body", "is_published", "show_in_footer", "order")}),
        ("SEO", {"fields": ("meta_title", "meta_description"), "classes": ("collapse",)}),
    )


@admin.register(SiteSettings)
class SiteSettingsAdmin(admin.ModelAdmin):
    fieldsets = (
        ("هویت و SEO", {"fields": ("site_name", "site_description", "default_og_image")}),
        ("تماس و شبکه‌های اجتماعی", {"fields": (
            "contact_email", "contact_phone", "address",
            "instagram_url", "telegram_url", "twitter_url", "linkedin_url", "github_url")}),
        ("پیشرفته", {"fields": ("head_scripts",), "classes": ("collapse",)}),
    )

    def has_add_permission(self, request):
        return not SiteSettings.objects.exists()

    def has_delete_permission(self, request, obj=None):
        return False

    def changelist_view(self, request, extra_context=None):
        obj = SiteSettings.load()
        return redirect(reverse("admin:core_sitesettings_change", args=[obj.pk]))

    def has_change_permission(self, request, obj=None):
        # head_scripts is injected unescaped, so only superusers may edit settings.
        return request.user.is_superuser

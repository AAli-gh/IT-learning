from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin

from .models import User


@admin.register(User)
class UserAdmin(BaseUserAdmin):
    list_display = ("username", "email", "get_full_name", "is_instructor", "is_staff", "date_joined")
    list_filter = ("is_instructor", "is_staff", "is_superuser", "is_active")
    fieldsets = BaseUserAdmin.fieldsets + (
        ("پروفایل", {"fields": ("bio", "avatar", "phone", "website", "github", "is_instructor")}),
    )

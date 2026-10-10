from django.contrib import admin

from .models import Batch, Category, Course, Enrollment, Faq, Review, Topic


@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    list_display = ("name", "slug", "order", "show_on_home")
    list_editable = ("order", "show_on_home")
    prepopulated_fields = {"slug": ("name",)}


class TopicInline(admin.TabularInline):
    model = Topic
    extra = 3


class BatchInline(admin.TabularInline):
    model = Batch
    extra = 1


@admin.register(Course)
class CourseAdmin(admin.ModelAdmin):
    list_display = ("title", "category", "level", "price", "instructor", "is_published", "is_featured")
    list_filter = ("category", "level", "is_published", "is_featured")
    list_editable = ("is_published", "is_featured")
    search_fields = ("title", "summary", "magazine_tag")
    prepopulated_fields = {"slug": ("title",)}
    inlines = [TopicInline, BatchInline]
    fieldsets = (
        (None, {"fields": ("title", "slug", "category", "instructor", "level", "summary", "description", "cover")}),
        ("جزئیات", {"fields": ("price", "duration_hours", "prerequisites")}),
        ("اتصال به مجله", {"fields": ("magazine_tag",)}),
        ("انتشار", {"fields": ("is_published", "is_featured", "published_at")}),
        ("SEO", {"fields": ("meta_title", "meta_description"), "classes": ("collapse",)}),
    )


@admin.register(Enrollment)
class EnrollmentAdmin(admin.ModelAdmin):
    list_display = ("full_name", "phone", "course", "batch", "status", "created_at")
    list_filter = ("status", "course")
    list_editable = ("status",)
    search_fields = ("full_name", "phone", "email")
    date_hierarchy = "created_at"
    actions = ["confirm", "cancel"]

    @admin.action(description="تأیید ثبت‌نام‌های انتخاب‌شده")
    def confirm(self, request, queryset):
        queryset.update(status=Enrollment.Status.CONFIRMED)

    @admin.action(description="لغو ثبت‌نام‌های انتخاب‌شده")
    def cancel(self, request, queryset):
        queryset.update(status=Enrollment.Status.CANCELLED)


@admin.register(Review)
class ReviewAdmin(admin.ModelAdmin):
    list_display = ("course", "user", "rating", "is_approved", "is_featured", "created_at")
    list_filter = ("is_approved", "is_featured", "rating", "course")
    list_editable = ("is_approved", "is_featured")
    search_fields = ("text", "user__username")


@admin.register(Faq)
class FaqAdmin(admin.ModelAdmin):
    list_display = ("question", "course", "order", "is_published")
    list_editable = ("order", "is_published")
    list_filter = ("is_published", "course")
    search_fields = ("question", "answer")

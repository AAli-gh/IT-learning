from django import forms
from django.contrib import admin
from django.urls import reverse
from django.utils.html import format_html

from .models import (Announcement, Assignment, Batch, Category, Certificate, Choice, ClassSession, Course, Enrollment,
                     Faq, Lesson, Question, Quiz, QuizAttempt, Review, Submission, Topic, WaitlistEntry,
                     Attendance)


@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    list_display = ("name", "slug", "order", "show_on_home")
    list_editable = ("order", "show_on_home")
    prepopulated_fields = {"slug": ("name",)}


class TopicInline(admin.TabularInline):
    model = Topic
    extra = 3


class LessonInline(admin.StackedInline):
    model = Lesson
    extra = 0
    classes = ("collapse",)


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
    inlines = [TopicInline, BatchInline, LessonInline]
    fieldsets = (
        (None, {"fields": ("title", "slug", "category", "instructor", "level", "summary", "description", "cover")}),
        ("جزئیات", {"fields": ("price", "duration_hours", "prerequisites")}),
        ("اتصال به مجله", {"fields": ("magazine_tag",)}),
        ("انتشار", {"fields": ("is_published", "is_featured", "published_at")}),
        ("SEO", {"fields": ("meta_title", "meta_description"), "classes": ("collapse",)}),
    )


@admin.register(Enrollment)
class EnrollmentAdmin(admin.ModelAdmin):
    list_display = ("full_name", "phone", "course", "batch", "status", "price", "paid_amount", "created_at")
    list_filter = ("status", "course")
    list_editable = ("status", "paid_amount")
    search_fields = ("full_name", "phone", "email")
    date_hierarchy = "created_at"
    actions = ["confirm", "cancel"]

    @admin.action(description="تأیید ثبت‌نام‌های انتخاب‌شده")
    def confirm(self, request, queryset):
        for enrollment in queryset.exclude(status=Enrollment.Status.CONFIRMED).select_related("course", "user"):
            enrollment.status = Enrollment.Status.CONFIRMED
            enrollment.save(update_fields=["status"])  # the signal sends the confirmation

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


@admin.register(ClassSession)
class ClassSessionAdmin(admin.ModelAdmin):
    list_display = ("title", "batch", "starts_at", "place")
    list_filter = ("batch__course",)
    date_hierarchy = "starts_at"


@admin.register(Announcement)
class AnnouncementAdmin(admin.ModelAdmin):
    list_display = ("title", "course", "batch", "is_published", "created_at")
    list_filter = ("course", "is_published")
    list_editable = ("is_published",)


class ChoiceInlineFormSet(forms.BaseInlineFormSet):
    def clean(self):
        super().clean()
        live = [f.cleaned_data for f in self.forms
                if f.cleaned_data and not f.cleaned_data.get("DELETE") and f.cleaned_data.get("text")]
        if len(live) < 2:
            raise forms.ValidationError("هر سؤال باید حداقل دو گزینه داشته باشد.")
        if sum(1 for c in live if c.get("is_correct")) != 1:
            raise forms.ValidationError("دقیقاً یک گزینه باید «پاسخ صحیح» باشد.")


class ChoiceInline(admin.TabularInline):
    model = Choice
    formset = ChoiceInlineFormSet
    extra = 4


class QuestionInline(admin.TabularInline):
    model = Question
    extra = 0
    show_change_link = True  # choices are edited on the question page


@admin.register(Quiz)
class QuizAdmin(admin.ModelAdmin):
    list_display = ("title", "course", "pass_percent", "time_limit_minutes", "max_attempts", "is_published")
    list_filter = ("course", "is_published")
    list_editable = ("is_published",)
    inlines = [QuestionInline]


@admin.register(Question)
class QuestionAdmin(admin.ModelAdmin):
    list_display = ("text", "quiz", "points", "order")
    list_filter = ("quiz__course", "quiz")
    inlines = [ChoiceInline]


@admin.register(QuizAttempt)
class QuizAttemptAdmin(admin.ModelAdmin):
    list_display = ("user", "quiz", "score_percent", "passed", "timed_out", "started_at", "submitted_at")
    list_filter = ("passed", "timed_out", "quiz__course")
    search_fields = ("user__username", "user__last_name")

    def has_add_permission(self, request):
        return False


@admin.register(Assignment)
class AssignmentAdmin(admin.ModelAdmin):
    list_display = ("title", "course", "due_at", "max_score", "is_published")
    list_filter = ("course", "is_published")
    list_editable = ("is_published",)


@admin.register(Submission)
class SubmissionAdmin(admin.ModelAdmin):
    """Grading screen: staff read the submission, then enter a score and feedback."""

    list_display = ("user", "assignment", "submitted_at", "score", "graded_at")
    list_filter = ("assignment__course", "assignment")
    search_fields = ("user__username", "user__last_name", "text")
    readonly_fields = ("assignment", "user", "text", "file_link", "submitted_at", "graded_at")
    fields = ("assignment", "user", "text", "file_link", "submitted_at", "score", "feedback", "graded_at")

    def has_add_permission(self, request):
        return False

    @admin.display(description="فایل")
    def file_link(self, obj):
        if not obj.pk or not obj.file:
            return "—"
        url = reverse("panel:submission_file", args=[obj.pk])
        return format_html('<a href="{}">دانلود فایل</a>', url)

    def save_model(self, request, obj, form, change):
        from .grading import grade_submission

        if "score" in form.changed_data and obj.score is not None:
            grade_submission(obj, obj.score, obj.feedback)  # caps the score, stamps graded_at, notifies the student
        else:
            super().save_model(request, obj, form, change)


@admin.register(Certificate)
class CertificateAdmin(admin.ModelAdmin):
    list_display = ("code", "holder_name", "course", "issued_at", "is_revoked")
    list_filter = ("is_revoked", "course")
    list_editable = ("is_revoked",)
    search_fields = ("code", "holder_name", "user__username")
    readonly_fields = ("code",)


@admin.register(WaitlistEntry)
class WaitlistEntryAdmin(admin.ModelAdmin):
    list_display = ("full_name", "phone", "batch", "status", "created_at", "notified_at")
    list_filter = ("status", "batch__course")
    search_fields = ("full_name", "phone", "email")


@admin.register(Attendance)
class AttendanceAdmin(admin.ModelAdmin):
    list_display = ("user", "session", "status")
    list_filter = ("status", "session__batch__course")

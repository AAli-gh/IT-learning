from django.conf import settings
from django.db import models
from django.db.models import Count, Q
from django.urls import reverse
from django.utils import timezone

from core.models import SEOFields
from core.rendering import render_markdown


class Category(SEOFields):
    name = models.CharField("نام", max_length=100)
    slug = models.SlugField("اسلاگ", unique=True, allow_unicode=True)
    icon = models.CharField("آیکون (ایموجی)", max_length=8, blank=True)
    description = models.TextField("توضیحات", blank=True)
    order = models.PositiveIntegerField("ترتیب", default=0)
    show_on_home = models.BooleanField("نمایش در صفحه اصلی", default=True)

    class Meta:
        ordering = ["order", "name"]
        verbose_name = "دسته‌بندی"
        verbose_name_plural = "دسته‌بندی‌ها"

    def __str__(self):
        return self.name

    def get_absolute_url(self):
        return reverse("courses:category", args=[self.slug])


class CourseQuerySet(models.QuerySet):
    def published(self):
        return self.filter(is_published=True, published_at__lte=timezone.now())

    def with_relations(self):
        return self.select_related("category", "instructor").prefetch_related("batches")

    def search(self, term):
        if not term:
            return self
        return self.filter(
            Q(title__icontains=term) | Q(summary__icontains=term)
            | Q(description__icontains=term) | Q(magazine_tag__icontains=term)
        )


class Course(SEOFields):
    class Level(models.TextChoices):
        BEGINNER = "beginner", "مقدماتی"
        INTERMEDIATE = "intermediate", "متوسط"
        ADVANCED = "advanced", "پیشرفته"

    title = models.CharField("عنوان", max_length=200)
    slug = models.SlugField("اسلاگ", unique=True, allow_unicode=True)
    category = models.ForeignKey(Category, verbose_name="دسته‌بندی", on_delete=models.PROTECT,
                                 related_name="courses")
    instructor = models.ForeignKey(settings.AUTH_USER_MODEL, verbose_name="مدرس", null=True, blank=True,
                                   on_delete=models.SET_NULL, related_name="courses",
                                   limit_choices_to={"is_instructor": True})
    level = models.CharField("سطح", max_length=15, choices=Level.choices, default=Level.BEGINNER)
    summary = models.CharField("خلاصه", max_length=300)
    description = models.TextField("توضیحات کامل (Markdown)", blank=True)
    cover = models.ImageField("تصویر کاور", upload_to="courses/", blank=True)
    price = models.PositiveBigIntegerField("شهریه (تومان)", default=0, help_text="۰ = رایگان")
    duration_hours = models.PositiveIntegerField("مدت (ساعت)", default=0)
    prerequisites = models.CharField("پیش‌نیاز", max_length=250, blank=True)
    magazine_tag = models.SlugField(
        "برچسب مجله", allow_unicode=True, blank=True,
        help_text="اسلاگ تگ متناظر در مجله؛ مطالب آن تگ در صفحه دوره نمایش داده می‌شود (مثلاً python).",
    )
    is_published = models.BooleanField("منتشر شده", default=False)
    is_featured = models.BooleanField("دوره ویژه", default=False)
    published_at = models.DateTimeField("تاریخ انتشار", default=timezone.now)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    objects = CourseQuerySet.as_manager()

    class Meta:
        ordering = ["-is_featured", "-published_at"]
        verbose_name = "دوره"
        verbose_name_plural = "دوره‌ها"

    def __str__(self):
        return self.title

    def get_absolute_url(self):
        return reverse("courses:detail", args=[self.slug])

    @property
    def description_html(self):
        return render_markdown(self.description)[0]

    @property
    def next_batch(self):
        """The earliest open batch that starts today or later."""
        today = timezone.localdate()
        open_batches = [b for b in self.batches.all() if b.is_open and b.start_date >= today]
        return min(open_batches, key=lambda b: b.start_date, default=None)


class Topic(models.Model):
    """One line of the course syllabus."""

    course = models.ForeignKey(Course, on_delete=models.CASCADE, related_name="topics")
    title = models.CharField("سرفصل", max_length=200)
    order = models.PositiveIntegerField("ترتیب", default=0)

    class Meta:
        ordering = ["order", "id"]
        verbose_name = "سرفصل"
        verbose_name_plural = "سرفصل‌ها"

    def __str__(self):
        return self.title


class Batch(models.Model):
    """A scheduled run of a course (دوره برگزاری)."""

    class Mode(models.TextChoices):
        IN_PERSON = "in_person", "حضوری"
        ONLINE = "online", "آنلاین"
        HYBRID = "hybrid", "ترکیبی"

    course = models.ForeignKey(Course, on_delete=models.CASCADE, related_name="batches")
    title = models.CharField("عنوان", max_length=100, blank=True, help_text="مثلاً «پاییز ۱۴۰۵»")
    start_date = models.DateField("تاریخ شروع")
    schedule = models.CharField("برنامه کلاس‌ها", max_length=150, blank=True,
                                help_text="مثلاً «شنبه و دوشنبه ۱۸ تا ۲۰»")
    mode = models.CharField("نحوه برگزاری", max_length=10, choices=Mode.choices, default=Mode.IN_PERSON)
    capacity = models.PositiveIntegerField("ظرفیت", default=20)
    is_open = models.BooleanField("ثبت‌نام باز است", default=True)

    class Meta:
        ordering = ["start_date"]
        verbose_name = "دوره برگزاری"
        verbose_name_plural = "دوره‌های برگزاری"

    def __str__(self):
        return f"{self.course.title} — {self.title or self.start_date}"

    @property
    def taken(self):
        return self.enrollments.exclude(status=Enrollment.Status.CANCELLED).count()

    @property
    def seats_left(self):
        return max(0, self.capacity - self.taken)

    @property
    def accepts_enrollment(self):
        return self.is_open and self.seats_left > 0


class Enrollment(models.Model):
    class Status(models.TextChoices):
        PENDING = "pending", "در انتظار تماس"
        CONFIRMED = "confirmed", "تأیید شده"
        CANCELLED = "cancelled", "لغو شده"

    course = models.ForeignKey(Course, on_delete=models.CASCADE, related_name="enrollments")
    batch = models.ForeignKey(Batch, null=True, blank=True, on_delete=models.SET_NULL,
                              related_name="enrollments", verbose_name="دوره برگزاری")
    user = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL,
                             related_name="enrollments")
    full_name = models.CharField("نام و نام خانوادگی", max_length=120)
    phone = models.CharField("شماره تماس", max_length=20)
    email = models.EmailField("ایمیل", blank=True)
    note = models.TextField("توضیحات", blank=True)
    status = models.CharField("وضعیت", max_length=10, choices=Status.choices, default=Status.PENDING)
    created_at = models.DateTimeField("زمان ثبت", auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
        verbose_name = "ثبت‌نام"
        verbose_name_plural = "ثبت‌نام‌ها"

    def __str__(self):
        return f"{self.full_name} — {self.course.title}"

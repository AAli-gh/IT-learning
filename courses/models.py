import datetime
import secrets

from django.conf import settings
from django.core.validators import FileExtensionValidator
from django.db import models
from django.db.models import Avg, Count, Q
from django.urls import reverse
from django.utils import timezone

from core import textutils
from core.models import SEOFields
from core.rendering import render_markdown

from .storage import private_storage
from .validators import validate_attachment_size, validate_video_size


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

    def _match(self, query):
        """AND over the words of each query variant, OR across variants (Persian/English synonyms)."""
        any_variant = Q()
        for variant in textutils.query_variants(query):
            all_words = Q()
            for word in variant.split():
                all_words &= Q(search_text__contains=word)
            any_variant |= all_words
        return self.filter(any_variant) if any_variant else self.none()

    def search(self, term):
        """Persian-aware search: ی/ک variants, digits, half-spaces, fa<->en synonyms and one-typo correction."""
        term = (term or "").strip()
        if not term or not textutils.normalize(term):
            return self
        found = self._match(term)
        if found.exists():
            return found
        vocabulary = set()
        for text in Course.objects.values_list("search_text", flat=True):
            vocabulary.update(text.split())
        fixed = textutils.suggest_correction(term, sorted(vocabulary))
        return self._match(fixed) if fixed else found


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
    # Normalised copy of the searchable fields (see core.textutils); rebuilt on every save.
    search_text = models.TextField(editable=False, blank=True, default="")

    objects = CourseQuerySet.as_manager()

    class Meta:
        ordering = ["-is_featured", "-published_at"]
        verbose_name = "دوره"
        verbose_name_plural = "دوره‌ها"

    def __str__(self):
        return self.title

    def get_absolute_url(self):
        return reverse("courses:detail", args=[self.slug])

    def build_search_text(self):
        parts = [self.title, self.summary, self.description, self.magazine_tag, self.prerequisites]
        if self.category_id:
            parts.append(self.category.name)
        return textutils.normalize(" ".join(p for p in parts if p))

    def save(self, *args, **kwargs):
        self.search_text = self.build_search_text()
        super().save(*args, **kwargs)

    @property
    def description_html(self):
        return render_markdown(self.description)[0]

    @property
    def approved_reviews(self):
        return [r for r in self.reviews.all() if r.is_approved]

    @property
    def rating(self):
        reviews = self.approved_reviews
        return round(sum(r.rating for r in reviews) / len(reviews), 1) if reviews else None

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
    def held_seats(self):
        """Seats offered to people on the waiting list who haven't registered yet (offer valid for HOLD_HOURS)."""
        cutoff = timezone.now() - datetime.timedelta(hours=WaitlistEntry.HOLD_HOURS)
        return self.waitlist.filter(status=WaitlistEntry.Status.NOTIFIED, notified_at__gte=cutoff).count()

    @property
    def accepts_enrollment(self):
        """Open to the public: a free seat that is not already offered to someone on the waiting list."""
        return self.is_open and self.seats_left - self.held_seats > 0

    def accepts_enrollment_for(self, phone):
        """Same, but a person holding a waiting-list offer for this batch may take their held seat."""
        if self.accepts_enrollment:
            return True
        cutoff = timezone.now() - datetime.timedelta(hours=WaitlistEntry.HOLD_HOURS)
        return self.is_open and self.seats_left > 0 and self.waitlist.filter(
            phone=phone, status=WaitlistEntry.Status.NOTIFIED, notified_at__gte=cutoff).exists()


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
    # Snapshot of the fee at registration time plus what has been collected so far (manual bookkeeping).
    price = models.PositiveBigIntegerField("شهریه (تومان)", default=0)
    paid_amount = models.PositiveBigIntegerField("مبلغ پرداخت‌شده (تومان)", default=0)

    class Meta:
        ordering = ["-created_at"]
        verbose_name = "ثبت‌نام"
        verbose_name_plural = "ثبت‌نام‌ها"

    def save(self, *args, **kwargs):
        if self._state.adding and not self.price:
            self.price = self.course.price
        super().save(*args, **kwargs)

    @property
    def outstanding(self):
        return max(0, self.price - self.paid_amount)

    def __str__(self):
        return f"{self.full_name} — {self.course.title}"


class Review(models.Model):
    """Student review; only people with a confirmed enrollment can write one, and staff approve it."""

    course = models.ForeignKey(Course, on_delete=models.CASCADE, related_name="reviews")
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="reviews")
    rating = models.PositiveSmallIntegerField("امتیاز", choices=[(i, str(i)) for i in range(1, 6)])
    text = models.TextField("نظر", max_length=1000)
    is_approved = models.BooleanField("تأیید شده", default=False)
    is_featured = models.BooleanField("نمایش در صفحه اصلی", default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
        constraints = [models.UniqueConstraint(fields=["course", "user"], name="one_review_per_user_course")]
        verbose_name = "نظر"
        verbose_name_plural = "نظرات دانشجویان"

    def __str__(self):
        return f"{self.user} → {self.course} ({self.rating})"


class Faq(models.Model):
    """Frequently asked question; ``course`` empty = general question."""

    question = models.CharField("پرسش", max_length=250)
    answer = models.TextField("پاسخ")
    course = models.ForeignKey(Course, null=True, blank=True, on_delete=models.CASCADE, related_name="faqs",
                               verbose_name="دوره (اختیاری)")
    order = models.PositiveIntegerField("ترتیب", default=0)
    is_published = models.BooleanField("منتشر شده", default=True)

    class Meta:
        ordering = ["order", "id"]
        verbose_name = "سؤال متداول"
        verbose_name_plural = "سؤالات متداول"

    def __str__(self):
        return self.question


class Lesson(models.Model):
    """One lesson of the course content, visible to students with a confirmed enrollment."""

    course = models.ForeignKey(Course, on_delete=models.CASCADE, related_name="lessons")
    title = models.CharField("عنوان", max_length=200)
    order = models.PositiveIntegerField("ترتیب", default=0)
    body = models.TextField("توضیحات (Markdown)", blank=True)
    video_url = models.URLField("لینک ویدئو", blank=True)
    attachment = models.FileField("فایل ضمیمه", upload_to="lessons/", storage=private_storage, blank=True,
                                  validators=[validate_attachment_size])
    video_file = models.FileField("ویدئوی آپلودی", upload_to="videos/", storage=private_storage, blank=True,
                                  validators=[FileExtensionValidator(["mp4", "webm"]), validate_video_size],
                                  help_text="mp4 یا webm؛ فقط برای دانشجویان تأییدشده پخش می‌شود.")
    duration_minutes = models.PositiveIntegerField("مدت (دقیقه)", default=0)
    is_published = models.BooleanField("منتشر شده", default=True)

    class Meta:
        ordering = ["order", "id"]
        verbose_name = "درس"
        verbose_name_plural = "درس‌ها"

    def __str__(self):
        return self.title

    @property
    def body_html(self):
        return render_markdown(self.body)[0]


class LessonProgress(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="lesson_progress")
    lesson = models.ForeignKey(Lesson, on_delete=models.CASCADE, related_name="progress")
    completed_at = models.DateTimeField(default=timezone.now)

    class Meta:
        constraints = [models.UniqueConstraint(fields=["user", "lesson"], name="one_progress_per_lesson")]
        verbose_name = "پیشرفت درس"
        verbose_name_plural = "پیشرفت درس‌ها"


class ClassSession(models.Model):
    """A scheduled class meeting of a batch."""

    batch = models.ForeignKey(Batch, on_delete=models.CASCADE, related_name="sessions")
    title = models.CharField("موضوع جلسه", max_length=200)
    starts_at = models.DateTimeField("زمان شروع")
    duration_minutes = models.PositiveIntegerField("مدت (دقیقه)", default=120)
    place = models.CharField("مکان / لینک کلاس آنلاین", max_length=250, blank=True)
    recording_url = models.URLField("لینک ضبط جلسه", blank=True)
    reminded_at = models.DateTimeField(null=True, blank=True, editable=False)

    class Meta:
        ordering = ["starts_at"]
        verbose_name = "جلسه کلاس"
        verbose_name_plural = "جلسات کلاس"

    def __str__(self):
        return f"{self.batch} — {self.title}"


class Announcement(models.Model):
    """Notice for the students of a course (optionally only of one batch)."""

    course = models.ForeignKey(Course, on_delete=models.CASCADE, related_name="announcements")
    batch = models.ForeignKey(Batch, null=True, blank=True, on_delete=models.CASCADE, related_name="announcements",
                              verbose_name="دوره برگزاری (اختیاری)")
    title = models.CharField("عنوان", max_length=200)
    body = models.TextField("متن")
    is_published = models.BooleanField("منتشر شده", default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
        verbose_name = "اطلاعیه"
        verbose_name_plural = "اطلاعیه‌ها"

    def __str__(self):
        return self.title


class Quiz(models.Model):
    """Multiple-choice quiz of a course."""

    course = models.ForeignKey(Course, on_delete=models.CASCADE, related_name="quizzes")
    title = models.CharField("عنوان", max_length=200)
    description = models.TextField("توضیحات", blank=True)
    order = models.PositiveIntegerField("ترتیب", default=0)
    pass_percent = models.PositiveSmallIntegerField("حد نصاب قبولی (٪)", default=60)
    time_limit_minutes = models.PositiveIntegerField("محدودیت زمان (دقیقه)", default=0, help_text="۰ = بدون محدودیت")
    max_attempts = models.PositiveSmallIntegerField("حداکثر دفعات شرکت", default=0, help_text="۰ = نامحدود")
    show_answers = models.BooleanField("نمایش پاسخ‌های صحیح پس از آزمون", default=False)
    is_published = models.BooleanField("منتشر شده", default=False)

    class Meta:
        ordering = ["order", "id"]
        verbose_name = "آزمون"
        verbose_name_plural = "آزمون‌ها"

    def __str__(self):
        return f"{self.course.title} — {self.title}"


class Question(models.Model):
    quiz = models.ForeignKey(Quiz, on_delete=models.CASCADE, related_name="questions")
    text = models.TextField("متن سؤال")
    order = models.PositiveIntegerField("ترتیب", default=0)
    points = models.PositiveSmallIntegerField("امتیاز", default=1)

    class Meta:
        ordering = ["order", "id"]
        verbose_name = "سؤال"
        verbose_name_plural = "سؤال‌ها"

    def __str__(self):
        return self.text[:60]


class Choice(models.Model):
    question = models.ForeignKey(Question, on_delete=models.CASCADE, related_name="choices")
    text = models.CharField("گزینه", max_length=300)
    is_correct = models.BooleanField("پاسخ صحیح", default=False)
    order = models.PositiveIntegerField("ترتیب", default=0)

    class Meta:
        ordering = ["order", "id"]
        verbose_name = "گزینه"
        verbose_name_plural = "گزینه‌ها"

    def __str__(self):
        return self.text


class QuizAttempt(models.Model):
    # A submission this many seconds after the deadline is still accepted (network delay, clock skew).
    GRACE_SECONDS = 60

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="quiz_attempts")
    quiz = models.ForeignKey(Quiz, on_delete=models.CASCADE, related_name="attempts")
    started_at = models.DateTimeField(auto_now_add=True)
    submitted_at = models.DateTimeField(null=True, blank=True)
    answers = models.JSONField(default=dict, blank=True)  # {question_id: choice_id}
    score_percent = models.PositiveSmallIntegerField(null=True, blank=True)
    passed = models.BooleanField(default=False)
    timed_out = models.BooleanField(default=False)

    class Meta:
        ordering = ["-started_at"]
        verbose_name = "شرکت در آزمون"
        verbose_name_plural = "نتایج آزمون‌ها"

    def __str__(self):
        return f"{self.user} — {self.quiz} ({self.score_percent})"

    @property
    def is_open(self):
        return self.submitted_at is None

    @property
    def deadline(self):
        if not self.quiz.time_limit_minutes:
            return None
        return self.started_at + datetime.timedelta(minutes=self.quiz.time_limit_minutes)

    def grade(self, answers):
        """Score ``answers`` ({question_id: choice_id}); too-late submissions score 0."""
        now = timezone.now()
        questions = list(self.quiz.questions.prefetch_related("choices"))
        valid = {}
        for q in questions:
            chosen = answers.get(q.pk)
            if chosen in {c.pk for c in q.choices.all()}:
                valid[q.pk] = chosen
        total = sum(q.points for q in questions)
        earned = sum(q.points for q in questions
                     if valid.get(q.pk) in {c.pk for c in q.choices.all() if c.is_correct})
        late = bool(self.deadline and now > self.deadline + datetime.timedelta(seconds=self.GRACE_SECONDS))
        self.answers = {str(k): v for k, v in valid.items()}
        self.timed_out = late
        self.score_percent = 0 if late or not total else round(100 * earned / total)
        self.passed = not late and self.score_percent >= self.quiz.pass_percent
        self.submitted_at = now
        self.save()


class Assignment(models.Model):
    course = models.ForeignKey(Course, on_delete=models.CASCADE, related_name="assignments")
    title = models.CharField("عنوان", max_length=200)
    description = models.TextField("شرح تکلیف (Markdown)")
    order = models.PositiveIntegerField("ترتیب", default=0)
    due_at = models.DateTimeField("مهلت تحویل", null=True, blank=True)
    allow_late = models.BooleanField("پذیرش تحویل با تأخیر", default=False)
    max_score = models.PositiveSmallIntegerField("نمره کل", default=100)
    pass_percent = models.PositiveSmallIntegerField("حد نصاب قبولی (٪)", default=50)
    is_published = models.BooleanField("منتشر شده", default=False)

    class Meta:
        ordering = ["order", "id"]
        verbose_name = "تکلیف"
        verbose_name_plural = "تکالیف"

    def __str__(self):
        return f"{self.course.title} — {self.title}"

    @property
    def description_html(self):
        return render_markdown(self.description)[0]

    @property
    def is_past_due(self):
        return bool(self.due_at and timezone.now() > self.due_at)


class Submission(models.Model):
    ALLOWED_EXTENSIONS = ["pdf", "zip", "txt", "py", "js", "html", "css", "md", "docx", "pptx", "xlsx", "png", "jpg", "jpeg"]

    assignment = models.ForeignKey(Assignment, on_delete=models.CASCADE, related_name="submissions")
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="submissions")
    text = models.TextField("پاسخ / توضیحات", blank=True)
    file = models.FileField("فایل", upload_to="submissions/", storage=private_storage, blank=True,
                            validators=[FileExtensionValidator(ALLOWED_EXTENSIONS)])
    submitted_at = models.DateTimeField("زمان تحویل", default=timezone.now)
    score = models.PositiveSmallIntegerField("نمره", null=True, blank=True)
    feedback = models.TextField("بازخورد مدرس", blank=True)
    graded_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        constraints = [models.UniqueConstraint(fields=["assignment", "user"], name="one_submission_per_user")]
        ordering = ["-submitted_at"]
        verbose_name = "تحویل تکلیف"
        verbose_name_plural = "تحویل‌های تکلیف"

    def __str__(self):
        return f"{self.user} — {self.assignment}"

    @property
    def is_graded(self):
        return self.score is not None

    @property
    def passed(self):
        return self.is_graded and self.score * 100 >= self.assignment.pass_percent * self.assignment.max_score


def _certificate_code():
    return "ITA-" + secrets.token_hex(5).upper()


class Certificate(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="certificates")
    course = models.ForeignKey(Course, on_delete=models.CASCADE, related_name="certificates")
    holder_name = models.CharField("نام روی گواهی", max_length=150)
    code = models.CharField("کد گواهی", max_length=20, unique=True, default=_certificate_code, editable=False)
    issued_at = models.DateTimeField("تاریخ صدور", default=timezone.now)
    is_revoked = models.BooleanField("ابطال شده", default=False)

    class Meta:
        constraints = [models.UniqueConstraint(fields=["user", "course"], name="one_certificate_per_course")]
        ordering = ["-issued_at"]
        verbose_name = "گواهی پایان دوره"
        verbose_name_plural = "گواهی‌های پایان دوره"

    def __str__(self):
        return f"{self.code} — {self.holder_name}"

    def get_absolute_url(self):
        return reverse("courses:certificate", args=[self.code])


class Attendance(models.Model):
    """Attendance of one student at one class session."""

    class Status(models.TextChoices):
        PRESENT = "present", "حاضر"
        LATE = "late", "تأخیر"
        ABSENT = "absent", "غایب"
        EXCUSED = "excused", "غیبت موجه"

    session = models.ForeignKey(ClassSession, on_delete=models.CASCADE, related_name="attendance")
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="attendance")
    status = models.CharField("وضعیت", max_length=10, choices=Status.choices, default=Status.PRESENT)
    note = models.CharField("یادداشت", max_length=200, blank=True)

    class Meta:
        constraints = [models.UniqueConstraint(fields=["session", "user"], name="one_attendance_per_session")]
        verbose_name = "حضور و غیاب"
        verbose_name_plural = "حضور و غیاب"

    def __str__(self):
        return f"{self.user} — {self.session}: {self.get_status_display()}"


class WaitlistEntry(models.Model):
    """Someone waiting for a seat in a batch that is full. Offered a seat (NOTIFIED) when one frees up."""

    HOLD_HOURS = 48

    class Status(models.TextChoices):
        WAITING = "waiting", "در انتظار"
        NOTIFIED = "notified", "اطلاع داده شد"
        ENROLLED = "enrolled", "ثبت‌نام کرد"
        EXPIRED = "expired", "منقضی شد"
        CANCELLED = "cancelled", "لغو شد"

    batch = models.ForeignKey(Batch, on_delete=models.CASCADE, related_name="waitlist")
    user = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL,
                             related_name="waitlist_entries")
    full_name = models.CharField("نام و نام خانوادگی", max_length=120)
    phone = models.CharField("شماره تماس", max_length=20)
    email = models.EmailField("ایمیل", blank=True)
    status = models.CharField("وضعیت", max_length=10, choices=Status.choices, default=Status.WAITING)
    created_at = models.DateTimeField(auto_now_add=True)
    notified_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["created_at"]
        verbose_name = "لیست انتظار"
        verbose_name_plural = "لیست انتظار"

    def __str__(self):
        return f"{self.full_name} — {self.batch}"

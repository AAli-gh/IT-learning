import datetime
import shutil
import tempfile

from django.core import mail
from django.core.cache import cache
from django.core.files.base import ContentFile
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from accounts.models import User
from courses.models import Announcement, Batch, Category, ClassSession, Course, Enrollment, Lesson, LessonProgress

PRIVATE = tempfile.mkdtemp()


def tearDownModule():
    shutil.rmtree(PRIVATE, ignore_errors=True)


@override_settings(MAGAZINE_URL="http://127.0.0.1:9")
class PanelTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cat = Category.objects.create(name="برنامه‌نویسی", slug="programming")
        cls.course = Course.objects.create(title="پایتون", slug="python", category=cat, summary="s", is_published=True)
        cls.other = Course.objects.create(title="وب", slug="web", category=cat, summary="s", is_published=True)
        cls.batch = Batch.objects.create(course=cls.course, title="b1", start_date=timezone.localdate())
        cls.batch2 = Batch.objects.create(course=cls.course, title="b2", start_date=timezone.localdate())
        cls.l1 = Lesson.objects.create(course=cls.course, title="درس یک", order=1)
        cls.l2 = Lesson.objects.create(course=cls.course, title="درس دو", order=2)
        cls.draft = Lesson.objects.create(course=cls.course, title="پیش‌نویس", order=3, is_published=False)
        cls.web_lesson = Lesson.objects.create(course=cls.other, title="درس وب")
        cls.student = User.objects.create_user("sara", "s@e.com", "pw-12345-xyz")
        cls.stranger = User.objects.create_user("bob", "b@e.com", "pw-12345-xyz")
        cls.enrollment = Enrollment.objects.create(course=cls.course, batch=cls.batch, user=cls.student,
                                                   full_name="s", phone="09120000000",
                                                   status=Enrollment.Status.CONFIRMED)

    def setUp(self):
        cache.clear()
        self.client.force_login(self.student)

    def lesson_url(self, name, lesson=None, course=None):
        lesson = lesson or self.l1
        return reverse(f"panel:{name}", args=[(course or self.course).slug, lesson.pk])

    def test_login_required(self):
        self.client.logout()
        for name in ("dashboard", "courses", "schedule", "announcements", "enrollments"):
            self.assertEqual(self.client.get(reverse(f"panel:{name}")).status_code, 302)

    def test_pages_render(self):
        ClassSession.objects.create(batch=self.batch, title="جلسه", starts_at=timezone.now() + datetime.timedelta(days=1))
        for name in ("dashboard", "courses", "schedule", "announcements", "enrollments"):
            self.assertEqual(self.client.get(reverse(f"panel:{name}")).status_code, 200, name)
        self.assertContains(self.client.get(reverse("panel:course", args=["python"])), "درس یک")
        self.assertContains(self.client.get(self.lesson_url("lesson")), "درس یک")

    def test_unconfirmed_or_foreign_course_is_404(self):
        self.assertEqual(self.client.get(reverse("panel:course", args=["web"])).status_code, 404)
        self.assertEqual(self.client.get(self.lesson_url("lesson", self.web_lesson, self.other)).status_code, 404)
        pending = User.objects.create_user("p", "p@e.com", "pw-12345-xyz")
        Enrollment.objects.create(course=self.course, user=pending, full_name="p", phone="09120000001")
        self.client.force_login(pending)
        self.assertEqual(self.client.get(reverse("panel:course", args=["python"])).status_code, 404)
        self.client.force_login(self.stranger)
        self.assertEqual(self.client.get(self.lesson_url("lesson")).status_code, 404)

    def test_lesson_of_another_course_not_reachable_via_my_course(self):
        url = reverse("panel:lesson", args=["python", self.web_lesson.pk])
        self.assertEqual(self.client.get(url).status_code, 404)

    def test_draft_lesson_hidden(self):
        self.assertEqual(self.client.get(self.lesson_url("lesson", self.draft)).status_code, 404)
        self.assertNotContains(self.client.get(reverse("panel:course", args=["python"])), "پیش‌نویس")

    def test_toggle_progress_and_percent(self):
        resp = self.client.post(self.lesson_url("toggle_lesson"), headers={"HX-Request": "true"})
        self.assertContains(resp, "۵۰٪")  # 1 of 2 published lessons
        self.assertTrue(LessonProgress.objects.filter(user=self.student, lesson=self.l1).exists())
        self.client.post(self.lesson_url("toggle_lesson"), headers={"HX-Request": "true"})
        self.assertFalse(LessonProgress.objects.exists())

    def test_cannot_toggle_without_access(self):
        self.client.force_login(self.stranger)
        self.assertEqual(self.client.post(self.lesson_url("toggle_lesson")).status_code, 404)
        self.assertFalse(LessonProgress.objects.exists())

    @override_settings(PRIVATE_MEDIA_ROOT=PRIVATE)
    def test_lesson_file_access_control(self):
        # Use a throwaway storage rooted in PRIVATE so tests never touch the real private_media dir.
        from django.core.files.storage import FileSystemStorage

        field = Lesson._meta.get_field("attachment")
        old, field.storage = field.storage, FileSystemStorage(location=PRIVATE)
        self.addCleanup(setattr, field, "storage", old)
        self.l1.attachment.save("notes.txt", ContentFile(b"secret"), save=True)
        resp = self.client.get(self.lesson_url("lesson_file"))
        self.assertEqual(b"".join(resp.streaming_content), b"secret")
        self.assertIn("attachment", resp["Content-Disposition"])
        self.client.force_login(self.stranger)
        self.assertEqual(self.client.get(self.lesson_url("lesson_file")).status_code, 404)
        self.client.logout()
        self.assertEqual(self.client.get(self.lesson_url("lesson_file")).status_code, 302)

    def test_announcements_scoped_to_course_and_batch(self):
        Announcement.objects.create(course=self.course, title="عمومی", body="x")
        Announcement.objects.create(course=self.course, batch=self.batch, title="دوره‌ی من", body="x")
        Announcement.objects.create(course=self.course, batch=self.batch2, title="دوره‌ی دیگر", body="x")
        Announcement.objects.create(course=self.other, title="درس وب", body="x")
        Announcement.objects.create(course=self.course, title="پیش‌نویس", body="x", is_published=False)
        page = self.client.get(reverse("panel:announcements")).content.decode()
        self.assertIn("عمومی", page)
        self.assertIn("دوره‌ی من", page)
        for hidden in ("دوره‌ی دیگر", "درس وب", "پیش‌نویس"):
            self.assertNotIn(hidden, page)

    def test_schedule_only_my_batches(self):
        soon = timezone.now() + datetime.timedelta(days=2)
        ClassSession.objects.create(batch=self.batch, title="جلسه من", starts_at=soon)
        ClassSession.objects.create(batch=self.batch2, title="جلسه دیگران", starts_at=soon)
        page = self.client.get(reverse("panel:schedule")).content.decode()
        self.assertIn("جلسه من", page)
        self.assertNotIn("جلسه دیگران", page)

    def test_cancel_only_own_pending(self):
        pending = Enrollment.objects.create(course=self.other, user=self.student, full_name="s", phone="09120000000")
        self.client.post(reverse("panel:cancel_enrollment", args=[pending.pk]))
        pending.refresh_from_db()
        self.assertEqual(pending.status, Enrollment.Status.CANCELLED)
        self.client.post(reverse("panel:cancel_enrollment", args=[self.enrollment.pk]))  # confirmed: refused
        self.enrollment.refresh_from_db()
        self.assertEqual(self.enrollment.status, Enrollment.Status.CONFIRMED)
        self.client.force_login(self.stranger)
        self.assertEqual(self.client.post(reverse("panel:cancel_enrollment", args=[pending.pk])).status_code, 404)

    def test_admin_confirmation_emails_student(self):
        from django.contrib.admin.sites import site
        from django.test import RequestFactory

        from courses.admin import EnrollmentAdmin

        e = Enrollment.objects.create(course=self.other, user=self.stranger, full_name="b", phone="09120000002")
        EnrollmentAdmin(Enrollment, site).confirm(RequestFactory().post("/"), Enrollment.objects.filter(pk=e.pk))
        e.refresh_from_db()
        self.assertEqual(e.status, Enrollment.Status.CONFIRMED)
        self.assertEqual(mail.outbox[0].to, ["b@e.com"])

import datetime

from django.core import mail
from django.core.cache import cache
from django.core.files.base import ContentFile
from django.core.management import call_command
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from accounts.models import User
from core.testing import use_temp_private_storage
from courses.models import (Announcement, Assignment, Attendance, Batch, Category, ClassSession, Course, Enrollment,
                            Lesson, Submission)
from courses.reports import attendance_summary, student_report
from notifications.models import Notification
from notifications.services import notify

VIDEO = bytes(range(256)) * 40  # 10 240 bytes


@override_settings(MAGAZINE_URL="")
class StudentFeatureBase(TestCase):
    @classmethod
    def setUpTestData(cls):
        cat = Category.objects.create(name="c", slug="c")
        cls.teacher = User.objects.create_user("teacher", "t@e.com", "pw-12345-xyz", is_instructor=True)
        cls.course = Course.objects.create(title="پایتون", slug="python", category=cat, summary="s", is_published=True,
                                           instructor=cls.teacher)
        cls.batch = Batch.objects.create(course=cls.course, title="b1", start_date=timezone.localdate())
        cls.other_batch = Batch.objects.create(course=cls.course, title="b2", start_date=timezone.localdate())
        cls.student = User.objects.create_user("sara", "s@e.com", "pw-12345-xyz", first_name="سارا")
        cls.classmate = User.objects.create_user("ali", "a@e.com", "pw-12345-xyz")
        cls.stranger = User.objects.create_user("eve", "e@e.com", "pw-12345-xyz")
        for user, batch in ((cls.student, cls.batch), (cls.classmate, cls.other_batch)):
            Enrollment.objects.create(course=cls.course, batch=batch, user=user, full_name=user.username,
                                      phone="09120000000", status=Enrollment.Status.CONFIRMED)
        Notification.objects.all().delete()  # drop the "enrollment confirmed" notices made by the fixtures

    def setUp(self):
        cache.clear()
        use_temp_private_storage(self)
        self.client.force_login(self.student)


class NotificationTests(StudentFeatureBase):
    def test_notify_creates_emails_and_dedupes(self):
        mail.outbox.clear()
        first = notify(self.student, "عنوان", "متن", "/panel/", dedupe_key="k1")
        self.assertIsNotNone(first)
        self.assertIsNone(notify(self.student, "عنوان", "متن", "/panel/", dedupe_key="k1"))
        self.assertEqual(Notification.objects.count() - Notification.objects.exclude(dedupe_key="k1").count(), 1)
        self.assertEqual(len(mail.outbox), 1)
        self.assertIn("/panel/", mail.outbox[0].body)

    def test_email_opt_out_and_external_urls_are_dropped(self):
        User.objects.filter(pk=self.student.pk).update(email_notifications=False)
        self.student.refresh_from_db()
        mail.outbox.clear()
        note = notify(self.student, "x", "y", "https://evil.example/")
        self.assertEqual((note.url, len(mail.outbox)), ("", 0))
        self.assertEqual(notify(self.student, "x", "y", "//evil.example").url, "")

    def test_list_open_and_read_all(self):
        n1 = notify(self.student, "یک", url="/panel/schedule/", email=False)
        notify(self.student, "دو", email=False)
        notify(self.classmate, "برای دیگری", email=False)
        page = self.client.get(reverse("panel:notifications"))
        self.assertContains(page, "یک")
        self.assertNotContains(page, "برای دیگری")
        self.assertEqual(page.context["unread_notifications"], 2)
        resp = self.client.get(reverse("panel:notification_open", args=[n1.pk]))
        self.assertRedirects(resp, "/panel/schedule/", fetch_redirect_response=False)
        n1.refresh_from_db()
        self.assertTrue(n1.is_read)
        self.client.post(reverse("panel:notifications_read_all"))
        self.assertFalse(Notification.objects.filter(user=self.student, is_read=False).exists())
        self.assertTrue(Notification.objects.filter(user=self.classmate, is_read=False).exists())  # not touched

    def test_cannot_open_someone_elses_notification(self):
        n = notify(self.classmate, "خصوصی", email=False)
        self.assertEqual(self.client.get(reverse("panel:notification_open", args=[n.pk])).status_code, 404)

    def test_bell_shows_unread_count_in_header(self):
        notify(self.student, "a", email=False)
        notify(self.student, "b", email=False)
        self.assertContains(self.client.get(reverse("courses:home")), 'aria-label="اعلان‌ها"')

    def test_announcement_reaches_course_students_and_respects_batch(self):
        Announcement.objects.create(course=self.course, title="برای همه", body="x")
        Announcement.objects.create(course=self.course, batch=self.batch, title="فقط دوره اول", body="x")
        titles = lambda u: set(Notification.objects.filter(user=u).values_list("title", flat=True))
        self.assertEqual(titles(self.student), {"برای همه", "فقط دوره اول"})
        self.assertEqual(titles(self.classmate), {"برای همه"})
        self.assertEqual(titles(self.stranger), set())

    def test_unpublished_announcement_notifies_nobody_until_published(self):
        ann = Announcement.objects.create(course=self.course, title="پیش‌نویس", body="x", is_published=False)
        self.assertFalse(Notification.objects.exists())
        ann.is_published = True
        ann.save()
        ann.save()  # saving again must not duplicate
        self.assertEqual(Notification.objects.filter(title="پیش‌نویس", user=self.student).count(), 1)

    def test_confirmation_notifies_student(self):
        e = Enrollment.objects.create(course=self.course, user=self.stranger, full_name="eve", phone="09120000009")
        self.assertFalse(Notification.objects.filter(user=self.stranger).exists())
        e.status = Enrollment.Status.CONFIRMED
        e.save()
        e.save()
        self.assertEqual(Notification.objects.filter(user=self.stranger, title__contains="تأیید شد").count(), 1)


class RemindersTests(StudentFeatureBase):
    def test_class_and_deadline_reminders_are_sent_once(self):
        soon = timezone.now() + datetime.timedelta(hours=5)
        ClassSession.objects.create(batch=self.batch, title="جلسه فردا", starts_at=soon, place="کلاس ۱")
        ClassSession.objects.create(batch=self.batch, title="جلسه دور", starts_at=timezone.now() + datetime.timedelta(days=9))
        a = Assignment.objects.create(course=self.course, title="تکلیف", description="d", is_published=True,
                                      due_at=timezone.now() + datetime.timedelta(hours=10))
        Submission.objects.create(assignment=a, user=self.classmate, text="done")
        call_command("send_reminders")
        call_command("send_reminders")  # idempotent
        mine = Notification.objects.filter(user=self.student)
        self.assertEqual(sorted(mine.values_list("title", flat=True)),
                         sorted(["یادآوری کلاس: جلسه فردا", "مهلت تحویل تکلیف: تکلیف"]))
        # the classmate is in another batch (no class reminder) and already submitted (no deadline reminder)
        self.assertFalse(Notification.objects.filter(user=self.classmate).exists())
        self.assertFalse(Notification.objects.filter(user=self.stranger).exists())

    def test_unpublished_assignment_and_past_deadline_are_ignored(self):
        Assignment.objects.create(course=self.course, title="پیش‌نویس", description="d", is_published=False,
                                  due_at=timezone.now() + datetime.timedelta(hours=3))
        Assignment.objects.create(course=self.course, title="گذشته", description="d", is_published=True,
                                  due_at=timezone.now() - datetime.timedelta(hours=3))
        call_command("send_reminders")
        self.assertFalse(Notification.objects.exists())


class VideoTests(StudentFeatureBase):
    def setUp(self):
        super().setUp()
        self.lesson = Lesson.objects.create(course=self.course, title="ویدئو")
        self.lesson.video_file.save("lesson.mp4", ContentFile(VIDEO), save=True)
        self.url = reverse("panel:lesson_video", args=["python", self.lesson.pk])

    def body(self, resp):
        return b"".join(resp.streaming_content)

    def test_full_stream_and_headers(self):
        resp = self.client.get(self.url)
        self.assertEqual((resp.status_code, resp["Content-Type"], resp["Accept-Ranges"]), (200, "video/mp4", "bytes"))
        self.assertEqual(self.body(resp), VIDEO)
        self.assertEqual(resp["Content-Length"], str(len(VIDEO)))
        self.assertEqual(resp["Cache-Control"], "private, no-store")
        self.assertEqual(resp["X-Content-Type-Options"], "nosniff")
        self.assertEqual(resp["Content-Disposition"], "inline")

    def test_byte_ranges(self):
        resp = self.client.get(self.url, headers={"Range": "bytes=100-199"})
        self.assertEqual((resp.status_code, resp["Content-Range"]), (206, f"bytes 100-199/{len(VIDEO)}"))
        self.assertEqual(self.body(resp), VIDEO[100:200])
        resp = self.client.get(self.url, headers={"Range": f"bytes={len(VIDEO) - 10}-"})
        self.assertEqual(self.body(resp), VIDEO[-10:])
        resp = self.client.get(self.url, headers={"Range": "bytes=-5"})
        self.assertEqual(self.body(resp), VIDEO[-5:])
        resp = self.client.get(self.url, headers={"Range": f"bytes=0-{len(VIDEO) * 3}"})  # end is clamped
        self.assertEqual(self.body(resp), VIDEO)

    def test_unsatisfiable_and_malformed_ranges(self):
        resp = self.client.get(self.url, headers={"Range": f"bytes={len(VIDEO) + 5}-"})
        self.assertEqual((resp.status_code, resp["Content-Range"]), (416, f"bytes */{len(VIDEO)}"))
        self.assertEqual(self.client.get(self.url, headers={"Range": "bytes=9-3"}).status_code, 416)
        resp = self.client.get(self.url, headers={"Range": "garbage"})  # ignored -> whole file
        self.assertEqual((resp.status_code, self.body(resp)), (200, VIDEO))

    def test_only_authorised_people_can_stream(self):
        for user in (self.stranger,):
            self.client.force_login(user)
            self.assertEqual(self.client.get(self.url).status_code, 404)
        self.client.logout()
        self.assertEqual(self.client.get(self.url).status_code, 302)
        pending = User.objects.create_user("p", "p@e.com", "pw-12345-xyz")
        Enrollment.objects.create(course=self.course, user=pending, full_name="p", phone="09120000008")
        self.client.force_login(pending)
        self.assertEqual(self.client.get(self.url).status_code, 404)  # not confirmed yet
        self.client.force_login(self.teacher)  # the course's own instructor can preview
        self.assertEqual(self.client.get(self.url).status_code, 200)
        other_teacher = User.objects.create_user("t2", "t2@e.com", "pw-12345-xyz", is_instructor=True)
        self.client.force_login(other_teacher)
        self.assertEqual(self.client.get(self.url).status_code, 404)

    def test_unpublished_or_videoless_lesson_is_404(self):
        Lesson.objects.filter(pk=self.lesson.pk).update(is_published=False)
        self.assertEqual(self.client.get(self.url).status_code, 404)
        plain = Lesson.objects.create(course=self.course, title="بدون ویدئو")
        self.assertEqual(self.client.get(reverse("panel:lesson_video", args=["python", plain.pk])).status_code, 404)

    def test_lesson_page_uses_player_without_download(self):
        html = self.client.get(reverse("panel:lesson", args=["python", self.lesson.pk])).content.decode()
        self.assertIn("<video", html)
        self.assertIn("nodownload", html)
        self.assertIn(self.url, html)
        self.assertNotIn("videos/lesson", html)  # the storage path is never exposed


class ReportCardTests(StudentFeatureBase):
    def make_sessions(self):
        past = timezone.now() - datetime.timedelta(days=3)
        return [ClassSession.objects.create(batch=self.batch, title=f"s{i}", starts_at=past - datetime.timedelta(days=i))
                for i in range(4)]

    def test_attendance_rate_rules(self):
        s1, s2, s3, s4 = self.make_sessions()
        ClassSession.objects.create(batch=self.batch, title="future", starts_at=timezone.now() + datetime.timedelta(days=2))
        Attendance.objects.create(session=s1, user=self.student, status="present")
        Attendance.objects.create(session=s2, user=self.student, status="late")
        Attendance.objects.create(session=s3, user=self.student, status="excused")
        # s4 is unmarked: counts as absent; the future session is ignored; excused is not held against the student
        a = attendance_summary(self.student, self.course)
        self.assertEqual((a["total"], a["present"], a["late"], a["absent"], a["excused"]), (4, 1, 1, 1, 1))
        self.assertEqual(a["rate"], 67)  # 2 attended of 3 counted

    def test_other_batch_sessions_do_not_count(self):
        ClassSession.objects.create(batch=self.other_batch, title="x", starts_at=timezone.now() - datetime.timedelta(days=1))
        self.assertEqual(attendance_summary(self.student, self.course), {
            "present": 0, "late": 0, "absent": 0, "excused": 0, "total": 0, "attended": 0, "rate": None})

    def test_report_page_and_access(self):
        self.make_sessions()
        page = self.client.get(reverse("panel:report", args=["python"]))
        self.assertContains(page, "کارنامه")
        self.assertEqual(student_report(self.student, self.course)["attendance"]["total"], 4)
        self.client.force_login(self.stranger)
        self.assertEqual(self.client.get(reverse("panel:report", args=["python"])).status_code, 404)

import datetime

from django.core.cache import cache
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from accounts.models import User
from core.testing import use_temp_private_storage
from courses.models import (Announcement, Assignment, Attendance, Batch, Category, ClassSession, Course, Enrollment,
                            Lesson, Submission)
from notifications.models import Notification


@override_settings(MAGAZINE_URL="")
class TeacherBase(TestCase):
    @classmethod
    def setUpTestData(cls):
        cat = Category.objects.create(name="c", slug="c")
        cls.teacher = User.objects.create_user("teacher", "t@e.com", "pw-12345-xyz", is_instructor=True)
        cls.rival = User.objects.create_user("rival", "r@e.com", "pw-12345-xyz", is_instructor=True)
        cls.student = User.objects.create_user("sara", "s@e.com", "pw-12345-xyz", first_name="سارا")
        cls.other_student = User.objects.create_user("ali", "a@e.com", "pw-12345-xyz")
        cls.course = Course.objects.create(title="پایتون", slug="python", category=cat, summary="s", is_published=True,
                                           instructor=cls.teacher)
        cls.rival_course = Course.objects.create(title="دورهٔ رقیب", slug="web", category=cat, summary="s", is_published=True,
                                                 instructor=cls.rival)
        cls.batch = Batch.objects.create(course=cls.course, title="b1", start_date=timezone.localdate())
        cls.rival_batch = Batch.objects.create(course=cls.rival_course, title="rb", start_date=timezone.localdate())
        Enrollment.objects.create(course=cls.course, batch=cls.batch, user=cls.student, full_name="سارا", phone="09120000000",
                                  status=Enrollment.Status.CONFIRMED)
        Notification.objects.all().delete()  # drop the "enrollment confirmed" notice made by the fixture

    def setUp(self):
        cache.clear()
        use_temp_private_storage(self)
        self.client.force_login(self.teacher)


class AccessTests(TeacherBase):
    def test_only_instructors_get_in(self):
        self.assertEqual(self.client.get(reverse("teacher:dashboard")).status_code, 200)
        self.client.force_login(self.student)
        for name, args in (("dashboard", []), ("course", ["python"]), ("lessons", ["python"])):
            self.assertEqual(self.client.get(reverse(f"teacher:{name}", args=args)).status_code, 404)
        self.client.logout()
        self.assertEqual(self.client.get(reverse("teacher:dashboard")).status_code, 302)

    def test_instructor_cannot_touch_another_instructors_course(self):
        lesson = Lesson.objects.create(course=self.rival_course, title="x")
        for url in (reverse("teacher:course", args=["web"]), reverse("teacher:lessons", args=["web"]),
                    reverse("teacher:lesson_edit", args=["web", lesson.pk]), reverse("teacher:sessions", args=["web"]),
                    reverse("teacher:students", args=["web"]), reverse("teacher:announcements", args=["web"])):
            self.assertEqual(self.client.get(url).status_code, 404, url)
        self.assertEqual(self.client.post(reverse("teacher:lesson_delete", args=["web", lesson.pk])).status_code, 404)
        self.assertTrue(Lesson.objects.filter(pk=lesson.pk).exists())

    def test_object_ids_must_belong_to_the_url_course(self):
        rival_lesson = Lesson.objects.create(course=self.rival_course, title="x")
        self.assertEqual(self.client.get(reverse("teacher:lesson_edit", args=["python", rival_lesson.pk])).status_code, 404)
        self.assertEqual(self.client.post(reverse("teacher:lesson_delete", args=["python", rival_lesson.pk])).status_code, 404)
        rival_assignment = Assignment.objects.create(course=self.rival_course, title="a", description="d")
        self.assertEqual(self.client.get(reverse("teacher:assignment", args=["python", rival_assignment.pk])).status_code, 404)
        rival_session = ClassSession.objects.create(batch=self.rival_batch, title="s", starts_at=timezone.now())
        self.assertEqual(self.client.get(reverse("teacher:attendance", args=["python", rival_session.pk])).status_code, 404)

    def test_superuser_sees_everything_and_dashboard_lists_only_own(self):
        page = self.client.get(reverse("teacher:dashboard"))
        self.assertContains(page, "پایتون")
        self.assertNotContains(page, "دورهٔ رقیب")
        admin = User.objects.create_superuser("boss", "b@e.com", "pw-12345-xyz")
        self.client.force_login(admin)
        self.assertEqual(self.client.get(reverse("teacher:course", args=["web"])).status_code, 200)

    def test_draft_course_is_still_manageable_by_its_instructor(self):
        Course.objects.filter(pk=self.course.pk).update(is_published=False)
        self.assertEqual(self.client.get(reverse("teacher:lessons", args=["python"])).status_code, 200)


class LessonTests(TeacherBase):
    def test_create_with_video_and_delete_removes_files(self):
        video = SimpleUploadedFile("intro.mp4", b"\x00" * 2048, content_type="video/mp4")
        resp = self.client.post(reverse("teacher:lesson_new", args=["python"]), {
            "title": "مقدمه", "order": 1, "duration_minutes": 10, "is_published": "on", "video_file": video})
        self.assertRedirects(resp, reverse("teacher:lessons", args=["python"]))
        lesson = Lesson.objects.get()
        self.assertEqual((lesson.course, lesson.title), (self.course, "مقدمه"))
        path = lesson.video_file.path
        import os

        self.assertTrue(os.path.exists(path))
        self.client.post(reverse("teacher:lesson_delete", args=["python", lesson.pk]))
        self.assertFalse(Lesson.objects.exists())
        self.assertFalse(os.path.exists(path))

    def test_bad_video_type_and_size_rejected(self):
        url = reverse("teacher:lesson_new", args=["python"])
        base = {"title": "x", "order": 0, "duration_minutes": 0, "is_published": "on"}
        self.client.post(url, {**base, "video_file": SimpleUploadedFile("evil.exe", b"MZ")})
        self.assertFalse(Lesson.objects.exists())
        with self.settings(MAX_VIDEO_UPLOAD_MB=0):
            self.client.post(url, {**base, "video_file": SimpleUploadedFile("big.mp4", b"x" * 10)})
        self.assertFalse(Lesson.objects.exists())

    def test_edit_cannot_move_lesson_to_another_course(self):
        lesson = Lesson.objects.create(course=self.course, title="old")
        self.client.post(reverse("teacher:lesson_edit", args=["python", lesson.pk]),
                         {"title": "new", "order": 0, "duration_minutes": 0, "course": self.rival_course.pk})
        lesson.refresh_from_db()
        self.assertEqual((lesson.title, lesson.course), ("new", self.course))


class AnnouncementAndGradingTests(TeacherBase):
    def test_announcement_notifies_students_of_this_course_only(self):
        Enrollment.objects.create(course=self.rival_course, user=self.other_student, full_name="ali", phone="09120000001",
                                  status=Enrollment.Status.CONFIRMED)
        Notification.objects.all().delete()  # the line above (confirmed enrollment) made a "confirmed" notice
        self.client.post(reverse("teacher:announcements", args=["python"]), {"title": "سلام", "body": "متن", "is_published": "on"})
        self.assertEqual(Announcement.objects.get().course, self.course)
        self.assertTrue(Notification.objects.filter(user=self.student, title="سلام").exists())
        self.assertFalse(Notification.objects.filter(user=self.other_student).exists())

    def test_announcement_batch_must_belong_to_the_course(self):
        resp = self.client.post(reverse("teacher:announcements", args=["python"]),
                                {"title": "x", "body": "y", "batch": self.rival_batch.pk, "is_published": "on"})
        self.assertFalse(Announcement.objects.exists())
        self.assertEqual(resp.status_code, 200)

    def test_grading_flow(self):
        assignment = Assignment.objects.create(course=self.course, title="پروژه", description="d", is_published=True, max_score=20)
        sub = Submission.objects.create(assignment=assignment, user=self.student, text="پاسخ")
        url = reverse("teacher:grade", args=["python", assignment.pk, sub.pk])
        self.assertContains(self.client.get(url), "پاسخ")
        self.assertEqual(self.client.post(url, {"score": 25, "feedback": "x"}).status_code, 200)  # over the maximum
        sub.refresh_from_db()
        self.assertIsNone(sub.score)
        self.client.post(url, {"score": 18, "feedback": "آفرین"})
        sub.refresh_from_db()
        self.assertEqual((sub.score, sub.feedback), (18, "آفرین"))
        self.assertIsNotNone(sub.graded_at)
        note = Notification.objects.get(user=self.student)
        self.assertIn("18", note.body)
        self.assertEqual(note.url, reverse("panel:assignment", args=["python", assignment.pk]))

    def test_cannot_grade_a_submission_of_another_assignment(self):
        mine = Assignment.objects.create(course=self.course, title="a", description="d")
        theirs = Assignment.objects.create(course=self.rival_course, title="b", description="d")
        sub = Submission.objects.create(assignment=theirs, user=self.student, text="x")
        self.assertEqual(self.client.get(reverse("teacher:grade", args=["python", mine.pk, sub.pk])).status_code, 404)
        self.assertEqual(self.client.post(reverse("teacher:grade", args=["python", mine.pk, sub.pk]), {"score": 5}).status_code, 404)

    def test_instructor_can_download_submission_file_but_not_a_rivals(self):
        assignment = Assignment.objects.create(course=self.course, title="a", description="d", is_published=True)
        sub = Submission(assignment=assignment, user=self.student, text="x")
        sub.file.save("a.txt", SimpleUploadedFile("a.txt", b"hello"), save=True)
        url = reverse("panel:submission_file", args=[sub.pk])
        self.assertEqual(b"".join(self.client.get(url).streaming_content), b"hello")
        self.client.force_login(self.rival)
        self.assertEqual(self.client.get(url).status_code, 404)

    def test_new_submission_notifies_instructor(self):
        assignment = Assignment.objects.create(course=self.course, title="پروژه", description="d", is_published=True)
        self.client.force_login(self.student)
        self.client.post(reverse("panel:assignment", args=["python", assignment.pk]), {"text": "پاسخ"})
        self.client.post(reverse("panel:assignment", args=["python", assignment.pk]), {"text": "ویرایش"})
        self.assertEqual(Notification.objects.filter(user=self.teacher).count(), 1)  # only the first submission


class SessionAndAttendanceTests(TeacherBase):
    def when(self):
        return (timezone.now() + datetime.timedelta(days=1)).strftime("%Y-%m-%dT%H:%M")

    def test_session_batch_limited_to_own_course(self):
        url = reverse("teacher:session_new", args=["python"])
        self.client.post(url, {"batch": self.rival_batch.pk, "title": "x", "starts_at": self.when(), "duration_minutes": 60})
        self.assertFalse(ClassSession.objects.exists())
        self.client.post(url, {"batch": self.batch.pk, "title": "جلسه ۱", "starts_at": self.when(), "duration_minutes": 60})
        self.assertEqual(ClassSession.objects.get().batch, self.batch)

    def test_attendance_marks_only_students_of_the_batch(self):
        session = ClassSession.objects.create(batch=self.batch, title="s", starts_at=timezone.now())
        url = reverse("teacher:attendance", args=["python", session.pk])
        self.assertContains(self.client.get(url), "سارا")
        self.client.post(url, {f"status_{self.student.pk}": "late", f"note_{self.student.pk}": "ترافیک",
                               f"status_{self.other_student.pk}": "present"})  # not enrolled: ignored
        record = Attendance.objects.get()
        self.assertEqual((record.user, record.status, record.note), (self.student, "late", "ترافیک"))
        self.client.post(url, {f"status_{self.student.pk}": "absent"})  # update, not duplicate
        self.assertEqual(Attendance.objects.get().status, "absent")
        self.client.post(url, {f"status_{self.student.pk}": "hacked"})  # invalid value ignored
        self.assertEqual(Attendance.objects.get().status, "absent")

    def test_students_list_and_detail(self):
        self.assertContains(self.client.get(reverse("teacher:students", args=["python"])), "سارا")
        self.assertEqual(self.client.get(reverse("teacher:student", args=["python", self.student.pk])).status_code, 200)
        self.assertEqual(self.client.get(reverse("teacher:student", args=["python", self.other_student.pk])).status_code, 404)

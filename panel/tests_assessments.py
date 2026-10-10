import datetime
import shutil
import tempfile

from django.contrib.auth.models import Permission
from django.core import mail
from django.core.cache import cache
from django.core.files.storage import FileSystemStorage
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from accounts.models import User
from courses.certificates import issue_certificate, requirements
from courses.models import (Assignment, Category, Certificate, Choice, Course, Enrollment, Lesson, LessonProgress,
                            Question, Quiz, QuizAttempt, Submission)

PRIVATE = tempfile.mkdtemp()


def tearDownModule():
    shutil.rmtree(PRIVATE, ignore_errors=True)


def make_quiz(course, **kw):
    quiz = Quiz.objects.create(course=course, title="آزمون", is_published=True, **kw)
    for i in range(2):
        q = Question.objects.create(quiz=quiz, text=f"سؤال {i}", order=i)
        Choice.objects.create(question=q, text="درست", is_correct=True, order=0)
        Choice.objects.create(question=q, text="غلط", order=1)
    return quiz


def answers_for(quiz, right=True):
    out = {}
    for q in quiz.questions.all():
        out[f"q{q.pk}"] = q.choices.get(is_correct=right).pk
    return out


@override_settings(MAGAZINE_URL="http://127.0.0.1:9")
class AssessmentBase(TestCase):
    @classmethod
    def setUpTestData(cls):
        cat = Category.objects.create(name="c", slug="c")
        cls.course = Course.objects.create(title="پایتون", slug="python", category=cat, summary="s", is_published=True)
        cls.student = User.objects.create_user("sara", "s@e.com", "pw-12345-xyz")
        cls.other = User.objects.create_user("bob", "b@e.com", "pw-12345-xyz")
        for u in (cls.student, cls.other):
            Enrollment.objects.create(course=cls.course, user=u, full_name="سارا احمدی" if u == cls.student else "باب",
                                      phone="09120000000", status=Enrollment.Status.CONFIRMED)

    def setUp(self):
        cache.clear()
        self.client.force_login(self.student)
        field = Submission._meta.get_field("file")
        old, field.storage = field.storage, FileSystemStorage(location=PRIVATE)
        self.addCleanup(setattr, field, "storage", old)


class QuizTests(AssessmentBase):
    def start(self, quiz):
        resp = self.client.post(reverse("panel:quiz_start", args=["python", quiz.pk]))
        return QuizAttempt.objects.filter(user=self.student, quiz=quiz).latest("id"), resp

    def submit(self, attempt, data):
        return self.client.post(reverse("panel:quiz_attempt", args=["python", attempt.quiz_id, attempt.pk]), data)

    def test_answer_key_not_leaked_while_taking(self):
        quiz = make_quiz(self.course)
        attempt, _ = self.start(quiz)
        html = self.client.get(reverse("panel:quiz_attempt", args=["python", quiz.pk, attempt.pk])).content.decode()
        right_ids = list(Choice.objects.filter(is_correct=True).values_list("pk", flat=True))
        self.assertIn('name="q', html)
        self.assertNotIn("is_correct", html)
        self.assertNotIn("correct", html.lower().replace("incorrect", ""))
        self.assertEqual(len(right_ids), 2)

    def test_grading_pass_and_fail(self):
        quiz = make_quiz(self.course, pass_percent=60)
        attempt, _ = self.start(quiz)
        self.submit(attempt, answers_for(quiz, right=True))
        attempt.refresh_from_db()
        self.assertEqual((attempt.score_percent, attempt.passed), (100, True))
        attempt2, _ = self.start(quiz)
        self.submit(attempt2, answers_for(quiz, right=False))
        attempt2.refresh_from_db()
        self.assertEqual((attempt2.score_percent, attempt2.passed), (0, False))

    def test_partial_score_and_junk_answers_ignored(self):
        quiz = make_quiz(self.course, pass_percent=60)
        attempt, _ = self.start(quiz)
        q1, q2 = list(quiz.questions.all())
        foreign = Choice.objects.exclude(question__quiz=quiz).count()
        data = {f"q{q1.pk}": q1.choices.get(is_correct=True).pk, f"q{q2.pk}": 999999, "q99999": 1, "x": "y"}
        self.submit(attempt, data)
        attempt.refresh_from_db()
        self.assertEqual(attempt.score_percent, 50)
        self.assertFalse(attempt.passed)
        self.assertNotIn(str(q2.pk), attempt.answers)
        self.assertEqual(foreign, 0)

    def test_choice_from_another_question_does_not_count(self):
        quiz = make_quiz(self.course)
        attempt, _ = self.start(quiz)
        q1, q2 = list(quiz.questions.all())
        self.submit(attempt, {f"q{q1.pk}": q2.choices.get(is_correct=True).pk})
        attempt.refresh_from_db()
        self.assertEqual(attempt.score_percent, 0)

    def test_late_submission_scores_zero(self):
        quiz = make_quiz(self.course, time_limit_minutes=10)
        attempt, _ = self.start(quiz)
        QuizAttempt.objects.filter(pk=attempt.pk).update(started_at=timezone.now() - datetime.timedelta(minutes=12))
        self.submit(attempt, answers_for(quiz))
        attempt.refresh_from_db()
        self.assertTrue(attempt.timed_out)
        self.assertEqual((attempt.score_percent, attempt.passed), (0, False))

    def test_within_grace_period_is_accepted(self):
        quiz = make_quiz(self.course, time_limit_minutes=10)
        attempt, _ = self.start(quiz)
        QuizAttempt.objects.filter(pk=attempt.pk).update(
            started_at=timezone.now() - datetime.timedelta(minutes=10, seconds=20))
        self.submit(attempt, answers_for(quiz))
        attempt.refresh_from_db()
        self.assertTrue(attempt.passed)

    def test_max_attempts_and_resume(self):
        quiz = make_quiz(self.course, max_attempts=1)
        first, _ = self.start(quiz)
        again, _ = self.start(quiz)  # unfinished attempt is resumed, not duplicated
        self.assertEqual(first.pk, again.pk)
        self.submit(first, answers_for(quiz, right=False))
        self.start(quiz)
        self.assertEqual(QuizAttempt.objects.filter(user=self.student).count(), 1)

    def test_cannot_resubmit_or_use_others_attempt(self):
        quiz = make_quiz(self.course)
        attempt, _ = self.start(quiz)
        self.submit(attempt, answers_for(quiz, right=False))
        self.submit(attempt, answers_for(quiz, right=True))  # attempt already closed
        attempt.refresh_from_db()
        self.assertEqual(attempt.score_percent, 0)
        self.client.force_login(self.other)
        url = reverse("panel:quiz_result", args=["python", quiz.pk, attempt.pk])
        self.assertEqual(self.client.get(url).status_code, 404)

    def test_correct_answers_shown_only_if_enabled(self):
        quiz = make_quiz(self.course, show_answers=False)
        attempt, _ = self.start(quiz)
        self.submit(attempt, answers_for(quiz, right=False))
        url = reverse("panel:quiz_result", args=["python", quiz.pk, attempt.pk])
        self.assertNotContains(self.client.get(url), "پاسخ صحیح:")
        Quiz.objects.filter(pk=quiz.pk).update(show_answers=True)
        self.assertContains(self.client.get(url), "پاسخ صحیح:")

    def test_unpublished_quiz_and_unenrolled_user(self):
        quiz = make_quiz(self.course)
        Quiz.objects.filter(pk=quiz.pk).update(is_published=False)
        self.assertEqual(self.client.get(reverse("panel:quiz", args=["python", quiz.pk])).status_code, 404)
        Quiz.objects.filter(pk=quiz.pk).update(is_published=True)
        stranger = User.objects.create_user("eve", "e@e.com", "pw-12345-xyz")
        self.client.force_login(stranger)
        self.assertEqual(self.client.post(reverse("panel:quiz_start", args=["python", quiz.pk])).status_code, 404)

    def test_admin_requires_one_correct_choice(self):
        from courses.admin import ChoiceInlineFormSet

        quiz = make_quiz(self.course)
        q = quiz.questions.first()
        data = {"choices-TOTAL_FORMS": "2", "choices-INITIAL_FORMS": "0", "choices-MIN_NUM_FORMS": "0",
                "choices-MAX_NUM_FORMS": "1000", "choices-0-text": "a", "choices-0-order": "0", "choices-1-text": "b", "choices-1-order": "1"}
        from django.forms import inlineformset_factory

        FormSet = inlineformset_factory(Question, Choice, formset=ChoiceInlineFormSet, fields=("text", "is_correct", "order"))
        self.assertFalse(FormSet(data, instance=q, prefix="choices").is_valid())  # no correct choice
        data["choices-0-is_correct"] = "on"
        data["choices-1-is_correct"] = "on"
        self.assertFalse(FormSet(data, instance=q, prefix="choices").is_valid())  # two correct choices
        del data["choices-1-is_correct"]
        # instance q already has choices; formset only sees the submitted forms
        self.assertTrue(FormSet(data, instance=q, prefix="choices").is_valid())


class AssignmentTests(AssessmentBase):
    def setUp(self):
        super().setUp()
        self.assignment = Assignment.objects.create(course=self.course, title="پروژه", description="d", is_published=True)
        self.url = reverse("panel:assignment", args=["python", self.assignment.pk])

    def test_submit_text_and_resubmit_until_graded(self):
        self.client.post(self.url, {"text": "نسخه یک"})
        self.client.post(self.url, {"text": "نسخه دو"})
        sub = Submission.objects.get()
        self.assertEqual(sub.text, "نسخه دو")
        sub.score = 80
        sub.save()
        resp = self.client.post(self.url, {"text": "تقلب"})
        sub.refresh_from_db()
        self.assertEqual(sub.text, "نسخه دو")
        self.assertContains(resp, "نمره‌گذاری شده")

    def test_empty_submission_rejected(self):
        self.assertContains(self.client.post(self.url, {"text": " "}), "متن یا فایل")
        self.assertFalse(Submission.objects.exists())

    def test_deadline_enforced_unless_late_allowed(self):
        Assignment.objects.filter(pk=self.assignment.pk).update(due_at=timezone.now() - datetime.timedelta(hours=1))
        self.assertContains(self.client.post(self.url, {"text": "دیر"}), "مهلت تحویل")
        self.assertFalse(Submission.objects.exists())
        Assignment.objects.filter(pk=self.assignment.pk).update(allow_late=True)
        self.client.post(self.url, {"text": "دیر ولی مجاز"})
        self.assertEqual(Submission.objects.count(), 1)

    def test_file_upload_rules(self):
        bad = SimpleUploadedFile("evil.exe", b"MZ")
        self.assertContains(self.client.post(self.url, {"text": "x", "file": bad}), "alert")
        self.assertFalse(Submission.objects.exists())
        with self.settings(MAX_SUBMISSION_MB=0):
            big = SimpleUploadedFile("a.txt", b"hello")
            self.assertContains(self.client.post(self.url, {"text": "x", "file": big}), "حجم فایل")
        self.client.post(self.url, {"text": "x", "file": SimpleUploadedFile("a.txt", b"hello")})
        self.assertTrue(Submission.objects.get().file.name.endswith(".txt"))

    def test_file_download_access(self):
        self.client.post(self.url, {"text": "x", "file": SimpleUploadedFile("a.txt", b"hello")})
        sub = Submission.objects.get()
        url = reverse("panel:submission_file", args=[sub.pk])
        self.assertEqual(b"".join(self.client.get(url).streaming_content), b"hello")
        self.client.force_login(self.other)
        self.assertEqual(self.client.get(url).status_code, 404)
        grader = User.objects.create_user("teacher", "t@e.com", "pw-12345-xyz", is_staff=True)
        grader.user_permissions.add(Permission.objects.get(codename="change_submission"))
        self.client.force_login(grader)
        self.assertEqual(b"".join(self.client.get(url).streaming_content), b"hello")
        self.client.logout()
        self.assertEqual(self.client.get(url).status_code, 302)

    def test_grading_in_admin_emails_student_and_caps_score(self):
        from django.contrib.admin.sites import site
        from django.test import RequestFactory

        from courses.admin import SubmissionAdmin

        sub = Submission.objects.create(assignment=self.assignment, user=self.student, text="x")

        class FakeForm:
            changed_data = ["score"]

        sub.score = 500
        SubmissionAdmin(Submission, site).save_model(RequestFactory().post("/"), sub, FakeForm(), True)
        sub.refresh_from_db()
        self.assertEqual(sub.score, self.assignment.max_score)
        self.assertIsNotNone(sub.graded_at)
        self.assertEqual(mail.outbox[0].to, ["s@e.com"])

    def test_pass_threshold(self):
        sub = Submission(assignment=self.assignment, user=self.student, score=49)
        self.assertFalse(sub.passed)
        sub.score = 50
        self.assertTrue(sub.passed)
        self.assertFalse(Submission(assignment=self.assignment, user=self.student).passed)  # ungraded


class CertificateTests(AssessmentBase):
    def setUp(self):
        super().setUp()
        self.lesson = Lesson.objects.create(course=self.course, title="l")
        self.quiz = make_quiz(self.course)
        self.assignment = Assignment.objects.create(course=self.course, title="p", description="d", is_published=True)

    def complete_everything(self, user=None):
        user = user or self.student
        LessonProgress.objects.get_or_create(user=user, lesson=self.lesson)
        QuizAttempt.objects.create(user=user, quiz=self.quiz, submitted_at=timezone.now(), score_percent=100, passed=True)
        Submission.objects.update_or_create(assignment=self.assignment, user=user, defaults={"score": 90})

    def test_not_eligible_until_every_requirement_done(self):
        self.assertIsNone(issue_certificate(self.student, self.course))
        self.assertEqual([i["done"] for i in requirements(self.student, self.course)], [False, False, False])
        LessonProgress.objects.create(user=self.student, lesson=self.lesson)
        QuizAttempt.objects.create(user=self.student, quiz=self.quiz, submitted_at=timezone.now(), score_percent=30, passed=False)
        self.assertIsNone(issue_certificate(self.student, self.course))  # failed quiz, no assignment
        Submission.objects.create(assignment=self.assignment, user=self.student, score=10)
        self.assertIsNone(issue_certificate(self.student, self.course))  # failed assignment

    def test_issue_when_complete_and_idempotent(self):
        self.complete_everything()
        cert = issue_certificate(self.student, self.course)
        self.assertEqual(cert.holder_name, "سارا احمدی")
        self.assertTrue(cert.code.startswith("ITA-"))
        self.assertEqual(issue_certificate(self.student, self.course), cert)
        self.assertEqual(Certificate.objects.count(), 1)

    def test_needs_confirmed_enrollment(self):
        self.complete_everything()
        Enrollment.objects.filter(user=self.student).update(status=Enrollment.Status.CANCELLED)
        self.assertIsNone(issue_certificate(self.student, self.course))

    def test_course_without_content_has_no_certificate(self):
        empty = Course.objects.create(title="خالی", slug="empty", category=self.course.category, summary="s", is_published=True)
        Enrollment.objects.create(course=empty, user=self.student, full_name="s", phone="09120000000", status="confirmed")
        self.assertIsNone(issue_certificate(self.student, empty))

    def test_issue_view_and_public_verification(self):
        resp = self.client.post(reverse("panel:certificate_issue", args=["python"]))
        self.assertRedirects(resp, reverse("panel:course", args=["python"]))
        self.assertFalse(Certificate.objects.exists())
        self.complete_everything()
        resp = self.client.post(reverse("panel:certificate_issue", args=["python"]))
        cert = Certificate.objects.get()
        self.assertRedirects(resp, cert.get_absolute_url())
        self.client.logout()  # verification is public
        page = self.client.get(cert.get_absolute_url())
        self.assertContains(page, "سارا احمدی")
        self.assertContains(page, "معتبر")
        self.assertEqual(self.client.get(reverse("courses:certificate", args=[cert.code.lower()])).status_code, 200)
        self.assertEqual(self.client.get(reverse("courses:certificate", args=["ITA-NOPE"])).status_code, 404)

    def test_revoked_certificate_is_flagged(self):
        self.complete_everything()
        cert = issue_certificate(self.student, self.course)
        Certificate.objects.filter(pk=cert.pk).update(is_revoked=True)
        page = self.client.get(cert.get_absolute_url())
        self.assertContains(page, "ابطال شده")
        self.assertNotContains(page, "سارا احمدی")
        self.assertNotContains(self.client.get(reverse("panel:certificates")), cert.code)

    def test_course_page_and_dashboard_render_new_sections(self):
        self.complete_everything()
        page = self.client.get(reverse("panel:course", args=["python"]))
        self.assertContains(page, "آزمون")
        self.assertContains(page, "دریافت گواهی")
        self.assertEqual(self.client.get(reverse("panel:dashboard")).status_code, 200)
        self.assertEqual(self.client.get(reverse("panel:certificates")).status_code, 200)

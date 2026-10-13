import datetime

from django.contrib.auth.models import Permission
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from accounts.models import User
from courses.models import Batch, Category, Certificate, Course, Enrollment, Review, WaitlistEntry


@override_settings(MAGAZINE_URL="")
class ReportsTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cat = Category.objects.create(name="c", slug="c")
        cls.py = Course.objects.create(title="پایتون", slug="py", category=cat, summary="s", is_published=True, price=1000)
        cls.web = Course.objects.create(title="وب", slug="web", category=cat, summary="s", is_published=True, price=500)
        cls.boss = User.objects.create_superuser("boss", "b@e.com", "pw-12345-xyz")
        cls.staff = User.objects.create_user("staff", "st@e.com", "pw-12345-xyz", is_staff=True)
        cls.student = User.objects.create_user("sara", "s@e.com", "pw-12345-xyz")
        cls.users = [User.objects.create_user(f"u{i}", f"u{i}@e.com", "pw-12345-xyz") for i in range(3)]

    def enroll(self, course, user, status, paid=0):
        e = Enrollment.objects.create(course=course, user=user, full_name=user.username, phone="09120000000", status=status)
        Enrollment.objects.filter(pk=e.pk).update(paid_amount=paid)
        return e

    def test_access_control(self):
        url = reverse("reports:dashboard")
        self.assertEqual(self.client.get(url).status_code, 302)
        self.client.force_login(self.student)
        self.assertEqual(self.client.get(url).status_code, 404)
        self.client.force_login(self.staff)  # staff without the permission
        self.assertEqual(self.client.get(url).status_code, 404)
        self.staff.user_permissions.add(Permission.objects.get(codename="view_enrollment"))
        self.client.force_login(User.objects.get(pk=self.staff.pk))
        self.assertEqual(self.client.get(url).status_code, 200)
        self.client.force_login(self.boss)
        self.assertEqual(self.client.get(url).status_code, 200)

    def test_numbers(self):
        c, p, x = Enrollment.Status.CONFIRMED, Enrollment.Status.PENDING, Enrollment.Status.CANCELLED
        self.enroll(self.py, self.users[0], c, paid=1000)   # paid in full
        self.enroll(self.py, self.users[1], c, paid=400)    # 600 outstanding
        self.enroll(self.web, self.users[2], c, paid=900)   # overpaid: outstanding is not negative
        self.enroll(self.py, self.student, p)
        self.enroll(self.web, self.student, x, paid=500)    # cancelled: not counted as revenue base
        Certificate.objects.create(user=self.users[0], course=self.py, holder_name="a")
        Review.objects.create(course=self.py, user=self.users[0], rating=5, text="x", is_approved=True)
        Review.objects.create(course=self.py, user=self.users[1], rating=3, text="x", is_approved=True)
        Review.objects.create(course=self.py, user=self.users[2], rating=1, text="x", is_approved=False)  # ignored
        batch = Batch.objects.create(course=self.py, start_date=timezone.localdate(), capacity=1)
        WaitlistEntry.objects.create(batch=batch, full_name="w", phone="1")
        self.client.force_login(self.boss)
        resp = self.client.get(reverse("reports:dashboard"))
        kpi = resp.context["kpi"]
        self.assertEqual((kpi["expected"], kpi["collected"], kpi["outstanding"]), (1000 + 1000 + 500, 1000 + 400 + 900, 600))
        self.assertEqual((kpi["confirmed"], kpi["pending"], kpi["students"], kpi["new"]), (3, 1, 3, 4))
        self.assertEqual((kpi["waiting"], kpi["certificates"]), (1, 1))
        rows = {r["course"].slug: r for r in resp.context["rows"]}
        self.assertEqual((rows["py"]["confirmed"], rows["py"]["certificates"], rows["py"]["completion"]), (2, 1, 50))
        self.assertEqual(rows["py"]["rating"], 4.0)
        self.assertEqual(rows["py"]["collected"], 1400)
        self.assertEqual(resp.context["rows"][0]["course"].slug, "py")  # most new enrollments first

    def test_periods_and_trend(self):
        e = self.enroll(self.py, self.users[0], Enrollment.Status.CONFIRMED)
        Enrollment.objects.filter(pk=e.pk).update(created_at=timezone.now() - datetime.timedelta(days=60))
        self.enroll(self.py, self.users[1], Enrollment.Status.CONFIRMED)
        self.client.force_login(self.boss)
        by_days = {}
        for days in (30, 90, 365):
            resp = self.client.get(reverse("reports:dashboard"), {"days": days})
            self.assertEqual(resp.status_code, 200)
            by_days[days] = (resp.context["trend_total"], len(resp.context["trend"]))
        self.assertEqual([by_days[d][0] for d in (30, 90, 365)], [1, 2, 2])  # the old one only shows in longer periods
        self.assertEqual(by_days[30][1], 31)          # daily buckets
        self.assertLess(by_days[365][1], 60)           # weekly buckets
        for bad in ("abc", "7", "-1", ""):
            self.assertEqual(self.client.get(reverse("reports:dashboard"), {"days": bad}).context["days"], 30)

    def test_empty_database_renders(self):
        Course.objects.all().delete()
        self.client.force_login(self.boss)
        self.assertEqual(self.client.get(reverse("reports:dashboard")).status_code, 200)


class MoneyFilterTests(TestCase):
    def test_zero_is_not_free(self):
        from core.templatetags.school import money, toman

        self.assertEqual(money(0), "۰ تومان")
        self.assertEqual(money(None), "۰ تومان")
        self.assertEqual(money(1500000), "۱٬۵۰۰٬۰۰۰ تومان")
        self.assertEqual(toman(0), "رایگان")  # for course prices, zero really means free

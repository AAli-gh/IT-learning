import datetime
from unittest import mock

from django.core.cache import cache
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from accounts.models import User
from core import magazine
from courses.models import Batch, Category, Course, Enrollment


def make_course(slug="python", tag="python", published=True, **kw):
    cat, _ = Category.objects.get_or_create(slug="programming", defaults={"name": "برنامه‌نویسی"})
    return Course.objects.create(title=f"دوره {slug}", slug=slug, category=cat, summary="خلاصه",
                                 magazine_tag=tag, is_published=published, **kw)


class PublicPagesTests(TestCase):
    def setUp(self):
        cache.clear()
        patcher = mock.patch("core.magazine._get", return_value=[])
        patcher.start()
        self.addCleanup(patcher.stop)

    def test_home_and_list(self):
        make_course()
        self.assertContains(self.client.get(reverse("courses:home")), "دوره python")
        self.assertContains(self.client.get(reverse("courses:list")), "دوره python")

    def test_draft_course_hidden(self):
        make_course(published=False)
        self.assertEqual(self.client.get(reverse("courses:detail", args=["python"])).status_code, 404)
        self.assertEqual(self.client.get("/api/courses/").json()["count"], 0)

    def test_filters(self):
        make_course(level=Course.Level.ADVANCED)
        self.assertEqual(len(self.client.get(reverse("courses:list"), {"level": "beginner"}).context["page_obj"]), 0)
        self.assertEqual(len(self.client.get(reverse("courses:list"), {"q": "python"}).context["page_obj"]), 1)

    def test_404_page_renders(self):
        self.assertEqual(self.client.get("/no-such-page/").status_code, 404)

    def test_healthz_and_sitemap(self):
        self.assertEqual(self.client.get("/healthz").content, b"ok")
        make_course()
        self.assertContains(self.client.get("/sitemap.xml"), "/courses/python/")


class EnrollmentTests(TestCase):
    def setUp(self):
        cache.clear()
        mock.patch("core.magazine._get", return_value=[]).start()
        self.addCleanup(mock.patch.stopall)
        self.course = make_course()
        self.url = reverse("courses:enroll", args=["python"])

    def post(self, **extra):
        data = {"full_name": "سارا احمدی", "phone": "09121234567", **extra}
        return self.client.post(self.url, data)

    def test_enroll_ok_normalises_persian_digits(self):
        resp = self.post(phone="۰۹۱۲۱۲۳۴۵۶۷")
        self.assertEqual(resp.status_code, 302)
        self.assertEqual(Enrollment.objects.get().phone, "09121234567")

    def test_invalid_phone_rejected(self):
        self.assertEqual(self.post(phone="123").status_code, 200)
        self.assertFalse(Enrollment.objects.exists())

    def test_honeypot_rejected(self):
        self.post(website="http://spam")
        self.assertFalse(Enrollment.objects.exists())

    def test_full_batch_rejected(self):
        batch = Batch.objects.create(course=self.course, start_date=timezone.localdate() + datetime.timedelta(days=5),
                                     capacity=1)
        Enrollment.objects.create(course=self.course, batch=batch, full_name="x", phone="09120000000")
        self.post(batch=batch.pk)
        self.assertEqual(Enrollment.objects.count(), 1)

    def test_htmx_returns_partial(self):
        resp = self.client.post(self.url, {"full_name": "علی", "phone": "09121234567"}, headers={"HX-Request": "true"})
        self.assertContains(resp, "ثبت‌نام شما")

    def test_rate_limit(self):
        for _ in range(5):
            self.post()
        self.assertEqual(self.post().status_code, 429)

    def test_logged_in_user_linked(self):
        user = User.objects.create_user("sara", "s@e.com", "pw-12345-xyz")
        self.client.force_login(user)
        self.post()
        self.assertEqual(Enrollment.objects.get().user, user)


class ApiTests(TestCase):
    def test_tag_filter_and_shape(self):
        make_course("python", "python")
        make_course("web", "web")
        data = self.client.get("/api/courses/", {"tag": "python"}).json()
        self.assertEqual(data["count"], 1)
        self.assertEqual(data["results"][0]["slug"], "python")
        self.assertIn("/courses/python/", data["results"][0]["url"])

    def test_detail_has_topics_and_batches(self):
        make_course("python")
        data = self.client.get("/api/courses/python/").json()
        self.assertIn("topics", data)
        self.assertIn("batches", data)

    @override_settings(API_CORS_ALLOWED_ORIGINS=["https://mag.example"])
    def test_cors_only_for_allowed_origin(self):
        ok = self.client.get("/api/courses/", headers={"Origin": "https://mag.example"})
        self.assertEqual(ok["Access-Control-Allow-Origin"], "https://mag.example")
        bad = self.client.get("/api/courses/", headers={"Origin": "https://evil.example"})
        self.assertNotIn("Access-Control-Allow-Origin", bad)


class MagazineClientTests(TestCase):
    def setUp(self):
        cache.clear()

    @override_settings(MAGAZINE_API_URL="https://mag.example/api")
    def test_articles_for_tag_uses_tag_filter(self):
        payload = {"results": [{"title": "t", "url": "https://mag.example/a/"}]}
        with mock.patch("core.magazine.requests.get") as get:
            get.return_value.json.return_value = payload
            get.return_value.raise_for_status = lambda: None
            self.assertEqual(magazine.articles_for_tag("python"), payload["results"])
            self.assertEqual(get.call_args.kwargs["params"], {"tag": "python"})
            magazine.articles_for_tag("python")  # second call is served from cache
            self.assertEqual(get.call_count, 1)

    def test_fails_soft_when_magazine_down(self):
        import requests

        with mock.patch("core.magazine.requests.get", side_effect=requests.ConnectionError):
            self.assertEqual(magazine.latest_articles(), [])
        make_course()
        with mock.patch("core.magazine.requests.get", side_effect=requests.ConnectionError):
            self.assertEqual(self.client.get(reverse("courses:detail", args=["python"])).status_code, 200)

    def test_no_tag_no_request(self):
        with mock.patch("core.magazine.requests.get") as get:
            self.assertEqual(magazine.articles_for_tag(""), [])
            get.assert_not_called()

    def test_detail_renders_related_articles(self):
        make_course()
        arts = [{"title": "مقاله پایتون", "display_title": "مقاله پایتون", "url": "https://mag.example/a/", "excerpt": "e"}]
        with mock.patch("core.magazine._get", return_value=arts):
            self.assertContains(self.client.get(reverse("courses:detail", args=["python"])), "مقاله پایتون")


class HoneypotMarkupTests(TestCase):
    @mock.patch("core.magazine._get", return_value=[])
    def test_honeypot_label_is_hidden(self, _get):
        make_course()
        html = self.client.get(reverse("courses:detail", args=["python"])).content.decode()
        self.assertIn('class="form-field hp-field"', html)

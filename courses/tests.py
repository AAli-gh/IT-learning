import datetime
from unittest import mock

from django.conf import settings
from django.core.cache import cache
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from accounts.models import User
from core import magazine
from courses.models import Batch, Category, Course, Enrollment, Review


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

    @override_settings(MAGAZINE_URL="https://mag.example", MAGAZINE_API_URL="https://mag.example/api")
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


@mock.patch("core.magazine._get", return_value=[])
class SchoolFeatureTests(TestCase):
    def setUp(self):
        cache.clear()
        self.course = make_course()
        self.user = User.objects.create_user("sara", "s@e.com", "pw-12345-xyz")

    def confirm(self):
        Enrollment.objects.create(course=self.course, user=self.user, full_name="s", phone="09120000000",
                                  status=Enrollment.Status.CONFIRMED)

    def test_review_requires_confirmed_enrollment(self, _g):
        self.client.force_login(self.user)
        url = reverse("courses:review", args=["python"])
        self.client.post(url, {"rating": 5, "text": "عالی"})
        self.assertFalse(Review.objects.exists())
        self.confirm()
        self.client.post(url, {"rating": 5, "text": "عالی"})
        self.client.post(url, {"rating": 1, "text": "دوباره"})
        review = Review.objects.get()
        self.assertFalse(review.is_approved)  # needs staff approval
        self.assertNotContains(self.client.get(self.course.get_absolute_url()), "عالی</p>")

    def test_approved_review_shown_and_rating(self, _g):
        Review.objects.create(course=self.course, user=self.user, rating=4, text="خوب بود", is_approved=True)
        page = self.client.get(self.course.get_absolute_url())
        self.assertContains(page, "خوب بود")
        self.assertEqual(Course.objects.get().rating, 4.0)

    def test_enrollment_sends_emails(self, _g):
        from django.core import mail

        from core.models import SiteSettings

        s = SiteSettings.load(); s.contact_email = "office@example.com"; s.save(); cache.clear()
        self.client.post(reverse("courses:enroll", args=["python"]),
                         {"full_name": "علی", "phone": "09121234567", "email": "ali@example.com"})
        self.assertEqual(sorted(m.to[0] for m in mail.outbox), ["ali@example.com", "office@example.com"])

    def test_contact_form(self, _g):
        from core.models import ContactMessage

        url = reverse("core:contact")
        self.assertEqual(self.client.get(url).status_code, 200)
        self.client.post(url, {"name": "علی", "message": "سلام"})  # no phone/email -> rejected
        self.assertFalse(ContactMessage.objects.exists())
        self.client.post(url, {"name": "علی", "email": "a@b.com", "message": "سلام"})
        self.assertEqual(ContactMessage.objects.count(), 1)
        self.client.post(url, {"name": "bot", "email": "a@b.com", "message": "x", "website": "spam"})
        self.assertEqual(ContactMessage.objects.count(), 1)

    def test_static_pages_and_suggest(self, _g):
        from courses.models import Faq

        Faq.objects.create(question="چطور؟", answer="اینطور")
        for name in ("courses:instructors", "courses:faq", "courses:home"):
            self.assertEqual(self.client.get(reverse(name)).status_code, 200)
        self.assertContains(self.client.get(reverse("courses:faq")), "اینطور")
        self.assertContains(self.client.get(reverse("courses:suggest"), {"q": "python"}), "دوره python")
        self.assertNotContains(self.client.get(reverse("courses:suggest"), {"q": "p"}), "<li>")


class MagazineLinksTests(TestCase):
    """Footer links must match the magazine's real routes (/type/<type>/, /tag/<slug>/)."""

    @override_settings(MAGAZINE_URL="https://mag.example")
    def test_footer_links_use_magazine_routes(self):
        with mock.patch("core.magazine._get", return_value=[]):
            html = self.client.get(reverse("courses:home")).content.decode()
        for path in ("/type/news/", "/type/article/", "/type/tutorial/"):
            self.assertIn(f"https://mag.example{path}", html)
        self.assertEqual(magazine.tag_url("python").replace(settings.MAGAZINE_URL, ""), "/tag/python/")


class MagazineOptionalTests(TestCase):
    """Until MAGAZINE_URL is set the site must work standalone: no links, no outbound requests."""

    @override_settings(MAGAZINE_URL="", MAGAZINE_API_URL="")
    def test_no_magazine_links_or_requests_when_not_configured(self):
        make_course()
        with mock.patch("core.magazine.requests.get") as get:
            for url in (reverse("courses:home"), reverse("courses:detail", args=["python"])):
                html = self.client.get(url).content.decode()
                self.assertNotIn("مجله IT", html)
                self.assertNotIn("/type/news/", html)
            get.assert_not_called()
        self.assertEqual(magazine.tag_url("python"), "")

    @override_settings(MAGAZINE_URL="https://mag.example", MAGAZINE_API_URL="https://mag.example/api")
    def test_links_appear_when_configured(self):
        with mock.patch("core.magazine._get", return_value=[]):
            html = self.client.get(reverse("courses:home")).content.decode()
        self.assertIn("https://mag.example", html)

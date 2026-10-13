import datetime
import json
import re
from unittest import mock

from django.core import mail
from django.core.cache import cache
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from accounts.models import User
from courses import seo
from courses.models import Batch, Category, Course, Enrollment, Review, WaitlistEntry
from courses.waitlist import release_seats


def make_course(slug="python", **kw):
    cat, _ = Category.objects.get_or_create(slug="c", defaults={"name": "دسته"})
    kw.setdefault("summary", "خلاصه")
    return Course.objects.create(title=f"دوره {slug}", slug=slug, category=cat, is_published=True, **kw)


@override_settings(MAGAZINE_URL="")
class WaitlistTests(TestCase):
    def setUp(self):
        cache.clear()
        self.course = make_course()
        self.batch = Batch.objects.create(course=self.course, title="پاییز", capacity=1,
                                          start_date=timezone.localdate() + datetime.timedelta(days=10))
        self.url = reverse("courses:enroll", args=["python"])
        self.taken = Enrollment.objects.create(course=self.course, batch=self.batch, full_name="اول", phone="09120000001",
                                               email="first@example.com", status=Enrollment.Status.CONFIRMED)

    def join(self, name, phone, email=""):
        return self.client.post(self.url, {"full_name": name, "phone": phone, "email": email, "batch": self.batch.pk})

    def test_full_batch_goes_to_waitlist_not_enrollment(self):
        self.join("دوم", "09120000002", "second@example.com")
        self.assertEqual(Enrollment.objects.count(), 1)
        entry = WaitlistEntry.objects.get()
        self.assertEqual((entry.status, entry.batch), (WaitlistEntry.Status.WAITING, self.batch))

    def test_no_duplicate_waitlist_entries(self):
        self.join("دوم", "09120000002")
        self.join("دوم", "09120000002")
        self.assertEqual(WaitlistEntry.objects.count(), 1)

    def test_htmx_response_mentions_waitlist(self):
        resp = self.client.post(self.url, {"full_name": "دوم", "phone": "09120000002", "batch": self.batch.pk},
                                headers={"HX-Request": "true"})
        self.assertContains(resp, "لیست انتظار")

    def test_cancelling_a_seat_offers_it_to_the_first_in_line_only(self):
        self.join("دوم", "09120000002", "second@example.com")
        self.join("سوم", "09120000003", "third@example.com")
        mail.outbox.clear()
        with self.captureOnCommitCallbacks(execute=True):
            self.taken.status = Enrollment.Status.CANCELLED
            self.taken.save()
        second, third = WaitlistEntry.objects.order_by("created_at")
        self.assertEqual((second.status, third.status), (WaitlistEntry.Status.NOTIFIED, WaitlistEntry.Status.WAITING))
        self.assertEqual([m.to for m in mail.outbox], [["second@example.com"]])

    def test_held_seat_is_not_open_to_the_public_but_is_to_the_notified_person(self):
        self.join("دوم", "09120000002")
        with self.captureOnCommitCallbacks(execute=True):
            Enrollment.objects.filter(pk=self.taken.pk).update(status=Enrollment.Status.CANCELLED)
            release_seats(self.batch)
        self.assertFalse(self.batch.accepts_enrollment)                      # held for the person who waited
        self.assertTrue(self.batch.accepts_enrollment_for("09120000002"))
        self.assertFalse(self.batch.accepts_enrollment_for("09120000099"))
        self.join("بیرونی", "09120000099")                                   # a stranger just joins the list
        self.assertEqual(Enrollment.objects.exclude(status="cancelled").count(), 0)
        self.assertEqual(WaitlistEntry.objects.filter(phone="09120000099").count(), 1)
        self.join("دوم", "09120000002")                                       # the notified person can take it
        self.assertEqual(Enrollment.objects.filter(phone="09120000002").count(), 1)
        self.assertEqual(WaitlistEntry.objects.get(phone="09120000002").status, WaitlistEntry.Status.ENROLLED)

    def test_offer_expires_and_passes_on(self):
        self.join("دوم", "09120000002")
        self.join("سوم", "09120000003")
        Enrollment.objects.filter(pk=self.taken.pk).update(status=Enrollment.Status.CANCELLED)
        release_seats(self.batch)
        WaitlistEntry.objects.filter(phone="09120000002").update(notified_at=timezone.now() - datetime.timedelta(hours=49))
        release_seats(self.batch)
        second, third = WaitlistEntry.objects.order_by("created_at")
        self.assertEqual((second.status, third.status), (WaitlistEntry.Status.EXPIRED, WaitlistEntry.Status.NOTIFIED))

    def test_raising_capacity_notifies_waiting_people(self):
        self.join("دوم", "09120000002", "second@example.com")
        with self.captureOnCommitCallbacks(execute=True):
            self.batch.capacity = 2
            self.batch.save()
        self.assertEqual(WaitlistEntry.objects.get().status, WaitlistEntry.Status.NOTIFIED)

    def test_closed_batch_does_not_notify(self):
        self.join("دوم", "09120000002")
        Batch.objects.filter(pk=self.batch.pk).update(is_open=False)
        Enrollment.objects.filter(pk=self.taken.pk).update(status=Enrollment.Status.CANCELLED)
        self.assertEqual(release_seats(Batch.objects.get(pk=self.batch.pk)), [])


@override_settings(MAGAZINE_URL="")
class SeoTests(TestCase):
    def setUp(self):
        cache.clear()
        self.teacher = User.objects.create_user("t", "t@e.com", "pw-12345-xyz", first_name="مدرس", is_instructor=True)
        self.course = make_course(price=500000, duration_hours=40, instructor=self.teacher,
                                  summary="خلاصه </script><script>alert(1)</script>")
        Batch.objects.create(course=self.course, start_date=timezone.localdate() + datetime.timedelta(days=5), mode="online")
        Batch.objects.create(course=self.course, start_date=timezone.localdate() + datetime.timedelta(days=9), is_open=False)

    def blocks(self, url):
        html = self.client.get(url).content.decode()
        return html, [json.loads(b) for b in re.findall(r'<script type="application/ld\+json">(.*?)</script>', html, re.S)]

    def test_course_jsonld(self):
        html, blocks = self.blocks(self.course.get_absolute_url())
        course = next(b for b in blocks if b["@type"] == "Course")
        self.assertEqual(course["offers"]["price"], "5000000")  # toman -> rial
        self.assertEqual(course["offers"]["priceCurrency"], "IRR")
        self.assertEqual(len(course["hasCourseInstance"]), 1)    # closed batch is not advertised
        self.assertEqual(course["hasCourseInstance"][0]["courseMode"], "online")
        self.assertEqual(course["hasCourseInstance"][0]["courseWorkload"], "PT40H")
        self.assertEqual(course["hasCourseInstance"][0]["instructor"]["name"], "مدرس")
        self.assertNotIn("aggregateRating", course)
        crumbs = next(b for b in blocks if b["@type"] == "BreadcrumbList")
        self.assertEqual(len(crumbs["itemListElement"]), 3)

    def test_jsonld_cannot_break_out_of_the_script_tag(self):
        html, blocks = self.blocks(self.course.get_absolute_url())
        self.assertNotIn("<script>alert(1)", html)
        self.assertIn("alert(1)", next(b for b in blocks if b["@type"] == "Course")["description"])  # data intact

    def test_aggregate_rating_and_free_course(self):
        Review.objects.create(course=self.course, user=self.teacher, rating=4, text="x", is_approved=True)
        Course.objects.filter(pk=self.course.pk).update(price=0)
        _, blocks = self.blocks(self.course.get_absolute_url())
        course = next(b for b in blocks if b["@type"] == "Course")
        self.assertEqual(course["aggregateRating"]["ratingValue"], 4.0)
        self.assertEqual(course["offers"]["category"], "Free")

    def test_home_has_website_and_organization(self):
        _, blocks = self.blocks(reverse("courses:home"))
        self.assertEqual({b["@type"] for b in blocks}, {"WebSite", "EducationalOrganization"})
        self.assertIn("search_term_string", next(b for b in blocks if b["@type"] == "WebSite")["potentialAction"]["target"])

    def test_open_graph_tags(self):
        html, _ = self.blocks(self.course.get_absolute_url())
        self.assertIn('property="og:title" content="دوره python"', html)
        self.assertIn('twitter:card', html)

    def test_dumps_escapes(self):
        self.assertNotIn("<", seo.dumps({"a": "</script>"}))

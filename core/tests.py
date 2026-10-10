from django.test import TestCase
from django.urls import reverse

from .models import Page


class CoreTests(TestCase):
    def test_page_detail(self):
        Page.objects.create(title="درباره", slug="about", body="سلام")
        self.assertContains(self.client.get(reverse("core:page", args=["about"])), "سلام")

    def test_robots(self):
        self.assertContains(self.client.get("/robots.txt"), "Sitemap:")

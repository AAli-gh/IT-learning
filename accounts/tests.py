from django.test import TestCase
from django.urls import reverse

from .models import User


class AccountsTests(TestCase):
    def test_profile_requires_login(self):
        resp = self.client.get(reverse("accounts:profile"))
        self.assertEqual(resp.status_code, 302)

    def test_profile_page_for_student(self):
        User.objects.create_user("sara", "s@example.com", "pw-12345-xyz")
        self.client.login(username="sara", password="pw-12345-xyz")
        self.assertEqual(self.client.get(reverse("accounts:profile")).status_code, 200)

    def test_unknown_instructor_404(self):
        User.objects.create_user("plain", "p@example.com", "pw-12345-xyz")
        self.assertEqual(self.client.get(reverse("accounts:instructor", args=["plain"])).status_code, 404)

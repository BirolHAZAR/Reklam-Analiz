from urllib.parse import parse_qs, urlsplit

from django.test import Client, TestCase
from django.urls import reverse


class AdminCsrfRecoveryTests(TestCase):
    def setUp(self):
        self.client = Client(enforce_csrf_checks=True)

    def test_stale_admin_login_is_rejected_and_replaced_with_fresh_form(self):
        url = reverse("admin:login")
        self.client.get(url)
        response = self.client.post(url, {
            "csrfmiddlewaretoken": "a" * 64,
            "username": "not-authenticated", "password": "never-replayed",
            "next": "/admin/core/integrationapplication/",
        })
        self.assertEqual(response.status_code, 302)
        query = parse_qs(urlsplit(response.url).query)
        self.assertEqual(query["next"], ["/admin/core/integrationapplication/"])
        self.assertIn("no-store", response["Cache-Control"])
        refreshed = self.client.get(response.url)
        self.assertContains(refreshed, "güvenlik kodu yenilendi")
        self.assertContains(refreshed, "csrfmiddlewaretoken")
        self.assertNotContains(refreshed, "never-replayed")
        self.assertNotIn("_auth_user_id", self.client.session)

    def test_external_next_is_not_preserved(self):
        response = self.client.post(reverse("admin:login"), {"next": "https://attacker.example/"})
        self.assertEqual(response.status_code, 302)
        self.assertNotIn("next", parse_qs(urlsplit(response.url).query))

    def test_other_admin_posts_still_fail_csrf_validation(self):
        response = self.client.post(reverse("admin:core_integrationapplication_add"), {"provider": "facebook"})
        self.assertEqual(response.status_code, 403)

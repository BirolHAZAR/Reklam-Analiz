from django.contrib.auth import get_user_model
from django.db import connection
from django.test import TestCase, override_settings
from django.urls import reverse

from core.integration_admin import IntegrationApplicationForm
from core.models import IntegrationApplication
from core.services.ads_integrations import application_values, IntegrationError


class IntegrationApplicationTests(TestCase):
    def setUp(self):
        self.data = dict(provider="google_ads", client_id="test-client",
                        client_secret="secret-for-test", developer_token="developer-for-test",
                        redirect_uri="https://www.reklamanaliz.net/connect/google-ads/callback/", enabled=True)
        self.application = IntegrationApplication.objects.create(**self.data)

    def test_encrypted_storage_and_runtime_configuration(self):
        with connection.cursor() as cursor:
            cursor.execute("SELECT client_secret, developer_token FROM core_integrationapplication WHERE id=%s", [self.application.pk])
            values = cursor.fetchone()
        self.assertTrue(all(value.startswith("enc:v1:") for value in values))
        self.assertEqual(application_values("google_ads")[1], self.data["client_secret"])
        self.assertEqual(application_values("google_ads")[3], self.data["developer_token"])

    @override_settings(GOOGLE_ADS_CLIENT_ID="fallback", GOOGLE_ADS_CLIENT_SECRET="fallback", GOOGLE_ADS_DEVELOPER_TOKEN="fallback")
    def test_disabled_application_cannot_fall_back_to_environment(self):
        self.application.enabled = False
        self.application.save()
        with self.assertRaises(IntegrationError):
            application_values("google_ads")

    def test_blank_secret_preserved_and_never_rendered(self):
        form = IntegrationApplicationForm(instance=self.application)
        self.assertNotIn(self.data["client_secret"], form.as_p())
        self.assertNotIn(self.data["developer_token"], form.as_p())
        form = IntegrationApplicationForm(data={**self.data, "client_secret": "", "developer_token": ""}, instance=self.application)
        self.assertTrue(form.is_valid(), form.errors)
        form.save()
        self.application.refresh_from_db()
        self.assertEqual(self.application.client_secret, self.data["client_secret"])

    def test_untrusted_callback_rejected(self):
        form = IntegrationApplicationForm(data={**self.data, "redirect_uri": "https://attacker.example/connect/google-ads/callback/"})
        self.assertFalse(form.is_valid())
        self.assertIn("redirect_uri", form.errors)

    def test_ordinary_staff_cannot_read_or_edit_secrets(self):
        user = get_user_model().objects.create_user(username="staff-settings", is_staff=True)
        self.client.force_login(user)
        result = self.client.get(reverse("admin:core_integrationapplication_change", args=[self.application.pk]))
        self.assertEqual(result.status_code, 403)

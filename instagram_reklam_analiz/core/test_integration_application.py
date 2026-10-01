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

    def test_new_google_cloud_project_does_not_require_legacy_developer_token(self):
        self.application.developer_token = ""
        self.application.full_clean()
        self.application.save()

        self.assertEqual(application_values("google_ads")[3], "")

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

    @override_settings(DEBUG=False)
    def test_production_rejects_local_callback(self):
        self.application.redirect_uri = "http://localhost:8000/connect/google-ads/callback/"
        self.application.save()
        with self.assertRaisesMessage(IntegrationError, "Canlı ortam"):
            application_values("google_ads")

    @override_settings(DEBUG=True)
    def test_development_accepts_local_callback(self):
        self.application.redirect_uri = "http://localhost:8000/connect/google-ads/callback/"
        self.application.save()
        self.assertEqual(application_values("google_ads")[2], self.application.redirect_uri)

    def test_runtime_rejects_invalid_callback_even_if_saved_without_validation(self):
        self.application.redirect_uri = "https://attacker.example/connect/google-ads/callback/"
        self.application.save()
        with self.assertRaises(IntegrationError):
            application_values("google_ads")

    def test_ordinary_staff_cannot_read_or_edit_secrets(self):
        user = get_user_model().objects.create_user(username="staff-settings", is_staff=True)
        self.client.force_login(user)
        result = self.client.get(reverse("admin:core_integrationapplication_change", args=[self.application.pk]))
        self.assertEqual(result.status_code, 403)

    def test_superuser_gets_direct_settings_links_for_existing_and_new_apps(self):
        user = get_user_model().objects.create_user(username="integration-admin", is_staff=True, is_superuser=True)
        self.client.force_login(user)
        response = self.client.get(reverse("platform_connections"))
        self.assertContains(response, reverse("admin:core_integrationapplication_change", args=[self.application.pk]))
        self.assertContains(response, reverse("admin:core_integrationapplication_add") + "?provider=facebook")
        self.assertContains(response, "uygulama ayarları")
        add_response = self.client.get(reverse("hesap_ekle"))
        self.assertContains(add_response, reverse("admin:core_integrationapplication_add") + "?provider=facebook")
        self.assertNotContains(response, self.data["client_secret"])

    def test_regular_user_has_no_application_settings_links(self):
        user = get_user_model().objects.create_user(username="integration-customer")
        self.client.force_login(user)
        response = self.client.get(reverse("platform_connections"))
        self.assertNotContains(response, reverse("admin:core_integrationapplication_add"))

    def test_admin_setup_hub_and_local_callback_defaults(self):
        user = get_user_model().objects.create_user(username="setup-admin", is_staff=True, is_superuser=True)
        self.client.force_login(user)
        response = self.client.get(reverse("admin:core_integrationapplication_changelist"))
        self.assertContains(response, "Hesap bağlantı ayarları")
        self.assertContains(response, "Google Ads ayarları")
        response = self.client.get(reverse("admin:core_integrationapplication_add"), {"provider": "facebook"}, HTTP_HOST="127.0.0.1:8000")
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "http://127.0.0.1:8000/connect/facebook/callback/")
        self.assertContains(response, "Meta Uygulama Kimliği (App ID)")
        self.assertNotContains(response, self.data["client_secret"])

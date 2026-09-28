from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.test import TestCase, override_settings
from django.urls import reverse
from django.contrib import admin

from core.integration_admin import IntegrationApplicationForm
from core.models import IntegrationApplication
from core.platform_setup import PLATFORM_SETUP
from core.services.platform_application import instagram_application_credentials


class PlatformSetupTests(TestCase):
    def setUp(self):
        self.admin = get_user_model().objects.create_user(username="all-platform-admin", is_staff=True, is_superuser=True)
        self.client.force_login(self.admin)

    def test_all_eight_platforms_have_separate_admin_forms(self):
        response = self.client.get(reverse("admin:core_integrationapplication_changelist"))
        self.assertEqual(len(response.context["setup_links"]), 8)
        for provider, spec in PLATFORM_SETUP.items():
            with self.subTest(provider=provider):
                response = self.client.get(reverse("admin:core_integrationapplication_add"), {"provider": provider})
                self.assertEqual(response.status_code, 200)
                self.assertContains(response, spec["client_label"])
                self.assertContains(response, spec["capability"])
                self.assertContains(response, spec["console"])
                form = IntegrationApplicationForm(data={"provider": provider, "client_id": "", "client_secret": "", "redirect_uri": ""})
                self.assertTrue(form.is_valid(), form.errors)
                self.assertFalse(form.save().enabled)

    def test_unimplemented_providers_cannot_be_activated_even_outside_form(self):
        for provider, spec in PLATFORM_SETUP.items():
            if spec["mode"] != "draft":
                continue
            with self.subTest(provider=provider):
                app = IntegrationApplication(provider=provider, client_id="id", client_secret="secret", enabled=True)
                with self.assertRaises(ValidationError):
                    app.full_clean()

    @override_settings(INSTAGRAM_APP_ID="env-id", INSTAGRAM_APP_SECRET="env-secret")
    def test_instagram_runtime_uses_encrypted_saved_settings_and_respects_disabled(self):
        self.assertEqual(instagram_application_credentials(), ("env-id", "env-secret"))
        form = IntegrationApplicationForm(data={"provider": "instagram", "client_id": "saved-id", "client_secret": "saved-secret", "redirect_uri": "", "enabled": True})
        self.assertTrue(form.is_valid(), form.errors)
        app = form.save()
        self.assertEqual(instagram_application_credentials(), ("saved-id", "saved-secret"))
        response = self.client.get(reverse("admin:core_integrationapplication_change", args=[app.pk]))
        self.assertNotContains(response, "saved-secret")
        app.enabled = False
        app.save()
        with self.assertRaises(ValueError):
            instagram_application_credentials()

    def test_blank_secret_keeps_each_platforms_existing_secret(self):
        for provider in PLATFORM_SETUP:
            app = IntegrationApplication.objects.create(provider=provider, client_id="id", client_secret="secret-"+provider)
            form = IntegrationApplicationForm(instance=app, data={"provider": provider, "client_id": "id", "client_secret": "", "redirect_uri": ""})
            self.assertTrue(form.is_valid(), form.errors)
            form.save()
            app.refresh_from_db()
            self.assertEqual(app.client_secret, "secret-"+provider)

    def test_saved_provider_cannot_be_reassigned(self):
        app = IntegrationApplication.objects.create(provider="instagram", client_secret="private")
        form = IntegrationApplicationForm(instance=app, data={"provider": "youtube", "client_id": "id", "redirect_uri": ""})
        self.assertFalse(form.is_valid())
        self.assertIn("provider", form.errors)

    def test_no_credential_csv_export_or_bulk_activation(self):
        from django.test import RequestFactory
        request = RequestFactory().get("/admin/")
        request.user = self.admin
        self.assertEqual(admin.site._registry[IntegrationApplication].get_actions(request), {})

    def test_regular_staff_cannot_open_platform_setup(self):
        staff = get_user_model().objects.create_user(username="ordinary-platform-staff", is_staff=True)
        self.client.force_login(staff)
        self.assertEqual(self.client.get(reverse("admin:core_integrationapplication_changelist")).status_code, 403)

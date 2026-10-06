from django.contrib.auth import get_user_model
from django.db import connection
from django.test import TestCase, override_settings
from django.urls import reverse

from core.integration_admin import IntegrationApplicationForm
from core.models import IntegrationApplication
from core.services.ads_integrations import application_values, IntegrationError


class CompetitorSourceSettingTests(TestCase):
    def setUp(self):
        from core.models import CompetitorSourceSetting
        self.data = dict(platform='instagram', source='searchapi', credential='competitor-test-secret',
                         countries='TR', enabled=True)
        self.setting = CompetitorSourceSetting.objects.create(**self.data)

    def test_encrypted_key_is_used_without_changing_other_platform(self):
        from core.models import CompetitorSourceSetting
        with connection.cursor() as cursor:
            cursor.execute('SELECT credential FROM core_competitorsourcesetting WHERE id=%s', [self.setting.pk])
            stored = cursor.fetchone()[0]
        self.assertTrue(stored.startswith('enc:v1:'))
        self.assertNotIn(self.data['credential'], stored)
        self.assertEqual(CompetitorSourceSetting.runtime('instagram')['credential'], self.data['credential'])
        with override_settings(META_COMPETITOR_SOURCE='graph'):
            self.assertEqual(CompetitorSourceSetting.runtime('facebook')['source'], 'graph')

    def test_blank_secret_is_preserved_but_never_rendered(self):
        from core.integration_admin import CompetitorSourceForm
        form = CompetitorSourceForm(instance=self.setting)
        self.assertNotIn(self.data['credential'], form.as_p())
        form = CompetitorSourceForm(data={**self.data, 'credential': ''}, instance=self.setting)
        self.assertTrue(form.is_valid(), form.errors)
        form.save()
        self.setting.refresh_from_db()
        self.assertEqual(self.setting.credential, self.data['credential'])

    def test_changing_provider_does_not_reuse_another_providers_secret(self):
        from core.integration_admin import CompetitorSourceForm
        form = CompetitorSourceForm(data={**self.data, 'source': 'graph', 'credential': ''}, instance=self.setting)
        self.assertTrue(form.is_valid(), form.errors)
        self.assertEqual(form.cleaned_data['credential'], '')

    @override_settings(SEARCHAPI_API_KEY='environment-must-not-be-used')
    def test_disabled_platform_blocks_source_and_reports_member_notice(self):
        from types import SimpleNamespace
        from core.services.competitor_public_sources import competitor_source, source_status
        from core.services.competitor_live_sync import CompetitorSyncError
        self.setting.enabled = False
        self.setting.save()
        competitor = SimpleNamespace(platform=SimpleNamespace(code='instagram'))
        self.assertFalse(source_status(competitor)['configured'])
        with self.assertRaises(CompetitorSyncError):
            competitor_source(competitor)

    def test_provider_country_and_platform_validation(self):
        from core.integration_admin import CompetitorSourceForm
        for changes, error in [({'source': 'serpapi'}, 'source'), ({'countries': 'Turkey'}, 'countries'),
                               ({'countries': 'TR,DE'}, 'countries'), ({'platform': 'facebook'}, 'platform')]:
            form = CompetitorSourceForm(data={**self.data, **changes}, instance=self.setting)
            self.assertFalse(form.is_valid())
            self.assertIn(error, form.errors)
            self.setting.refresh_from_db()

    def test_admin_is_superuser_only_and_has_no_export_action(self):
        from django.contrib import admin
        from django.test import RequestFactory
        from core.models import CompetitorSourceSetting
        model_admin = admin.site._registry[CompetitorSourceSetting]
        request = RequestFactory().get('/')
        request.user = get_user_model().objects.create_user(username='source-staff', is_staff=True)
        self.assertFalse(model_admin.has_view_permission(request))
        self.client.force_login(request.user)
        self.assertEqual(self.client.get(reverse('admin:core_competitorsourcesetting_changelist')).status_code, 403)
        request.user.is_superuser = True
        self.assertEqual(set(model_admin.get_actions(request)), {'test_connection'})
        self.assertFalse(model_admin.has_delete_permission(request))

    def test_admin_test_does_not_store_secrets_from_provider_errors(self):
        from unittest.mock import patch
        from django.contrib import admin
        from django.test import RequestFactory
        from core.models import CompetitorSourceSetting, Competitor, Platform
        user = get_user_model().objects.create_user(username='source-test-admin', is_superuser=True, is_staff=True)
        platform = Platform.objects.create(code='instagram', name='Instagram')
        competitor = Competitor.objects.create(user=user, platform=platform, name='Example', platform_identifier='example')
        self.setting.test_competitor = competitor
        self.setting.save()
        request = RequestFactory().post('/')
        request.user = user
        model_admin = admin.site._registry[CompetitorSourceSetting]
        with patch('core.services.competitor_public_sources.competitor_source', side_effect=RuntimeError(self.data['credential'])), patch.object(model_admin, 'message_user'):
            model_admin.test_connection(request, CompetitorSourceSetting.objects.filter(pk=self.setting.pk))
        self.setting.refresh_from_db()
        self.assertNotIn(self.data['credential'], self.setting.last_test_result)
        self.assertIsNotNone(self.setting.last_test_at)
        self.assertFalse(competitor.ads.exists())


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

from datetime import timedelta
from unittest.mock import Mock, patch
from io import StringIO
from django.core.management import call_command

from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.test import SimpleTestCase, TestCase, override_settings
from django.utils import timezone

from core.models import Platform, PlatformAccount, PlatformConnection
from core.services import ads_integrations as ads
from core.services import platform_token_service as health
from core.services.meta_rate_limit import before_request, after_response, MetaRateLimitError


class MetaCooldownTests(SimpleTestCase):
    def setUp(self):
        cache.clear()
        self.url = "https://graph.facebook.com/v25.0/me"
        self.options = {"headers": {"Authorization": "Bearer test-token"}}

    def test_meta_400_rate_error_blocks_next_request_and_keeps_token_private(self):
        response = Mock(status_code=400, headers={"Retry-After": "600"})
        with self.assertRaises(MetaRateLimitError) as caught:
            after_response(self.url, self.options, response, {"error": {"code": 17}})
        self.assertEqual(caught.exception.retry_after, 600)
        self.assertNotIn("test-token", str(caught.exception))
        with self.assertRaises(MetaRateLimitError):
            before_request(self.url, self.options)
        with self.assertRaises(MetaRateLimitError):
            before_request(self.url, {"params": {"access_token": "test-token"}})
        before_request(self.url, {"params": {"access_token": "another-token"}})

    def test_successful_response_at_high_usage_preserves_result_but_pauses_next_call(self):
        response = Mock(status_code=200, headers={"X-Business-Use-Case-Usage":
            '{"123": [{"call_count": 95, "estimated_time_to_regain_access": 5}]}'})
        after_response(self.url, self.options, response, {"data": []})
        with self.assertRaises(MetaRateLimitError) as caught:
            before_request(self.url, self.options)
        self.assertGreater(caught.exception.retry_after, 290)

    def test_authentication_error_does_not_start_cooldown(self):
        after_response(self.url, self.options, Mock(status_code=400, headers={}), {"error": {"code": 190}})
        before_request(self.url, self.options)

    @patch("core.services.ads_integrations.requests.request")
    def test_shared_ads_client_does_not_call_provider_during_cooldown(self, request):
        with self.assertRaises(MetaRateLimitError):
            after_response(self.url, self.options, Mock(status_code=429, headers={}), {})
        with self.assertRaises(ads.IntegrationRateLimitError):
            ads._request("GET", self.url, **self.options)
        request.assert_not_called()

    @patch("core.services.ads_integrations.configuration", return_value=("app", "secret", "https://example.com/callback"))
    @patch("core.services.ads_integrations._request")
    def test_missing_facebook_expiry_is_read_from_meta_instead_of_one_hour(self, request, config):
        deadline = int(timezone.now().timestamp()) + 5000000
        request.side_effect = [{"access_token": "short"}, {"access_token": "long"},
            {"data": {"is_valid": True, "expires_at": deadline}},
            {"data": [{"permission": "ads_read", "status": "granted"}]}]
        token = ads.exchange_code("facebook", "code")
        self.assertGreater(token["expires_in"], 4999990)

    @patch("core.services.ads_integrations.configuration", return_value=("app", "secret", "https://example.com/callback"))
    @patch("core.services.ads_integrations._request")
    def test_explicit_zero_meta_expiry_does_not_invent_a_deadline(self, request, config):
        request.side_effect = [{"access_token": "short"}, {"access_token": "long"},
            {"data": {"is_valid": True, "expires_at": 0, "data_access_expires_at": 2000000000}},
            {"data": [{"permission": "ads_read", "status": "granted"}]}]
        self.assertIsNone(ads.exchange_code("facebook", "code")["expires_in"])


@override_settings(INSTAGRAM_ACCESS_TOKEN="", META_AD_LIBRARY_ACCESS_TOKEN="")
class MetaHealthTests(TestCase):
    def setUp(self):
        cache.clear()
        self.user = get_user_model().objects.create_user(username="meta-health")
        self.platform, _ = Platform.objects.get_or_create(code="instagram", defaults={"name": "Instagram"})
        self.connection = PlatformConnection.objects.create(user=self.user, platform=self.platform,
            access_token="old-token", token_expiry=timezone.now() + timedelta(days=2),
            extra_data={"auth_type": "instagram_login"})
        self.account = PlatformAccount.objects.create(user=self.user, platform=self.platform,
            connection=self.connection, account_id="123", access_token="old-token")

    @patch.object(health, "_validate_connection")
    def test_readonly_audit_does_not_call_api_or_expose_token(self, validate):
        output = StringIO()
        call_command("audit_meta_connections", stdout=output)
        validate.assert_not_called()
        self.assertNotIn("old-token", output.getvalue())
        self.connection.refresh_from_db()
        self.assertEqual(self.connection.access_token, "old-token")

    @patch.object(health, "_validate_connection")
    def test_overlapping_maintenance_does_not_repeat_api_calls(self, validate):
        cache.set("platform_token_health:running", "other-worker", timeout=60)
        result = health.check_and_refresh_platform_tokens()
        self.assertEqual(result["reason"], "already_running")
        validate.assert_not_called()
        self.assertEqual(cache.get("platform_token_health:running"), "other-worker")

    @patch.object(health, "_meta_get")
    def test_incomplete_refresh_response_is_not_accepted_as_success(self, get):
        get.return_value = Mock(ok=True)
        get.return_value.json.return_value = {"access_token": "new-token"}
        with self.assertRaises(RuntimeError):
            health._refresh_instagram_token("old-token", instagram_login=True)

    @patch.object(health, "_refresh_instagram_token", return_value=("renewed-token", 5184000))
    @patch.object(health, "_validate_connection")
    def test_refresh_persists_same_token_and_expiry_to_connected_account(self, validate, refresh):
        validate.return_value = {"valid": True, "expires_at": self.connection.token_expiry}
        result = health.check_and_refresh_platform_tokens()
        self.assertEqual(result["refreshed"], 1)
        self.connection.refresh_from_db()
        self.account.refresh_from_db()
        self.assertEqual(self.account.access_token, "renewed-token")
        self.assertEqual(self.account.token_expiry, self.connection.token_expiry)

    @patch.object(health, "_validate_connection", side_effect=MetaRateLimitError(600))
    def test_temporary_limit_does_not_expire_or_erase_connection(self, validate):
        result = health.check_and_refresh_platform_tokens()
        self.connection.refresh_from_db()
        self.assertEqual(result["check_failed"], 1)
        self.assertEqual(self.connection.status, "active")
        self.assertEqual(self.connection.access_token, "old-token")

    @patch.object(health, "_validate_connection", return_value={"valid": True, "expiry_known": True, "expires_at": None})
    def test_meta_no_expiry_repairs_false_local_expiry_without_replacing_token(self, validate):
        facebook, _ = Platform.objects.get_or_create(code="facebook", defaults={"name": "Facebook"})
        self.connection.platform = facebook
        self.connection.token_expiry = timezone.now() - timedelta(hours=1)
        self.connection.save()
        result = health.check_and_refresh_platform_tokens()
        self.connection.refresh_from_db()
        self.account.refresh_from_db()
        self.assertEqual(result["active"], 1)
        self.assertIsNone(self.connection.token_expiry)
        self.assertIsNone(self.account.token_expiry)
        self.assertEqual(self.connection.access_token, "old-token")

    @patch.object(health, "_notify_connection_issue")
    @patch.object(health, "_validate_connection")
    def test_facebook_data_access_deadline_is_not_used_as_token_expiry(self, validate, notify):
        facebook, _ = Platform.objects.get_or_create(code="facebook", defaults={"name": "Facebook"})
        self.connection.platform = facebook
        self.connection.save()
        expiry = timezone.now() + timedelta(days=40)
        data_expiry = timezone.now() + timedelta(days=2)
        validate.return_value = {"valid": True, "expires_at": expiry, "data_access_expires_at": data_expiry}
        result = health.check_and_refresh_platform_tokens()
        self.connection.refresh_from_db()
        self.assertEqual(self.connection.token_expiry, expiry)
        self.assertEqual(self.connection.extra_data["data_access_expires_at"], data_expiry.isoformat())
        self.assertTrue(result["results"][0]["reauthorization_required_soon"])
        notify.assert_called_once()

    @patch("core.services.ads_integrations.configuration", return_value=("saved-app", "saved-secret", "https://example.com/callback"))
    @patch.object(health.requests, "get")
    def test_facebook_debug_uses_saved_application_configuration(self, get, config):
        get.return_value = Mock(ok=True, status_code=200, headers={})
        get.return_value.json.return_value = {"data": {"is_valid": True}}
        health._debug_meta_token("user-token", "facebook")
        self.assertEqual(get.call_args.kwargs["params"]["access_token"], "saved-app|saved-secret")

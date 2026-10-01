import time
from io import StringIO
from unittest.mock import patch
from urllib.parse import parse_qs, urlsplit

from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from django.urls import reverse
from django.core.management import call_command, CommandError

from core.models import AgencyClient, Organization, Platform, PlatformAccount, PlatformConnection
from core.services import instagram_oauth as api
from core.services.ads_integrations import IntegrationError
from core.views.instagram_oauth import SESSION_KEY, save_account


@override_settings(INSTAGRAM_APP_ID="ig-app", INSTAGRAM_APP_SECRET="ig-secret",
    INSTAGRAM_REDIRECT_URI="https://reklamanaliz.net/connect/instagram/callback/")
class InstagramOAuthTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(username="ig-owner")
        self.client.force_login(self.user)
        self.token = {"access_token": "private-token", "expires_in": 5184000, "scope": list(api.SCOPES)}
        self.profile = {"id": "123456", "username": "example"}

    def flow(self, **values):
        session = self.client.session
        session[SESSION_KEY] = {"state": "nonce", "created": time.time(), "user": self.user.pk, "client": None, **values}
        session.save()

    def callback(self, **params):
        return self.client.get(reverse("instagram_oauth_callback"), {"code": "one-use-code", "state": "nonce", **params})

    def test_subscriber_has_direct_connect_without_token_modal_or_settings(self):
        response = self.client.get(reverse("hesap_ekle"))
        self.assertContains(response, reverse("instagram_connect"))
        self.assertNotContains(response, "modalInstagram")
        self.assertNotContains(response, "?provider=instagram")

    def test_post_only_connect_stores_state_and_uses_instagram(self):
        url = reverse("instagram_connect")
        self.assertEqual(self.client.get(url).status_code, 405)
        response = self.client.post(url)
        parsed = urlsplit(response.url)
        self.assertEqual(parsed.hostname, "www.instagram.com")
        params = parse_qs(parsed.query)
        self.assertEqual(params["scope"], [",".join(api.SCOPES)])
        self.assertEqual(params["state"][0], self.client.session[SESSION_KEY]["state"])
        self.assertNotIn("ig-secret", response.url)
        self.assertNotIn("force_authentication", params)

    @override_settings(DEBUG=False)
    def test_production_setup_check_does_not_expose_credentials(self):
        output = StringIO()
        call_command("check_instagram_setup", stdout=output)
        self.assertIn("https://reklamanaliz.net/connect/instagram/callback/", output.getvalue())
        self.assertNotIn("ig-secret", output.getvalue())
        self.assertNotIn("ig-app", output.getvalue())

    @override_settings(DEBUG=False, INSTAGRAM_REDIRECT_URI="https://127.0.0.1:8443/connect/instagram/callback/")
    def test_production_rejects_local_test_callback(self):
        with self.assertRaises(CommandError):
            call_command("check_instagram_setup", stdout=StringIO())
        response = self.client.post(reverse("instagram_connect"))
        self.assertRedirects(response, reverse("hesap_ekle"), fetch_redirect_response=False)
        self.assertNotIn(SESSION_KEY, self.client.session)

    @patch("core.views.instagram_oauth.api.exchange_code")
    def test_bad_expired_and_replayed_state_do_not_exchange(self, exchange):
        for values, params in [({}, {"state": "wrong"}), ({}, {"state": "yanlış"}), ({"created": time.time()-601}, {}), ({"user": self.user.pk+1}, {})]:
            self.flow(**values)
            self.callback(**params)
        self.callback()
        exchange.assert_not_called()
        self.assertFalse(PlatformConnection.objects.exists())

    @patch("core.views.instagram_oauth.api.exchange_code")
    def test_cancel_creates_nothing(self, exchange):
        self.flow()
        self.callback(error="access_denied")
        exchange.assert_not_called()
        self.assertFalse(PlatformConnection.objects.exists())

    @patch("core.views.instagram_oauth.ensure_platform_account_capacity")
    @patch("core.views.instagram_oauth.api.exchange_code")
    def test_callback_connects_directly_and_preserves_alias_on_reconnect(self, exchange, capacity):
        exchange.return_value = self.token, self.profile
        self.flow()
        response = self.callback()
        self.assertRedirects(response, reverse("platform_connections"), fetch_redirect_response=False)
        account = PlatformAccount.objects.get(account_id=self.profile["id"])
        self.assertEqual(account.account_name, "@example")
        self.assertEqual(account.connection.scopes, list(api.SCOPES))
        account.local_name = "Local alias"
        account.save()
        old_connection = account.connection
        self.flow()
        self.callback()
        account.refresh_from_db(); old_connection.refresh_from_db()
        self.assertEqual(account.local_name, "Local alias")
        self.assertEqual(PlatformAccount.objects.count(), 1)
        self.assertFalse(old_connection.is_active)

    @patch("core.views.instagram_oauth.ensure_platform_account_capacity", side_effect=ValueError("capacity exceeded"))
    def test_capacity_failure_rolls_back_everything(self, capacity):
        with self.assertRaises(ValueError):
            save_account(self.user, None, self.token, self.profile)
        self.assertFalse(PlatformConnection.objects.exists())
        self.assertFalse(PlatformAccount.objects.exists())

    @patch("core.views.instagram_oauth.ensure_platform_account_capacity")
    def test_reconnect_cannot_move_account_to_another_client(self, capacity):
        org = Organization.objects.create(owner=self.user, name="Agency")
        brand = AgencyClient.objects.create(organization=org, name="Brand")
        save_account(self.user, None, self.token, self.profile)
        with self.assertRaises(IntegrationError):
            save_account(self.user, brand, self.token, self.profile)
        self.assertEqual(PlatformConnection.objects.count(), 1)

    @patch("core.views.instagram_oauth.api.exchange_code")
    def test_callback_rechecks_client_permission_before_exchange(self, exchange):
        other = get_user_model().objects.create_user(username="other-agency")
        org = Organization.objects.create(owner=other, name="Other")
        brand = AgencyClient.objects.create(organization=org, name="Other brand")
        self.flow(client=brand.pk)
        self.assertEqual(self.callback().status_code, 403)
        exchange.assert_not_called()

    @patch("core.services.instagram_oauth._request")
    def test_exchange_uses_instagram_endpoints_and_verifies_identity(self, request):
        request.side_effect = [
            {"access_token": "short", "user_id": 123456, "permissions": list(api.SCOPES)},
            {"access_token": "long", "expires_in": 5184000},
            {"user_id": "123456", "username": "example"},
        ]
        token, profile = api.exchange_code("code")
        self.assertEqual(token["access_token"], "long")
        self.assertEqual(profile, self.profile)
        self.assertEqual(request.call_args_list[0].args[:2], ("POST", "https://api.instagram.com/oauth/access_token"))
        self.assertIn("graph.instagram.com", request.call_args_list[2].args[1])

    @patch("core.services.instagram_oauth._request")
    def test_missing_permissions_and_mismatched_identity_rejected(self, request):
        request.return_value = {"access_token": "short", "permissions": [api.SCOPES[0]]}
        with self.assertRaises(IntegrationError):
            api.exchange_code("code")
        request.side_effect = [
            {"access_token": "short", "user_id": 999, "permissions": list(api.SCOPES)},
            {"access_token": "long", "expires_in": 5184000},
            {"user_id": "123456", "username": "example"},
        ]
        with self.assertRaises(IntegrationError):
            api.exchange_code("code")

    @patch("core.services.instagram_oauth.profile", return_value={"id": "123456", "username": "example"})
    @patch("core.views.instagram_oauth.ensure_platform_account_capacity")
    def test_health_check_uses_instagram_profile_and_media_host(self, capacity, profile):
        from core.services.platform_token_service import _validate_connection
        from core.instagram_api import InstagramAPI
        account = save_account(self.user, None, self.token, self.profile)
        self.assertTrue(_validate_connection(account.connection)["valid"])
        self.assertTrue(InstagramAPI("token", instagram_login=True).graph_url.startswith("https://graph.instagram.com/"))
        from core.tasks.v2_platform_sync import _should_skip_ad_sync
        self.assertEqual(_should_skip_ad_sync(account, "instagram"), "organic_account_use_meta_ads_for_ad_sync")

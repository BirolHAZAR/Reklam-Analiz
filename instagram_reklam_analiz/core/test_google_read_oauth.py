from datetime import timedelta
import time
from unittest.mock import Mock, patch
from urllib.parse import parse_qs, urlsplit

from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from core.models import IntegrationApplication, Platform, PlatformAccount, PlatformConnection
from core.services import ads_integrations as ads
from core.services import google_read_oauth as api


class GoogleReadOAuthTests(TestCase):
    def setUp(self):
        cache.clear()
        self.user = get_user_model().objects.create_user(username="google-reader")
        self.client.force_login(self.user)
        self.platforms = {}
        for provider in api.SCOPES:
            self.platforms[provider], _ = Platform.objects.get_or_create(code=provider, defaults={"name": provider})
            IntegrationApplication.objects.create(provider=provider, client_id=provider+"-client", client_secret=provider+"-secret",
                redirect_uri="https://www.reklamanaliz.net" + "/connect/youtube/callback/", enabled=True)

    def connection(self, provider="youtube", **kwargs):
        return PlatformConnection.objects.create(user=self.user, platform=self.platforms[provider],
            access_token="old-token", refresh_token="refresh-secret", extra_data={"source": "google_read_oauth"}, **kwargs)

    def test_scopes_and_callbacks_are_isolated_from_ads(self):
        for provider, scope in api.SCOPES.items():
            query = parse_qs(urlsplit(ads.authorization_url(provider, "nonce")).query)
            self.assertEqual(query["scope"], [scope])
            self.assertNotIn(ads.ADWORDS_SCOPE, query["scope"])
            self.assertEqual(query["client_id"], [provider+"-client"])
            self.assertEqual(query["access_type"], ["offline"])

    @patch("core.services.ads_integrations.authorization_url")
    def test_retired_analytics_links_do_not_start_oauth(self, authorization):
        response = self.client.post(reverse("integration_connect", args=["google_analytics"]))
        self.assertEqual(response.status_code, 404)
        response = self.client.get(reverse("integration_select", args=["google_analytics"]))
        self.assertEqual(response.status_code, 404)
        for url in ("/connect/google-analytics/callback/", "/google-analytics/"):
            self.assertEqual(self.client.get(url).status_code, 404)
        authorization.assert_not_called()

    @patch("core.services.google_read_oauth.request")
    def test_scope_or_refresh_denial_does_not_create_connection(self, request):
        for data in ({"access_token": "secret", "scope": ads.ADWORDS_SCOPE, "refresh_token": "secret"},
                     {"access_token": "secret", "scope": api.SCOPES["youtube"]}):
            request.return_value = data
            with self.assertRaises(ads.IntegrationError):
                api.exchange_code("youtube", "code")
        self.assertFalse(PlatformConnection.objects.exists())

    @patch("core.services.google_read_oauth.request")
    def test_expired_token_uses_correct_client_and_updates_accounts(self, request):
        for provider in api.SCOPES:
            connection = self.connection(provider, token_expiry=timezone.now()-timedelta(seconds=1))
            account = PlatformAccount.objects.create(user=self.user, platform=self.platforms[provider], connection=connection, account_id="123")
            request.return_value = {"access_token": "fresh-token", "expires_in": 3600}
            self.assertEqual(ads.connection_token(connection), "fresh-token")
            self.assertEqual(request.call_args.kwargs["data"]["client_id"], provider+"-client")
            account.refresh_from_db()
            self.assertEqual(account.access_token, "fresh-token")
            self.assertEqual(account.refresh_token, "refresh-secret")
            count = request.call_count
            api.connection_token(connection)
            self.assertEqual(request.call_count, count)

    @patch("core.services.google_read_oauth.requests.request")
    def test_rate_limit_cools_down_without_disconnect_or_retry_storm(self, request):
        request.return_value = Mock(status_code=429, ok=False, headers={"Retry-After": "600"})
        request.return_value.json.return_value = {"error": {"code": 429}}
        for _ in range(2):
            with self.assertRaises(api.GoogleReadRateLimitError):
                api.request("GET", "https://www.googleapis.com/youtube/v3/channels", quota_key="youtube-client")
        self.assertEqual(request.call_count, 1)

    @patch("core.services.google_read_oauth.exchange_code")
    def test_wrong_oauth_state_does_not_exchange(self, exchange):
        session = self.client.session
        session["ads_oauth:youtube"] = {"state": "nonce", "user": self.user.pk, "created": time.time()}
        session.save()
        self.client.get(reverse("youtube_callback"), {"state": "wrong", "code": "secret"})
        exchange.assert_not_called()

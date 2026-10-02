from datetime import timedelta
import time
from unittest.mock import Mock, patch
from urllib.parse import parse_qs, urlsplit

from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from core.models import AnalyticsProperty, IntegrationApplication, Platform, PlatformAccount, PlatformConnection
from core.services import ads_integrations as ads
from core.services import google_read_oauth as api
from core.platforms.google_analytics import GoogleAnalyticsAPI


class GoogleReadOAuthTests(TestCase):
    def setUp(self):
        cache.clear()
        self.user = get_user_model().objects.create_user(username="google-reader")
        self.client.force_login(self.user)
        self.platforms = {}
        for provider in api.SCOPES:
            self.platforms[provider], _ = Platform.objects.get_or_create(code=provider, defaults={"name": provider})
            IntegrationApplication.objects.create(provider=provider, client_id=provider+"-client", client_secret=provider+"-secret",
                redirect_uri="https://www.reklamanaliz.net" + ("/connect/youtube/callback/" if provider == "youtube" else "/connect/google-analytics/callback/"), enabled=True)

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

    @patch("core.services.plan_limits.ensure_platform_account_capacity")
    @patch("core.services.google_read_oauth.discover_accounts")
    @patch("core.services.google_read_oauth.exchange_code")
    def test_ga4_selection_only_saves_verified_property(self, exchange, discover, limit):
        exchange.return_value = {"access_token": "secret", "refresh_token": "refresh", "scope": api.SCOPES["google_analytics"]}
        discover.return_value = [{"id": "123", "name": "Site", "property_id": "123", "kind": "ga4_property"}]
        session = self.client.session
        session["ads_oauth:google_analytics"] = {"state": "nonce", "user": self.user.pk, "created": time.time()}
        session.save()
        self.client.get(reverse("google_analytics_callback"), {"state": "nonce", "code": "secret"})
        url = reverse("integration_select", args=["google_analytics"])
        self.client.post(url, {"accounts": ["forged"]})
        self.assertFalse(PlatformAccount.objects.exists())
        self.client.post(url, {"accounts": ["123"]})
        account = PlatformAccount.objects.get()
        self.assertEqual(account.extra_data["source"], "google_read_oauth")
        self.assertEqual(AnalyticsProperty.objects.get().platform_connection_id, account.connection_id)
        self.assertEqual(self.client.get(reverse("integration_campaigns", args=[account.pk])).status_code, 404)

    @patch("core.services.google_read_oauth.request")
    def test_property_discovery_paginates_and_deduplicates(self, request):
        request.side_effect = [
            {"accountSummaries": [{"propertySummaries": [{"property": "properties/123", "displayName": "Site"}]}], "nextPageToken": "next"},
            {"accountSummaries": [{"propertySummaries": [{"property": "properties/123", "displayName": "Site"}, {"property": "properties/456"}]}]},
        ]
        self.assertEqual([r["id"] for r in api.discover_accounts("google_analytics", "token")], ["123", "456"])
        self.assertEqual(request.call_args.kwargs["params"]["pageToken"], "next")

    @patch("core.platforms.google_analytics.request")
    def test_ga4_report_maps_dates_and_metrics_and_rejects_other_property(self, request):
        connection = self.connection("google_analytics", token_expiry=timezone.now()+timedelta(hours=1))
        account = PlatformAccount.objects.create(user=self.user, platform=self.platforms["google_analytics"], connection=connection, account_id="123")
        request.return_value = {"rowCount": 1, "rows": [{"dimensionValues": [{"value": "20261001"}],
            "metricValues": [{"value": str(i+1)} for i in range(len(GoogleAnalyticsAPI.DAILY))]}]}
        api_obj = GoogleAnalyticsAPI(account)
        row = api_obj.get_daily_metrics("123")[0]
        self.assertEqual(row["date"], "2026-10-01")
        self.assertEqual(row["sessions"], "1")
        self.assertEqual(row["conversions"], row["key_events"])
        self.assertLessEqual(len(request.call_args.kwargs["json"]["metrics"]), 10)
        with self.assertRaises(ads.IntegrationError):
            api_obj.get_daily_metrics("456")

    @patch("core.platforms.google_analytics.GoogleAnalyticsAPI")
    def test_worker_persists_real_report_and_skips_duplicate_jobs(self, api_class):
        from core.tasks.analytics_tasks import sync_analytics_account
        connection = self.connection("google_analytics", token_expiry=timezone.now()+timedelta(hours=1))
        account = PlatformAccount.objects.create(user=self.user, platform=self.platforms["google_analytics"], connection=connection, account_id="123")
        api_class.return_value.get_properties.return_value = [{"property_id": "123", "property_name": "Site", "currency": "USD"}]
        api_class.return_value.get_daily_metrics.return_value = [{"date": "2026-10-01", "sessions": "17", "users": "12"}]
        api_class.return_value.get_landing_page_metrics.return_value = [{"date": "2026-10-01", "landing_page": "/", "sessions": "11"}]
        cache.set(f"ga4_sync:running:{account.pk}", "other-worker", 1800)
        self.assertEqual(sync_analytics_account.run(account.pk)["reason"], "already_running")
        api_class.assert_not_called()
        cache.delete(f"ga4_sync:running:{account.pk}")
        result = sync_analytics_account.run(account.pk)
        self.assertEqual(result["daily_metrics"], 1)
        prop = AnalyticsProperty.objects.get()
        self.assertEqual(prop.daily_metrics.get().sessions, 17)
        self.assertEqual(prop.landing_page_metrics.get().sessions, 11)
        self.assertEqual(prop.currency, "USD")

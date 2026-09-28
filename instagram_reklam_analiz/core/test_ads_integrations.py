from datetime import timedelta
from decimal import Decimal
from unittest.mock import Mock, patch
from urllib.parse import parse_qs, urlparse
import time

from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from core.models import Platform, PlatformAccount, PlatformConnection, CampaignMetricHistory
from core.services import ads_integrations as api


@override_settings(
    GOOGLE_ADS_CLIENT_ID="client", GOOGLE_ADS_CLIENT_SECRET="secret",
    GOOGLE_ADS_REDIRECT_URI="https://reklamanaliz.net/connect/google-ads/callback/",
    GOOGLE_ADS_DEVELOPER_TOKEN="developer", GOOGLE_ADS_API_VERSION="v25",
    FACEBOOK_APP_ID="meta-app", FACEBOOK_APP_SECRET="meta-secret",
    FACEBOOK_REDIRECT_URI="https://reklamanaliz.net/connect/facebook/callback/",
)
class AdsIntegrationTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(username="ads-owner")
        self.other = get_user_model().objects.create_user(username="ads-other")
        self.client.force_login(self.user)
        self.platform, _ = Platform.objects.get_or_create(code="google_ads", defaults={"name": "Google Ads"})

    def connection(self, **kwargs):
        return PlatformConnection.objects.create(user=self.user, platform=self.platform,
            access_token="private-access", refresh_token="private-refresh",
            extra_data={"source": "ads_oauth"}, token_expiry=timezone.now()+timedelta(hours=1), **kwargs)

    def flow(self, provider="google_ads", **overrides):
        session = self.client.session
        session[f"ads_oauth:{provider}"] = {"state": "nonce", "user": self.user.pk, "created": time.time(), "client": None, **overrides}
        session.save()

    def test_connect_requires_post_and_creates_unpredictable_state(self):
        url = reverse("integration_connect", args=["google_ads"])
        self.assertEqual(self.client.get(url).status_code, 405)
        result = self.client.post(url)
        params = parse_qs(urlparse(result.url).query)
        self.assertEqual(params["scope"], [api.ADWORDS_SCOPE])
        self.assertEqual(params["access_type"], ["offline"])
        self.assertGreater(len(params["state"][0]), 30)
        self.assertNotIn("secret", result.url)

    @patch("core.services.ads_integrations.exchange_code")
    def test_wrong_expired_or_cross_user_state_never_exchanges_code(self, exchange):
        for overrides, state in (({}, "wrong"), ({"created": 0}, "nonce"), ({"user": self.other.pk}, "nonce")):
            self.flow(**overrides)
            self.client.get(reverse("google_ads_callback"), {"state": state, "code": "secret-code"})
        exchange.assert_not_called()

    @patch("core.services.ads_integrations.exchange_code")
    def test_denial_does_not_save_connection(self, exchange):
        self.flow()
        self.client.get(reverse("google_ads_callback"), {"state": "nonce", "error": "access_denied"})
        exchange.assert_not_called()
        self.assertEqual(PlatformConnection.objects.count(), 0)

    @patch("core.services.plan_limits.ensure_platform_account_capacity")
    @patch("core.services.ads_integrations.discover_accounts")
    @patch("core.services.ads_integrations.exchange_code")
    def test_callback_selects_only_verified_accounts_and_replay_is_rejected(self, exchange, discover, limit):
        exchange.return_value = {"access_token": "private-access", "refresh_token": "private-refresh", "scope": api.ADWORDS_SCOPE, "expires_in": 3600}
        discover.return_value = [{"id": "1234567890", "name": "Real account", "currency": "USD", "kind": "ad_account"}]
        self.flow()
        response = self.client.get(reverse("google_ads_callback"), {"state": "nonce", "code": "code"})
        self.assertRedirects(response, reverse("integration_select", args=["google_ads"]), fetch_redirect_response=False)
        self.assertFalse(PlatformAccount.objects.exists())
        self.assertNotIn("private-access", str(dict(self.client.session)))
        self.client.get(reverse("google_ads_callback"), {"state": "nonce", "code": "code"})
        self.assertEqual(exchange.call_count, 1)
        select = reverse("integration_select", args=["google_ads"])
        response = self.client.post(select, {"accounts": ["forged"]})
        self.assertContains(response, "Listeden en az bir")
        self.assertFalse(PlatformAccount.objects.exists())
        response = self.client.post(select, {"accounts": ["1234567890"]})
        self.assertEqual(response.status_code, 302)
        account = PlatformAccount.objects.get()
        self.assertEqual(account.account_id, "1234567890")
        self.assertTrue(account.connection.is_active)
        self.assertNotContains(self.client.get(reverse("integrations")), "private-access")

    @patch("core.services.ads_integrations.campaigns")
    def test_other_users_account_is_inaccessible(self, campaigns):
        account = PlatformAccount.objects.create(user=self.other, platform=self.platform, account_id="123", access_token="secret")
        self.assertEqual(self.client.get(reverse("integration_campaigns", args=[account.pk])).status_code, 404)
        campaigns.assert_not_called()

    @patch("core.services.ads_integrations.campaign_performance")
    @patch("core.services.ads_integrations.campaigns", return_value=[{"id": "99", "name": "Search", "status": "ENABLED", "channel": "SEARCH"}])
    def test_campaign_detail_rejects_wrong_account_campaign_and_renders_metrics(self, campaigns, performance):
        account = PlatformAccount.objects.create(user=self.user, platform=self.platform, connection=self.connection(), account_id="123", access_token="secret", extra_data={"currency": "USD"})
        response = self.client.get(reverse("integration_campaign_detail", args=[account.pk, "100"]))
        self.assertEqual(response.status_code, 404)
        performance.assert_not_called()
        response = self.client.get(reverse("integration_campaigns", args=[account.pk]))
        self.assertContains(response, "SEARCH")
        performance.return_value = [{"date": "2026-09-28", "impressions": 100, "clicks": 4, "spend": Decimal("2.5"), "conversions": 1, "conversion_value": 3}]
        response = self.client.get(reverse("integration_campaign_detail", args=[account.pk, "99"]))
        self.assertContains(response, "Search")
        self.assertContains(response, "USD")
        self.assertContains(response, "2026-09-28")

    @patch("core.services.ads_integrations._request")
    def test_refresh_updates_connection_and_accounts(self, request):
        connection = self.connection()
        connection.token_expiry = timezone.now()-timedelta(seconds=5)
        connection.save()
        account = PlatformAccount.objects.create(user=self.user, platform=self.platform, connection=connection, account_id="123", access_token="old")
        request.return_value = {"access_token": "renewed", "expires_in": 3600}
        self.assertEqual(api.connection_token(connection), "renewed")
        account.refresh_from_db()
        self.assertEqual(account.access_token, "renewed")
        self.assertEqual(account.refresh_token, "private-refresh")

    @patch("core.services.ads_integrations._request")
    def test_missing_adwords_scope_is_rejected(self, request):
        request.return_value = {"access_token": "secret", "refresh_token": "refresh", "scope": "openid"}
        with self.assertRaises(api.IntegrationError):
            api.exchange_code("google_ads", "code")

    @patch("core.services.ads_integrations.google_search")
    @patch("core.services.ads_integrations._request")
    def test_manager_discovers_client_accounts(self, request, search):
        request.return_value = {"resourceNames": ["customers/111"]}
        search.side_effect = [[{"customer": {"id": "111", "manager": True}}], [{"customerClient": {"id": "222", "descriptiveName": "Client", "currencyCode": "EUR"}}]]
        accounts = api.discover_accounts("google_ads", "token")
        self.assertEqual(accounts[0]["id"], "222")
        self.assertEqual(accounts[0]["login_customer_id"], "111")

    @patch("core.services.ads_integrations._request")
    def test_google_pagination_and_manager_header(self, request):
        request.side_effect = [{"results": [{"id": 1}], "nextPageToken": "next"}, {"results": [{"id": 2}]}]
        self.assertEqual(len(api.google_search("token", "222", "SELECT customer.id FROM customer", "111")), 2)
        self.assertEqual(request.call_args.kwargs["headers"]["login-customer-id"], "111")
        self.assertEqual(request.call_args.kwargs["json"]["pageToken"], "next")

    @patch("core.services.ads_integrations._request")
    def test_meta_uses_ad_accounts_and_fixed_origin_pagination(self, request):
        request.side_effect = [{"data": [{"id": "act_1", "account_status": 1}], "paging": {"next": "https://untrusted.invalid/?token=secret", "cursors": {"after": "cursor"}}}, {"data": [{"id": "act_2", "account_status": 2}]}]
        accounts = api.discover_accounts("facebook", "token")
        self.assertEqual([row["id"] for row in accounts], ["act_1"])
        self.assertTrue(request.call_args.args[1].endswith("/me/adaccounts"))
        self.assertEqual(request.call_args.kwargs["params"]["after"], "cursor")

    @patch("core.services.ads_integrations.requests.request")
    def test_provider_errors_do_not_leak_credentials(self, request):
        request.return_value = Mock(ok=False, status_code=403)
        request.return_value.json.return_value = {"error": {"code": 10, "message": "private-token"}}
        with self.assertRaises(api.IntegrationError) as error:
            api._request("GET", "https://example.invalid")
        self.assertNotIn("private-token", str(error.exception))

    def test_unimplemented_ad_providers_are_skipped(self):
        from core.tasks.v2_platform_sync import _should_skip_ad_sync
        for code in ("tiktok", "linkedin", "youtube", "x"):
            self.assertEqual(_should_skip_ad_sync(Mock(), code), "unsupported_for_ad_sync")

    def test_zero_reported_revenue_is_not_estimated_and_rollups_sum_ads(self):
        from core.services.v2_ad_sync import upsert_v2_ad_snapshot, rebuild_ad_metric_rollups
        account = PlatformAccount.objects.create(user=self.user, platform=self.platform, account_id="123", access_token="secret", extra_data={"currency": "USD"})
        for ad_id in ("1", "2"):
            upsert_v2_ad_snapshot(user=self.user, platform_account=account, payload={
                "platform_ad_id": ad_id, "campaign_id": "campaign", "date": "2026-09-28",
                "impressions": 100, "clicks": 10, "spend": "2.5", "conversions": "1",
                "conversion_value": "0", "allow_estimated_conversion_value": False,
            })
        rebuild_ad_metric_rollups(account, ["2026-09-28"])
        metric = CampaignMetricHistory.objects.get()
        self.assertEqual(metric.spend, Decimal("5"))
        self.assertEqual(metric.conversion_value, 0)
        self.assertEqual(metric.impressions, 200)

    def test_legacy_manual_ad_registration_does_not_create_account(self):
        for platform in ("google_ads", "facebook", "google_analytics"):
            response = self.client.post(reverse("hesap_ekle"), {"platform": platform, "account_id": "unverified", "access_token": "developer-token"})
            self.assertRedirects(response, reverse("integrations"), fetch_redirect_response=False)
        self.assertFalse(PlatformAccount.objects.exists())

    def test_agency_client_requires_management_permission(self):
        from core.models import Organization, AgencyClient
        from core.views.ads_integrations import _client
        from django.test import RequestFactory
        from django.core.exceptions import PermissionDenied
        organization = Organization.objects.create(owner=self.other, name="Other agency")
        client = AgencyClient.objects.create(organization=organization, name="Other brand")
        request = RequestFactory().post("/")
        request.user = self.user
        with self.assertRaises(PermissionDenied):
            _client(request, client.pk)

    @patch("core.services.ads_integrations._request")
    def test_meta_exchange_requires_granted_ad_permission(self, request):
        request.side_effect = [{"access_token": "short"}, {"access_token": "long", "expires_in": 5000}, {"data": [{"permission": "ads_read", "status": "declined"}]}]
        with self.assertRaises(api.IntegrationError):
            api.exchange_code("facebook", "code")

    @patch("core.platforms.google_ads.google_search")
    def test_google_ad_adapter_preserves_dates_currency_and_micros(self, search):
        from core.platforms.google_ads import GoogleAdsAPI
        import json
        account = PlatformAccount.objects.create(user=self.user, platform=self.platform, connection=self.connection(), account_id="123", access_token="secret", extra_data={"currency": "EUR"})
        search.return_value = [{"campaign": {"id": "1", "name": "Campaign", "status": "ENABLED"},
            "adGroup": {"id": "2", "name": "Group"}, "adGroupAd": {"ad": {"id": "3"}, "status": "ENABLED"},
            "segments": {"date": "2026-09-25"}, "metrics": {"costMicros": "2500000", "impressions": "100", "clicks": "10", "conversions": 2, "conversionsValue": 0}}]
        row = GoogleAdsAPI(account).get_ads(since_days=7)[0]
        self.assertEqual(Decimal(row["spend"]), Decimal("2.5"))
        self.assertEqual(row["currency"], "EUR")
        self.assertEqual(row["date"], "2026-09-25")
        json.dumps(row)  # Persistable in Ad.raw_data without Decimal serialization failures.

    def test_meta_purchase_aliases_are_not_double_counted(self):
        from core.platforms.facebook import _distinct_actions
        from core.services.performance_metrics import normalize_metric_payload
        actions = [{"action_type": key, "value": "3"} for key in ("purchase", "omni_purchase", "offsite_conversion.fb_pixel_purchase")]
        result = normalize_metric_payload({"actions": _distinct_actions(actions), "allow_estimated_conversion_value": False})
        self.assertEqual(result["purchases"], 3)
        self.assertEqual(result["conversions"], 3)
        self.assertEqual(result["conversion_value"], 0)

    def test_verified_account_identity_cannot_be_manually_replaced(self):
        account = PlatformAccount.objects.create(user=self.user, platform=self.platform, connection=self.connection(), account_id="123", access_token="secret", extra_data={"source": "ads_oauth"})
        response = self.client.post(reverse("platform_account_update", args=[account.pk]), {
            "account_id": "forged", "connection": str(account.connection_id), "is_active": "on",
        })
        self.assertEqual(response.status_code, 302)
        account.refresh_from_db()
        self.assertEqual(account.account_id, "123")

    def test_report_date_uses_advertiser_timezone(self):
        from datetime import datetime, date, timezone as dt_timezone
        account = Mock(extra_data={"timezone": "America/Los_Angeles"})
        with patch("django.utils.timezone.now", return_value=datetime(2026, 9, 28, 1, tzinfo=dt_timezone.utc)):
            self.assertEqual(api.account_today(account), date(2026, 9, 27))

from datetime import timedelta
from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import Mock, patch
from urllib.parse import parse_qs, urlsplit
import time

from django.contrib.auth import get_user_model
from django.test import TestCase, SimpleTestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from core.models import Platform, PlatformAccount, PlatformConnection, Campaign, CampaignMetricHistory, Ad, AdMetricHistory, AdGroupMetricHistory
from core.services import tiktok_ads as api
from core.services.ads_integrations import IntegrationError
from core.services.tiktok_campaign_sync import sync_tiktok_campaigns


@override_settings(TIKTOK_ADS_APP_ID="app-ads", TIKTOK_ADS_APP_SECRET="private-secret",
    TIKTOK_ADS_REDIRECT_URI="https://www.reklamanaliz.net/connect/tiktok-ads/callback/")
class TikTokAdsProtocolTests(SimpleTestCase):
    @patch("core.services.tiktok_ads.request")
    def test_daily_report_accepts_measured_zero_and_rejects_missing_or_invalid_metrics(self, request):
        day = timezone.localdate()
        row = {"dimensions": {"campaign_id": "123", "stat_time_day": day.isoformat()},
               "metrics": {"impressions": "0", "clicks": "0", "spend": "0.00"}}
        request.return_value = {"list": [row], "page_info": {"total_page": 1}}
        self.assertEqual(api.report("private-token", "1", day, day)[0]["spend"], Decimal("0"))
        for value in (None, "NaN", "Infinity", "-1", True):
            row["metrics"]["spend"] = value
            with self.assertRaises(IntegrationError):
                api.report("private-token", "1", day, day)
        row["metrics"].pop("spend")
        with self.assertRaises(IntegrationError):
            api.report("private-token", "1", day, day)

    @patch("core.services.tiktok_ads.request")
    def test_duplicate_day_and_incomplete_pagination_fail(self, request):
        day = timezone.localdate()
        row = {"dimensions": {"campaign_id": "123", "stat_time_day": day.isoformat()},
               "metrics": {"impressions": "1", "clicks": "0", "spend": "1"}}
        request.return_value = {"list": [row, row], "page_info": {"total_page": 1}}
        with self.assertRaises(IntegrationError):
            api.report("token", "1", day, day)
        request.return_value = {"list": [], "page_info": {"total_page": 2}}
        with self.assertRaises(IntegrationError):
            api.report("token", "1", day, day)

    @patch("core.services.tiktok_ads.request", return_value={"list": [], "page_info": {"total_page": 0}})
    def test_large_date_range_is_split_into_nonoverlapping_month_windows(self, request):
        end = timezone.localdate()
        start = end - timedelta(days=60)
        self.assertEqual(api.report("token", "1", start, end), [])
        self.assertEqual(request.call_count, 3)
        self.assertEqual(request.call_args_list[0].kwargs["params"]["end_date"], (start + timedelta(days=29)).isoformat())
        self.assertEqual(request.call_args_list[1].kwargs["params"]["start_date"], (start + timedelta(days=30)).isoformat())

    @patch("core.services.tiktok_ads.requests.request")
    def test_provider_errors_are_sanitized_and_redirects_disabled(self, request):
        request.return_value = Mock(ok=False)
        request.return_value.json.return_value = {"code": 401, "message": "private-secret private-token"}
        with self.assertRaises(IntegrationError) as failure:
            api.request("GET", "campaign/get", "private-token")
        self.assertNotIn("private", str(failure.exception))
        self.assertFalse(request.call_args.kwargs["allow_redirects"])


@override_settings(TIKTOK_ADS_APP_ID="app-ads", TIKTOK_ADS_APP_SECRET="private-secret",
    TIKTOK_ADS_REDIRECT_URI="https://www.reklamanaliz.net/connect/tiktok-ads/callback/")
class TikTokAdsFlowTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(username="tik-ads", is_superuser=True, is_staff=True)
        self.client.force_login(self.user)
        self.platform = Platform.objects.create(code="tiktok", name="TikTok")
        self.connection = PlatformConnection.objects.create(user=self.user, platform=self.platform, status="active",
            is_active=True, access_token="private-token", extra_data={"source": "tiktok_ads_oauth", "tiktok_ads_app_id": "app-ads"})
        self.account = PlatformAccount.objects.create(user=self.user, platform=self.platform, connection=self.connection,
            account_id="1", extra_data={"source": "tiktok_ads_oauth"})

    def test_organic_credentials_and_cross_user_connection_cannot_be_used_for_ads(self):
        self.assertEqual(api.account_token(self.account), "private-token")
        self.connection.extra_data["source"] = "tiktok_oauth"
        self.connection.save()
        with self.assertRaises(IntegrationError):
            api.account_token(self.account)
        self.connection.extra_data["source"] = "tiktok_ads_oauth"
        self.connection.user = get_user_model().objects.create_user(username="other-ads-owner")
        self.connection.save()
        with self.assertRaises(IntegrationError):
            api.account_token(self.account)

    def test_authorization_uses_separate_business_app_without_secret(self):
        result = self.client.post(reverse("integration_connect", args=["tiktok_ads"]))
        parsed = urlsplit(result.url)
        self.assertEqual(parsed.hostname, "business-api.tiktok.com")
        params = parse_qs(parsed.query)
        self.assertEqual(params["app_id"], ["app-ads"])
        self.assertNotIn("private-secret", result.url)

    @patch("core.services.tiktok_ads.discover_accounts", return_value=[{"id": "99", "name": "Advertiser", "currency": "USD", "timezone": "UTC"}])
    @patch("core.services.tiktok_ads.exchange_code", return_value={"access_token": "new-private", "expires_in": None,
        "scope": "", "tiktok_ads_app_id": "app-ads"})
    @patch("core.services.plan_limits.ensure_platform_account_capacity")
    def test_callback_auth_code_selection_preserves_separate_connection_and_rejects_replay(self, capacity, exchange, discover):
        session = self.client.session
        session["ads_oauth:tiktok_ads"] = {"user": self.user.pk, "created": time.time(), "state": "nonce", "client": None}
        session.save()
        url = reverse("tiktok_ads_callback")
        result = self.client.get(url, {"state": "nonce", "auth_code": "one-use", "code": "wrong"})
        exchange.assert_called_once_with("one-use")
        self.assertEqual(result.status_code, 302)
        self.client.post(reverse("integration_select", args=["tiktok_ads"]), {"accounts": ["99"]})
        account = PlatformAccount.objects.get(account_id="99")
        self.assertEqual(account.platform.code, "tiktok")
        self.assertEqual(account.connection.extra_data["source"], "tiktok_ads_oauth")
        self.assertEqual(account.connection.extra_data["tiktok_ads_app_id"], "app-ads")
        self.assertIsNone(account.token_expiry)
        self.client.get(url, {"state": "nonce", "auth_code": "one-use"})
        self.assertEqual(exchange.call_count, 1)

    def read_fixture(self, *, reports=None):
        inventory = {"10": {"id": "10", "name": "Measured campaign", "status": "PAUSED", "objective": "TRAFFIC", "raw": {}},
                     "11": {"id": "11", "name": "No data", "status": "ACTIVE", "objective": "TRAFFIC", "raw": {}}}
        metrics = {"date": timezone.localdate().isoformat(), "impressions": 100, "clicks": 5, "spend": Decimal("2.50")}
        patches = [patch("core.services.tiktok_campaign_sync.api.advertiser_info", return_value={"currency": "USD", "timezone": "UTC"}),
                   patch("core.services.tiktok_campaign_sync.api.inventory", return_value=inventory),
                   patch("core.services.tiktok_campaign_sync.api.report", side_effect=reports if reports is not None else [
                       [{**metrics, "campaign_id": "10"}], [{**metrics, "ad_id": "20"}]]),
                   patch("core.services.tiktok_campaign_sync.api.rows", side_effect=[
                       [{"ad_id": "20", "ad_name": "Measured ad", "campaign_id": "10", "adgroup_id": "30", "operation_status": "DISABLE"},
                        {"ad_id": "21", "ad_name": "Other ad", "campaign_id": "10", "adgroup_id": "30", "operation_status": "DISABLE"}],
                       [{"adgroup_id": "30", "campaign_id": "10", "adgroup_name": "Group"}]])]
        for item in patches:
            item.start()
        try:
            return sync_tiktok_campaigns(self.account, 30, 100)
        finally:
            for item in reversed(patches):
                item.stop()

    def test_sync_persists_only_measured_hierarchy_and_is_idempotent(self):
        for _ in range(2):
            result = self.read_fixture()
        self.assertEqual(result["campaigns_synced"], 1)
        self.assertEqual(Campaign.objects.count(), 1)
        self.assertEqual(CampaignMetricHistory.objects.count(), 1)
        self.assertEqual(Ad.objects.count(), 1)
        self.assertEqual(AdMetricHistory.objects.count(), 1)
        metric = CampaignMetricHistory.objects.get()
        self.assertEqual(metric.spend, Decimal("2.50"))
        self.assertEqual(metric.currency, "USD")
        self.assertEqual(metric.impressions, 100)

    def test_failed_or_empty_report_creates_no_inventory_or_placeholder_rows(self):
        with self.assertRaises(IntegrationError):
            self.read_fixture(reports=[[], IntegrationError("Unavailable")])
        self.assertFalse(Campaign.objects.exists())
        result = self.read_fixture(reports=[[], []])
        self.assertEqual(result["metric_rows"], 0)
        self.assertFalse(Campaign.objects.exists())
        self.assertFalse(Ad.objects.exists())

    def test_multiple_ads_are_summed_but_campaign_report_remains_authoritative(self):
        metric = {"date": timezone.localdate().isoformat(), "impressions": 100, "clicks": 5, "spend": Decimal("2.50")}
        self.read_fixture(reports=[[{**metric, "campaign_id": "10", "impressions": 250}],
                                  [{**metric, "ad_id": "20"}, {**metric, "ad_id": "21"}]])
        self.assertEqual(CampaignMetricHistory.objects.get().impressions, 250)
        self.assertEqual(AdGroupMetricHistory.objects.get().impressions, 200)
        self.assertEqual(AdMetricHistory.objects.count(), 2)

    @patch("core.services.tiktok_campaign_sync.sync_tiktok_campaigns", return_value={"campaigns_synced": 1})
    @patch("core.services.sync_policy.policy_for_user", return_value=SimpleNamespace(history_days=30, max_records=100))
    def test_worker_routes_only_ads_connection_to_ad_sync(self, policy, sync):
        from core.tasks.v2_platform_sync import sync_v2_platform_account_ads
        result = sync_v2_platform_account_ads.run(self.account.pk, retry_errors=False)
        self.assertEqual(result["campaigns_synced"], 1)
        self.connection.extra_data["source"] = "tiktok_oauth"
        self.connection.save()
        result = sync_v2_platform_account_ads.run(self.account.pk, retry_errors=False)
        self.assertTrue(result["skipped"])
        self.assertEqual(sync.call_count, 1)

from datetime import date
import json
from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import TestCase

from core.models import (Platform, PlatformAccount, PlatformConnection, Campaign,
                         Ad, AdMetricHistory, CampaignMetricHistory, PlatformSyncJob)
from core.platforms.facebook import FacebookAPI
from core.services.v2_ad_sync import upsert_v2_ad_snapshot
from core.services.campaign_panel_service import build_campaign_list


class MetaCampaignInventoryTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(username="meta-inventory")
        self.platform = Platform.objects.create(code="facebook", name="Facebook")
        connection = PlatformConnection.objects.create(user=self.user, platform=self.platform,
            access_token="test-token", extra_data={"source": "ads_oauth"})
        self.account = PlatformAccount.objects.create(user=self.user, platform=self.platform,
            connection=connection, account_id="act_123", extra_data={"currency": "TRY"})
        self.ads = [{"id": "a1", "name": "New ad", "effective_status": "IN_PROCESS",
            "campaign": {"id": "c1", "name": "New campaign", "status": "ACTIVE", "objective": "OUTCOME_TRAFFIC"},
            "adset": {"id": "s1", "name": "Ad set", "status": "ACTIVE", "lifetime_budget": "6000"}},
            {"id": "a2", "name": "Old ad", "effective_status": "PAUSED",
             "campaign": {"id": "c2", "name": "Old campaign", "status": "PAUSED"},
             "adset": {"id": "s2", "name": "Old set", "status": "PAUSED"}}]
        self.insights = []
        self.campaigns = [ad["campaign"] for ad in self.ads] + [
            {"id": "c3", "name": "Empty paused campaign", "status": "PAUSED"}]

    def rows(self, token, path, params):
        if path.endswith("/ads"):
            self.assertNotIn("filtering", params)
            self.assertNotIn("time_range", params)
            self.assertTrue({"PAUSED", "ARCHIVED", "DELETED", "IN_PROCESS"}.issubset(json.loads(params["effective_status"])))
            return self.ads
        if path.endswith("/campaigns"):
            self.assertNotIn("filtering", params)
            self.assertNotIn("time_range", params)
            self.assertTrue({"PAUSED", "ARCHIVED", "DELETED"}.issubset(json.loads(params["effective_status"])))
            return self.campaigns
        self.assertEqual(path, "act_123/insights")
        self.assertEqual(params["time_increment"], 1)
        return self.insights

    def sync(self):
        from core.tasks.v2_platform_sync import sync_v2_platform_account_ads
        with patch("core.platforms.facebook.account_token", return_value="test-token"), \
             patch("core.platforms.facebook.meta_rows", side_effect=self.rows), \
             patch("core.platforms.facebook.account_today", return_value=date(2026, 10, 9)), \
             patch("core.services.sync_policy.policy_for_user", return_value=SimpleNamespace(history_days=365, max_records=100)), \
             patch("core.tasks.admin_ops.generate_octo_tasks.apply_async"):
            return sync_v2_platform_account_ads.run(self.account.id, "OWN", 365)

    def test_new_and_paused_entities_without_insights_are_visible_without_fake_metrics(self):
        self.sync()
        self.assertEqual(Campaign.objects.filter(platform_account=self.account).count(), 3)
        self.assertEqual(Ad.objects.filter(platform_account=self.account).count(), 2)
        self.assertEqual(Ad.objects.get(platform_ad_id="a2").status, "PAUSED")
        self.assertEqual(Ad.objects.get(platform_ad_id="a1").ad_group.lifetime_budget, Decimal("60"))
        self.assertFalse(AdMetricHistory.objects.exists())
        self.assertFalse(CampaignMetricHistory.objects.exists())
        # Dates select metrics; they must not hide paused/empty campaigns.
        cards = build_campaign_list(self.user, self.account, date(2020, 1, 1), date(2020, 1, 2))
        self.assertEqual({card["platform_campaign_id"] for card in cards}, {"c1", "c2", "c3"})

    def test_daily_history_is_idempotent_and_metadata_sync_does_not_erase_it(self):
        self.insights = [{"ad_id": "a2", "campaign_id": "c2", "adset_id": "s2", "ad_name": "Old ad",
            "campaign_name": "Old campaign", "adset_name": "Old set", "date_start": day,
            "spend": spend, "impressions": impressions, "clicks": "1", "account_currency": "TRY"}
            for day, spend, impressions in [("2026-09-01", "3", "10"), ("2026-09-02", "5", "20")]]
        self.sync()
        self.sync()
        self.assertEqual(AdMetricHistory.objects.count(), 2)
        self.assertEqual(set(AdMetricHistory.objects.values_list("date", flat=True)), {date(2026, 9, 1), date(2026, 9, 2)})
        self.assertEqual(CampaignMetricHistory.objects.get(date="2026-09-02").spend, Decimal("5"))
        self.insights = []
        self.sync()
        self.assertEqual(AdMetricHistory.objects.count(), 2)
        self.assertEqual(AdMetricHistory.objects.get(date="2026-09-02").spend, Decimal("5"))
        self.assertEqual(Campaign.objects.get(platform_campaign_id="c2").status, "PAUSED")

    def test_deleted_ad_insights_are_preserved_when_absent_from_inventory(self):
        self.insights = [{"ad_id": "deleted-ad", "campaign_id": "old-c", "adset_id": "old-s",
            "date_start": "2026-09-01", "spend": "7", "impressions": "30"}]
        self.sync()
        self.assertEqual(AdMetricHistory.objects.get().ad.platform_ad_id, "deleted-ad")

    def test_campaign_status_filter_has_separate_cache_and_keeps_history(self):
        self.sync()
        self.client.force_login(self.user)
        url = "/api/campaign-panel/campaigns/"
        for status, expected in [("", {"c1", "c2", "c3"}), ("ACTIVE", {"c1"}),
                                 ("INACTIVE", {"c2", "c3"}), ("UNKNOWN", set()), ("", {"c1", "c2", "c3"})]:
            response = self.client.get(url, {"account_id": self.account.id, "campaign_status": status})
            self.assertEqual(response.status_code, 200)
            self.assertEqual({row["platform_campaign_id"] for row in response.json()["campaigns"]}, expected)
        self.assertEqual(self.client.get(url, {"account_id": self.account.id, "campaign_status": "invalid"}).status_code, 400)

    def test_metadata_only_update_preserves_existing_same_day_metric(self):
        payload = {"platform_ad_id": "a1", "platform_campaign_id": "c1", "platform_adgroup_id": "s1",
                   "date": "2026-10-09", "spend": "8", "impressions": 100}
        upsert_v2_ad_snapshot(user=self.user, platform_account=self.account, payload=payload)
        payload.update(metrics_available=False, spend="0", impressions=0, status="PAUSED")
        result = upsert_v2_ad_snapshot(user=self.user, platform_account=self.account, payload=payload)
        self.assertIsNone(result["metric"])
        self.assertEqual(result["ad"].status, "PAUSED")
        self.assertEqual(AdMetricHistory.objects.get().spend, Decimal("8"))

    def test_manual_pipeline_performs_provider_pull_before_counting_success(self):
        from core.tasks.ads_pipeline import sync_platform_account_ads
        job = PlatformSyncJob.objects.create(user=self.user, platform_account=self.account, days_back=30)
        def pull(*args, **kwargs):
            Campaign.objects.create(user=self.user, platform_account=self.account,
                                    platform_campaign_id="pulled", name="Pulled")
            return SimpleNamespace(get=lambda **kw: {"ads_synced": 0, "rule_engine": {"status": "queued"}})
        with patch("core.tasks.v2_platform_sync.sync_v2_platform_account_ads.apply", side_effect=pull) as request:
            result = sync_platform_account_ads.run(job.id)
        request.assert_called_once_with(args=(self.account.id, "OWN", 30), throw=True)
        self.assertEqual(result["campaigns_count"], 1)
        job.refresh_from_db()
        self.assertEqual(job.status, "completed")

    def test_manual_pipeline_cannot_report_success_for_skipped_provider(self):
        from core.tasks.ads_pipeline import sync_platform_account_ads
        job = PlatformSyncJob.objects.create(user=self.user, platform_account=self.account, days_back=30)
        with patch("core.tasks.v2_platform_sync.sync_v2_platform_account_ads.apply") as request, \
             patch.object(sync_platform_account_ads, "retry", side_effect=ValueError("sync failed")):
            request.return_value.get.return_value = {"skipped": True, "reason": "token_missing"}
            with self.assertRaises(ValueError):
                sync_platform_account_ads.run(job.id)
        job.refresh_from_db()
        self.assertEqual(job.status, "failed")

from datetime import timedelta
from decimal import Decimal
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone

from core.models import Platform, PlatformAccount, PlatformConnection, Campaign, CampaignMetricHistory, Ad
from core.services.linkedin_campaign_sync import sync_linkedin_campaigns
from core.services.ads_integrations import IntegrationError


class LinkedInCampaignSyncTests(TestCase):
    def setUp(self):
        user = get_user_model().objects.create_user(username="linkedin-sync")
        platform, _ = Platform.objects.get_or_create(code="linkedin", defaults={"name": "LinkedIn"})
        connection = PlatformConnection.objects.create(user=user, platform=platform,
            access_token="fixture", extra_data={"source": "ads_oauth"})
        self.account = PlatformAccount.objects.create(user=user, platform=platform,
            connection=connection, account_id="123", extra_data={"currency": "USD"})
        self.old = Campaign.objects.create(user=user, platform_account=self.account,
            platform_campaign_id="old", name="History", status="ACTIVE")
        self.row = {"id": "10", "name": "Active", "status": "ACTIVE"}

    @patch("core.services.linkedin_campaign_sync.api.campaign_performance")
    @patch("core.services.linkedin_campaign_sync.api.campaigns")
    def test_daily_campaign_metrics_are_idempotent_without_fake_ads(self, inventory, performance):
        inventory.return_value = [self.row]
        performance.return_value = [{"date": timezone.localdate().isoformat(),
            "impressions": 100, "clicks": 5, "spend": Decimal("2.50")}]
        for _ in range(2):
            result = sync_linkedin_campaigns(self.account, 30, 100)
        self.assertEqual(result["campaigns_synced"], 1)
        self.assertEqual(CampaignMetricHistory.objects.count(), 1)
        self.assertEqual(CampaignMetricHistory.objects.get().spend, Decimal("2.50"))
        self.assertFalse(Ad.objects.exists())
        self.assertFalse(Campaign.objects.filter(pk=self.old.pk).exists())

    @patch("core.services.linkedin_campaign_sync.api.campaign_performance", side_effect=IntegrationError("provider unavailable"))
    @patch("core.services.linkedin_campaign_sync.api.campaigns")
    def test_failed_provider_read_preserves_inventory(self, inventory, performance):
        inventory.return_value = [self.row]
        with self.assertRaises(IntegrationError):
            sync_linkedin_campaigns(self.account, 30, 100)
        self.old.refresh_from_db()
        self.assertTrue(self.old.is_active)
        self.assertEqual(Campaign.objects.count(), 1)

    @patch("core.services.linkedin_campaign_sync.api.campaigns", return_value=[])
    def test_successful_empty_inventory_retains_history(self, inventory):
        day = timezone.localdate() - timedelta(days=1)
        CampaignMetricHistory.objects.create(campaign=self.old, date=day, spend=3)
        result = sync_linkedin_campaigns(self.account, 30, 100)
        self.assertEqual(result["campaigns_synced"], 0)
        self.old.refresh_from_db()
        self.assertFalse(self.old.is_active)
        self.assertEqual(CampaignMetricHistory.objects.get().spend, 3)

    @patch("core.services.linkedin_campaign_sync.api.campaigns", return_value=[])
    @patch("core.services.sync_policy.policy_for_user")
    def test_worker_routes_linkedin_to_real_campaign_service(self, policy, inventory):
        from types import SimpleNamespace
        from core.tasks.v2_platform_sync import sync_v2_platform_account_ads
        policy.return_value = SimpleNamespace(history_days=30, max_records=100)
        result = sync_v2_platform_account_ads.run(self.account.pk, retry_errors=False)
        self.assertNotIn("skipped", result)
        inventory.assert_called_once()

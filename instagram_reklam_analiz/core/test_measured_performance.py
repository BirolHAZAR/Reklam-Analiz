from datetime import timedelta

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from core.models import Platform, PlatformAccount, Campaign, Ad, AdMetricHistory, CampaignMetricHistory


class MeasuredPerformanceTests(TestCase):
    def setUp(self):
        from django.core.cache import cache
        cache.clear()
        self.user = get_user_model().objects.create_user(username="measured-performance")
        self.client.force_login(self.user)
        platform, _ = Platform.objects.get_or_create(code="facebook", defaults={"name": "Facebook"})
        self.account = PlatformAccount.objects.create(user=self.user, platform=platform, account_id="123")
        self.campaign = Campaign.objects.create(user=self.user, platform_account=self.account,
            platform_campaign_id="campaign", name="Inventory", status="ACTIVE")
        self.ad = Ad.objects.create(user=self.user, platform_account=self.account,
            campaign=self.campaign, platform_ad_id="ad", name="Unmeasured")
        self.today = timezone.localdate()

    def movements(self, **params):
        response = self.client.get(reverse("reklam_hareketleri"), params,
            HTTP_X_REQUESTED_WITH="XMLHttpRequest")
        self.assertEqual(response.status_code, 200)
        return response.json()

    def campaigns(self, **params):
        response = self.client.get(reverse("api_campaigns_by_account"),
            {"account_id": self.account.pk, **params})
        self.assertEqual(response.status_code, 200)
        return response.json()["campaigns"]

    def test_missing_metrics_are_hidden_by_default_and_not_zero(self):
        data = self.movements()
        self.assertEqual(data["ads"], [])
        self.assertIsNone(data["total_spend"])
        self.assertFalse(data["has_data"])
        self.assertEqual(data["inventory_count"], 1)
        data = self.movements(include_unmeasured="1")
        self.assertEqual(data["ads"], [])
        self.assertIsNone(data["total_impressions"])

    def test_real_zero_measurements_are_retained(self):
        AdMetricHistory.objects.create(ad=self.ad, date=self.today, impressions=0, spend=0)
        data = self.movements()
        self.assertEqual(len(data["ads"]), 1)
        self.assertTrue(data["has_data"])
        self.assertEqual(data["total_spend"], 0)

    def test_out_of_period_measurement_does_not_generate_current_score(self):
        AdMetricHistory.objects.create(ad=self.ad, date=self.today-timedelta(days=100), spend=12)
        self.assertEqual(self.movements()["ads"], [])
        data = self.movements(include_unmeasured="1")
        self.assertIsNone(data["selected_ad"])
        self.assertEqual(data["chart_labels"], [])

    def test_instagram_duplicate_is_excluded_even_with_metrics(self):
        platform, _ = Platform.objects.get_or_create(code="instagram", defaults={"name": "Instagram"})
        self.account.platform = platform
        self.account.save(update_fields=["platform"])
        AdMetricHistory.objects.create(ad=self.ad, date=self.today, impressions=100)
        self.assertEqual(self.movements(include_unmeasured="1")["ads"], [])

    def test_campaign_inventory_cannot_bypass_measurement_policy(self):
        self.assertEqual(self.campaigns(), [])
        self.assertEqual(self.campaigns(include_unmeasured="1"), [])
        self.assertEqual(self.campaigns(), [])

    def test_campaign_measurements_respect_period_and_preserve_zero(self):
        CampaignMetricHistory.objects.create(campaign=self.campaign, date=self.today, spend=0)
        self.assertEqual(len(self.campaigns()), 1)
        self.assertEqual(self.campaigns(date_to=str(self.today-timedelta(days=1))), [])

    def test_upsert_does_not_create_any_entity_without_measurements(self):
        from core.services.v2_ad_sync import upsert_v2_ad_snapshot
        from core.models import AdGroup, Creative
        for payload in ({"platform_ad_id": "empty", "name": "Empty"},
                        {"platform_ad_id": "empty", "metrics_available": False, "spend": 0}):
            result = upsert_v2_ad_snapshot(user=self.user, platform_account=self.account, payload=payload)
            self.assertIsNone(result["ad"])
        self.assertEqual(Ad.objects.count(), 1)
        self.assertEqual(Campaign.objects.count(), 1)
        self.assertFalse(AdGroup.objects.exists())
        self.assertFalse(Creative.objects.exists())

    def test_cleanup_retains_measured_history_including_real_zero(self):
        from core.services.measurement_policy import prune_unmeasured
        measured = Ad.objects.create(user=self.user, platform_account=self.account,
            campaign=self.campaign, platform_ad_id="zero", name="Measured zero")
        AdMetricHistory.objects.create(ad=measured, date=self.today, spend=0)
        result = prune_unmeasured(self.account, apply=True)
        self.assertEqual(result["ads"], 1)
        self.assertTrue(Ad.objects.filter(pk=measured.pk).exists())
        self.assertTrue(Campaign.objects.filter(pk=self.campaign.pk).exists())

    def test_provider_campaign_metrics_are_imported_without_ad_metrics(self):
        from types import SimpleNamespace
        from unittest.mock import patch
        from core.models import PlatformConnection
        from core.tasks.v2_platform_sync import sync_v2_platform_account_ads
        self.account.connection = PlatformConnection.objects.create(user=self.user,
            platform=self.account.platform, access_token="fixture", extra_data={"source": "ads_oauth"})
        self.account.save(update_fields=["connection"])
        day = self.today.isoformat()

        class CampaignOnlyAPI:
            def __init__(self, account):
                pass

            def get_campaigns(self):
                return [{"id": "new", "name": "Measured new campaign", "status": "ACTIVE"},
                        {"id": "empty", "name": "Unmeasured new campaign", "status": "ACTIVE"}]

            def get_ads(self, **kwargs):
                return []

            def get_campaign_metrics(self, **kwargs):
                return [{"platform_campaign_id": "new", "date": day, "impressions": 100,
                         "clicks": 5, "spend": "12.5", "allow_estimated_conversion_value": False}]

        with patch("core.tasks.v2_platform_sync._get_api_class", return_value=CampaignOnlyAPI), \
             patch("core.services.sync_policy.policy_for_user", return_value=SimpleNamespace(history_days=30, max_records=100)), \
             patch("core.tasks.admin_ops.generate_octo_tasks.apply_async"):
            sync_v2_platform_account_ads.run(self.account.pk, retry_errors=False)
        self.assertEqual(list(Campaign.objects.values_list("platform_campaign_id", flat=True)), ["new"])
        metric = CampaignMetricHistory.objects.get()
        self.assertEqual(float(metric.spend), 12.5)
        self.assertEqual(metric.raw_metrics["source"], "provider_campaign")
        self.assertFalse(Ad.objects.exists())

    def test_manual_policy_is_staff_only_and_empty_pull_does_not_queue_ai(self):
        from unittest.mock import Mock, patch
        from core.models import PlatformConnection
        from core.tasks.v2_platform_sync import sync_v2_platform_account_ads
        self.account.connection = PlatformConnection.objects.create(user=self.user,
            platform=self.account.platform, access_token="fixture", extra_data={"source": "ads_oauth"})
        self.account.save(update_fields=["connection"])
        provider = Mock()
        provider.get_report_data.return_value = ([], [], [])
        with patch("core.services.sync_policy.policy_for_user", return_value=None), \
             patch("core.tasks.v2_platform_sync._get_api_class", return_value=Mock(return_value=provider)), \
             patch("core.tasks.admin_ops.generate_octo_tasks.apply_async") as queue:
            denied = sync_v2_platform_account_ads.run(self.account.pk, staff_manual=True)
            self.assertEqual(denied["reason"], "active_subscription_required")
            provider.get_report_data.assert_not_called()
            self.user.is_staff = True
            self.user.save(update_fields=["is_staff"])
            result = sync_v2_platform_account_ads.run(self.account.pk, staff_manual=True, retry_errors=False)
            self.assertEqual(result["rule_engine"]["status"], "no_measurements")
            queue.assert_not_called()

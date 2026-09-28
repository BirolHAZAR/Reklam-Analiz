from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from core.models import (
    Ad, AdGroup, AdMetricHistory, Campaign, Creative, Platform,
    PlatformAccount, PlatformSyncJob,
)


class SyncCenterAccessTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(username="sync-owner")
        self.other = get_user_model().objects.create_user(username="sync-other")
        self.meta, _ = Platform.objects.get_or_create(code="facebook", defaults={"name": "Meta"})
        self.google, _ = Platform.objects.get_or_create(code="google_ads", defaults={"name": "Google Ads"})
        self.account = PlatformAccount.objects.create(user=self.user, platform=self.meta, account_id="own", access_token="test")
        self.other_account = PlatformAccount.objects.create(user=self.other, platform=self.meta, account_id="other", access_token="test")
        for user, account, count in [(self.user, self.account, 1), (self.other, self.other_account, 2)]:
            for i in range(count):
                campaign = Campaign.objects.create(user=user, platform_account=account, platform_campaign_id=str(i), name="Campaign")
                group = AdGroup.objects.create(user=user, campaign=campaign, platform_adgroup_id=str(i), name="Group")
                creative = Creative.objects.create(user=user, platform_account=account)
                ad = Ad.objects.create(user=user, platform_account=account, campaign=campaign, ad_group=group, creative=creative)
                AdMetricHistory.objects.create(ad=ad, date=timezone.localdate())

    def test_login_required(self):
        self.assertEqual(self.client.get(reverse("sync_center")).status_code, 302)

    def test_ordinary_user_sees_only_own_counts_even_with_foreign_query_parameters(self):
        self.client.force_login(self.user)
        response = self.client.get(reverse("sync_center"), {"user": self.other.pk, "account_id": self.other_account.pk})
        self.assertEqual(response.status_code, 200)
        for key in ("today_campaigns", "today_adgroups", "today_ads", "today_creatives", "today_metrics",
                    "total_accounts", "total_campaigns", "total_ads", "total_metrics"):
            self.assertEqual(response.context[key], 1, key)

    def test_jobs_stay_with_their_owner_and_platform_and_errors_are_not_exposed(self):
        PlatformSyncJob.objects.create(user=self.user, platform_account=self.account, status="failed", error_message="private-provider-response")
        PlatformSyncJob.objects.create(user=self.other, platform_account=self.other_account, status="running")
        self.client.force_login(self.user)
        response = self.client.get(reverse("sync_center"))
        platforms = {p["code"]: p for p in response.context["platforms"]}
        self.assertEqual(platforms["facebook"]["status"], "error")
        self.assertEqual(platforms["facebook"]["account_count"], 1)
        self.assertEqual(platforms["google_ads"]["status"], "empty")
        self.assertNotContains(response, "private-provider-response")

    def test_staff_is_also_scoped_to_own_data(self):
        self.user.is_staff = True
        self.user.save(update_fields=["is_staff"])
        self.client.force_login(self.user)
        self.assertEqual(self.client.get(reverse("sync_center")).context["total_campaigns"], 1)

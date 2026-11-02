from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone
from datetime import timedelta

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

    def test_rate_limit_wait_is_displayed_as_waiting_instead_of_error(self):
        PlatformSyncJob.objects.create(user=self.user, platform_account=self.account,
            status="pending", result={"waiting_reason": "meta_rate_limit", "retry_after": 300})
        self.client.force_login(self.user)
        response = self.client.get(reverse("sync_center"))
        platform = next(p for p in response.context["platforms"] if p["code"] == "facebook")
        self.assertEqual(platform["status"], "running")
        self.assertEqual(platform["status_label"], "Meta kotası bekleniyor")

    def test_instagram_organic_health_does_not_follow_meta_ad_cooldown(self):
        from core.models import PlatformConnection
        instagram, _ = Platform.objects.get_or_create(code="instagram", defaults={"name": "Instagram"})
        profile = PlatformAccount.objects.create(user=self.user, platform=instagram, account_id="profile",
            access_token="test", extra_data={"auth_type": "instagram_login"})
        connection = PlatformConnection.objects.create(user=self.user, platform=self.meta,
            access_token="test", extra_data={"source": "ads_oauth"})
        self.account.connection = connection
        self.account.save(update_fields=["connection"])
        PlatformSyncJob.objects.create(user=self.user, platform_account=self.account, status="pending",
            result={"waiting_reason": "meta_rate_limit"})
        PlatformSyncJob.objects.create(user=self.user, platform_account=profile, status="failed")
        profile.extra_data = {**profile.extra_data, "organic_last_sync_at":
                              (timezone.now() + timedelta(seconds=1)).isoformat()}
        profile.save(update_fields=["extra_data"])
        self.client.force_login(self.user)
        response = self.client.get(reverse("sync_center"))
        platform = next(p for p in response.context["platforms"] if p["code"] == "instagram")
        self.assertEqual(platform["status"], "ok")
        self.assertEqual(platform["status_label"], "Senkron tamam")
        meta = next(p for p in response.context["platforms"] if p["code"] == "facebook")
        self.assertEqual(meta["status_label"], "Meta kotası bekleniyor")

    def test_newer_success_does_not_hide_another_accounts_failure_or_wait(self):
        second = PlatformAccount.objects.create(user=self.user, platform=self.meta,
            account_id="second", access_token="test")
        failure = PlatformSyncJob.objects.create(user=self.user, platform_account=self.account, status="failed")
        PlatformSyncJob.objects.create(user=self.user, platform_account=second, status="completed")
        self.client.force_login(self.user)
        response = self.client.get(reverse("sync_center"))
        platform = next(p for p in response.context["platforms"] if p["code"] == "facebook")
        self.assertEqual(platform["status"], "error")
        failure.status = "pending"
        failure.result = {"waiting_reason": "meta_rate_limit"}
        failure.save(update_fields=["status", "result"])
        response = self.client.get(reverse("sync_center"))
        platform = next(p for p in response.context["platforms"] if p["code"] == "facebook")
        self.assertEqual(platform["status_label"], "Meta kotası bekleniyor")
        # The account recovers: historical failures must no longer dominate.
        PlatformSyncJob.objects.create(user=self.user, platform_account=self.account, status="completed")
        response = self.client.get(reverse("sync_center"))
        platform = next(p for p in response.context["platforms"] if p["code"] == "facebook")
        self.assertEqual(platform["status"], "ok")

    def test_background_success_is_visible_without_a_manual_job(self):
        self.account.extra_data = {"ads_sync_summary": {"completed_at": timezone.now().isoformat()}}
        self.account.save(update_fields=["extra_data"])
        self.client.force_login(self.user)
        platform = next(p for p in self.client.get(reverse("sync_center")).context["platforms"]
                        if p["code"] == "facebook")
        self.assertEqual(platform["status_label"], "Senkron tamam")
        self.assertNotEqual(platform["last_sync_label"], "Henüz senkron yok")

    def test_background_recovery_replaces_old_failure_but_not_another_accounts_error(self):
        PlatformSyncJob.objects.create(user=self.user, platform_account=self.account, status="failed")
        self.account.extra_data = {"ads_sync_summary": {
            "completed_at": (timezone.now() + timedelta(seconds=1)).isoformat()}}
        self.account.save(update_fields=["extra_data"])
        self.client.force_login(self.user)
        platform = next(p for p in self.client.get(reverse("sync_center")).context["platforms"]
                        if p["code"] == "facebook")
        self.assertEqual(platform["status_label"], "Senkron tamam")
        second = PlatformAccount.objects.create(user=self.user, platform=self.meta, account_id="failed-second")
        PlatformSyncJob.objects.create(user=self.user, platform_account=second, status="failed")
        platform = next(p for p in self.client.get(reverse("sync_center")).context["platforms"]
                        if p["code"] == "facebook")
        self.assertEqual(platform["status"], "error")

    def test_organic_success_is_visible_and_plain_last_sync_is_not_proof(self):
        self.account.last_sync = timezone.now()
        self.account.extra_data = {"ads_sync_summary": {"completed_at": "invalid-date"}}
        self.account.save(update_fields=["last_sync", "extra_data"])
        self.client.force_login(self.user)
        platform = next(p for p in self.client.get(reverse("sync_center")).context["platforms"]
                        if p["code"] == "facebook")
        self.assertEqual(platform["status_label"], "Hazır")
        self.account.extra_data = {"organic_last_sync_at": timezone.now().isoformat()}
        self.account.save(update_fields=["extra_data"])
        platform = next(p for p in self.client.get(reverse("sync_center")).context["platforms"]
                        if p["code"] == "facebook")
        self.assertEqual(platform["status_label"], "Senkron tamam")
        PlatformSyncJob.objects.create(user=self.user, platform_account=self.account, status="pending",
                                      result={"waiting_reason": "meta_rate_limit"})
        platform = next(p for p in self.client.get(reverse("sync_center")).context["platforms"]
                        if p["code"] == "facebook")
        self.assertEqual(platform["status_label"], "Meta kotası bekleniyor")

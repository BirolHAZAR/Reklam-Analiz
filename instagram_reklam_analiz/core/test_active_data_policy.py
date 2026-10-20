from datetime import timedelta
from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import TestCase, SimpleTestCase
from django.utils import timezone

from core.models import (Platform, PlatformAccount, PlatformConnection, Campaign,
                         Ad, AdMetricHistory, SocialPost, SocialPostMetricHistory)
from core.services.ad_eligibility import is_current_campaign
from core.services.campaign_panel_service import build_campaign_list, metric_payload
from core.services.organic_content_service import organic_summary_for_user, sync_instagram_organic_content


class ActiveDatesTests(SimpleTestCase):
    def test_expired_future_paused_and_unknown_are_excluded(self):
        now = timezone.now()
        for row in ({"status": "PAUSED"}, {"status": "UNKNOWN"}, {},
                    {"status": "ACTIVE", "effective_status": "CAMPAIGN_PAUSED"},
                    {"status": "ACTIVE", "stop_time": (now-timedelta(seconds=1)).isoformat()},
                    {"status": "ACTIVE", "start_time": (now+timedelta(days=1)).isoformat()},
                    {"status": "ACTIVE", "end_date": "2026-02-30"},
                    {"status": "ACTIVE", "end_date": "not-a-date"},
                    {"status": "ENABLED", "end_date": str(now.date()-timedelta(days=1))}):
            with self.subTest(row=row):
                self.assertFalse(is_current_campaign(row, now=now))
        self.assertTrue(is_current_campaign({"status": "ACTIVE"}, now=now))

    def test_missing_measurement_differs_from_measured_zero(self):
        missing = metric_payload({"rows": 0}, "TRY")
        zero = metric_payload({"rows": 1, "spend": Decimal(0), "impressions": 0}, "TRY")
        self.assertFalse(missing["has_data"])
        self.assertIsNone(missing["spend"])
        self.assertEqual(missing["spend_label"], "—")
        self.assertTrue(zero["has_data"])
        self.assertEqual(zero["spend"], 0)

    @patch("core.instagram_api.InstagramAPI._request")
    def test_legacy_instagram_ad_read_filters_all_entity_levels(self, request):
        from core.instagram_api import InstagramAPI
        campaign = {"id": "10", "status": "ACTIVE"}
        group = {"id": "20", "status": "ACTIVE", "effective_status": "ACTIVE"}
        request.side_effect = [
            {"data": [campaign, {"id": "11", "status": "PAUSED"}]},
            {"data": [
                {"id": "30", "effective_status": "ACTIVE", "campaign": campaign, "adset": group},
                {"id": "31", "effective_status": "PAUSED", "campaign": campaign, "adset": group},
                {"id": "32", "effective_status": "ACTIVE", "campaign": campaign,
                 "adset": {**group, "effective_status": "PAUSED"}},
            ]},
            {"data": [{"ad_id": "30", "campaign_id": "10"}, {"ad_id": "31", "campaign_id": "10"}]},
        ]
        rows = InstagramAPI(access_token="fixture").get_ads_insights("act_123")["data"]
        self.assertEqual([row["ad_id"] for row in rows], ["30"])
        self.assertIn('"30"', request.call_args.args[1]["filtering"])
        self.assertNotIn('"31"', request.call_args.args[1]["filtering"])

    @patch("core.services.ads_integrations._request", return_value={"unexpected": []})
    def test_malformed_meta_inventory_is_not_treated_as_empty(self, request):
        from core.services.ads_integrations import meta_rows, IntegrationError
        with self.assertRaises(IntegrationError):
            meta_rows("fixture", "act_123/campaigns", {})


class ActiveSyncTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(username="active-policy-owner")
        self.platform, _ = Platform.objects.get_or_create(code="google_ads", defaults={"name": "Google Ads"})
        self.connection = PlatformConnection.objects.create(user=self.user, platform=self.platform,
            access_token="test-token", extra_data={"source": "ads_oauth"})
        self.account = PlatformAccount.objects.create(user=self.user, platform=self.platform,
            connection=self.connection, account_id="123", extra_data={"currency": "TRY", "timezone": "UTC"})

    def test_panel_excludes_expired_configured_active_and_retains_history(self):
        expired = Campaign.objects.create(user=self.user, platform_account=self.account,
            platform_campaign_id="old", name="Repeated name", status="ACTIVE",
            end_time=timezone.now()-timedelta(days=100))
        current = Campaign.objects.create(user=self.user, platform_account=self.account,
            platform_campaign_id="current", name="Repeated name", status="ACTIVE")
        self.assertEqual([c["id"] for c in build_campaign_list(self.user,self.account,status="ACTIVE")], [current.pk])
        self.assertEqual([c["id"] for c in build_campaign_list(self.user,self.account,status="INACTIVE")], [expired.pk])
        self.assertEqual(len(build_campaign_list(self.user,self.account)), 2)
        self.assertEqual(build_campaign_list(self.user,self.account,status="INACTIVE")[0]["status_label"], "Tamamlandı")

    def test_google_sync_does_not_store_campaign_or_ad_without_metrics(self):
        from core.tasks.v2_platform_sync import sync_v2_platform_account_ads
        old = Campaign.objects.create(user=self.user, platform_account=self.account,
            platform_campaign_id="999", name="Old", status="ACTIVE")
        active_campaign = {"id": "10", "name": "Active", "status": "ENABLED"}
        empty_campaign = {"id": "11", "name": "No ads", "status": "ENABLED"}
        paused_campaign = {"id": "12", "name": "Paused", "status": "PAUSED"}
        active_ad = {"campaign": active_campaign, "adGroup": {"id":"20","name":"Group","status":"ENABLED"},
            "adGroupAd": {"status":"ENABLED","ad":{"id":"30","name":"Ad"}}}
        paused_ad = {**active_ad, "adGroupAd":{"status":"PAUSED","ad":{"id":"31"}}}
        def search(token, account_id, query, manager=""):
            if "FROM campaign " in query:
                return [{"campaign": c} for c in (active_campaign, empty_campaign, paused_campaign)]
            if "segments.date" in query:
                return []
            return [active_ad, paused_ad]
        with patch("core.platforms.google_ads.account_token",return_value="test-token"), \
             patch("core.platforms.google_ads.google_search",side_effect=search), \
             patch("core.services.sync_policy.policy_for_user",return_value=SimpleNamespace(history_days=30,max_records=100)), \
             patch("core.tasks.admin_ops.generate_octo_tasks.apply_async"):
            sync_v2_platform_account_ads.run(self.account.pk,"OWN",30,retry_errors=False)
        self.assertFalse(Campaign.objects.exists())
        self.assertFalse(Ad.objects.exists())
        self.assertFalse(AdMetricHistory.objects.exists())
        self.assertFalse(Campaign.objects.filter(pk=old.pk).exists())

    def test_failed_inventory_cannot_mark_existing_campaign_inactive(self):
        from core.tasks.v2_platform_sync import sync_v2_platform_account_ads
        from core.services.ads_integrations import IntegrationError
        old = Campaign.objects.create(user=self.user,platform_account=self.account,
            platform_campaign_id="999",name="Existing",status="ACTIVE")
        with patch("core.platforms.google_ads.account_token",return_value="test-token"), \
             patch("core.platforms.google_ads.google_search",side_effect=IntegrationError("unavailable")), \
             patch("core.services.sync_policy.policy_for_user",return_value=SimpleNamespace(history_days=30,max_records=100)):
            with self.assertRaises(IntegrationError):
                sync_v2_platform_account_ads.run(self.account.pk,"OWN",30,retry_errors=False)
        old.refresh_from_db()
        self.assertTrue(old.is_active)


class RecentPostsTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(username="recent-post-owner")
        platform, _ = Platform.objects.get_or_create(code="instagram", defaults={"name":"Instagram"})
        self.account = PlatformAccount.objects.create(user=self.user,platform=platform,
            account_id="123",access_token="test-token",extra_data={"auth_type":"instagram_login"})

    def test_report_uses_latest_post_snapshot_and_preserves_unknown_metrics(self):
        post = SocialPost.objects.create(user=self.user,platform_account=self.account,platform_post_id="1")
        today = timezone.localdate()
        SocialPostMetricHistory.objects.create(social_post=post,date=today-timedelta(days=1),likes=4,engagement=4)
        SocialPostMetricHistory.objects.create(social_post=post,date=today,likes=5,engagement=5)
        summary = organic_summary_for_user(self.user,platform_accounts=[self.account])
        self.assertEqual(summary["likes"],5)
        self.assertEqual(summary["engagement"],5)
        self.assertIsNone(summary["reach"])

    def test_recent_posts_paginate_dedupe_and_update_one_daily_snapshot(self):
        now = timezone.now()
        media = lambda key,days:{"id":key,"timestamp":(now-timedelta(days=days)).isoformat(),
            "media_type":"IMAGE","like_count":5,"comments_count":1}
        pages = [{"data":[media("1",1),media("old",20)],"paging":{
                    "next":"https://untrusted.invalid/?access_token=secret","cursors":{"after":"cursor"}}},
                 {"data":[media("1",1),media("2",14),media("older",40)]}]
        def response(url,params):
            if url.endswith("/insights"):
                return {"data":[]}
            return pages[1] if "after" in params else pages[0]
        for _ in range(2):
            with patch("core.services.organic_content_service.InstagramAPI") as api:
                api.return_value.graph_url="https://graph.instagram.com/v25.0"
                api.return_value._request.side_effect=response
                result=sync_instagram_organic_content(self.account)
                self.assertTrue(result["success"])
                self.assertTrue(all(call.args[0].startswith("https://graph.instagram.com/v25.0/")
                                    for call in api.return_value._request.call_args_list))
        self.assertEqual(set(SocialPost.objects.values_list("platform_post_id",flat=True)),{"1","2"})
        self.assertEqual(SocialPostMetricHistory.objects.count(),2)
        self.assertEqual(organic_summary_for_user(self.user)["likes"],10)

    def test_daily_dispatch_skips_accounts_already_updated_today(self):
        from core.tasks.sync_tasks import sync_due_organic_accounts
        self.account.extra_data["organic_last_sync_at"]=timezone.now().isoformat()
        self.account.save(update_fields=["extra_data"])
        with patch("core.services.sync_policy.is_sync_due",return_value=True), \
             patch("core.tasks.sync_tasks.sync_organic_account.delay") as task:
            self.assertEqual(sync_due_organic_accounts.run()["queued"],0)
            task.assert_not_called()

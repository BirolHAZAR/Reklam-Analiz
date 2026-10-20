from copy import deepcopy
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import TestCase, RequestFactory
from django.utils import timezone

from core.models import Platform, PlatformAccount, PlatformConnection, SocialPost, SocialPostMetricHistory
from core.services.ads_integrations import IntegrationError
from core.services.organic_insights import summarize_snapshots
from core.services.tiktok_organic import sync_tiktok_organic_content


class TikTokOrganicTests(TestCase):
    def setUp(self):
        user = get_user_model().objects.create_user(username="tik-organic")
        platform = Platform.objects.create(code="tiktok", name="TikTok")
        connection = PlatformConnection.objects.create(user=user, platform=platform,
            extra_data={"source": "tiktok_oauth"})
        self.account = PlatformAccount.objects.create(user=user, platform=platform,
            connection=connection, account_id="subject")
        self.video = {"id": "100", "create_time": int(timezone.now().timestamp()) - 10,
                      "view_count": 30, "like_count": 4, "comment_count": 2, "share_count": 1,
                      "video_description": "Real video"}

    def sync(self, pages, **kwargs):
        with patch("core.services.tiktok_organic.tiktok_oauth.access_token", return_value="private"), \
             patch("core.services.tiktok_organic.tiktok_oauth.videos", side_effect=pages):
            return sync_tiktok_organic_content(self.account, **kwargs)

    def test_paginated_import_and_same_day_update_are_idempotent(self):
        result = self.sync([([self.video], 123), ([{**self.video, "id": "101"}], None)])
        self.assertEqual(result["created"], 2)
        self.assertEqual(SocialPostMetricHistory.objects.count(), 2)
        self.sync([([{**self.video, "view_count": 40}], None)])
        self.assertEqual(SocialPost.objects.count(), 2)
        self.assertEqual(SocialPostMetricHistory.objects.count(), 2)
        metric = SocialPostMetricHistory.objects.get(social_post__platform_post_id="100")
        self.assertEqual(metric.video_views, 40)
        totals = summarize_snapshots([metric])
        self.assertEqual(totals["engagement"], 7)
        self.assertEqual(totals["views"], 40)
        self.assertIsNone(totals["reach"])
        self.assertIsNone(totals["impressions"])
        self.assertIsNone(totals["saves"])

    def test_measured_zero_is_valid_but_missing_counters_write_nothing(self):
        for value in (None, -1, True, "0"):
            result = self.sync([([{**self.video, "view_count": value}], None)])
            self.assertFalse(result["success"])
            self.assertFalse(SocialPost.objects.exists())
        zero = {**self.video, **{key: 0 for key in ("view_count", "like_count", "comment_count", "share_count")}}
        self.assertTrue(self.sync([([zero], None)])["success"])
        self.assertEqual(SocialPostMetricHistory.objects.get().video_views, 0)

    def test_failed_second_page_does_not_leave_partial_data(self):
        result = self.sync([([self.video], 123), IntegrationError("TikTok unavailable")])
        self.assertFalse(result["success"])
        self.assertFalse(SocialPost.objects.exists())
        self.account.refresh_from_db()
        self.assertNotIn("organic_last_sync_at", self.account.extra_data)

    def test_duplicate_cursor_duplicate_id_and_limit_fail_before_writes(self):
        cases = [([([self.video], 123), ([{**self.video, "id": "101"}], 123)], {}),
                 ([([self.video, deepcopy(self.video)], None)], {}),
                 ([([self.video, {**self.video, "id": "101"}], None)], {"limit": 1})]
        for pages, options in cases:
            self.assertFalse(self.sync(pages, **options)["success"])
            self.assertFalse(SocialPost.objects.exists())

    def test_empty_account_creates_no_posts_or_metrics(self):
        result = self.sync([([], None)])
        self.assertTrue(result["success"])
        self.assertEqual(result["metrics"], 0)
        self.assertFalse(SocialPost.objects.exists())
        self.assertFalse(SocialPostMetricHistory.objects.exists())

    def test_shared_center_lists_tiktok_snapshot_and_hides_ads_account(self):
        from core.views.social_content import organic_content_center, _scoped_platform_accounts
        self.sync([([self.video], None)])
        ads_connection = PlatformConnection.objects.create(user=self.account.user, platform=self.account.platform,
            extra_data={"source": "tiktok_ads_oauth"})
        ads_account = PlatformAccount.objects.create(user=self.account.user, platform=self.account.platform,
            connection=ads_connection, account_id="advertiser")
        request = RequestFactory().get("/organic-content/")
        request.user, request.session = self.account.user, {}
        with patch("core.views.social_content.CacheService.get", return_value=None), \
             patch("core.views.social_content.CacheService.set"), \
             patch("core.views.social_content.render") as render:
            organic_content_center(request)
        context = render.call_args.args[2]
        self.assertEqual(context["posts"][0].platform_post_id, self.video["id"])
        self.assertEqual(context["stats"]["views"], 30)
        self.assertEqual(context["stats"]["shares"], 1)
        self.assertIsNone(context["stats"]["reach"])
        self.assertNotIn(ads_account.pk, _scoped_platform_accounts(request).values_list("pk", flat=True))

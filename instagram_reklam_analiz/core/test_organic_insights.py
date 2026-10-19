from datetime import timedelta
from types import SimpleNamespace
from unittest.mock import Mock, patch

from django.contrib.auth import get_user_model
from django.test import TestCase, SimpleTestCase, RequestFactory
from django.utils import timezone

from core.models import Platform, PlatformAccount, PlatformConnection, SocialPost, SocialPostMetricHistory
from core.services.organic_insights import fetch_media_insights, summarize_snapshots
from core.services.organic_content_service import sync_instagram_organic_content
from core.views.social_content import organic_content_center


class MediaInsightsTests(SimpleTestCase):
    def test_reads_zero_and_total_value_without_fabricating_missing_values(self):
        api = Mock(graph_url="https://graph.instagram.com/v25.0")
        api._request.return_value = {"data": [
            {"name": "views", "values": [{"value": 0}]},
            {"name": "reach", "total_value": {"value": 12}},
            {"name": "saved", "values": []},
        ]}
        values, status = fetch_media_insights(api, {"id": "123", "media_product_type": "FEED"})
        self.assertEqual(values, {"views": 0, "reach": 12})
        self.assertEqual(status, "available")
        self.assertEqual(api._request.call_args.args[0], "https://graph.instagram.com/v25.0/123/insights")
        self.assertNotIn("impressions", api._request.call_args.args[1]["metric"])

    def test_error_and_empty_response_remain_distinct_from_measured_zero(self):
        for response, expected in (({"error": "secret"}, "unavailable"), ({"data": []}, "empty")):
            api = Mock(graph_url="https://graph.instagram.com/v25.0")
            api._request.return_value = response
            self.assertEqual(fetch_media_insights(api, {"id": "123"}), ({}, expected))

    def test_story_does_not_request_saved(self):
        api = Mock(graph_url="https://graph.instagram.com/v25.0")
        api._request.return_value = {"data": []}
        fetch_media_insights(api, {"id": "123", "media_product_type": "STORY"})
        self.assertNotIn("saved", api._request.call_args.args[1]["metric"])


class OrganicInsightsIntegrationTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(username="organic-owner")
        platform = Platform.objects.create(code="instagram", name="Instagram")
        self.connection = PlatformConnection.objects.create(user=self.user, platform=platform,
            access_token="test-token", scopes=["instagram_business_basic", "instagram_business_manage_insights"])
        self.account = PlatformAccount.objects.create(user=self.user, platform=platform,
            connection=self.connection, account_id="123", access_token="test-token",
            extra_data={"auth_type": "instagram_login"})
        self.media = {"id": "456", "media_type": "IMAGE", "media_product_type": "FEED",
                      "like_count": 4, "comments_count": 1, "timestamp": timezone.now().isoformat()}

    def sync(self, insights):
        with patch("core.services.organic_content_service.InstagramAPI") as api:
            api.return_value.graph_url = "https://graph.instagram.com/v25.0"
            api.return_value._request.side_effect = [{"data": [self.media]}, insights]
            return sync_instagram_organic_content(self.account)

    def test_sync_stores_real_insights_and_ratio(self):
        result = self.sync({"data": [
            {"name": name, "values": [{"value": value}]} for name, value in
            (("views", 40), ("reach", 20), ("total_interactions", 7), ("shares", 1), ("saved", 1))
        ]})
        self.assertTrue(result["success"])
        row = SocialPostMetricHistory.objects.get()
        self.assertEqual(row.engagement, 7)
        self.assertEqual(row.engagement_rate, 35)
        summary = summarize_snapshots([row])
        self.assertEqual(summary["views"], 40)
        self.assertEqual(summary["avg_engagement_rate"], 35)
        self.assertIsNone(summary["impressions"])
        self.assertIsNone(summary["profile_visits"])

    def test_unavailable_insights_still_syncs_media_without_fake_500_percent(self):
        self.sync({"error": "permission denied test-token"})
        row = SocialPostMetricHistory.objects.get()
        summary = summarize_snapshots([row])
        self.assertEqual(summary["engagement"], 5)
        self.assertIsNone(summary["avg_engagement_rate"])
        self.assertIsNone(summary["reach"])
        self.assertIsNone(summary["shares"])
        self.assertNotIn("test-token", str(row.raw_metrics))

    def test_measured_zero_is_preserved(self):
        self.sync({"data": [{"name": "reach", "values": [{"value": 0}]}]})
        summary = summarize_snapshots(SocialPostMetricHistory.objects.all())
        self.assertEqual(summary["reach"], 0)
        self.assertIsNone(summary["avg_engagement_rate"])

    def test_center_uses_latest_lifetime_snapshot_not_sum_of_daily_snapshots(self):
        self.sync({"error": "unavailable"})
        row = SocialPostMetricHistory.objects.get()
        SocialPostMetricHistory.objects.create(social_post=row.social_post,
            date=timezone.localdate() - timedelta(days=1), likes=3, engagement=3)
        request = RequestFactory().get("/organic-content/")
        request.user = self.user
        request.session = {}
        with patch("core.views.social_content.CacheService.get", return_value=None), \
             patch("core.views.social_content.CacheService.set"), \
             patch("core.views.social_content.render") as render:
            organic_content_center(request)
        context = render.call_args.args[2]
        self.assertEqual(context["stats"]["engagement"], 5)
        self.assertIsNone(context["stats"]["avg_engagement_rate"])
        self.assertEqual(context["posts"][0].organic_metrics["engagement"], 5)
        from django.template.loader import render_to_string
        html = render_to_string("social_content/organic_content_center.html", context, request=request)
        self.assertIn("Veri yok", html)
        self.assertNotIn("%500", html)

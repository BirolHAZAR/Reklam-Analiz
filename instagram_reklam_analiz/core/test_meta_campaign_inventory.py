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
        self.ads = [{"id": "a1", "name": "New ad", "effective_status": "ACTIVE",
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
            self.assertNotIn("time_range", params)
            statuses = json.loads(params["effective_status"])
            self.assertEqual(statuses, ["ACTIVE"])
            self.assertIn("filtering", params)
            return self.ads
        if path.endswith("/campaigns"):
            self.assertNotIn("filtering", params)
            self.assertNotIn("time_range", params)
            statuses = json.loads(params["effective_status"])
            self.assertEqual(statuses, ["ACTIVE"])
            return self.campaigns
        self.assertEqual(path, "act_123/insights")
        self.assertEqual(params["time_increment"], 1)
        period = json.loads(params["time_range"])
        return [row for row in self.insights if period["since"] <= row["date_start"] <= period["until"]]

    def sync(self):
        from core.tasks.v2_platform_sync import sync_v2_platform_account_ads
        with patch("core.platforms.facebook.account_token", return_value="test-token"), \
             patch("core.platforms.facebook.meta_rows", side_effect=self.rows), \
             patch("core.platforms.facebook.account_today", return_value=date(2026, 10, 9)), \
             patch("core.services.sync_policy.policy_for_user", return_value=SimpleNamespace(history_days=365, max_records=100)), \
             patch("core.tasks.admin_ops.generate_octo_tasks.apply_async"):
            return sync_v2_platform_account_ads.run(self.account.id, "OWN", 365)

    def test_only_active_entities_are_imported_without_fabricating_metrics(self):
        self.sync()
        self.assertEqual(Campaign.objects.filter(platform_account=self.account).count(), 1)
        self.assertEqual(Ad.objects.filter(platform_account=self.account).count(), 1)
        self.assertEqual(Ad.objects.get(platform_ad_id="a1").ad_group.lifetime_budget, Decimal("60"))
        self.assertFalse(AdMetricHistory.objects.exists())
        self.assertFalse(CampaignMetricHistory.objects.exists())
        # Dates select metrics; they must not hide paused/empty campaigns.
        cards = build_campaign_list(self.user, self.account, date(2020, 1, 1), date(2020, 1, 2))
        self.assertEqual({card["platform_campaign_id"] for card in cards}, {"c1"})

    def test_yearly_insights_windows_cover_every_day_once(self):
        from datetime import timedelta
        with patch("core.platforms.facebook.meta_rows", side_effect=self.rows) as request, \
             patch("core.platforms.facebook.account_today", return_value=date(2026, 10, 9)):
            FacebookAPI(self.account).get_ads(since_days=365)
        periods = [json.loads(call.args[2]["time_range"]) for call in request.call_args_list
                   if call.args[1].endswith("/insights")]
        self.assertEqual(len(periods), 13)
        days = []
        for period in periods:
            start, end = date.fromisoformat(period["since"]), date.fromisoformat(period["until"])
            self.assertLessEqual((end - start).days, 29)
            days.extend(start + timedelta(days=offset) for offset in range((end - start).days + 1))
        self.assertEqual(days, [date(2026, 10, 9) - timedelta(days=364-offset) for offset in range(365)])

    def test_slow_insights_window_splits_without_losing_or_duplicating_dates(self):
        from core.services.ads_integrations import IntegrationTransportError
        periods = []
        def read(token, path, params):
            if path.endswith("/campaigns"):
                return self.campaigns
            if path.endswith("/ads"):
                return self.ads
            period = json.loads(params["time_range"])
            start, end = date.fromisoformat(period["since"]), date.fromisoformat(period["until"])
            if (end - start).days > 14:
                raise IntegrationTransportError("slow", is_timeout=True)
            periods.append((start, end))
            return [{"ad_id": "a1", "campaign_id": "c1", "adset_id": "s1", "date_start": start.isoformat()}]
        with patch("core.platforms.facebook.meta_rows", side_effect=read), \
             patch("core.platforms.facebook.account_today", return_value=date(2026, 10, 9)):
            rows = FacebookAPI(self.account).get_ads(since_days=30)
        self.assertEqual(periods, [(date(2026, 9, 10), date(2026, 9, 24)),
                                   (date(2026, 9, 25), date(2026, 10, 9))])
        self.assertEqual(len(rows), 3)

    def test_connection_failure_does_not_fan_out_into_smaller_requests(self):
        from core.services.ads_integrations import IntegrationTransportError
        with patch("core.platforms.facebook.meta_rows", side_effect=[self.campaigns, self.ads, IntegrationTransportError("offline")]) as request:
            with self.assertRaises(IntegrationTransportError):
                FacebookAPI(self.account).get_ads(since_days=30)
        self.assertEqual(request.call_count, 3)

    def test_daily_history_is_idempotent_and_metadata_sync_does_not_erase_it(self):
        self.insights = [{"ad_id": "a1", "campaign_id": "c1", "adset_id": "s1", "ad_name": "New ad",
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
        self.assertEqual(Campaign.objects.get(platform_campaign_id="c1").status, "ACTIVE")

    def test_inactive_ad_insights_are_not_imported(self):
        self.insights = [{"ad_id": "deleted-ad", "campaign_id": "old-c", "adset_id": "old-s",
            "date_start": "2026-09-01", "spend": "7", "impressions": "30"}]
        self.sync()
        self.assertFalse(AdMetricHistory.objects.exists())

    def test_campaign_status_filter_has_separate_cache_and_keeps_history(self):
        for cid in ("c2", "c3"):
            Campaign.objects.create(user=self.user, platform_account=self.account,
                platform_campaign_id=cid, name=cid, status="PAUSED")
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
        request.assert_called_once_with(args=(self.account.id, "OWN", 30),
            kwargs={"retry_errors": False, "retry_context": f"manual:{job.id}"}, throw=True)
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

    def test_rate_limit_has_one_retry_owner_and_keeps_job_pending(self):
        from celery.exceptions import Retry
        from core.services.meta_rate_limit import MetaRateLimitError
        from core.tasks.ads_pipeline import sync_platform_account_ads
        for delay, expected in [(54, 300), (600, 600)]:
            with self.subTest(delay=delay):
                job = PlatformSyncJob.objects.create(user=self.user, platform_account=self.account)
                error = MetaRateLimitError(delay)
                with patch("core.tasks.v2_platform_sync.sync_v2_platform_account_ads.apply", side_effect=error), \
                     patch.object(sync_platform_account_ads, "retry", side_effect=Retry()) as retry:
                    with self.assertRaises(Retry):
                        sync_platform_account_ads.run(job.pk)
                retry.assert_called_once_with(exc=error, countdown=expected, max_retries=48)
                job.refresh_from_db()
                self.assertEqual(job.status, "pending")
                self.assertEqual(job.error_message, "")
                self.assertIsNone(job.finished_at)
                self.assertEqual(job.result["waiting_reason"], "meta_rate_limit")
                self.assertEqual(job.result["retry_after"], expected)

    def test_large_inventory_quota_wait_continues_after_three_attempts(self):
        from celery.exceptions import Retry
        from core.services.meta_rate_limit import MetaRateLimitError
        from core.tasks.ads_pipeline import sync_platform_account_ads
        job = PlatformSyncJob.objects.create(user=self.user, platform_account=self.account)
        error = MetaRateLimitError(60)
        sync_platform_account_ads.push_request(retries=3)
        try:
            with patch("core.tasks.v2_platform_sync.sync_v2_platform_account_ads.apply", side_effect=error), \
                 patch.object(sync_platform_account_ads, "retry", side_effect=Retry()) as retry:
                with self.assertRaises(Retry):
                    sync_platform_account_ads.run(job.pk)
        finally:
            sync_platform_account_ads.pop_request()
        retry.assert_called_once_with(exc=error, countdown=300, max_retries=48)
        job.refresh_from_db()
        self.assertEqual(job.status, "pending")

    def test_provider_error_propagates_without_inner_retry_when_pipeline_owns_retry(self):
        from core.services.meta_rate_limit import MetaRateLimitError
        from core.tasks.v2_platform_sync import sync_v2_platform_account_ads
        error = MetaRateLimitError(54)
        with patch("core.services.sync_policy.policy_for_user", return_value=SimpleNamespace(history_days=30, max_records=100)), \
             patch("core.tasks.v2_platform_sync._get_api_class") as api, \
             patch.object(sync_v2_platform_account_ads, "retry") as retry:
            api.return_value.return_value.get_ads.side_effect = error
            with self.assertRaises(MetaRateLimitError):
                sync_v2_platform_account_ads.run(self.account.pk, retry_errors=False)
        retry.assert_not_called()

    def test_transport_failure_after_quota_waits_has_separate_bounded_retries(self):
        from celery.exceptions import Retry
        from core.services.ads_integrations import IntegrationTransportError
        from core.tasks.ads_pipeline import sync_platform_account_ads
        job = PlatformSyncJob.objects.create(user=self.user, platform_account=self.account,
            result={"waiting_reason": "meta_rate_limit"})
        error = IntegrationTransportError("Temporary provider failure")
        for attempt in range(4):
            sync_platform_account_ads.push_request(retries=5 + attempt)
            try:
                with patch("core.tasks.v2_platform_sync.sync_v2_platform_account_ads.apply", side_effect=error), \
                     patch.object(sync_platform_account_ads, "retry", side_effect=Retry()) as retry:
                    with self.assertRaises(IntegrationTransportError if attempt == 3 else Retry):
                        sync_platform_account_ads.run(job.pk)
            finally:
                sync_platform_account_ads.pop_request()
            job.refresh_from_db()
            if attempt < 3:
                retry.assert_called_once_with(exc=error, countdown=60, max_retries=6 + attempt)
                self.assertEqual(job.status, "pending")
                self.assertIsNone(job.finished_at)
                self.assertEqual(job.error_message, "")
                self.assertEqual(job.result["transport_retries"], attempt + 1)
                self.assertEqual(job.result["waiting_reason"], "provider_transport")
            else:
                retry.assert_not_called()
                self.assertEqual(job.status, "failed")
                self.assertNotIn("waiting_reason", job.result)

    def test_transport_retries_do_not_consume_meta_quota_budget(self):
        from celery.exceptions import Retry
        from core.services.meta_rate_limit import MetaRateLimitError
        from core.tasks.ads_pipeline import sync_platform_account_ads
        job = PlatformSyncJob.objects.create(user=self.user, platform_account=self.account,
            result={"transport_retries": 3})
        error = MetaRateLimitError(60)
        for retries, expected_status in [(50, "pending"), (51, "failed")]:
            sync_platform_account_ads.push_request(retries=retries)
            try:
                with patch("core.tasks.v2_platform_sync.sync_v2_platform_account_ads.apply", side_effect=error), \
                     patch.object(sync_platform_account_ads, "retry", side_effect=Retry()) as retry:
                    with self.assertRaises(Retry if retries == 50 else MetaRateLimitError):
                        sync_platform_account_ads.run(job.pk)
            finally:
                sync_platform_account_ads.pop_request()
            job.refresh_from_db()
            self.assertEqual(job.status, expected_status)
            if retries == 50:
                retry.assert_called_once_with(exc=error, countdown=300, max_retries=51)
            else:
                retry.assert_not_called()
                self.assertNotIn("waiting_reason", job.result)

    def test_instagram_rate_response_propagates_to_pipeline_without_inner_retry(self):
        from core.services.meta_rate_limit import MetaRateLimitError
        from core.tasks.v2_platform_sync import sync_v2_platform_account_ads
        instagram, _ = Platform.objects.get_or_create(code="instagram", defaults={"name": "Instagram"})
        self.account.platform = instagram
        self.account.access_token = "fixture-instagram-access-token"
        self.account.save(update_fields=["platform", "access_token"])
        with patch("core.services.sync_policy.policy_for_user", return_value=SimpleNamespace(history_days=30, max_records=100)), \
             patch("core.instagram_api.InstagramAPI.get_ads_insights", return_value={"error": "rate", "status_code": 429, "retry_after": 54}), \
             patch.object(sync_v2_platform_account_ads, "retry") as retry:
            with self.assertRaises(MetaRateLimitError) as error:
                sync_v2_platform_account_ads.run(self.account.pk, retry_errors=False)
        self.assertEqual(error.exception.retry_after, 54)
        retry.assert_not_called()

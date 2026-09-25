from datetime import date, timedelta
from decimal import Decimal
from unittest.mock import patch

from django.conf import settings
from django.test import TestCase, override_settings
from django.utils import timezone

from core.models import (
    Ad, AdMetricHistory, Campaign, CampaignMetricHistory, Creative,
    CreativeMetricHistory, Platform, PlatformAccount, PlatformConnection,
    ScheduledReport, User,
)
from core.services.demo_metrics import refresh_demo_metrics_for_date
from core.tasks.sync_tasks import sync_due_organic_accounts, sync_organic_account


class DemoBackgroundTests(TestCase):
    def setUp(self):
        self.demo = User.objects.create_user(username="demo")
        self.real = User.objects.create_user(username="real-background")
        self.platform = Platform.objects.create(code="instagram", name="Instagram")
        self.connection = PlatformConnection.objects.create(user=self.demo, platform=self.platform)
        self.account = PlatformAccount.objects.create(
            user=self.demo, platform=self.platform, connection=self.connection,
            account_id="demo-no-token", is_active=True,
        )

    def test_demo_organic_never_checks_policy_or_calls_api(self):
        with patch("core.services.sync_policy.policy_for_user") as policy, patch(
            "core.services.organic_content_service.sync_instagram_organic_content"
        ) as sync:
            self.assertEqual(sync_organic_account.run(self.account.pk)["reason"], "demo_metrics_only")
        policy.assert_not_called()
        sync.assert_not_called()

    def test_organic_dispatch_excludes_demo_but_keeps_real_accounts(self):
        account = PlatformAccount.objects.create(user=self.real, platform=self.platform, account_id="real")
        with patch("core.services.sync_policy.is_sync_due", return_value=True), patch(
            "core.services.sync_policy.acquire_sync_lock", return_value=("key", True)
        ), patch("core.tasks.sync_tasks.sync_organic_account.delay") as delay:
            sync_due_organic_accounts.run()
        delay.assert_called_once_with(account.pk)

    @override_settings(INSTAGRAM_ACCESS_TOKEN="", META_AD_LIBRARY_ACCESS_TOKEN="")
    def test_token_check_ignores_demo_and_checks_real_connection(self):
        from core.services.platform_token_service import check_and_refresh_platform_tokens
        real_connection = PlatformConnection.objects.create(user=self.real, platform=self.platform)
        with patch("core.services.platform_token_service._validate_connection", return_value={"valid": True}) as validate:
            result = check_and_refresh_platform_tokens()
        self.assertEqual(result["checked"], 1)
        self.assertEqual(validate.call_args.args[0].pk, real_connection.pk)
        self.connection.refresh_from_db()
        self.assertNotIn("token_health_checked_at", self.connection.extra_data)

    def test_demo_marker_on_connection_protects_other_owners_account(self):
        from core.tasks.v2_platform_sync import _should_skip_ad_sync
        self.connection.user = self.real
        self.connection.extra_data = {"demo": True}
        self.connection.save()
        self.account.user = self.real
        self.account.save()
        self.account.refresh_from_db()
        self.assertEqual(_should_skip_ad_sync(self.account, "instagram"), "demo_account")

    def test_demo_refresh_keeps_octo_and_has_one_schedule(self):
        from core.tasks.metric_tasks import refresh_daily_demo_metrics
        with patch("core.services.demo_metrics.refresh_demo_metrics_for_date", return_value={"success": True}), patch(
            "core.tasks.admin_ops.dispatch_octo_rule_engine_sweep.apply_async"
        ) as dispatch:
            refresh_daily_demo_metrics.run()
        dispatch.assert_called_once()
        self.assertNotIn("core.tasks.metric_tasks.refresh_daily_demo_metrics", [
            entry["task"] for entry in settings.CELERY_BEAT_SCHEDULE.values()
        ])

    def test_scheduled_reports_dispatch_demo_and_real_users(self):
        from core.tasks.report_tasks import dispatch_due_scheduled_reports, send_scheduled_report
        reports = [ScheduledReport.objects.create(user=user, name="Report", next_run_at=timezone.now()-timedelta(hours=1))
                   for user in (self.demo, self.real)]
        with patch("core.tasks.report_tasks.send_scheduled_report.delay") as delay:
            dispatch_due_scheduled_reports.run()
        self.assertEqual(delay.call_count, 2)
        self.assertEqual({call.args[0] for call in delay.call_args_list}, {report.pk for report in reports})
        with patch("core.services.scheduled_reports.send_scheduled_report", return_value={"sent": 1}) as send:
            result = send_scheduled_report.run(reports[0].pk)
        send.assert_called_once()
        self.assertTrue(result["success"])

    def test_metrics_are_independent_consistent_and_idempotent(self):
        campaign = Campaign.objects.create(user=self.demo, name="Demo campaign")
        creative = Creative.objects.create(user=self.demo)
        ads = [Ad.objects.create(user=self.demo, campaign=campaign, creative=creative, name=str(i)) for i in range(3)]
        real_ad = Ad.objects.create(user=self.real, name="Real ad")
        day = date(2026, 9, 25)
        with patch("core.services.demo_metrics._create_daily_demo_signal", return_value={"alerts": 0, "notifications": 0}):
            refresh_demo_metrics_for_date(day)
            first = list(AdMetricHistory.objects.filter(date=day).order_by("ad_id").values("ad_id", "impressions", "clicks", "spend"))
            refresh_demo_metrics_for_date(day)
            self.assertEqual(first, list(AdMetricHistory.objects.filter(date=day).order_by("ad_id").values("ad_id", "impressions", "clicks", "spend")))
            refresh_demo_metrics_for_date(day+timedelta(days=1))
        self.assertEqual(len({row["impressions"] for row in first}), 3)
        self.assertFalse(AdMetricHistory.objects.filter(ad=real_ad).exists())
        rows = list(AdMetricHistory.objects.filter(date=day))
        for row in AdMetricHistory.objects.all():
            self.assertLessEqual(row.reach, row.impressions)
            self.assertLessEqual(row.link_clicks, row.clicks)
            self.assertLessEqual(row.landing_page_views, row.link_clicks)
            self.assertLessEqual(row.conversions, row.clicks)
            self.assertLessEqual(row.purchases, row.initiate_checkout)
            self.assertLessEqual(row.initiate_checkout, row.add_to_cart)
            self.assertAlmostEqual(row.ctr, Decimal(row.clicks)*100/row.impressions, places=3)
        total = sum(row.spend for row in rows)
        self.assertEqual(CampaignMetricHistory.objects.get(campaign=campaign, date=day).spend, total)
        self.assertEqual(CreativeMetricHistory.objects.get(creative=creative, date=day).spend, total)

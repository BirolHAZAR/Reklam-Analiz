import os
from datetime import timedelta
from decimal import Decimal
from pathlib import Path
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import SimpleTestCase, TestCase
from django.urls import reverse
from django.utils import timezone

from core.models import Platform, PlatformAccount, PlatformConnection
from core.services.ads_integrations import IntegrationError, campaign_summaries
from core.services.campaign_reporting import decorate_campaign, summarize_metrics


class CampaignPresentationTests(SimpleTestCase):
    def test_enabled_campaign_past_end_is_completed_while_switch_stays_active(self):
        now = timezone.now()
        row = decorate_campaign({"status": "ACTIVE", "stop_time": (now-timedelta(days=1)).isoformat()}, now=now)
        self.assertEqual(row["status_label"], "Tamamlandı")
        self.assertEqual(row["status_group"], "inactive")
        self.assertEqual(row["configured_status_label"], "Aktif")

    def test_active_paused_future_and_unknown_are_not_confused(self):
        now = timezone.now()
        for status, expected in (("ACTIVE", "Aktif"), ("ENABLED", "Aktif"),
                                 ("PAUSED", "Duraklatıldı"), ("OTHER", "Durum bilinmiyor")):
            self.assertEqual(decorate_campaign({"status": status}, now=now)["status_label"], expected)
        self.assertEqual(decorate_campaign({"status": "ACTIVE", "start_time": (now+timedelta(days=1)).isoformat()}, now=now)["status_label"], "Planlandı")

    def test_totals_compute_weighted_rates_and_preserve_measured_zero(self):
        summary = summarize_metrics([{"impressions": 100, "clicks": 10, "spend": "2"},
                                     {"impressions": 900, "clicks": 0, "spend": "3"}])
        self.assertEqual(summary["ctr"], 1)
        self.assertEqual(summary["cpc"], Decimal("0.5"))
        self.assertEqual(summarize_metrics([{"impressions": 10}])["ctr"], 0)
        self.assertIsNone(summarize_metrics([{}])["cpc"])
        self.assertIsNone(summarize_metrics([]))


class CampaignReportingViewsTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(username="report-owner")
        self.client.force_login(self.user)
        platform = Platform.objects.create(code="facebook", name="Meta Ads")
        connection = PlatformConnection.objects.create(user=self.user, platform=platform,
            access_token="private-access", extra_data={"source": "ads_oauth"})
        self.account = PlatformAccount.objects.create(user=self.user, platform=platform, connection=connection,
            account_id="act_123", account_name="Birol Hazar", access_token="private-access",
            extra_data={"currency": "TRY", "timezone": "Europe/Istanbul"})
        now = timezone.now()
        self.rows = [
            {"id": "99", "name": "ReklamAnaliz | Web Sitesi Tanıtımı", "status": "ACTIVE",
             "objective": "OUTCOME_TRAFFIC", "start_time": (now-timedelta(days=3)).isoformat(),
             "stop_time": (now-timedelta(days=2)).isoformat()},
            {"id": "100", "name": "Marka Bilinirliği", "status": "ACTIVE", "objective": "OUTCOME_AWARENESS"},
            {"id": "101", "name": "Yeni Müşteriler", "status": "PAUSED", "objective": "OUTCOME_LEADS"},
        ]

    def preview(self, response, name):
        destination = os.environ.get("CAMPAIGN_PREVIEW_DIR")
        if destination:
            root = Path(destination)
            root.mkdir(parents=True, exist_ok=True)
            html = response.content.decode().replace('/static/', 'http://127.0.0.1:8000/static/')
            (root / name).write_text(html, encoding="utf-8")

    def test_account_picker_never_shows_other_users_accounts(self):
        other = get_user_model().objects.create_user(username="another-owner")
        hidden = PlatformAccount.objects.create(user=other, platform=self.account.platform, account_id="hidden-account")
        response = self.client.get(reverse("integration_campaign_browser"))
        self.assertContains(response, "Bir reklam hesabı seçerek başla")
        self.assertContains(response, "Kampanya Performansı")
        self.assertNotContains(response, "hidden-account")
        response = self.client.get(reverse("integration_campaign_browser"), {"account": hidden.pk})
        self.assertEqual(response.status_code, 404)

    def test_list_shows_states_real_metrics_and_weighted_summary_in_one_call(self):
        with patch("core.services.ads_integrations.campaigns", return_value=self.rows), \
             patch("core.services.ads_integrations.campaign_summaries", return_value={
                 "99": {"impressions": 2209, "clicks": 129, "spend": "59.63"},
                 "100": {"impressions": 0, "clicks": 0, "spend": "0"},
             }) as summaries:
            response = self.client.get(reverse("integration_campaigns", args=[self.account.pk]))
        self.assertContains(response, "Tamamlandı")
        self.assertContains(response, "Duraklatıldı")
        self.assertContains(response, "Trafik")
        self.assertContains(response, "59,63")
        self.assertNotContains(response, "private-access")
        self.assertEqual(response.context["summary"]["impressions"], 2209)
        self.assertEqual(response.context["active_campaigns"], 1)
        self.assertIsNone(response.context["campaigns"][2]["performance"])
        summaries.assert_called_once()
        self.preview(response, "campaign-list.html")

    def test_search_and_status_filter_summary_match_visible_campaigns(self):
        with patch("core.services.ads_integrations.campaigns", return_value=self.rows), \
             patch("core.services.ads_integrations.campaign_summaries", return_value={
                 "99": {"impressions": 2209, "clicks": 129, "spend": "59.63"},
                 "100": {"impressions": 100, "clicks": 1, "spend": "1"},
             }):
            response = self.client.get(reverse("integration_campaigns", args=[self.account.pk]),
                                       {"status": "inactive", "q": "Web Sitesi"})
        self.assertEqual([row["id"] for row in response.context["campaigns"]], ["99"])
        self.assertEqual(response.context["summary"]["spend"], Decimal("59.63"))

    def test_invalid_dates_do_not_send_provider_requests(self):
        with patch("core.services.ads_integrations.campaigns") as campaigns:
            for start, end in (("bad", "2026-10-12"), ("2026-02-30", "2026-10-12"), ("2026-10-12", "2026-10-01"), ("2024-01-01", "2026-01-01")):
                response = self.client.get(reverse("integration_campaigns", args=[self.account.pk]), {"start": start, "end": end})
                self.assertContains(response, "tarihini kontrol edin")
        campaigns.assert_not_called()

    def test_metrics_error_keeps_campaign_list_without_false_zero(self):
        with patch("core.services.ads_integrations.campaigns", return_value=self.rows), \
             patch("core.services.ads_integrations.campaign_summaries", side_effect=IntegrationError("API erişimi reddedildi")):
            response = self.client.get(reverse("integration_campaigns", args=[self.account.pk]))
        self.assertContains(response, "performans verileri alınamadı")
        self.assertContains(response, "ReklamAnaliz | Web Sitesi Tanıtımı")
        self.assertIsNone(response.context["summary"])

    def test_detail_preserves_dates_and_computes_totals(self):
        with patch("core.services.ads_integrations.campaigns", return_value=self.rows), \
             patch("core.services.ads_integrations.campaign_performance", return_value=[
                 {"date": "2026-10-09", "impressions": 1526, "clicks": 90, "spend": Decimal("31.84")},
                 {"date": "2026-10-10", "impressions": 683, "clicks": 39, "spend": Decimal("27.79")},
             ]) as performance:
            response = self.client.get(reverse("integration_campaign_detail", args=[self.account.pk, "99"]),
                                       {"start": "2026-10-01", "end": "2026-10-12"})
        self.assertContains(response, "Dönem toplamı")
        self.assertEqual(response.context["summary"]["clicks"], 129)
        self.assertEqual(response.context["summary"]["spend"], Decimal("59.63"))
        self.assertEqual(performance.call_args.args[2].isoformat(), "2026-10-01")
        self.preview(response, "campaign-detail.html")

    def test_meta_summary_requests_account_totals_without_daily_duplication(self):
        with patch("core.services.ads_integrations.account_token", return_value="secret"), \
             patch("core.services.ads_integrations.meta_rows", return_value=[
                 {"campaign_id": "99", "impressions": "2209", "clicks": "129", "spend": "59.63"},
             ]) as meta:
            result = campaign_summaries(self.account, timezone.localdate()-timedelta(days=29), timezone.localdate(), campaign_ids=["99"])
        self.assertEqual(result["99"]["spend"], Decimal("59.63"))
        self.assertNotIn("time_increment", meta.call_args.args[2])

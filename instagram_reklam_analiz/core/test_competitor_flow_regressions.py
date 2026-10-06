import importlib
import json
from datetime import timedelta
from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import Mock, patch

from django.apps import apps
from django.contrib.auth import get_user_model
from django.contrib.messages.storage.fallback import FallbackStorage
from django.core.cache import cache
from django.db import connection
from django.test import RequestFactory, TestCase, override_settings
from django.utils import timezone

from core.models import Ad, AdMetricHistory, AgencyClient, Competitor, Organization, Platform, PlatformAccount
from core.services.competitor_live_sync import CompetitorSyncError, MetaAdLibraryCompetitorSync, _token_for_competitor, sync_competitor_live
from core.services.competitor_metrics import summarize_metrics
from core.views.rakip_ekle import rakip_ekle, api_rakip_guncelle
from core.views.rakip_reklam_paneli import api_rakip_reklam_sync, _ad_payload
from core.views.rakip_reklam_hareketleri import api_rakip_reklam_hareketleri


@override_settings(META_AD_LIBRARY_ACCESS_TOKEN="library-token")
class CompetitorFlowRegressionTests(TestCase):
    def setUp(self):
        cache.clear()
        self.user = get_user_model().objects.create_user(username="flow-user")
        self.platform, _ = Platform.objects.get_or_create(code="instagram", defaults={"name": "Instagram"})
        self.competitor = Competitor.objects.create(user=self.user, platform=self.platform,
            name="Example Brand", platform_identifier="@examplebrand")

    def request(self, path, data=None, method="post", json_body=False):
        factory = RequestFactory()
        if json_body:
            req = factory.post(path, json.dumps(data), content_type="application/json")
        else:
            req = getattr(factory, method)(path, data or {})
        req.user = self.user
        req.session = {}
        req._messages = FallbackStorage(req)
        return req

    def ad(self):
        return Ad.objects.create(user=self.user, competitor=self.competitor, source_type="COMPETITOR",
            platform_ad_id="ad-1", raw_data={"provider": "meta_ad_library", "snapshot_url": "https://www.facebook.com/ads/library/?id=1"})

    def test_member_adds_google_website_without_connecting_own_ads_account(self):
        platform, _ = Platform.objects.get_or_create(code='google_ads', defaults={'name': 'Google Ads'})
        request = self.request('/rakip/ekle/', {'platform': platform.pk, 'platform_identifier': 'https://www.example.com/products',
            'name': 'Example Company', 'facebook_page_id': 'irrelevant-google-field'})
        result = rakip_ekle(request)
        self.assertEqual(result.status_code, 302)
        self.assertNotIn('connect', result.url)
        competitor = Competitor.objects.get(user=self.user, platform=platform)
        self.assertEqual(competitor.platform_identifier, 'example.com')
        self.assertIsNone(competitor.platform_account)
        self.assertEqual(competitor.raw_data['facebook_page_id'], '')

    def test_empty_panel_response_explains_source_failure(self):
        from core.views.rakip_reklam_paneli import api_rakip_reklamlar
        self.competitor.raw_data = {'last_live_sync_warning': 'Kaynak bu sorgu için reklam döndürmedi.'}
        self.competitor.save()
        result = api_rakip_reklamlar(self.request('/ads/', method='get'), self.competitor.pk)
        data = json.loads(result.content)
        self.assertEqual(data['count'], 0)
        self.assertEqual(data['sync_warning'], 'Kaynak bu sorgu için reklam döndürmedi.')
        self.assertIn('source_notice', data)

    @override_settings(SERPAPI_API_KEY='test-key')
    @patch('core.services.competitor_public_sources.requests.get')
    def test_google_firm_choice_is_persisted_and_selected_inside_app(self, get):
        platform, _ = Platform.objects.get_or_create(code='google_ads', defaults={'name': 'Google Ads'})
        self.competitor.platform = platform
        self.competitor.platform_identifier = 'example.com'
        self.competitor.save()
        self.user.is_staff = True
        self.user.save()
        rows = [dict(advertiser_id=identifier, advertiser=name, target_domain='example.com',
                     ad_creative_id=creative, format='image')
                for identifier, name, creative in [('AR111', 'First Legal Company', 'CR1'), ('AR222', 'Second Legal Company', 'CR2')]]
        get.return_value = Mock(ok=True, status_code=200, json=Mock(return_value={'ad_creatives': rows}))
        result = api_rakip_reklam_sync(self.request('/sync/'), self.competitor.pk)
        self.assertEqual(result.status_code, 409)
        self.assertEqual(json.loads(result.content)['advertiser_candidates'][0]['name'], 'First Legal Company')
        self.competitor.refresh_from_db()
        self.assertEqual(len(self.competitor.raw_data['google_advertiser_candidates']), 2)
        result = api_rakip_reklam_sync(self.request('/sync/', {'advertiser_id': 'AR222'}), self.competitor.pk)
        self.assertEqual(result.status_code, 200)
        self.assertEqual(self.competitor.ads.get().platform_ad_id, 'CR2')
        self.competitor.refresh_from_db()
        self.assertEqual(self.competitor.raw_data['google_advertiser_id'], 'AR222')
        self.assertNotIn('google_advertiser_candidates', self.competitor.raw_data)

    @patch('core.views.rakip_reklam_paneli.sync_competitor_live')
    def test_firm_choice_rejects_forged_id_without_fetching(self, sync):
        self.user.is_staff = True
        self.user.save()
        result = api_rakip_reklam_sync(self.request('/sync/', {'advertiser_id': 'AR999'}), self.competitor.pk)
        self.assertEqual(result.status_code, 400)
        sync.assert_not_called()

    @patch('core.tasks.competitor_sync.sync_competitor_live', return_value={'created': 1})
    @patch('core.services.sync_policy.policy_for_user', return_value=None)
    def test_staff_add_worker_uses_same_record_limit_as_manual_sync(self, policy, sync):
        from core.tasks.competitor_sync import _sync_competitor_live_ads
        self.user.is_staff = True
        self.user.save()
        result = _sync_competitor_live_ads(self.competitor.pk)
        self.assertTrue(result['success'])
        self.assertEqual(sync.call_args.kwargs['limit'], 50)

    @patch('core.views.competitor_intelligence.render')
    def test_intelligence_includes_google_public_ads_and_regional_coverage(self, render):
        from core.views.competitor_intelligence import competitor_intelligence
        platform, _ = Platform.objects.get_or_create(code='google_ads', defaults={'name': 'Google Ads'})
        self.competitor.platform = platform
        self.competitor.save()
        ad = self.ad()
        ad.raw_data = {'provider': 'google_ads_transparency_serpapi', 'raw': {
            'detail_information': {'regions': [{'region_name': 'Turkiye', 'times_shown': '3000 - 4000'}]}}}
        ad.save()
        competitor_intelligence(self.request('/competitor-intelligence/', method='get'))
        context = render.call_args.args[2]
        self.assertEqual(context['total_ads'], 1)
        self.assertEqual(context['regional_range_count'], 1)

    def snapshot(self, ad, day=0, impressions=1000, spend=50, legacy_engagement=0):
        return AdMetricHistory.objects.create(ad=ad, date=timezone.localdate()-timedelta(days=day),
            impressions=impressions, spend=spend, engagement=legacy_engagement, reach=900,
            is_competitor_snapshot=True, raw_metrics={"provider": "meta_ad_library",
                "impressions_range": {"lower_bound": impressions, "upper_bound": impressions},
                "spend_range": {"lower_bound": spend, "upper_bound": spend}})

    @patch("core.tasks.competitor_sync.queue_competitor_sync")
    def test_duplicate_handle_is_rejected_even_with_a_different_connected_account(self, queue):
        PlatformAccount.objects.create(user=self.user, platform=self.platform, account_id="new-account", access_token="")
        response = rakip_ekle(self.request("/rakip/ekle/", {"platform": self.platform.pk,
            "platform_identifier": "ExampleBrand", "is_active": "on"}))
        self.assertEqual(response.status_code, 302)
        self.assertEqual(Competitor.objects.filter(user=self.user).count(), 1)
        queue.assert_not_called()

    def test_agency_duplicate_handle_is_rejected_across_member_users(self):
        from core.forms import AgencyCompetitorForm
        organization = Organization.objects.create(owner=self.user, name="Example Agency")
        client = AgencyClient.objects.create(organization=organization, name="Example Client")
        self.competitor.agency_client = client
        self.competitor.save()
        form = AgencyCompetitorForm({"agency_client": client.pk, "platform": self.platform.pk,
            "platform_identifier": "EXAMPLEBRAND", "name": "Example Brand", "category": "direct", "is_active": "on"}, organization=organization)
        self.assertFalse(form.is_valid())
        self.assertIn("zaten", str(form.errors))

    def test_page_change_does_not_mix_advertiser_history(self):
        ad = self.ad()
        self.competitor.raw_data = {"facebook_page_id": "123"}
        self.competitor.save()
        response = api_rakip_guncelle(self.request("/update/", {"platform_identifier": "examplebrand", "facebook_page_id": "456", "is_active": True}, json_body=True), self.competitor.pk)
        self.assertEqual(response.status_code, 400)
        self.competitor.refresh_from_db()
        self.assertEqual(self.competitor.raw_data["facebook_page_id"], "123")
        self.assertTrue(self.competitor.ads.filter(pk=ad.pk).exists())

    @patch("core.tasks.competitor_sync.queue_competitor_sync")
    def test_notes_update_preserves_ad_last_seen_and_attached_account(self, queue):
        ad = self.ad()
        old_seen = timezone.now()-timedelta(days=5)
        Ad.objects.filter(pk=ad.pk).update(last_seen_at=old_seen)
        account = PlatformAccount.objects.create(user=self.user, platform=self.platform, account_id="old", access_token="")
        self.competitor.platform_account = account
        self.competitor.save()
        PlatformAccount.objects.create(user=self.user, platform=self.platform, account_id="new", access_token="")
        response = api_rakip_guncelle(self.request("/update/", {"platform_identifier": "@ExampleBrand", "description": "New note", "is_active": True}, json_body=True), self.competitor.pk)
        self.assertEqual(response.status_code, 200)
        ad.refresh_from_db()
        self.competitor.refresh_from_db()
        self.assertEqual(ad.last_seen_at, old_seen)
        self.assertEqual(self.competitor.platform_account_id, account.pk)

    def test_json_array_and_string_boolean_are_rejected(self):
        for payload in ([], {"platform_identifier": "examplebrand", "is_active": "false"}):
            response = api_rakip_guncelle(self.request("/update/", payload, json_body=True), self.competitor.pk)
            self.assertEqual(response.status_code, 400)

    @patch("core.views.rakip_reklam_paneli.sync_competitor_live")
    @patch("core.views.rakip_reklam_paneli.manual_sync_allowed", return_value=False)
    def test_manual_sync_denied_before_provider_call(self, allowed, sync):
        self.assertEqual(api_rakip_reklam_sync(self.request("/sync/"), self.competitor.pk).status_code, 403)
        sync.assert_not_called()

    @patch("core.views.rakip_reklam_paneli.sync_competitor_live")
    def test_inactive_sync_denied_before_provider_call(self, sync):
        self.competitor.is_active = False
        self.competitor.save()
        self.assertEqual(api_rakip_reklam_sync(self.request("/sync/"), self.competitor.pk).status_code, 400)
        sync.assert_not_called()

    @patch("core.views.rakip_reklam_paneli.sync_competitor_live")
    @patch("core.views.rakip_reklam_paneli.policy_for_user", return_value=SimpleNamespace(max_records=7))
    @patch("core.views.rakip_reklam_paneli.manual_sync_allowed", return_value=True)
    def test_manual_sync_respects_plan_record_limit(self, allowed, policy, sync):
        sync.return_value = {"created": 0, "updated": 0, "total": 0, "fetched": 0, "provider": "meta_ad_library"}
        self.assertEqual(api_rakip_reklam_sync(self.request("/sync/"), self.competitor.pk).status_code, 200)
        self.assertEqual(sync.call_args.kwargs["limit"], 7)

    @override_settings(META_AD_LIBRARY_ACCESS_TOKEN="", INSTAGRAM_ACCESS_TOKEN="global-instagram")
    def test_instagram_login_and_global_instagram_tokens_are_never_used(self):
        account = SimpleNamespace(access_token="IGprivate", connection=None, extra_data={"auth_type": "instagram_login"})
        self.assertEqual(_token_for_competitor(SimpleNamespace(platform_account=account)), "")
        self.assertEqual(_token_for_competitor(SimpleNamespace(platform_account=None)), "")

    @override_settings(META_AD_LIBRARY_ACCESS_TOKEN="")
    def test_expired_connection_does_not_fallback_to_account_token(self):
        account = SimpleNamespace(access_token="stale", extra_data={}, connection=SimpleNamespace(
            access_token="stale", extra_data={}, status="expired", is_token_expired=True))
        self.assertEqual(_token_for_competitor(SimpleNamespace(platform_account=account)), "")

    @patch("core.services.competitor_live_sync.requests.get")
    def test_sync_preserves_unknown_format_and_does_not_invent_metrics(self, get):
        get.return_value = Mock(status_code=200, json=Mock(return_value={"data": [{"id": "123", "page_id": "456", "page_name": "Example Brand",
            "publisher_platforms": ["instagram"], "ad_snapshot_url": "https://www.facebook.com/ads/archive/render_ad/?id=123",
            "impressions": {"lower_bound": 1000, "upper_bound": 2000}}]}))
        sync_competitor_live(self.competitor)
        ad = self.competitor.ads.get()
        metric = ad.metric_history.get()
        self.assertEqual(ad.ad_format, "UNKNOWN")
        self.assertEqual(ad.landing_url, "")
        self.assertEqual((metric.engagement, metric.reach, metric.frequency), (0, 0, Decimal("0")))
        payload = _ad_payload(ad)
        self.assertIsNone(payload["engagement"])
        self.assertIsNone(payload["clicks"])
        self.assertIsNone(payload["performance_score"])
        self.assertEqual(payload["impressions"], 1500)
        self.assertTrue(payload["snapshot_url"])

    def test_cumulative_snapshots_are_not_summed_and_legacy_estimates_are_ignored(self):
        ad = self.ad()
        self.snapshot(ad, day=1, legacy_engagement=27)
        self.snapshot(ad, day=0, legacy_engagement=27)
        summary = summarize_metrics(ad.metric_history.all())
        self.assertEqual(summary["impressions"], 1000)
        self.assertEqual(summary["spend"], 50)
        self.assertIsNone(summary["engagement"])
        from core.views.competitor_intelligence import _metric_summary, _ad_payload as detail_payload
        self.assertEqual(_metric_summary(ad)["impressions"], 1000)
        self.assertEqual(detail_payload(ad)["metrics"]["engagement_label"], "Veri yok")

    def test_measured_daily_metrics_still_sum(self):
        ad = self.ad()
        for day in (0, 1):
            AdMetricHistory.objects.create(ad=ad, date=timezone.localdate()-timedelta(days=day), impressions=100, spend=5, clicks=10)
        summary = summarize_metrics(ad.metric_history.all())
        self.assertEqual(summary["impressions"], 200)
        self.assertEqual(summary["clicks"], 20)

    def test_snapshot_movement_totals_use_last_snapshot(self):
        ad = self.ad()
        self.snapshot(ad, day=1)
        self.snapshot(ad, day=0)
        response = api_rakip_reklam_hareketleri(self.request("/movements/", {"reklam_id": ad.pk}, method="get"))
        data = json.loads(response.content)
        self.assertEqual(data["total_impressions"], 1000)
        self.assertIsNone(data["total_engagement"])
        self.assertEqual(data["chart_engagement"], [None, None])
        self.assertEqual(data["measurement_type"], "cumulative_snapshot")

    def test_date_filter_does_not_fallback_to_out_of_range_metrics(self):
        ad = self.ad()
        self.snapshot(ad, day=30)
        data = json.loads(api_rakip_reklam_hareketleri(self.request("/movements/", {"reklam_id": ad.pk, "date_range": "daily"}, method="get")).content)
        self.assertEqual(data["chart_labels"], [])
        self.assertIsNone(data["total_impressions"])

    @patch("core.services.competitor_live_sync.MetaAdLibraryCompetitorSync._fetch")
    def test_partial_import_rolls_back_and_persists_failure(self, fetch):
        self.competitor.raw_data = {"facebook_page_id": "456"}
        self.competitor.save()
        fetch.return_value = {"data": [{"id": "1", "page_id": "456"}, {"page_id": "456"}]}
        with self.assertRaises(CompetitorSyncError):
            sync_competitor_live(self.competitor)
        self.assertFalse(self.competitor.ads.exists())
        self.competitor.refresh_from_db()
        self.assertEqual(self.competitor.raw_data["last_live_sync_status"], "error")

    @patch("core.services.competitor_live_sync.MetaAdLibraryCompetitorSync._fetch", side_effect=RuntimeError("private upstream info"))
    def test_unexpected_error_is_visible_without_exposing_details(self, fetch):
        with self.assertRaises(CompetitorSyncError):
            sync_competitor_live(self.competitor)
        self.competitor.refresh_from_db()
        self.assertEqual(self.competitor.raw_data["last_live_sync_status"], "error")
        self.assertNotIn("private upstream info", self.competitor.raw_data["last_live_sync_error"])

    @patch("core.services.sync_policy.is_sync_due", return_value=True)
    @patch("core.tasks.competitor_sync.sync_competitor_live_ads.delay")
    def test_scheduled_broker_failure_releases_lock_and_continues(self, delay, due):
        from core.tasks.competitor_sync import sync_all_live_competitors
        other = Competitor.objects.create(user=self.user, platform=self.platform, name="Another", platform_identifier="another")
        delay.side_effect = [RuntimeError("broker unavailable"), SimpleNamespace(id="job-2")]
        result = sync_all_live_competitors()
        self.assertEqual(result["queued"], 1)
        self.assertEqual(result["items"][0]["competitor_id"], other.pk)
        self.assertIsNone(cache.get(f"sync-lock:competitor-dispatch:{self.competitor.pk}"))
        self.competitor.refresh_from_db()
        self.assertEqual(self.competitor.raw_data["last_live_sync_status"], "error")

    @patch("core.services.sync_policy.policy_for_user", side_effect=RuntimeError("policy error"))
    def test_worker_unexpected_failure_sets_error_and_releases_dispatch_lock(self, policy):
        from core.tasks.competitor_sync import sync_competitor_live_ads
        cache.set(f"sync-lock:competitor-dispatch:{self.competitor.pk}", "queued")
        self.assertFalse(sync_competitor_live_ads(self.competitor.pk)["success"])
        self.competitor.refresh_from_db()
        self.assertEqual(self.competitor.raw_data["last_live_sync_status"], "error")
        self.assertIsNone(cache.get(f"sync-lock:competitor-dispatch:{self.competitor.pk}"))

    def test_data_cleanup_removes_old_estimates_without_touching_daily_metrics(self):
        ad = self.ad()
        metric = self.snapshot(ad, legacy_engagement=27)
        other = Ad.objects.create(user=self.user, competitor=self.competitor, source_type="COMPETITOR", platform_ad_id="ad-2")
        measured = AdMetricHistory.objects.create(ad=other, date=timezone.localdate(), engagement=80, reach=400)
        migration = importlib.import_module("core.migrations.0081_correct_competitor_library_data")
        migration.correct_library_data(apps, SimpleNamespace(connection=connection))
        metric.refresh_from_db()
        measured.refresh_from_db()
        self.assertEqual((metric.engagement, metric.reach), (0, 0))
        self.assertEqual((measured.engagement, measured.reach), (80, 400))

    def test_intelligence_page_renders_unavailable_metrics(self):
        from core.views.competitor_intelligence import competitor_intelligence
        ad = self.ad()
        self.snapshot(ad, legacy_engagement=27)
        response = competitor_intelligence(self.request("/competitor-intelligence/", method="get"))
        self.assertEqual(response.status_code, 200)
        self.assertIn("Veri yok", response.content.decode())

    def test_open_ended_and_invalid_ranges_are_not_misrepresented_as_midpoints(self):
        from core.services.competitor_metrics import range_midpoint
        for value in ({"lower_bound": 1000}, {"lower_bound": 1000, "upper_bound": 10}, "invalid", "NaN"):
            self.assertIsNone(range_midpoint(value))

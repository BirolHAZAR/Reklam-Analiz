from types import SimpleNamespace
from unittest.mock import Mock, patch

from django.contrib.auth import get_user_model
from django.test import RequestFactory, SimpleTestCase, TestCase, override_settings
from django.contrib.messages.storage.fallback import FallbackStorage

from core.models import Competitor, Platform
from core.services.competitor_live_sync import (
    CompetitorSyncError, MetaAdLibraryCompetitorSync, _token_for_competitor,
    sync_competitor_live,
)


@override_settings(META_AD_LIBRARY_ACCESS_TOKEN="library-token")
class CompetitorLiveSyncTests(TestCase):
    def setUp(self):
        user = get_user_model().objects.create_user(username="competitor-test")
        platform, _ = Platform.objects.get_or_create(code="instagram", defaults={"name": "Instagram"})
        self.competitor = Competitor.objects.create(user=user, platform=platform,
            name="Example Brand", platform_identifier="@examplebrand")

    def test_library_token_takes_precedence_over_instagram_token(self):
        account = SimpleNamespace(access_token="instagram-token", connection=None)
        self.assertEqual(_token_for_competitor(SimpleNamespace(platform_account=account)), "library-token")

    @patch("core.services.competitor_live_sync.requests.get")
    def test_supported_fields_and_safe_pagination_respect_total_limit(self, get):
        get.side_effect = [
            Mock(status_code=200, json=Mock(return_value={"data": [{"id": "1"}],
                 "paging": {"next": "https://untrusted.example/", "cursors": {"after": "next"}}})),
            Mock(status_code=200, json=Mock(return_value={"data": [{"id": "2"}, {"id": "3"}]})),
        ]
        result = MetaAdLibraryCompetitorSync(self.competitor)._fetch(limit=2)
        self.assertEqual([r["id"] for r in result["data"]], ["1", "2"])
        self.assertEqual(get.call_count, 2)
        for call in get.call_args_list:
            self.assertTrue(call.args[0].endswith('/ads_archive'))
            self.assertNotIn('funding_entity', call.kwargs['params']['fields'])
            self.assertEqual(call.kwargs['params']['access_token'], 'library-token')

    @patch("core.services.competitor_live_sync.requests.get")
    def test_upstream_error_persists_and_success_clears_it(self, get):
        get.return_value = Mock(status_code=400, json=Mock(return_value={"error": {"message": "Access denied", "code": 10}}))
        with self.assertRaises(CompetitorSyncError):
            sync_competitor_live(self.competitor)
        self.competitor.refresh_from_db()
        self.assertEqual(self.competitor.raw_data['last_live_sync_status'], 'error')
        self.assertIn('Access denied', self.competitor.raw_data['last_live_sync_error'])
        get.return_value = Mock(status_code=200, json=Mock(return_value={"data": []}))
        sync_competitor_live(self.competitor)
        self.competitor.refresh_from_db()
        self.assertEqual(self.competitor.raw_data['last_live_sync_error'], '')
        self.assertEqual(self.competitor.raw_data['last_live_sync_status'], 'success')

    @patch("core.services.competitor_live_sync.requests.get")
    def test_real_rows_upsert_idempotently(self, get):
        get.return_value = Mock(status_code=200, json=Mock(return_value={"data": [
            {"id": "123", "page_id": "456", "page_name": "Example Brand", "ad_creative_bodies": ["Test"],
             "ad_creative_link_titles": ["Example Brand"], "publisher_platforms": ["instagram"]}]}))
        self.assertEqual(sync_competitor_live(self.competitor)['created'], 1)
        self.assertEqual(sync_competitor_live(self.competitor)['updated'], 1)
        self.assertEqual(self.competitor.ads.count(), 1)

    @patch("core.tasks.competitor_sync.sync_competitor_live_ads.delay", side_effect=RuntimeError("broker unavailable"))
    def test_queue_failure_is_visible_on_saved_competitor(self, delay):
        from core.tasks.competitor_sync import queue_competitor_sync
        queue_competitor_sync(self.competitor.pk)
        self.competitor.refresh_from_db()
        self.assertEqual(self.competitor.raw_data['last_live_sync_status'], 'error')
        self.assertTrue(self.competitor.raw_data['last_live_sync_error'])

    @patch('core.tasks.competitor_sync.queue_competitor_sync')
    @patch('core.views.rakip_ekle._get_user_platform_account', return_value=None)
    @patch('core.views.rakip_ekle.get_agency_scope')
    def test_new_active_competitor_is_queued_after_commit(self, scope, account, queue):
        from core.views.rakip_ekle import rakip_ekle
        scope.return_value = SimpleNamespace(is_agency=False, selected_client=None)
        request = RequestFactory().post('/rakip/ekle/', {'platform': self.competitor.platform_id,
            'platform_identifier': '@another', 'name': 'Another', 'is_active': 'on'})
        request.user = self.competitor.user
        request.session = {}
        request._messages = FallbackStorage(request)
        with self.captureOnCommitCallbacks(execute=True):
            response = rakip_ekle(request)
            queue.assert_not_called()
        self.assertEqual(response.status_code, 302)
        queue.assert_called_once_with(Competitor.objects.get(platform_identifier='another').pk)

    @patch("core.services.competitor_live_sync.requests.get")
    def test_keyword_collision_never_imports_another_advertiser(self, get):
        get.return_value = Mock(status_code=200, json=Mock(return_value={"data": [
            {"id": "123", "page_id": "456", "page_name": "Other Advertiser", "ad_creative_bodies": ["Example Brand mentioned here"]}]}))
        with self.assertRaisesMessage(CompetitorSyncError, 'Hesap reklamverenle otomatik eşleştirilemedi'):
            sync_competitor_live(self.competitor)
        self.assertFalse(self.competitor.ads.exists())

    def test_page_reference_validation_rejects_foreign_hosts(self):
        from core.services.competitor_live_sync import parse_meta_page_reference
        self.assertEqual(parse_meta_page_reference('https://www.facebook.com/ads/library/?view_all_page_id=123'), '123')
        for value in ['https://evil.example/?view_all_page_id=123', 'https://facebook.com.evil.example/123', 'abc', 'https://www.facebook.com/ads/library/?q=brand']:
            with self.assertRaises(ValueError):
                parse_meta_page_reference(value)

    def test_agency_form_only_offers_supported_platforms(self):
        from core.forms import AgencyCompetitorForm
        Platform.objects.get_or_create(code='google_ads', defaults={'name': 'Google Ads'})
        form = AgencyCompetitorForm()
        self.assertEqual(set(form.fields['platform'].queryset.values_list('code', flat=True)) - {'instagram', 'facebook', 'google_ads', 'tiktok', 'linkedin'}, set())
        self.assertIn('google_ads', form.fields['platform'].queryset.values_list('code', flat=True))
        self.assertTrue(form.fields['platform'].required)

    @patch("core.services.competitor_live_sync.requests.get")
    def test_empty_response_does_not_verify_account_or_claim_no_ads(self, get):
        get.return_value = Mock(status_code=200, json=Mock(return_value={"data": []}))
        result = sync_competitor_live(self.competitor)
        self.competitor.refresh_from_db()
        self.assertEqual(self.competitor.raw_data['identity_status'], 'unverified')
        self.assertTrue(result['warning'])

    @patch("core.services.competitor_live_sync.requests.get")
    def test_other_platforms_are_rejected_before_network_call(self, get):
        platform, _ = Platform.objects.get_or_create(code='twitter', defaults={'name': 'X'})
        self.competitor.platform = platform
        self.competitor.save(update_fields=["platform"])
        with self.assertRaises(CompetitorSyncError):
            sync_competitor_live(self.competitor)
        get.assert_not_called()

    @patch("core.services.competitor_live_sync.requests.get")
    def test_page_id_and_country_are_json_arrays(self, get):
        import json
        self.competitor.raw_data = {'facebook_page_id': '456'}
        get.return_value = Mock(status_code=200, json=Mock(return_value={'data': []}))
        MetaAdLibraryCompetitorSync(self.competitor)._fetch(limit=1)
        params = get.call_args.kwargs['params']
        self.assertEqual(json.loads(params['search_page_ids']), ['456'])
        self.assertEqual(json.loads(params['ad_reached_countries']), ['TR'])
        self.assertNotIn('search_terms', params)

    @patch("core.services.competitor_live_sync.requests.get")
    def test_page_identity_permission_failure_is_not_nonexistent_account(self, get):
        get.return_value = Mock(ok=False, json=Mock(return_value={'error': {'code': 100}}))
        result = MetaAdLibraryCompetitorSync(self.competitor)._check_page_identity('456')
        self.assertEqual(result['status'], 'unverified')
        self.assertIn('Page Public Metadata Access', result['message'])

    @patch("core.services.competitor_live_sync.requests.get")
    def test_page_identity_success_requires_matching_id_and_name(self, get):
        get.return_value = Mock(ok=True, json=Mock(return_value={'id': '456', 'name': 'Example Brand'}))
        result = MetaAdLibraryCompetitorSync(self.competitor)._check_page_identity('456')
        self.assertEqual(result['status'], 'matched')

    def test_instagram_user_id_is_never_used_as_facebook_advertiser_id(self):
        from core.services.competitor_live_sync import _page_ids_for_competitor
        self.competitor.platform_identifier = '17841400000000000'
        self.assertEqual(_page_ids_for_competitor(self.competitor), [])
        self.competitor.raw_data = {'facebook_page_id': '456'}
        self.assertEqual(_page_ids_for_competitor(self.competitor), ['456'])

    @patch("core.services.competitor_live_sync.requests.get")
    def test_instagram_numeric_id_requires_advertiser_mapping_before_fetch(self, get):
        self.competitor.platform_identifier = '17841400000000000'
        self.competitor.save(update_fields=['platform_identifier'])
        with self.assertRaisesMessage(CompetitorSyncError, "Instagram hesap ID'si"):
            sync_competitor_live(self.competitor)
        get.assert_not_called()

    def test_facebook_numeric_page_id_can_be_used_directly(self):
        from core.services.competitor_live_sync import _page_ids_for_competitor
        platform, _ = Platform.objects.get_or_create(code='facebook', defaults={'name': 'Facebook'})
        self.competitor.platform = platform
        self.competitor.platform_identifier = '456'
        self.assertEqual(_page_ids_for_competitor(self.competitor), ['456'])

    def test_instagram_and_facebook_ids_are_allowed_to_be_different(self):
        from core.services.competitor_identity import identity_change_error, platform_identity_metadata
        identifier = '17841400000000000'
        self.assertEqual(identity_change_error(self.competitor, self.competitor.platform, identifier, '456'), '')
        self.assertEqual(platform_identity_metadata(self.competitor.platform, identifier), {'instagram_user_id': identifier})


class CompetitorIdentifierNamespaceTests(SimpleTestCase):
    def test_instagram_user_id_is_not_used_as_advertiser_keyword(self):
        from core.services.competitor_live_sync import _search_term, competitor_library_url
        competitor = SimpleNamespace(platform_identifier='17841400000000000', name='Example Brand',
                                     raw_data={}, platform=SimpleNamespace(code='instagram'))
        self.assertEqual(_search_term(competitor), 'Example Brand')
        self.assertNotIn('17841400000000000', competitor_library_url(competitor))

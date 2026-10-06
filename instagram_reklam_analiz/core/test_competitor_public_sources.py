import json
from types import SimpleNamespace
from io import StringIO
from unittest.mock import Mock, patch
from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.test import TestCase, SimpleTestCase, override_settings
from core.models import Competitor, Platform, AdMetricHistory
from core.services.competitor_live_sync import CompetitorSyncError, sync_competitor_live
from core.services.competitor_metrics import summarize_metrics, metric_values
from core.services.competitor_identity import normalize_competitor_identifier
from core.views.rakip_reklam_paneli import _ad_payload
from core.services.competitor_public_sources import competitor_media_assets


class CompetitorMediaTests(SimpleTestCase):
    def assets(self, raw, image='', video=''):
        return competitor_media_assets(SimpleNamespace(raw_data={'raw': raw},
            preview_image_url=image, preview_video_url=video))

    def test_carousel_preserves_all_cards_and_mixed_media(self):
        cards = [{'original_image_url': f'https://example.com/{i}.jpg',
                  'title': f'Card {i}', 'body': {'text': f'Copy {i}'},
                  'cta_text': 'Shop'} for i in range(6)]
        cards[2]['video_hd_url'] = 'https://example.com/video.mp4'
        assets = self.assets({'snapshot': {'cards': cards}})
        self.assertEqual(len(assets), 6)
        self.assertEqual(assets[2]['kind'], 'video')
        self.assertEqual(assets[5]['body'], 'Copy 5')
        self.assertEqual(assets[5]['call_to_action'], 'Shop')

    def test_youtube_page_is_embedded_instead_of_video_file(self):
        for url in ['https://www.youtube.com/watch?v=abcdefghijk',
                    'https://youtu.be/abcdefghijk', 'https://www.youtube.com/shorts/abcdefghijk']:
            asset = self.assets({'creative_variants': [{'video_link': url}]})[0]
            self.assertEqual(asset['kind'], 'embed')
            self.assertEqual(asset['embed_url'], 'https://www.youtube-nocookie.com/embed/abcdefghijk')
            self.assertEqual(asset['video_url'], url)

    def test_missing_or_unsafe_media_is_not_fabricated(self):
        asset = self.assets({}, image='javascript:alert(1)')[0]
        self.assertEqual(asset['image_url'], '')
        self.assertEqual(asset['kind'], 'text')
        asset = self.assets({}, video='https://www.youtube.com/watch?v=invalid')[0]
        self.assertEqual(asset['kind'], 'link')
        self.assertEqual(asset['embed_url'], '')

    def test_tiktok_preserves_multiple_images_and_video(self):
        assets = self.assets({'ad': {'image_urls': ['https://example.com/1.jpg',
            'https://example.com/2.jpg'], 'videos': [{'url': 'https://example.com/ad.mp4'}]}})
        self.assertEqual([a['kind'] for a in assets], ['image', 'image', 'video'])

    def test_text_variants_do_not_hide_existing_preview(self):
        assets = self.assets({'creative_variants': [{'snippet': 'Actual copy'}]},
                             image='https://example.com/preview.jpg')
        self.assertEqual(assets[0]['image_url'], 'https://example.com/preview.jpg')
        self.assertEqual(assets[1]['body'], 'Actual copy')


def response(data, status=200):
    return Mock(ok=status < 400, status_code=status, json=Mock(return_value=data))


@override_settings(SERPAPI_API_KEY='test-key', TIKTOK_AD_LIBRARY_ACCESS_TOKEN='test-tiktok', TIKTOK_AD_LIBRARY_COUNTRIES=['DE'])
class PublicSourceTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(username='public-sources')
        self.platform, _ = Platform.objects.get_or_create(code='google_ads', defaults={'name': 'Google Ads'})
        self.competitor = Competitor.objects.create(user=self.user, platform=self.platform,
            name='Example Brand', platform_identifier='ar123')

    def google_row(self, advertiser='AR123', creative='CR1'):
        return {'advertiser_id': advertiser, 'advertiser': 'Example Brand', 'ad_creative_id': creative,
                'format': 'image', 'image': 'https://example.com/image.jpg',
                'first_shown': 1700000000, 'last_shown': 1700010000,
                'details_link': 'https://adstransparency.google.com/advertiser/'+advertiser+'/creative/'+creative}

    @patch('core.services.competitor_public_sources.requests.get')
    def test_google_id_filters_other_advertisers_and_imports_real_creative(self, get):
        get.return_value = response({'ad_creatives': [self.google_row('AR999'), self.google_row()]})
        result = sync_competitor_live(self.competitor, limit=5)
        self.assertEqual(result['created'], 1)
        self.assertEqual(get.call_args.kwargs['params']['advertiser_id'], 'AR123')
        ad = self.competitor.ads.get()
        self.assertEqual(ad.ad_format, 'IMAGE')
        self.assertEqual(ad.status, 'UNKNOWN')
        self.assertIsNotNone(ad.first_seen_at)
        self.assertEqual(ad.landing_url, '')
        metric = AdMetricHistory.objects.get(ad=ad)
        self.assertIsNone(metric_values(metric)['spend'])
        self.assertIsNone(summarize_metrics(AdMetricHistory.objects.all())['impressions'])
        payload = _ad_payload(ad)
        self.assertIsNone(payload['clicks'])
        self.assertIsNone(payload['spend'])
        self.assertEqual(payload['media_type'], 'image')
        self.assertEqual(self.competitor.raw_data['google_advertiser_id'], 'AR123')

    @override_settings(GOOGLE_COMPETITOR_DETAILS_ENABLED=True)
    @patch('core.services.competitor_public_sources.requests.get')
    def test_google_details_store_variants_and_regional_ranges_without_fake_performance(self, get):
        def provider(url, **kwargs):
            if kwargs['params']['engine'] == 'google_ads_transparency_center':
                return response({'ad_creatives': [self.google_row()]})
            return response({'search_parameters': {'advertiser_id': 'AR123', 'creative_id': 'CR1', 'api_key': 'test-key'},
                'search_information': {'regions': [{'region_name': 'Turkiye', 'times_shown': '3000 - 4000'}]},
                'ad_creatives': [{'headline': 'Real product offer', 'snippet': 'Actual ad copy',
                                  'call_to_action': 'Shop now', 'link': 'https://example.com/product',
                                  'image': 'https://example.com/original.jpg'}]})
        get.side_effect = provider
        result = sync_competitor_live(self.competitor)
        ad = self.competitor.ads.get()
        self.assertEqual(result['created'], 1)
        self.assertEqual(ad.primary_text, 'Actual ad copy')
        self.assertEqual(ad.headline, 'Real product offer')
        self.assertEqual(ad.call_to_action, 'Shop now')
        self.assertEqual(ad.preview_image_url, 'https://example.com/original.jpg')
        self.assertEqual(ad.landing_url, 'https://example.com/product')
        self.assertNotIn('test-key', json.dumps(ad.raw_data))
        self.assertEqual(_ad_payload(ad)['regions'][0]['impressions_range'], '3000 - 4000')
        self.assertIsNone(_ad_payload(ad)['clicks'])
        self.assertIsNone(_ad_payload(ad)['impressions'])
        sync_competitor_live(self.competitor)
        self.assertEqual(get.call_count, 3)  # cached detail is not charged again

    @override_settings(GOOGLE_COMPETITOR_DETAILS_ENABLED=True)
    @patch('core.services.competitor_public_sources.requests.get')
    def test_google_details_with_wrong_identity_are_not_saved(self, get):
        get.side_effect = [response({'ad_creatives': [self.google_row()]}),
                           response({'search_parameters': {'advertiser_id': 'AR999', 'creative_id': 'CR1'},
                                     'ad_creatives': [{'snippet': 'Other advertiser text'}]})]
        sync_competitor_live(self.competitor)
        ad = self.competitor.ads.get()
        self.assertEqual(ad.primary_text, '')
        self.assertNotIn('Other advertiser text', json.dumps(ad.raw_data))
        self.assertTrue(_ad_payload(ad)['detail_error'])

    @patch('core.services.competitor_public_sources.requests.get')
    def test_google_ambiguous_name_refuses_import(self, get):
        self.competitor.platform_identifier='examplebrand'
        self.competitor.save()
        get.return_value = response({'ad_creatives': [self.google_row('AR111'), self.google_row('AR222')]})
        with self.assertRaises(CompetitorSyncError):
            sync_competitor_live(self.competitor)
        self.assertFalse(self.competitor.ads.exists())

    @patch('core.services.competitor_public_sources.requests.get')
    def test_domain_resolves_legal_name_across_pages_and_reuses_id(self, get):
        self.competitor.name = 'example.com'
        self.competitor.platform_identifier = 'example.com'
        self.competitor.save()
        first = dict(self.google_row(), advertiser='Different Legal Company Limited', target_domain='www.example.com')
        second = dict(first, ad_creative_id='CR2')
        get.side_effect = [response({'ad_creatives': [first], 'serpapi_pagination': {'next_page_token': 'next'}}),
                           response({'ad_creatives': [second]})]
        result = sync_competitor_live(self.competitor, limit=1)
        self.assertEqual(get.call_count, 2)
        self.assertEqual(result['created'], 1)
        self.assertEqual(self.competitor.raw_data['google_advertiser_id'], 'AR123')
        get.side_effect = None
        get.return_value = response({'ad_creatives': [first]})
        result = sync_competitor_live(self.competitor, limit=1)
        self.assertEqual(result['created'], 0)
        self.assertEqual(result['updated'], 1)
        self.assertEqual(get.call_args.kwargs['params']['advertiser_id'], 'AR123')
        self.assertEqual(self.competitor.ads.count(), 1)

    @patch('core.services.competitor_public_sources.requests.get')
    def test_domain_refuses_second_advertiser_beyond_import_limit(self, get):
        self.competitor.platform_identifier = 'example.com'
        self.competitor.save()
        first = dict(self.google_row('AR111'), target_domain='example.com')
        second = dict(self.google_row('AR222'), target_domain='example.com')
        get.side_effect = [response({'ad_creatives': [first], 'serpapi_pagination': {'next_page_token': 'next'}}),
                           response({'ad_creatives': [second]})]
        with self.assertRaises(CompetitorSyncError):
            sync_competitor_live(self.competitor, limit=1)
        self.assertFalse(self.competitor.ads.exists())

    @patch('core.services.competitor_public_sources.requests.get')
    def test_domain_does_not_accept_name_match_on_another_website(self, get):
        self.competitor.platform_identifier = 'example.com'
        self.competitor.save()
        get.return_value = response({'ad_creatives': [dict(self.google_row(), target_domain='example.com.evil.test')]})
        with self.assertRaises(CompetitorSyncError):
            sync_competitor_live(self.competitor)
        self.assertFalse(self.competitor.ads.exists())

    @patch('core.services.competitor_public_sources.requests.get')
    def test_google_pagination_uses_cursor_not_untrusted_url(self, get):
        get.side_effect=[response({'ad_creatives':[self.google_row(creative='CR1')],
            'serpapi_pagination':{'next':'https://evil.example', 'next_page_token':'abc'}}),
            response({'ad_creatives':[self.google_row(creative='CR2')]})]
        result=sync_competitor_live(self.competitor, limit=2)
        self.assertEqual(result['created'],2)
        self.assertEqual(get.call_args.args[0], 'https://serpapi.com/search.json')
        self.assertEqual(get.call_args.kwargs['params']['next_page_token'],'abc')

    @override_settings(SERPAPI_API_KEY='')
    @patch('core.services.competitor_public_sources.requests.get')
    def test_missing_key_never_calls_provider(self,get):
        with self.assertRaises(CompetitorSyncError):
            sync_competitor_live(self.competitor)
        get.assert_not_called()

    @patch('core.services.competitor_public_sources.requests.get')
    def test_key_is_never_exposed_in_error(self,get):
        get.return_value=response({'error':'request failed test-key'},403)
        with self.assertRaises(CompetitorSyncError) as error:
            sync_competitor_live(self.competitor)
        self.assertNotIn('test-key',str(error.exception))
        self.assertNotIn('test-key',self.competitor.raw_data['last_live_sync_error'])

    def tiktok(self, identifier='123'):
        platform,_=Platform.objects.get_or_create(code='tiktok', defaults={'name':'TikTok'})
        self.competitor.platform=platform
        self.competitor.platform_identifier=identifier
        self.competitor.save()

    @patch('core.services.competitor_public_sources.requests.post')
    def test_tiktok_business_id_filters_other_accounts(self,post):
        self.tiktok()
        post.return_value=response({'error':{'code':'ok'}, 'data':{'ads':[
            {'advertiser':{'business_id':999},'ad':{'id':1}},
            {'advertiser':{'business_id':123},'ad':{'id':2,'image_urls':['https://example.com/ad.jpg'],
             'first_shown_date':20260101,'last_shown_date':20260102,'status':'active'}}]}})
        result=sync_competitor_live(self.competitor)
        self.assertEqual(result['created'],1)
        self.assertEqual(self.competitor.ads.get().platform_ad_id,'2')
        self.assertEqual(post.call_args.kwargs['json']['filters']['country_code_list'],['DE'])
        self.assertNotIn('advertiser_id',post.call_args.kwargs['json']['filters'])
        self.assertIsNone(metric_values(AdMetricHistory.objects.get(ad=self.competitor.ads.get()))['clicks'])

    @patch('core.services.competitor_public_sources.requests.post')
    def test_tiktok_resolves_name_to_single_business_id(self,post):
        self.tiktok('examplebrand')
        post.side_effect=[response({'data':{'advertisers':[{'business_id':123,'business_name':'Example Brand'},
                            {'business_id':999,'business_name':'Other Brand'}]}}),
                          response({'data':{'ads':[]}})]
        result=sync_competitor_live(self.competitor)
        self.assertEqual(result['fetched'],0)
        self.assertEqual(self.competitor.raw_data['tiktok_business_id'],'123')
        self.assertIsNone(self.competitor.last_seen_at)

    @override_settings(TIKTOK_AD_LIBRARY_COUNTRIES=['TR'])
    @patch('core.services.competitor_public_sources.requests.post')
    def test_tiktok_rejects_unsupported_country_without_network(self,post):
        self.tiktok()
        with self.assertRaises(CompetitorSyncError):
            sync_competitor_live(self.competitor)
        post.assert_not_called()

    @patch('core.services.competitor_public_sources.requests.get')
    def test_read_only_probe_does_not_create_competitors_or_ads(self,get):
        get.return_value=response({'ad_creatives':[self.google_row()]})
        output=StringIO()
        call_command('probe_competitor_source',platform='google_ads',identifier='AR123',name='Example Brand',stdout=output)
        self.assertEqual(json.loads(output.getvalue())['rows'],1)
        self.assertEqual(Competitor.objects.count(),1)
        self.assertFalse(self.competitor.ads.exists())


class PublicIdentityTests(TestCase):
    @override_settings(META_COMPETITOR_SOURCE='graph', META_AD_LIBRARY_COUNTRIES=['TR'])
    @patch('core.services.competitor_live_sync._token_for_competitor', return_value='test-token')
    def test_valid_meta_connection_still_discloses_turkey_commercial_coverage_limit(self, token):
        from types import SimpleNamespace
        from core.services.competitor_public_sources import source_status
        status = source_status(SimpleNamespace(platform=SimpleNamespace(code='instagram')))
        self.assertTrue(status['configured'])
        self.assertTrue(status['coverage_limited'])
        self.assertIn('Türkiye', status['message'])
        self.assertIn('sistem yöneticisi', status['message'])

    def test_typed_platform_links(self):
        self.assertEqual(normalize_competitor_identifier('https://adstransparency.google.com/advertiser/AR123'),'ar123')
        self.assertEqual(normalize_competitor_identifier('https://www.tiktok.com/@examplebrand'),'examplebrand')

    def test_google_website_link_is_supported_without_relaxing_other_platforms(self):
        self.assertEqual(normalize_competitor_identifier('https://www.example.com/products?q=1', 'google_ads'), 'example.com')
        with self.assertRaises(ValueError):
            normalize_competitor_identifier('https://www.example.com/products', 'instagram')

    def test_member_error_does_not_request_api_credentials(self):
        from core.services.competitor_public_sources import competitor_user_error
        self.assertNotIn('SEARCHAPI_API_KEY', competitor_user_error('SEARCHAPI_API_KEY yapılandırılmalı.'))
        self.assertIn('sistem yöneticisi', competitor_user_error('API token bulunamadı.'))
        self.assertEqual(competitor_user_error('Aktif abonelik gerekiyor.'), 'Aktif abonelik gerekiyor.')

    def test_public_urls_reject_executable_and_authenticated_links(self):
        from core.services.competitor_public_sources import public_url
        for url in ('javascript:alert(1)', 'https://key:secret@example.com', 'data:text/html,hello'):
            self.assertEqual(public_url(url), '')
        self.assertEqual(public_url('https://example.com/ad'), 'https://example.com/ad')

    @patch('core.management.commands.audit_competitor_access.requests.get')
    def test_meta_audit_does_not_print_provider_error_text_or_tokens(self,get):
        from core.management.commands.audit_competitor_access import probe
        get.return_value=response({'error':{'code':190,'message':'secret token input'}},400)
        result=probe('https://graph.facebook.com/v25.0/debug_token',{},lambda d:d)
        self.assertEqual(result['error_code'],190)
        self.assertNotIn('secret',json.dumps(result))


@override_settings(SEARCHAPI_API_KEY='test-searchapi', META_COMPETITOR_SOURCE='searchapi')
class SearchApiSourcesTests(TestCase):
    def setUp(self):
        user = get_user_model().objects.create_user(username='searchapi-sources')
        platform, _ = Platform.objects.get_or_create(code='instagram', defaults={'name': 'Instagram'})
        self.competitor = Competitor.objects.create(user=user, platform=platform,
            name='Example Brand', platform_identifier='examplebrand')

    @patch('core.services.competitor_searchapi.requests.post')
    def test_meta_resolves_instagram_handle_before_querying_advertiser_id(self,post):
        post.side_effect=[response({'page_results':[
            {'page_id':'123','name':'Different display name','ig_username':'examplebrand'},
            {'page_id':'999','name':'Example Brand','ig_username':'otherbrand'}]}),
            response({'ads':[{'ad_archive_id':'456','page_id':'123','is_active':True,
                              'snapshot':{'body':{'text':'Actual ad'},'images':[{'original_image_url':'https://example.com/image.jpg'}]}},
                             {'ad_archive_id':'777','page_id':'999'}]})]
        result=sync_competitor_live(self.competitor)
        self.assertEqual(result['created'],1)
        self.assertEqual(post.call_args.kwargs['json']['page_id'],'123')
        self.assertEqual(post.call_args.kwargs['json']['platforms'],'instagram')
        ad=self.competitor.ads.get()
        self.assertEqual(ad.primary_text,'Actual ad')
        self.assertEqual(ad.ad_format,'IMAGE')
        self.assertIsNone(_ad_payload(ad)['spend'])
        self.assertEqual(self.competitor.raw_data['facebook_page_id'],'123')

    @patch('core.services.competitor_searchapi.requests.post')
    def test_meta_same_username_on_multiple_pages_refuses_import(self,post):
        post.return_value=response({'page_results':[{'page_id':'123','ig_username':'examplebrand'},
                                                    {'page_id':'999','ig_username':'examplebrand'}]})
        with self.assertRaises(CompetitorSyncError):
            sync_competitor_live(self.competitor)
        self.assertEqual(post.call_count,1)
        self.assertFalse(self.competitor.ads.exists())

    @override_settings(SEARCHAPI_API_KEY='')
    @patch('core.services.competitor_searchapi.requests.post')
    def test_meta_selected_public_source_needs_own_key(self,post):
        with self.assertRaises(CompetitorSyncError):
            sync_competitor_live(self.competitor)
        post.assert_not_called()

    @patch('core.services.competitor_searchapi.requests.post')
    def test_linkedin_only_imports_exact_advertiser(self,post):
        platform,_=Platform.objects.get_or_create(code='linkedin',defaults={'name':'LinkedIn'})
        self.competitor.platform=platform
        self.competitor.save()
        post.return_value=response({'ads':[
            {'id':'123','advertiser':{'name':'Example Brand'},'ad_type':'image',
             'content':{'headline':'Actual headline','image':'https://example.com/ad.jpg'},
             'link':'https://www.linkedin.com/ad-library/detail/123'},
            {'id':'999','advertiser':{'name':'Other Brand'},'content':{}}]})
        result=sync_competitor_live(self.competitor)
        self.assertEqual(result['created'],1)
        self.assertEqual(self.competitor.ads.get().platform_ad_id,'123')
        self.assertEqual(self.competitor.ads.get().status,'UNKNOWN')
        self.assertIsNone(_ad_payload(self.competitor.ads.get())['impressions'])

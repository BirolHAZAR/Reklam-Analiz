from decimal import Decimal
import time
from unittest.mock import Mock, patch
from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone
from core.models import Platform, PlatformAccount, PlatformConnection, Campaign, CampaignMetricHistory, Ad, AdMetricHistory
from core.services import x_ads as api
from core.services.ads_integrations import IntegrationError
from core.services.x_campaign_sync import sync_x_campaigns


@override_settings(X_ADS_CONSUMER_KEY='consumer', X_ADS_CONSUMER_SECRET='private-consumer-secret',
                  X_ADS_REDIRECT_URI='https://www.reklamanaliz.net/connect/x-ads/callback/')
class XAdsTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(username='x-ads',is_staff=True,is_superuser=True)
        self.client.force_login(self.user)
        self.platform = Platform.objects.create(code='x',name='X')
        self.connection = PlatformConnection.objects.create(user=self.user,platform=self.platform,is_active=True,status='active',
            access_token='private-token',refresh_token='private-token-secret',scopes=['ads.read'],
            extra_data={'source':'x_ads_oauth','x_ads_consumer_key':'consumer','authorized_account_ids':['acc1']})
        self.account = PlatformAccount.objects.create(user=self.user,platform=self.platform,connection=self.connection,
            account_id='acc1',extra_data={'source':'x_ads_oauth','currency':'TRY','timezone':'Europe/Istanbul'})
        self.info = {'id':'acc1','name':'Account','currency':'TRY','timezone':'Europe/Istanbul'}
        self.day = timezone.localdate()
        self.metric = {'id':'cmp1','date':self.day.isoformat(),'impressions':10,'clicks':2,
                       'spend':Decimal('1.25'),'metrics_available':True}

    def test_tokens_require_owner_app_source_and_selected_account(self):
        self.assertEqual(api.account_token(self.account),('private-token','private-token-secret'))
        for changes in ({'source':'x_oauth'},{'x_ads_consumer_key':'other'},{'authorized_account_ids':[]}):
            original = self.connection.extra_data
            self.connection.extra_data = {**original,**changes}
            with self.assertRaises(IntegrationError):
                api.account_token(self.account)
            self.connection.extra_data = original
        self.connection.user = get_user_model().objects.create_user(username='other')
        with self.assertRaises(IntegrationError):
            api.account_token(self.account)

    @patch('core.services.x_ads.requests.request')
    def test_requests_use_oauth1_header_and_never_follow_redirects_or_echo_secrets(self, request):
        request.return_value = Mock(status_code=200)
        request.return_value.json.return_value = {'data':[]}
        self.assertEqual(api.read(('token','secret'),'accounts'),{'data':[]})
        import requests
        prepared = requests.Request('GET',api.API+'accounts',auth=request.call_args.kwargs['auth']).prepare()
        self.assertTrue(prepared.headers['Authorization'].startswith(b'OAuth '))
        self.assertNotIn('private-consumer-secret',str(prepared.headers))
        self.assertFalse(request.call_args.kwargs['allow_redirects'])
        for status in (302,401,403,429,500):
            request.return_value.status_code = status
            with self.assertRaises(IntegrationError) as error:
                api.read(('token','secret'),'accounts')
            self.assertNotIn('secret',str(error.exception))

    @patch('core.services.x_ads._response')
    def test_oauth_tokens_validate_callback_confirmation_and_duplicate_keys(self, response):
        response.return_value.text = 'oauth_token=temporary&oauth_token_secret=secret&oauth_callback_confirmed=true'
        self.assertEqual(api.oauth_token(),('temporary','secret'))
        for text in ('oauth_token=a&oauth_token_secret=b','oauth_token=a&oauth_token=a&oauth_token_secret=b&oauth_callback_confirmed=true'):
            response.return_value.text = text
            with self.assertRaises(IntegrationError):
                api.oauth_token()

    @patch('core.services.x_ads.read')
    def test_pagination_is_complete_bounded_and_detects_cycles(self, read):
        read.side_effect = [{'data':[{'id':'a'}],'next_cursor':'cursor'},{'data':[]}]
        self.assertEqual(api.rows(('a','b'),'accounts'),[{'id':'a'}])
        read.side_effect = None
        read.return_value = {'data':[{'id':'a'}],'next_cursor':'cursor'}
        with self.assertRaises(IntegrationError):
            api.rows(('a','b'),'accounts')

    def stats(self, impressions=10, clicks=2, spend=1250000):
        return {'time_series_length':1,'data':[{'id':'cmp1','id_data':[{'segment':None,'metrics':{
            'impressions':[impressions],'clicks':[clicks],'billed_charge_local_micro':[spend]}}]}]}

    @patch('core.services.x_ads.read')
    def test_daily_metrics_include_all_placements_and_convert_micro_currency(self, read):
        read.side_effect = [self.stats(),self.stats(0,0,0),self.stats(0,0,0)]
        result = api.report(('a','b'),'acc1',['cmp1'],'Europe/Istanbul',self.day,self.day)
        self.assertEqual(result[0]['spend'],Decimal('1.25'))
        self.assertEqual(result[0]['impressions'],10)
        self.assertEqual({call.args[2]['placement'] for call in read.call_args_list},set(api.PLACEMENTS))
        self.assertTrue(read.call_args_list[0].args[2]['start_time'].endswith('21:00:00Z'))

    @patch('core.services.x_ads.read')
    def test_missing_metrics_bad_ids_and_duplicate_entities_never_become_zero(self, read):
        for value in (None,-1,True,'1'):
            read.return_value = self.stats(spend=value)
            with self.assertRaises(IntegrationError):
                api.report(('a','b'),'acc1',['cmp1'],'UTC',self.day,self.day)
        payload = self.stats()
        payload['data'] *= 2
        read.return_value = payload
        with self.assertRaises(IntegrationError):
            api.report(('a','b'),'acc1',['cmp1'],'UTC',self.day,self.day)
        read.return_value = {'time_series_length':1,'data':[{'id':'cmp1','id_data':[{'segment':None,'metrics':{}}]}]}
        self.assertEqual(api.report(('a','b'),'acc1',['cmp1'],'UTC',self.day,self.day),[])

    @patch('core.services.x_ads.oauth_token',return_value=('temporary','temporary-secret'))
    def test_post_connect_keeps_temporary_secrets_encrypted_not_in_session(self, token):
        response = self.client.post(reverse('integration_connect',args=['x_ads']))
        self.assertEqual(response.status_code,302)
        self.assertIn('api.x.com/oauth/authorize?oauth_token=temporary',response.url)
        flow = self.client.session['x_ads_oauth']
        self.assertNotIn('temporary',str(flow))
        from django.db import connection
        with connection.cursor() as cursor:
            cursor.execute('SELECT refresh_token FROM core_platformconnection WHERE id=%s',[flow['id']])
            self.assertNotIn('temporary-secret',cursor.fetchone()[0])

    @patch('core.services.x_ads.discover_accounts')
    @patch('core.services.x_ads.oauth_token')
    @patch('core.services.plan_limits.ensure_platform_account_capacity')
    def test_callback_selection_and_replay(self, capacity, token, discover):
        token.return_value = ('temporary','temporary-secret')
        self.client.post(reverse('integration_connect',args=['x_ads']))
        token.return_value = ('access','access-secret')
        discover.return_value = [self.info]
        url = reverse('x_ads_callback')+'?oauth_token=temporary&oauth_verifier=verified'
        response = self.client.get(url)
        self.assertIn('/integrations/x_ads/accounts/',response.url)
        pending = PlatformConnection.objects.get(pk=self.client.session['ads_pending:x_ads'])
        self.assertEqual(pending.extra_data['source'],'x_ads_oauth')
        self.assertFalse(pending.is_active)
        selected = self.client.post(reverse('integration_select',args=['x_ads']),{'accounts':['acc1']})
        self.assertEqual(selected.status_code,302)
        account = PlatformAccount.objects.get(pk=self.account.pk)
        self.assertEqual(api.account_token(account),('access','access-secret'))
        calls = token.call_count
        self.client.get(url)
        self.assertEqual(token.call_count,calls)

    @patch('core.services.x_ads.oauth_token')
    def test_bad_expired_or_other_user_flow_never_exchanges_token(self, token):
        for extra in ({'created':time.time()-700},{'user':self.user.pk+1}):
            session = self.client.session
            session['x_ads_oauth'] = {'id':self.connection.pk,'created':time.time(),'user':self.user.pk,**extra}
            session.save()
            self.client.get(reverse('x_ads_callback')+'?oauth_token=bad&oauth_verifier=bad')
        token.assert_not_called()

    def sync(self, campaign_metrics, ad_metrics=None, *, fail=False):
        inventories = [{'cmp1':{'id':'cmp1','name':'Campaign','entity_status':'ACTIVE'}},
                       {'grp1':{'id':'grp1','name':'Group','campaign_id':'cmp1'}},
                       {'ad1':{'id':'ad1','line_item_id':'grp1','tweet_id':'123','entity_status':'ACTIVE'}}]
        with patch('core.services.x_ads.read',return_value={'data':self.info}), \
             patch('core.services.x_ads.inventory',side_effect=inventories), \
             patch('core.services.x_ads.report',side_effect=[campaign_metrics,IntegrationError('failure') if fail else (ad_metrics or [])]):
            return sync_x_campaigns(self.account,1,100)

    def test_measured_campaign_and_ad_import_is_idempotent(self):
        ad = {**self.metric,'id':'ad1'}
        self.sync([self.metric],[ad])
        self.sync([self.metric],[ad])
        self.assertEqual(Campaign.objects.count(),1)
        self.assertEqual(Ad.objects.count(),1)
        self.assertEqual(CampaignMetricHistory.objects.count(),1)
        self.assertEqual(AdMetricHistory.objects.count(),1)
        self.assertEqual(CampaignMetricHistory.objects.get().spend,Decimal('1.25'))

    def test_empty_reports_never_create_entities_and_late_failure_is_atomic(self):
        self.sync([])
        self.assertFalse(Campaign.objects.exists())
        with self.assertRaises(IntegrationError):
            self.sync([self.metric],fail=True)
        self.assertFalse(Campaign.objects.exists())
        self.assertFalse(Ad.objects.exists())

    def test_organic_and_ads_accounts_are_separate_in_capabilities_and_ui(self):
        from core.services.ad_sync_capabilities import supports_account_ad_sync
        from core.views.social_content import _accessible_platform_accounts
        self.assertTrue(supports_account_ad_sync(self.account))
        self.assertNotIn(self.account,list(_accessible_platform_accounts(self.user)))
        self.connection.extra_data['source'] = 'x_oauth'
        self.assertFalse(supports_account_ad_sync(self.account))

    def test_account_add_page_offers_separate_x_ads_authorization(self):
        response = self.client.get(reverse('hesap_ekle'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, reverse('integration_connect', args=['x_ads']))
        self.assertContains(response, 'X Ads bağla')

    @patch('core.services.x_ads.read')
    def test_excessive_report_budget_rejected_before_network(self, read):
        from datetime import timedelta
        with self.assertRaises(IntegrationError):
            api.report(('a','b'),'acc1',[str(i) for i in range(1000)],'UTC',self.day-timedelta(days=30),self.day)
        read.assert_not_called()

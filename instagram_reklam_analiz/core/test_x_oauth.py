import base64
import hashlib
import time
from copy import deepcopy
from datetime import timedelta
from unittest.mock import Mock, patch
from urllib.parse import parse_qs, urlsplit

from django.contrib.auth import get_user_model
from django.db import connection
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone
from core.models import PlatformAccount, PlatformConnection, SocialPost, SocialPostMetricHistory
from core.services import x_oauth as api
from core.services.ads_integrations import IntegrationError
from core.services.x_organic import sync_x_organic_content
from core.views.x_oauth import SESSION_KEY, save_account


@override_settings(X_CLIENT_ID='x-client', X_CLIENT_SECRET='private-secret',
                   X_REDIRECT_URI='https://www.reklamanaliz.net/connect/x/callback/',
                   X_API_READ_ENABLED=True, X_AUTO_SYNC_ENABLED=False, X_MAX_POSTS_PER_SYNC=10)
class XConnectionTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(username='x-owner', is_staff=True, is_superuser=True)
        self.client.force_login(self.user)
        capacity = patch('core.views.x_oauth.ensure_platform_account_capacity')
        capacity.start()
        self.addCleanup(capacity.stop)
        self.token = {'access_token': 'private-access', 'refresh_token': 'private-refresh',
                      'expires_in': 7200, 'scope': list(api.SCOPES)}
        self.profile = {'id': '123', 'username': 'owner', 'name': 'Owner'}
        self.post = {'id': '456', 'author_id': '123', 'text': 'Measured post',
                     'created_at': (timezone.now()-timedelta(days=1)).isoformat(),
                     'public_metrics': {'impression_count': 10, 'like_count': 2,
                                        'reply_count': 1, 'retweet_count': 3, 'quote_count': 1}}

    def account(self):
        return save_account(self.user, None, self.token, self.profile)

    def flow(self, **changes):
        session = self.client.session
        session[SESSION_KEY] = {'state': 'nonce', 'verifier': 'a'*64,
                               'user': self.user.pk, 'created': time.time(), 'client': None, **changes}
        session.save()

    def test_pkce_is_s256_read_only_and_post_only(self):
        self.assertEqual(self.client.get(reverse('x_connect')).status_code, 405)
        response = self.client.post(reverse('x_connect'))
        self.assertEqual(response.status_code, 302)
        query = parse_qs(urlsplit(response.url).query)
        flow = self.client.session[SESSION_KEY]
        challenge = base64.urlsafe_b64encode(hashlib.sha256(flow['verifier'].encode()).digest()).rstrip(b'=').decode()
        self.assertEqual(query['code_challenge'], [challenge])
        self.assertEqual(query['code_challenge_method'], ['S256'])
        self.assertEqual(query['scope'], [' '.join(api.SCOPES)])
        self.assertNotIn('private-secret', response.url)
        self.assertNotIn(flow['verifier'], response.url)

    @patch('core.views.x_oauth.api.exchange_code')
    def test_invalid_expired_cancelled_and_replayed_flow_never_exchanges(self, exchange):
        for changes, params in [({}, {'state': 'wrong'}), ({'created': time.time()-601}, {}),
                                ({'user': self.user.pk+1}, {}), ({'verifier': ''}, {}),
                                ({}, {'error': 'denied'})]:
            self.flow(**changes)
            self.client.get(reverse('x_oauth_callback'), {'state': 'nonce', 'code': 'code', **params})
        self.client.get(reverse('x_oauth_callback'), {'state': 'nonce', 'code': 'code'})
        exchange.assert_not_called()
        self.assertFalse(PlatformAccount.objects.exists())

    @patch('core.views.x_oauth.api.exchange_code')
    def test_callback_saves_encrypted_tokens_and_consumes_flow(self, exchange):
        exchange.return_value = self.token, self.profile
        self.flow()
        self.client.get(reverse('x_oauth_callback'), {'state': 'nonce', 'code': 'code'})
        account = PlatformAccount.objects.get()
        self.assertEqual(account.connection.extra_data['source'], 'x_oauth')
        self.assertEqual(account.account_id, '123')
        with connection.cursor() as cursor:
            cursor.execute('SELECT access_token, refresh_token FROM core_platformconnection WHERE id=%s', [account.connection_id])
            self.assertTrue(all(value.startswith('enc:v1:') for value in cursor.fetchone()))
        self.client.get(reverse('x_oauth_callback'), {'state': 'nonce', 'code': 'code'})
        self.assertEqual(exchange.call_count, 1)

    @override_settings(X_API_READ_ENABLED=False)
    @patch('core.services.x_oauth.requests.request')
    def test_paid_reads_and_connect_are_disabled_without_operator_approval(self, request):
        response = self.client.post(reverse('x_connect'))
        self.assertEqual(response.url, reverse('hesap_ekle'))
        with self.assertRaises(IntegrationError):
            api.profile('private')
        request.assert_not_called()

    @patch('core.services.x_oauth.requests.request')
    def test_http_errors_do_not_leak_tokens_and_never_follow_redirects(self, request):
        for status in (302, 401, 402, 429, 500):
            request.return_value = Mock(ok=False, status_code=status)
            request.return_value.json.return_value = {'error': 'private-access private-secret'}
            with self.assertRaises(IntegrationError) as error:
                api.profile('private-access')
            self.assertNotIn('private', str(error.exception))
            self.assertFalse(request.call_args.kwargs['allow_redirects'])

    @patch('core.services.x_oauth.request')
    def test_token_validation_requires_complete_scopes_refresh_and_finite_expiry(self, request):
        payload = {**self.token, 'token_type': 'bearer', 'scope': ' '.join(api.SCOPES)}
        request.return_value = payload
        self.assertEqual(api.token_request(grant_type='authorization_code')['scope'], list(api.SCOPES))
        for change in ({'scope': 'users.read'}, {'refresh_token': ''}, {'expires_in': True},
                       {'expires_in': 0}, {'token_type': 'other'}, {'token_type': None}, {'token_type': 1}):
            request.return_value = {**payload, **change}
            with self.assertRaises(IntegrationError):
                api.token_request(grant_type='authorization_code')

    @patch('core.services.x_oauth.request')
    def test_profile_rejects_malformed_username(self, request):
        for username in (None, 123, {}, 'wrong/name', 'a' * 51):
            request.return_value = {'data': {'id': '123', 'username': username}}
            with self.assertRaises(IntegrationError):
                api.profile('private')

    @patch('core.services.x_oauth.token_request')
    @patch('core.services.x_oauth.profile')
    def test_refresh_checks_identity_before_rotating_tokens(self, profile, token_request):
        account = self.account()
        PlatformConnection.objects.filter(pk=account.connection_id).update(token_expiry=timezone.now()-timedelta(seconds=1))
        token_request.return_value = {**self.token, 'access_token': 'rotated', 'refresh_token': 'rotated-refresh'}
        profile.side_effect = IntegrationError('identity mismatch')
        with self.assertRaises(IntegrationError):
            api.access_token(account)
        account.connection.refresh_from_db()
        self.assertEqual(account.connection.access_token, 'private-access')
        profile.side_effect = None
        self.assertEqual(api.access_token(account), 'rotated')
        account.refresh_from_db()
        self.assertEqual(account.refresh_token, 'rotated-refresh')

    def test_source_identity_and_application_binding_are_required(self):
        account = self.account()
        for changes in ({'source': 'token_verification'}, {'client_id': 'different'}, {'profile': {'id': '321'}}):
            account.connection.extra_data = {**account.extra_data, **changes}
            account.connection.save()
            with self.assertRaises(IntegrationError):
                api.access_token(account)

    def sync(self, account, pages, **kwargs):
        with patch('core.services.x_organic.api.access_token', return_value='private'), \
             patch('core.services.x_organic.api.posts', side_effect=pages):
            return sync_x_organic_content(account, **kwargs)

    def test_measured_import_is_idempotent_and_unknown_metrics_stay_unavailable(self):
        account = self.account()
        self.assertTrue(self.sync(account, [([self.post], None)])['success'])
        self.sync(account, [([self.post], None)])
        self.assertEqual(SocialPost.objects.count(), 1)
        metric = SocialPostMetricHistory.objects.get()
        self.assertEqual(metric.impressions, 10)
        self.assertEqual(metric.engagement, 7)
        from core.services.organic_insights import summarize_snapshots
        totals = summarize_snapshots([metric])
        self.assertIsNone(totals['reach'])
        self.assertIsNone(totals['views'])
        self.assertIsNone(totals['saves'])

    def test_missing_invalid_metrics_and_wrong_identity_never_write(self):
        account = self.account()
        cases = []
        for value in (None, True, -1, '0'):
            row = deepcopy(self.post)
            row['public_metrics']['impression_count'] = value
            cases.append(row)
        cases += [{**self.post, 'author_id': '321'}, {**self.post, 'created_at': '2026-99-99T00:00:00Z'}]
        for row in cases:
            self.assertFalse(self.sync(account, [([row], None)])['success'])
            self.assertFalse(SocialPost.objects.exists())

    def test_empty_response_and_real_measured_zero(self):
        account = self.account()
        self.assertTrue(self.sync(account, [([], None)])['success'])
        self.assertFalse(SocialPost.objects.exists())
        row = deepcopy(self.post)
        row['public_metrics'] = dict.fromkeys(row['public_metrics'], 0)
        self.assertTrue(self.sync(account, [([row], None)])['success'])
        self.assertEqual(SocialPostMetricHistory.objects.get().impressions, 0)

    def test_later_page_failure_and_duplicate_do_not_commit_partial_rows(self):
        account = self.account()
        for pages in [([self.post], 'cursor'),]:
            result = self.sync(account, [pages, IntegrationError('unavailable')])
            self.assertFalse(result['success'])
            self.assertFalse(SocialPost.objects.exists())
        self.assertFalse(self.sync(account, [([self.post, self.post], None)])['success'])
        self.assertFalse(SocialPost.objects.exists())

    @patch('core.services.x_oauth.request')
    def test_api_pagination_validation(self, request):
        for payload in ({'meta': {'result_count': 1}}, {'data': [], 'meta': {'result_count': True}},
                        {'data': [], 'meta': {'result_count': 0, 'next_token': 12}}):
            request.return_value = payload
            with self.assertRaises(IntegrationError):
                api.posts('private', '123')

    @patch('core.services.x_oauth.requests.request')
    def test_token_health_does_not_spend_credits_or_disable_refreshable_account(self, request):
        account = self.account()
        account.connection.token_expiry = timezone.now() - timedelta(hours=1)
        from core.services.platform_token_service import _validate_connection
        result = _validate_connection(account.connection)
        self.assertTrue(result['valid'])
        self.assertEqual(result['validation'], 'local_expiry_only')
        request.assert_not_called()

    @override_settings(X_MAX_POSTS_PER_SYNC=5)
    def test_sync_never_requests_another_paid_page_past_cap(self):
        account = self.account()
        rows = [{**self.post, 'id': str(456+i)} for i in range(5)]
        with patch('core.services.x_organic.api.access_token', return_value='private'), \
             patch('core.services.x_organic.api.posts', return_value=(rows, 'more')) as posts:
            self.assertEqual(sync_x_organic_content(account, limit=100)['fetched'], 5)
            posts.assert_called_once()
            self.assertEqual(posts.call_args.kwargs['max_results'], 5)

    def test_client_page_renders_disabled_x_link_without_requesting_credits(self):
        with override_settings(X_API_READ_ENABLED=False):
            response = self.client.get(reverse('hesap_ekle'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'X API veri okuma kapalı')

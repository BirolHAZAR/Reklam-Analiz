from datetime import timedelta
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.test import RequestFactory, TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from core.models import AgencyClient, Organization, OrganizationMember, Platform, PlatformAccount, PlatformConnection
from core.services.cache_service import CacheService


@override_settings(FACEBOOK_APP_ID='app', FACEBOOK_APP_SECRET='secret', FACEBOOK_REDIRECT_URI='https://reklamanaliz.net/connect/facebook/callback/')
class MultiplePlatformAccountTests(TestCase):
    def setUp(self):
        cache.clear()
        self.user = get_user_model().objects.create_user(username='multiple-owner')
        self.client.force_login(self.user)
        self.platform = Platform.objects.create(code='facebook', name='Facebook')

    def pending(self, choices):
        connection = PlatformConnection.objects.create(
            user=self.user, platform=self.platform, access_token='test-token',
            is_active=False, status='disconnected', token_expiry=timezone.now()+timedelta(hours=1),
            extra_data={'source': 'ads_oauth', 'pending': True, 'choices': choices},
        )
        session = self.client.session
        session['ads_pending:facebook'] = connection.pk
        session.save()
        return connection

    def visible_ids(self):
        response = self.client.get('/api/campaign-panel/accounts/', {'platform': 'facebook'})
        self.assertEqual(response.status_code, 200)
        return {row['account_id'] for platform in response.json()['platforms'] for row in platform['accounts']}

    @patch('core.services.plan_limits.ensure_platform_account_capacity')
    def test_second_selection_keeps_first_account_and_refreshes_warm_cache(self, limit):
        first = self.pending([{'id': 'act_1', 'name': 'First account'}])
        with self.captureOnCommitCallbacks(execute=True):
            response = self.client.post(reverse('integration_select', args=['facebook']), {'accounts': ['act_1']})
        self.assertEqual(response.status_code, 302)
        self.assertEqual(self.visible_ids(), {'act_1'})
        cache.set(CacheService.make_key('invalidate_guard', 'user', self.user.pk), 1, timeout=60)
        second = self.pending([{'id': 'act_2', 'name': 'Second account'}])
        self.assertContains(self.client.get(reverse('integration_select', args=['facebook'])), 'First account')
        with self.captureOnCommitCallbacks(execute=True):
            response = self.client.post(reverse('integration_select', args=['facebook']), {'accounts': ['act_2']})
        self.assertEqual(response.status_code, 302)
        self.assertEqual(self.visible_ids(), {'act_1', 'act_2'})
        first.refresh_from_db()
        self.assertTrue(first.is_active)
        self.assertEqual(PlatformAccount.objects.get(account_id='act_1').connection_id, first.pk)
        self.assertEqual(PlatformAccount.objects.get(account_id='act_2').connection_id, second.pk)
        response = self.client.get(reverse('platform_connections'))
        self.assertContains(response, 'First account')
        self.assertContains(response, 'Second account')

    @patch('core.services.plan_limits.ensure_platform_account_capacity')
    def test_selecting_multiple_accounts_and_reauthorizing_one_preserves_sibling(self, limit):
        first = self.pending([{'id': 'act_1', 'name': 'First'}, {'id': 'act_2', 'name': 'Second'}])
        url = reverse('integration_select', args=['facebook'])
        self.client.post(url, {'accounts': ['act_1', 'act_2']})
        second = self.pending([{'id': 'act_1', 'name': 'First'}])
        self.assertContains(self.client.get(url), 'Zaten bağlı')
        self.client.post(url, {'accounts': ['act_1']})
        self.assertEqual(PlatformAccount.objects.count(), 2)
        self.assertEqual(PlatformAccount.objects.get(account_id='act_2').connection_id, first.pk)
        self.assertEqual(PlatformAccount.objects.get(account_id='act_1').connection_id, second.pk)
        first.refresh_from_db()
        self.assertTrue(first.is_active)

    def test_agency_member_sees_scoped_accounts_without_owner_edit_controls(self):
        member = get_user_model().objects.create_user(username='viewer')
        outsider = get_user_model().objects.create_user(username='outsider')
        organization = Organization.objects.create(owner=self.user, name='Agency')
        OrganizationMember.objects.create(organization=organization, user=member, role=OrganizationMember.ROLE_VIEWER)
        brand = AgencyClient.objects.create(organization=organization, name='Brand')
        other_brand = AgencyClient.objects.create(organization=organization, name='Other brand')
        account = PlatformAccount.objects.create(user=self.user, platform=self.platform, account_id='act_1', account_name='Visible brand account', agency_client=brand)
        PlatformAccount.objects.create(user=self.user, platform=self.platform, account_id='act_2', account_name='Other scoped account', agency_client=other_brand)
        PlatformAccount.objects.create(user=outsider, platform=self.platform, account_id='act_3', account_name='Private outsider account')
        from core.views.platform_connect import platform_connections
        from core.views.hesap_ekle import hesap_ekle_view
        for view in [platform_connections, hesap_ekle_view]:
            request = RequestFactory().get('/accounts/', {'agency_client': brand.pk})
            request.user = member
            request.session = {}
            response = view(request)
            self.assertContains(response, 'Visible brand account')
            self.assertNotContains(response, 'Other scoped account')
            self.assertNotContains(response, 'Private outsider account')
            self.assertNotContains(response, reverse('platform_account_delete', args=[account.pk]))
            self.assertNotContains(response, reverse('hesap_sil', args=[account.pk]))

"""Separate OAuth 1.0a authorization for X advertising accounts."""
import secrets
import time
from urllib.parse import urlencode

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.shortcuts import redirect
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_GET, require_POST
from core.models import Platform, PlatformConnection
from core.services import x_ads as api
from core.services.ads_integrations import IntegrationError, configuration
from core.views.ads_integrations import _client

SESSION_KEY = 'x_ads_oauth'


@login_required
@require_POST
@never_cache
def connect(request):
    try:
        client = _client(request, request.POST.get('agency_client'))
        key, _, _ = configuration('x_ads')
        token, secret = api.oauth_token()
        platform, _ = Platform.objects.get_or_create(code='x', defaults={'name':'X','is_active':True})
        connection = PlatformConnection.objects.create(user=request.user, platform=platform, name='X Ads',
            access_token=token, refresh_token=secret, is_active=False, status='disconnected',
            scopes=['ads.read'], extra_data={'source':'x_ads_request', 'x_ads_consumer_key':key,
                                            'agency_client':client.pk if client else None})
        request.session[SESSION_KEY] = {'id':connection.pk, 'user':request.user.pk, 'created':time.time()}
        return redirect('https://api.x.com/oauth/authorize?' + urlencode({'oauth_token':token}))
    except IntegrationError as exc:
        messages.error(request, str(exc))
        return redirect('platform_connections')


@login_required
@require_GET
@never_cache
def callback(request):
    flow = request.session.pop(SESSION_KEY, None)
    if (not isinstance(flow, dict) or flow.get('user') != request.user.pk
            or not isinstance(flow.get('created'), (int,float))
            or not 0 <= time.time()-flow['created'] <= 600):
        messages.error(request, 'X Ads bağlantı isteği geçersiz veya süresi doldu.')
        return redirect('platform_connections')
    try:
        with transaction.atomic():
            connection = PlatformConnection.objects.select_for_update().filter(pk=flow.get('id'), user=request.user,
                platform__code='x', extra_data__source='x_ads_request', is_active=False).first()
            if connection is None:
                raise IntegrationError('X Ads bağlantısı zaten kullanılmış veya geçersiz.')
            # Consume before exchange; a failed or cancelled flow cannot be replayed.
            temporary = connection.access_token, connection.refresh_token
            connection.access_token, connection.refresh_token = '', ''
            connection.extra_data = {**connection.extra_data, 'source':'x_ads_consumed'}
            connection.save()
        if (request.GET.get('denied') or not request.GET.get('oauth_verifier')
                or not secrets.compare_digest(temporary[0].encode(), request.GET.get('oauth_token','').encode())):
            raise IntegrationError('X Ads okuma yetkisi verilmedi veya istek eşleşmedi.')
        key, _, _ = configuration('x_ads')
        if connection.extra_data.get('x_ads_consumer_key') != key:
            raise IntegrationError('X Ads uygulama ayarları değişti. Yeniden bağlayın.')
        _client(request, connection.extra_data.get('agency_client'))
        credentials = api.oauth_token(temporary=temporary, verifier=request.GET['oauth_verifier'])
        choices = api.discover_accounts(credentials)
        if not choices:
            raise IntegrationError('Bu X kullanıcısının erişebildiği reklam hesabı bulunamadı. X Ads hesabına erişimi olan kullanıcıyla bağlanın.')
        connection.access_token, connection.refresh_token = credentials
        connection.extra_data = {**connection.extra_data, 'source':'x_ads_oauth', 'pending':True,
            'choices':choices, 'authorized_account_ids':[row['id'] for row in choices]}
        connection.save()
        request.session['ads_pending:x_ads'] = connection.pk
        return redirect('integration_select', provider='x_ads')
    except IntegrationError as exc:
        messages.error(request, str(exc))
        return redirect('platform_connections')

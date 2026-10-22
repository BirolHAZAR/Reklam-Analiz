"""Connect an explicitly authorized X account without using social sign-in."""
import secrets
import time
from datetime import timedelta

from django.contrib import messages
from django.contrib.auth import get_user_model
from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.shortcuts import redirect
from django.utils import timezone
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_GET, require_POST
from core.models import Organization, Platform, PlatformAccount, PlatformConnection
from core.services import x_oauth as api
from core.services.ads_integrations import IntegrationError, configuration
from core.services.plan_limits import ensure_platform_account_capacity
from core.views.ads_integrations import _client

SESSION_KEY = 'x_reporting_oauth'


@login_required
@require_POST
@never_cache
def connect(request):
    try:
        client = _client(request, request.POST.get('agency_client'))
        api.require_read_access()
        state, verifier = secrets.token_urlsafe(32), secrets.token_urlsafe(48)
        url = api.authorization_url(state, verifier)
    except IntegrationError as exc:
        messages.error(request, str(exc))
        return redirect('hesap_ekle')
    request.session[SESSION_KEY] = {'state': state, 'verifier': verifier, 'user': request.user.pk,
                                  'created': time.time(), 'client': client.pk if client else None}
    return redirect(url)


@transaction.atomic
def save_account(user, client, token, profile):
    get_user_model().objects.select_for_update().get(pk=user.pk)
    account_id = profile['id']
    if client:
        Organization.objects.select_for_update().get(pk=client.organization_id)
        if PlatformAccount.objects.filter(platform__code='x', account_id=account_id,
                agency_client__organization=client.organization).exclude(user=user).exists():
            raise IntegrationError('Bu X hesabı ajansınızda zaten kayıtlı.')
    platform, _ = Platform.objects.get_or_create(code='x', defaults={'name': 'X', 'is_active': True})
    old = PlatformAccount.objects.filter(user=user, platform=platform, account_id=account_id).first()
    if old and (old.extra_data or {}).get('source') == 'x_ads_oauth':
        raise IntegrationError('Bu kimlik bir X reklam hesabına ait; organik bağlantıyla değiştirilemez.')
    if old and old.agency_client_id != (client.pk if client else None):
        raise IntegrationError('Bu X hesabı başka bir müşteriyle eşleştirilmiş.')
    ensure_platform_account_capacity(user, [('x', account_id)], organization=client.organization if client else None)
    client_id, _, _ = configuration('x')
    metadata = {'source': 'x_oauth', 'client_id': client_id, 'profile': profile}
    expiry = timezone.now() + timedelta(seconds=token['expires_in'])
    name = ('@' + profile['username'])[:200]
    connection = PlatformConnection.objects.create(user=user, platform=platform, name=name,
        access_token=token['access_token'], refresh_token=token['refresh_token'], token_expiry=expiry,
        scopes=token['scope'], is_active=True, status='active', extra_data=metadata)
    account, _ = PlatformAccount.objects.update_or_create(user=user, platform=platform, account_id=account_id,
        defaults={'account_name': name, 'agency_client': client, 'connection': connection,
                  'access_token': token['access_token'], 'refresh_token': token['refresh_token'],
                  'token_expiry': expiry, 'is_active': True,
                  'extra_data': {**((old.extra_data or {}) if old else {}), **metadata}})
    if old and old.connection_id:
        PlatformConnection.objects.filter(pk=old.connection_id, accounts__isnull=True).update(is_active=False, status='disconnected')
    return account


@login_required
@require_GET
@never_cache
def callback(request):
    flow = request.session.pop(SESSION_KEY, None)
    if (not isinstance(flow, dict) or flow.get('user') != request.user.pk
            or not isinstance(flow.get('created'), (int, float))
            or not 0 <= time.time() - flow['created'] <= 600
            or not isinstance(flow.get('verifier'), str) or not 43 <= len(flow['verifier']) <= 128
            or not secrets.compare_digest(str(flow.get('state', '')).encode(), request.GET.get('state', '').encode())):
        messages.error(request, 'X bağlantı isteği geçersiz veya süresi dolmuş. Yeniden bağlayın.')
        return redirect('hesap_ekle')
    if request.GET.get('error') or not request.GET.get('code'):
        messages.info(request, 'X okuma izni verilmedi; hesap bağlanmadı.')
        return redirect('hesap_ekle')
    try:
        client = _client(request, flow.get('client'))
        api.require_read_access()
        token, profile = api.exchange_code(request.GET['code'], flow['verifier'])
        save_account(request.user, client, token, profile)
    except IntegrationError as exc:
        messages.error(request, str(exc))
        return redirect('hesap_ekle')
    messages.success(request, 'X hesabı bağlandı. Organik İçerik ekranından metrikleri eşitleyebilirsiniz.')
    return redirect('hesap_ekle')

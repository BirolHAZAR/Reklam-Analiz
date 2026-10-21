"""Read-only X OAuth 2.0 PKCE and bounded, explicitly enabled API reads."""
import base64
import hashlib
from datetime import timedelta
from urllib.parse import urlencode

import requests
from django.conf import settings
from django.db import transaction
from django.utils import timezone
from core.models import PlatformConnection
from core.services.ads_integrations import IntegrationError, configuration

SCOPES = ('tweet.read', 'users.read', 'offline.access')
API = 'https://api.x.com/2/'


def request(method, path, **kwargs):
    try:
        response = requests.request(method, API + path, timeout=30, allow_redirects=False, **kwargs)
        payload = response.json()
    except (requests.RequestException, ValueError):
        raise IntegrationError('X API isteği tamamlanamadı. Yeniden deneyin.') from None
    if response.status_code == 402:
        raise IntegrationError('X API kredisi yetersiz. Geliştirici konsolundaki bakiyeyi kontrol edin.')
    if response.status_code == 429:
        raise IntegrationError('X API kullanım sınırına ulaşıldı. Daha sonra tekrar deneyin.')
    if not response.ok or not isinstance(payload, dict) or payload.get('errors') or payload.get('error'):
        raise IntegrationError('X isteği reddedildi. API erişimini ve hesap izinlerini kontrol edin.')
    return payload


def require_read_access():
    if not getattr(settings, 'X_API_READ_ENABLED', False):
        raise IntegrationError('X API veri okuma kapalı. Kredi ve kullanım onayı sonrasında yönetici açmalıdır.')


def authorization_url(state, verifier):
    client_id, _, uri = configuration('x')
    challenge = base64.urlsafe_b64encode(hashlib.sha256(verifier.encode('ascii')).digest()).rstrip(b'=').decode('ascii')
    return 'https://x.com/i/oauth2/authorize?' + urlencode({
        'response_type': 'code', 'client_id': client_id, 'redirect_uri': uri,
        'scope': ' '.join(SCOPES), 'state': state, 'code_challenge': challenge,
        'code_challenge_method': 'S256',
    })


def token_request(**data):
    client_id, secret, _ = configuration('x')
    result = request('POST', 'oauth2/token', auth=(client_id, secret), data=data)
    scope = result.get('scope')
    expires = result.get('expires_in')
    if (not isinstance(scope, str) or not set(SCOPES).issubset(scope.split())
            or not isinstance(expires, int) or isinstance(expires, bool) or not 0 < expires <= 31536000
            or not isinstance(result.get('token_type'), str) or result['token_type'].lower() != 'bearer'
            or not all(isinstance(result.get(k), str) and result[k] for k in ('access_token', 'refresh_token'))):
        raise IntegrationError('X okuma ve çevrimdışı erişim izinleri doğrulanamadı. Yeniden bağlayın.')
    return {key: result[key] for key in ('access_token', 'refresh_token', 'expires_in')} | {'scope': scope.split()}


def profile(token, expected_id=None):
    require_read_access()
    payload = request('GET', 'users/me', headers={'Authorization': f'Bearer {token}'},
                      params={'user.fields': 'id,name,username,description,profile_image_url,public_metrics'})
    user = payload.get('data')
    if (not isinstance(user, dict) or not isinstance(user.get('id'), str) or not user['id'].isascii()
            or not user['id'].isdigit() or len(user['id']) > 100
            or not isinstance(user.get('username'), str) or not user['username']
            or len(user['username']) > 50 or not user['username'].isascii()
            or not user['username'].replace('_', '').isalnum()
            or (expected_id is not None and user['id'] != expected_id)):
        raise IntegrationError('X hesap kimliği doğrulanamadı.')
    return user


def exchange_code(code, verifier):
    _, _, uri = configuration('x')
    token = token_request(grant_type='authorization_code', code=code, redirect_uri=uri, code_verifier=verifier)
    return token, profile(token['access_token'])


@transaction.atomic
def access_token(account):
    if not account.is_active or account.platform.code != 'x' or not account.connection_id:
        raise IntegrationError('X hesabını yeniden bağlayın.')
    connection = PlatformConnection.objects.select_for_update().get(pk=account.connection_id)
    metadata = connection.extra_data or {}
    client_id, _, _ = configuration('x')
    if (connection.user_id != account.user_id or connection.platform_id != account.platform_id
            or not connection.is_active or connection.status != 'active'
            or metadata.get('source') != 'x_oauth' or metadata.get('client_id') != client_id
            or metadata.get('profile', {}).get('id') != account.account_id
            or not set(SCOPES).issubset(connection.scopes or [])):
        raise IntegrationError('X uygulaması, hesap kimliği veya okuma izni değişmiş. Yeniden bağlayın.')
    if not connection.token_expiry or connection.token_expiry <= timezone.now() + timedelta(minutes=2):
        if not connection.refresh_token:
            raise IntegrationError('X erişimi sona erdi. Yeniden bağlayın.')
        token = token_request(grant_type='refresh_token', refresh_token=connection.refresh_token)
        # Verify the refreshed identity before replacing any encrypted tokens.
        profile(token['access_token'], account.account_id)
        connection.access_token, connection.refresh_token = token['access_token'], token['refresh_token']
        connection.token_expiry = timezone.now() + timedelta(seconds=token['expires_in'])
        connection.scopes = token['scope']
        connection.save(update_fields=['access_token', 'refresh_token', 'token_expiry', 'scopes', 'updated_at'])
        account.access_token, account.refresh_token = connection.access_token, connection.refresh_token
        account.token_expiry = connection.token_expiry
        account.save(update_fields=['access_token', 'refresh_token', 'token_expiry', 'updated_at'])
    if not connection.access_token:
        raise IntegrationError('X erişimi bulunamadı. Yeniden bağlayın.')
    return connection.access_token


def posts(token, user_id, cursor=None, *, max_results=10):
    require_read_access()
    if not isinstance(user_id, str) or not user_id.isascii() or not user_id.isdigit():
        raise IntegrationError('X hesap kimliği geçersiz.')
    params = {'max_results': max(5, min(int(max_results), 100)),
              'tweet.fields': 'id,text,author_id,created_at,public_metrics', 'exclude': 'retweets'}
    if cursor is not None:
        params['pagination_token'] = cursor
    payload = request('GET', f'users/{user_id}/tweets', headers={'Authorization': f'Bearer {token}'}, params=params)
    meta = payload.get('meta')
    rows = payload.get('data', [])
    if (not isinstance(meta, dict) or not isinstance(rows, list)
            or type(meta.get('result_count')) is not int or meta['result_count'] != len(rows)
            or len(rows) > params['max_results']
            or any(not isinstance(row, dict) for row in rows)):
        raise IntegrationError('X gönderi listesi doğrulanamadı.')
    cursor = meta.get('next_token')
    if cursor is not None and (not isinstance(cursor, str) or not cursor or len(cursor) > 2048):
        raise IntegrationError('X gönderi sayfalaması doğrulanamadı.')
    return rows, cursor

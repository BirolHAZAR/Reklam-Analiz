"""X Ads API v12: OAuth 1.0a and strictly read-only, bounded reporting.

Token secrets use the encrypted refresh_token field; OAuth 1 tokens do not refresh.
Organic OAuth 2 credentials are deliberately incompatible with this connection.
"""
from datetime import datetime, time, timedelta, timezone as utc_timezone
from decimal import Decimal
import re
from urllib.parse import parse_qsl
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

import requests
from requests_oauthlib import OAuth1
from core.services.ads_integrations import IntegrationError, configuration

API = 'https://ads-api.x.com/12/'
PLACEMENTS = ('ALL_ON_TWITTER', 'SPOTLIGHT', 'TREND')


def identifier(value):
    if not isinstance(value, str) or not re.fullmatch(r'[a-zA-Z0-9]{1,100}', value):
        raise IntegrationError('X Ads hesap veya reklam kimliği doğrulanamadı.')
    return value


def auth(token='', secret='', **kwargs):
    key, consumer_secret, _ = configuration('x_ads')
    return OAuth1(key, client_secret=consumer_secret, resource_owner_key=token or None,
                  resource_owner_secret=secret or None, **kwargs)


def _response(method, url, **kwargs):
    try:
        response = requests.request(method, url, timeout=30, allow_redirects=False, **kwargs)
    except requests.RequestException:
        raise IntegrationError('X Ads bağlantısı tamamlanamadı. Yeniden deneyin.') from None
    if response.status_code != 200:
        if response.status_code in (401, 403):
            raise IntegrationError('X Ads uygulama onayını ve reklam hesabı okuma yetkisini kontrol edin; hesabı yeniden bağlayın.')
        if response.status_code == 429:
            raise IntegrationError('X Ads istek sınırına ulaşıldı. Daha sonra tekrar deneyin.')
        raise IntegrationError('X Ads isteği tamamlanamadı.')
    return response


def oauth_token(*, temporary=None, verifier=None):
    _, _, callback = configuration('x_ads')
    if temporary is None:
        signer = auth(callback_uri=callback)
        path = 'request_token'
    else:
        signer = auth(*temporary, verifier=verifier)
        path = 'access_token'
    response = _response('POST', 'https://api.x.com/oauth/' + path, auth=signer)
    pairs = parse_qsl(response.text, keep_blank_values=True)
    data = dict(pairs)
    if (len(data) != len(pairs) or not all(isinstance(data.get(k), str) and 0 < len(data[k]) <= 2000
            for k in ('oauth_token', 'oauth_token_secret'))
            or (temporary is None and data.get('oauth_callback_confirmed') != 'true')):
        raise IntegrationError('X Ads OAuth yanıtı doğrulanamadı.')
    return data['oauth_token'], data['oauth_token_secret']


def read(credentials, path, params=None):
    # Callers supply only fixed resource paths and validated identifiers.
    response = _response('GET', API + path, auth=auth(*credentials), params=params or {})
    try:
        payload = response.json()
    except ValueError:
        raise IntegrationError('X Ads yanıtı okunamadı.') from None
    if not isinstance(payload, dict) or payload.get('errors') or payload.get('error'):
        raise IntegrationError('X Ads verisi okunamadı.')
    return payload


def rows(credentials, path, params=None, *, limit=10000):
    result, seen, cursor = [], set(), None
    for _ in range(100):
        payload = read(credentials, path, {**(params or {}), 'count': min(200, limit),
                                        **({'cursor': cursor} if cursor else {})})
        data = payload.get('data')
        if not isinstance(data, list) or any(not isinstance(row, dict) for row in data):
            raise IntegrationError('X Ads listesi eksik veya geçersiz.')
        result.extend(data)
        if len(result) > limit:
            raise IntegrationError('X Ads kayıt sınırı aşıldı. Daha kısa bir dönem seçin.')
        cursor = payload.get('next_cursor')
        if cursor is None:
            return result
        if not isinstance(cursor, str) or not cursor or len(cursor) > 2000 or cursor in seen or not data:
            raise IntegrationError('X Ads sayfalaması tamamlanamadı.')
        seen.add(cursor)
    raise IntegrationError('X Ads sayfa sınırı aşıldı.')


def account_info(row):
    if not isinstance(row, dict):
        raise IntegrationError('X reklam hesabı okunamadı.')
    aid = identifier(row.get('id'))
    currency, zone = row.get('currency'), row.get('timezone')
    try:
        ZoneInfo(zone if isinstance(zone, str) else '')
    except (ValueError, ZoneInfoNotFoundError):
        raise IntegrationError('X reklam hesabının saat dilimi doğrulanamadı.') from None
    if not isinstance(currency, str) or not re.fullmatch(r'[A-Z]{3}', currency):
        raise IntegrationError('X reklam hesabının para birimi doğrulanamadı.')
    return {'id': aid, 'name': row.get('name') or aid, 'currency': currency,
            'timezone': zone, 'kind': 'ad_account'}


def discover_accounts(credentials):
    result, ids = [], set()
    for row in rows(credentials, 'accounts'):
        if row.get('deleted') is True:
            continue
        info = account_info(row)
        if info['id'] in ids:
            raise IntegrationError('X reklam hesabı listesinde yinelenen hesap var.')
        ids.add(info['id'])
        result.append(info)
    return result


def account_token(account):
    key, _, _ = configuration('x_ads')
    conn = account.connection
    if (not account.is_active or account.platform.code != 'x' or not conn
            or not conn.is_active or conn.status != 'active' or conn.user_id != account.user_id
            or conn.platform_id != account.platform_id or not conn.access_token or not conn.refresh_token
            or (conn.extra_data or {}).get('source') != 'x_ads_oauth'
            or conn.extra_data.get('x_ads_consumer_key') != key
            or account.account_id not in conn.extra_data.get('authorized_account_ids', [])):
        raise IntegrationError('X reklam hesabını ayrı X Ads bağlantısından yeniden bağlayın.')
    identifier(account.account_id)
    return conn.access_token, conn.refresh_token


def inventory(credentials, account_id, kind='campaigns', *, limit=10000):
    if kind not in {'campaigns', 'line_items', 'promoted_tweets'}:
        raise IntegrationError('Geçersiz X Ads envanteri.')
    result = {}
    for row in rows(credentials, f'accounts/{identifier(account_id)}/{kind}', {'with_deleted': 'true'}, limit=limit):
        cid = identifier(row.get('id'))
        if cid in result or row.get('account_id', account_id) != account_id:
            raise IntegrationError('X Ads envanteri hesapla eşleşmiyor.')
        if kind != 'promoted_tweets' and (not isinstance(row.get('name'), str) or not row['name']):
            raise IntegrationError('X Ads kampanya veya grup adı eksik.')
        result[cid] = row
    return result


def report(credentials, account_id, ids, zone, start, end, *, entity='CAMPAIGN', limit=10000):
    """Small daily batches; no async job creation or campaign mutation scopes.

    Null arrays mean unavailable data, never measured zero. Partial data aborts
    the complete import rather than replacing a stored value with zero.
    """
    if entity not in {'CAMPAIGN', 'PROMOTED_TWEET'} or not 0 <= (end-start).days < 31:
        raise IntegrationError('X Ads raporu için en fazla 31 günlük dönem seçin.')
    ids = [identifier(value) for value in ids]
    if len(ids) != len(set(ids)):
        raise IntegrationError('X Ads rapor kimlikleri yineleniyor.')
    if ((len(ids)+19)//20) * (((end-start).days+7)//7) * len(PLACEMENTS) > 100:
        raise IntegrationError('X Ads rapor istek sınırı aşılıyor. Daha kısa bir dönem seçin.')
    tz = ZoneInfo(zone)
    totals = {}
    current = start
    while current <= end:
        until = min(end, current + timedelta(days=6))
        days = (until-current).days + 1
        def stamp(day):
            return datetime.combine(day, time.min, tzinfo=tz).astimezone(utc_timezone.utc).isoformat().replace('+00:00', 'Z')
        for offset in range(0, len(ids), 20):
            batch = ids[offset:offset+20]
            for placement in PLACEMENTS:
                payload = read(credentials, f'stats/accounts/{identifier(account_id)}', {
                    'entity': entity, 'entity_ids': ','.join(batch), 'start_time': stamp(current),
                    'end_time': stamp(until+timedelta(days=1)), 'granularity': 'DAY',
                    'metric_groups': 'ENGAGEMENT,BILLING', 'placement': placement})
                data = payload.get('data')
                if (not isinstance(data, list) or type(payload.get('time_series_length')) is not int
                        or payload['time_series_length'] != days):
                    raise IntegrationError('X Ads günlük rapor uzunluğu doğrulanamadı.')
                seen = set()
                for row in data:
                    if not isinstance(row, dict) or row.get('id') not in batch or row['id'] in seen:
                        raise IntegrationError('X Ads raporu seçili nesnelerle eşleşmiyor.')
                    seen.add(row['id'])
                    segments = row.get('id_data')
                    if (not isinstance(segments, list) or len(segments) != 1 or not isinstance(segments[0], dict)
                            or segments[0].get('segment') is not None or not isinstance(segments[0].get('metrics'), dict)):
                        raise IntegrationError('X Ads metrikleri doğrulanamadı.')
                    arrays = [segments[0]['metrics'].get(k) for k in ('impressions','clicks','billed_charge_local_micro')]
                    if all(value is None for value in arrays):
                        continue
                    if any(not isinstance(value, list) or len(value) != days for value in arrays):
                        raise IntegrationError('X Ads metrikleri eksik; hiçbir veri kaydedilmedi.')
                    for i in range(days):
                        values = [value[i] for value in arrays]
                        if all(value is None for value in values):
                            continue
                        if any(type(value) is not int or not 0 <= value < 2**63 for value in values):
                            raise IntegrationError('X Ads günlük metrikleri eksik veya geçersiz.')
                        key = row['id'], current+timedelta(days=i)
                        total = totals.setdefault(key, [0,0,0])
                        for j, value in enumerate(values):
                            total[j] += value
                            if total[j] >= 2**63:
                                raise IntegrationError('X Ads günlük metrik sınırı aşıldı.')
                        if len(totals) > limit:
                            raise IntegrationError('X Ads raporu plan sınırını aşıyor.')
        current = until+timedelta(days=1)
    return [{'id': cid, 'date': day.isoformat(), 'impressions': v[0], 'clicks': v[1],
             'spend': Decimal(v[2])/Decimal(1000000), 'metrics_available': True}
            for (cid,day),v in sorted(totals.items())]

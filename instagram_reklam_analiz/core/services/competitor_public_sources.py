"""Public advertiser sources; never use a customer's private Ads API for rivals."""
from datetime import datetime, timedelta, timezone as dt_timezone
from concurrent.futures import ThreadPoolExecutor
import re
from urllib.parse import urlencode, urlsplit, parse_qs
import requests
from django.conf import settings
from django.utils import timezone
from core.models import Ad, Creative, AdMetricHistory, CompetitorSourceSetting
from core.services.competitor_live_sync import CompetitorSyncError, CompetitorAdvertiserChoiceRequired, _normalized_name

SUPPORTED_COMPETITOR_PLATFORMS = {'instagram', 'facebook', 'google_ads', 'tiktok', 'linkedin'}
TIKTOK_COUNTRIES = set('AT BE BG HR CY CZ DK EE FI FR DE GR HU IE IT LV LT LU MT NL PL PT RO SK SI ES SE NO IS LI GB CH'.split())


def public_library_url(competitor):
    code = competitor.platform.code
    if code == 'google_ads':
        advertiser = str((competitor.raw_data or {}).get('google_advertiser_id') or competitor.platform_identifier).upper()
        if re.fullmatch(r'AR\d+', advertiser):
            return 'https://adstransparency.google.com/advertiser/' + advertiser
        return 'https://adstransparency.google.com/?' + urlencode({'domain': competitor.website or competitor.platform_identifier})
    if code == 'tiktok':
        return 'https://library.tiktok.com/ads'
    if code == 'linkedin':
        return 'https://www.linkedin.com/ad-library/search?' + urlencode({'accountOwner': competitor.name})
    from core.services.competitor_live_sync import competitor_library_url
    return competitor_library_url(competitor)


def source_status(competitor):
    code = competitor.platform.code
    config = CompetitorSourceSetting.runtime(code)
    if not config['enabled']:
        return {'provider': config['source'], 'configured': False, 'message': 'Bu platformun rakip reklam kaynağı yönetici tarafından devre dışı bırakıldı.'}
    if code == 'linkedin' or (code in {'instagram', 'facebook'} and config['source'] == 'searchapi'):
        ready = bool(config['credential'])
        return {'provider': 'linkedin_ad_library_searchapi' if code == 'linkedin' else 'meta_ad_library_searchapi',
                'configured': ready, 'message': '' if ready else 'Reklam kaynağı henüz kullanıma hazır değil. Bağlantıyı sistem yöneticisi tamamlamalı.'}
    if code == 'google_ads':
        ready = bool(config['credential'])
        return {'provider': 'google_ads_transparency_serpapi', 'configured': ready,
                'message': '' if ready else 'Google reklam kaynağı henüz kullanıma hazır değil. Bağlantıyı sistem yöneticisi tamamlamalı.'}
    if code == 'tiktok':
        ready = bool(config['credential'])
        return {'provider': 'tiktok_commercial_content', 'configured': ready,
                'message': '' if ready else 'TikTok reklam kaynağı henüz kullanıma hazır değil. Bağlantıyı sistem yöneticisi tamamlamalı. Türkiye bu kaynağın ülke kapsamında değil.'}
    from core.services.competitor_live_sync import _token_for_competitor
    ready = bool(_token_for_competitor(competitor))
    coverage_warning = ''
    if ready and set(config['countries']) == {'TR'}:
        coverage_warning = 'Türkiye’deki ticari Instagram/Facebook reklamları için mevcut kaynağın kapsamı sınırlı. Genel reklam kütüphanesi bağlantısını sistem yöneticisi tamamlamalı.'
    return {'provider': 'meta_ad_library', 'configured': ready,
            'coverage_limited': bool(coverage_warning),
            'message': coverage_warning if ready else 'Meta reklam kaynağı henüz kullanıma hazır değil. Bağlantıyı sistem yöneticisi tamamlamalı.'}


def competitor_user_error(message):
    message = str(message or '')
    if any(term in message.casefold() for term in ('api', 'token', 'anahtar', '.env')):
        return 'Reklam kaynağına şu anda ulaşılamıyor. Bağlantıyı sistem yöneticisi kontrol etmeli; sizin bir reklam hesabı bağlamanız gerekmiyor.'
    return message


def safe_json(response, credential, label):
    try:
        data = response.json()
    except ValueError:
        raise CompetitorSyncError(f'{label} geçersiz JSON döndürdü.') from None
    if not isinstance(data, dict):
        raise CompetitorSyncError(f'{label} geçersiz veri döndürdü.')
    error = data.get('error')
    if isinstance(error, dict) and error.get('code') == 'ok':
        error = None
    if not response.ok or error:
        # Provider messages/URLs can contain keys; expose status/code only.
        code = error.get('code') if isinstance(error, dict) else response.status_code
        raise CompetitorSyncError(f'{label} erişim hatası (HTTP {response.status_code}, kod {code}). Anahtar, API yetkisi ve kota kontrol edilmeli.')
    return data


def timestamp(value, compact=False):
    if not value:
        return None
    try:
        if compact:
            return timezone.make_aware(datetime.strptime(str(value), '%Y%m%d'))
        return datetime.fromtimestamp(float(value), tz=dt_timezone.utc)
    except (ValueError, TypeError, OverflowError, OSError):
        return None


def public_url(value):
    value = str(value or '')
    try:
        parsed = urlsplit(value)
        if parsed.scheme in {'https', 'http'} and parsed.hostname and not parsed.username and not parsed.password:
            return value
    except ValueError:
        pass
    return ''


def domain_name(value):
    """Exact host matching, including the conventional www alias only."""
    try:
        value = str(value or '').strip()
        parsed = urlsplit(value if '://' in value else 'https://' + value)
        host = (parsed.hostname or '').lower().rstrip('.').removeprefix('www.')
        if parsed.scheme in {'http', 'https'} and not parsed.username and not parsed.password and '.' in host:
            return host.encode('idna').decode('ascii')
    except (ValueError, UnicodeError):
        pass
    return ''


def public_ad_facts(ad):
    """Expose stored public evidence without treating presence as performance."""
    raw = (ad.raw_data or {}).get('raw') or {}
    information = raw.get('detail_information') or {}
    def date_label(value):
        compact = bool(re.fullmatch(r'20\d{6}', str(value or '')))
        parsed = timestamp(value, compact=compact)
        return parsed.strftime('%d.%m.%Y') if parsed else ''

    regions = []
    for region in information.get('regions') or []:
        if not isinstance(region, dict):
            continue
        regions.append({'name': str(region.get('region_name') or ''),
                        'impressions_range': str(region.get('times_shown') or ''),
                        'first_shown': date_label(region.get('first_shown')),
                        'last_shown': date_label(region.get('last_shown'))})
    variants = raw.get('creative_variants') or []
    assets = competitor_media_assets(ad)
    return {'advertiser_name': raw.get('advertiser') or '',
            'target_domain': raw.get('target_domain') or '',
            'total_days_shown': raw.get('total_days_shown'),
            'dimensions': f"{raw['width']} × {raw['height']}" if raw.get('width') and raw.get('height') else '',
            'regions': regions, 'creative_variants': variants, 'media_assets': assets,
            'media_count': sum(bool(a['image_url'] or a['video_url']) for a in assets),
            'detail_error': raw.get('detail_error') or '',
            'source_notice': 'Google reklam kütüphanesi bölgesel gösterim aralıkları sağlayabilir. Harcama, tıklama ve dönüşüm verileri bu kaynaktan sağlanmıyor.'
                             if (ad.raw_data or {}).get('provider') == GoogleTransparencyCompetitorSync.provider else ''}


def competitor_media_assets(ad):
    """Expose every stored card and distinguish video pages from playable files."""
    raw = (ad.raw_data or {}).get('raw') or {}
    snapshot = raw.get('snapshot') or {}
    cards = snapshot.get('cards') or []
    variants = raw.get('creative_variants') or []
    if cards:
        items = cards
    elif variants:
        items = variants
        if not any(isinstance(item, dict) and any(item.get(key) for key in
                   ('image', 'image_url', 'video_link', 'video', 'video_url')) for item in items):
            if ad.preview_image_url or ad.preview_video_url:
                items = [{'image': ad.preview_image_url, 'video_link': ad.preview_video_url}, *items]
    else:
        items = [*(snapshot.get('images') or []), *(snapshot.get('videos') or [])]
        tiktok = raw.get('ad') or {}
        if not items and isinstance(tiktok, dict):
            items = [{'image': image} for image in (tiktok.get('image_urls') or [])]
            items.extend({'video_link': video.get('url'), 'thumbnail_url': video.get('thumbnail_url')}
                         for video in (tiktok.get('videos') or []) if isinstance(video, dict))
        content = raw.get('content') or {}
        if not items and isinstance(content, dict):
            items = content.get('cards') or content.get('images') or []
        if not items:
            items = [{'image': ad.preview_image_url, 'video_link': ad.preview_video_url}]
    assets = []
    for item in items[:50]:
        if isinstance(item, str):
            item = {'image': item}
        if not isinstance(item, dict):
            continue
        image = public_url(item.get('original_image_url') or item.get('resized_image_url') or item.get('image') or item.get('image_url'))
        video = public_url(item.get('video_hd_url') or item.get('video_sd_url') or item.get('video_link') or item.get('video') or item.get('video_url'))
        poster = public_url(item.get('video_preview_image_url') or item.get('thumbnail_url')) or image
        embed = ''
        if video:
            url = urlsplit(video)
            host = (url.hostname or '').lower()
            if host in {'youtube.com', 'www.youtube.com', 'm.youtube.com', 'youtu.be', 'www.youtube-nocookie.com'}:
                video_id = (parse_qs(url.query).get('v') or [''])[0]
                if host == 'youtu.be':
                    video_id = url.path.strip('/').split('/')[0]
                elif url.path.startswith(('/embed/', '/shorts/')):
                    video_id = url.path.strip('/').split('/')[1]
                if re.fullmatch(r'[A-Za-z0-9_-]{11}', video_id):
                    embed = 'https://www.youtube-nocookie.com/embed/' + video_id
                kind = 'embed' if embed else 'link'
            else:
                kind = 'video'
        else:
            kind = 'image' if image else 'text'
        body = item.get('body') or item.get('snippet') or item.get('link_description') or ''
        if isinstance(body, dict):
            body = body.get('text') or ''
        assets.append({'kind': kind, 'image_url': image, 'video_url': video, 'embed_url': embed,
                       'thumbnail_url': poster, 'title': str(item.get('title') or item.get('headline') or ''),
                       'body': str(body), 'call_to_action': str(item.get('cta_text') or item.get('call_to_action') or ''),
                       'landing_url': public_url(item.get('link_url') or item.get('landing_url'))})
    return assets


class PublicCompetitorSync:
    provider = ''
    identity_key = ''

    def __init__(self, competitor):
        self.competitor = competitor
        self.platform_code = competitor.platform.code
        self.config = CompetitorSourceSetting.runtime(self.platform_code)
        if not self.config['enabled']:
            raise CompetitorSyncError('Bu platformun rakip reklam kaynağı yönetici tarafından devre dışı bırakıldı.')

    def sync(self, limit=None):
        if not self.competitor.is_active:
            raise CompetitorSyncError('Önce rakibin aktif takibini etkinleştirin.')
        rows, advertiser_id = self.fetch(max(1, int(limit or 50)))
        created = updated = 0
        ads = []
        for row in rows:
            ad, new = self.import_ad(row)
            ads.append(ad.pk)
            created += int(new)
            updated += int(not new)
        raw = dict(self.competitor.raw_data or {})
        if advertiser_id and self.identity_key:
            raw[self.identity_key] = advertiser_id
            if self.identity_key == 'google_advertiser_id':
                raw.pop('google_advertiser_candidates', None)
        warning = '' if rows else 'Kaynak bu sorgu için reklam döndürmedi. Bu sonuç firmanın reklam yayınlamadığı anlamına gelmez; ülke ve kaynak kapsamını kontrol edin.'
        raw.update(last_live_sync_source=self.provider, last_live_sync_count=len(rows),
                   last_live_sync_result='ads_fetched' if rows else 'no_data',
                   last_live_sync_warning=warning, last_live_sync_at=timezone.now().isoformat(),
                   identity_status='matched' if rows else raw.get('identity_status', 'unverified'))
        self.competitor.raw_data = raw
        self.competitor.total_ads_seen = self.competitor.ads.filter(source_type='COMPETITOR').count()
        if rows:
            self.competitor.last_seen_at = timezone.now()
        self.competitor.save(update_fields=['raw_data', 'total_ads_seen', 'last_seen_at', 'updated_at'])
        return {'success': True, 'provider': self.provider, 'created': created, 'updated': updated,
                'total': self.competitor.total_ads_seen, 'fetched': len(rows), 'ads': ads,
                'result_status': raw['last_live_sync_result'], 'warning': warning,
                'library_url': public_library_url(self.competitor)}

    def import_ad(self, row):
        if not row.get('id'):
            raise CompetitorSyncError('Kaynak reklam ID’si eksik; kayıt yapılmadı.')
        now = timezone.now()
        competitor = self.competitor
        account = competitor.platform_account
        connection = getattr(account, 'connection', None)
        title = row.get('title') or competitor.name
        creative, _ = Creative.objects.update_or_create(user=competitor.user,
            platform_account=account, platform_connection=connection,
            platform_creative_id=f'{self.provider}-{row["id"]}', defaults={
                'name': title, 'title': title, 'creative_type': row['format'],
                'landing_url': public_url(row.get('landing')), 'body_text': row.get('body', ''),
                'raw_data': row['raw'], 'first_seen_at': row.get('start') or now,
                'last_seen_at': now})
        ad, created = Ad.objects.update_or_create(user=competitor.user, competitor=competitor,
            source_type='COMPETITOR', platform_ad_id=str(row['id']), defaults={
                'platform_account': account, 'platform_connection': connection, 'creative': creative,
                'ad_library_id': str(row['id']), 'name': title, 'headline': title,
                'status': row.get('status', 'UNKNOWN'), 'objective': 'UNKNOWN',
                'ad_format': row['format'], 'landing_url': public_url(row.get('landing')), 'primary_text': row.get('body', ''),
                'call_to_action': row.get('cta') or '',
                'preview_image_url': public_url(row.get('image')), 'preview_video_url': public_url(row.get('video')),
                'first_seen_at': row.get('start'), 'last_seen_at': row.get('last') or now,
                'ended_at': None, 'last_synced_at': now, 'is_active': competitor.is_active,
                'raw_data': {'provider': self.provider, 'raw': row['raw'],
                             'snapshot_url': public_url(row.get('snapshot')), 'available_metrics': [],
                             'advertiser_id': row['advertiser_id']}})
        # A presence snapshot carries no private clicks/spend/engagement metrics.
        AdMetricHistory.objects.update_or_create(ad=ad, date=timezone.localdate(), defaults={
            'is_competitor_snapshot': True, 'raw_metrics': {'provider': self.provider,
            'measurement_type': 'public_ad_snapshot', 'available_metrics': ['regional_impressions'] if any(isinstance(r, dict) and r.get('times_shown') for r in row.get('regions', [])) else [],
            'regional_visibility_ranges': row.get('regions', [])}})
        return ad, created


class GoogleTransparencyCompetitorSync(PublicCompetitorSync):
    provider = 'google_ads_transparency_serpapi'
    identity_key = 'google_advertiser_id'

    def enrich(self, rows, advertiser_id, key):
        existing = {ad.platform_ad_id: (ad.raw_data or {}).get('raw', {}) for ad in self.competitor.ads.all()}

        def fetch_detail(row):
            row = {**existing.get(str(row.get('ad_creative_id')), {}), **row}
            cached_at = row.get('detail_fetched_at')
            try:
                if cached_at and timezone.now() - datetime.fromisoformat(cached_at) < timedelta(hours=24):
                    return row
            except (ValueError, TypeError):
                pass
            try:
                response = requests.get('https://serpapi.com/search.json', params={
                    'engine': 'google_ads_transparency_center_ad_details', 'api_key': key,
                    'advertiser_id': advertiser_id, 'creative_id': row['ad_creative_id']}, timeout=45)
                data = safe_json(response, key, 'Google reklam ayrıntıları')
                identity = data.get('search_parameters') or {}
                if identity.get('advertiser_id') != advertiser_id or identity.get('creative_id') != row['ad_creative_id']:
                    raise CompetitorSyncError('Google reklam ayrıntısı kimliği eşleşmedi.')
                variants = data.get('ad_creatives', [])
                information = data.get('search_information', {})
                if not isinstance(variants, list) or any(not isinstance(v, dict) for v in variants) or not isinstance(information, dict):
                    raise CompetitorSyncError('Google reklam ayrıntıları geçersiz.')
                # Never persist search_parameters/search_metadata containing keys.
                row.update(creative_variants=variants, detail_information=information,
                           detail_fetched_at=timezone.now().isoformat(), detail_error='')
            except (requests.RequestException, CompetitorSyncError, KeyError):
                row['detail_error'] = 'Reklam ayrıntıları alınamadı; sonraki yenilemede tekrar denenecek.'
            return row

        with ThreadPoolExecutor(max_workers=4) as executor:
            return list(executor.map(fetch_detail, rows))

    def fetch(self, limit):
        key = self.config['credential']
        if not key:
            raise CompetitorSyncError(source_status(self.competitor)['message'])
        raw = self.competitor.raw_data or {}
        advertiser_id = str(raw.get(self.identity_key) or self.competitor.platform_identifier).upper()
        params = {'engine': 'google_ads_transparency_center', 'api_key': key, 'num': min(100, limit)}
        explicit = bool(re.fullmatch(r'AR\d+', advertiser_id))
        if explicit:
            params['advertiser_id'] = advertiser_id
        else:
            advertiser_id = ''
            params['text'] = self.competitor.website or self.competitor.platform_identifier
        # Complete domain discovery before choosing an advertiser: later pages
        # can contain a reseller with a different advertiser ID.
        discovery_limit = limit if explicit else max(500, limit)
        params['num'] = min(100, discovery_limit)
        rows, seen = [], set()
        complete = False
        while len(rows) < discovery_limit:
            try:
                response = requests.get('https://serpapi.com/search.json', params=params, timeout=45)
            except requests.RequestException:
                raise CompetitorSyncError('Google reklam şeffaflık kaynağına ağ bağlantısı kurulamadı.') from None
            data = safe_json(response, key, 'Google reklam şeffaflığı')
            page = data.get('ad_creatives', [])
            if not isinstance(page, list) or any(not isinstance(r, dict) for r in page):
                raise CompetitorSyncError('Google reklam listesi geçersiz.')
            rows.extend(page[:discovery_limit-len(rows)])
            cursor = (data.get('serpapi_pagination') or {}).get('next_page_token')
            if not cursor:
                complete = True
                break
            if cursor in seen:
                break
            seen.add(cursor)
            params.update(next_page_token=cursor, num=min(100, discovery_limit-len(rows)))
        if not explicit and rows:
            # Domain queries may return resellers; never import them as the brand.
            domain = domain_name(params['text'])
            matches = {str(r.get('advertiser_id')) for r in rows
                       if ((domain and domain_name(r.get('target_domain')) == domain)
                           or (not domain and _normalized_name(r.get('advertiser')) == _normalized_name(self.competitor.name)))
                       and re.fullmatch(r'AR\d+', str(r.get('advertiser_id', '')))}
            if not complete:
                raise CompetitorSyncError('Reklamveren araması tamamlanamadı. Daha belirgin bir firma adı veya alan adı girin.')
            if len(matches) > 1:
                candidates = {}
                for row in rows:
                    identifier = str(row.get('advertiser_id'))
                    if identifier in matches:
                        candidates[identifier] = {'id': identifier, 'name': str(row.get('advertiser') or 'Reklamveren')[:200],
                                                  'domain': domain_name(row.get('target_domain'))}
                raise CompetitorAdvertiserChoiceRequired(list(candidates.values()))
            if not matches:
                raise CompetitorSyncError('Girilen alan adı veya firma adıyla reklamveren eşleşmedi. Rakibin web sitesini veya firma adını kontrol edin.')
            advertiser_id = matches.pop()
        rows = [r for r in rows if str(r.get('advertiser_id')) == advertiser_id][:limit]
        if getattr(settings, 'GOOGLE_COMPETITOR_DETAILS_ENABLED', True):
            rows = self.enrich(rows, advertiser_id, key)
        normalized = []
        for row in rows:
            variants = row.get('creative_variants') or []
            variant = variants[0] if variants else {}
            regions = (row.get('detail_information') or {}).get('regions') or []
            normalized.append(dict(id=row.get('ad_creative_id'), advertiser_id=advertiser_id,
                format={'text': 'TEXT', 'image': 'IMAGE', 'video': 'VIDEO'}.get(row.get('format'), 'UNKNOWN'),
                title=variant.get('headline') or variant.get('title') or variant.get('call_to_action') or '',
                body=variant.get('snippet') or '', landing=variant.get('link') or '',
                cta=variant.get('call_to_action') or '',
                image=variant.get('image') or row.get('image') or '', video=variant.get('video_link') or '',
                start=timestamp(row.get('first_shown')), last=timestamp(row.get('last_shown')),
                snapshot=row.get('details_link') or '', raw=row, regions=regions))
        return normalized, advertiser_id


class TikTokCommercialCompetitorSync(PublicCompetitorSync):
    provider = 'tiktok_commercial_content'
    identity_key = 'tiktok_business_id'

    def request(self, path, body, fields):
        token = self.config['credential']
        try:
            response = requests.post('https://open.tiktokapis.com/v2/research/adlib/' + path + '/',
                headers={'Authorization': 'Bearer ' + token}, params={'fields': fields}, json=body, timeout=30)
        except requests.RequestException:
            raise CompetitorSyncError('TikTok Commercial Content API ağ bağlantısı kurulamadı.') from None
        return safe_json(response, token, 'TikTok Commercial Content API').get('data') or {}

    def fetch(self, limit):
        if not self.config['credential']:
            raise CompetitorSyncError(source_status(self.competitor)['message'])
        countries = self.config['countries']
        if set(countries) - TIKTOK_COUNTRIES:
            raise CompetitorSyncError('TikTok resmi reklam kütüphanesi seçilen ülkeyi desteklemiyor. Türkiye kapsamda değil; desteklenen Avrupa ülkeleri seçilmeli.')
        raw = self.competitor.raw_data or {}
        identifier = str(raw.get(self.identity_key) or self.competitor.platform_identifier)
        business_id = identifier if identifier.isascii() and identifier.isdigit() else ''
        name = self.competitor.name
        if not name or len(name) > 50:
            raise CompetitorSyncError('TikTok reklamveren şirket adı 1–50 karakter olmalı.')
        if not business_id:
            data = self.request('advertiser/query', {'search_term': name, 'max_count': 50}, 'business_id,business_name,country_code')
            candidates = data.get('advertisers', [])
            if not isinstance(candidates, list) or any(not isinstance(r, dict) for r in candidates):
                raise CompetitorSyncError('TikTok reklamveren listesi geçersiz.')
            matches = {str(r['business_id']) for r in candidates if r.get('business_id')
                       and _normalized_name(r.get('business_name')) == _normalized_name(name)}
            if len(matches) != 1:
                raise CompetitorSyncError('TikTok reklamvereni kesin eşleştirilemedi. Hesap adı / ID alanına reklamveren business ID’si girin.')
            business_id = matches.pop()
        today = timezone.localdate()
        body = {'filters': {'ad_published_date_range': {'min': (today-timedelta(days=364)).strftime('%Y%m%d'), 'max': today.strftime('%Y%m%d')}},
                'search_term': name, 'search_type': 'exact_phrase', 'max_count': min(10, limit)}
        if countries:
            body['filters']['country_code_list'] = countries
        rows, seen = [], set()
        while len(rows) < limit:
            data = self.request('ad/query', body, 'ad.id,ad.first_shown_date,ad.last_shown_date,ad.status,ad.videos,ad.image_urls,advertiser.business_id,advertiser.business_name')
            page = data.get('ads', [])
            if not isinstance(page, list) or any(not isinstance(r, dict) or not isinstance(r.get('ad'), dict)
                                                 or not isinstance(r.get('advertiser'), dict) for r in page):
                raise CompetitorSyncError('TikTok reklam listesi geçersiz.')
            for r in page:
                advertiser = r['advertiser']
                # Historical documentation misspells buisness_id; both are typed advertiser IDs.
                if str(advertiser.get('business_id', advertiser.get('buisness_id', ''))) == business_id:
                    rows.append(r)
                    if len(rows) == limit:
                        break
            cursor = data.get('search_id')
            if data.get('has_more') not in (True, 'true') or not cursor or cursor in seen:
                break
            seen.add(cursor)
            if len(seen) >= 100:
                raise CompetitorSyncError('TikTok araması eşleşme sınırına ulaştı; daha dar bir reklamveren adı kullanın.')
            body.update(search_id=cursor, max_count=min(10, limit-len(rows)))
        normalized = []
        for r in rows:
            ad = r['ad']
            images, videos = ad.get('image_urls') or [], ad.get('videos') or []
            normalized.append(dict(id=ad.get('id'), advertiser_id=business_id,
                format='VIDEO' if videos else 'IMAGE' if images else 'UNKNOWN',
                image=images[0] if images else '', video=(videos[0].get('url') or '') if videos else '',
                start=timestamp(ad.get('first_shown_date'), True), last=timestamp(ad.get('last_shown_date'), True),
                status={'active': 'ACTIVE', 'inactive': 'ENDED'}.get(str(ad.get('status', '')).lower(), 'UNKNOWN'),
                raw=r))
        return normalized, business_id


def competitor_source(competitor):
    code = competitor.platform.code
    config = CompetitorSourceSetting.runtime(code)
    if not config['enabled']:
        raise CompetitorSyncError('Bu platformun rakip reklam kaynağı yönetici tarafından devre dışı bırakıldı.')
    if code == 'linkedin':
        from core.services.competitor_searchapi import LinkedInLibraryCompetitorSync
        return LinkedInLibraryCompetitorSync(competitor)
    if code in {'instagram', 'facebook'}:
        selection = config['source']
        if selection == 'searchapi':
            from core.services.competitor_searchapi import MetaPublicLibraryCompetitorSync
            return MetaPublicLibraryCompetitorSync(competitor)
        if selection != 'graph':
            raise CompetitorSyncError('Meta reklam kaynağı graph veya searchapi olmalı.')
    if code == 'google_ads':
        return GoogleTransparencyCompetitorSync(competitor)
    if code == 'tiktok':
        return TikTokCommercialCompetitorSync(competitor)
    from core.services.competitor_live_sync import MetaAdLibraryCompetitorSync
    return MetaAdLibraryCompetitorSync(competitor)

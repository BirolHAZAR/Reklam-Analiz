"""Optional public Meta/LinkedIn libraries; explicitly configured provider only."""
import requests
from django.conf import settings
from core.services.competitor_public_sources import PublicCompetitorSync, safe_json
from core.services.competitor_live_sync import CompetitorSyncError, _page_ids_for_competitor, _parse_dt, _normalized_name


class SearchApiLibrarySync(PublicCompetitorSync):
    def request(self, params):
        key = self.config['credential']
        if not key:
            raise CompetitorSyncError('Reklam kütüphanesi veri sağlayıcısı bağlantısı gerekiyor. SEARCHAPI_API_KEY yapılandırılmalı.')
        try:
            response = requests.post('https://www.searchapi.io/api/v1/search',
                headers={'Authorization': 'Bearer ' + key}, json=params, timeout=45)
        except requests.RequestException:
            raise CompetitorSyncError('Reklam kütüphanesi veri sağlayıcısına ağ bağlantısı kurulamadı.') from None
        return safe_json(response, key, 'Reklam kütüphanesi veri sağlayıcısı')

    def pages(self, params, limit, accept):
        rows, seen = [], set()
        while len(rows) < limit:
            data = self.request(dict(params))
            page = data.get('ads', [])
            if not isinstance(page, list) or any(not isinstance(r, dict) for r in page):
                raise CompetitorSyncError('Reklam kütüphanesi listesi geçersiz.')
            rows.extend([r for r in page if accept(r)][:limit-len(rows)])
            cursor = (data.get('pagination') or {}).get('next_page_token')
            if not cursor or cursor in seen:
                break
            seen.add(cursor)
            if len(seen) >= 100:
                raise CompetitorSyncError('Reklam araması eşleşme sınırına ulaştı; kimlik ve sorgu daraltılmalı.')
            params['next_page_token'] = cursor
        return rows


class MetaPublicLibraryCompetitorSync(SearchApiLibrarySync):
    provider = 'meta_ad_library_searchapi'
    identity_key = 'facebook_page_id'

    def fetch(self, limit):
        # Fail before any name lookup when provider credentials are unavailable.
        if not self.config['credential']:
            raise CompetitorSyncError('Türkiye ticari Meta reklamları için reklam kütüphanesi veri sağlayıcısı bağlantısı gerekiyor. SEARCHAPI_API_KEY yapılandırılmalı.')
        ids = _page_ids_for_competitor(self.competitor)
        if len(ids) > 1:
            raise CompetitorSyncError('Tek bir Facebook reklamveren sayfa ID’si seçilmeli.')
        page_id = ids[0] if ids else ''
        countries = self.config['countries'] or ['TR']
        country = countries[0] if len(countries) == 1 else 'ALL'
        if not page_id:
            handle = self.competitor.platform_identifier.strip().lstrip('@').casefold()
            if handle.isdigit():
                raise CompetitorSyncError('Instagram hesap ID’si Facebook sayfa ID’si değildir. Facebook reklamveren sayfa ID’si eşleştirilmeli.')
            data = self.request({'engine': 'meta_ad_library_page_search', 'q': handle, 'country': country})
            candidates = data.get('page_results', [])
            if not isinstance(candidates, list) or any(not isinstance(r, dict) for r in candidates):
                raise CompetitorSyncError('Meta reklamveren araması geçersiz.')
            alias = 'ig_username' if self.platform_code == 'instagram' else 'page_alias'
            matches = {str(r['page_id']) for r in candidates if str(r.get('page_id', '')).isdigit()
                       and str(r.get(alias) or '').strip().lstrip('@').casefold() == handle}
            if len(matches) != 1:
                raise CompetitorSyncError('Hesap adı tek bir reklamverenle eşleştirilemedi. Facebook sayfa ID’sini veya reklam kütüphanesi bağlantısını girin.')
            page_id = matches.pop()
        params = {'engine': 'meta_ad_library', 'page_id': page_id, 'country': country,
                  'ad_type': 'all', 'active_status': 'all', 'platforms': self.platform_code}
        rows = self.pages(params, limit, lambda r: str(r.get('page_id')) == page_id)
        normalized = []
        for row in rows:
            snapshot = row.get('snapshot') or {}
            cards = snapshot.get('cards') or []
            images = snapshot.get('images') or []
            videos = snapshot.get('videos') or []
            card = cards[0] if cards else {}
            image = card.get('original_image_url') or ((images[0].get('original_image_url') or '') if images else '')
            video = card.get('video_hd_url') or card.get('video_sd_url') or ((videos[0].get('video_hd_url') or videos[0].get('video_sd_url') or '') if videos else '')
            body = snapshot.get('body') or {}
            ad_id = row.get('ad_archive_id')
            normalized.append(dict(id=ad_id, advertiser_id=page_id, raw=row,
                format='CAROUSEL' if len(cards) > 1 else 'VIDEO' if video else 'IMAGE' if image else 'UNKNOWN',
                title=card.get('title') or snapshot.get('title') or self.competitor.name,
                body=body.get('text', '') if isinstance(body, dict) else str(body),
                cta=card.get('cta_text') or snapshot.get('cta_text') or '',
                landing=card.get('link_url') or snapshot.get('link_url') or '', image=image, video=video,
                start=_parse_dt(row.get('start_date')), last=None,
                status='ACTIVE' if row.get('is_active') is True else 'ENDED' if row.get('is_active') is False else 'UNKNOWN',
                snapshot='https://www.facebook.com/ads/library/?id=' + str(ad_id or '')))
        return normalized, page_id


class LinkedInLibraryCompetitorSync(SearchApiLibrarySync):
    provider = 'linkedin_ad_library_searchapi'

    def fetch(self, limit):
        name = self.competitor.name
        params = {'engine': 'linkedin_ad_library', 'advertiser': name, 'time_period': 'last_year'}
        rows = self.pages(params, limit, lambda r: isinstance(r.get('advertiser'), dict)
                          and _normalized_name(r['advertiser'].get('name')) == _normalized_name(name))
        normalized = []
        for row in rows:
            content = row.get('content') or {}
            normalized.append(dict(id=row.get('id'), advertiser_id=name, raw=row,
                format={'image': 'IMAGE', 'video': 'VIDEO', 'text': 'TEXT', 'carousel': 'CAROUSEL'}.get(row.get('ad_type'), 'UNKNOWN'),
                title=content.get('headline') or name, body=row.get('headline') or '',
                image=content.get('image') or '', video=content.get('video') or '', snapshot=row.get('link') or ''))
        return normalized, ''

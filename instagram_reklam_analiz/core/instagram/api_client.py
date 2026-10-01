# core/instagram/api_client.py
"""
Instagram Graph API İstemcisi
Instagram API ile iletişim kurmak için gerekli tüm fonksiyonları içerir
"""

import requests
import json
import time
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any
from django.conf import settings
from django.core.cache import cache


class InstagramAPIClient:
    """
    Instagram Graph API istemcisi
    Instagram hesap bilgileri, medyalar, içgörüler ve reklam verilerini çeker
    """
    
    def __init__(self, access_token: str = None, user_id: str = None):
        """
        API istemcisini başlat
        
        Args:
            access_token: Instagram access token
            user_id: Instagram kullanıcı ID'si
        """
        self.base_url = "https://graph.instagram.com"
        self.graph_url = getattr(settings, "FACEBOOK_GRAPH_URL", "https://graph.facebook.com/v25.0")
        self.access_token = access_token or getattr(settings, 'INSTAGRAM_ACCESS_TOKEN', None)
        self.user_id = user_id or "me"
        self.rate_limit = 200  # Dakikada maksimum istek
        self.request_count = 0
        self.last_request_time = datetime.now()
    
    def _make_request(self, url: str, params: Dict = None, method: str = 'GET', data: Dict = None) -> Dict:
        """
        API isteği yap (rate limit kontrolü ile)
        
        Args:
            url: API URL
            params: Query parametreleri
            method: HTTP metodu (GET, POST)
            data: POST verileri
        
        Returns:
            Dict: API yanıtı
        """
        # Rate limit kontrolü
        now = datetime.now()
        if (now - self.last_request_time).seconds < 60:
            self.request_count += 1
            if self.request_count >= self.rate_limit:
                time.sleep(60)
                self.request_count = 0
        else:
            self.request_count = 1
            self.last_request_time = now
        
        # Token'ı parametrelere ekle
        if params is None:
            params = {}
        params['access_token'] = self.access_token
        
        try:
            if method == 'GET':
                response = requests.get(url, params=params, timeout=30)
            elif method == 'POST':
                response = requests.post(url, params=params, data=data, timeout=30)
            else:
                response = requests.request(method, url, params=params, data=data, timeout=30)
            
            response.raise_for_status()
            return response.json()
            
        except requests.exceptions.RequestException as e:
            error_msg = str(e)
            if response and response.status_code == 400:
                try:
                    error_data = response.json()
                    return {'error': error_data}
                except:
                    pass
            return {'error': {'message': error_msg, 'status_code': response.status_code if response else 0}}
    
    # ============================================
    # KULLANICI BİLGİLERİ
    # ============================================
    
    def get_user_info(self, user_id: str = None) -> Dict:
        """
        Kullanıcı bilgilerini al
        
        Args:
            user_id: Kullanıcı ID (varsayılan: me)
        
        Returns:
            Dict: Kullanıcı bilgileri
        """
        uid = user_id or self.user_id
        url = f"{self.base_url}/{uid}"
        params = {
            'fields': 'id,username,account_type,media_count'
        }
        
        return self._make_request(url, params)
    
    def get_user_info_detailed(self, user_id: str = None) -> Dict:
        """
        Detaylı kullanıcı bilgilerini al
        
        Args:
            user_id: Kullanıcı ID
        
        Returns:
            Dict: Detaylı kullanıcı bilgileri
        """
        uid = user_id or self.user_id
        url = f"{self.graph_url}/{uid}"
        params = {
            'fields': 'id,username,name,biography,followers_count,follows_count,media_count,website,profile_picture_url'
        }
        
        return self._make_request(url, params)
    
    # ============================================
    # MEDYA İŞLEMLERİ
    # ============================================
    
    def get_user_media(self, user_id: str = None, limit: int = 100, after: str = None) -> Dict:
        """
        Kullanıcının medyalarını al
        
        Args:
            user_id: Kullanıcı ID
            limit: Medya sayısı (max 100)
            after: Pagination cursor
        
        Returns:
            Dict: Medya listesi
        """
        uid = user_id or self.user_id
        url = f"{self.base_url}/{uid}/media"
        params = {
            'fields': 'id,caption,media_type,media_url,permalink,timestamp,like_count,comments_count',
            'limit': min(limit, 100)
        }
        
        if after:
            params['after'] = after
        
        return self._make_request(url, params)
    
    def get_media_by_id(self, media_id: str) -> Dict:
        """
        Medya ID'sine göre medya bilgilerini al
        
        Args:
            media_id: Medya ID'si
        
        Returns:
            Dict: Medya bilgileri
        """
        url = f"{self.base_url}/{media_id}"
        params = {
            'fields': 'id,caption,media_type,media_url,permalink,timestamp,like_count,comments_count,children'
        }
        
        return self._make_request(url, params)
    
    def get_media_insights(self, media_id: str) -> Dict:
        """
        Medya içgörülerini al
        
        Args:
            media_id: Medya ID'si
        
        Returns:
            Dict: İçgörü verileri
        """
        url = f"{self.base_url}/{media_id}/insights"
        params = {
            'metric': 'engagement,impressions,reach,saved'
        }
        
        return self._make_request(url, params)
    
    def get_media_children(self, media_id: str) -> Dict:
        """
        Karusel medyasının alt medyalarını al
        
        Args:
            media_id: Ana medya ID'si
        
        Returns:
            Dict: Alt medyalar
        """
        url = f"{self.base_url}/{media_id}/children"
        params = {
            'fields': 'id,media_type,media_url,permalink,timestamp'
        }
        
        return self._make_request(url, params)
    
    # ============================================
    # HESAP İÇGÖRÜLERİ
    # ============================================
    
    def get_account_insights(self, user_id: str = None, since_days: int = 30) -> Dict:
        """
        Hesap içgörülerini al
        
        Args:
            user_id: Kullanıcı ID
            since_days: Kaç günlük veri
        
        Returns:
            Dict: İçgörü verileri
        """
        uid = user_id or self.user_id
        since_date = (datetime.now() - timedelta(days=since_days)).strftime('%Y-%m-%d')
        until_date = datetime.now().strftime('%Y-%m-%d')
        
        url = f"{self.base_url}/{uid}/insights"
        params = {
            'metric': 'impressions,reach,profile_views,website_clicks',
            'period': 'day',
            'since': since_date,
            'until': until_date
        }
        
        return self._make_request(url, params)
    
    def get_follower_demographics(self, user_id: str = None) -> Dict:
        """
        Takipçi demografik verilerini al (Business hesap gerektirir)
        
        Args:
            user_id: Kullanıcı ID
        
        Returns:
            Dict: Demografik veriler
        """
        uid = user_id or self.user_id
        url = f"{self.graph_url}/{uid}/insights"
        params = {
            'metric': 'follower_demographics',
            'period': 'lifetime'
        }
        
        return self._make_request(url, params)
    
    def get_audience_insights(self, user_id: str = None) -> Dict:
        """
        Hedef kitle içgörülerini al
        
        Args:
            user_id: Kullanıcı ID
        
        Returns:
            Dict: Hedef kitle verileri
        """
        uid = user_id or self.user_id
        url = f"{self.graph_url}/{uid}/insights"
        params = {
            'metric': 'audience_city,audience_country,audience_gender_age,audience_locale',
            'period': 'lifetime'
        }
        
        return self._make_request(url, params)
    
    # ============================================
    # İŞLETME HESAP İŞLEMLERİ
    # ============================================
    
    def get_business_accounts(self) -> Dict:
        """
        Facebook sayfalarına bağlı işletme hesaplarını al
        
        Returns:
            Dict: İşletme hesapları
        """
        url = f"{self.graph_url}/me/accounts"
        params = {
            'fields': 'id,name,instagram_business_account,access_token'
        }
        
        return self._make_request(url, params)
    
    def get_business_insights(self, business_id: str, since_days: int = 30) -> Dict:
        """
        İşletme hesabı içgörülerini al
        
        Args:
            business_id: İşletme hesap ID'si
            since_days: Kaç günlük veri
        
        Returns:
            Dict: İçgörü verileri
        """
        since_date = (datetime.now() - timedelta(days=since_days)).strftime('%Y-%m-%d')
        until_date = datetime.now().strftime('%Y-%m-%d')
        
        url = f"{self.graph_url}/{business_id}/insights"
        params = {
            'metric': 'impressions,reach,profile_views,website_clicks,email_contacts,phone_call_clicks,text_message_clicks,get_directions_clicks',
            'period': 'day',
            'since': since_date,
            'until': until_date
        }
        
        return self._make_request(url, params)
    
    # ============================================
    # HASHTAG İŞLEMLERİ
    # ============================================
    
    def search_hashtag(self, hashtag: str) -> Dict:
        """
        Hashtag ara
        
        Args:
            hashtag: Hashtag adı (# işareti olmadan)
        
        Returns:
            Dict: Hashtag bilgileri
        """
        url = f"{self.graph_url}/ig_hashtag_search"
        params = {
            'q': hashtag
        }
        
        return self._make_request(url, params)
    
    def get_hashtag_media(self, hashtag_id: str, limit: int = 100) -> Dict:
        """
        Hashtag'e göre medyaları al
        
        Args:
            hashtag_id: Hashtag ID'si
            limit: Medya sayısı
        
        Returns:
            Dict: Medya listesi
        """
        url = f"{self.graph_url}/{hashtag_id}/recent_media"
        params = {
            'fields': 'id,caption,media_type,media_url,permalink,timestamp,like_count,comments_count',
            'limit': min(limit, 100)
        }
        
        return self._make_request(url, params)
    
    def get_hashtag_insights(self, hashtag_id: str) -> Dict:
        """
        Hashtag içgörülerini al
        
        Args:
            hashtag_id: Hashtag ID'si
        
        Returns:
            Dict: İçgörü verileri
        """
        url = f"{self.graph_url}/{hashtag_id}/insights"
        params = {
            'metric': 'impressions,reach'
        }
        
        return self._make_request(url, params)
    
    # ============================================
    # REKLAM İŞLEMLERİ
    # ============================================
    
    def get_ad_accounts(self) -> Dict:
        """
        Reklam hesaplarını al
        
        Returns:
            Dict: Reklam hesapları
        """
        url = f"{self.graph_url}/me/adaccounts"
        params = {
            'fields': 'id,name,account_status,currency,amount_spent,balance'
        }
        
        return self._make_request(url, params)
    
    def get_ad_campaigns(self, ad_account_id: str, limit: int = 100) -> Dict:
        """
        Reklam kampanyalarını al
        
        Args:
            ad_account_id: Reklam hesap ID'si
            limit: Kampanya sayısı
        
        Returns:
            Dict: Kampanya listesi
        """
        url = f"{self.graph_url}/act_{ad_account_id}/campaigns"
        params = {
            'fields': 'id,name,status,objective,start_time,stop_time,daily_budget,lifetime_budget',
            'limit': min(limit, 100)
        }
        
        return self._make_request(url, params)
    
    def get_ad_sets(self, ad_account_id: str, limit: int = 100) -> Dict:
        """
        Reklam setlerini al
        
        Args:
            ad_account_id: Reklam hesap ID'si
            limit: Ad set sayısı
        
        Returns:
            Dict: Ad set listesi
        """
        url = f"{self.graph_url}/act_{ad_account_id}/adsets"
        params = {
            'fields': 'id,name,status,daily_budget,lifetime_budget,targeting,start_time,end_time',
            'limit': min(limit, 100)
        }
        
        return self._make_request(url, params)
    
    def get_ads(self, ad_account_id: str, limit: int = 100) -> Dict:
        """
        Reklamları al
        
        Args:
            ad_account_id: Reklam hesap ID'si
            limit: Reklam sayısı
        
        Returns:
            Dict: Reklam listesi
        """
        url = f"{self.graph_url}/act_{ad_account_id}/ads"
        params = {
            'fields': 'id,name,status,creative,adset_id,campaign_id',
            'limit': min(limit, 100)
        }
        
        return self._make_request(url, params)
    
    def get_ad_insights(self, ad_account_id: str, since_days: int = 30) -> Dict:
        """
        Reklam içgörülerini al
        
        Args:
            ad_account_id: Reklam hesap ID'si
            since_days: Kaç günlük veri
        
        Returns:
            Dict: İçgörü verileri
        """
        since_date = (datetime.now() - timedelta(days=since_days)).strftime('%Y-%m-%d')
        until_date = datetime.now().strftime('%Y-%m-%d')
        
        url = f"{self.graph_url}/act_{ad_account_id}/insights"
        params = {
            'fields': 'campaign_id,campaign_name,adset_id,adset_name,ad_id,ad_name,impressions,clicks,ctr,cpc,cpm,spend,reach,frequency,actions,action_values,purchase_roas,website_purchase_roas,date_start,date_stop',
            'time_increment': 1,
            'time_range': json.dumps({'since': since_date, 'until': until_date}),
            'level': 'ad',
            'limit': 100
        }
        
        return self._make_request(url, params)
    
    def create_campaign(self, ad_account_id: str, campaign_data: Dict) -> Dict:
        """
        Yeni reklam kampanyası oluştur
        
        Args:
            ad_account_id: Reklam hesap ID'si
            campaign_data: Kampanya verileri
        
        Returns:
            Dict: Oluşturulan kampanya
        """
        url = f"{self.graph_url}/act_{ad_account_id}/campaigns"
        
        return self._make_request(url, method='POST', data=campaign_data)
    
    # ============================================
    # TOKEN YÖNETİMİ
    # ============================================
    
    def refresh_access_token(self) -> Dict:
        """
        Access token'ı yenile (long-lived token al)
        
        Returns:
            Dict: Yeni token bilgileri
        """
        url = f"{self.base_url}/refresh_access_token"
        params = {
            'grant_type': 'ig_refresh_token'
        }
        
        return self._make_request(url, params)
    
    def get_long_lived_token(self, short_lived_token: str) -> Dict:
        """
        Short-lived token'ı long-lived token'a çevir (60 gün geçerli)
        
        Args:
            short_lived_token: Short-lived access token
        
        Returns:
            Dict: Long-lived token bilgileri
        """
        url = f"{self.graph_url}/oauth/access_token"
        params = {
            'grant_type': 'ig_exchange_token',
            'client_secret': getattr(settings, 'INSTAGRAM_APP_SECRET', ''),
            'access_token': short_lived_token
        }
        
        return self._make_request(url, params)
    
    def exchange_code_for_token(self, code: str) -> Dict:
        """
        Authorization code'u access token'a çevir
        
        Args:
            code: Authorization code
        
        Returns:
            Dict: Token bilgileri
        """
        url = f"{self.base_url}/oauth/access_token"
        data = {
            'client_id': getattr(settings, 'INSTAGRAM_APP_ID', ''),
            'client_secret': getattr(settings, 'INSTAGRAM_APP_SECRET', ''),
            'grant_type': 'authorization_code',
            'redirect_uri': getattr(settings, 'INSTAGRAM_REDIRECT_URI', 'http://localhost:8000/instagram/callback/'),
            'code': code
        }
        
        return self._make_request(url, method='POST', data=data)
    
    # ============================================
    # WEBHOOK İŞLEMLERİ
    # ============================================
    
    def verify_webhook(self, verify_token: str, challenge: str, mode: str) -> bool:
        """
        Webhook doğrulama
        
        Args:
            verify_token: Doğrulama token'ı
            challenge: Challenge değeri
            mode: Mod (subscribe, unsubscribe)
        
        Returns:
            bool: Doğrulama başarılı mı
        """
        expected_token = getattr(settings, 'INSTAGRAM_WEBHOOK_VERIFY_TOKEN', '')
        return verify_token == expected_token
    
    def process_webhook_data(self, data: Dict) -> Dict:
        """
        Webhook verilerini işle
        
        Args:
            data: Webhook'tan gelen veri
        
        Returns:
            Dict: İşlenmiş veri
        """
        result = {
            'object': data.get('object'),
            'entry': []
        }
        
        for entry in data.get('entry', []):
            processed_entry = {
                'id': entry.get('id'),
                'time': entry.get('time'),
                'changes': []
            }
            
            for change in entry.get('changes', []):
                processed_change = {
                    'field': change.get('field'),
                    'value': change.get('value')
                }
                processed_entry['changes'].append(processed_change)
            
            result['entry'].append(processed_entry)
        
        return result
    
    # ============================================
    # YARDIMCI FONKSİYONLAR
    # ============================================
    
    def get_rate_limit_status(self) -> Dict:
        """
        Rate limit durumunu döndür
        
        Returns:
            Dict: Rate limit bilgileri
        """
        return {
            'request_count': self.request_count,
            'rate_limit': self.rate_limit,
            'last_request_time': self.last_request_time.isoformat(),
            'remaining': max(0, self.rate_limit - self.request_count)
        }
    
    def clear_cache(self):
        """Cache temizleme"""
        cache.delete_pattern('instagram_*')
    
    def set_access_token(self, token: str):
        """
        Access token'ı güncelle
        
        Args:
            token: Yeni access token
        """
        self.access_token = token
    
    def test_connection(self) -> bool:
        """
        API bağlantısını test et
        
        Returns:
            bool: Bağlantı başarılı mı
        """
        result = self.get_user_info()
        return 'error' not in result




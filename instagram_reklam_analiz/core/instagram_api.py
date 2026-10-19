import json
from datetime import datetime, timedelta
import requests
from django.conf import settings


def _sanitize_error_text(text, token):
    text = str(text or "")
    token = str(token or "")
    if token:
        text = text.replace(token, "[ACCESS_TOKEN]")
    return text


class InstagramAPI:
   

    def __init__(self, access_token=None, *, instagram_login=False):
        self.access_token = access_token or getattr(settings, 'INSTAGRAM_ACCESS_TOKEN', '')
        self.base_url = "https://graph.instagram.com"
        self.graph_url = getattr(settings, "FACEBOOK_GRAPH_URL", "https://graph.facebook.com/v25.0")
        if instagram_login:
            from core.services.instagram_oauth import graph_url
            self.graph_url = graph_url()

    def _request(self, url, params=None, method='GET', data=None):
        params = params or {}
        params['access_token'] = self.access_token
        resp = None
        try:
            from core.services.meta_rate_limit import before_request, after_response
            request_options = {"params": params, "data": data}
            before_request(url, request_options)
            if method == 'GET':
                resp = requests.get(url, params=params, timeout=30)
            else:
                resp = requests.post(url, params=params, data=data, timeout=30)
            payload = resp.json()
            after_response(url, request_options, resp, payload)
            resp.raise_for_status()
            return payload
        except Exception as e:
            from core.services.meta_rate_limit import MetaRateLimitError
            if isinstance(e, MetaRateLimitError):
                return {'error': str(e), 'status_code': 429, 'retry_after': e.retry_after}
            response_body = ""
            if resp is not None:
                try:
                    response_body = resp.text
                except Exception:
                    response_body = ""
            error_text = _sanitize_error_text(str(e), self.access_token)
            response_body = _sanitize_error_text(response_body, self.access_token)
            if response_body:
                error_text = f"{error_text} | response={response_body[:1000]}"
            return {'error': error_text, 'status_code': getattr(resp, 'status_code', 0)}

    def get_user_info(self, user_id="me"):
        return self._request(f"{self.base_url}/{user_id}", {'fields': 'id,username,account_type,media_count'})

    def get_user_media(self, user_id="me", limit=50):
        return self._request(f"{self.base_url}/{user_id}/media", {'fields': 'id,caption,media_type,media_url,permalink,timestamp,like_count,comments_count', 'limit': limit})

    def get_business_accounts(self):
        return self._request(f"{self.graph_url}/me/accounts", {'fields': 'id,name,instagram_business_account,access_token'})

    def get_ads_insights(self, ad_account_id, since_days=30):
        from core.services.ad_eligibility import is_current_campaign
        account_id = f"act_{str(ad_account_id).removeprefix('act_')}"

        def collect(edge, params):
            rows, seen = [], set()
            while True:
                response = self._request(f"{self.graph_url}/{account_id}/{edge}", dict(params))
                if response.get("error"):
                    return response
                if not isinstance(response.get("data"), list):
                    return {"error": "Meta reklam listesi eksiksiz okunamadı."}
                rows.extend(response["data"])
                paging = response.get("paging") or {}
                if not paging.get("next"):
                    return {"data": rows}
                cursor = (paging.get("cursors") or {}).get("after")
                if not cursor or cursor in seen:
                    return {"error": "Meta reklam sayfalaması tamamlanamadı."}
                seen.add(cursor)
                params["after"] = cursor

        campaigns = collect("campaigns", {"fields": "id,status,effective_status,start_time,stop_time",
                            "effective_status": json.dumps(["ACTIVE"]), "limit": 100})
        if campaigns.get("error"):
            return campaigns
        campaign_ids = {str(row["id"]) for row in campaigns["data"] if is_current_campaign(row)}
        if not campaign_ids:
            return {"data": []}
        ads = collect("ads", {"fields": "id,effective_status,campaign{id,status,start_time,stop_time},adset{id,status,effective_status,start_time,end_time}",
            "effective_status": json.dumps(["ACTIVE"]), "limit": 100,
            "filtering": json.dumps([{"field": "campaign.id", "operator": "IN", "value": sorted(campaign_ids)}])})
        if ads.get("error"):
            return ads
        active_ids = {str(row["id"]) for row in ads["data"]
            if row.get("effective_status") == "ACTIVE"
            and str((row.get("campaign") or {}).get("id")) in campaign_ids
            and is_current_campaign(row.get("campaign") or {})
            and is_current_campaign(row.get("adset") or {})}
        if not active_ids:
            return {"data": []}
        since = (datetime.now() - timedelta(days=since_days)).strftime('%Y-%m-%d')
        until = datetime.now().strftime('%Y-%m-%d')
        result = collect(
            "insights",
            {
                'fields': 'campaign_id,campaign_name,adset_id,adset_name,ad_id,ad_name,impressions,clicks,ctr,cpc,cpm,spend,reach,frequency,actions,action_values,purchase_roas,website_purchase_roas,date_start,date_stop',
                'time_range': json.dumps({'since': since, 'until': until}),
                'time_increment': 1,
                'level': 'ad',
                'filtering': json.dumps([{"field": "ad.id", "operator": "IN", "value": sorted(active_ids)}]),
                'limit': 500,
            },
        )
        if not result.get("error"):
            result["data"] = [{**row, "status": "ACTIVE", "campaign_status": "ACTIVE", "adgroup_status": "ACTIVE"}
                for row in result["data"] if str(row.get("ad_id")) in active_ids
                and str(row.get("campaign_id")) in campaign_ids]
        return result

    def publish_instagram_post(self, instagram_business_id, image_url, caption):
        creation = self._request(f"{self.graph_url}/{instagram_business_id}/media", method='POST', data={'image_url': image_url, 'caption': caption})
        if 'error' in creation:
            return creation
        creation_id = creation.get('id')
        if not creation_id:
            return {'error': 'Container oluşturulamadı'}
        return self._request(f"{self.graph_url}/{instagram_business_id}/media_publish", method='POST', data={'creation_id': creation_id})

    def publish_instagram_carousel(self, instagram_business_id, image_urls, caption):
        image_urls = [str(url).strip() for url in (image_urls or []) if str(url).strip()]
        if not 2 <= len(image_urls) <= 10:
            return {'error': 'Instagram carousel 2 ile 10 görsel içermelidir.'}

        child_ids = []
        for image_url in image_urls:
            child = self._request(
                f"{self.graph_url}/{instagram_business_id}/media",
                method='POST',
                data={'image_url': image_url, 'is_carousel_item': 'true'},
            )
            if 'error' in child:
                return child
            child_id = child.get('id')
            if not child_id:
                return {'error': 'Carousel alt görsel kapsayıcısı oluşturulamadı.'}
            child_ids.append(child_id)

        creation = self._request(
            f"{self.graph_url}/{instagram_business_id}/media",
            method='POST',
            data={'media_type': 'CAROUSEL', 'children': ','.join(child_ids), 'caption': caption},
        )
        if 'error' in creation:
            return creation
        creation_id = creation.get('id')
        if not creation_id:
            return {'error': 'Carousel kapsayıcısı oluşturulamadı.'}
        return self._request(
            f"{self.graph_url}/{instagram_business_id}/media_publish",
            method='POST',
            data={'creation_id': creation_id},
        )

    def refresh_access_token(self):
        return self._request(f"{self.base_url}/refresh_access_token", {'grant_type': 'ig_refresh_token'})

    def get_long_lived_token(self, short_lived_token):
        return self._request(f"{self.graph_url}/oauth/access_token", {'grant_type': 'ig_exchange_token', 'client_secret': settings.INSTAGRAM_APP_SECRET, 'access_token': short_lived_token})

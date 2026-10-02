"""Read-only Google connections, isolated from the Google Ads OAuth client."""
from datetime import timedelta
import hashlib
from urllib.parse import urlencode

import requests
from django.core.cache import cache
from django.db import transaction
from django.utils import timezone

from core.services.ads_integrations import IntegrationError, configuration

SCOPES = {
    "youtube": "https://www.googleapis.com/auth/youtube.readonly",
    "google_analytics": "https://www.googleapis.com/auth/analytics.readonly",
}


class GoogleReadRateLimitError(IntegrationError):
    def __init__(self, retry_after=300):
        self.retry_after = retry_after
        super().__init__("Google istek sınırına ulaşıldı. Bağlantı korunuyor; daha sonra tekrar deneyin.")


def request(method, url, *, quota_key="", **kwargs):
    key = "google_read:cooldown:" + hashlib.sha256(quota_key.encode()).hexdigest()
    if quota_key and cache.get(key):
        raise GoogleReadRateLimitError()
    try:
        response = requests.request(method, url, timeout=30, **kwargs)
        payload = response.json()
    except (requests.RequestException, ValueError):
        raise IntegrationError("Google servisine ulaşılamadı. Lütfen tekrar deneyin.") from None
    error = payload.get("error") if isinstance(payload, dict) else None
    reasons = {e.get("reason") for e in (error.get("errors", []) if isinstance(error, dict) else [])}
    if response.status_code == 429 or reasons.intersection({"quotaExceeded", "dailyLimitExceeded", "rateLimitExceeded", "userRateLimitExceeded"}):
        try:
            retry = max(60, min(86400, int(response.headers.get("Retry-After", 300))))
        except (ValueError, TypeError):
            retry = 300
        if reasons.intersection({"quotaExceeded", "dailyLimitExceeded"}):
            retry = max(retry, 3600)
        if quota_key:
            cache.set(key, True, timeout=retry)
        raise GoogleReadRateLimitError(retry)
    if not response.ok or error:
        if error == "invalid_grant":
            raise IntegrationError("Google yenileme izni sona ermiş veya kaldırılmış. Hesabı yeniden bağlayın.")
        if response.status_code == 403:
            raise IntegrationError("Google erişimi reddetti. API'nin açık olduğunu ve hesabın okuma yetkisini kontrol edin.")
        raise IntegrationError(f"Google isteği tamamlanamadı (HTTP {response.status_code}).")
    if not isinstance(payload, dict):
        raise IntegrationError("Google yanıtı doğrulanamadı.")
    return payload


def authorization_url(provider, state):
    client_id, _, redirect_uri = configuration(provider)
    return "https://accounts.google.com/o/oauth2/v2/auth?" + urlencode({
        "client_id": client_id, "redirect_uri": redirect_uri, "response_type": "code",
        "state": state, "scope": SCOPES[provider], "access_type": "offline",
        "prompt": "consent select_account",
    })


def exchange_code(provider, code):
    client_id, secret, redirect_uri = configuration(provider)
    data = request("POST", "https://oauth2.googleapis.com/token", data={
        "client_id": client_id, "client_secret": secret, "redirect_uri": redirect_uri,
        "code": code, "grant_type": "authorization_code",
    })
    if SCOPES[provider] not in data.get("scope", "").split():
        raise IntegrationError("Gerekli okuma izni verilmedi. Bağlantıyı yeniden başlatın.")
    if not data.get("access_token") or not data.get("refresh_token"):
        raise IntegrationError("Google kalıcı erişim izni dönmedi. Bağlantıyı yeniden başlatın.")
    return data


def connection_token(connection):
    from core.models import PlatformConnection
    if connection.platform.code not in SCOPES or not connection.is_active:
        raise IntegrationError("Bağlantı etkin değil. Hesabı yeniden bağlayın.")
    if connection.access_token and connection.token_expiry and connection.token_expiry > timezone.now() + timedelta(seconds=60):
        return connection.access_token
    with transaction.atomic():
        fresh = PlatformConnection.objects.select_for_update().select_related("platform").get(pk=connection.pk)
        if not fresh.is_active:
            raise IntegrationError("Bağlantı etkin değil.")
        if fresh.access_token and fresh.token_expiry and fresh.token_expiry > timezone.now() + timedelta(seconds=60):
            connection.access_token, connection.token_expiry = fresh.access_token, fresh.token_expiry
            return fresh.access_token
        if not fresh.refresh_token:
            raise IntegrationError("Google yenileme izni bulunamadı. Hesabı yeniden bağlayın.")
        client_id, secret, _ = configuration(fresh.platform.code)
        data = request("POST", "https://oauth2.googleapis.com/token", quota_key=client_id, data={
            "client_id": client_id, "client_secret": secret,
            "refresh_token": fresh.refresh_token, "grant_type": "refresh_token",
        })
        if not data.get("access_token"):
            raise IntegrationError("Google erişimi yenilenemedi.")
        fresh.access_token = data["access_token"]
        fresh.token_expiry = timezone.now() + timedelta(seconds=int(data.get("expires_in", 3600)))
        fresh.refresh_token = data.get("refresh_token") or fresh.refresh_token
        fresh.status = "active"
        fresh.save(update_fields=["access_token", "refresh_token", "token_expiry", "status", "updated_at"])
        fresh.accounts.update(access_token=fresh.access_token, refresh_token=fresh.refresh_token, token_expiry=fresh.token_expiry)
        connection.access_token, connection.refresh_token, connection.token_expiry = fresh.access_token, fresh.refresh_token, fresh.token_expiry
        return fresh.access_token


def discover_accounts(provider, token):
    headers = {"Authorization": f"Bearer {token}"}
    client_id = configuration(provider)[0]
    rows, seen, page = {}, set(), ""
    for _ in range(100):
        if provider == "youtube":
            data = request("GET", "https://www.googleapis.com/youtube/v3/channels", quota_key=client_id,
                           headers=headers, params={"part": "snippet,statistics", "mine": "true", "maxResults": 50, "pageToken": page})
            for item in data.get("items", []):
                rows[item["id"]] = {"id": item["id"], "name": item.get("snippet", {}).get("title", item["id"]),
                                    "kind": "youtube_channel", "statistics": item.get("statistics", {})}
        else:
            data = request("GET", "https://analyticsadmin.googleapis.com/v1beta/accountSummaries", quota_key=client_id,
                           headers=headers, params={"pageSize": 200, "pageToken": page})
            for account in data.get("accountSummaries", []):
                for item in account.get("propertySummaries", []):
                    pid = item.get("property", "").removeprefix("properties/")
                    if pid.isdigit():
                        rows[pid] = {"id": pid, "name": item.get("displayName", pid), "kind": "ga4_property", "property_id": pid}
        page = data.get("nextPageToken", "")
        if not page:
            return list(rows.values())
        if page in seen:
            break
        seen.add(page)
    raise IntegrationError("Google hesap listesi tamamlanamadı. Yeniden deneyin.")

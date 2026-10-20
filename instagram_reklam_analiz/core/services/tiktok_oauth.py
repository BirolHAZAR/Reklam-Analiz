"""TikTok Login Kit and read-only Display API; never return provider errors."""
from datetime import timedelta
from urllib.parse import urlencode

from django.db import transaction
from django.utils import timezone
from core.models import PlatformConnection

import requests

from core.services.ads_integrations import IntegrationError, configuration

SCOPES = ("user.info.basic", "user.info.profile", "user.info.stats", "video.list")
API = "https://open.tiktokapis.com/v2"
PROFILE_FIELDS = ("open_id", "display_name", "username", "bio_description",
                  "follower_count", "following_count", "likes_count", "video_count")
VIDEO_FIELDS = ("id", "title", "video_description", "create_time", "view_count",
                "like_count", "comment_count", "share_count", "cover_image_url", "share_url")


def request(method, path, **kwargs):
    try:
        response = requests.request(method, f"{API}/{path}/", timeout=30, **kwargs)
        payload = response.json()
    except (requests.RequestException, ValueError):
        raise IntegrationError("TikTok'a ulaşılamadı. Lütfen tekrar deneyin.") from None
    error = payload.get("error") if isinstance(payload, dict) else True
    failed = (error.get("code") != "ok") if isinstance(error, dict) else bool(error)
    if not response.ok or not isinstance(payload, dict) or failed:
        raise IntegrationError("TikTok isteği tamamlanamadı. İzinleri kontrol edip yeniden bağlanın.")
    return payload


def authorization_url(state):
    key, _, uri = configuration("tiktok")
    return "https://www.tiktok.com/v2/auth/authorize/?" + urlencode({
        "client_key": key, "redirect_uri": uri, "scope": ",".join(SCOPES),
        "response_type": "code", "state": state,
    })


def token_request(**values):
    key, secret, _ = configuration("tiktok")
    result = request("POST", "oauth/token", data={
        "client_key": key, "client_secret": secret, **values,
    })
    scopes = result.get("scope")
    try:
        expires = int(result.get("expires_in", 0))
        refresh_expires = int(result.get("refresh_expires_in", 0))
    except (ValueError, TypeError, OverflowError):
        raise IntegrationError("TikTok erişim süresi doğrulanamadı.") from None
    if (not isinstance(scopes, str) or not set(SCOPES).issubset(scopes.split(","))
            or not all(isinstance(result.get(k), str) and result[k] for k in
                       ("access_token", "refresh_token", "open_id"))
            or not 0 < expires <= 31536000 or not 0 < refresh_expires <= 63072000
            or result.get("token_type", "").lower() != "bearer"
            or len(result["open_id"]) > 100):
        raise IntegrationError("TikTok profil ve video okuma izinlerini vererek yeniden bağlanın.")
    return {k: result[k] for k in ("access_token", "refresh_token", "open_id")} | {
        "scope": scopes.split(","), "expires_in": expires, "refresh_expires_in": refresh_expires,
    }


def profile(access_token, open_id):
    result = request("GET", "user/info", headers={"Authorization": f"Bearer {access_token}"},
                     params={"fields": ",".join(PROFILE_FIELDS)})
    data = result.get("data")
    user = data.get("user") if isinstance(data, dict) else None
    if not isinstance(user, dict) or user.get("open_id") != open_id:
        raise IntegrationError("TikTok hesap kimliği doğrulanamadı. Yeniden bağlanın.")
    return {k: user.get(k) for k in PROFILE_FIELDS}


def exchange_code(code):
    _, _, uri = configuration("tiktok")
    token = token_request(grant_type="authorization_code", code=code, redirect_uri=uri)
    return token, profile(token["access_token"], token["open_id"])


def videos(access_token, cursor=None):
    body = {"max_count": 20}
    if cursor is not None:
        body["cursor"] = cursor
    payload = request("POST", "video/list", headers={"Authorization": f"Bearer {access_token}"},
                      params={"fields": ",".join(VIDEO_FIELDS)}, json=body)
    data = payload.get("data")
    if not isinstance(data, dict) or not isinstance(data.get("videos"), list):
        raise IntegrationError("TikTok video listesi okunamadı.")
    if any(not isinstance(row, dict) for row in data["videos"]) or not isinstance(data.get("has_more"), bool):
        raise IntegrationError("TikTok video listesi doğrulanamadı.")
    rows = [{k: row.get(k) for k in VIDEO_FIELDS} for row in data["videos"]]
    next_cursor = data.get("cursor")
    if data.get("has_more") and (not isinstance(next_cursor, int) or isinstance(next_cursor, bool) or next_cursor < 0):
        raise IntegrationError("TikTok video sayfalaması doğrulanamadı.")
    return rows, next_cursor if data.get("has_more") else None


@transaction.atomic
def access_token(account):
    connection = PlatformConnection.objects.select_for_update().get(pk=account.connection_id)
    if (connection.user_id != account.user_id or connection.platform_id != account.platform_id
            or not account.is_active or not connection.is_active or connection.status != "active"
            or (connection.extra_data or {}).get("source") != "tiktok_oauth"):
        raise IntegrationError("TikTok hesabını yeniden bağlayın.")
    if ((connection.extra_data or {}).get("profile", {}).get("open_id") != account.account_id
            or not set(SCOPES).issubset(connection.scopes or [])):
        raise IntegrationError("TikTok hesap kimliği veya okuma izinleri doğrulanamadı. Yeniden bağlanın.")
    key, _, _ = configuration("tiktok")
    if (connection.extra_data or {}).get("client_key") != key:
        raise IntegrationError("TikTok uygulama ayarı değişmiş. Hesabı yeniden bağlayın.")
    if not connection.token_expiry or connection.token_expiry <= timezone.now() + timedelta(minutes=2):
        if not connection.refresh_token:
            raise IntegrationError("TikTok erişim süresi dolmuş. Yeniden bağlayın.")
        token = token_request(grant_type="refresh_token", refresh_token=connection.refresh_token)
        if token["open_id"] != account.account_id:
            raise IntegrationError("TikTok yenileme hesabı doğrulanamadı.")
        connection.access_token, connection.refresh_token = token["access_token"], token["refresh_token"]
        connection.token_expiry = timezone.now() + timedelta(seconds=token["expires_in"])
        connection.scopes = token["scope"]
        connection.extra_data = {**connection.extra_data, "refresh_expiry":
            (timezone.now() + timedelta(seconds=token["refresh_expires_in"])).isoformat()}
        connection.save()
        # Keep the account's encrypted token copy aligned with its connection.
        account.access_token, account.refresh_token = connection.access_token, connection.refresh_token
        account.token_expiry = connection.token_expiry
        account.save(update_fields=["access_token", "refresh_token", "token_expiry", "updated_at"])
    return connection.access_token



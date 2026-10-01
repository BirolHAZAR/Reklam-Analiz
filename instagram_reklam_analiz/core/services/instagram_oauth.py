"""Instagram professional login; credentials stay on the server."""
from urllib.parse import urlencode

from django.conf import settings

from core.services.ads_integrations import IntegrationError, _request, configuration

SCOPES = ("instagram_business_basic", "instagram_business_manage_insights")


def graph_url():
    version = settings.FACEBOOK_GRAPH_URL.rstrip("/").split("/")[-1]
    return f"https://graph.instagram.com/{version}"


def authorization_url(state):
    client_id, _, redirect_uri = configuration("instagram")
    return "https://www.instagram.com/oauth/authorize?" + urlencode({
        "client_id": client_id, "redirect_uri": redirect_uri,
        "response_type": "code", "scope": ",".join(SCOPES), "state": state,
        "enable_fb_login": "0",
    })


def profile(token):
    data = _request("GET", f"{graph_url()}/me", params={
        "fields": "user_id,username", "access_token": token,
    }, operation="Instagram profilini okuma")
    if not isinstance(data, dict) or not str(data.get("user_id", "")).isdigit() or not data.get("username"):
        raise IntegrationError("Instagram profil bilgileri alınamadı. Yeniden bağlanın.")
    return {"id": str(data["user_id"]), "username": str(data["username"])}


def exchange_code(code):
    client_id, secret, redirect_uri = configuration("instagram")
    short = _request("POST", "https://api.instagram.com/oauth/access_token", operation="Instagram giriş kodunu doğrulama", data={
        "client_id": client_id, "client_secret": secret, "redirect_uri": redirect_uri,
        "grant_type": "authorization_code", "code": code,
    })
    if isinstance(short, dict) and "data" in short:
        rows = short["data"]
        if short.get("access_token") or not isinstance(rows, list) or len(rows) != 1:
            raise IntegrationError("Instagram giriş yanıtı doğrulanamadı.")
        short = rows[0]
    if not isinstance(short, dict) or not short.get("access_token"):
        raise IntegrationError("Instagram erişim izni alınamadı.")
    permissions = short.get("permissions", [])
    if isinstance(permissions, str):
        permissions = permissions.replace(",", " ").split()
    if not isinstance(permissions, list) or not set(SCOPES).issubset(permissions):
        raise IntegrationError("Profil ve istatistik izinlerini vererek Instagram'ı yeniden bağlayın.")
    token = _request("GET", "https://graph.instagram.com/access_token", operation="Instagram erişim süresini uzatma", params={
        "grant_type": "ig_exchange_token", "client_secret": secret,
        "access_token": short["access_token"],
    })
    if not isinstance(token, dict) or not token.get("access_token"):
        raise IntegrationError("Instagram bağlantısı tamamlanamadı.")
    try:
        token["expires_in"] = int(token.get("expires_in", 0))
    except (TypeError, ValueError):
        raise IntegrationError("Instagram erişim süresi doğrulanamadı.") from None
    if token["expires_in"] <= 0:
        raise IntegrationError("Instagram erişim süresi doğrulanamadı.")
    account = profile(token["access_token"])
    # The authorization-code response and ``/me`` can expose different ID
    # namespaces for the same professional account. The long-lived token is
    # already bound to the profile returned by ``/me``; comparing those two
    # provider-specific identifiers rejects valid Instagram logins.
    token["scope"] = list(SCOPES)
    return token, account

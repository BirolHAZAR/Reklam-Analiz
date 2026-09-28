"""Official OAuth and read-only reporting for advertiser-owned accounts."""
from datetime import timedelta
from decimal import Decimal
import json
import re
from urllib.parse import urlencode
from urllib.parse import urlsplit
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

import requests
from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils import timezone

ADWORDS_SCOPE = "https://www.googleapis.com/auth/adwords"
PROVIDERS = {"google_ads": "Google Ads", "facebook": "Meta Ads (Facebook ve Instagram)"}


class IntegrationError(ValueError):
    pass


def application_values(provider):
    if provider == "google_ads":
        names = ("GOOGLE_ADS_CLIENT_ID", "GOOGLE_ADS_CLIENT_SECRET", "GOOGLE_ADS_REDIRECT_URI", "GOOGLE_ADS_DEVELOPER_TOKEN")
    elif provider == "facebook":
        names = ("FACEBOOK_APP_ID", "FACEBOOK_APP_SECRET", "FACEBOOK_REDIRECT_URI")
    else:
        raise IntegrationError("Bu platform için reklam OAuth bağlantısı henüz desteklenmiyor.")
    from core.models import IntegrationApplication
    application = IntegrationApplication.objects.filter(provider=provider).first()
    if application is not None:
        if not application.enabled:
            raise IntegrationError("Yönetici bu platformun bağlantısını kapattı.")
        values = [application.client_id, application.client_secret, application.redirect_uri]
        if provider == "google_ads":
            values.append(application.developer_token)
    else:
        values = [getattr(settings, name, "") or "" for name in names]
    values = [value.strip() if isinstance(value, str) else value for value in values]
    if not all(values):
        raise IntegrationError("Platform bağlantısı sunucuda henüz yapılandırılmamış. Yöneticiyle iletişime geçin.")
    candidate = IntegrationApplication(
        provider=provider, client_id=values[0], client_secret=values[1],
        redirect_uri=values[2], enabled=True,
        developer_token=values[3] if provider == "google_ads" else "",
    )
    try:
        candidate.clean()
    except ValidationError:
        raise IntegrationError("Platformun OAuth dönüş adresi geçersiz. Yönetici uygulama ayarlarını kontrol etmeli.") from None
    if not settings.DEBUG and urlsplit(values[2]).hostname in {"localhost", "127.0.0.1"}:
        raise IntegrationError("Canlı ortam için HTTPS site dönüş adresi gerekli. Yönetici uygulama ayarlarını kontrol etmeli.")
    return values


def configuration(provider):
    return application_values(provider)[:3]


def authorization_url(provider, state):
    client_id, _, redirect_uri = configuration(provider)
    params = {"client_id": client_id, "redirect_uri": redirect_uri, "response_type": "code", "state": state}
    if provider == "google_ads":
        params.update(scope=ADWORDS_SCOPE, access_type="offline", prompt="consent select_account")
        url = "https://accounts.google.com/o/oauth2/v2/auth"
    else:
        params.update(scope="ads_read", auth_type="rerequest")
        url = f"https://www.facebook.com/{settings.FACEBOOK_GRAPH_URL.rstrip('/').split('/')[-1]}/dialog/oauth"
    return url + "?" + urlencode(params)


def _request(method, url, **kwargs):
    # Never expose requests exceptions (URLs may contain authorization codes),
    # response bodies or provider-echoed credentials to notifications/logs.
    try:
        response = requests.request(method, url, timeout=30, **kwargs)
        payload = response.json()
    except (requests.RequestException, ValueError):
        raise IntegrationError("Platforma ulaşılamadı. Lütfen tekrar deneyin.") from None
    if not response.ok or (isinstance(payload, dict) and payload.get("error")):
        error = payload.get("error", {}) if isinstance(payload, dict) else {}
        code = error.get("code", error.get("status", "")) if isinstance(error, dict) else error
        code = re.sub(r"[^a-zA-Z0-9_ -]", "", str(code))[:50]
        subcode = error.get("error_subcode") if isinstance(error, dict) else None
        suffix = f" / {subcode}" if isinstance(subcode, int) else ""
        raise IntegrationError(f"Platform isteği reddedildi (HTTP {response.status_code}, {code}{suffix}). Hesap erişimini ve uygulama izinlerini kontrol edin.")
    return payload


def exchange_code(provider, code):
    client_id, secret, redirect_uri = configuration(provider)
    if provider == "google_ads":
        data = _request("POST", "https://oauth2.googleapis.com/token", data={
            "client_id": client_id, "client_secret": secret, "code": code,
            "redirect_uri": redirect_uri, "grant_type": "authorization_code",
        })
        if ADWORDS_SCOPE not in data.get("scope", "").split():
            raise IntegrationError("Google Ads izni verilmedi. Bağlantıyı yeniden başlatıp reklam hesabı erişimine izin verin.")
        if not data.get("refresh_token"):
            raise IntegrationError("Google kalıcı erişim izni dönmedi. Bağlantıyı yeniden başlatıp izin verin.")
    else:
        data = _request("GET", f"{settings.FACEBOOK_GRAPH_URL}/oauth/access_token", params={
            "client_id": client_id, "client_secret": secret, "redirect_uri": redirect_uri, "code": code,
        })
        if not data.get("access_token"):
            raise IntegrationError("Meta erişim bilgisi alınamadı.")
        data = _request("GET", f"{settings.FACEBOOK_GRAPH_URL}/oauth/access_token", params={
            "grant_type": "fb_exchange_token", "client_id": client_id,
            "client_secret": secret, "fb_exchange_token": data["access_token"],
        })
        permissions = meta_rows(data.get("access_token", ""), "me/permissions", {})
        granted = [row["permission"] for row in permissions if row.get("status") == "granted"]
        if not {"ads_read", "ads_management"}.intersection(granted):
            raise IntegrationError("Meta reklam okuma izni verilmedi. Bağlantıyı yeniden başlatın.")
        data["scope"] = " ".join(granted)
    if not data.get("access_token"):
        raise IntegrationError("Erişim bilgisi alınamadı.")
    return data


def connection_token(connection):
    if not connection.is_active:
        raise IntegrationError("Bağlantı etkin değil. Hesabı yeniden bağlayın.")
    if connection.platform.code != "google_ads":
        if connection.is_token_expired:
            raise IntegrationError("Meta izninin süresi dolmuş. Hesabı yeniden bağlayın.")
        return connection.access_token
    if connection.token_expiry and connection.token_expiry > timezone.now() + timedelta(seconds=60):
        return connection.access_token
    from core.models import PlatformConnection
    with transaction.atomic():
        fresh = PlatformConnection.objects.select_for_update().get(pk=connection.pk)
        if not fresh.is_active:
            raise IntegrationError("Bağlantı etkin değil.")
        if fresh.token_expiry and fresh.token_expiry > timezone.now() + timedelta(seconds=60):
            connection.access_token, connection.token_expiry = fresh.access_token, fresh.token_expiry
            return fresh.access_token
        if not fresh.refresh_token:
            raise IntegrationError("Google hesabını yeniden bağlayın; yenileme izni bulunamadı.")
        client_id, secret, _ = configuration("google_ads")
        data = _request("POST", "https://oauth2.googleapis.com/token", data={
            "grant_type": "refresh_token", "refresh_token": fresh.refresh_token,
            "client_id": client_id, "client_secret": secret,
        })
        if not data.get("access_token"):
            raise IntegrationError("Google erişimi yenilenemedi.")
        fresh.access_token = data["access_token"]
        fresh.token_expiry = timezone.now() + timedelta(seconds=int(data.get("expires_in", 3600)))
        if data.get("refresh_token"):
            fresh.refresh_token = data["refresh_token"]
        fresh.status = "active"
        fresh.save(update_fields=["access_token", "refresh_token", "token_expiry", "status", "updated_at"])
        fresh.accounts.update(access_token=fresh.access_token, refresh_token=fresh.refresh_token, token_expiry=fresh.token_expiry)
        connection.access_token, connection.token_expiry = fresh.access_token, fresh.token_expiry
        return fresh.access_token


def _google_headers(token, manager_id=""):
    headers = {"Authorization": f"Bearer {token}", "developer-token": application_values("google_ads")[3]}
    if manager_id:
        headers["login-customer-id"] = str(manager_id)
    return headers


def google_search(token, customer_id, query, manager_id=""):
    url = f"https://googleads.googleapis.com/{settings.GOOGLE_ADS_API_VERSION}/customers/{customer_id}/googleAds:search"
    rows, page_token = [], None
    while True:
        body = {"query": query}
        if page_token:
            body["pageToken"] = page_token
        data = _request("POST", url, headers=_google_headers(token, manager_id), json=body)
        rows.extend(data.get("results", []))
        next_token = data.get("nextPageToken")
        if not next_token:
            return rows
        if next_token == page_token:
            raise IntegrationError("Google sayfalama tamamlanamadı.")
        page_token = next_token


def meta_rows(token, path, params):
    # Rebuild the fixed Graph endpoint with a cursor, never follow an arbitrary
    # pagination URL with an Authorization header.
    rows, after = [], None
    while True:
        query = {**params, "limit": 100}
        if after:
            query["after"] = after
        data = _request("GET", f"{settings.FACEBOOK_GRAPH_URL}/{path}",
                        headers={"Authorization": f"Bearer {token}"}, params=query)
        rows.extend(data.get("data", []))
        paging = data.get("paging", {})
        if not paging.get("next"):
            return rows
        cursor = paging.get("cursors", {}).get("after")
        if not cursor or cursor == after:
            raise IntegrationError("Meta sayfalama tamamlanamadı.")
        after = cursor


def discover_accounts(provider, token):
    if provider == "facebook":
        return [{"id": r["id"], "name": r.get("name", r["id"]),
                 "currency": r.get("currency", ""), "timezone": r.get("timezone_name", ""),
                 "kind": "ad_account"}
                for r in meta_rows(token, "me/adaccounts", {"fields": "id,name,currency,timezone_name,account_status"})
                if r.get("account_status") == 1]
    data = _request("GET", f"https://googleads.googleapis.com/{settings.GOOGLE_ADS_API_VERSION}/customers:listAccessibleCustomers",
                    headers=_google_headers(token))
    accounts = {}
    for resource in data.get("resourceNames", []):
        root = resource.split("/")[-1]
        info = google_search(token, root, "SELECT customer.id, customer.descriptive_name, customer.manager, customer.currency_code, customer.time_zone FROM customer")
        if not info:
            continue
        customer = info[0]["customer"]
        if not customer.get("manager"):
            accounts[root] = {"id": root, "name": customer.get("descriptiveName") or root,
                              "currency": customer.get("currencyCode", ""), "timezone": customer.get("timeZone", ""), "kind": "ad_account"}
            continue
        children = google_search(token, root, "SELECT customer_client.id, customer_client.descriptive_name, customer_client.manager, customer_client.currency_code, customer_client.time_zone, customer_client.status FROM customer_client WHERE customer_client.manager = FALSE AND customer_client.status = 'ENABLED'", root)
        for row in children:
            c = row["customerClient"]
            cid = str(c["id"])
            accounts.setdefault(cid, {"id": cid, "name": c.get("descriptiveName") or cid,
                                     "currency": c.get("currencyCode", ""), "timezone": c.get("timeZone", ""),
                                     "login_customer_id": root, "kind": "ad_account"})
    return list(accounts.values())


def account_token(account):
    if not account.connection_id or (account.connection.extra_data or {}).get("source") != "ads_oauth":
        raise IntegrationError("Bu hesabı Hesap Ekle ekranından yeniden bağlayın.")
    return connection_token(account.connection)


def account_today(account):
    zone = (account.extra_data or {}).get("timezone")
    try:
        return timezone.localdate(timezone=ZoneInfo(zone)) if zone else timezone.localdate()
    except (ZoneInfoNotFoundError, ValueError):
        return timezone.localdate()


def campaigns(account):
    token = account_token(account)
    if account.platform.code == "google_ads":
        rows = google_search(token, account.account_id, "SELECT campaign.id, campaign.name, campaign.status, campaign.advertising_channel_type FROM campaign WHERE campaign.status != 'REMOVED'", account.extra_data.get("login_customer_id", ""))
        return [{"id": str(r["campaign"]["id"]), "name": r["campaign"]["name"], "status": r["campaign"]["status"], "channel": r["campaign"].get("advertisingChannelType", "")} for r in rows]
    return meta_rows(token, f"{account.account_id}/campaigns", {"fields": "id,name,status,objective"})


def campaign_performance(account, campaign_id, start, end):
    if not str(campaign_id).isdigit():
        raise IntegrationError("Geçersiz kampanya.")
    token = account_token(account)
    if account.platform.code == "google_ads":
        query = f"SELECT segments.date, metrics.impressions, metrics.clicks, metrics.cost_micros, metrics.conversions, metrics.conversions_value FROM campaign WHERE campaign.id = {campaign_id} AND segments.date BETWEEN '{start.isoformat()}' AND '{end.isoformat()}' ORDER BY segments.date"
        rows = google_search(token, account.account_id, query, account.extra_data.get("login_customer_id", ""))
        return [{"date": r["segments"]["date"], **google_metrics(r["metrics"])} for r in rows]
    return [{"date": r["date_start"], "impressions": int(r.get("impressions", 0)),
             "clicks": int(r.get("clicks", 0)), "spend": Decimal(r.get("spend", "0"))}
            for r in meta_rows(token, f"{account.account_id}/insights", {
                "level": "campaign", "fields": "date_start,impressions,clicks,spend",
                "time_increment": 1, "time_range": json.dumps({"since": start.isoformat(), "until": end.isoformat()}),
                "filtering": json.dumps([{"field": "campaign.id", "operator": "IN", "value": [str(campaign_id)]}]),
            })]


def google_metrics(metrics):
    return {"impressions": int(metrics.get("impressions", 0)), "clicks": int(metrics.get("clicks", 0)),
            "spend": Decimal(metrics.get("costMicros", "0")) / Decimal("1000000"),
            "conversions": Decimal(str(metrics.get("conversions", 0))),
            "conversion_value": Decimal(str(metrics.get("conversionsValue", 0)))}

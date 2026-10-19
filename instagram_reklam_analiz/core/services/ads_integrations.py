"""Official OAuth and read-only reporting for advertiser-owned accounts."""
from datetime import timedelta
from decimal import Decimal
import json
import logging
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
PROVIDERS = {"google_ads": "Google Ads", "facebook": "Meta Ads (Facebook ve Instagram)", "linkedin": "LinkedIn Ads"}
GOOGLE_READ_PROVIDERS = {"youtube": "YouTube"}
CONNECTION_PROVIDERS = {**PROVIDERS, **GOOGLE_READ_PROVIDERS}
logger = logging.getLogger(__name__)


class IntegrationError(ValueError):
    def __init__(self, message, *, google_codes=()):
        self.google_codes = tuple(google_codes)
        super().__init__(message)


class IntegrationRateLimitError(IntegrationError):
    def __init__(self, error):
        self.retry_after = error.retry_after
        super().__init__(str(error))


class IntegrationTransportError(IntegrationError):
    """Temporary transport/response failure, safe to retry during a read job."""

    def __init__(self, message, *, is_timeout=False):
        self.is_timeout = is_timeout
        super().__init__(message)


def application_values(provider):
    if provider == "google_ads":
        names = ("GOOGLE_ADS_CLIENT_ID", "GOOGLE_ADS_CLIENT_SECRET", "GOOGLE_ADS_REDIRECT_URI", "GOOGLE_ADS_DEVELOPER_TOKEN")
    elif provider == "facebook":
        names = ("FACEBOOK_APP_ID", "FACEBOOK_APP_SECRET", "FACEBOOK_REDIRECT_URI")
    elif provider == "instagram":
        names = ("INSTAGRAM_APP_ID", "INSTAGRAM_APP_SECRET", "INSTAGRAM_REDIRECT_URI")
    elif provider == "tiktok":
        names = ("TIKTOK_CLIENT_KEY", "TIKTOK_CLIENT_SECRET", "TIKTOK_REDIRECT_URI")
    elif provider == "linkedin":
        if not getattr(settings, "LINKEDIN_ADS_APPROVED", False):
            raise IntegrationError("LinkedIn Advertising API onayı bekleniyor. Onay sonrası yönetici bağlantıyı açabilir.")
        names = ("LINKEDIN_CLIENT_ID", "LINKEDIN_CLIENT_SECRET", "LINKEDIN_REDIRECT_URI")
    elif provider in GOOGLE_READ_PROVIDERS:
        prefix = "YOUTUBE"
        names = (f"{prefix}_CLIENT_ID", f"{prefix}_CLIENT_SECRET", f"{prefix}_REDIRECT_URI")
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
    required_values = values[:3] if provider == "google_ads" else values
    if not all(required_values):
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
    if provider == "linkedin":
        from core.services.linkedin_ads import authorization_url as linkedin_url
        return linkedin_url(state)
    if provider in GOOGLE_READ_PROVIDERS:
        from core.services.google_read_oauth import authorization_url as google_url
        return google_url(provider, state)
    client_id, _, redirect_uri = configuration(provider)
    params = {"client_id": client_id, "redirect_uri": redirect_uri, "response_type": "code", "state": state}
    if provider == "google_ads":
        params.update(scope=ADWORDS_SCOPE, access_type="offline", prompt="consent select_account")
        url = "https://accounts.google.com/o/oauth2/v2/auth"
    else:
        params.update(scope="ads_read", auth_type="rerequest")
        url = f"https://www.facebook.com/{settings.FACEBOOK_GRAPH_URL.rstrip('/').split('/')[-1]}/dialog/oauth"
    return url + "?" + urlencode(params)


def _google_error_codes(error):
    """Return structured error enums only; never provider messages or metadata."""
    details = error.get("details", [])
    if not isinstance(details, list):
        return []
    codes = []
    for detail in details[:20]:
        if not isinstance(detail, dict):
            continue
        kind = detail.get("@type", "")
        if isinstance(kind, str) and re.fullmatch(
            r"type\.googleapis\.com/google\.ads\.googleads\.v[0-9]+\.errors\.GoogleAdsFailure", kind
        ):
            errors = detail.get("errors", [])
            if not isinstance(errors, list):
                continue
            for item in errors[:20]:
                code_map = item.get("errorCode", {}) if isinstance(item, dict) else {}
                if not isinstance(code_map, dict):
                    continue
                for group, value in code_map.items():
                    if group in {"authorizationError", "authenticationError", "requestError", "quotaError", "internalError", "queryError"} and isinstance(value, str) and re.fullmatch(r"[A-Z][A-Z_]{1,79}", value):
                        code = f"{group}.{value}"
                        if code not in codes:
                            codes.append(code)
        elif kind == "type.googleapis.com/google.rpc.ErrorInfo":
            reason = detail.get("reason", "")
            if isinstance(reason, str) and re.fullmatch(r"[A-Z][A-Z_]{1,79}", reason):
                code = f"ErrorInfo.{reason}"
                if code not in codes:
                    codes.append(code)
    return codes[:5]


def _request(method, url, *, operation="", **kwargs):
    # Never expose requests exceptions (URLs may contain authorization codes),
    # response bodies or provider-echoed credentials to notifications/logs.
    from core.services.meta_rate_limit import before_request, after_response, MetaRateLimitError
    try:
        before_request(url, kwargs)
        response = requests.request(method, url, timeout=30, **kwargs)
        payload = response.json()
        after_response(url, kwargs, response, payload)
    except MetaRateLimitError as exc:
        raise IntegrationRateLimitError(exc) from None
    except (requests.RequestException, ValueError) as exc:
        prefix = f"{operation}: " if operation else ""
        logger.warning("Provider transport failed operation=%s exception_type=%s",
                       operation or "unspecified", type(exc).__name__)
        raise IntegrationTransportError(f"{prefix}Platforma ulaşılamadı. Lütfen tekrar deneyin.",
                                        is_timeout=isinstance(exc, requests.Timeout)) from None
    if not response.ok or (isinstance(payload, dict) and payload.get("error")):
        error = payload.get("error", {}) if isinstance(payload, dict) else {}
        if not isinstance(error, dict):
            error = {"message": error}
        # Graph API nests errors under ``error``. Instagram's token endpoint
        # returns the same fields at the top level.
        code = error.get("code", error.get("status", payload.get("code", "") if isinstance(payload, dict) else ""))
        code = re.sub(r"[^a-zA-Z0-9_ -]", "", str(code))[:50]
        error_type = error.get("type", payload.get("error_type", "") if isinstance(payload, dict) else "")
        error_type = re.sub(r"[^a-zA-Z0-9_ -]", "", str(error_type))[:80]
        message = error.get("message", payload.get("error_message", "") if isinstance(payload, dict) else "")
        message = str(message).lower()
        subcode = error.get("error_subcode")
        suffix = f" / {subcode}" if isinstance(subcode, int) else ""
        prefix = f"{operation}: " if operation else ""
        logger.warning(
            "OAuth provider request rejected operation=%s status=%s error_type=%s error_code=%s error_subcode=%s",
            operation or "unspecified", response.status_code, error_type or "unknown", code or "unknown", subcode or "none",
        )
        if urlsplit(url).hostname == "googleads.googleapis.com":
            google_codes = _google_error_codes(error)
            if google_codes:
                logger.warning("Google Ads request rejected operation=%s status=%s structured_codes=%s",
                               operation or "unspecified", response.status_code, ", ".join(google_codes))
                guidance = {
                    "authorizationError.CUSTOMER_NOT_ENABLED": "Google Ads hesabı etkin değil. Google Ads panelinde hesap kurulumunu ve hesap durumunu kontrol edin.",
                    "authorizationError.CLOUD_PROJECT_NOT_APPROVED_FOR_PRODUCTION": "Uygulamanın Google Cloud projesi gerçek reklam hesaplarına erişim için onaylı değil. Yönetici Google Ads API erişim seviyesini kontrol etmeli.",
                    "authorizationError.USER_PERMISSION_DENIED": "Seçtiğiniz Google kullanıcısının bu reklam hesabına erişimi yok. Hesaba erişimi olan Google kullanıcısıyla yeniden bağlanın.",
                    "authenticationError.OAUTH_TOKEN_INVALID": "Google erişim izni geçersiz. Google Ads hesabını yeniden bağlayın.",
                    "ErrorInfo.SERVICE_DISABLED": "Uygulamanın Google Cloud projesinde Google Ads API kapalı. Yönetici API'yi etkinleştirmeli.",
                }
                hint = next((guidance[code] for code in google_codes if code in guidance), "")
                raise IntegrationError(f"{prefix}{hint + ' ' if hint else ''}Google Ads isteği reddedildi (HTTP {response.status_code}, {', '.join(google_codes)}).", google_codes=google_codes)
        if any(marker in message for marker in ("client secret", "client_secret", "app secret", "invalid platform app")):
            raise IntegrationError(
                f"{prefix}Uygulama kimliği ile gizli anahtar eşleşmiyor. Yönetici platform ayarındaki güncel App Secret değerini kaydetmeli."
            )
        if "redirect_uri" in message or "redirect uri" in message:
            raise IntegrationError(
                f"{prefix}OAuth dönüş adresi platform ayarıyla eşleşmiyor. Yönetici kayıtlı dönüş adresini kontrol etmeli."
            )
        detail = ", ".join(part for part in (error_type, code) if part) or "sağlayıcı hatası"
        raise IntegrationError(f"{prefix}Platform isteği reddedildi (HTTP {response.status_code}, {detail}{suffix}).")
    return payload


def exchange_code(provider, code):
    if provider == "linkedin":
        from core.services.linkedin_ads import exchange_code as linkedin_exchange
        return linkedin_exchange(code)
    if provider in GOOGLE_READ_PROVIDERS:
        from core.services.google_read_oauth import exchange_code as google_exchange
        return google_exchange(provider, code)
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
        data = _request("GET", f"{settings.FACEBOOK_GRAPH_URL}/oauth/access_token", operation="Meta giriş kodunu doğrulama", params={
            "client_id": client_id, "client_secret": secret, "redirect_uri": redirect_uri, "code": code,
        })
        if not data.get("access_token"):
            raise IntegrationError("Meta erişim bilgisi alınamadı.")
        data = _request("GET", f"{settings.FACEBOOK_GRAPH_URL}/oauth/access_token", operation="Meta erişim süresini uzatma", params={
            "grant_type": "fb_exchange_token", "client_id": client_id,
            "client_secret": secret, "fb_exchange_token": data["access_token"],
        })
        # Do not silently turn a valid long-lived grant into a one-hour local
        # connection when Meta omits expires_in. Read its actual deadline.
        if not data.get("access_token"):
            raise IntegrationError("Meta erişim bilgisi alınamadı.")
        try:
            expires_in = int(data.get("expires_in") or 0)
        except (ValueError, TypeError):
            expires_in = 0
        if expires_in <= 0:
            debug = _request("GET", f"{settings.FACEBOOK_GRAPH_URL}/debug_token", params={
                "input_token": data["access_token"], "access_token": f"{client_id}|{secret}",
            }, operation="Meta erişim süresini doğrulama").get("data", {})
            try:
                expires_in = int(debug.get("expires_at") or 0) - int(timezone.now().timestamp())
            except (ValueError, TypeError):
                expires_in = 0
            if debug.get("is_valid") and debug.get("expires_at") == 0:
                # Meta explicitly reports no token deadline. Data-access expiry
                # is independent and is tracked by the health service.
                expires_in = None
            elif not debug.get("is_valid") or expires_in <= 0:
                raise IntegrationError("Meta erişim süresi doğrulanamadı. Yeniden bağlanın.")
        data["expires_in"] = expires_in
        permissions = meta_rows(data.get("access_token", ""), "me/permissions", {})
        granted = [row["permission"] for row in permissions if row.get("status") == "granted"]
        if not {"ads_read", "ads_management"}.intersection(granted):
            raise IntegrationError("Meta reklam okuma izni verilmedi. Bağlantıyı yeniden başlatın.")
        data["scope"] = " ".join(granted)
        identity = _request("GET", f"{settings.FACEBOOK_GRAPH_URL}/me",
                            operation="Meta bağlantı kimliğini doğrulama",
                            headers={"Authorization": f"Bearer {data['access_token']}"}, params={"fields": "id"})
        subject = str(identity.get("id", "")) if isinstance(identity, dict) else ""
        if not re.fullmatch(r"[0-9]{1,100}", subject):
            raise IntegrationError("Meta bağlantı kimliği doğrulanamadı.")
        data["meta_user_id"], data["meta_app_id"] = subject, str(client_id)
    if not data.get("access_token"):
        raise IntegrationError("Erişim bilgisi alınamadı.")
    return data


def connection_token(connection):
    if connection.platform.code == "linkedin":
        from core.services.linkedin_ads import connection_token as linkedin_token
        return linkedin_token(connection)
    if connection.platform.code in GOOGLE_READ_PROVIDERS:
        from core.services.google_read_oauth import connection_token as google_token
        return google_token(connection)
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
    developer_token = application_values("google_ads")[3]
    headers = {"Authorization": f"Bearer {token}"}
    # Google sunset developer tokens on 2026-09-09. Existing migrated
    # projects may keep sending one for compatibility, while new projects
    # are authorized by their Google Cloud project and omit this header.
    if developer_token:
        headers["developer-token"] = developer_token
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
        data = _request("POST", url, operation="Google Ads kampanya verilerini okuma", headers=_google_headers(token, manager_id), json=body)
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
    from django.core.cache import cache
    from core.services.meta_sync_checkpoint import checkpoint_key, save_checkpoint
    key = checkpoint_key(token, path, params)
    saved = cache.get(key) if key else None
    rows, after = (saved["rows"], saved["after"]) if saved else ([], None)
    if saved and saved["complete"]:
        return rows
    while True:
        query = {**params, "limit": 100}
        if after:
            query["after"] = after
        data = _request("GET", f"{settings.FACEBOOK_GRAPH_URL}/{path}",
                        operation={"me/permissions": "Meta izinlerini kontrol etme", "me/adaccounts": "Meta reklam hesaplarını listeleme"}.get(path, "Meta verilerini okuma"),
                        headers={"Authorization": f"Bearer {token}"}, params=query)
        if not isinstance(data, dict) or not isinstance(data.get("data"), list):
            raise IntegrationError("Meta veri listesi eksiksiz okunamadı.")
        rows.extend(data["data"])
        paging = data.get("paging", {})
        if not paging.get("next"):
            save_checkpoint(key, rows, None, True)
            return rows
        cursor = paging.get("cursors", {}).get("after")
        if not cursor or cursor == after:
            raise IntegrationError("Meta sayfalama tamamlanamadı.")
        after = cursor
        save_checkpoint(key, rows, after, False)


def discover_accounts(provider, token):
    if provider == "linkedin":
        from core.services.linkedin_ads import discover_accounts as linkedin_accounts
        return linkedin_accounts(token)
    if provider in GOOGLE_READ_PROVIDERS:
        from core.services.google_read_oauth import discover_accounts as google_accounts
        return google_accounts(provider, token)
    if provider == "facebook":
        return [{"id": r["id"], "name": r.get("name", r["id"]),
                 "currency": r.get("currency", ""), "timezone": r.get("timezone_name", ""),
                 "kind": "ad_account"}
                for r in meta_rows(token, "me/adaccounts", {"fields": "id,name,currency,timezone_name,account_status"})
                if r.get("account_status") == 1]
    data = _request("GET", f"https://googleads.googleapis.com/{settings.GOOGLE_ADS_API_VERSION}/customers:listAccessibleCustomers",
                    headers=_google_headers(token))
    accounts = {}
    unavailable = False
    for resource in data.get("resourceNames", []):
        root = resource.split("/")[-1]
        try:
            info = google_search(token, root, "SELECT customer.id, customer.descriptive_name, customer.manager, customer.currency_code, customer.time_zone, customer.status, customer.test_account FROM customer")
        except IntegrationError as exc:
            if set(exc.google_codes) == {"authorizationError.CUSTOMER_NOT_ENABLED"}:
                unavailable = True
                continue
            raise
        if not info:
            continue
        customer = info[0]["customer"]
        if customer.get("status") and customer["status"] != "ENABLED" and not (customer.get("testAccount") is True and customer["status"] in {"CANCELED", "CLOSED"}):
            unavailable = True
            continue
        if not customer.get("manager"):
            name = customer.get("descriptiveName") or root
            accounts[root] = {"id": root, "name": f"{name} (Google Ads test)" if customer.get("testAccount") else name,
                              "test_account": customer.get("testAccount") is True,
                              "currency": customer.get("currencyCode", ""), "timezone": customer.get("timeZone", ""), "kind": "ad_account"}
            continue
        try:
            children = google_search(token, root, "SELECT customer_client.id, customer_client.descriptive_name, customer_client.manager, customer_client.currency_code, customer_client.time_zone, customer_client.status, customer_client.test_account FROM customer_client WHERE customer_client.manager = FALSE", root)
        except IntegrationError as exc:
            if set(exc.google_codes) == {"authorizationError.CUSTOMER_NOT_ENABLED"}:
                unavailable = True
                continue
            raise
        for row in children:
            c = row["customerClient"]
            if c.get("status") and c["status"] != "ENABLED" and not (c.get("testAccount") is True and c["status"] in {"CANCELED", "CLOSED"}):
                unavailable = True
                continue
            cid = str(c["id"])
            name = c.get("descriptiveName") or cid
            accounts.setdefault(cid, {"id": cid, "name": f"{name} (Google Ads test)" if c.get("testAccount") else name,
                                     "test_account": c.get("testAccount") is True,
                                     "currency": c.get("currencyCode", ""), "timezone": c.get("timeZone", ""),
                                     "login_customer_id": root, "kind": "ad_account"})
    if not accounts and unavailable:
        raise IntegrationError("Bu Google kullanıcısının erişebildiği reklam hesapları etkin değil. Yeni hesap açtıysanız Google Ads panelinde hesap kurulumunu tamamlayın ve hesap durumunu kontrol edin. Yönetici hesabı kullanıyorsanız altında etkin bir reklam hesabı bulunmalıdır. Google Ads'te etkin bir reklam hesabına erişimi olan Google kullanıcısıyla bağlanın. OAuth izin onayı reklam hesabını etkinleştirmez.")
    return list(accounts.values())


def account_token(account):
    if account.platform.code == "linkedin":
        if (not account.is_active or not account.connection_id
                or account.connection.user_id != account.user_id
                or account.connection.platform_id != account.platform_id):
            raise IntegrationError("LinkedIn hesabını yeniden bağlayın.")
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
    from core.services.ad_eligibility import is_current_campaign
    token = account_token(account)
    if account.platform.code == "linkedin":
        from core.services.linkedin_ads import campaigns as linkedin_campaigns
        return linkedin_campaigns(token, account.account_id)
    if account.platform.code == "google_ads":
        rows = google_search(token, account.account_id, "SELECT campaign.id, campaign.name, campaign.status, campaign.advertising_channel_type, campaign.start_date_time, campaign.end_date_time FROM campaign WHERE campaign.status = 'ENABLED'", account.extra_data.get("login_customer_id", ""))
        # v23+ exposes customer-local datetimes. Keep the reporting interface's
        # date-only values in the account's timezone, without converting to UTC.
        result = [{"id": str(r["campaign"]["id"]), "name": r["campaign"]["name"], "status": r["campaign"]["status"], "channel": r["campaign"].get("advertisingChannelType", ""), "start_date": (r["campaign"].get("startDateTime") or "")[:10] or None, "end_date": (r["campaign"].get("endDateTime") or "")[:10] or None} for r in rows]
        return [row for row in result if is_current_campaign(row, today=account_today(account))]
    from core.platforms.facebook import FacebookAPI
    return FacebookAPI(account).get_campaigns()


def campaign_summaries(account, start, end, campaign_ids=None):
    """One account-level request, rather than one Insights call per campaign."""
    token = account_token(account)
    if campaign_ids is None:
        campaign_ids = [str(row["id"]) for row in campaigns(account)]
    campaign_ids = list(dict.fromkeys(str(value) for value in campaign_ids))
    if any(not value.isdigit() for value in campaign_ids):
        raise IntegrationError("Geçersiz kampanya.")
    if not campaign_ids:
        return {}
    if account.platform.code == "linkedin":
        from core.services.linkedin_ads import campaign_summaries as linkedin_summaries
        return linkedin_summaries(token, account.account_id, start, end, campaign_ids=campaign_ids)
    if account.platform.code == "google_ads":
        query = f"SELECT campaign.id, metrics.impressions, metrics.clicks, metrics.cost_micros, metrics.conversions, metrics.conversions_value FROM campaign WHERE campaign.status = 'ENABLED' AND campaign.id IN ({','.join(campaign_ids)}) AND segments.date BETWEEN '{start.isoformat()}' AND '{end.isoformat()}'"
        return {str(row["campaign"]["id"]): google_metrics(row["metrics"])
                for row in google_search(token, account.account_id, query, account.extra_data.get("login_customer_id", ""))}
    return {str(row["campaign_id"]): {"impressions": int(row.get("impressions", 0)),
             "clicks": int(row.get("clicks", 0)), "spend": Decimal(row.get("spend", "0"))}
            for row in meta_rows(token, f"{account.account_id}/insights", {
                "level": "campaign", "fields": "campaign_id,impressions,clicks,spend",
                "time_range": json.dumps({"since": start.isoformat(), "until": end.isoformat()}),
                "filtering": json.dumps([{"field": "campaign.id", "operator": "IN", "value": campaign_ids}]),
            })}


def campaign_performance(account, campaign_id, start, end):
    if not str(campaign_id).isdigit():
        raise IntegrationError("Geçersiz kampanya.")
    token = account_token(account)
    if account.platform.code == "linkedin":
        from core.services.linkedin_ads import campaign_performance as linkedin_performance
        return linkedin_performance(token, account.account_id, campaign_id, start, end)
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

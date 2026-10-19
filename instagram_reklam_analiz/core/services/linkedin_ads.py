"""LinkedIn Advertising API: read-only OAuth, accounts and campaign reporting.

No member profile, audience, lead or campaign mutation endpoints are used.
Programmatic refresh is not assumed: expired tokens require authorization again.
"""
from datetime import date, datetime, timedelta, timezone as dt_timezone
from decimal import Decimal, InvalidOperation
import re
from urllib.parse import urlencode

import requests
from django.conf import settings
from django.utils import timezone

from core.services.ads_integrations import IntegrationError, configuration

SCOPES = ("r_ads", "r_ads_reporting")
API = "https://api.linkedin.com/rest/"


def _request(method, url, **kwargs):
    try:
        response = requests.request(method, url, timeout=30, allow_redirects=False, **kwargs)
        payload = response.json()
    except (requests.RequestException, ValueError):
        raise IntegrationError("LinkedIn'e ulaşılamadı. Lütfen tekrar deneyin.") from None
    if not response.ok or response.is_redirect or not isinstance(payload, dict) or payload.get("error"):
        # Never echo provider messages, codes, tokens or request URLs.
        if response.status_code == 403:
            raise IntegrationError("LinkedIn Advertising API iznini ve reklam hesabındaki erişim rolünüzü kontrol edin.")
        if response.status_code == 401:
            raise IntegrationError("LinkedIn erişimi geçersiz. Hesabı yeniden bağlayın.")
        if response.status_code == 429:
            raise IntegrationError("LinkedIn istek sınırına ulaşıldı. Daha sonra tekrar deneyin.")
        raise IntegrationError("LinkedIn isteği tamamlanamadı. Uygulama ayarlarını kontrol edin.")
    return payload


def authorization_url(state):
    client, _, uri = configuration("linkedin")
    return "https://www.linkedin.com/oauth/v2/authorization?" + urlencode({
        "client_id": client, "redirect_uri": uri, "response_type": "code",
        "state": state, "scope": " ".join(SCOPES),
    })


def exchange_code(code):
    client, secret, uri = configuration("linkedin")
    data = _request("POST", "https://www.linkedin.com/oauth/v2/accessToken", data={
        "grant_type": "authorization_code", "client_id": client, "client_secret": secret,
        "redirect_uri": uri, "code": code,
    })
    try:
        expires = int(data.get("expires_in", 0))
    except (TypeError, ValueError, OverflowError):
        expires = 0
    scope = data.get("scope", "")
    if (not isinstance(data.get("access_token"), str) or not data["access_token"]
            or not 0 < expires <= 31536000 or not isinstance(scope, str)
            or not set(SCOPES).issubset(scope.replace(",", " ").split())):
        raise IntegrationError("LinkedIn reklam okuma ve raporlama izinleri alınamadı. Yeniden bağlanın.")
    return {"access_token": data["access_token"], "expires_in": expires,
            "scope": " ".join(scope.replace(",", " ").split()), "linkedin_client_id": client}


def connection_token(connection):
    client, _, _ = configuration("linkedin")
    extra = connection.extra_data or {}
    if (not connection.is_active or connection.status != "active"
            or extra.get("source") != "ads_oauth" or extra.get("pending")
            or extra.get("linkedin_client_id") != client
            or not set(SCOPES).issubset(connection.scopes or [])
            or not connection.access_token or not connection.token_expiry
            or connection.token_expiry <= timezone.now() + timedelta(seconds=60)):
        raise IntegrationError("LinkedIn erişimi süresi dolmuş veya ayarları değişmiş. Hesabı yeniden bağlayın.")
    return connection.access_token


def _id(value, kind=None):
    value = str(value)
    if kind:
        prefix = f"urn:li:{kind}:"
        if not value.startswith(prefix):
            raise IntegrationError("LinkedIn hesap veya kampanya kimliği doğrulanamadı.")
        value = value[len(prefix):]
    if not re.fullmatch(r"[0-9]{1,30}", value):
        raise IntegrationError("LinkedIn hesap veya kampanya kimliği doğrulanamadı.")
    return value


def read(token, path, params=None):
    # Callers construct paths only from fixed endpoint names and numeric IDs.
    version = getattr(settings, "LINKEDIN_ADS_API_VERSION", "202610")
    if not re.fullmatch(r"20[0-9]{2}(0[1-9]|1[0-2])", version):
        raise IntegrationError("LinkedIn API sürüm ayarını kontrol edin.")
    return _request("GET", API + path, params=params or {}, headers={
        "Authorization": f"Bearer {token}", "LinkedIn-Version": version,
        "X-Restli-Protocol-Version": "2.0.0",
    })


def rows(token, path, params, *, cursor=False):
    result, seen, offset, page_token = [], set(), 0, None
    for _ in range(200):
        page = {**params, **({"pageSize": 100} if cursor else {"start": offset, "count": 100})}
        if page_token:
            page["pageToken"] = page_token
        data = read(token, path, page)
        elements = data.get("elements")
        if not isinstance(elements, list) or any(not isinstance(r, dict) for r in elements):
            raise IntegrationError("LinkedIn liste yanıtı doğrulanamadı.")
        result.extend(elements)
        if cursor:
            metadata = data.get("metadata") or {}
            if not isinstance(metadata, dict):
                raise IntegrationError("LinkedIn sayfalaması doğrulanamadı.")
            next_token = metadata.get("nextPageToken")
            if not next_token:
                return result
            if not isinstance(next_token, str) or next_token in seen:
                raise IntegrationError("LinkedIn sayfalaması tamamlanamadı.")
            seen.add(next_token)
            page_token = next_token
        else:
            paging = data.get("paging") or {}
            if not isinstance(paging, dict):
                raise IntegrationError("LinkedIn sayfalaması doğrulanamadı.")
            links = paging.get("links") or []
            has_next = any(isinstance(link, dict) and link.get("rel") == "next" for link in links)
            total = paging.get("total")
            offset += len(elements)
            if not has_next and ((isinstance(total, int) and offset >= total)
                                 or (total is None and len(elements) < 100)):
                return result
            fingerprint = repr(elements)
            if not elements or fingerprint in seen:
                raise IntegrationError("LinkedIn sayfalaması tamamlanamadı.")
            seen.add(fingerprint)
    raise IntegrationError("LinkedIn liste boyutu sınırı aşıldı. Destek ile iletişime geçin.")


def discover_accounts(token):
    memberships = rows(token, "adAccountUsers", {"q": "authenticatedUser"})
    accounts = {}
    for membership in memberships:
        cid = _id(membership.get("account", ""), "sponsoredAccount")
        if cid in accounts:
            continue
        info = read(token, f"adAccounts/{cid}")
        if _id(info.get("id", "")) != cid:
            raise IntegrationError("LinkedIn reklam hesabı doğrulanamadı.")
        if info.get("status") != "ACTIVE":
            continue
        accounts[cid] = {"id": cid, "name": info.get("name") or cid,
                         "currency": info.get("currency", ""), "timezone": "UTC",
                         "kind": "ad_account", "test_account": info.get("test") is True}
    return list(accounts.values())


def campaigns(token, account_id):
    cid = _id(account_id)
    statuses = "ACTIVE,PAUSED,ARCHIVED,COMPLETED,CANCELED,DRAFT,PENDING_DELETION,REMOVED"
    data = rows(token, f"adAccounts/{cid}/adCampaigns", {
        "q": "search", "search": f"(status:(values:List({statuses})))",
    }, cursor=True)
    result = []
    for row in data:
        if row.get("account") != f"urn:li:sponsoredAccount:{cid}":
            raise IntegrationError("LinkedIn kampanyasının hesabı doğrulanamadı.")
        schedule = row.get("runSchedule") or {}
        if not isinstance(schedule, dict):
            raise IntegrationError("LinkedIn kampanya tarihi doğrulanamadı.")
        def timestamp(key):
            value = schedule.get(key)
            if value is None:
                return None
            try:
                return datetime.fromtimestamp(int(value) / 1000, dt_timezone.utc).isoformat()
            except (ValueError, TypeError, OverflowError, OSError):
                raise IntegrationError("LinkedIn kampanya tarihi doğrulanamadı.") from None
        result.append({"id": _id(row.get("id", "")), "name": row.get("name") or str(row["id"]),
                       "status": row.get("status", "UNKNOWN"), "objective": row.get("objectiveType", ""),
                       "start_time": timestamp("start"), "stop_time": timestamp("end")})
    return result


def _metrics(row):
    try:
        spend = Decimal(str(row.get("costInLocalCurrency", "0")))
        impressions, clicks = int(row.get("impressions", 0)), int(row.get("clicks", 0))
        if not spend.is_finite() or min(spend, impressions, clicks) < 0:
            raise ValueError
        return {"impressions": impressions, "clicks": clicks, "spend": spend}
    except (TypeError, ValueError, InvalidOperation, OverflowError):
        raise IntegrationError("LinkedIn rapor metrikleri doğrulanamadı.") from None


def analytics(token, account_id, start, end, *, campaign_id=None):
    cid = _id(account_id)
    if start > end or (end - start).days > 365:
        raise IntegrationError("LinkedIn rapor tarihlerini kontrol edin.")
    params = {"q": "analytics", "pivot": "CAMPAIGN",
              "accounts": f"List(urn:li:sponsoredAccount:{cid})",
              "timeGranularity": "DAILY" if campaign_id else "ALL",
              "fields": "pivotValues,dateRange,impressions,clicks,costInLocalCurrency"}
    if campaign_id:
        params["campaigns"] = f"List(urn:li:sponsoredCampaign:{_id(campaign_id)})"
    # At most 31 daily rows per campaign call; ALL returns at most 5,000
    # campaigns per account. Never silently accept the 15,000-row API cap.
    result, current = [], start
    while current <= end:
        until = min(current + timedelta(days=30), end) if campaign_id else end
        def part(d):
            return f"(year:{d.year},month:{d.month},day:{d.day})"
        data = read(token, "adAnalytics", {**params, "dateRange": f"(start:{part(current)},end:{part(until)})"})
        elements = data.get("elements")
        if not isinstance(elements, list) or len(elements) >= 15000 or any(not isinstance(r, dict) for r in elements):
            raise IntegrationError("LinkedIn raporu eksiksiz okunamadı.")
        for row in elements:
            # LinkedIn may round older ALL requests to whole months. Never
            # display the resulting spend as if it matched the selected dates.
            if "dateRange" in row:
                try:
                    actual_start = date(**row["dateRange"]["start"])
                    actual_end = date(**row["dateRange"].get("end", row["dateRange"]["start"]))
                except (KeyError, TypeError, ValueError, AttributeError):
                    raise IntegrationError("LinkedIn rapor tarihi doğrulanamadı.") from None
                if not current <= actual_start <= actual_end <= until:
                    raise IntegrationError("LinkedIn bu dönem için tarihleri yuvarladı. Daha yakın bir rapor dönemi seçin.")
        result.extend(elements)
        current = until + timedelta(days=1)
    return result


def campaign_summaries(token, account_id, start, end):
    result = {}
    for row in analytics(token, account_id, start, end):
        pivots = row.get("pivotValues")
        if not isinstance(pivots, list) or len(pivots) != 1:
            raise IntegrationError("LinkedIn kampanya raporu doğrulanamadı.")
        cid = _id(pivots[0], "sponsoredCampaign")
        if cid in result:
            raise IntegrationError("LinkedIn raporunda yinelenen kampanya var.")
        result[cid] = _metrics(row)
    return result


def campaign_performance(token, account_id, campaign_id, start, end):
    campaign_id = _id(campaign_id)
    # Check campaign ownership before requesting analytics for its URN.
    row = read(token, f"adAccounts/{_id(account_id)}/adCampaigns/{campaign_id}")
    if (row.get("account") != f"urn:li:sponsoredAccount:{account_id}"
            or _id(row.get("id", "")) != campaign_id):
        raise IntegrationError("LinkedIn kampanyasının hesabı doğrulanamadı.")
    result, seen = [], set()
    for row in analytics(token, account_id, start, end, campaign_id=campaign_id):
        if row.get("pivotValues") != [f"urn:li:sponsoredCampaign:{campaign_id}"]:
            raise IntegrationError("LinkedIn rapor kampanyası doğrulanamadı.")
        try:
            day = date(**row["dateRange"]["start"])
        except (KeyError, TypeError, ValueError):
            raise IntegrationError("LinkedIn rapor tarihi doğrulanamadı.") from None
        if not start <= day <= end or day in seen:
            raise IntegrationError("LinkedIn rapor tarih aralığı doğrulanamadı.")
        seen.add(day)
        result.append({"date": day.isoformat(), **_metrics(row)})
    return sorted(result, key=lambda row: row["date"])

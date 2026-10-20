"""TikTok Marketing API v1.3, advertiser OAuth and read-only reports.

This is deliberately separate from Login Kit/Display API credentials.
"""
from datetime import date, timedelta
from decimal import Decimal, InvalidOperation
import json
from urllib.parse import urlencode

import requests

from core.services.ads_integrations import IntegrationError, configuration

API = "https://business-api.tiktok.com/open_api/v1.3/"


def request(method, path, token=None, **kwargs):
    try:
        response = requests.request(method, API + path.strip("/") + "/",
            headers={"Access-Token": token} if token else {}, timeout=30,
            allow_redirects=False, **kwargs)
        payload = response.json()
    except (requests.RequestException, ValueError):
        raise IntegrationError("TikTok Ads isteği tamamlanamadı. Yeniden deneyin.") from None
    if (not response.ok or not isinstance(payload, dict) or type(payload.get("code")) is not int or payload.get("code") != 0
            or not isinstance(payload.get("data"), dict)):
        # Provider error text / request URLs can contain credentials.
        raise IntegrationError("TikTok Ads verisi okunamadı. Uygulama onayını ve reklam hesabı izinlerini kontrol edin.")
    return payload["data"]


def authorization_url(state):
    app_id, _, uri = configuration("tiktok_ads")
    return "https://business-api.tiktok.com/portal/auth?" + urlencode({
        "app_id": app_id, "redirect_uri": uri, "state": state,
    })


def exchange_code(code):
    app_id, secret, _ = configuration("tiktok_ads")
    data = request("POST", "oauth2/access_token", json={
        "app_id": app_id, "secret": secret, "auth_code": code,
    })
    token = data.get("access_token")
    ids = data.get("advertiser_ids")
    if (not isinstance(token, str) or not token or not isinstance(ids, list)
            or any(not str(value).isdigit() for value in ids)):
        raise IntegrationError("TikTok reklam hesabı yetkisi doğrulanamadı.")
    return {"access_token": token, "expires_in": None, "scope": "",
            "tiktok_ads_app_id": app_id}


def discover_accounts(token):
    app_id, secret, _ = configuration("tiktok_ads")
    data = request("GET", "oauth2/advertiser/get", token, params={"app_id": app_id, "secret": secret})
    rows = data.get("list")
    if not isinstance(rows, list):
        raise IntegrationError("TikTok reklam hesabı listesi okunamadı.")
    result = []
    for row in rows:
        if not isinstance(row, dict) or not str(row.get("advertiser_id", "")).isdigit():
            raise IntegrationError("TikTok reklam hesabı kimliği doğrulanamadı.")
        info = advertiser_info(token, str(row["advertiser_id"]))
        result.append({"id": str(row["advertiser_id"]), "name": row.get("advertiser_name") or str(row["advertiser_id"]),
                       "kind": "ad_account", **info})
    return result


def advertiser_info(token, account_id):
    data = request("GET", "advertiser/info", token, params={
        "advertiser_ids": json.dumps([str(account_id)]),
        "fields": json.dumps(["advertiser_id", "currency", "timezone"]),
    })
    items = data.get("list")
    if (not isinstance(items, list) or len(items) != 1 or not isinstance(items[0], dict)
            or str(items[0].get("advertiser_id")) != str(account_id)
            or not isinstance(items[0].get("currency"), str) or len(items[0]["currency"]) != 3
            or not items[0].get("timezone")):
        raise IntegrationError("TikTok reklam hesabının para birimi ve saat dilimi doğrulanamadı.")
    return {"currency": items[0]["currency"], "timezone": items[0]["timezone"]}


def account_token(account):
    app_id, _, _ = configuration("tiktok_ads")
    connection = account.connection
    if (not account.is_active or not connection or not connection.is_active
            or connection.status != "active" or connection.user_id != account.user_id
            or connection.platform_id != account.platform_id or connection.is_token_expired
            or (connection.extra_data or {}).get("source") != "tiktok_ads_oauth"
            or (connection.extra_data or {}).get("tiktok_ads_app_id") != app_id
            or not connection.access_token or not str(account.account_id).isdigit()):
        raise IntegrationError("TikTok Ads hesabını ayrı reklam bağlantısından yeniden bağlayın.")
    return connection.access_token


def rows(token, path, params, *, limit=10000):
    result = []
    for page in range(1, 101):
        data = request("GET", path, token, params={**params, "page": page, "page_size": 100})
        items, info = data.get("list"), data.get("page_info")
        if not isinstance(items, list) or any(not isinstance(item, dict) for item in items) or not isinstance(info, dict):
            raise IntegrationError("TikTok Ads sayfalaması doğrulanamadı.")
        total = info.get("total_page")
        if not isinstance(total, int) or isinstance(total, bool) or total < 0 or total > 100:
            raise IntegrationError("TikTok Ads sayfa sınırı aşıldı.")
        result.extend(items)
        if len(result) > limit:
            raise IntegrationError("TikTok Ads kayıtları plan sınırını aşıyor.")
        if page >= total:
            return result
        if not items:
            raise IntegrationError("TikTok Ads sayfalaması tamamlanamadı.")
    raise IntegrationError("TikTok Ads sayfa sınırı aşıldı.")


def inventory(token, account_id, *, limit=10000):
    params = {"advertiser_id": str(account_id), "filtering": json.dumps({"primary_status": "STATUS_ALL"})}
    campaigns = rows(token, "campaign/get", params, limit=limit)
    result = {}
    for row in campaigns:
        cid = str(row.get("campaign_id") or "")
        if not cid.isdigit() or cid in result or not row.get("campaign_name"):
            raise IntegrationError("TikTok kampanya bilgileri doğrulanamadı.")
        status = {"ENABLE": "ACTIVE", "DISABLE": "PAUSED", "DELETE": "DELETED"}.get(row.get("operation_status"), "UNKNOWN")
        result[cid] = {"id": cid, "name": row["campaign_name"], "status": status,
                       "objective": row.get("objective_type") or "UNKNOWN", "raw": row}
    return result


def report(token, account_id, start, end, *, level="campaign", limit=10000):
    if level not in {"campaign", "ad"}:
        raise IntegrationError("Geçersiz TikTok rapor düzeyi.")
    if (end - start).days >= 30:
        result = []
        chunk_start = start
        while chunk_start <= end:
            chunk_end = min(end, chunk_start + timedelta(days=29))
            result.extend(report(token, account_id, chunk_start, chunk_end, level=level, limit=limit))
            if len(result) > limit:
                raise IntegrationError("TikTok Ads kayıtları plan sınırını aşıyor.")
            chunk_start = chunk_end + timedelta(days=1)
        return result
    identity = f"{level}_id"
    params = {"advertiser_id": str(account_id), "report_type": "BASIC", "service_type": "AUCTION",
              "data_level": f"AUCTION_{level.upper()}", "dimensions": json.dumps([identity, "stat_time_day"]),
              "metrics": json.dumps(["impressions", "clicks", "spend"]),
              "start_date": start.isoformat(), "end_date": end.isoformat()}
    result, seen = [], set()
    for row in rows(token, "report/integrated/get", params, limit=limit):
        dimensions, metrics = row.get("dimensions"), row.get("metrics")
        if not isinstance(dimensions, dict) or not isinstance(metrics, dict):
            raise IntegrationError("TikTok rapor metrikleri eksik.")
        identifier = str(dimensions.get(identity) or "")
        try:
            day = date.fromisoformat(str(dimensions.get("stat_time_day", ""))[:10])
            values = {key: Decimal(str(metrics[key])) for key in ("impressions", "clicks", "spend")}
        except (KeyError, ValueError, TypeError, InvalidOperation):
            raise IntegrationError("TikTok rapor metrikleri doğrulanamadı.") from None
        if (not identifier.isdigit() or not start <= day <= end or (identifier, day) in seen
                or any(not value.is_finite() or value < 0 for value in values.values())
                or values["spend"] >= Decimal("1000000000000")
                or any(values[key] != values[key].to_integral_value() or values[key] >= 2**63 for key in ("impressions", "clicks"))):
            raise IntegrationError("TikTok rapor satırı doğrulanamadı.")
        seen.add((identifier, day))
        result.append({identity: identifier, "date": day.isoformat(), "metrics_available": True,
                       "impressions": int(values["impressions"]), "clicks": int(values["clicks"]),
                       "spend": values["spend"]})
    return result

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Any

import requests
import json
import re
import unicodedata
from urllib.parse import urlsplit, parse_qs, urlencode
from django.conf import settings
from django.db import transaction
from django.utils import timezone
import logging

from core.models import Ad, AdMetricHistory, Competitor, Creative
from core.services.competitor_metrics import range_midpoint


SUPPORTED_META_PLATFORMS = {"instagram", "facebook"}


class CompetitorSyncError(Exception):
    pass


class CompetitorAdvertiserChoiceRequired(CompetitorSyncError):
    def __init__(self, candidates):
        super().__init__('Bu alan adı için birden fazla reklamveren bulundu. Takip etmek istediğiniz firmayı seçin.')
        self.candidates = candidates


def _first(value, default=""):
    if isinstance(value, list):
        return value[0] if value else default
    return value if value not in (None, "") else default


def _parse_dt(value):
    if not value:
        return None
    try:
        if len(value) == 10:
            return timezone.make_aware(datetime.fromisoformat(value))
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        return timezone.make_aware(parsed) if timezone.is_naive(parsed) else parsed
    except Exception:
        return None


def _q2(value):
    return Decimal(value or 0).quantize(Decimal("0.01"))


def _token_for_competitor(competitor):
    from core.models import CompetitorSourceSetting
    config = CompetitorSourceSetting.runtime(getattr(getattr(competitor, 'platform', None), 'code', 'facebook'))
    if not config['enabled']:
        return ''
    # Instagram Login tokens cannot authenticate the Facebook ads_archive API.
    dedicated = config['credential'] if config['source'] == 'graph' else ''
    if dedicated:
        return dedicated
    account = competitor.platform_account
    connection = getattr(account, "connection", None) if account else None
    token = ""
    account_meta = getattr(account, "extra_data", {}) or {}
    connection_meta = getattr(connection, "extra_data", {}) or {}
    if account_meta.get("auth_type") == "instagram_login" or connection_meta.get("auth_type") == "instagram_login":
        return ""
    if connection and getattr(connection, "access_token", "") and connection.status == "active" and not connection.is_token_expired:
        token = connection.access_token
    if not token and not connection and account and getattr(account, "access_token", ""):
        token = account.access_token
    if token and str(token).startswith("IG"):
        return ""
    return token


def _ad_reached_countries_param(competitor=None):
    from core.models import CompetitorSourceSetting
    countries = (CompetitorSourceSetting.runtime(competitor.platform.code)['countries'] if competitor
                 else getattr(settings, "META_AD_LIBRARY_COUNTRIES", ["TR"])) or ["TR"]
    countries = [str(country).strip().upper() for country in countries if str(country).strip()]
    return json.dumps(countries)


def _normalize_page_ids(value):
    if not value:
        return []
    values = value if isinstance(value, list) else str(value).split(",")
    page_ids = []
    for item in values:
        page_id = str(item).strip()
        if page_id.isdigit():
            page_ids.append(page_id)
    return page_ids


def parse_meta_page_reference(value):
    value = str(value or "").strip()
    if not value:
        return ""
    if value.isascii() and value.isdigit():
        return value
    parsed = urlsplit(value)
    if parsed.scheme in {"https", "http"} and parsed.hostname in {"facebook.com", "www.facebook.com", "m.facebook.com", "business.facebook.com"}:
        query = parse_qs(parsed.query)
        candidate = (query.get("view_all_page_id") or query.get("id") or [parsed.path.strip("/")])[0]
        if str(candidate).isascii() and str(candidate).isdigit():
            return str(candidate)
    raise ValueError("Facebook sayfa ID'sini veya sayfaya ait Meta Reklam Kütüphanesi bağlantısını girin.")


def competitor_library_url(competitor):
    if competitor.platform.code not in SUPPORTED_META_PLATFORMS:
        from core.services.competitor_public_sources import public_library_url
        return public_library_url(competitor)
    ids = _page_ids_for_competitor(competitor)
    params = {"active_status": "all", "ad_type": "all", "country": "TR"}
    params.update({"view_all_page_id": ids[0], "search_type": "page"} if ids else
                  {"q": _search_term(competitor), "search_type": "keyword_unordered"})
    return "https://www.facebook.com/ads/library/?" + urlencode(params)


def _page_ids_for_competitor(competitor):
    raw_data = competitor.raw_data or {}
    # An explicit page reference overrides legacy aliases and numeric profile IDs.
    explicit = _normalize_page_ids(raw_data.get("facebook_page_id"))
    if explicit:
        return explicit
    page_ids = []
    page_ids.extend(_normalize_page_ids(raw_data.get("facebook_page_ids")))
    page_ids.extend(_normalize_page_ids(raw_data.get("facebook_page_id")))
    page_ids.extend(_normalize_page_ids(raw_data.get("page_ids")))
    page_ids.extend(_normalize_page_ids(raw_data.get("page_id")))
    # ads_archive accepts Facebook advertiser Page IDs, not Instagram User IDs.
    if getattr(competitor.platform, "code", "") == "facebook":
        page_ids.extend(_normalize_page_ids(competitor.platform_identifier))
    return list(dict.fromkeys(page_ids))


def _search_term(competitor):
    raw = (competitor.platform_identifier or competitor.name or "").strip()
    if raw.isdigit() and getattr(competitor.platform, "code", "") == "instagram":
        return competitor.name or ""
    return raw.lstrip("@").replace("_", " ") or competitor.name


def _normalized_name(value):
    value = unicodedata.normalize("NFKD", str(value or "").casefold())
    return re.sub(r"[^a-z0-9]", "", value)


class MetaAdLibraryCompetitorSync:
    def __init__(self, competitor: Competitor):
        self.competitor = competitor
        self.platform_code = getattr(competitor.platform, "code", "") if competitor.platform else ""
        self.token = _token_for_competitor(competitor)
        self.graph_url = getattr(settings, "FACEBOOK_GRAPH_URL", "https://graph.facebook.com/v25.0").rstrip("/")

    def sync(self, limit=None):
        if not self.competitor.is_active:
            raise CompetitorSyncError("Rakip aktif izlenmiyor. Reklam çekmek için önce takibi etkinleştirin.")
        if self.platform_code not in SUPPORTED_META_PLATFORMS:
            raise CompetitorSyncError(
                f"{self.platform_code or 'unknown'} için canlı rakip reklam çekimi desteklenmiyor. "
                "Canlı kaynak olarak şu an Meta Ad Library üzerinden Instagram/Facebook desteklenir."
            )
        if not self.token or self.token.startswith("demo") or self.token.startswith("placeholder"):
            raise CompetitorSyncError(
                "Meta Ad Library token bulunamadı. .env içine META_AD_LIBRARY_ACCESS_TOKEN veya geçerli Meta bağlantı tokenı eklenmeli."
            )

        if (self.platform_code == "instagram" and self.competitor.platform_identifier.isdigit()
                and not _page_ids_for_competitor(self.competitor)):
            raise CompetitorSyncError(
                "Instagram hesap ID'si Facebook reklamveren sayfa ID'si değildir. "
                "Bu Instagram hesabına ait reklamverenin Facebook sayfa ID'si veya Reklam Kütüphanesi bağlantısı eşleştirilmelidir."
            )

        payload = self._fetch(limit=limit)
        rows = payload.get("data") or []
        page_ids = _page_ids_for_competitor(self.competitor)
        if page_ids:
            rows = [row for row in rows if str(row.get("page_id")) in page_ids]
        elif rows:
            names = {_normalized_name(self.competitor.name), _normalized_name(_search_term(self.competitor))} - {""}
            matching_ids = {str(row.get("page_id")) for row in rows
                            if row.get("page_id") and _normalized_name(row.get("page_name")) in names}
            if len(matching_ids) != 1:
                raise CompetitorSyncError(
                    "Hesap reklamverenle otomatik eşleştirilemedi. Reklam kaynağını sistem yöneticisi kontrol etmeli; "
                    "anahtar kelime sonuçları başka firmalara ait olabilir."
                )
            rows = [row for row in rows if str(row.get("page_id")) in matching_ids]
            self.competitor.raw_data = {**(self.competitor.raw_data or {}), "facebook_page_id": next(iter(matching_ids))}
        created = 0
        updated = 0
        ads = []
        for row in rows:
            ad, was_created = self._upsert_ad(row)
            ads.append(ad)
            if was_created:
                created += 1
            else:
                updated += 1

        self.competitor.total_ads_seen = Ad.objects.filter(
            user=self.competitor.user,
            source_type="COMPETITOR",
            competitor=self.competitor,
        ).count()
        if rows:
            self.competitor.last_seen_at = timezone.now()
        raw_data = self.competitor.raw_data or {}
        identity = {"status": "matched" if rows else "unverified", "message": ""}
        if not rows and page_ids:
            identity = self._check_page_identity(page_ids[0])
        raw_data.update({
            "last_live_sync_result": "ads_fetched" if rows else "no_data",
            "identity_status": identity["status"],
            "identity_check_message": identity["message"],
            "last_live_sync_warning": "" if rows else (
                "Meta API bu sorgu için reklam döndürmedi. Bu sonuç hesabın olmadığı veya reklam yayınlamadığı anlamına gelmez. "
                "Reklam Kütüphanesi'nden kontrol edin; API kapsamı web sitesinden farklı olabilir."
                " Türkiye'deki ticari reklamların tamamı resmi API kapsamında değildir."
            ),
            "last_live_sync_at": timezone.now().isoformat(),
            "last_live_sync_source": "meta_ad_library",
            "last_live_sync_count": len(rows),
            "search_term": _search_term(self.competitor),
            "search_page_ids": _page_ids_for_competitor(self.competitor),
        })
        self.competitor.raw_data = raw_data
        self.competitor.save(update_fields=["total_ads_seen", "last_seen_at", "raw_data", "updated_at"])

        return {
            "success": True,
            "provider": "meta_ad_library",
            "created": created,
            "updated": updated,
            "total": self.competitor.total_ads_seen,
            "fetched": len(rows),
            "warning": raw_data.get("last_live_sync_warning", ""),
            "result_status": raw_data["last_live_sync_result"],
            "library_url": competitor_library_url(self.competitor),
            "ads": [ad.id for ad in ads],
        }

    def _check_page_identity(self, page_id):
        try:
            response = requests.get(f"{self.graph_url}/{page_id}",
                params={"access_token": self.token, "fields": "id,name"}, timeout=15)
            data = response.json()
        except (requests.RequestException, ValueError):
            return {"status": "unverified", "message": "Reklamveren kimlik kontrolüne ulaşılamadı."}
        if response.ok and str(data.get("id")) == page_id and data.get("name"):
            return {"status": "matched", "message": str(data["name"])}
        return {"status": "unverified", "message":
            "Meta sayfa kimliğini doğrulamadı. Sayfa erişimi veya Page Public Metadata Access izni gerekebilir; "
            "bu yanıt hesabın bulunmadığı anlamına gelmez."}

    def _fetch(self, limit=None):
        page_ids = _page_ids_for_competitor(self.competitor)
        params = {
            "access_token": self.token,
            "ad_reached_countries": _ad_reached_countries_param(self.competitor),
            "search_type": getattr(settings, "META_AD_LIBRARY_SEARCH_TYPE", "KEYWORD_UNORDERED"),
            "ad_active_status": getattr(settings, "META_AD_LIBRARY_ACTIVE_STATUS", "ALL"),
            "ad_type": getattr(settings, "META_AD_LIBRARY_AD_TYPE", "ALL"),
            "limit": int(limit or getattr(settings, "META_AD_LIBRARY_LIMIT", 50) or 50),
            "fields": ",".join([
                "id",
                "ad_creation_time",
                "ad_creative_bodies",
                "ad_creative_link_captions",
                "ad_creative_link_descriptions",
                "ad_creative_link_titles",
                "ad_delivery_start_time",
                "ad_delivery_stop_time",
                "ad_snapshot_url",
                "currency",
                "demographic_distribution",
                "impressions",
                "page_id",
                "page_name",
                "publisher_platforms",
                "spend",
            ]),
        }
        if page_ids:
            params["search_page_ids"] = json.dumps(page_ids)
            params.pop("search_type", None)
        else:
            params["search_terms"] = _search_term(self.competitor)
        total_limit = max(1, params["limit"])
        params["limit"] = min(total_limit, 100)
        rows = []
        cursors = set()
        while len(rows) < total_limit:
            data = self._request(dict(params))
            rows.extend((data.get("data") or [])[:total_limit - len(rows)])
            paging = data.get("paging") or {}
            cursor = (paging.get("cursors") or {}).get("after")
            if not paging.get("next") or not cursor or cursor in cursors:
                break
            cursors.add(cursor)
            params["after"] = cursor
            params["limit"] = min(100, total_limit - len(rows))
        return {"data": rows}

    def _request(self, params):
        try:
            response = requests.get(f"{self.graph_url}/ads_archive", params=params, timeout=30)
        except requests.RequestException as exc:
            raise CompetitorSyncError(
                "Meta Ad Library baglantisi kurulamadi. Ag erisimi, firewall veya Meta Graph API erisimi kontrol edilmeli."
            ) from exc
        try:
            data = response.json()
        except ValueError:
            data = {"error": {"message": response.text[:300]}}
        if not isinstance(data, dict) or ("data" in data and not isinstance(data["data"], list)):
            raise CompetitorSyncError("Meta Ad Library geçersiz veri döndürdü.")
        if response.status_code >= 400 or data.get("error"):
            error = data.get("error", {})
            message = error.get("message") if isinstance(error, dict) else error
            code = error.get("code") if isinstance(error, dict) else None
            if code == 10 and message == "Application does not have permission for this action":
                message = (
                    "Meta uygulamasinda Ad Library API/ads_archive erisimi yok. "
                    "Meta App Review uzerinden Ad Library API erisimi onaylanmadan rakip reklamlari canli cekilemez."
                )
            message = str(message or response.status_code).replace(self.token, "[REDACTED]")
            raise CompetitorSyncError(f"Meta Ad Library hata verdi: {message}")
        return data

    def _upsert_ad(self, row: dict[str, Any]):
        now = timezone.now()
        platform_ad_id = str(row.get("id") or "")
        if not platform_ad_id:
            raise CompetitorSyncError("Meta reklam kaydında reklam ID'si eksik; veri kaydedilmedi.")
        title = _first(row.get("ad_creative_link_titles"), self.competitor.name or "Rakip Reklam")
        body = _first(row.get("ad_creative_bodies"), "")
        description = _first(row.get("ad_creative_link_descriptions"), "")
        caption = _first(row.get("ad_creative_link_captions"), "")
        snapshot_url = row.get("ad_snapshot_url") or ""
        start_time = _parse_dt(row.get("ad_delivery_start_time") or row.get("ad_creation_time"))
        stop_time = _parse_dt(row.get("ad_delivery_stop_time"))
        is_active = stop_time is None or stop_time >= now
        creative_type = "UNKNOWN"
        platforms = row.get("publisher_platforms") or []

        creative, _ = Creative.objects.update_or_create(
            user=self.competitor.user,
            platform_connection=getattr(self.competitor.platform_account, "connection", None),
            platform_account=self.competitor.platform_account,
            platform_creative_id=f"meta-library-{platform_ad_id}",
            defaults={
                "creative_type": creative_type,
                "name": title or f"Rakip Kreatif {platform_ad_id}",
                "title": title,
                "body_text": body,
                "description": description,
                "landing_url": "",
                "raw_data": row,
                "first_seen_at": start_time or now,
                "last_seen_at": now,
            },
        )

        ad, created = Ad.objects.update_or_create(
            user=self.competitor.user,
            source_type="COMPETITOR",
            platform_ad_id=platform_ad_id,
            competitor=self.competitor,
            defaults={
                "platform_connection": getattr(self.competitor.platform_account, "connection", None),
                "platform_account": self.competitor.platform_account,
                "creative": creative,
                "ad_library_id": platform_ad_id,
                "name": title or f"{self.competitor.name} Reklam",
                "status": "ACTIVE" if is_active else "ENDED",
                "ad_format": creative_type,
                "objective": "UNKNOWN",
                "headline": title,
                "primary_text": body,
                "description": description or caption,
                "landing_url": "",
                "preview_image_url": "",
                "first_seen_at": start_time,
                "last_seen_at": now,
                "ended_at": stop_time,
                "raw_data": {
                    "provider": "meta_ad_library",
                    "snapshot_url": snapshot_url,
                    "publisher_platforms": platforms,
                    "currency": row.get("currency") or "TRY",
                    "raw": row,
                },
                "last_synced_at": now,
                "is_active": self.competitor.is_active,
            },
        )
        self._upsert_metric(ad, row)
        return ad, created

    def _upsert_metric(self, ad, row):
        metric_date = timezone.localdate()
        impressions = int(range_midpoint(row.get("impressions")) or 0)
        spend = range_midpoint(row.get("spend")) or Decimal("0")
        AdMetricHistory.objects.update_or_create(
            ad=ad,
            date=metric_date,
            defaults={
                "impressions": impressions,
                "reach": 0,
                "frequency": Decimal("0"),
                "clicks": 0,
                "spend": _q2(spend),
                "currency": row.get("currency") or "TRY",
                "ctr": Decimal("0"),
                "cpc": Decimal("0"),
                "cpm": Decimal("0"),
                "engagement": 0,
                "engagement_rate": Decimal("0"),
                "estimated_engagement": 0,
                "estimated_reach_min": 0,
                "estimated_reach_max": 0,
                "is_competitor_snapshot": True,
                "raw_metrics": {
                    "provider": "meta_ad_library",
                    "measurement_type": "cumulative_range_snapshot",
                    "available_metrics": [key for key in ("impressions", "spend") if row.get(key) is not None],
                    "impressions_range": row.get("impressions"),
                    "spend_range": row.get("spend"),
                    "demographic_distribution": row.get("demographic_distribution"),
                    "snapshot_date": metric_date.isoformat(),
                },
            },
        )


def sync_competitor_live(competitor: Competitor, limit=None):
    try:
        with transaction.atomic():
            # Prevent identity edits during fetch and roll back partial imports.
            locked = Competitor.objects.select_for_update().get(pk=competitor.pk)
            from core.services.competitor_public_sources import competitor_source
            result = competitor_source(locked).sync(limit=limit)
            locked.raw_data = {**(locked.raw_data or {}),
                "last_live_sync_status": "success", "last_live_sync_error": "",
                "last_live_sync_attempt_at": timezone.now().isoformat()}
            locked.save(update_fields=["raw_data", "updated_at"])
        competitor.refresh_from_db()
    except Exception as exc:
        competitor.refresh_from_db()
        error = str(exc) if isinstance(exc, CompetitorSyncError) else "Rakip reklam çekimi tamamlanamadı. Yeniden deneyin; sorun sürerse destekle iletişime geçin."
        if not isinstance(exc, CompetitorSyncError):
            logging.getLogger(__name__).error("Competitor sync failed id=%s error_type=%s", competitor.pk, type(exc).__name__)
        competitor.raw_data = {**(competitor.raw_data or {}),
            "last_live_sync_status": "error", "last_live_sync_error": error,
            "last_live_sync_attempt_at": timezone.now().isoformat()}
        if isinstance(exc, CompetitorAdvertiserChoiceRequired):
            competitor.raw_data['google_advertiser_candidates'] = exc.candidates
        competitor.save(update_fields=["raw_data", "updated_at"])
        if isinstance(exc, CompetitorSyncError):
            raise
        raise CompetitorSyncError(error) from exc
    return result

"""Persist measured TikTok Ads campaign and ad history after complete reads."""
from datetime import date, timedelta
from collections import defaultdict
import json

from django.db import transaction
from django.utils import timezone

from core.models import PlatformAccount, Campaign, CampaignMetricHistory
from core.services import tiktok_ads as api
from core.services.ads_integrations import IntegrationError, account_today
from core.services.v2_ad_sync import metric_defaults, upsert_v2_ad_snapshot, rebuild_ad_metric_rollups


def sync_tiktok_campaigns(account, days_back, max_records, source_type="OWN"):
    token = api.account_token(account)
    info = api.advertiser_info(token, account.account_id)
    account.extra_data = {**(account.extra_data or {}), **info}
    end = account_today(account)
    start = end - timedelta(days=max(1, min(int(days_back), 3650)) - 1)
    inventory = api.inventory(token, account.account_id)
    campaign_metrics = api.report(token, account.account_id, start, end, limit=max_records)
    ad_metrics = api.report(token, account.account_id, start, end, level="ad", limit=max_records)
    if len(campaign_metrics) + len(ad_metrics) > max_records:
        raise IntegrationError("TikTok performans kayıtları plan sınırını aşıyor. Daha kısa tarih aralığı seçin.")
    measured_ids = {row["campaign_id"] for row in campaign_metrics}
    campaign_reports = defaultdict(list)
    for row in campaign_metrics:
        campaign_reports[row["campaign_id"]].append(row)
    if not measured_ids <= inventory.keys():
        raise IntegrationError("TikTok metrikleri kampanya listesiyle eşleştirilemedi.")
    ads, groups = {}, {}
    if ad_metrics:
        params = {"advertiser_id": account.account_id, "filtering": json.dumps({"primary_status": "STATUS_ALL"})}
        for row in api.rows(token, "ad/get", params):
            aid = str(row.get("ad_id") or "")
            if not aid.isdigit() or aid in ads:
                raise IntegrationError("TikTok reklam kimliği doğrulanamadı.")
            ads[aid] = row
        for row in api.rows(token, "adgroup/get", params):
            gid = str(row.get("adgroup_id") or "")
            if not gid.isdigit() or gid in groups:
                raise IntegrationError("TikTok reklam grubu kimliği doğrulanamadı.")
            groups[gid] = row
    payloads = []
    for metric in ad_metrics:
        ad = ads.get(metric["ad_id"])
        if not ad:
            raise IntegrationError("TikTok reklam metriği reklam bilgisiyle eşleştirilemedi.")
        cid, gid = str(ad.get("campaign_id") or ""), str(ad.get("adgroup_id") or "")
        group = groups.get(gid)
        if (cid not in inventory or not group or str(group.get("campaign_id")) != cid
                or not ad.get("ad_name") or not group.get("adgroup_name")):
            raise IntegrationError("TikTok reklam hiyerarşisi eksik. Hiçbir veri kaydedilmedi.")
        campaign = inventory[cid]
        measured_ids.add(cid)
        payloads.append({**metric, "spend": str(metric["spend"]), "currency": info["currency"], "platform_ad_id": metric["ad_id"],
            "platform_campaign_id": cid, "campaign_name": campaign["name"], "campaign_status": campaign["status"],
            "platform_adgroup_id": gid, "adgroup_name": group["adgroup_name"], "ad_name": ad["ad_name"],
            "status": {"ENABLE": "ACTIVE", "DISABLE": "PAUSED", "DELETE": "DELETED"}.get(ad.get("operation_status"), "UNKNOWN"),
            "campaign_raw": campaign["raw"], "ad_raw": ad, "objective": campaign["objective"],
            "allow_estimated_conversion_value": False})
    now = timezone.now()
    with transaction.atomic():
        locked = PlatformAccount.objects.select_for_update().get(pk=account.pk)
        if not locked.is_active or locked.connection_id != account.connection_id:
            raise IntegrationError("TikTok reklam bağlantısı değişti. Yeniden deneyin.")
        for payload in payloads:
            upsert_v2_ad_snapshot(user=account.user, platform_account=account, payload=payload, source_type=source_type)
        rebuild_ad_metric_rollups(account, {date.fromisoformat(row["date"]) for row in payloads})
        # Campaign report is authoritative; ad totals cannot replace it.
        for cid in measured_ids:
            row = inventory[cid]
            campaign, _ = Campaign.objects.update_or_create(platform_account=account, platform_campaign_id=cid,
                defaults={"user": account.user, "platform_connection": account.connection, "name": row["name"],
                          "status": row["status"], "objective": row["objective"], "currency": info["currency"],
                          "is_active": row["status"] == "ACTIVE", "raw_data": row["raw"], "last_synced_at": now})
            for metric in campaign_reports[cid]:
                defaults = metric_defaults({**metric, "currency": info["currency"], "allow_estimated_conversion_value": False})
                defaults["raw_metrics"] = {key: str(value) for key, value in metric.items()}
                CampaignMetricHistory.objects.update_or_create(campaign=campaign, date=date.fromisoformat(metric["date"]), defaults=defaults)
        locked.last_sync = now
        locked.extra_data = {**(locked.extra_data or {}), **info, "ads_sync_summary": {
            "completed_at": now.isoformat(), "days_back": days_back, "campaigns": len(measured_ids),
            "ads": len({row["ad_id"] for row in ad_metrics}), "metric_rows": len(campaign_metrics) + len(ad_metrics)}}
        locked.save(update_fields=["last_sync", "extra_data", "updated_at"])
    return {"account_id": account.pk, "platform": "tiktok", "source_type": source_type,
            "ads_synced": len({row["ad_id"] for row in ad_metrics}), "campaigns_synced": len(measured_ids),
            "metric_rows": len(campaign_metrics) + len(ad_metrics)}

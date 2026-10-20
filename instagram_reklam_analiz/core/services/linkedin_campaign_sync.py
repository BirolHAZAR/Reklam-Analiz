"""Persist the existing LinkedIn campaign report without inventing ads or creatives."""
from datetime import date, timedelta

from django.db import transaction
from django.utils import timezone
from django.utils.dateparse import parse_datetime

from core.models import Campaign, CampaignMetricHistory
from core.services import ads_integrations as api
from core.services.v2_ad_sync import metric_defaults


def sync_linkedin_campaigns(account, days_back, max_records, source_type="OWN"):
    end = timezone.localdate()
    start = end - timedelta(days=days_back - 1)
    inventory = api.campaigns(account)
    if len(inventory) > max_records:
        raise api.IntegrationError("Kampanya sayısı planın kayıt sınırını aşıyor.")
    # Finish every provider read before changing stored inventory or history.
    reports = {}
    for row in inventory:
        reports[str(row["id"])] = api.campaign_performance(account, row["id"], start, end)
    metric_count = sum(len(rows) for rows in reports.values())
    if metric_count > max_records:
        raise api.IntegrationError("Veri aralığı planın kayıt sınırını aşıyor; daha kısa bir tarih aralığı seçin.")
    inventory = [row for row in inventory if reports[str(row["id"])]]
    now = timezone.now()
    currency = (account.extra_data or {}).get("currency") or "TRY"
    with transaction.atomic():
        for row in inventory:
            if not reports[str(row["id"])]:
                continue
            campaign, _ = Campaign.objects.update_or_create(
                platform_account=account, platform_campaign_id=str(row["id"]),
                defaults={"user": account.user, "platform_connection": account.connection,
                    "name": row["name"], "status": row["status"], "is_active": True,
                    "objective": row.get("objective") or "UNKNOWN", "currency": currency,
                    "start_time": parse_datetime(row["start_time"]) if row.get("start_time") else None,
                    "end_time": parse_datetime(row["stop_time"]) if row.get("stop_time") else None,
                    "raw_data": row, "last_synced_at": now})
            for metric in reports[str(row["id"])]:
                defaults = metric_defaults({**metric, "currency": currency,
                                           "allow_estimated_conversion_value": False})
                defaults["raw_metrics"] = {key: str(value) for key, value in metric.items()}
                CampaignMetricHistory.objects.update_or_create(campaign=campaign,
                    date=date.fromisoformat(metric["date"]), defaults=defaults)
        Campaign.objects.filter(platform_account=account).exclude(
            platform_campaign_id__in=[str(row["id"]) for row in inventory]).update(is_active=False)
        account.last_sync = now
        account.extra_data = {**(account.extra_data or {}), "ads_sync_summary": {
            "completed_at": now.isoformat(), "active_only": True, "days_back": days_back,
            "campaigns": len(inventory), "ads": 0, "metric_rows": metric_count,
            "report_level": "campaign"}}
        account.save(update_fields=["last_sync", "extra_data"])
        from core.services.measurement_policy import prune_unmeasured
        prune_unmeasured(account, apply=True)
    return {"account_id": account.pk, "platform": "linkedin", "source_type": source_type,
            "ads_synced": 0, "campaigns_synced": len(inventory), "metric_rows": metric_count}

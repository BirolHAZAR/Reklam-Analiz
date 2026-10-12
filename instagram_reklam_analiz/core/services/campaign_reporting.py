"""Human-readable campaign state and weighted reporting metrics."""
from decimal import Decimal
from django.utils import timezone
from django.utils.dateparse import parse_date, parse_datetime


OBJECTIVES = {
    "OUTCOME_TRAFFIC": "Trafik", "OUTCOME_SALES": "Satış", "OUTCOME_LEADS": "Potansiyel müşteri",
    "OUTCOME_ENGAGEMENT": "Etkileşim", "OUTCOME_AWARENESS": "Bilinirlik",
    "OUTCOME_APP_PROMOTION": "Uygulama tanıtımı", "LINK_CLICKS": "Bağlantı tıklamaları",
    "CONVERSIONS": "Dönüşümler", "REACH": "Erişim", "BRAND_AWARENESS": "Marka bilinirliği",
    "SEARCH": "Arama ağı", "DISPLAY": "Görüntülü reklam", "VIDEO": "Video",
    "SHOPPING": "Alışveriş", "PERFORMANCE_MAX": "Performance Max", "DEMAND_GEN": "Talep yaratma",
}


def decorate_campaign(row, *, now=None, today=None):
    row = dict(row)
    row.setdefault("objective", "")
    row.setdefault("channel", "")
    now = now or timezone.now()
    today = today or timezone.localdate(now)
    status = row.get("status", "UNKNOWN")
    label, tone, group = {
        "ACTIVE": ("Aktif", "active", "active"), "ENABLED": ("Aktif", "active", "active"),
        "PAUSED": ("Duraklatıldı", "paused", "inactive"),
        "ARCHIVED": ("Arşivlendi", "inactive", "inactive"),
        "DELETED": ("Silindi", "inactive", "inactive"), "REMOVED": ("Kaldırıldı", "inactive", "inactive"),
        "DISAPPROVED": ("Reddedildi", "danger", "inactive"),
        "IN_PROCESS": ("İşleniyor", "paused", "other"),
        "WITH_ISSUES": ("Sorun var", "danger", "other"),
    }.get(status, ("Durum bilinmiyor", "inactive", "other"))
    row["configured_status_label"] = label
    state_note = ""
    stop = parse_datetime(row.get("stop_time") or "")
    start = parse_datetime(row.get("start_time") or "")
    if stop and timezone.is_naive(stop):
        stop = timezone.make_aware(stop)
    if start and timezone.is_naive(start):
        start = timezone.make_aware(start)
    end_date = parse_date(row.get("end_date") or "")
    start_date = parse_date(row.get("start_date") or "")
    if status in {"ACTIVE", "ENABLED"}:
        if (stop and stop <= now) or (end_date and end_date < today):
            label, tone, group = "Tamamlandı", "inactive", "inactive"
            state_note = "Yayın süresi sona erdi"
        elif (start and start > now) or (start_date and start_date > today):
            label, tone, group = "Planlandı", "paused", "other"
            state_note = "Başlangıç tarihi bekleniyor"
    objective = row.get("channel") or row.get("objective") or ""
    row.update(status_label=label, status_tone=tone, status_group=group,
               status_note=state_note,
               objective_label=OBJECTIVES.get(objective, objective or "Belirtilmedi"),
               start_label=timezone.localtime(start).strftime("%d.%m.%Y") if start else
               (start_date.strftime("%d.%m.%Y") if start_date else "—"),
               end_label=timezone.localtime(stop).strftime("%d.%m.%Y") if stop else
               (end_date.strftime("%d.%m.%Y") if end_date and end_date.year < 2037 else "—"))
    return row


def summarize_metrics(rows):
    rows = list(rows)
    if not rows:
        return None
    summary = {key: sum(Decimal(str(row.get(key) or 0)) for row in rows)
               for key in ("impressions", "clicks", "spend", "conversions", "conversion_value")}
    summary["ctr"] = summary["clicks"] / summary["impressions"] * 100 if summary["impressions"] else None
    summary["cpc"] = summary["spend"] / summary["clicks"] if summary["clicks"] else None
    summary["cpm"] = summary["spend"] / summary["impressions"] * 1000 if summary["impressions"] else None
    return summary

from decimal import Decimal
from datetime import timedelta

from django.contrib.auth.decorators import login_required
from django.db.models import Sum, Count, Q, Max
from django.http import JsonResponse
from django.shortcuts import render
from django.urls import reverse, NoReverseMatch
from django.utils import timezone

from core.models import (
    Ad,
    AdGroup,
    AdMetricHistory,
    AnomalyAlert,
    Campaign,
    CampaignMetricHistory,

    Creative,
    Notification,
    OctoTaskInstance,
    OpportunityWindow,
    PlatformAccount,
    PlatformConnection,
)
from core.services.cache_service import DashboardCacheManager
from core.services.agency_scope import (
    get_agency_scope,
    platform_accounts_for_request,
    scope_client_queryset,
    scope_queryset,
)
from core.services.performance_metrics import aggregate_metric_queryset, user_performance_queryset
from core.services.control_tower_context import _octo_ai_score_engine, _pct_change, _score_from_roas_ctr


EXECUTIVE_DASHBOARD_CACHE_TIMEOUT = 120


def _money(value):
    value = Decimal(value or 0)
    return f"{value:,.2f} TL".replace(",", "X").replace(".", ",").replace("X", ".")


def _num(value):
    try:
        return f"{int(value or 0):,}".replace(",", ".")
    except Exception:
        return "0"


def _pct(value, digits=2):
    try:
        return round(float(value or 0), digits)
    except Exception:
        return 0


def _metric_summary_for_ads(ads_qs, start_date, end_date):
    metrics_qs = AdMetricHistory.objects.filter(
        ad__in=ads_qs,
        date__gte=start_date,
        date__lte=end_date,
    )
    return aggregate_metric_queryset(metrics_qs)


def _metric_summary_for_ad(ad, start_date, end_date):
    metrics_qs = ad.metric_history.filter(date__gte=start_date, date__lte=end_date)
    return aggregate_metric_queryset(metrics_qs)


def _safe_url(name, fallback="#"):
    try:
        return reverse(name)
    except NoReverseMatch:
        return fallback


def _trend_percent(current, previous):
    current = float(current or 0)
    previous = float(previous or 0)
    if previous == 0:
        return 100 if current > 0 else 0
    return round(((current - previous) / previous) * 100, 1)


SEVERITY_LABELS = {
    "critical": "Kritik",
    "high": "Yüksek",
    "medium": "Orta",
    "low": "Düşük",
}


@login_required
def executive_dashboard(request):
    """
    Executive Command Center
    ------------------------
    Bu sayfa kullanıcının gerçek veritabanı kayıtlarından
    kampanya, reklam, reklam grubu, kreatif, anomali, bildirim ve platform durumunu okur.
    Kayıt yoksa metrikler 0 değerleriyle gösterilir.
    """
    user = request.user
    agency_scope = get_agency_scope(request)
    cached_context = DashboardCacheManager.get_user_dashboard(user.id, agency_scope.cache_key)
    if cached_context is not None:
        return render(request, "dashboard/executive.html", cached_context)

    today = timezone.localdate()
    start_30 = today - timedelta(days=29)
    prev_start = today - timedelta(days=59)
    prev_end = today - timedelta(days=30)

    own_ads = scope_queryset(request, Ad.objects.filter(source_type="OWN"))
    campaigns = scope_queryset(request, Campaign.objects.all())
    adgroups = scope_queryset(request, AdGroup.objects.all(), account_lookup="campaign__platform_account")
    creatives = scope_queryset(request, Creative.objects.all())

    current_qs = AdMetricHistory.objects.filter(ad__in=own_ads, date__gte=start_30, date__lte=today)
    previous_qs = AdMetricHistory.objects.filter(ad__in=own_ads, date__gte=prev_start, date__lte=prev_end)
    current_metrics = _metric_summary_for_ads(own_ads, start_30, today)
    previous_metrics = _metric_summary_for_ads(own_ads, prev_start, prev_end)

    spend = current_metrics["spend"] or Decimal("0")
    impressions = current_metrics["impressions"] or 0
    clicks = current_metrics["clicks"] or 0
    conversions = current_metrics["conversions"] or Decimal("0")
    ctr = float(current_metrics["ctr"] or 0)
    cpc = float(current_metrics["cpc"] or 0)
    cpa = float(current_metrics["cpa"] or 0)
    roas = float(current_metrics["roas"] or 0)
    revenue = current_metrics["conversion_value"] or Decimal("0")
    reach = current_metrics["reach"] or 0
    cpm = float(current_metrics["cpm"] or 0)
    conversion_rate = float(current_metrics["conversion_rate"] or 0)

    prev_spend = previous_metrics["spend"] or Decimal("0")
    prev_conversions = previous_metrics["conversions"] or Decimal("0")
    prev_roas = float(previous_metrics["roas"] or 0)
    prev_ctr = float(previous_metrics["ctr"] or 0)

    critical_alerts = AnomalyAlert.objects.filter(
        user=user,
        is_dismissed=False,
    ).filter(
        Q(severity="critical") | Q(severity="high")
    ).order_by("is_read", "-detected_at", "-id")

    if agency_scope.selected_client:
        critical_alerts = critical_alerts.filter(
            ad__platform_account__agency_client=agency_scope.selected_client
        )

    # Notification ve OpportunityWindow modellerinde musteri baglantisi yok. Ajans
    # musteri ekraninda kullanici-geneli metinleri gostermek veri sizintisi riski
    # tasidigi icin musteri seciliyken bunlari bilincli olarak disarida birakiyoruz.
    unread_notifications = 0 if agency_scope.selected_client else Notification.objects.filter(user=user, is_read=False).count()

    platform_rows = []
    account_stats = platform_accounts_for_request(request).values(
        "platform__name", "platform__code"
    ).annotate(
        account_count=Count("id"),
        active_accounts=Count("id", filter=Q(is_active=True)),
        last_sync=Max("last_sync"),
    ).order_by("platform__name")

    for row in account_stats:
        code = row.get("platform__code") or ""
        name = row.get("platform__name") or "Platform"
        platform_rows.append({
            "name": name,
            "code": code,
            "account_count": row["account_count"],
            "active_accounts": row["active_accounts"],
            "last_sync": row["last_sync"],
            "ads_count": own_ads.filter(platform_account__platform__code=code).count() if code else 0,
            "status": "active" if row["active_accounts"] else "passive",
        })

    # PlatformAccount yoksa bağlantı seviyesinden de göster.
    if not platform_rows:
        connection_stats = PlatformConnection.objects.filter(user=user).values(
            "platform__name", "platform__code", "status"
        ).annotate(connection_count=Count("id"), last_sync=Max("last_sync")).order_by("platform__name")
        for row in connection_stats:
            platform_rows.append({
                "name": row.get("platform__name") or "Platform",
                "code": row.get("platform__code") or "",
                "account_count": row["connection_count"],
                "active_accounts": row["connection_count"] if row.get("status") == "active" else 0,
                "last_sync": row["last_sync"],
                "ads_count": 0,
                "status": row.get("status") or "unknown",
            })

    top_campaigns = []
    campaign_perf = campaigns.annotate(
        spend_30=Sum("metric_history__spend", filter=Q(metric_history__date__gte=start_30, metric_history__date__lte=today)),
        impressions_30=Sum("metric_history__impressions", filter=Q(metric_history__date__gte=start_30, metric_history__date__lte=today)),
        clicks_30=Sum("metric_history__clicks", filter=Q(metric_history__date__gte=start_30, metric_history__date__lte=today)),
        conversions_30=Sum("metric_history__conversions", filter=Q(metric_history__date__gte=start_30, metric_history__date__lte=today)),
        value_30=Sum("metric_history__conversion_value", filter=Q(metric_history__date__gte=start_30, metric_history__date__lte=today)),
    ).order_by("-spend_30", "name")

    for campaign in campaign_perf:
        c_summary = aggregate_metric_queryset(
            campaign.metric_history.filter(date__gte=start_30, date__lte=today)
        )
        c_spend = c_summary.get("spend") or Decimal("0")
        top_campaigns.append({
            "id": campaign.id,
            "name": campaign.name,
            "status": campaign.status,
            "status_label": campaign.get_status_display(),
            "objective": campaign.objective,
            "objective_label": campaign.get_objective_display(),
            "spend": _money(c_spend),
            "ctr": round(float(c_summary.get("ctr") or 0), 2),
            "roas": round(float(c_summary.get("roas") or 0), 2),
            "url": f"{_safe_url('campaign_center', '/campaign-center/')}?campaign_id={campaign.id}",
        })

    opportunities = (
        OpportunityWindow.objects.none()
        if agency_scope.selected_client
        else OpportunityWindow.objects.filter(user=user, is_taken=False).order_by("-confidence_score", "-detected_at")[:4]
    )

    ai_actions = []
    if critical_alerts:
        ai_actions.append({
            "group": "own",
            "level": "danger",
            "icon_class": "fa-triangle-exclamation",
            "title": f"{critical_alerts.count()} kritik uyarı müdahale bekliyor",
            "text": "Bütçe, CTR veya performans anomalilerini önceliklendir.",
            "priority": "Acil",
            "impact": "Yüksek",
            "reason": "Kritik veya yüksek seviye uyarılar operasyon sağlığını doğrudan etkiliyor.",
            "url": _safe_url("anomaly_detector", "/anomaly-detector/"),
            "button": "Uyarıları İncele",
        })
    if roas and roas < 1.5 and spend:
        ai_actions.append({
            "group": "own",
            "level": "warning",
            "icon_class": "fa-sack-dollar",
            "title": "ROAS baskı altında",
            "text": "Düşük dönüşüm değerli kampanyalarda bütçe ve kreatif kontrolü önerilir.",
            "priority": "Yüksek",
            "impact": "Gelir",
            "reason": f"Son dönem ROAS {roas:.2f}x seviyesinde ve harcama devam ediyor.",
            "url": _safe_url("budget_optimization", "/budget-optimization/"),
            "button": "Bütçeyi İncele",
        })
    if not ai_actions:
        ai_actions.append({
            "group": "own",
            "level": "success",
            "icon_class": "fa-circle-check",
            "title": "Operasyon stabil görünüyor",
            "text": "Kritik aksiyon yok. Performans trendlerini takip etmeye devam edin.",
            "priority": "Normal",
            "impact": "Takip",
            "reason": "Kritik eşikleri aşan yeni risk görünmüyor.",
            "url": _safe_url("performance_center", "/performance-center/"),
            "button": "Performansı Aç",
        })
    ai_action_groups = [
        {
            "kind": "own",
            "icon_class": "fa-brain",
            "title": "Kendi Kampanya Hareketleri",
            "subtitle": "Bütçe, ROAS, uyarı ve performans aksiyonları",
            "actions": [action for action in ai_actions if action.get("group") == "own"],
        },
    ]
    ai_action_groups = [group for group in ai_action_groups if group["actions"]]

    has_data = (
        campaigns.exists()
        or own_ads.exists()
        or bool(platform_rows)
        or current_qs.exists()
    )

    if has_data:
        # Executive Dashboard ve Control Tower aynı Octo sağlık motorunu kullanır.
        # Böylece yalnızca varlıkların mevcut olmasına puan veren eski 50 tabanlı
        # "hazırlık" skoru müşteriye performans sağlığı gibi sunulmaz.
        active_task_qs = OctoTaskInstance.objects.filter(
            user=user,
            status__in=["open", "viewed", "snoozed"],
        )
        if agency_scope.selected_client:
            client = agency_scope.selected_client
            active_task_qs = active_task_qs.filter(
                Q(platform_account__agency_client=client)
                | Q(campaign__platform_account__agency_client=client)
                | Q(ad_group__campaign__platform_account__agency_client=client)
                | Q(ad__platform_account__agency_client=client)
                | Q(creative__platform_account__agency_client=client)
            ).distinct()

        high_task_count = active_task_qs.filter(severity="critical").count()
        critical_signal_count = critical_alerts.count() + high_task_count
        spend_delta = _pct_change(spend, prev_spend)
        creative_score = _score_from_roas_ctr(roas, ctr)
        octo_health = _octo_ai_score_engine(
            roas=roas,
            ctr=ctr,
            cpc=cpc,
            conversion_rate=conversion_rate,
            spend_delta=spend_delta,
            creative_score=creative_score,
            critical_alert_count=critical_signal_count,
            pending_ai_tasks=active_task_qs.filter(status="open").count(),
            high_ai_tasks=high_task_count,
        )
        health_score = octo_health["score"]
        health_state_label = octo_health["label"]
        date_range_label = f"{start_30.strftime('%d.%m.%Y')} - {today.strftime('%d.%m.%Y')}"
    else:
        health_score = 0
        health_state_label = "Hazır"
        date_range_label = "0 kayıt"

    context = {
        "page_kicker": "Yönetici Komuta Merkezi",
        "date_range_label": date_range_label,
        "health_score": health_score,
        "health_state_label": health_state_label,
        "metrics": [
            {"label": "Toplam Harcama", "value": _money(spend), "trend": _trend_percent(spend, prev_spend), "icon_class": "fa-sack-dollar", "tone": "primary"},
            {"label": "ROAS", "value": f"{roas:.2f}x", "trend": _trend_percent(roas, prev_roas), "icon_class": "fa-chart-line", "tone": "success"},
            {"label": "CTR", "value": f"%{ctr:.2f}", "trend": _trend_percent(ctr, prev_ctr), "icon_class": "fa-bullseye", "tone": "info"},
            {"label": "Dönüşüm", "value": _num(conversions), "trend": _trend_percent(conversions, prev_conversions), "icon_class": "fa-bolt", "tone": "warning"},
        ],
        "summary": {
            "campaigns": campaigns.count(),
            "active_campaigns": campaigns.filter(status="ACTIVE").count(),
            "adgroups": adgroups.count(),
            "own_ads": own_ads.count(),
            "active_ads": own_ads.filter(status="ACTIVE").count(),
            "creatives": creatives.count(),
            "unread_notifications": unread_notifications,
            "critical_alerts": critical_alerts.count(),
            "impressions": _num(impressions),
            "reach": _num(reach),
            "clicks": _num(clicks),
            "cpc": _money(cpc),
            "cpm": _money(cpm),
            "cpa": _money(cpa),
            "revenue": _money(revenue),
            "conversion_rate": f"%{conversion_rate:.2f}",
        },
        "platform_rows": platform_rows,
        "top_campaigns": top_campaigns,
        "critical_alerts": [
            {
                "title": alert.title,
                "description": alert.description,
                "severity": alert.severity,
                "severity_label": SEVERITY_LABELS.get(alert.severity, alert.get_severity_display()),
            }
            for alert in critical_alerts
        ],
        "opportunities": list(opportunities),
        "ai_actions": ai_actions,
        "ai_action_groups": ai_action_groups,
        "has_data": True,
        "has_operational_data": has_data,
        "urls": {
            "campaign_center": _safe_url("campaign_center", "/campaign-center/"),
            "adgroup_center": _safe_url("adgroup_center", "/adgroup-center/"),
            "ads_center": _safe_url("ads_center", "/reklam-paneli/"),
            "budget": _safe_url("budget_optimization", "/budget-optimization/"),
            "notifications": _safe_url("notification_center", "/notifications/"),
            "sync": _safe_url("sync_center", "/sync-center/"),
        },
    }
    DashboardCacheManager.set_user_dashboard(
        user.id,
        context,
        timeout=EXECUTIVE_DASHBOARD_CACHE_TIMEOUT,
        scope_key=agency_scope.cache_key,
    )
    return render(request, "dashboard/executive.html", context)


@login_required
def check_alerts_api(request):
    alerts = AnomalyAlert.objects.filter(user=request.user, is_read=False, is_dismissed=False)
    agency_scope = get_agency_scope(request)
    if agency_scope.selected_client:
        alerts = alerts.filter(ad__platform_account__agency_client=agency_scope.selected_client)
    count = alerts.count()
    return JsonResponse({"success": True, "count": count})


@login_required
def mark_alerts_read(request):
    alerts = AnomalyAlert.objects.filter(user=request.user, is_dismissed=False)
    agency_scope = get_agency_scope(request)
    if agency_scope.selected_client:
        alerts = alerts.filter(ad__platform_account__agency_client=agency_scope.selected_client)
    alerts.update(is_read=True)
    return JsonResponse({"success": True})

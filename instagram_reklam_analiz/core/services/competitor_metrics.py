"""Ad Library ranges are cumulative snapshots, not measured daily performance."""
from decimal import Decimal, InvalidOperation

from django.db.models import OuterRef, Q, Subquery, Sum, Avg

LIBRARY_PROVIDERS = ('meta_ad_library', 'meta_ad_library_searchapi', 'linkedin_ad_library_searchapi', 'google_ads_transparency_serpapi', 'tiktok_commercial_content')


LIBRARY_UNAVAILABLE = (
    "clicks", "reach", "frequency", "engagement", "engagement_rate", "ctr", "cpc", "cpm",
    "conversions", "conversion_rate", "roi", "roas", "budget", "budget_usage_percent",
    "likes", "comments", "shares", "saves", "video_views", "video_completion_rate", "performance_score",
)


def is_library_metric(metric):
    return bool(metric and (metric.raw_metrics or {}).get("provider") in LIBRARY_PROVIDERS)


def range_midpoint(value):
    if value is None:
        return None
    try:
        if isinstance(value, dict):
            lower = value.get("lower_bound", value.get("min"))
            upper = value.get("upper_bound", value.get("max"))
            # An open-ended range does not have a known midpoint.
            if lower is None or upper is None:
                return None
            if Decimal(str(upper)) < Decimal(str(lower)):
                return None
            value = (Decimal(str(lower)) + Decimal(str(upper))) / 2
        result = Decimal(str(value))
        return result if result.is_finite() and result >= 0 else None
    except (InvalidOperation, ValueError, TypeError):
        return None


def metric_values(metric):
    if not metric:
        return {key: None for key in (*LIBRARY_UNAVAILABLE, "impressions", "spend")}
    values = {key: getattr(metric, key, None) for key in (*LIBRARY_UNAVAILABLE, "impressions", "spend")}
    if is_library_metric(metric):
        values.update({key: None for key in LIBRARY_UNAVAILABLE})
        values["impressions"] = range_midpoint(metric.raw_metrics.get("impressions_range"))
        values["spend"] = range_midpoint(metric.raw_metrics.get("spend_range"))
    return values


def effective_history(queryset):
    latest = queryset.filter(is_competitor_snapshot=True, ad_id=OuterRef("ad_id")).order_by("-date", "-pk").values("pk")[:1]
    return queryset.filter(Q(is_competitor_snapshot=False) | Q(pk=Subquery(latest)))


def summarize_metrics(queryset):
    selected = effective_history(queryset)
    # Legacy fabricated metrics must not leak into totals, even before cleanup.
    measured = selected.filter(Q(raw_metrics__provider__isnull=True) | ~Q(raw_metrics__provider__in=LIBRARY_PROVIDERS))
    fields = ("impressions", "clicks", "engagement", "spend", "conversions")
    result = measured.aggregate(**{key: Sum(key) for key in fields},
                                ctr=Avg("ctr"), cpc=Avg("cpc"), roas=Avg("roas"))
    for metric in selected.filter(raw_metrics__provider__in=LIBRARY_PROVIDERS):
        values = metric_values(metric)
        for key in ("impressions", "spend"):
            if values[key] is not None:
                result[key] = (result.get(key) or Decimal("0")) + values[key]
    return result

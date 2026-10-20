"""Only provider measurements may create performance entities. Zero is a value."""
from django.db import transaction
from django.db.models import Exists, OuterRef
from core.models import Ad, AdGroup, Creative, Campaign


def has_measurement(payload):
    return payload.get("metrics_available") is not False and any(
        payload.get(key) not in (None, "") for key in (
            "impressions", "clicks", "spend", "reach", "conversions", "engagement", "likes", "video_views"))


def prune_unmeasured(account, *, apply=False):
    """Keep all measured history, including history on inactive entities."""
    with transaction.atomic():
        ads = Ad.objects.filter(platform_account=account, source_type="OWN", metric_history__isnull=True)
        counts = {"ads": ads.count()}
        if not apply:
            kept_ads = Ad.objects.exclude(pk__in=ads.values("pk"))
            groups = AdGroup.objects.filter(campaign__platform_account=account,
                metric_history__isnull=True).filter(~Exists(kept_ads.filter(ad_group_id=OuterRef("pk"))))
            creatives = Creative.objects.filter(platform_account=account,
                metric_history__isnull=True).filter(~Exists(kept_ads.filter(creative_id=OuterRef("pk"))))
            kept_groups = AdGroup.objects.exclude(pk__in=groups.values("pk"))
            campaigns = Campaign.objects.filter(platform_account=account,
                metric_history__isnull=True).filter(~Exists(kept_ads.filter(campaign_id=OuterRef("pk"))),
                ~Exists(kept_groups.filter(campaign_id=OuterRef("pk"))))
            counts.update(ad_groups=groups.count(), creatives=creatives.count(), campaigns=campaigns.count())
            return counts
        ads.delete()
        groups = AdGroup.objects.filter(campaign__platform_account=account,
            ads__isnull=True, metric_history__isnull=True)
        counts["ad_groups"] = groups.count()
        groups.delete()
        creatives = Creative.objects.filter(platform_account=account, ads__isnull=True, metric_history__isnull=True)
        counts["creatives"] = creatives.count()
        creatives.delete()
        campaigns = Campaign.objects.filter(platform_account=account, ads__isnull=True,
            ad_groups__isnull=True, metric_history__isnull=True)
        counts["campaigns"] = campaigns.count()
        campaigns.delete()
        return counts

from .base import BasePlatformAPI
from datetime import timedelta
import json
from decimal import Decimal
from django.utils import timezone
from core.services.ads_integrations import account_token, account_today, meta_rows


def _distinct_actions(items):
    """Meta reports overlapping aliases for a single purchase/lead event."""
    aliases = (
        ("purchase", "omni_purchase", "offsite_conversion.fb_pixel_purchase", "onsite_conversion.purchase", "web_in_store_purchase"),
        ("lead", "omni_lead", "offsite_conversion.fb_pixel_lead", "onsite_conversion.lead_grouped"),
        ("add_to_cart", "omni_add_to_cart", "offsite_conversion.fb_pixel_add_to_cart"),
        ("initiate_checkout", "omni_initiated_checkout", "offsite_conversion.fb_pixel_initiate_checkout"),
    )
    values = {item.get("action_type"): item for item in (items or [])}
    excluded = {name for group in aliases for name in group} | {"offsite_conversion.fb_pixel_custom"}
    result = [item for item in (items or []) if item.get("action_type") not in excluded]
    for group in aliases:
        first = next((values[name] for name in group if name in values), None)
        if first is not None:
            result.append(first)
    return result


class FacebookAPI(BasePlatformAPI):
    def get_campaigns(self):
        # No date or ACTIVE-only filter: paused campaigns and campaigns without
        # ads must remain discoverable even when there are no Insights rows.
        return meta_rows(account_token(self.account), f"{self.account.account_id}/campaigns", {
            "fields": "id,name,status,objective,daily_budget,lifetime_budget,start_time,stop_time",
            # Graph v25 rejects DELETED as an inventory filter (1815001).
            # Deleted entities already in history remain in the database.
            "effective_status": json.dumps(["ACTIVE", "PAUSED", "ARCHIVED", "IN_PROCESS", "WITH_ISSUES"]),
        })

    def get_ads(self, since_days=30):
        end = account_today(self.account)
        start = end - timedelta(days=max(1, min(int(since_days), 365)) - 1)
        token = account_token(self.account)
        metadata = {row["id"]: row for row in meta_rows(token, f"{self.account.account_id}/ads", {
            "fields": "id,name,effective_status,campaign{id,name,status,objective},adset{id,name,status,daily_budget,lifetime_budget,start_time,end_time},creative{id,name,title,body,thumbnail_url,object_url,call_to_action_type,image_url}",
            "effective_status": json.dumps(["ACTIVE", "PAUSED", "ARCHIVED", "PENDING_REVIEW", "DISAPPROVED", "PREAPPROVED", "PENDING_BILLING_INFO", "CAMPAIGN_PAUSED", "ADSET_PAUSED", "IN_PROCESS", "WITH_ISSUES"]),
        })}
        rows = meta_rows(token, f"{self.account.account_id}/insights", {
            "level": "ad", "time_increment": 1,
            "fields": "ad_id,ad_name,campaign_id,campaign_name,adset_id,adset_name,date_start,impressions,reach,clicks,spend,actions,action_values,account_currency",
            "time_range": json.dumps({"since": start.isoformat(), "until": end.isoformat()}),
        })
        inventory = []
        for ad_id, ad in metadata.items():
            campaign = ad.get("campaign") or {}
            adset = ad.get("adset") or {}
            creative = ad.get("creative") or {}
            inventory.append({
                "platform_ad_id": ad_id, "name": ad.get("name"),
                "platform_campaign_id": campaign.get("id"), "campaign_name": campaign.get("name"),
                "campaign_status": campaign.get("status", "UNKNOWN"),
                "objective": campaign.get("objective"), "campaign_raw": campaign,
                "platform_adgroup_id": adset.get("id"), "adgroup_name": adset.get("name"),
                "adgroup_status": adset.get("status", "UNKNOWN"), "adgroup_raw": adset,
                **{f"adgroup_{key}": str(Decimal(str(adset[key])) / 100) for key in ("daily_budget", "lifetime_budget") if adset.get(key) is not None},
                "platform_creative_id": creative.get("id"), "creative_name": creative.get("name"),
                "title": creative.get("title"), "primary_text": creative.get("body"),
                "image_url": creative.get("image_url"), "thumbnail_url": creative.get("thumbnail_url"),
                "landing_url": creative.get("object_url"), "call_to_action": creative.get("call_to_action_type"),
                "creative_raw": creative, "status": ad.get("effective_status", "UNKNOWN"),
                "currency": self.account.extra_data.get("currency", ""),
                "metrics_available": False,
            })
        by_id = {item["platform_ad_id"]: item for item in inventory}
        # Historical Insights can reference deleted ads absent from /ads.
        # Preserve those rows rather than intersecting with current inventory.
        return inventory + [{**by_id.get(row["ad_id"], {}), **row,
            "metrics_available": True,
            "allow_estimated_conversion_value": False,
            "actions": _distinct_actions(row.get("actions")),
            "action_values": _distinct_actions(row.get("action_values")),
            "platform_ad_id": row["ad_id"], "name": row.get("ad_name"),
            "platform_campaign_id": row["campaign_id"], "platform_adgroup_id": row["adset_id"],
            "adgroup_name": row.get("adset_name"), "date": row["date_start"],
            "status": metadata.get(row["ad_id"], {}).get("effective_status", "UNKNOWN"),
            "campaign_status": metadata.get(row["ad_id"], {}).get("campaign", {}).get("status", "UNKNOWN"),
            "adgroup_status": metadata.get(row["ad_id"], {}).get("adset", {}).get("status", "UNKNOWN"),
            "currency": row.get("account_currency") or self.account.extra_data.get("currency", ""),
        } for row in rows]


def save_campaign_inventory(account, rows):
    from django.utils.dateparse import parse_datetime
    from core.models import Campaign
    from core.services.v2_ad_sync import normalize_status
    for row in rows:
        defaults = {
            "user": account.user, "platform_connection": account.connection,
            "name": row.get("name") or row["id"], "status": normalize_status(row.get("status")),
            "objective": row.get("objective") or "UNKNOWN",
            "currency": account.extra_data.get("currency") or "TRY",
            "raw_data": row, "last_synced_at": timezone.now(),
            "is_active": row.get("status") == "ACTIVE",
            "start_time": parse_datetime(row["start_time"]) if row.get("start_time") else None,
            "end_time": parse_datetime(row["stop_time"]) if row.get("stop_time") else None,
        }
        for key in ("daily_budget", "lifetime_budget"):
            if key in row:
                defaults[key] = Decimal(str(row[key])) / 100 if row[key] is not None else None
        Campaign.objects.update_or_create(platform_account=account, platform_campaign_id=row["id"], defaults=defaults)

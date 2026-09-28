from .base import BasePlatformAPI
from datetime import timedelta
import json
from django.utils import timezone
from core.services.ads_integrations import account_token, meta_rows


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
    def get_ads(self, since_days=30):
        end = timezone.localdate()
        start = end - timedelta(days=max(1, min(int(since_days), 365)) - 1)
        token = account_token(self.account)
        metadata = {row["id"]: row for row in meta_rows(token, f"{self.account.account_id}/ads", {
            "fields": "id,name,effective_status,campaign{id,name,status},adset{id,name,status}",
        })}
        rows = meta_rows(token, f"{self.account.account_id}/insights", {
            "level": "ad", "time_increment": 1,
            "fields": "ad_id,ad_name,campaign_id,campaign_name,adset_id,adset_name,date_start,impressions,reach,clicks,spend,actions,action_values,account_currency",
            "time_range": json.dumps({"since": start.isoformat(), "until": end.isoformat()}),
        })
        return [{**row,
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

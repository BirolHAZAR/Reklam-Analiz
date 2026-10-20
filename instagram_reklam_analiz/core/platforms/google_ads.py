from .base import BasePlatformAPI
from datetime import timedelta
from core.services.ads_integrations import account_token, account_today, google_search, google_metrics
from core.services.ad_eligibility import is_current_campaign


class GoogleAdsAPI(BasePlatformAPI):
    def get_report_data(self, since_days=30):
        inventory = self.get_campaigns(include_history=True)
        metrics = self.get_campaign_metrics(since_days, inventory, include_history=True)
        ids = {row["platform_campaign_id"] for row in metrics}
        return inventory, self.get_ads(since_days, include_history=True, campaign_ids=ids), metrics

    def get_campaign_metrics(self, since_days=30, campaign_inventory=None, include_history=False):
        campaigns = self.get_campaigns() if campaign_inventory is None else campaign_inventory
        ids = {str(row["campaign"]["id"]) for row in campaigns}
        if not ids:
            return []
        end = account_today(self.account)
        start = end - timedelta(days=max(1, min(int(since_days), 365)) - 1)
        rows = google_search(account_token(self.account), self.account.account_id,
            "SELECT campaign.id, segments.date, metrics.impressions, metrics.clicks, metrics.cost_micros, "
            "metrics.conversions, metrics.conversions_value FROM campaign WHERE "
            + ("" if include_history else "campaign.status = 'ENABLED' AND ")
            + f"segments.date BETWEEN '{start}' AND '{end}'", self.account.extra_data.get("login_customer_id", ""))
        return [{"platform_campaign_id": str(row["campaign"]["id"]), "date": row["segments"]["date"],
            **{key: str(value) for key, value in google_metrics(row["metrics"]).items()},
            "currency": self.account.extra_data.get("currency", "TRY"), "allow_estimated_conversion_value": False}
            for row in rows if str(row["campaign"]["id"]) in ids and row.get("segments") and row.get("metrics")]

    def get_campaigns(self, include_history=False):
        rows = google_search(account_token(self.account), self.account.account_id,
            "SELECT campaign.id, campaign.name, campaign.status, campaign.advertising_channel_type, "
            "campaign.start_date_time, campaign.end_date_time, campaign_budget.amount_micros "
            "FROM campaign" + ("" if include_history else " WHERE campaign.status = 'ENABLED'"),
            self.account.extra_data.get("login_customer_id", ""))
        return rows if include_history else [row for row in rows if is_current_campaign(row["campaign"], today=account_today(self.account),
                    zone=self.account.extra_data.get("timezone") or "UTC")]

    def get_ads(self, since_days=30, include_history=False, campaign_ids=None):
        end = account_today(self.account)
        start = end - timedelta(days=max(1, min(int(since_days), 365)) - 1)
        token = account_token(self.account)
        manager = self.account.extra_data.get("login_customer_id", "")
        fields = ("campaign.id, campaign.name, campaign.status, campaign.start_date_time, campaign.end_date_time, "
                  "ad_group.id, ad_group.name, ad_group.status, "
                  "ad_group_ad.ad.id, ad_group_ad.ad.name, ad_group_ad.status")
        active = ("campaign.status = 'ENABLED' AND ad_group.status = 'ENABLED' "
                  "AND ad_group_ad.status = 'ENABLED'")
        if include_history:
            if not campaign_ids:
                return []
            if any(not str(value).isdigit() for value in campaign_ids):
                raise ValueError("Geçersiz kampanya kimliği")
            active = f"campaign.id IN ({','.join(sorted(campaign_ids))})"
        inventory_rows = google_search(token, self.account.account_id,
            f"SELECT {fields} FROM ad_group_ad WHERE {active}", manager)
        inventory = {}
        for row in inventory_rows:
            if not include_history and (not is_current_campaign(row["campaign"], today=end, zone=self.account.extra_data.get("timezone") or "UTC")
                    or row["adGroup"].get("status") != "ENABLED"
                    or row["adGroupAd"].get("status") != "ENABLED"):
                continue
            item = {
                "platform_ad_id": str(row["adGroupAd"]["ad"]["id"]),
                "name": row["adGroupAd"]["ad"].get("name") or str(row["adGroupAd"]["ad"]["id"]),
                "status": row["adGroupAd"]["status"],
                "platform_campaign_id": str(row["campaign"]["id"]), "campaign_name": row["campaign"]["name"],
                "campaign_status": row["campaign"]["status"], "campaign_raw": row["campaign"],
                "platform_adgroup_id": str(row["adGroup"]["id"]), "adgroup_name": row["adGroup"]["name"],
                "adgroup_status": row["adGroup"]["status"],
                "currency": self.account.extra_data.get("currency", ""), "metrics_available": False,
            }
            inventory[item["platform_ad_id"]] = item
        if not inventory:
            return []
        rows = google_search(token, self.account.account_id,
            f"SELECT {fields}, segments.date, "
            "metrics.impressions, metrics.clicks, metrics.cost_micros, metrics.conversions, metrics.conversions_value "
            f"FROM ad_group_ad WHERE {active} AND segments.date BETWEEN '{start}' AND '{end}'", manager)
        return list(inventory.values()) + [{
            **inventory[str(row["adGroupAd"]["ad"]["id"])],
            "metrics_available": True, "date": row["segments"]["date"],
            "allow_estimated_conversion_value": False,
            **{key: str(value) for key, value in google_metrics(row.get("metrics", {})).items()},
        } for row in rows if str(row["adGroupAd"]["ad"]["id"]) in inventory
            and str(row["campaign"]["id"]) == inventory[str(row["adGroupAd"]["ad"]["id"])]["platform_campaign_id"]]


def save_campaign_inventory(account, rows):
    from decimal import Decimal
    from django.utils import timezone
    from django.utils.dateparse import parse_datetime
    from core.models import Campaign
    for row in rows:
        c = row["campaign"]
        def stamp(key):
            value = parse_datetime(c.get(key) or "")
            if value and timezone.is_naive(value):
                from zoneinfo import ZoneInfo
                value = timezone.make_aware(value, ZoneInfo(account.extra_data.get("timezone") or "UTC"))
            return value
        Campaign.objects.update_or_create(platform_account=account, platform_campaign_id=str(c["id"]), defaults={
            "user": account.user, "platform_connection": account.connection,
            "name": c["name"], "status": "ACTIVE" if c.get("status") == "ENABLED" else "PAUSED",
            "is_active": c.get("status") == "ENABLED",
            "objective": c.get("advertisingChannelType") or "UNKNOWN",
            "start_time": stamp("startDateTime"), "end_time": stamp("endDateTime"),
            "daily_budget": Decimal(str(row.get("campaignBudget", {}).get("amountMicros", 0))) / 1000000,
            "currency": account.extra_data.get("currency") or "TRY", "raw_data": c,
            "last_synced_at": timezone.now(),
        })

from .base import BasePlatformAPI
from datetime import timedelta
from core.services.ads_integrations import account_token, account_today, google_search, google_metrics


class GoogleAdsAPI(BasePlatformAPI):
    def get_ads(self, since_days=30):
        end = account_today(self.account)
        start = end - timedelta(days=max(1, min(int(since_days), 365)) - 1)
        rows = google_search(account_token(self.account), self.account.account_id,
            "SELECT campaign.id, campaign.name, campaign.status, ad_group.id, ad_group.name, "
            "ad_group_ad.ad.id, ad_group_ad.ad.name, ad_group_ad.status, segments.date, "
            "metrics.impressions, metrics.clicks, metrics.cost_micros, metrics.conversions, metrics.conversions_value "
            f"FROM ad_group_ad WHERE segments.date BETWEEN '{start}' AND '{end}'",
            self.account.extra_data.get("login_customer_id", ""))
        return [{
            "platform_ad_id": str(row["adGroupAd"]["ad"]["id"]),
            "name": row["adGroupAd"]["ad"].get("name") or str(row["adGroupAd"]["ad"]["id"]),
            "status": row["adGroupAd"]["status"],
            "platform_campaign_id": str(row["campaign"]["id"]), "campaign_name": row["campaign"]["name"],
            "campaign_status": row["campaign"]["status"],
            "platform_adgroup_id": str(row["adGroup"]["id"]), "adgroup_name": row["adGroup"]["name"],
            "date": row["segments"]["date"], "currency": self.account.extra_data.get("currency", ""),
            "allow_estimated_conversion_value": False,
            **{key: str(value) for key, value in google_metrics(row.get("metrics", {})).items()},
        } for row in rows]

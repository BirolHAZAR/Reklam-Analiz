from datetime import datetime

from core.services.ads_integrations import IntegrationError, configuration
from core.services.google_read_oauth import connection_token, request


class GoogleAnalyticsAPI:
    DAILY = {
        "sessions": "sessions", "activeUsers": "users", "newUsers": "new_users",
        "engagedSessions": "engaged_sessions", "engagementRate": "engagement_rate",
        "bounceRate": "bounce_rate",
        "screenPageViews": "screen_page_views", "eventCount": "event_count",
        "keyEvents": "key_events", "totalRevenue": "total_revenue",
    }
    LANDING = {name: field for name, field in DAILY.items() if name in {
        "sessions", "activeUsers", "newUsers", "engagedSessions", "engagementRate",
        "bounceRate", "keyEvents", "totalRevenue",
    }}

    def __init__(self, account):
        self.account = account
        self.connection = account.connection
        if not self.connection or not self.connection.is_active or self.connection.extra_data.get("source") != "google_read_oauth":
            raise IntegrationError("GA4 mülkünü Google hesabınızla yeniden bağlayın.")
        self.quota_key = configuration("google_analytics")[0] + ":" + account.account_id

    def _request(self, method, url, **kwargs):
        return request(method, url, quota_key=self.quota_key,
                       headers={"Authorization": f"Bearer {connection_token(self.connection)}"}, **kwargs)

    def _property_id(self, property_id):
        if str(property_id) != self.account.account_id or not str(property_id).isdigit():
            raise IntegrationError("Bağlı GA4 mülkünü seçin.")
        return str(property_id)

    def get_properties(self):
        pid = self._property_id(self.account.account_id)
        data = self._request("GET", f"https://analyticsadmin.googleapis.com/v1beta/properties/{pid}")
        return [{"property_id": pid, "property_name": data.get("displayName", self.account.account_name),
                 "property_type": "GA4", "currency": data.get("currencyCode", "TRY"), "timezone": data.get("timeZone")}]

    def _report(self, property_id, dimensions, metrics, since_days):
        pid = self._property_id(property_id)
        days = max(1, min(365, int(since_days)))
        result, offset = [], 0
        for _ in range(100):
            data = self._request("POST", f"https://analyticsdata.googleapis.com/v1beta/properties/{pid}:runReport", json={
                "dateRanges": [{"startDate": f"{days}daysAgo", "endDate": "yesterday"}],
                "dimensions": [{"name": name} for name in dimensions],
                "metrics": [{"name": name} for name in metrics],
                "limit": 10000, "offset": offset,
                "orderBys": [{"dimension": {"dimensionName": name}} for name in dimensions],
                "returnPropertyQuota": True,
            })
            rows = data.get("rows", [])
            for row in rows:
                dims = {name: value["value"] for name, value in zip(dimensions, row["dimensionValues"])}
                item = {field: value["value"] for field, value in zip(metrics.values(), row["metricValues"])}
                item["date"] = datetime.strptime(dims["date"], "%Y%m%d").date().isoformat()
                item["conversions"] = item.get("key_events", "0")
                if "landingPagePlusQueryString" in dims:
                    item["landing_page"] = dims["landingPagePlusQueryString"]
                result.append(item)
            offset += len(rows)
            if offset >= int(data.get("rowCount", 0)):
                return result
            if not rows:
                break
        raise IntegrationError("GA4 raporu tamamlanamadı. Daha sonra tekrar deneyin.")

    def get_daily_metrics(self, property_id, since_days=30):
        return self._report(property_id, ["date"], self.DAILY, since_days)

    def get_landing_page_metrics(self, property_id, since_days=30):
        return self._report(property_id, ["date", "landingPagePlusQueryString"], self.LANDING, since_days)

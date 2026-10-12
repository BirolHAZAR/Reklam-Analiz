"""Media Insights and lifetime snapshot summaries; missing is not zero."""


def fetch_media_insights(api, media):
    names = ["views", "reach", "total_interactions", "shares"]
    if media.get("media_product_type") != "STORY":
        names.append("saved")
    response = api._request(
        f"{api.graph_url}/{media['id']}/insights",
        {"metric": ",".join(names)},
    )
    if not isinstance(response, dict) or response.get("error"):
        # Never persist provider error bodies: they can contain credentials.
        return {}, "unavailable"
    values = {}
    for row in response.get("data", []):
        if not isinstance(row, dict) or row.get("name") not in names:
            continue
        entries = row.get("values") or []
        value = entries[-1].get("value") if entries and isinstance(entries[-1], dict) else None
        if value is None and isinstance(row.get("total_value"), dict):
            value = row["total_value"].get("value")
        if isinstance(value, (int, float)) and not isinstance(value, bool) and value >= 0:
            values[row["name"]] = int(value)
    return values, "available" if values else "empty"


def summarize_snapshots(rows):
    rows = list(rows)
    result = {key: sum(getattr(row, key) for row in rows) for key in (
        "likes", "comments", "engagement",
    )}
    for field, provider_name in (("views", "views"), ("reach", "reach"),
                                 ("impressions", "impressions"), ("profile_visits", "profile_visits"),
                                 ("shares", "shares"), ("saves", "saved"),
                                 ("video_views", "video_views"), ("website_clicks", "website_clicks")):
        values = []
        for row in rows:
            insights = (row.raw_metrics or {}).get("insights", {})
            if provider_name in insights:
                values.append(insights[provider_name])
            elif field != "views" and getattr(row, field) > 0:
                values.append(getattr(row, field))
        result[field] = sum(values) if rows and len(values) == len(rows) else None
    result["latest_date"] = max((row.date for row in rows), default=None)
    result["avg_engagement_rate"] = (
        round(result["engagement"] / result["reach"] * 100, 2)
        if result["reach"] else None
    )
    result["insights_available"] = bool(rows) and all(
        (row.raw_metrics or {}).get("insights_status") == "available" for row in rows
    )
    return result

"""Choose the real read flow for each connected account."""
from django.conf import settings
from core.services.ad_sync_capabilities import supports_account_ad_sync


def account_sync_mode(account):
    code = account.platform.code
    connection = account.connection if account.connection_id else None
    source = (connection.extra_data or {}).get("source") if connection else None
    if code == "youtube":
        return "youtube" if source == "google_read_oauth" else None
    if code == "instagram":
        return "organic"
    if code == "tiktok" and source == "tiktok_oauth":
        return "organic"
    if code == "x" and source == "x_oauth":
        return "organic" if getattr(settings, "X_API_READ_ENABLED", False) else None
    return "ad" if supports_account_ad_sync(account) else None

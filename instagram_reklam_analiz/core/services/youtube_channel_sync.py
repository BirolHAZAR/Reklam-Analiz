"""Refresh the authorized YouTube channel, independently of advertising sync."""
from django.db import transaction
from django.utils import timezone
from core.models import PlatformAccount
from core.services import google_read_oauth as api
from core.services.ads_integrations import IntegrationError


def sync_youtube_channel(account):
    connection = account.connection if account.connection_id else None
    if (account.platform.code != "youtube" or not account.is_active or not connection
            or not connection.is_active or connection.user_id != account.user_id
            or connection.platform_id != account.platform_id
            or (connection.extra_data or {}).get("source") != "google_read_oauth"):
        raise IntegrationError("YouTube kanal bağlantısını yeniden kurun.")
    token = api.connection_token(connection)
    channels = api.discover_accounts("youtube", token)
    channel = next((row for row in channels if row.get("id") == account.account_id), None)
    if not channel or channel.get("kind") != "youtube_channel":
        raise IntegrationError("Bağlı YouTube kanalı bu Google yetkisinde bulunamadı. Hesabı yeniden bağlayın.")
    raw = channel.get("statistics")
    if not isinstance(raw, dict) or not {"viewCount", "videoCount"} <= raw.keys():
        raise IntegrationError("YouTube kanal sayaçları doğrulanamadı.")
    statistics = {}
    for key in ("viewCount", "subscriberCount", "videoCount"):
        if key in raw:
            value = raw[key]
            if not isinstance(value, str) or not value.isascii() or not value.isdigit() or len(value) > 20:
                raise IntegrationError("YouTube kanal sayaçları doğrulanamadı.")
            statistics[key] = int(value)
    if "hiddenSubscriberCount" in raw:
        if type(raw["hiddenSubscriberCount"]) is not bool:
            raise IntegrationError("YouTube abone görünürlüğü doğrulanamadı.")
        statistics["hiddenSubscriberCount"] = raw["hiddenSubscriberCount"]
    now = timezone.now()
    with transaction.atomic():
        fresh = PlatformAccount.objects.select_for_update().get(pk=account.pk)
        if not fresh.is_active or fresh.connection_id != connection.pk:
            raise IntegrationError("YouTube bağlantısı değişti. Yeniden deneyin.")
        fresh.extra_data = {**(fresh.extra_data or {}), "youtube_channel_statistics": statistics,
                            "organic_last_sync_at": now.isoformat()}
        fresh.last_sync = now
        fresh.save(update_fields=["extra_data", "last_sync", "updated_at"])
    return {"success": True, "channel_synced": True, "created": 0, "updated": 1, "metrics": len(statistics)}

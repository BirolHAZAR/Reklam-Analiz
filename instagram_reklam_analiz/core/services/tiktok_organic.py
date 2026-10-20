"""Read-only public video import. Missing counters never become zero data."""
from datetime import datetime, timezone as datetime_timezone

from django.db import transaction
from django.utils import timezone

from core.models import PlatformAccount, SocialPost, SocialPostMetricHistory
from core.services import tiktok_oauth
from core.services.ads_integrations import IntegrationError
from core.services.demo_policy import is_demo_object, demo_skip_result


def sync_tiktok_organic_content(account, *, limit=50):
    if is_demo_object(account):
        return demo_skip_result()
    empty = {"success": False, "created": 0, "updated": 0, "metrics": 0}
    if not account or account.platform.code != "tiktok" or not account.connection_id:
        return {**empty, "error": "TikTok organik hesabı bulunamadı."}
    try:
        token = tiktok_oauth.access_token(account)
        rows, seen_ids, seen_cursors = [], set(), set()
        cursor = None
        record_limit = max(1, int(limit))
        now = timezone.now()
        for _ in range(100):
            videos, next_cursor = tiktok_oauth.videos(token, cursor)
            for video in videos:
                video_id = video.get("id")
                timestamp = video.get("create_time")
                if (not isinstance(video_id, str) or not video_id or len(video_id) > 255
                        or video_id in seen_ids or not isinstance(timestamp, int)
                        or isinstance(timestamp, bool)):
                    raise IntegrationError("TikTok video kimliği veya tarihi doğrulanamadı.")
                seen_ids.add(video_id)
                try:
                    posted_at = datetime.fromtimestamp(timestamp, datetime_timezone.utc)
                except (ValueError, OverflowError, OSError):
                    raise IntegrationError("TikTok video tarihi doğrulanamadı.") from None
                if timestamp <= 0 or posted_at > now:
                    raise IntegrationError("TikTok video tarihi doğrulanamadı.")
                # All four counters are requested together. Reject incomplete
                # payloads before writing any posts or snapshots.
                counts = {}
                for field in ("view_count", "like_count", "comment_count", "share_count"):
                    value = video.get(field)
                    if not isinstance(value, int) or isinstance(value, bool) or not 0 <= value < 2**63:
                        raise IntegrationError("TikTok video metrikleri eksik; hiçbir içerik kaydedilmedi.")
                    counts[field] = value
                rows.append((video, posted_at, counts))
                if len(rows) > record_limit:
                    raise IntegrationError("TikTok videoları planın kayıt sınırını aşıyor.")
            if next_cursor is None:
                break
            if next_cursor in seen_cursors or not videos:
                raise IntegrationError("TikTok video sayfalaması tamamlanamadı.")
            seen_cursors.add(next_cursor)
            cursor = next_cursor
        else:
            raise IntegrationError("TikTok video tarama sınırı aşıldı.")
        created = 0
        with transaction.atomic():
            # Serialize same-account imports; SocialPost has no unique key.
            locked = PlatformAccount.objects.select_for_update().get(pk=account.pk)
            if not locked.is_active or locked.connection_id != account.connection_id:
                raise IntegrationError("TikTok hesap bağlantısı değişti. Yeniden deneyin.")
            for video, posted_at, counts in rows:
                post, was_created = SocialPost.objects.update_or_create(
                    user=account.user, platform_account=account, platform_post_id=video["id"],
                    defaults={"platform_connection": account.connection, "post_type": "VIDEO",
                              "caption": video.get("video_description") or video.get("title") or "",
                              "permalink": video.get("share_url") or None,
                              "thumbnail_url": video.get("cover_image_url") or None,
                              "posted_at": posted_at, "last_synced_at": now, "is_active": True,
                              "raw_data": {"source": "tiktok_video_sync", "status": "synced", "raw": video}},
                )
                created += int(was_created)
                likes, comments, shares = (counts[key] for key in ("like_count", "comment_count", "share_count"))
                engagement = likes + comments + shares
                SocialPostMetricHistory.objects.update_or_create(
                    social_post=post, date=timezone.localdate(now), defaults={
                        "likes": likes, "comments": comments, "shares": shares,
                        "video_views": counts["view_count"], "engagement": engagement,
                        "raw_metrics": {"provider": "tiktok_display", "synced_at": now.isoformat(),
                                        "insights_status": "available", "insights": {
                                            "views": counts["view_count"], "video_views": counts["view_count"],
                                            "likes": likes, "comments": comments, "shares": shares,
                                            "total_interactions": engagement}},
                    },
                )
            locked.last_sync = now
            locked.extra_data = {**(locked.extra_data or {}), "organic_last_sync_at": now.isoformat(),
                                 "organic_synced_posts": len(rows)}
            locked.save(update_fields=["last_sync", "extra_data", "updated_at"])
        return {"success": True, "created": created, "updated": len(rows) - created,
                "metrics": len(rows), "fetched": len(rows), "insights_available": len(rows),
                "insights_unavailable": 0}
    except IntegrationError as exc:
        return {**empty, "error": str(exc)}

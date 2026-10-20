from __future__ import annotations

from datetime import timedelta
from decimal import Decimal

from django.db.models import Avg, Count, Max, Sum, OuterRef, Subquery
from django.utils import timezone

from core.instagram_api import InstagramAPI
from core.models import PlatformAccount, SocialPost, SocialPostMetricHistory
from core.services.organic_publish import can_publish_post


READY_PLATFORM_CODES = {"instagram", "tiktok"}
ORGANIC_SYNC_SOURCES = ("instagram_media_sync", "tiktok_video_sync")


def sync_organic_content(account, *, limit=50):
    if getattr(account.platform, "code", "") == "tiktok":
        from core.services.tiktok_organic import sync_tiktok_organic_content
        return sync_tiktok_organic_content(account, limit=limit)
    return sync_instagram_organic_content(account, limit=limit)



def post_status(post: SocialPost) -> str:
    raw_status = (post.raw_data or {}).get("status")
    if raw_status:
        return str(raw_status)
    if post.posted_at:
        return "published"
    return "draft"


def post_status_label(status: str, labels: dict | None = None) -> str:
    labels = labels or {}
    return {
        "draft": labels.get("draft", "Taslak"),
        "scheduled": labels.get("status_scheduled", "Yayin kuyrugunda"),
        "published": labels.get("status_published", "Platforma gonderildi"),
        "synced": labels.get("status_synced", "Yayinda / senkronize"),
        "failed": labels.get("status_failed", "Yayin hatasi"),
    }.get(status, labels.get("draft", "Taslak"))


def post_status_class(status: str) -> str:
    return {
        "draft": "draft",
        "scheduled": "queued",
        "published": "published",
        "synced": "published",
        "failed": "failed",
    }.get(status, "draft")


def post_status_note(post: SocialPost, status: str, labels: dict | None = None) -> str:
    labels = labels or {}
    raw = post.raw_data or {}
    if status in {"published", "synced"}:
        sent_at = raw.get("published_at")
        return (
            labels.get("status_note_published_at", "Icerik platforma gonderildi ve performans takibine alindi.")
            if sent_at
            else labels.get("status_note_live", "Icerik yayinda olarak takip ediliyor.")
        )
    if status == "scheduled":
        scheduled_at = raw.get("scheduled_at")
        if scheduled_at:
            return f"{labels.get('status_note_scheduled_prefix', 'Planlanan yayin zamani')}: {scheduled_at}"
        return labels.get("status_note_scheduled", "Icerik yayin kuyrugunda bekliyor.")
    if status == "failed":
        return raw.get("error_message") or labels.get(
            "status_note_failed",
            "Platform yayini tamamlanamadi; baglanti ve izinleri kontrol et.",
        )
    if raw.get("source") == "creative_studio":
        return labels.get(
            "status_note_creative",
            "Creative Studio'dan aktarildi; yayin icin hesap ve izin durumu hazir olmali.",
        )
    return labels.get("status_note_draft", "Yayinlanmamis taslak.")


def is_publish_ready(post: SocialPost) -> bool:
    ready, _ = can_publish_post(post)
    return ready


def decorate_posts(posts, *, labels: dict | None = None):
    for post in posts:
        status = post_status(post)
        post.organic_status = status
        post.organic_status_label = post_status_label(status, labels)
        post.organic_status_class = post_status_class(status)
        post.organic_status_note = post_status_note(post, status, labels)
        post.organic_publish_ready = is_publish_ready(post)
        _, publish_block_reason = can_publish_post(post)
        post.organic_publish_block_reason = publish_block_reason
        post.organic_scheduled_at = (post.raw_data or {}).get("scheduled_at")
    return posts



def organic_summary_for_user(user, *, start_date=None, end_date=None, days: int = 30, platform_accounts=None) -> dict:
    today = timezone.localdate()
    if end_date is None:
        end_date = today
    if start_date is None:
        start_date = end_date - timedelta(days=days)

    if platform_accounts is None:
        posts = SocialPost.objects.filter(user=user)
        metrics = SocialPostMetricHistory.objects.filter(social_post__user=user)
    else:
        posts = SocialPost.objects.filter(platform_account__in=platform_accounts)
        metrics = SocialPostMetricHistory.objects.filter(social_post__platform_account__in=platform_accounts)
    metrics = metrics.filter(date__gte=start_date, date__lte=end_date)
    # Instagram returns lifetime counters. The same post's counters on two
    # dates are snapshots, not two additive days of engagement.
    from core.services.organic_insights import summarize_snapshots
    latest = metrics.filter(social_post_id=OuterRef("social_post_id")).order_by("-date").values("pk")[:1]
    totals = summarize_snapshots(metrics.filter(pk=Subquery(latest)))
    status_counts = {"draft": 0, "scheduled": 0, "published": 0, "synced": 0}
    for status in posts.values_list("raw_data__status", flat=True):
        key = status or "draft"
        status_counts[key] = status_counts.get(key, 0) + 1

    published_count = posts.filter(posted_at__isnull=False).count()
    total_posts = posts.count()
    engagement = totals.get("engagement") or 0
    reach = totals.get("reach") or 0

    return {
        "start_date": start_date,
        "end_date": end_date,
        "total_posts": total_posts,
        "active_posts": posts.filter(is_active=True).count(),
        "draft_posts": status_counts.get("draft", 0),
        "scheduled_posts": status_counts.get("scheduled", 0),
        "published_posts": published_count,
        "synced_posts": status_counts.get("synced", 0),
        "impressions": totals.get("impressions"),
        "reach": totals.get("reach"),
        "engagement": engagement,
        "likes": totals.get("likes") or 0,
        "comments": totals.get("comments") or 0,
        "shares": totals.get("shares"),
        "saves": totals.get("saves"),
        "video_views": totals.get("video_views"),
        "profile_visits": totals.get("profile_visits"),
        "website_clicks": totals.get("website_clicks"),
        "avg_engagement_rate": totals.get("avg_engagement_rate"),
        "latest_date": totals.get("latest_date"),
        "engagement_per_post": round(engagement / total_posts, 2) if total_posts else 0,
        "reach_per_post": round(reach / published_count, 2) if published_count else 0,
    }


def organic_type_breakdown(user, *, limit: int = 6):
    return (
        SocialPost.objects.filter(user=user)
        .values("post_type")
        .annotate(total=Count("id"))
        .order_by("-total")[:limit]
    )


def _parse_instagram_timestamp(value):
    if not value:
        return None
    try:
        parsed = timezone.datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except ValueError:
        return None
    if timezone.is_naive(parsed):
        return timezone.make_aware(parsed)
    return parsed


def _post_type_from_media(media):
    media_type = str((media or {}).get("media_type") or "").upper()
    if media_type == "VIDEO":
        return "VIDEO"
    if media_type == "CAROUSEL_ALBUM":
        return "CAROUSEL"
    if media_type == "IMAGE":
        return "IMAGE"
    return "UNKNOWN"


def sync_instagram_organic_content(account: PlatformAccount, *, limit: int = 50, lookback_days: int = 15) -> dict:
    from core.services.demo_policy import is_demo_object, demo_skip_result
    if is_demo_object(account):
        return demo_skip_result()
    if not account or getattr(account.platform, "code", "") != "instagram":
        return {"success": False, "created": 0, "updated": 0, "metrics": 0, "error": "Instagram hesabi bulunamadi."}

    token = getattr(account, "access_token", "") or getattr(getattr(account, "connection", None), "access_token", "") or ""
    instagram_business_id = (account.extra_data or {}).get("instagram_business_account_id") or account.account_id
    if not token or not instagram_business_id:
        return {"success": False, "created": 0, "updated": 0, "metrics": 0, "error": "Instagram token veya business id eksik."}

    api = InstagramAPI(access_token=token, instagram_login=(account.extra_data or {}).get("auth_type") == "instagram_login")
    now = timezone.now()
    cutoff = now - timedelta(days=max(1, int(lookback_days)))
    page_size = min(100, max(1, int(limit or 50)))
    params = {
            "fields": "id,caption,media_type,media_product_type,media_url,thumbnail_url,permalink,timestamp,like_count,comments_count",
            "limit": page_size,
    }
    media_rows, seen_ids, seen_cursors = [], set(), set()
    # Fixed endpoint + opaque cursor: never follow a provider URL containing
    # credentials. Old post metadata is ignored; only recent posts get Insights.
    for _ in range(100):
        response = api._request(f"{api.graph_url}/{instagram_business_id}/media", dict(params))
        if not isinstance(response, dict) or response.get("error") or not isinstance(response.get("data"), list):
            return {"success": False, "created": 0, "updated": 0, "metrics": 0,
                    "error": "Instagram gönderileri eksiksiz okunamadı."}
        dates = []
        for media in response["data"]:
            posted_at = _parse_instagram_timestamp(media.get("timestamp"))
            if posted_at:
                dates.append(posted_at)
            media_id = str(media.get("id") or "")
            if not posted_at or not cutoff <= posted_at <= now or not media_id or media_id in seen_ids:
                continue
            seen_ids.add(media_id)
            media_rows.append(media)
        paging = response.get("paging") or {}
        if not paging.get("next") or (dates and max(dates) < cutoff):
            break
        cursor = (paging.get("cursors") or {}).get("after")
        if not cursor or cursor in seen_cursors:
            return {"success": False, "created": 0, "updated": 0, "metrics": 0,
                    "error": "Instagram sayfalaması tamamlanamadı."}
        seen_cursors.add(cursor)
        params["after"] = cursor
    else:
        return {"success": False, "created": 0, "updated": 0, "metrics": 0,
                "error": "Instagram gönderi taraması sınırı aşıldı."}
    if len(media_rows) > max(1, int(limit or 50)):
        return {"success": False, "created": 0, "updated": 0, "metrics": 0,
                "error": "Son 15 gündeki gönderiler planın kayıt sınırını aşıyor."}

    created = 0
    updated = 0
    metrics = 0
    insights_count = 0
    for media in media_rows:
        media_id = str(media.get("id") or "").strip()
        if not media_id:
            continue
        media_type = _post_type_from_media(media)
        media_url = media.get("media_url") or ""
        thumbnail_url = media.get("thumbnail_url") or media_url
        posted_at = _parse_instagram_timestamp(media.get("timestamp"))

        post, was_created = SocialPost.objects.update_or_create(
            user=account.user,
            platform_account=account,
            platform_post_id=media_id,
            defaults={
                "platform_connection": account.connection,
                "post_type": media_type,
                "caption": media.get("caption") or "",
                "permalink": media.get("permalink") or None,
                "image_url": media_url if media_type in {"IMAGE", "CAROUSEL", "UNKNOWN"} else None,
                "video_url": media_url if media_type == "VIDEO" else None,
                "thumbnail_url": thumbnail_url or None,
                "posted_at": posted_at,
                "raw_data": {
                    "status": "synced",
                    "source": "instagram_media_sync",
                    "instagram_business_account_id": instagram_business_id,
                    "raw": media,
                },
                "last_synced_at": now,
                "is_active": True,
            },
        )
        if was_created:
            created += 1
        else:
            updated += 1

        # Metrik geçmişi paylaşım tarihini değil snapshot tarihini tutar. Böylece
        # eski bir gönderinin bugün güncellenen beğenisi seçili dönemde görünür.
        metric_date = timezone.localdate(now)
        likes = int(media.get("like_count") or 0)
        comments = int(media.get("comments_count") or 0)
        from core.services.organic_insights import fetch_media_insights
        insights, insights_status = fetch_media_insights(api, media)
        insights_count += int(insights_status == "available")
        engagement = insights.get("total_interactions", likes + comments)
        SocialPostMetricHistory.objects.update_or_create(
            social_post=post,
            date=metric_date,
            defaults={
                "likes": likes,
                "comments": comments,
                "engagement": engagement,
                "reach": insights.get("reach", 0),
                "shares": insights.get("shares", 0),
                "saves": insights.get("saved", 0),
                "engagement_rate": (Decimal(engagement) / Decimal(insights["reach"]) * 100
                                    if insights.get("reach") else Decimal("0")),
                "raw_metrics": {
                    "provider": "instagram_graph",
                    "like_count": likes,
                    "comments_count": comments,
                    "synced_at": now.isoformat(),
                    "insights": insights,
                    "insights_status": insights_status,
                },
            },
        )
        metrics += 1

    account.last_sync = now
    account.extra_data = {**(account.extra_data or {}), "organic_last_sync_at": now.isoformat(),
        "organic_sync_window_days": lookback_days, "organic_synced_posts": created + updated}
    account.save(update_fields=["last_sync", "extra_data", "updated_at"])
    return {"success": True, "created": created, "updated": updated, "metrics": metrics,
            "fetched": created + updated, "insights_available": insights_count,
            "insights_unavailable": metrics - insights_count}


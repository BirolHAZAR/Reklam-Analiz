from core.services.demo_policy import is_demo_object, demo_skip_result
from celery import shared_task

from core.models import Competitor
from core.services.cache_service import CacheService
from core.services.competitor_live_sync import CompetitorSyncError, sync_competitor_live
from core.services.competitor_public_sources import SUPPORTED_COMPETITOR_PLATFORMS
from django.utils import timezone
from django.db import transaction
from core.services.sync_policy import acquire_sync_lock, release_sync_lock
import logging


def queue_competitor_sync(competitor_id):
    """Persist dispatch failure so a saved competitor never silently stalls."""
    competitor = Competitor.objects.filter(pk=competitor_id, is_active=True).first()
    if not competitor or is_demo_object(competitor):
        return None
    lock_key, acquired = acquire_sync_lock("competitor-dispatch", competitor_id, timeout=1800)
    if not acquired:
        return None
    try:
        with transaction.atomic():
            competitor = Competitor.objects.select_for_update().get(pk=competitor_id)
            competitor.raw_data = {**(competitor.raw_data or {}), "last_live_sync_status": "queued",
                           "last_live_sync_error": ""}
            competitor.save(update_fields=["raw_data", "updated_at"])
        CacheService.bump_version("competitors", competitor.user_id)
        return sync_competitor_live_ads.delay(competitor_id)
    except Exception as exc:
        release_sync_lock(lock_key)
        logging.getLogger(__name__).error("Competitor sync dispatch failed id=%s error_type=%s", competitor_id, type(exc).__name__)
        competitor.refresh_from_db()
        competitor.raw_data.update(last_live_sync_status="error",
            last_live_sync_error="Reklam çekme görevi başlatılamadı. Yenile düğmesiyle tekrar deneyin.",
            last_live_sync_attempt_at=timezone.now().isoformat())
        competitor.save(update_fields=["raw_data", "updated_at"])
        CacheService.bump_version("competitors", competitor.user_id)
        return None


def _sync_competitor_live_ads(competitor_id):
    from core.services.sync_policy import policy_for_user
    competitor = (
        Competitor.objects
        .select_related("platform", "platform_account", "platform_account__connection")
        .filter(id=competitor_id, is_active=True)
        .first()
    )
    if not competitor:
        return {"success": False, "skipped": True, "reason": "competitor_not_found_or_inactive", "competitor_id": competitor_id}
    if is_demo_object(competitor):
        return demo_skip_result()
    try:
        policy = policy_for_user(competitor.user)
        if not policy and not (competitor.user.is_staff or competitor.user.is_superuser):
            competitor.raw_data = {**(competitor.raw_data or {}), "last_live_sync_status": "error",
                "last_live_sync_error": "Rakip reklam takibi için aktif abonelik gerekiyor."}
            competitor.save(update_fields=["raw_data", "updated_at"])
            CacheService.bump_version("competitors", competitor.user_id)
            return {"success": False, "skipped": True, "reason": "active_subscription_required", "competitor_id": competitor.id}
        result = sync_competitor_live(competitor, limit=policy.max_records if policy else 50)
    except CompetitorSyncError as exc:
        CacheService.bump_version("competitors", competitor.user_id)
        CacheService.bump_version("competitor_ads", competitor.user_id, competitor.id)
        return {
            "success": False,
            "skipped": True,
            "reason": str(exc),
            "competitor_id": competitor.id,
            "platform": competitor.platform.code if competitor.platform else "unknown",
        }
    except Exception as exc:
        logging.getLogger(__name__).error("Competitor sync task failed id=%s error_type=%s", competitor_id, type(exc).__name__)
        competitor.refresh_from_db()
        competitor.raw_data = {**(competitor.raw_data or {}), "last_live_sync_status": "error",
            "last_live_sync_error": "Rakip reklam çekimi tamamlanamadı. Yeniden deneyin.",
            "last_live_sync_attempt_at": timezone.now().isoformat()}
        competitor.save(update_fields=["raw_data", "updated_at"])
        CacheService.bump_version("competitors", competitor.user_id)
        return {"success": False, "reason": competitor.raw_data["last_live_sync_error"], "competitor_id": competitor_id}
    CacheService.bump_version("competitors", competitor.user_id)
    CacheService.bump_version("competitor_ads", competitor.user_id, competitor.id)
    CacheService.bump_version("competitor_movements", competitor.user_id)
    CacheService.bump_version("competitor_intelligence", competitor.user_id)
    return {"success": True, "competitor_id": competitor.id, **result}


@shared_task(name="core.tasks.competitor_sync.sync_competitor_live_ads")
def sync_competitor_live_ads(competitor_id):
    try:
        return _sync_competitor_live_ads(competitor_id)
    finally:
        release_sync_lock(f"sync-lock:competitor-dispatch:{competitor_id}")


@shared_task(name="core.tasks.competitor_sync.sync_all_live_competitors")
def sync_all_live_competitors():
    from core.services.sync_policy import is_sync_due
    competitors = (
        Competitor.objects
        .select_related("platform")
        .filter(is_active=True, platform__code__in=SUPPORTED_COMPETITOR_PLATFORMS)
        .order_by("id")
    )
    results = []
    for competitor in competitors:
        if is_demo_object(competitor):
            continue
        last_sync = (competitor.raw_data or {}).get("last_live_sync_at")
        if not is_sync_due(competitor.user, last_sync, kind="competitor"):
            continue
        async_result = queue_competitor_sync(competitor.id)
        if not async_result:
            continue
        results.append({
            "competitor_id": competitor.id,
            "platform": competitor.platform.code if competitor.platform else "unknown",
            "task_id": async_result.id,
        })
    return {"queued": len(results), "items": results}

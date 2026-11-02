import logging
from celery import shared_task
from django.utils import timezone
from django.db import transaction
from core.models import PlatformSyncJob
from core.services.account_sync import account_sync_mode
from core.services.sync_policy import manual_sync_allowed, policy_for_user

logger = logging.getLogger(__name__)


@shared_task
def sync_account_read_job(job_id):
    with transaction.atomic():
        job = PlatformSyncJob.objects.select_for_update().get(pk=job_id)
        if job.status != "pending":
            return
        job.status, job.started_at, job.progress = "running", timezone.now(), 10
        job.message, job.error_message = "Hesap verileri yenileniyor...", ""
        job.save(update_fields=["status", "started_at", "progress", "message", "error_message", "updated_at"])
    account = job.platform_account
    try:
        if (not account.is_active or account.user_id != job.user_id
                or not manual_sync_allowed(job.user, "organic")):
            raise ValueError("Account sync no longer permitted")
        mode = account_sync_mode(account)
        if mode == "youtube":
            from core.services.youtube_channel_sync import sync_youtube_channel
            result = sync_youtube_channel(account)
        elif mode == "organic":
            from core.services.organic_content_service import sync_organic_content
            policy = policy_for_user(job.user)
            result = sync_organic_content(account, limit=policy.max_records if policy else 50)
        else:
            raise ValueError("Unsupported account read")
        if not result.get("success"):
            raise ValueError("Provider read did not complete")
        job.status, job.progress, job.message = "completed", 100, "Hesap verileri güncellendi."
        job.result = {key: result[key] for key in ("created", "updated", "metrics", "channel_synced") if key in result}
        from core.services.cache_service import CacheService
        for area in ("dashboard", "control_tower", "reports_center", "health_center", "organic_content"):
            CacheService.bump_version(area, job.user_id)
    except Exception as exc:
        logger.warning("Account read sync failed account=%s exception_type=%s", account.pk, type(exc).__name__)
        job.status, job.message = "failed", "Hesap verileri yenilenemedi. Bağlantıyı ve okuma izinlerini kontrol edin."
        job.error_message = job.message
    job.finished_at = timezone.now()
    job.save(update_fields=["status", "progress", "message", "error_message", "result", "finished_at", "updated_at"])

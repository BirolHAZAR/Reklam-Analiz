from core.services.demo_policy import is_demo_object
from celery import shared_task
from django.utils import timezone
import logging

from core.services.v2_ad_sync import upsert_v2_ad_snapshot
from core.services.ad_sync_capabilities import SUPPORTED_AD_SYNC_PLATFORMS, ad_sync_unavailable_message

logger = logging.getLogger(__name__)


PLATFORM_ALIASES = {
    # Meta / Facebook / Instagram
    "meta": "facebook",
    "facebook": "facebook",
    "fb": "facebook",
    "instagram": "instagram",
    "ig": "instagram",

    # TikTok
    "tiktok": "tiktok",
    "tik_tok": "tiktok",
    "tik tok": "tiktok",

    # Google
    "google": "google_ads",
    "googleads": "google_ads",
    "google_ads": "google_ads",
    "google ads": "google_ads",
    "adwords": "google_ads",

    # LinkedIn
    "linkedin": "linkedin",
    "linked_in": "linkedin",
    "linked in": "linkedin",

    # X / Twitter
    "x": "x",
    "twitter": "x",

    # YouTube
    "youtube": "youtube",
    "you tube": "youtube",
}


def normalize_platform_code(platform):
    """Platform.code veya Platform.name alanından standart servis kodu üretir."""
    code = getattr(platform, "code", "") or ""
    name = getattr(platform, "name", "") or ""

    raw_values = [code, name]

    for raw in raw_values:
        key = str(raw or "").strip().lower()
        if not key:
            continue

        normalized_key = (
            key.replace("-", "_")
            .replace(".", "_")
            .replace("/", "_")
        )

        if key in PLATFORM_ALIASES:
            return PLATFORM_ALIASES[key]

        if normalized_key in PLATFORM_ALIASES:
            return PLATFORM_ALIASES[normalized_key]

        compact_key = normalized_key.replace("_", "")
        if compact_key in PLATFORM_ALIASES:
            return PLATFORM_ALIASES[compact_key]

    return str(code or name or "").strip().lower()


def _get_api_class(platform_code):
    if platform_code == "facebook":
        from core.platforms.facebook import FacebookAPI
        return FacebookAPI
    if platform_code == "tiktok":
        from core.platforms.tiktok import TikTokAPI
        return TikTokAPI
    if platform_code == "google_ads":
        from core.platforms.google_ads import GoogleAdsAPI
        return GoogleAdsAPI
    if platform_code == "linkedin":
        from core.platforms.linkedin import LinkedInAPI
        return LinkedInAPI
    if platform_code == "x":
        from core.platforms.x import XAPI
        return XAPI
    if platform_code == "youtube":
        from core.platforms.youtube import YouTubeAPI
        return YouTubeAPI
    return None


def _get_account_token(account):
    connection = getattr(account, "connection", None)
    return getattr(account, "access_token", None) or getattr(connection, "access_token", None) or ""


def _is_placeholder_token(token):
    token = str(token or "").strip().lower()
    return (
        not token
        or token in {"test", "token", "em", "none", "null"}
        or len(token) < 20
    )


def _should_skip_ad_sync(account, platform_code):
    if is_demo_object(account):
        return "demo_account"

    if platform_code not in SUPPORTED_AD_SYNC_PLATFORMS:
        return "unsupported_for_ad_sync"

    if platform_code == "tiktok":
        connection = getattr(account, "connection", None)
        if not connection or not connection.is_active or (connection.extra_data or {}).get("source") != "tiktok_ads_oauth":
            return "unsupported_for_ad_sync"

    if platform_code in {"google_ads", "facebook", "linkedin"}:
        connection = getattr(account, "connection", None)
        if not connection or not connection.is_active or (connection.extra_data or {}).get("source") != "ads_oauth":
            return "oauth_reconnection_required"

    return None


def _skip_result(account, platform_code, source_type, reason, failed=False, error=None):
    result = {
        "account_id": account.id,
        "platform": platform_code,
        "source_type": source_type,
        "ads_synced": 0,
        "skipped": True,
        "reason": reason,
    }
    if failed:
        result["failed"] = True
    if error:
        result["error"] = str(error)
    elif reason == "unsupported_for_ad_sync":
        result["error"] = ad_sync_unavailable_message(platform_code)
    return result


def _is_non_retryable_api_error(response):
    status_code = response.get("status_code") if isinstance(response, dict) else None
    return status_code in {400, 401, 403, 404}


def _normalize_item(platform_code, item):
    item = dict(item or {})

    item.setdefault("platform_ad_id", item.get("ad_id") or item.get("id"))
    item.setdefault("platform_campaign_id", item.get("campaign_id") or f"{platform_code}-default-campaign")
    item.setdefault("campaign_name", item.get("campaign_name") or "Varsayılan Kampanya")
    item.setdefault(
        "platform_adgroup_id",
        item.get("adset_id") or item.get("adgroup_id") or f"{item['platform_campaign_id']}-default-adgroup",
    )
    item.setdefault("adgroup_name", item.get("adset_name") or item.get("adgroup_name") or "Varsayılan Reklam Grubu")
    item.setdefault("date", timezone.now().date().isoformat())

    return item


@shared_task(bind=True, max_retries=3, default_retry_delay=300)
def sync_v2_platform_account_ads(self, account_id, source_type="OWN", days_back=None, retry_errors=True, retry_context=None, staff_manual=False):
    from core.models import PlatformAccount
    from core.services.sync_policy import policy_for_user

    account = PlatformAccount.objects.select_related("platform", "connection", "user").get(
        id=account_id,
        is_active=True,
    )

    platform_code = normalize_platform_code(account.platform)
    source_type = (source_type or "OWN").upper()
    policy = policy_for_user(account.user)
    if not policy and staff_manual and (account.user.is_staff or account.user.is_superuser):
        # The manual API already permits staff operations without a personal
        # subscription. Keep that explicit path consistent inside the worker.
        from core.services.sync_policy import SyncPolicy
        policy = SyncPolicy(60, 60, 60, 30, 10000, "staff_manual")
    if not policy:
        return _skip_result(account, platform_code, source_type, "active_subscription_required")
    days_back = int(days_back or policy.history_days)

    skip_reason = _should_skip_ad_sync(account, platform_code)
    if skip_reason:
        logger.info(
            "V2 ad sync skipped account=%s platform=%s reason=%s",
            account_id,
            platform_code,
            skip_reason,
        )
        return _skip_result(account, platform_code, source_type, skip_reason)

    try:
        if platform_code == "tiktok":
            from core.services.tiktok_campaign_sync import sync_tiktok_campaigns
            return sync_tiktok_campaigns(account, days_back, policy.max_records, source_type)
        if platform_code == "linkedin":
            from core.services.linkedin_campaign_sync import sync_linkedin_campaigns
            return sync_linkedin_campaigns(account, days_back, policy.max_records, source_type)
        campaign_inventory = []
        api_class = _get_api_class(platform_code)
        if not api_class:
            raise Exception(
                f"Desteklenmeyen platform: code={getattr(account.platform, 'code', '')}, "
                f"name={getattr(account.platform, 'name', '')}, normalized={platform_code}"
            )

        api = api_class(account)
        from core.services.meta_sync_checkpoint import meta_read_checkpoint
        with meta_read_checkpoint((retry_context or self.request.id) if platform_code == "facebook" else None):
            if hasattr(api, "get_report_data"):
                campaign_inventory, ads_data, campaign_metrics = api.get_report_data(since_days=days_back)
            else:
                campaign_inventory = api.get_campaigns()
                ads_data = (api.get_ads(since_days=days_back, campaign_inventory=campaign_inventory)
                            if platform_code == "facebook" else api.get_ads(since_days=days_back))
                campaign_metrics = (api.get_campaign_metrics(since_days=days_back, campaign_inventory=campaign_inventory)
                                    if hasattr(api, "get_campaign_metrics") else [])

        from core.services.measurement_policy import has_measurement, prune_unmeasured
        ads_data = [row for row in ads_data or [] if has_measurement(row)]
        campaign_metrics = [row for row in campaign_metrics if has_measurement(row)]

        created_or_updated = 0
        if platform_code in {"google_ads", "facebook"} and len(ads_data or []) > policy.max_records:
            return _skip_result(account, platform_code, source_type, "record_limit_exceeded", failed=True,
                                error="Veri aralığı planın kayıt sınırını aşıyor; daha kısa bir tarih aralığı seçin.")
        synced_dates = set()

        if len(campaign_inventory) > policy.max_records:
            return _skip_result(account, platform_code, source_type, "record_limit_exceeded", failed=True,
                                error="Kampanya sayısı planın kayıt sınırını aşıyor.")
        if len(campaign_metrics) > policy.max_records:
            return _skip_result(account, platform_code, source_type, "record_limit_exceeded", failed=True,
                                error="Kampanya metrikleri planın kayıt sınırını aşıyor.")

        from django.db import transaction
        with transaction.atomic():
            for item in (ads_data or [])[:policy.max_records]:
                item = _normalize_item(platform_code, item)
                snapshot = upsert_v2_ad_snapshot(
                    user=account.user,
                    platform_account=account,
                    payload=item,
                    source_type=source_type,
                )
                if platform_code in {"google_ads", "facebook"} and snapshot["metric"] is not None:
                    synced_dates.add(snapshot["metric"].date)
                created_or_updated += 1

            if platform_code in {"facebook", "google_ads"}:
                if platform_code == "facebook":
                    from core.platforms.facebook import save_campaign_inventory
                    campaign_ids = {str(row["id"]) for row in campaign_inventory}
                else:
                    from core.platforms.google_ads import save_campaign_inventory
                    campaign_ids = {str(row["campaign"]["id"]) for row in campaign_inventory}
                measured_ids = {str(row["platform_campaign_id"]) for row in campaign_metrics}
                measured_ids.update(str(row.get("platform_campaign_id") or row.get("campaign_id")) for row in ads_data)
                save_campaign_inventory(account, [row for row in campaign_inventory
                    if str(row["id"] if platform_code == "facebook" else row["campaign"]["id"]) in measured_ids])
                # Only a complete, successful active inventory may mark older
                # local records inactive. Keep their history and configured status.
                from core.models import Campaign, Ad
                Campaign.objects.filter(platform_account=account).exclude(
                    platform_campaign_id__in=campaign_ids).update(is_active=False)
                active_ad_ids = {str(row["platform_ad_id"]) for row in ads_data or []}
                Ad.objects.filter(platform_account=account, source_type="OWN").exclude(
                    platform_ad_id__in=active_ad_ids).update(is_active=False)

            if synced_dates:
                from core.services.v2_ad_sync import rebuild_ad_metric_rollups
                rebuild_ad_metric_rollups(account, synced_dates)

            from core.models import Campaign, CampaignMetricHistory
            from core.services.v2_ad_sync import metric_defaults, get_metric_date
            for row in campaign_metrics:
                campaign = Campaign.objects.get(platform_account=account,
                                                platform_campaign_id=str(row["platform_campaign_id"]))
                defaults = metric_defaults(row)
                defaults["raw_metrics"] = {"source": "provider_campaign", "payload": row}
                CampaignMetricHistory.objects.update_or_create(campaign=campaign, date=get_metric_date(row), defaults=defaults)
            prune_unmeasured(account, apply=True)

            account.last_sync = timezone.now()
            account.extra_data = {**(account.extra_data or {}), "ads_sync_summary": {
                "completed_at": account.last_sync.isoformat(), "active_only": True,
                "days_back": days_back, "campaigns": len(measured_ids),
                "ads": len({str(row.get("platform_ad_id")) for row in ads_data or []}),
                "metric_rows": len(ads_data) + len(campaign_metrics),
            }}
            account.save(update_fields=["last_sync", "extra_data"])

        # Reklamlar ve metrikler veritabanına yazıldıktan sonra kural motoru
        # yalnız ilgili hesap için otomatik çalışır. Kuyruk geçici olarak kapalıysa
        # periyodik güvenlik taraması aynı kullanıcıyı daha sonra yeniden yakalar.
        rule_engine_task_id = None
        try:
            if not ads_data and not campaign_metrics:
                return {"account_id": account.id, "platform": platform_code, "source_type": source_type,
                        "ads_synced": 0, "campaigns_synced": 0, "metric_rows": 0,
                        "message": "Sağlayıcı seçilen dönemde metrik kaydı döndürmedi; boş kayıt oluşturulmadı.",
                        "rule_engine": {"status": "no_measurements"}}
            from core.tasks.admin_ops import generate_octo_tasks

            rule_engine_task = generate_octo_tasks.apply_async(
                kwargs={
                    "user_id": account.user_id,
                    "account_id": account.id,
                    "trigger": "ad_sync",
                    "days": min(max(days_back, 7), 30),
                },
                countdown=5,
                queue="ai",
            )
            rule_engine_task_id = rule_engine_task.id
        except Exception:
            logger.exception("Octo kural motoru kuyruğa alınamadı account=%s", account.id)

        return {
            "account_id": account.id,
            "platform": platform_code,
            "source_type": source_type,
            "ads_synced": created_or_updated,
            "rule_engine": {
                "status": "queued" if rule_engine_task_id else "periodic_fallback",
                "task_id": rule_engine_task_id,
            },
        }

    except Exception as exc:
        # The pipeline owns retries for its tracked PlatformSyncJob. Propagate
        # the original error so one provider pull cannot schedule two tasks.
        if not retry_errors:
            raise
        logger.exception("V2 sync hatası account=%s platform=%s", account_id, platform_code)
        retry_after = getattr(exc, "retry_after", None)
        if retry_after:
            raise self.retry(exc=exc, countdown=max(300, retry_after))
        raise self.retry(exc=exc)


@shared_task
def sync_all_v2_platform_accounts():
    from core.models import PlatformAccount
    from core.services.sync_policy import acquire_sync_lock, is_sync_due

    results = []

    for account in PlatformAccount.objects.filter(is_active=True).select_related("platform", "connection"):
        if not is_sync_due(account.user, account.last_sync, kind="ad"):
            continue
        lock_key, acquired = acquire_sync_lock("platform-dispatch", account.id, timeout=1800)
        if not acquired:
            continue
        platform_code = normalize_platform_code(account.platform)
        skip_reason = _should_skip_ad_sync(account, platform_code)
        if skip_reason:
            results.append(_skip_result(account, platform_code, "OWN", skip_reason))
            continue
        task = sync_v2_platform_account_ads.delay(account.id, "OWN")
        results.append({
            "account_id": account.id,
            "platform": platform_code,
            "task_id": task.id,
        })

    return results

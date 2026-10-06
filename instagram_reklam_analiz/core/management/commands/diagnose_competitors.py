"""Read-only diagnostics using the same query as the live sync service."""
import json

from django.conf import settings
from django.core.management.base import BaseCommand

from core.models import Competitor
from core.services.competitor_live_sync import (
    CompetitorSyncError, MetaAdLibraryCompetitorSync, SUPPORTED_META_PLATFORMS,
    _page_ids_for_competitor, competitor_library_url,
)
from core.services.sync_policy import policy_for_user
from core.services.competitor_public_sources import competitor_source, source_status


class Command(BaseCommand):
    help = "Inspect competitor configuration; --fetch queries upstream without writing ads."

    def add_arguments(self, parser):
        parser.add_argument("--user-id", type=int, required=True)
        parser.add_argument("--competitor-id", type=int)
        parser.add_argument("--fetch", action="store_true")

    def handle(self, *args, **options):
        competitors = Competitor.objects.select_related(
            "user", "platform", "platform_account__connection",
        ).filter(user_id=options["user_id"]).order_by("id")
        if options["competitor_id"]:
            competitors = competitors.filter(pk=options["competitor_id"])
        self.stdout.write(json.dumps({
            "dedicated_token_configured": bool(settings.META_AD_LIBRARY_ACCESS_TOKEN),
            "countries": settings.META_AD_LIBRARY_COUNTRIES,
            "graph_url": settings.FACEBOOK_GRAPH_URL,
        }, ensure_ascii=False))
        for competitor in competitors:
            service = MetaAdLibraryCompetitorSync(competitor)
            source = competitor_source(competitor)
            policy = policy_for_user(competitor.user)
            raw = competitor.raw_data or {}
            result = {
                "id": competitor.pk, "user_id": competitor.user_id,
                "name": competitor.name, "identifier": competitor.platform_identifier,
                "platform": service.platform_code, "active": competitor.is_active,
                "page_ids": _page_ids_for_competitor(competitor),
                "library_url": competitor_library_url(competitor),
                "token_available": bool(service.token),
                "source_status": source_status(competitor),
                "subscription_available": bool(policy),
                "max_records": policy.max_records if policy else None,
                "stored_ads": competitor.ads.count(),
                "sync_status": raw.get("last_live_sync_status"),
                "sync_error": raw.get("last_live_sync_error"),
                "sync_warning": raw.get("last_live_sync_warning"),
            }
            if options["fetch"]:
                if source is not None and hasattr(source, 'fetch'):
                    try:
                        rows, advertiser_id = source.fetch(policy.max_records if policy else 1)
                        result.update(upstream_rows=len(rows), advertiser_id=advertiser_id)
                    except CompetitorSyncError as exc:
                        result['fetch_error'] = str(exc)
                elif not service.token or service.platform_code not in SUPPORTED_META_PLATFORMS:
                    result["fetch_error"] = "Supported platform and Ad Library token required."
                else:
                    try:
                        payload = service._fetch(limit=policy.max_records if policy else 1)
                        rows = payload.get("data") or []
                        result["upstream_rows"] = len(rows)
                        result["advertisers"] = sorted({
                            (str(row.get("page_id") or ""), str(row.get("page_name") or ""))
                            for row in rows
                        })
                    except CompetitorSyncError as exc:
                        result["fetch_error"] = str(exc)
            # Neither credentials nor complete upstream payloads belong in diagnostics.
            output = json.dumps(result, ensure_ascii=False)
            for token in (service.token, settings.META_AD_LIBRARY_ACCESS_TOKEN):
                if token:
                    output = output.replace(token, "[REDACTED]")
            self.stdout.write(output)

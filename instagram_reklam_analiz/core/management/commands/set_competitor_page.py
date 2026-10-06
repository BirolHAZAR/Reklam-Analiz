"""Set an explicit user's competitor advertiser reference without brand constants."""
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from core.models import Competitor
from core.services.cache_service import CacheService
from core.services.competitor_identity import lock_competitor_scope, duplicate_competitors, normalize_competitor_identifier, set_page_reference
from core.services.competitor_live_sync import (
    SUPPORTED_META_PLATFORMS, _page_ids_for_competitor, parse_meta_page_reference,
)


class Command(BaseCommand):
    help = "Set a competitor's Facebook page ID/library URL; optionally queue sync."

    def add_arguments(self, parser):
        parser.add_argument("--user-id", type=int, required=True)
        parser.add_argument("--competitor-id", type=int, required=True)
        parser.add_argument("--page-reference", required=True)
        parser.add_argument("--sync", action="store_true")

    def handle(self, *args, **options):
        try:
            page_id = parse_meta_page_reference(options["page_reference"])
        except ValueError as exc:
            raise CommandError(str(exc)) from exc
        if not page_id:
            raise CommandError("A Facebook page ID/library URL is required.")
        with transaction.atomic():
            competitor = Competitor.objects.select_related("platform", "user", "agency_client").filter(
                pk=options["competitor_id"], user_id=options["user_id"],
            ).first()
            if not competitor:
                raise CommandError("Competitor does not belong to the specified user.")
            lock_competitor_scope(competitor.user, competitor.agency_client)
            competitor = Competitor.objects.select_for_update().get(pk=competitor.pk)
            if not competitor.platform or competitor.platform.code not in SUPPORTED_META_PLATFORMS:
                raise CommandError("Only Instagram/Facebook advertiser references are supported.")
            identifier = competitor.platform_identifier.strip()
            if competitor.platform.code == "facebook" and identifier.isascii() and identifier.isdigit() and identifier != page_id:
                raise CommandError("Numeric platform identifier conflicts with the requested page ID.")
            if competitor.ads.exists() and _page_ids_for_competitor(competitor) != [page_id]:
                raise CommandError("Existing ads may belong to another advertiser; review them before changing identity.")
            if options["sync"] and not competitor.is_active:
                raise CommandError("Activate the competitor before requesting sync.")
            try:
                canonical = normalize_competitor_identifier(competitor.platform_identifier)
            except ValueError as exc:
                raise CommandError(str(exc)) from exc
            if duplicate_competitors(competitor.user, competitor.platform, canonical, competitor.agency_client, page_id).exclude(pk=competitor.pk).exists():
                raise CommandError("This advertiser is already tracked in the same scope.")
            raw = set_page_reference(competitor.raw_data, page_id)
            competitor.raw_data = raw
            competitor.save(update_fields=["raw_data", "updated_at"])
            transaction.on_commit(lambda: CacheService.bump_version("competitors", competitor.user_id))
            if options["sync"]:
                from core.tasks.competitor_sync import queue_competitor_sync
                transaction.on_commit(lambda: queue_competitor_sync(competitor.pk))
        self.stdout.write(f"Updated competitor {competitor.pk}: page {page_id}.")

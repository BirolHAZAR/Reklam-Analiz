"""Read-only public source check without creating a competitor or importing ads."""
import json
from types import SimpleNamespace
from django.core.management.base import BaseCommand, CommandError
from core.services.competitor_public_sources import competitor_source
from core.services.competitor_live_sync import CompetitorSyncError


class Command(BaseCommand):
    help = 'Probe Google/TikTok public advertiser sources without writing records.'

    def add_arguments(self, parser):
        parser.add_argument('--platform', choices=['google_ads', 'tiktok', 'linkedin', 'instagram', 'facebook'], required=True)
        parser.add_argument('--identifier', required=True)
        parser.add_argument('--name', required=True)
        parser.add_argument('--website', default='')
        parser.add_argument('--limit', type=int, default=1)

    def handle(self, *args, **options):
        if not 1 <= options['limit'] <= 10:
            raise CommandError('Probe limit must be 1–10.')
        competitor = SimpleNamespace(platform=SimpleNamespace(code=options['platform']),
            platform_identifier=options['identifier'], name=options['name'], website=options['website'], raw_data={})
        source = competitor_source(competitor)
        if not hasattr(source, 'fetch'):
            raise CommandError('This probe requires a public provider adapter; use audit_competitor_access for Meta Graph.')
        try:
            rows, advertiser = source.fetch(options['limit'])
            report = {'provider': source.provider, 'advertiser_id': advertiser,
                      'rows': len(rows), 'ads': [{'id': str(row['id']), 'format': row['format']} for row in rows]}
        except CompetitorSyncError as exc:
            report = {'provider': source.provider, 'error': str(exc)}
        self.stdout.write(json.dumps(report, ensure_ascii=False))

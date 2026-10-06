"""Read-only, secret-free Meta permission and country/control-query audit."""
import json
import requests
from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from core.models import Competitor, IntegrationApplication
from core.services.competitor_live_sync import MetaAdLibraryCompetitorSync, _page_ids_for_competitor


def probe(url, params, select):
    try:
        response = requests.get(url, params=params, timeout=30)
        data = response.json()
        if not isinstance(data, dict):
            return {"http_status": response.status_code, "invalid_payload": True}
        error = data.get("error") or {}
        return {"http_status": response.status_code, "error_code": error.get("code"),
                "error_subcode": error.get("error_subcode"), **(select(data) if not error else {})}
    except (requests.RequestException, ValueError):
        return {"network_or_json_error": True}


class Command(BaseCommand):
    help = "Read-only token, permission, target/control and IP restriction diagnostics; no ads imported."

    def add_arguments(self, parser):
        parser.add_argument('--user-id', required=True, type=int)
        parser.add_argument('--competitor-id', required=True, type=int)

    def handle(self, *args, **options):
        competitor = Competitor.objects.select_related('platform', 'platform_account__connection').filter(
            pk=options['competitor_id'], user_id=options['user_id']).first()
        if not competitor:
            raise CommandError('Rakip bulunamadı.')
        service = MetaAdLibraryCompetitorSync(competitor)
        report = {"competitor_id": competitor.pk, "token_available": bool(service.token),
                  "page_ids": _page_ids_for_competitor(competitor),
                  "google_provider_configured": bool(getattr(settings, 'SERPAPI_API_KEY', '')),
                  "tiktok_library_token_configured": bool(getattr(settings, 'TIKTOK_AD_LIBRARY_ACCESS_TOKEN', ''))}
        if not service.token:
            self.stdout.write(json.dumps(report))
            return
        root = service.graph_url
        token = service.token
        # Instagram Login app credentials belong to a different namespace.
        app_id = getattr(settings, 'FACEBOOK_APP_ID', '')
        secret = getattr(settings, 'FACEBOOK_APP_SECRET', '')
        report['environment_facebook_app_id'] = app_id or None
        application = IntegrationApplication.objects.filter(provider='facebook').first()
        if application:
            app_id, secret = application.client_id, application.client_secret
            report['app_credentials_source'] = 'IntegrationApplication'
            report['app_connection_enabled'] = application.enabled
        else:
            report['app_credentials_source'] = 'environment'
        report['facebook_app_credentials_configured'] = bool(app_id and secret)
        report['configured_facebook_app_id'] = app_id or None
        if app_id and secret:
            app_token = f'{app_id}|{secret}'
            report['token_debug'] = probe(root + '/debug_token', {'input_token': token, 'access_token': app_token},
                lambda d: {"data": {k: d.get('data', {}).get(k) for k in ('app_id', 'type', 'is_valid', 'expires_at', 'data_access_expires_at', 'scopes')}})
            report['app_ip_settings'] = probe(root + '/' + str(app_id),
                {'access_token': app_token, 'fields': 'id,server_ip_whitelist'},
                lambda d: {'server_ip_whitelist': d.get('server_ip_whitelist'), 'app_id': d.get('id')})
        else:
            report['token_debug'] = {'not_checked': 'App ID/secret unavailable'}
            report['app_ip_settings'] = {'not_checked': 'App ID/secret unavailable'}
        report['token_self_debug'] = probe(root + '/debug_token', {'input_token': token, 'access_token': token},
            lambda d: {'data': {k: d.get('data', {}).get(k) for k in ('app_id', 'type', 'is_valid', 'expires_at', 'scopes')}})
        report['permissions'] = probe(root + '/me/permissions', {'access_token': token},
                                     lambda d: {'permissions': d.get('data')})
        page_ids = _page_ids_for_competitor(competitor)
        checks = {}
        for label, countries, selector, ad_type in (
            ('target_TR', ['TR'], {'search_page_ids': json.dumps(page_ids)}, 'ALL'),
            ('target_DE', ['DE'], {'search_page_ids': json.dumps(page_ids)}, 'ALL'),
            ('control_DE', ['DE'], {'search_terms': 'Nike'}, 'ALL'),
            ('control_US_political', ['US'], {'search_terms': 'Trump'}, 'POLITICAL_AND_ISSUE_ADS'),
        ):
            if label.startswith('target') and not page_ids:
                continue
            params = {'access_token': token, 'fields': 'id,page_id', 'limit': 1,
                      'ad_reached_countries': json.dumps(countries), 'ad_active_status': 'ALL',
                      'ad_type': ad_type, **selector}
            checks[label] = probe(root + '/ads_archive', params,
                                 lambda d: {'rows': len(d.get('data') or [])})
        report['queries'] = checks
        report['network_context'] = 'Command execution host only; production egress and dashboard secure IP settings require production access.'
        self.stdout.write(json.dumps(report, ensure_ascii=False))

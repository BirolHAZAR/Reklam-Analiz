"""Read-only production verification after Analytics retirement."""
import json
import shlex
import subprocess


def run(*args):
    return subprocess.check_output(args, text=True).strip()


services = ['reklam-analiz-analiz-8dzpai', 'reklam-analiz-worker-j2xrq4', 'reklam-analiz-beats-hcni7b']
for service in services:
    cid = run('docker', 'ps', '--filter', f'label=com.docker.swarm.service.name={service}', '--format', '{{.ID}}')
    print(json.dumps({'service': service, 'head': run('docker', 'exec', cid, 'git', 'rev-parse', 'HEAD'),
                      'image': run('docker', 'inspect', '--format', '{{.Image}}', cid)}))
web = run('docker', 'ps', '--filter', f'label=com.docker.swarm.service.name={services[0]}', '--format', '{{.ID}}')
code = '''
import json
from django.db import connection
from django.db.migrations.recorder import MigrationRecorder
from core.models import Platform, PlatformAccount, PlatformConnection, IntegrationApplication, LegalDocument
from config.celery import app
app.autodiscover_tasks(force=True)
expected = {73,64,63,49,48,50,51,52,80,66,67,47,78,68,79}
actual = set(PlatformAccount.objects.filter(platform__code__in=['google_ads','facebook','instagram']).values_list('pk',flat=True))
result = {
 'ga_platforms': Platform.objects.filter(code='google_analytics').count(),
 'ga_apps': IntegrationApplication.objects.filter(provider='google_analytics').count(),
 'ga_connections': PlatformConnection.objects.filter(platform__code='google_analytics').count(),
 'ga_tables': [t for t in connection.introspection.table_names() if 'analytics' in t],
 'ad_accounts_preserved': expected.issubset(actual), 'ad_accounts_count': len(actual),
 'migrations': list(MigrationRecorder.Migration.objects.filter(app='core',name__in=['0079_remove_google_analytics','0080_remove_analytics_legal_reference']).values_list('name',flat=True)),
 'ga_tasks': [n for n in app.tasks if 'ga4' in n or 'google_analytics' in n],
 'ga_schedules': [n for n in app.conf.beat_schedule if 'ga4' in n or 'google_analytics' in n],
 'legal_ga_references': list(LegalDocument.objects.filter(content__icontains='Google Analytics').values_list('slug',flat=True))
}
print(json.dumps(result))
assert not any(result[k] for k in ['ga_platforms','ga_apps','ga_connections','ga_tables','ga_tasks','ga_schedules','legal_ga_references'])
assert result['ad_accounts_preserved'] and len(result['migrations']) == 2
'''
print(run('docker', 'exec', '-w', '/app/instagram_reklam_analiz', web, '/bin/bash', '-lc',
          shlex.join(['/opt/venv/bin/python', 'manage.py', 'shell', '-c', code])))

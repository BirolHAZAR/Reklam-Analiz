"""Run on the production Swarm manager before deploying GA4 retirement."""
import json
import os
from pathlib import Path
import subprocess
import shlex
from datetime import datetime, timezone


def container(service):
    rows = subprocess.check_output([
        'docker', 'ps', '--filter', f'label=com.docker.swarm.service.name={service}', '--format', '{{.ID}}',
    ], text=True).splitlines()
    if len(rows) != 1:
        raise RuntimeError(f'Expected one running container for {service}')
    return rows[0]


def main():
    web = container('reklam-analiz-analiz-8dzpai')
    database = container('reklam-analiz-analiz-db-jvlssm')
    directory = Path('/var/backups/reklamanaliz')
    directory.mkdir(parents=True, exist_ok=True, mode=0o700)
    os.chmod(directory, 0o700)
    stamp = datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')
    destination = directory / f'before-ga4-retirement-{stamp}.dump'
    with destination.open('xb') as output:
        os.chmod(destination, 0o600)
        subprocess.run([
            'docker', 'exec', database, 'sh', '-c', 'exec pg_dump -Fc -U "$POSTGRES_USER" "$POSTGRES_DB"',
        ], stdout=output, check=True, timeout=600)
    subprocess.run(['docker', 'exec', '-i', database, 'pg_restore', '--list'],
                   stdin=destination.open('rb'), stdout=subprocess.DEVNULL, check=True, timeout=60)
    code = (
        "import json; from core.models import PlatformAccount, PlatformConnection, AnalyticsProperty, "
        "AnalyticsDailyMetric, AnalyticsLandingPageMetric; "
        "print(json.dumps({'ga4_accounts': PlatformAccount.objects.filter(platform__code='google_analytics').count(), "
        "'ga4_connections': PlatformConnection.objects.filter(platform__code='google_analytics').count(), "
        "'ga4_properties': AnalyticsProperty.objects.count(), 'ga4_daily_metrics': AnalyticsDailyMetric.objects.count(), "
        "'ga4_landing_metrics': AnalyticsLandingPageMetric.objects.count(), "
        "'ad_accounts': list(PlatformAccount.objects.filter(platform__code__in=['google_ads','facebook','instagram'])"
        ".values_list('pk',flat=True))}))"
    )
    result = subprocess.check_output([
        'docker', 'exec', '-w', '/app/instagram_reklam_analiz', web, '/bin/bash', '-lc',
        shlex.join(['/opt/venv/bin/python', 'manage.py', 'shell', '-c', code]),
    ], text=True, timeout=60)
    (directory / f'before-ga4-retirement-{stamp}.json').write_text(result, encoding='utf-8')
    print(json.dumps({'backup': str(destination), 'bytes': destination.stat().st_size}))
    print(result)


if __name__ == '__main__':
    main()

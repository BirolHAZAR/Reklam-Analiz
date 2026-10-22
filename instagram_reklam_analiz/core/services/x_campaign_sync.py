"""Atomic X Ads imports: measured campaigns and promoted posts only."""
from collections import defaultdict
from datetime import date, timedelta
from django.db import transaction
from django.utils import timezone
from core.models import PlatformAccount, Campaign, CampaignMetricHistory
from core.services import x_ads as api
from core.services.ads_integrations import IntegrationError
from core.services.v2_ad_sync import metric_defaults, upsert_v2_ad_snapshot, rebuild_ad_metric_rollups


def sync_x_campaigns(account, days_back, max_records, source_type='OWN'):
    if not 1 <= int(days_back) <= 31:
        raise IntegrationError('X Ads aktarımı için 1–31 günlük dönem seçin.')
    credentials = api.account_token(account)
    info = api.account_info(api.read(credentials, f'accounts/{api.identifier(account.account_id)}').get('data'))
    if info['id'] != account.account_id:
        raise IntegrationError('X reklam hesabı eşleşmedi.')
    # Date bounds are derived from the provider timezone, never the host timezone.
    from zoneinfo import ZoneInfo
    end = timezone.localdate(timezone=ZoneInfo(info['timezone']))
    start = end-timedelta(days=int(days_back)-1)
    campaigns = api.inventory(credentials, account.account_id, limit=max_records)
    groups = api.inventory(credentials, account.account_id, 'line_items', limit=max_records)
    ads = api.inventory(credentials, account.account_id, 'promoted_tweets', limit=max_records)
    campaign_metrics = api.report(credentials, account.account_id, list(campaigns), info['timezone'], start, end, limit=max_records)
    ad_metrics = api.report(credentials, account.account_id, list(ads), info['timezone'], start, end,
                            entity='PROMOTED_TWEET', limit=max_records)
    if len(campaign_metrics)+len(ad_metrics) > max_records:
        raise IntegrationError('X Ads kayıtları plan sınırını aşıyor.')
    reports = defaultdict(list)
    for row in campaign_metrics:
        if row['id'] not in campaigns:
            raise IntegrationError('X kampanya raporu envanterle eşleşmedi.')
        reports[row['id']].append(row)
    payloads = []
    for row in ad_metrics:
        ad = ads.get(row['id'])
        group = groups.get(ad.get('line_item_id')) if ad else None
        campaign = campaigns.get(group.get('campaign_id')) if group else None
        if not campaign or not isinstance(ad.get('tweet_id'), str) or not ad['tweet_id'].isascii() or not ad['tweet_id'].isdigit():
            raise IntegrationError('X reklam hiyerarşisi eksik. Hiçbir veri kaydedilmedi.')
        payloads.append({**row, 'spend':str(row['spend']), 'currency':info['currency'],
            'platform_ad_id':ad['id'], 'platform_campaign_id':campaign['id'],
            'campaign_name':campaign['name'], 'campaign_status':campaign.get('entity_status','UNKNOWN'),
            'platform_adgroup_id':group['id'], 'adgroup_name':group['name'],
            'ad_name':ad.get('name') or f"Promoted post {ad['tweet_id']}",
            'status':ad.get('entity_status','UNKNOWN'), 'objective':group.get('objective','UNKNOWN'),
            'campaign_raw':campaign, 'ad_raw':ad, 'allow_estimated_conversion_value':False})
    now = timezone.now()
    with transaction.atomic():
        locked = PlatformAccount.objects.select_for_update().get(pk=account.pk)
        if not locked.is_active or locked.connection_id != account.connection_id:
            raise IntegrationError('X reklam bağlantısı değişti. Yeniden deneyin.')
        for payload in payloads:
            upsert_v2_ad_snapshot(user=account.user, platform_account=account, payload=payload, source_type=source_type)
        rebuild_ad_metric_rollups(account, {date.fromisoformat(row['date']) for row in payloads})
        for cid, metrics in reports.items():
            row = campaigns[cid]
            status = row.get('entity_status','UNKNOWN')
            campaign, _ = Campaign.objects.update_or_create(platform_account=account, platform_campaign_id=cid,
                defaults={'user':account.user, 'platform_connection':account.connection, 'name':row['name'],
                    'status':status, 'is_active':status == 'ACTIVE', 'currency':info['currency'],
                    'raw_data':row, 'last_synced_at':now})
            for metric in metrics:
                defaults = metric_defaults({**metric,'currency':info['currency'],'allow_estimated_conversion_value':False})
                defaults['raw_metrics'] = {key:str(value) for key,value in metric.items()}
                CampaignMetricHistory.objects.update_or_create(campaign=campaign, date=date.fromisoformat(metric['date']), defaults=defaults)
        locked.last_sync = now
        locked.extra_data = {**(locked.extra_data or {}), **info, 'ads_sync_summary':{
            'completed_at':now.isoformat(), 'days_back':days_back, 'campaigns':len(reports),
            'ads':len({row['id'] for row in ad_metrics}), 'metric_rows':len(campaign_metrics)+len(ad_metrics)}}
        locked.save(update_fields=['last_sync','extra_data','updated_at'])
    return {'account_id':account.pk,'platform':'x','source_type':source_type,
            'campaigns_synced':len(reports),'ads_synced':len({row['id'] for row in ad_metrics}),
            'metric_rows':len(campaign_metrics)+len(ad_metrics)}

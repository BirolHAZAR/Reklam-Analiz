"""Import only complete, provider-measured X posts; never invent absent metrics."""
from django.conf import settings
from django.db import transaction
from django.utils import timezone
from django.utils.dateparse import parse_datetime
from core.models import PlatformAccount, SocialPost, SocialPostMetricHistory
from core.services import x_oauth as api
from core.services.ads_integrations import IntegrationError
from core.services.demo_policy import is_demo_object, demo_skip_result


def sync_x_organic_content(account, *, limit=50):
    if is_demo_object(account):
        return demo_skip_result()
    empty = {'success': False, 'created': 0, 'updated': 0, 'metrics': 0}
    if not account or account.platform.code != 'x' or not account.connection_id:
        return {**empty, 'error': 'X organik hesabı bulunamadı.'}
    try:
        api.require_read_access()
        token = api.access_token(account)
        # Paid reads are capped independently from the subscription's record limit.
        cap = min(max(1, int(limit)), max(1, min(int(getattr(settings, 'X_MAX_POSTS_PER_SYNC', 10)), 100)))
        collected, ids, cursors = [], set(), set()
        if cap < 5:
            raise IntegrationError('X API tek istekte en az 5 gönderi ister; kayıt sınırı yetersiz.')
        cursor, now = None, timezone.now()
        for _ in range(20):
            rows, next_cursor = api.posts(token, account.account_id, cursor, max_results=min(100, cap - len(collected)))
            for row in rows:
                pid = row.get('id')
                created_at = row.get('created_at')
                try:
                    posted_at = parse_datetime(created_at) if isinstance(created_at, str) else None
                except (ValueError, OverflowError):
                    posted_at = None
                metrics = row.get('public_metrics')
                if (not isinstance(pid, str) or not pid.isascii() or not pid.isdigit() or len(pid) > 100
                        or pid in ids or row.get('author_id') != account.account_id
                        or not isinstance(row.get('text'), str) or not posted_at
                        or timezone.is_naive(posted_at) or posted_at > now or not isinstance(metrics, dict)):
                    raise IntegrationError('X gönderi kimliği, tarihi veya metrikleri eksik; hiçbir içerik kaydedilmedi.')
                counts = {}
                for key in ('impression_count', 'like_count', 'reply_count', 'retweet_count', 'quote_count'):
                    value = metrics.get(key)
                    if type(value) is not int or not 0 <= value < 2**63:
                        raise IntegrationError('X gönderi metrikleri eksik; hiçbir içerik kaydedilmedi.')
                    counts[key] = value
                if sum(counts[k] for k in ('like_count', 'reply_count', 'retweet_count', 'quote_count')) >= 2**63:
                    raise IntegrationError('X etkileşim sayısı geçersiz.')
                ids.add(pid)
                collected.append((row, posted_at, counts))
                if len(collected) == cap:
                    break
            if cap - len(collected) < 5 or next_cursor is None:
                break
            if next_cursor in cursors or not rows:
                raise IntegrationError('X gönderi sayfalaması tamamlanamadı; hiçbir içerik kaydedilmedi.')
            cursors.add(next_cursor)
            cursor = next_cursor
        else:
            raise IntegrationError('X gönderi tarama sınırına ulaşıldı.')
        created = 0
        with transaction.atomic():
            locked = PlatformAccount.objects.select_for_update().get(pk=account.pk)
            if not locked.is_active or locked.connection_id != account.connection_id:
                raise IntegrationError('X hesap bağlantısı değişti. Yeniden deneyin.')
            for row, posted_at, counts in collected:
                post, new = SocialPost.objects.update_or_create(user=account.user, platform_account=account,
                    platform_post_id=row['id'], defaults={'platform_connection': account.connection,
                        'post_type': 'TEXT', 'caption': row['text'], 'posted_at': posted_at,
                        'permalink': f'https://x.com/i/web/status/{row["id"]}', 'last_synced_at': now,
                        'is_active': True, 'raw_data': {'source': 'x_post_sync', 'status': 'synced', 'raw': row}})
                created += int(new)
                shares = counts['retweet_count'] + counts['quote_count']
                engagement = counts['like_count'] + counts['reply_count'] + shares
                SocialPostMetricHistory.objects.update_or_create(social_post=post, date=timezone.localdate(now),
                    defaults={'likes': counts['like_count'], 'comments': counts['reply_count'], 'shares': shares,
                        'impressions': counts['impression_count'], 'engagement': engagement,
                        'raw_metrics': {'provider': 'x_api', 'synced_at': now.isoformat(),
                            'insights_status': 'available', 'insights': {'impressions': counts['impression_count'],
                                'likes': counts['like_count'], 'comments': counts['reply_count'],
                                'shares': shares, 'total_interactions': engagement}}})
            locked.last_sync = now
            locked.extra_data = {**(locked.extra_data or {}), 'organic_last_sync_at': now.isoformat(),
                                 'organic_synced_posts': len(collected), 'organic_post_limit': cap}
            locked.save(update_fields=['last_sync', 'extra_data', 'updated_at'])
        return {'success': True, 'created': created, 'updated': len(collected) - created,
                'metrics': len(collected), 'fetched': len(collected), 'insights_available': len(collected),
                'insights_unavailable': 0}
    except IntegrationError as exc:
        return {**empty, 'error': str(exc)}

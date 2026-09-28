# Demo günlük metrik kontrolü

28 Eylül 2026 yerel kontrolü: `0073_admin_manage_demo_daily_metrics` uygulanmış,
günlük görev aktif ve son görev sonucu SUCCESS. Günlük servis yalnızca çalıştığı
günü üretir; kaçırılan günleri otomatik tamamlamaz. Zamanlamadaki `last_run_at`
kuyruğa gönderim zamanıdır, başarı kanıtı değildir; `last_task_id` sonucu ayrıca
kontrol edilmelidir.

Geçmiş tamamlama sırasında pazaryeri fiyatlarının önceki indirimli fiyattan tekrar
üretilmesi `numeric field overflow` hatasına yol açtı. Servis artık önceki liste
fiyatını kullanır ve sentetik fiyatlara maliyete bağlı bir alt sınır uygular.
Bu düzeltmeyi canlıya almadan geçmiş tamamlama çalıştırmayın; günlük worker da
yeni servis kodunu yüklemek için yeniden başlatılmalıdır.

Komutları uygulama dizininde, ilgili ortamın Python ve Django ayarlarıyla çalıştırın.

## Canlıda önce kontrol

```sh
python manage.py showmigrations core
python manage.py migrate --plan
python manage.py shell -c "from core.models import AdminManagedCelerySchedule; print(list(AdminManagedCelerySchedule.objects.filter(task_name='core.tasks.metric_tasks.refresh_daily_demo_metrics').values('is_active','interval_every','interval_period','last_run_at','last_task_id','last_error')))"
python manage.py shell -c "from core.models import AdminManagedCelerySchedule; from config.celery import app; s=AdminManagedCelerySchedule.objects.get(task_name='core.tasks.metric_tasks.refresh_daily_demo_metrics'); r=app.AsyncResult(s.last_task_id); print(r.state, r.result); print(app.control.inspect(timeout=3).ping())"
```

Sonuç `PENDING` ise tek başına görev çalışmadı anlamına gelmez; sonuç kaydı
silinmiş olabilir. Worker/Beat logları ve metrik tarihleriyle doğrulayın.
Beat, `dispatch-admin-managed-schedules` görevini dakikada bir maintenance
kuyruğuna gönderir. Worker'ın ilgili kuyrukları dinlemesi gerekir.

## 90 günlük geçmiş

Önce iki markanın kapsamını `--dry-run` ile kontrol edin. Ardından:

```sh
python manage.py refresh_demo_agency_history --days 90 --client-name "Demo Marka"
python manage.py refresh_demo_agency_history --days 90 --client-name "Demo Marka 2"
python manage.py update_demo_daily --days 90 --missing-only
python manage.py update_demo_daily
```

İlk iki komut sentetik marka reklamlarının geçmişini yeniden üretir ve pencere
dışındaki ilgili eski geçmişi temizler. `--remove-live-connections` kullanmayın.
Son komut, herhangi bir demo reklamının metrik kaydı eksik olan günleri ortak
günlük servisle tamamlar. Bu günlerin kampanya, reklam grubu, kreatif, pazaryeri
ve organik metriklerini de yeniler; geçmiş günler için bildirim üretmez.
`--missing-only` reklam kapsamını kontrol eder; pazaryeri/organik veride tek
başına oluşmuş eksikleri tespit etmez. Bitiş tarihi için `--date YYYY-MM-DD`
kullanılabilir.

Kontrol için Django shell içinde:

```python
from datetime import timedelta
from django.utils import timezone
from django.db.models import Count
from core.models import AdMetricHistory
from core.services.demo_metrics import _demo_ads_queryset

end = timezone.localdate()
ads = _demo_ads_queryset()
rows = AdMetricHistory.objects.filter(
    ad__in=ads, date__range=(end - timedelta(days=89), end),
)
print('Beklenen:', ads.count() * 90, 'Mevcut:', rows.count())
print('Eksik:', list(rows.values('ad_id').annotate(
    days=Count('date', distinct=True),
).filter(days__lt=90)))
```

Beklenen ve mevcut sayılar eşit olmalı. Bu kontrol canlıda henüz çalıştırılmadı.

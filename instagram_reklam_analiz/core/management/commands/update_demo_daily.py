"""Compatibility command for the canonical daily demo metrics service.

The actual demo-data generation lives in ``core.services.demo_metrics`` and
is scheduled through ``core.tasks.metric_tasks.refresh_daily_demo_metrics``.
This command is intentionally a thin wrapper so manual invocations cannot
create a second, divergent demo-metrics implementation.
"""

from __future__ import annotations

from datetime import timedelta

from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone
from django.utils.dateparse import parse_date


class Command(BaseCommand):
    help = (
        "Demo kullanicisinin gunluk reklam/kampanya metriklerini, "
        "Celery ile kullanilan canonical servis uzerinden yeniler."
    )

    def add_arguments(self, parser):
        parser.add_argument("--days", type=int, default=1, help="Bitis tarihi dahil yenilenecek gun sayisi (1-365).")
        parser.add_argument("--missing-only", action="store_true", help="Reklam metrikleri eksiksiz olan gunleri atla.")
        parser.add_argument(
            "--date",
            dest="metric_date",
            default=None,
            help="Opsiyonel YYYY-MM-DD tarih. Verilmezse bugunun tarihi kullanilir.",
        )

    def handle(self, *args, **options):
        metric_date = options.get("metric_date")
        if metric_date:
            try:
                metric_date = parse_date(metric_date)
            except ValueError as exc:
                raise CommandError("--date YYYY-MM-DD formatinda gecerli bir tarih olmalidir.") from exc
            if metric_date is None:
                raise CommandError("--date YYYY-MM-DD formatinda olmalidir.")

        from core.services.demo_metrics import refresh_demo_metrics_for_date

        days = options["days"]
        if not 1 <= days <= 365:
            raise CommandError("--days 1-365 araliginda olmalidir.")
        end_date = metric_date or timezone.localdate()
        from core.services.demo_metrics import _demo_ads_queryset
        from core.models import AdMetricHistory

        ad_ids = list(_demo_ads_queryset().values_list("pk", flat=True))
        if not ad_ids:
            raise CommandError("Demo reklam bulunamadi.")
        for offset in range(days - 1, -1, -1):
            day = end_date - timedelta(days=offset)
            if options["missing_only"] and AdMetricHistory.objects.filter(
                ad_id__in=ad_ids, date=day,
            ).values("ad_id").distinct().count() == len(ad_ids):
                continue
            result = refresh_demo_metrics_for_date(
                metric_date=day, create_signals=day == timezone.localdate(),
            )
            if not result.get("success"):
                raise CommandError(f"Demo metrikleri yenilenemedi: {day}")
            self.stdout.write(f"{day}: {result}")
        self.stdout.write(self.style.SUCCESS(f"Demo metrik kontrolu tamamlandi: {days} gun."))

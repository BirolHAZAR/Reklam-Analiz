"""Compatibility command for the canonical daily demo metrics service.

The actual demo-data generation lives in ``core.services.demo_metrics`` and
is scheduled through ``core.tasks.metric_tasks.refresh_daily_demo_metrics``.
This command is intentionally a thin wrapper so manual invocations cannot
create a second, divergent demo-metrics implementation.
"""

from __future__ import annotations

from django.core.management.base import BaseCommand, CommandError
from django.utils.dateparse import parse_date


class Command(BaseCommand):
    help = (
        "Demo kullanicisinin gunluk reklam/kampanya metriklerini, "
        "Celery ile kullanilan canonical servis uzerinden yeniler."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--date",
            dest="metric_date",
            default=None,
            help="Opsiyonel YYYY-MM-DD tarih. Verilmezse bugunun tarihi kullanilir.",
        )

    def handle(self, *args, **options):
        metric_date = options.get("metric_date")
        if metric_date:
            metric_date = parse_date(metric_date)
            if metric_date is None:
                raise CommandError("--date YYYY-MM-DD formatinda olmalidir.")

        from core.services.demo_metrics import refresh_demo_metrics_for_date

        result = refresh_demo_metrics_for_date(metric_date=metric_date)

        if not result.get("success"):
            raise CommandError("Demo gunluk metrikleri yenilenemedi.")

        self.stdout.write(
            self.style.SUCCESS(
                "Demo gunluk metrikleri yenilendi: "
                f"{result['date']} | "
                f"ads={result['ads']} | "
                f"competitor_ads={result['competitor_ads']} | "
                f"campaigns={result['campaigns']} | "
                f"ad_groups={result['ad_groups']} | "
                f"creatives={result['creatives']}"
            )
        )

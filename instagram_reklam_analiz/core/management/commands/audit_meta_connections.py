"""Read-only Meta diagnostics; never print token or application credentials."""
import json

from django.conf import settings
from django.apps import apps
from django.core.management.base import BaseCommand
from django.utils import timezone

from core.models import PlatformConnection
from core.services.demo_policy import is_demo_object
from core.services.platform_token_service import _validate_connection


class Command(BaseCommand):
    help = "Meta bağlantı sürelerini ve bakım zamanlayıcısını salt okunur denetler."

    def add_arguments(self, parser):
        parser.add_argument("--live", action="store_true", help="Meta üzerinde salt okunur token/profil kontrolü yapar.")

    def handle(self, *args, **options):
        now = timezone.now()
        rows = []
        for connection in PlatformConnection.objects.select_related("platform").filter(
            platform__code__in=("instagram", "facebook"), is_active=True
        ):
            if is_demo_object(connection):
                continue
            extra = connection.extra_data or {}
            row = {
                "connection_id": connection.pk, "platform": connection.platform.code,
                "status": connection.status, "auth_type": extra.get("auth_type", extra.get("source", "legacy")),
                "token_expiry": connection.token_expiry.isoformat() if connection.token_expiry else None,
                "remaining_hours": round((connection.token_expiry - now).total_seconds() / 3600, 1) if connection.token_expiry else None,
                "last_health_check": extra.get("token_health_checked_at"),
                "last_health_status": extra.get("token_health_status"),
                "failure_count": extra.get("token_health_failure_count", 0),
                "data_access_expires_at": extra.get("data_access_expires_at"),
            }
            if options["live"]:
                try:
                    result = _validate_connection(connection)
                    row["api_valid"] = result.get("valid")
                    for field in ("expires_at", "data_access_expires_at"):
                        value = result.get(field)
                        row["api_" + field] = value.isoformat() if value else None
                except Exception as exc:
                    # Exceptions can contain token-bearing URLs. Only output
                    # the class and safe, numeric cooldown information.
                    row["api_valid"] = None
                    row["api_error_type"] = type(exc).__name__
                    row["retry_after"] = getattr(exc, "retry_after", None)
            rows.append(row)
        schedules = []
        for name, entry in settings.CELERY_BEAT_SCHEDULE.items():
            if entry.get("task", "").endswith("refresh_expired_tokens"):
                schedules.append({"name": name, "task": entry["task"], "schedule": str(entry["schedule"]),
                                  "queue": entry.get("options", {}).get("queue")})
        database_schedules = []
        if apps.is_installed("django_celery_beat"):
            PeriodicTask = apps.get_model("django_celery_beat", "PeriodicTask")
            database_schedules = list(PeriodicTask.objects.filter(task__endswith="refresh_expired_tokens").values(
                "name", "task", "enabled", "queue", "last_run_at", "total_run_count"))
        self.stdout.write(json.dumps({"checked_at": now.isoformat(), "connections": rows,
            "configured_schedules": schedules, "database_schedules": database_schedules,
            "note": "Zamanlama kaydı worker/beat sürecinin şu anda çalıştığını kanıtlamaz."},
            ensure_ascii=False, indent=2, default=str))

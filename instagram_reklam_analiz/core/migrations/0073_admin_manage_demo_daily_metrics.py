from django.db import migrations
from django.utils import timezone


SCHEDULE_NAME = "Demo Günlük Metrik Yenileme"
TASK_NAME = "core.tasks.metric_tasks.refresh_daily_demo_metrics"


def create_demo_schedule(apps, schema_editor):
    Schedule = apps.get_model("core", "AdminManagedCelerySchedule")
    now = timezone.now()
    Schedule.objects.update_or_create(
        name=SCHEDULE_NAME,
        defaults={
            "task_name": TASK_NAME,
            "args": [],
            "kwargs": {},
            "interval_every": 24,
            "interval_period": "hours",
            "is_active": True,
            "description": (
                "Demo kullanıcısının reklam, kampanya, reklam grubu ve creative "
                "günlük metriklerini canonical demo_metrics servisi ile yeniler. "
                "Admin panelinden aktif/pasif yapılabilir ve çalışma aralığı değiştirilebilir."
            ),
            "last_run_at": now,
            "last_task_id": "",
            "last_error": "",
        },
    )


def remove_demo_schedule(apps, schema_editor):
    Schedule = apps.get_model("core", "AdminManagedCelerySchedule")
    Schedule.objects.filter(name=SCHEDULE_NAME, task_name=TASK_NAME).delete()


class Migration(migrations.Migration):
    dependencies = [
        ("core", "0072_alter_adgroupmetrichistory_unique_together_and_more"),
    ]

    operations = [
        migrations.RunPython(create_demo_schedule, remove_demo_schedule),
    ]

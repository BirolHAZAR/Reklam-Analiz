"""Remove inferred performance values from historical Ad Library records."""
from django.db import migrations


def correct_library_data(apps, schema_editor):
    alias = schema_editor.connection.alias
    Metric = apps.get_model("core", "AdMetricHistory")
    Ad = apps.get_model("core", "Ad")
    Creative = apps.get_model("core", "Creative")
    Metric.objects.using(alias).filter(raw_metrics__provider="meta_ad_library").update(
        reach=0, frequency=0, engagement=0, engagement_rate=0, cpm=0,
        estimated_engagement=0, estimated_reach_min=0, estimated_reach_max=0,
        is_competitor_snapshot=True,
    )
    library_ads = Ad.objects.using(alias).filter(source_type="COMPETITOR", raw_data__provider="meta_ad_library")
    Creative.objects.using(alias).filter(pk__in=library_ads.values("creative_id")).update(
        creative_type="UNKNOWN", landing_url="",
    )
    library_ads.update(ad_format="UNKNOWN", landing_url="")


class Migration(migrations.Migration):
    dependencies = [("core", "0080_remove_analytics_legal_reference")]
    operations = [migrations.RunPython(correct_library_data, migrations.RunPython.noop)]

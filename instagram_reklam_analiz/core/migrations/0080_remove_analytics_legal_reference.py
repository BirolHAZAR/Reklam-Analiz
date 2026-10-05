from datetime import date

from django.db import migrations


def remove_analytics_reference(apps, schema_editor):
    documents = apps.get_model('core', 'LegalDocument').objects.using(
        schema_editor.connection.alias,
    ).filter(slug='google-ads-veri-kullanim-bildirimi')
    old = 'metrikleri; ayrıca kullanıcı bağlarsa salt okunur Analytics raporları alınabilir.'
    new = 'metrikleri alınabilir.'
    for document in documents:
        if old in document.content:
            document.content = document.content.replace(old, new)
            document.version = '1.2'
            document.effective_date = date(2026, 10, 5)
            document.save(using=schema_editor.connection.alias,
                          update_fields=['content', 'version', 'effective_date'])


class Migration(migrations.Migration):
    dependencies = [('core', '0079_remove_google_analytics')]
    operations = [migrations.RunPython(remove_analytics_reference)]

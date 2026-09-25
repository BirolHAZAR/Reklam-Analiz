from django.db import migrations


def unify_company(apps, schema_editor):
    Company = apps.get_model("core", "LegalSiteSettings")
    company, _ = Company.objects.using(schema_editor.connection.alias).get_or_create(pk=1)
    if not company.company_name or company.company_name in {"HZR Yazılım Danışmanlık Dijital Paz. LTD ŞTİ", "HZR Bilişim Yazılım San. Tic. LTD ŞTİ."}:
        company.company_name = "HZRSoft Yazılım Dijital Pazarlama Danışmanlık ve Ticaret"
    if not company.address or company.address == "Bakırköy":
        company.address = "Yeni Mahalle Ahmet Kabaklı Cad. 1583. Sokak No:12/3, Bağcılar / İstanbul"
    if not company.phone:
        company.phone = "0212 651 52 53"
    # Preserve tax/MERSIS/KEP values and previously accepted document snapshots.
    company.save(update_fields=["company_name", "address", "phone"])


class Migration(migrations.Migration):
    dependencies = [("core", "0073_admin_manage_demo_daily_metrics")]
    operations = [migrations.RunPython(unify_company, migrations.RunPython.noop)]

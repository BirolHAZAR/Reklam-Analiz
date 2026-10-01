"""Read-only deployment check; never prints credentials or contacts Meta."""
from urllib.parse import urlsplit

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError

from core.services.ads_integrations import IntegrationError, configuration


class Command(BaseCommand):
    help = "Instagram canlı OAuth ayarlarını gizli bilgileri göstermeden doğrular."

    def handle(self, *args, **options):
        if settings.DEBUG:
            raise CommandError("Canlı kontrolü DEBUG=False ile çalıştırılmalıdır.")
        try:
            _, _, redirect = configuration("instagram")
        except IntegrationError as exc:
            raise CommandError(str(exc)) from None
        parsed = urlsplit(redirect)
        if parsed.scheme != "https" or parsed.hostname not in {"reklamanaliz.net", "www.reklamanaliz.net"} or parsed.port not in {None, 443}:
            raise CommandError("Canlı Instagram dönüş adresi sitenin HTTPS adresi olmalıdır.")
        self.stdout.write(self.style.SUCCESS(f"Instagram sunucu ayarları geçerli. Dönüş adresi: {redirect}"))
        self.stdout.write("Meta izin onayları ve gerçek hesap bağlantısı bu kontrolle doğrulanmaz.")

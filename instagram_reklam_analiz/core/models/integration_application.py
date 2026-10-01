from urllib.parse import urlsplit

from django.core.exceptions import ValidationError
from django.db import models

from core.fields import EncryptedTextField
from core.platform_setup import PLATFORM_CHOICES, PLATFORM_SETUP


class IntegrationApplication(models.Model):
    provider = models.CharField("Platform", max_length=32, unique=True, choices=PLATFORM_CHOICES)
    client_id = models.CharField("Uygulama / istemci kimliği", max_length=255, blank=True)
    client_secret = EncryptedTextField("Uygulama gizli anahtarı", blank=True)
    developer_token = EncryptedTextField("Google Ads geliştirici tokenı", blank=True, default="")
    redirect_uri = models.URLField("OAuth dönüş adresi", max_length=500, blank=True)
    enabled = models.BooleanField("Bu uygulama ayarlarını kullan", default=False)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Platform Ayarı"
        verbose_name_plural = "Platform Ayarları"

    def __str__(self):
        return self.get_provider_display()

    def clean(self):
        spec = PLATFORM_SETUP.get(self.provider)
        if not spec:
            raise ValidationError({"provider": "Desteklenen bir platform seçin."})
        uri = urlsplit(self.redirect_uri)
        local = uri.hostname in {"localhost", "127.0.0.1"}
        if self.redirect_uri and (uri.hostname not in {"reklamanaliz.net", "www.reklamanaliz.net", "localhost", "127.0.0.1"}
                or uri.scheme not in ({"http", "https"} if local else {"https"})
                or uri.username or uri.password or uri.query or uri.fragment
                or (spec["callback"] and uri.path != spec["callback"])):
            raise ValidationError({"redirect_uri": "Platformun bu siteye ait tam OAuth dönüş adresini girin."})
        if self.enabled:
            if spec["mode"] == "draft":
                raise ValidationError({"enabled": "Bu platformun uygulama ayarlarını kullanan bağlantı henüz uygulanmadı. Taslak olarak kaydedebilirsiniz."})
            required = ["client_id", "client_secret"]
            if spec["mode"] == "oauth":
                required.append("redirect_uri")
            missing = {name: "Bağlantıyı etkinleştirmek için gereklidir." for name in required if not (getattr(self, name, "") or "").strip()}
            if missing:
                raise ValidationError(missing)

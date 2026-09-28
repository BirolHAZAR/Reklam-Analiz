from urllib.parse import urlsplit

from django.core.exceptions import ValidationError
from django.db import models

from core.fields import EncryptedTextField


class IntegrationApplication(models.Model):
    provider = models.CharField("Platform", max_length=32, unique=True, choices=[
        ("google_ads", "Google Ads"), ("facebook", "Meta Ads"),
    ])
    client_id = models.CharField("Uygulama / istemci kimliği", max_length=255)
    client_secret = EncryptedTextField("Uygulama gizli anahtarı")
    developer_token = EncryptedTextField("Google Ads geliştirici tokenı", blank=True, default="")
    redirect_uri = models.URLField("OAuth dönüş adresi", max_length=500)
    enabled = models.BooleanField("Bu uygulama ayarlarını kullan", default=False)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Entegrasyon Uygulaması"
        verbose_name_plural = "Entegrasyon Uygulama Ayarları"

    def __str__(self):
        return self.get_provider_display()

    def clean(self):
        callback_paths = {"google_ads": "/connect/google-ads/callback/", "facebook": "/connect/facebook/callback/"}
        uri = urlsplit(self.redirect_uri)
        local = uri.hostname in {"localhost", "127.0.0.1"}
        if (uri.hostname not in {"reklamanaliz.net", "www.reklamanaliz.net", "localhost", "127.0.0.1"}
                or uri.scheme not in ({"http", "https"} if local else {"https"})
                or uri.username or uri.password or uri.query or uri.fragment
                or uri.path != callback_paths.get(self.provider)):
            raise ValidationError({"redirect_uri": "Platformun bu siteye ait tam OAuth dönüş adresini girin."})
        if self.enabled:
            required = ["client_id", "client_secret"]
            if self.provider == "google_ads":
                required.append("developer_token")
            missing = {name: "Bağlantıyı etkinleştirmek için gereklidir." for name in required if not (getattr(self, name, "") or "").strip()}
            if missing:
                raise ValidationError(missing)

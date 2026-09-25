import uuid
from urllib.parse import urlsplit

from django.core.exceptions import ValidationError
from django.db import models
from core.fields import EncryptedTextField


class PaymentGatewaySettings(models.Model):
    provider = models.CharField("Aktif sanal POS", max_length=20, choices=[("iyzico", "iyzico"), ("garanti", "Garanti BBVA")], default="iyzico")
    enabled = models.BooleanField("Kart ödemesi açık", default=False)
    sandbox = models.BooleanField("Test ortamı (yalnızca personel)", default=True)
    public_origin = models.URLField("Dönüş adresinin site kökü", default="https://reklamanaliz.net", help_text="Yalnızca HTTPS site kökü. Örnek: https://reklamanaliz.net")
    iyzico_api_key = EncryptedTextField("iyzico API anahtarı", blank=True, default="")
    iyzico_secret_key = EncryptedTextField("iyzico gizli anahtar", blank=True, default="")
    garanti_merchant_id = models.CharField("Garanti üye işyeri numarası", max_length=30, blank=True, default="")
    garanti_terminal_id = models.CharField("Garanti terminal numarası", max_length=8, blank=True, default="")
    garanti_user_id = models.CharField("Garanti kullanıcı adı", max_length=40, default="GARANTI")
    garanti_prov_user = models.CharField("Garanti provizyon kullanıcısı", max_length=40, default="PROVOOS")
    garanti_prov_password = EncryptedTextField("Garanti provizyon şifresi", blank=True, default="")
    garanti_store_key = EncryptedTextField("Garanti 3D güvenlik anahtarı", blank=True, default="")
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Sanal POS Ayarları"
        verbose_name_plural = "Sanal POS Ayarları"

    def __str__(self):
        return f"{self.get_provider_display()} — {'Test' if self.sandbox else 'Canlı'}"

    @classmethod
    def load(cls):
        return cls.objects.get_or_create(pk=1)[0]

    def save(self, *args, **kwargs):
        self.pk = 1
        return super().save(*args, **kwargs)

    def clean(self):
        origin = urlsplit(self.public_origin)
        if origin.scheme != "https" or origin.hostname not in {"reklamanaliz.net", "www.reklamanaliz.net"} or origin.path not in {"", "/"} or origin.query or origin.fragment or origin.username or origin.port:
            raise ValidationError({"public_origin": "reklamanaliz.net veya www.reklamanaliz.net HTTPS kök adresini girin."})
        if self.enabled:
            fields = ("iyzico_api_key", "iyzico_secret_key") if self.provider == "iyzico" else ("garanti_merchant_id", "garanti_terminal_id", "garanti_user_id", "garanti_prov_user", "garanti_prov_password", "garanti_store_key")
            missing = {field: "Kart ödemesini açmak için bu alan gereklidir." for field in fields if not getattr(self, field).strip()}
            if missing:
                raise ValidationError(missing)
        if self.garanti_terminal_id and (not self.garanti_terminal_id.isdigit() or len(self.garanti_terminal_id) != 8):
            raise ValidationError({"garanti_terminal_id": "8 haneli terminal numarasını girin."})

    def available_for(self, user):
        try:
            self.full_clean()
        except ValidationError:
            return False
        return self.enabled and (not self.sandbox or bool(user and user.is_staff))


class HostedPaymentSession(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    payment = models.OneToOneField("core.Payment", on_delete=models.PROTECT, related_name="hosted_session")
    provider = models.CharField(max_length=20)
    configuration = EncryptedTextField()
    token = EncryptedTextField(blank=True, default="")
    purchase_data = models.JSONField(default=dict)
    verified = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Sanal POS İşlemi"
        verbose_name_plural = "Sanal POS İşlemleri"

    def __str__(self):
        return f"{self.provider} / {self.payment_id}"

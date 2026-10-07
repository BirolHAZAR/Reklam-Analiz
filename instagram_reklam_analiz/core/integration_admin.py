from django import forms
from django.contrib import admin, messages
from django.conf import settings
from django.urls import reverse
from django.utils.html import format_html

from core.models import IntegrationApplication
from core.platform_setup import PLATFORM_SETUP






class IntegrationApplicationForm(forms.ModelForm):
    class Meta:
        model = IntegrationApplication
        fields = "__all__"
        widgets = {
            "client_secret": forms.PasswordInput(render_value=False, attrs={"autocomplete": "new-password"}),
            "developer_token": forms.PasswordInput(render_value=False, attrs={"autocomplete": "new-password"}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for name in ("client_secret", "developer_token"):
            self.fields[name].required = False
            self.fields[name].help_text = "Şifreli saklanır. Kayıtlı değeri korumak için boş bırakın."
        provider = self.data.get("provider") or self.initial.get("provider") or self.instance.provider
        spec = PLATFORM_SETUP.get(provider)
        if provider == "facebook":
            self.fields["client_id"].label = "Meta Uygulama Kimliği (App ID)"
            self.fields["client_id"].help_text = "Meta for Developers → Uygulama ayarları → Temel. Reklam hesabı veya Instagram kimliği değildir."
            self.fields["client_secret"].label = "Meta Uygulama Gizli Anahtarı (App Secret)"
            self.fields["developer_token"].widget = forms.HiddenInput()
        elif provider == "google_ads":
            self.fields["client_id"].label = "Google OAuth İstemci Kimliği"
            self.fields["client_id"].help_text = "Google Cloud → Google Auth Platform → Clients → Web application. .apps.googleusercontent.com ile biter."
            self.fields["client_secret"].label = "Google OAuth İstemci Gizli Anahtarı"
            self.fields["developer_token"].label = "Eski Google Ads geliştirici tokenı (isteğe bağlı)"
            self.fields["developer_token"].help_text = "9 Eylül 2026 öncesinden aktarılmış bir tokenınız varsa geriye dönük uyumluluk için saklayabilirsiniz. Yeni Google Cloud projelerinde boş bırakın."
        self.fields["redirect_uri"].help_text = "Bu adresi sağlayıcının izin verilen OAuth dönüş adreslerine de birebir ekleyin. localhost ile 127.0.0.1 farklı oturumlardır."
        if spec:
            self.fields["client_id"].label = spec["client_label"]
            self.fields["client_secret"].label = spec["secret_label"]
            self.fields["provider"].help_text = spec["capability"]
            self.fields["client_id"].help_text = format_html('{} <a href="{}" target="_blank" rel="noopener">Sağlayıcı panelini aç</a> · <a href="{}" target="_blank" rel="noopener">Resmi kurulum belgesi</a>', spec["instructions"], spec["console"], spec["docs"])
            if provider != "google_ads":
                self.fields["developer_token"].widget = forms.HiddenInput()
            if not spec["callback"]:
                self.fields["redirect_uri"].help_text = "Bu platform için çalışan bir OAuth callback uç noktası henüz yok. Boş bırakabilirsiniz; buraya adres yazmak yeni bir bağlantı akışı oluşturmaz."
            if spec["mode"] == "draft":
                self.fields["enabled"].disabled = True
                self.fields["enabled"].help_text = "Hazırlık kaydı: OAuth/veri aktarımı geliştirilene kadar etkinleştirilemez."

    def clean(self):
        data = super().clean()
        if self.instance.pk and data.get("provider") != self.instance.provider:
            self.add_error("provider", "Kayıtlı platform değiştirilemez; diğer platform için ayrı kayıt açın.")
        for name in ("client_secret", "developer_token"):
            if not data.get(name) and self.instance.pk:
                data[name] = getattr(self.instance, name)
        return data


@admin.register(IntegrationApplication)
class IntegrationApplicationAdmin(admin.ModelAdmin):
    form = IntegrationApplicationForm
    change_list_template = "admin/core/integrationapplication/change_list.html"
    actions = None  # Global CSV actions must never export decrypted credentials.
    list_display = ("provider", "configuration_status", "enabled", "redirect_uri", "updated_at")
    readonly_fields = ("setup_help", "updated_at")

    @admin.display(description="Yapılandırma durumu")
    def configuration_status(self, obj):
        if not obj:
            return "Ayar girilmedi"
        spec = PLATFORM_SETUP[obj.provider]
        if spec["mode"] == "draft":
            return "Hazırlık kaydı — bağlantı henüz uygulanmadı"
        required = [obj.client_id, obj.client_secret]
        if spec["mode"] == "oauth":
            required.append(obj.redirect_uri)
        if not all(required):
            return "Gerekli bilgiler eksik"
        return "Ayar etkin — gerçek erişim ayrıca doğrulanmalı" if obj.enabled else "Bilgiler kayıtlı — devre dışı"

    @admin.display(description="Kurulum")
    def setup_help(self, obj):
        if obj and obj.provider in PLATFORM_SETUP:
            spec = PLATFORM_SETUP[obj.provider]
            return format_html('<p>{}</p><p>{}</p><a href="{}" target="_blank" rel="noopener">Sağlayıcı paneli</a> · <a href="{}" target="_blank" rel="noopener">Resmi belge</a><p>Durum: {}</p>', spec["capability"], spec["instructions"], spec["console"], spec["docs"], self.configuration_status(obj))
        return format_html(
            '<p>Bu bölüm platform uygulamasının ayarlarıdır. Kaydettikten sonra '
            '<a href="{}">Hesap Ekle</a> ekranından giriş yapıp reklam hesabınızı seçin.</p>'
            '<p><a href="https://developers.facebook.com/apps/" target="_blank" rel="noopener">Meta uygulama paneli</a> · '
            '<a href="https://console.cloud.google.com/auth/clients" target="_blank" rel="noopener">Google OAuth istemcileri</a></p>'
            '<p>Sağlayıcıya giriş yapmak gizli anahtarları otomatik olarak bu siteye aktarmaz. '
            'Google mevcut gizli anahtarı tekrar göstermez; kayıtlı anahtarınızı kullanın veya Google panelinde yeni bir anahtar oluşturun.</p>',
            reverse("hesap_ekle"),
        )

    def get_changeform_initial_data(self, request):
        data = super().get_changeform_initial_data(request)
        provider = data.get("provider")
        spec = PLATFORM_SETUP.get(provider)
        if spec:
            if spec["callback"]:
                data["redirect_uri"] = request.build_absolute_uri(spec["callback"])
            data["client_id"] = getattr(settings, spec["env"], "") or ""
        return data

    def changelist_view(self, request, extra_context=None):
        setup_links = []
        if self.has_module_permission(request):
            for code, label in IntegrationApplication._meta.get_field("provider").choices:
                app = IntegrationApplication.objects.filter(provider=code).first()
                url = reverse("admin:core_integrationapplication_change", args=[app.pk]) if app else reverse("admin:core_integrationapplication_add") + "?provider=" + code
                setup_links.append({"name": label, "url": url, "saved": app is not None, "status": self.configuration_status(app), "capability": PLATFORM_SETUP[code]["capability"]})
        return super().changelist_view(request, {**(extra_context or {}), "title": "Hesap bağlantı ayarları", "setup_links": setup_links})

    def has_module_permission(self, request):
        return request.user.is_active and request.user.is_superuser

    def has_view_permission(self, request, obj=None):
        return self.has_module_permission(request)

    def has_change_permission(self, request, obj=None):
        return self.has_module_permission(request)

    def has_add_permission(self, request):
        return self.has_module_permission(request)

    def has_delete_permission(self, request, obj=None):
        return self.has_module_permission(request)

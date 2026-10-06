from django import forms
from django.contrib import admin, messages
from django.conf import settings
from django.urls import reverse
from django.utils.html import format_html

from core.models import IntegrationApplication, CompetitorSourceSetting, Competitor
from core.platform_setup import PLATFORM_SETUP


class CompetitorSourceForm(forms.ModelForm):
    class Meta:
        model = CompetitorSourceSetting
        fields = '__all__'
        widgets = {'credential': forms.PasswordInput(render_value=False, attrs={'autocomplete': 'new-password'})}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['credential'].help_text = 'Şifreli saklanır ve ekranda gösterilmez. Mevcut anahtarı korumak için boş bırakın. Meta resmi API anahtarı boşsa mevcut geçerli Meta bağlantısı kullanılır.'
        platform = self.data.get('platform') or self.initial.get('platform') or self.instance.platform
        if platform:
            self.fields['source'].choices = [(code, label) for code, label in CompetitorSourceSetting.SOURCES
                                            if code in CompetitorSourceSetting.ALLOWED.get(platform, set())]
            self.fields['test_competitor'].queryset = Competitor.objects.filter(platform__code=platform)

    def clean(self):
        data = super().clean()
        if self.instance.pk and data.get('platform') != self.instance.platform:
            self.add_error('platform', 'Platform değiştirilemez; diğer platform için ayrı ayar ekleyin.')
        if self.instance.pk and not data.get('credential') and data.get('source') == self.instance.source:
            data['credential'] = self.instance.credential
        return data


@admin.register(CompetitorSourceSetting)
class CompetitorSourceAdmin(admin.ModelAdmin):
    form = CompetitorSourceForm
    change_list_template = 'admin/core/competitorsourcesetting/change_list.html'
    list_display = ('platform', 'source', 'enabled', 'credential_status', 'countries', 'last_test_at', 'last_test_result')
    readonly_fields = ('setup_help', 'last_test_at', 'last_test_result', 'updated_at')
    fields = ('platform', 'source', 'enabled', 'credential', 'countries', 'setup_help', 'test_competitor',
              'last_test_at', 'last_test_result', 'updated_at')
    actions = ('test_connection',)

    def get_actions(self, request):
        # Global CSV/export actions must never expose decrypted credentials.
        return {name: action for name, action in super().get_actions(request).items() if name == 'test_connection'}

    @admin.display(description='Anahtar durumu')
    def credential_status(self, obj):
        return 'Anahtar kayıtlı' if obj.credential else 'Anahtar girilmedi'

    @admin.display(description='Kaynak kapsamı ve kurulum')
    def setup_help(self, obj):
        return format_html('<p>Bu ayarlar tüm abonelerin rakip reklam çekimini yönetir. Aboneler yalnızca rakibin hesap adını veya web sitesini girer.</p>'
            '<p>Instagram / Facebook: Türkiye’deki ticari reklamlar için SearchApi; resmi Meta API ülke ve reklam türü açısından sınırlıdır. '
            'Google Ads: SerpApi reklam şeffaflık kaynağı. LinkedIn: SearchApi. TikTok: resmi Commercial Content API; Türkiye kapsamda değildir.</p>'
            '<p><a href="https://www.searchapi.io/" target="_blank" rel="noopener">SearchApi hesabı / anahtar</a> · '
            '<a href="https://serpapi.com/manage-api-key" target="_blank" rel="noopener">SerpApi anahtarı</a></p>'
            '<p>Test için aynı platformdaki bir rakibi seçip kaydedin. Listede ayarı işaretleyerek “Bağlantıyı test et” işlemini çalıştırın. '
            'Test en fazla bir reklamın sonucunu kontrol eder; reklamveren eşleşmesi ek sorgular gerektirebilir. Sağlayıcı kotası kullanabilir ve reklamları veritabanına kaydetmez. '
            'Sıfır sonuç bağlantının başarısız olduğu veya rakibin hiç reklamı olmadığı anlamına gelmez. Sonuç, son test anına aittir.</p>')

    def get_changeform_initial_data(self, request):
        data = super().get_changeform_initial_data(request)
        data['source'] = {'instagram': 'searchapi', 'facebook': 'searchapi', 'google_ads': 'serpapi',
                          'linkedin': 'searchapi', 'tiktok': 'tiktok_official'}.get(data.get('platform'), 'searchapi')
        if data.get('platform') in {'instagram', 'facebook'}:
            data['countries'] = 'TR'
        return data

    def changelist_view(self, request, extra_context=None):
        links = []
        if self.has_module_permission(request):
            rows = {row.platform: row for row in CompetitorSourceSetting.objects.all()}
            for code, name in CompetitorSourceSetting.PLATFORMS:
                row = rows.get(code)
                url = reverse('admin:core_competitorsourcesetting_change', args=[row.pk]) if row else reverse('admin:core_competitorsourcesetting_add') + '?platform=' + code
                links.append({'name': name, 'url': url, 'status': ('Etkin' if row.enabled else 'Devre dışı') if row else 'Mevcut sunucu ayarları kullanılıyor',
                              'source': row.get_source_display() if row else '', 'test': row.last_test_result if row else ''})
        return super().changelist_view(request, {**(extra_context or {}), 'setup_links': links})

    @admin.action(description='Bağlantıyı test et (bir reklam; kayıt yapmaz)')
    def test_connection(self, request, queryset):
        from django.utils import timezone
        from core.services.competitor_public_sources import competitor_source
        from core.services.competitor_live_sync import CompetitorSyncError
        if queryset.count() != 1:
            self.message_user(request, 'Test için tek bir platform ayarı seçin.', messages.WARNING)
            return
        obj = queryset.select_related('test_competitor__platform').get()
        if not obj.enabled or not obj.test_competitor:
            self.message_user(request, 'Ayarı etkinleştirin ve aynı platformda bir test rakibi seçip kaydedin.', messages.WARNING)
            return
        try:
            if obj.test_competitor.platform.code != obj.platform:
                raise CompetitorSyncError('Platform eşleşmiyor.')
            source = competitor_source(obj.test_competitor)
            if hasattr(source, 'fetch'):
                rows, _ = source.fetch(1)
            else:
                if not source.token:
                    raise CompetitorSyncError('Token eksik.')
                rows = source._fetch(limit=1).get('data', [])
            result = f'Bağlantı başarılı; {len(rows)} reklam döndü.' if rows else 'Kaynak sorgusu başarılı; bu rakip / ülke için reklam dönmedi. Kaynak kapsamını kontrol edin.'
            level = messages.SUCCESS if rows else messages.WARNING
        except Exception as exc:
            # Provider errors may include credentials; never store or display their text.
            result = 'Bağlantı testi başarısız. Anahtar, API yetkisi, kota, ülke kapsamı ve rakip eşleşmesini kontrol edin.'
            if isinstance(exc, CompetitorSyncError):
                import re
                http = re.search(r'HTTP ([1-5][0-9]{2})\b', str(exc))
                if http:
                    result = 'Sağlayıcı erişim hatası: HTTP ' + http.group(1) + '. Anahtar, API yetkisi ve kota kontrol edilmeli.'
                elif 'eşleştir' in str(exc).casefold():
                    result = 'Reklamveren kesin eşleştirilemedi. Test rakibinin hesap adını ve kayıtlı reklamveren kimliğini kontrol edin.'
                elif 'ağ bağlantısı' in str(exc).casefold():
                    result = 'Sağlayıcıya ağ bağlantısı kurulamadı. Sunucunun dış ağ erişimini kontrol edin.'
            level = messages.ERROR
        obj.last_test_at = timezone.now()
        obj.last_test_result = result
        obj.save(update_fields=['last_test_at', 'last_test_result'])
        self.message_user(request, result, level)

    def save_model(self, request, obj, form, change):
        obj.last_test_at = None
        obj.last_test_result = ''
        super().save_model(request, obj, form, change)
        from core.services.cache_service import CacheService
        for cid, uid in Competitor.objects.filter(platform__code=obj.platform).values_list('pk', 'user_id'):
            CacheService.bump_version('competitors', uid)
            CacheService.bump_version('competitor_ads', uid, cid)

    def has_module_permission(self, request):
        return request.user.is_active and request.user.is_superuser

    def has_view_permission(self, request, obj=None):
        return self.has_module_permission(request)

    def has_change_permission(self, request, obj=None):
        return self.has_module_permission(request)

    def has_add_permission(self, request):
        return self.has_module_permission(request)

    def has_delete_permission(self, request, obj=None):
        return False


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

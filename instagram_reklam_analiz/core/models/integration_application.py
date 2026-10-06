from urllib.parse import urlsplit

from django.core.exceptions import ValidationError
from django.db import models

from core.fields import EncryptedTextField
from core.platform_setup import PLATFORM_CHOICES, PLATFORM_SETUP


class CompetitorSourceSetting(models.Model):
    PLATFORMS = [('instagram', 'Instagram'), ('facebook', 'Facebook'), ('google_ads', 'Google Ads'),
                 ('tiktok', 'TikTok'), ('linkedin', 'LinkedIn')]
    SOURCES = [('searchapi', 'SearchApi reklam kütüphanesi'), ('graph', 'Meta resmi Ad Library API'),
               ('serpapi', 'SerpApi Google Ads Transparency'), ('tiktok_official', 'TikTok Commercial Content API')]
    ALLOWED = {'instagram': {'graph', 'searchapi'}, 'facebook': {'graph', 'searchapi'},
               'google_ads': {'serpapi'}, 'tiktok': {'tiktok_official'}, 'linkedin': {'searchapi'}}
    platform = models.CharField('Platform', max_length=32, unique=True, choices=PLATFORMS)
    source = models.CharField('Reklam kaynağı', max_length=32, choices=SOURCES)
    credential = EncryptedTextField('API anahtarı / erişim tokenı', blank=True, default='')
    countries = models.CharField('Ülkeler', max_length=200, blank=True, default='',
        help_text='ISO ülke kodlarını virgülle ayırın: TR veya DE,FR. Boş bırakılırsa mevcut varsayılan kapsam kullanılır.')
    enabled = models.BooleanField('Rakip reklam çekimi etkin', default=False)
    test_competitor = models.ForeignKey('core.Competitor', verbose_name='Bağlantı testi için örnek rakip',
        null=True, blank=True, on_delete=models.SET_NULL)
    last_test_at = models.DateTimeField('Son bağlantı testi', null=True, blank=True)
    last_test_result = models.CharField('Son test sonucu', max_length=500, blank=True, default='')
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Rakip Reklam Kaynağı'
        verbose_name_plural = 'Rakip Reklam Kaynakları'

    def __str__(self):
        return self.get_platform_display()

    def clean(self):
        import re
        if self.source not in self.ALLOWED.get(self.platform, set()):
            raise ValidationError({'source': 'Bu platform için desteklenen reklam kaynağını seçin.'})
        codes = [c.strip().upper() for c in self.countries.split(',') if c.strip()]
        if any(not re.fullmatch(r'[A-Z]{2}', c) for c in codes):
            raise ValidationError({'countries': 'İki harfli ülke kodlarını virgülle ayırın.'})
        self.countries = ','.join(dict.fromkeys(codes))
        if self.platform in {'google_ads', 'linkedin'} and codes:
            raise ValidationError({'countries': 'Bu kaynak tüm mevcut bölgeleri alır. Ülke alanını boş bırakın.'})
        if self.enabled and self.source != 'graph' and not self.credential.strip():
            raise ValidationError({'credential': 'Bu kaynağı etkinleştirmek için API anahtarı / token girin.'})
        if self.source == 'searchapi' and len(codes) > 1 and self.platform in {'instagram', 'facebook'}:
            raise ValidationError({'countries': 'Meta SearchApi için tek ülke seçin; boş bırakarak varsayılan kapsamı kullanabilirsiniz.'})
        if self.source == 'tiktok_official':
            from core.services.competitor_public_sources import TIKTOK_COUNTRIES
            if set(codes) - TIKTOK_COUNTRIES:
                raise ValidationError({'countries': 'TikTok resmi kaynak Türkiye’yi desteklemiyor. Desteklenen Avrupa ülkesini seçin.'})
        if self.test_competitor_id and self.test_competitor.platform.code != self.platform:
            raise ValidationError({'test_competitor': 'Test rakibinin platformu bu ayarla aynı olmalı.'})

    @classmethod
    def runtime(cls, platform):
        from django.conf import settings
        row = cls.objects.filter(platform=platform).first()
        if row:
            return {'source': row.source, 'credential': row.credential, 'enabled': row.enabled,
                    'countries': row.countries.split(',') if row.countries else cls.default_countries(platform)}
        source = {'instagram': getattr(settings, 'META_COMPETITOR_SOURCE', 'graph'),
                  'facebook': getattr(settings, 'META_COMPETITOR_SOURCE', 'graph'),
                  'google_ads': 'serpapi', 'tiktok': 'tiktok_official', 'linkedin': 'searchapi'}.get(platform)
        env = {'searchapi': 'SEARCHAPI_API_KEY', 'graph': 'META_AD_LIBRARY_ACCESS_TOKEN',
               'serpapi': 'SERPAPI_API_KEY', 'tiktok_official': 'TIKTOK_AD_LIBRARY_ACCESS_TOKEN'}
        return {'source': source, 'credential': getattr(settings, env.get(source, ''), ''),
                'enabled': True, 'countries': cls.default_countries(platform)}

    @staticmethod
    def default_countries(platform):
        from django.conf import settings
        if platform in {'instagram', 'facebook'}:
            return getattr(settings, 'META_AD_LIBRARY_COUNTRIES', ['TR']) or ['TR']
        if platform == 'tiktok':
            return getattr(settings, 'TIKTOK_AD_LIBRARY_COUNTRIES', [])
        return []


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

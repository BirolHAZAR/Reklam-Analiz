# LinkedIn reklam raporlaması hazırlığı — 19 Ekim 2026

## Kapsam

- Ayrı reklam OAuth bağlantısı; yalnızca `r_ads` ve `r_ads_reporting`.
- Mevcut ortak hesap seçimi, ajans müşteri yetkileri ve abonelik kapasitesi kuralları kullanılır.
- Hesaplar `adAccountUsers?q=authenticatedUser` üzerinden bulunur. Yalnız etkin reklam hesapları seçilir.
- Kampanya listesi, dönem toplamı ve günlük gösterim/tıklama/harcama; CTR/CPC ortak raporda hesaplanır. Kampanya/bütçe değişikliği, profil okuma, içerik paylaşımı, lead ve audience işlemleri yoktur.
- Token ve uygulama anahtarı mevcut şifreli alanlarda saklanır. Süresi dolan LinkedIn erişimi yeniden OAuth bağlantısı ister; programatik yenileme ayrı sağlayıcı yetkisi gerektirdiği için varsayılmadı.
- Arka plandaki reklam/kreatif senkronizasyonu ve Octo veri aktarımı bu aşamaya dahil değildir. Yeni okuma akışı ortak kampanya raporunda çalışır.

## Onay beklenirken

Kod henüz canlıda değildir. Hazırlık, LinkedIn'den alınmış erişim onayı anlamına gelmez.

Yayın sonrası yönetici → Platform Ayarları → LinkedIn:

- Client ID: LinkedIn Developers → ReklamAnaliz → Auth bölümündeki değer.
- Client Secret: aynı uygulamadan, yalnız gizli anahtar alanına; belgeye/loga yazılmaz.
- Callback: `https://www.reklamanaliz.net/connect/linkedin/callback/`
- LinkedIn portalı Auth → Authorized redirect URLs listesine aynı adres eklenmelidir.
- `LINKEDIN_ADS_APPROVED=False` varsayılanı OAuth ve veri okumayı engeller. Uygulama bilgileri yönetimde kaydedilebilir; kayıt etkinleştirilse bile onay kapısı açılmadan kullanılamaz.
- `LINKEDIN_ADS_API_VERSION=202610`; mevcut organik paylaşım sürüm ayarından ayrıdır.
- Yönetim kaydı yoksa `LINKEDIN_CLIENT_ID`, `LINKEDIN_CLIENT_SECRET`, `LINKEDIN_REDIRECT_URI` ortam ayarları kullanılabilir. Devre dışı yönetim kaydı ortam ayarlarına sessizce düşmez.

## Onay sonrası canlı doğrulama

1. Advertising API ürün onayını, `r_ads` / `r_ads_reporting` izinlerini ve test kullanıcısının reklam hesabı rolünü kontrol et.
2. Yukarıdaki uygulama bilgilerini ve callback'i eşleştir; `LINKEDIN_ADS_APPROVED=True` yapıp sunucu ayarını uygula.
3. Hesap Ekle → LinkedIn → ajans müşterisi → OAuth → reklam hesabı seçimi.
4. Raporu LinkedIn Campaign Manager ile aynı dönem, UTC günleri ve hesap para biriminde karşılaştır.
5. Boş/dolu kampanyalar, sayfalama, günlük metrikler, reddedilmiş izin, süresi dolmuş erişim ve bağlantı kaldırmayı gerçek API'de doğrula.

Yerel testler gerçek API erişiminin yerine geçmez. Canlı test bu onay gelmeden tamamlanmış sayılmamalıdır.

## Yerel doğrulama

- İzole SQLite/bellek önbelleği ayarları: `config.settings_test_seo`; gerçek API istekleri testlerde taklit edildi, canlı veri değiştirilmedi.
- `core.test_linkedin_ads core.test_ads_integrations core.test_platform_setup`: 65 test başarılı (ilk grup).
- Son ek kontrollerle `core.test_linkedin_ads core.test_platform_setup core.test_integration_application`: 36 test başarılı. Bu grup ilk grupla ortak testler içerir.
- `core.test_linkedin_ads.LinkedInAnalyticsBoundaryTests`: 5 test başarılı; seçilen dönem dışına yuvarlanan tarih, tam dönem yanıtı, 15.000 satır kesilme sınırı, bozuk kampanya takvimi ve kampanya durum etiketleri kontrol edildi.
- Django sistem kontrolü ve `git diff --check` başarılı. Yeni veritabanı şeması/migrasyonu gerekmedi.
- Kullanıcı yeni commit için `7` numarasını seçti. LinkedIn hazırlığı ve geliştirme açılış düzeltmeleri `reklamanaliz V1.2.7` kapsamında kaydedilir; canlı dağıtım yapılmadı. Önceki commit `reklamanaliz V1.2.6` (`36e332cf`).

Resmî kaynaklar:

- https://learn.microsoft.com/en-us/linkedin/shared/authentication/authorization-code-flow
- https://learn.microsoft.com/en-us/linkedin/marketing/integrations/ads/account-structure/create-and-manage-account-users
- https://learn.microsoft.com/en-us/linkedin/marketing/integrations/ads/account-structure/create-and-manage-campaigns
- https://learn.microsoft.com/en-us/linkedin/marketing/integrations/ads-reporting/ads-reporting

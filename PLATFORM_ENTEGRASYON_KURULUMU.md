# Platform entegrasyonları

Giriş → `/integrations/` → Google Ads veya Meta Ads → resmi izin ekranı →
erişilebilir reklam hesabı seçimi → Kampanyalar → Kampanya detayı → son 30 günün
gerçek performans verileri. Ajans kullanıcıları önce müşteriyi seçer.

## Google Ads

Sunucu ortam değişkenleri:

```dotenv
GOOGLE_ADS_CLIENT_ID=
GOOGLE_ADS_CLIENT_SECRET=
GOOGLE_ADS_DEVELOPER_TOKEN=
GOOGLE_ADS_REDIRECT_URI=https://reklamanaliz.net/connect/google-ads/callback/
GOOGLE_ADS_API_VERSION=v25
```

Developer token kullanıcı OAuth tokenı değildir ve kullanıcı formuna girilmez.
Google Cloud'da Google Ads API etkinleştirilmeli, Web application OAuth istemcisi
oluşturulmalı ve yukarıdaki dönüş adresi birebir kaydedilmelidir. Yerelde ayrı
istemci/dönüş adresi kullanın. İzin ekranında `https://www.googleapis.com/auth/adwords`
kapsamını yapılandırın. Bu kapsam Google tarafından salt okunur olarak
sınırlandırılmamıştır; uygulama entegrasyonu yalnız okuma uç noktalarını çağırır.
Yayın/test kullanıcıları, OAuth doğrulaması ve developer token'ın gerçek hesaplara
erişim seviyesi Google konsolundan doğrulanmalıdır.

Kaynaklar: [OAuth web sunucusu akışı](https://developers.google.com/identity/protocols/oauth2/web-server),
[Google Ads yetkilendirmesi](https://developers.google.com/google-ads/api/rest/auth),
[yönetici hesabı hiyerarşisi](https://developers.google.com/google-ads/api/docs/account-management/get-account-hierarchy).

## Meta Ads

```dotenv
FACEBOOK_APP_ID=
FACEBOOK_APP_SECRET=
FACEBOOK_REDIRECT_URI=https://reklamanaliz.net/connect/facebook/callback/
FACEBOOK_GRAPH_URL=https://graph.facebook.com/v25.0
```

Meta uygulamasında Facebook Login/uygun işletme kullanım senaryosu, birebir OAuth
dönüş adresi ve `ads_read` erişimi yapılandırılmalıdır. Geliştirme modundaki roller,
uygulama incelemesi ve dış müşterilere erişim Meta panelinde doğrulanmalıdır.
Kod kısa tokenı uzun ömürlü tokenla değiştirir, gerçekten verilen izinleri kontrol
eder, `/me/adaccounts` üzerinden aktif reklam hesaplarını listeler. Kişisel
Facebook profili veya Sayfa ID'si reklam hesabı olarak kaydedilmez. Instagram
reklamları da Meta reklam hesabından okunur; organik Instagram bağlantısı ayrıdır.
Ad Library yetkisi bu reklam hesabı bağlantısından bağımsızdır.

Kaynaklar: [Marketing API yetkilendirme](https://developers.facebook.com/docs/marketing-api/get-started/authorization/),
[Insights API](https://developers.facebook.com/docs/marketing-api/insights/).

## Diğer platformların mevcut durumu

| Platform | Bu uygulamadaki gerçek durum |
| --- | --- |
| Instagram | Mevcut token doğrulamalı profesyonel profil/organik akışı korunur. Reklam hesabı için Meta Ads kullanılır. |
| YouTube | Kanal doğrulaması organik bağlantıdır. Reklam kampanyaları Google Ads ile okunur. |
| TikTok | Kullanıcı profili doğrulaması reklam erişimi değildir; reklam sağlayıcısı uygulanmamış. |
| LinkedIn | Profil doğrulaması Advertising API erişimi değildir; reklam sağlayıcısı uygulanmamış. |
| X | Kullanıcı doğrulaması Ads API erişimi değildir; reklam sağlayıcısı uygulanmamış. |
| GA4 | Eski form doğrulanmamış mülk/JSON kaydı yapıyordu; gerçek rapor sağlayıcısı uygulanmadığından yeni bağlantı kapatıldı. |

Kaynaklar: [YouTube reklam raporları](https://developers.google.com/google-ads/api/docs/video/overview),
[YouTube Analytics izinleri](https://developers.google.com/youtube/analytics/reference),
[TikTok kullanıcı kapsamları](https://developers.tiktok.com/docs/en/scopes-overview),
[LinkedIn reklam erişimi](https://www.linkedin.com/help/linkedin/answer/a524477),
[X Ads erişimi](https://docs.x.com/x-ads-api/getting-started/step-by-step-guide),
[GA4 mülk keşfi](https://developers.google.com/analytics/devguides/config/admin/v1/rest/v1beta/accountSummaries/list).

## Doğrulama ve işletim

- Tokens mevcut şifreli model alanlarında saklanır; tarayıcı oturumuna veya HTML'ye konmaz.
- Tek kullanımlık OAuth state kullanıcıya ve oturuma bağlanır; 10 dakikada sona erer.
- Hesap seçim süresi 15 dakikadır. Seçilmeyen bağlantı etkinleşmez.
- Hesap listesi API'den alınır; kullanıcı tarafından gönderilen yabancı ID kabul edilmez.
- Google erişim tokenı refresh token ile yenilenir; Meta süresi bitince kullanıcı yeniden bağlar.
- Manuel developer token ile oluşturulmuş Google hesapları ve eski Facebook profil/sayfa kayıtları reklam erişimi için yeniden OAuth bağlantısı ister. Mevcut kayıtlar silinmez.
- Kampanya sayfaları anlık API okuması yapar; sahte veya örnek performans üretmez.
- Arka plan Google/Meta reklam aktarımı gerçek API verisini kullanır. Google campaign raporları, ad-level kaydı olmayan kampanya türlerini de ayrı kampanya ekranında gösterir.
- Reklam satırlarından kampanya/grup toplamları yeniden hesaplanır. Tekil erişim gibi toplanamayan metrikler bu toplamdan türetilmez.
- OAuth aktarımında raporlanmayan dönüşüm değeri tahmini gelirle doldurulmaz.
- Uygulama ve Celery worker dağıtımdan sonra yeniden başlatılmalıdır. Şema migration'ı gerekmez.

Yerel ortamda 28 Eylül 2026 kontrolü: Google Ads client ID, client secret ve
developer token eksik. Meta uygulama bilgileri var; dönüş adresi localhost.
Canlı konsol yapılandırması ve gerçek hesapla kullanıcı onayı bu çalışma sırasında
doğrulanmadı. Gerçek kabul testi: izin reddi → tekrar bağlantı → hesap seçimi →
kampanya listesi → hesap arayüzüyle aynı tarih/para biriminde performans karşılaştırması.

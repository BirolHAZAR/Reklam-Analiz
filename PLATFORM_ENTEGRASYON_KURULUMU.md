# Platform entegrasyonları

## Bu sürümün canlıya geçişi

- `python manage.py migrate --noinput` ile mevcut `core.0076` dahil migration'ları uygulayın.
- `python manage.py collectstatic --noinput` çalıştırın; web ve Celery süreçlerini yeniden başlatın.
- Canlıda `DEBUG=False` kullanın. Meta dönüş adresinin varsayılanı bu modda
  `https://reklamanaliz.net/connect/facebook/callback/` olur. Ortam değişkeni veya
  yönetici kaydı bu varsayılanı geçersiz kılar; geliştirme ortamının localhost
  değerini canlıya taşımayın. Canlıda localhost adresiyle yeni reklam OAuth akışı başlatılmaz.
- Google Ads ve Meta uygulama bilgilerini ortam değişkenlerinden veya süper yöneticiye
  açık `/admin/core/integrationapplication/` ekranından tamamlayın. Veritabanı ayarı
  varsa önceliklidir. Platform konsolundaki izinli dönüş adresiyle birebir eşleştirin.
- `/integrations/` ekranında iki sağlayıcının bağlantı düğmesini, ardından gerçek
  kullanıcı izni → hesap seçimi → kampanya okuma akışını doğrulayın.

Dağıtım, eksik platform anahtarlarını veya sağlayıcı izinlerini oluşturmaz.
Geliştirme ortamında localhost kullanılabilir. Süresi dolan Meta bağlantıları
yeniden yetkilendirme ister; yenileme tokenı olan Google bağlantıları yenilenebilir.
Bu sürüm için 30 entegrasyon testi izole test veritabanında geçti; gerçek sağlayıcı
izinleri bu testlerin kapsamı dışındadır.

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

## Veritabanı token şifreleme denetimi

Yerel ham kolon denetimi: 68 platform access/refresh tokenı ve 13 pazaryeri/ödeme
gizli alanı, toplam 81 dolu değer şifreli. Düz metin ve çözülemeyen değer sayısı
sıfır. `TOKEN_ENCRYPTION_KEY` mevcut; anahtar değeri veya tokenlar yazdırılmadı.
Bağlantı/hesap metadata JSON alanlarında bilinen token/secret anahtarları altında
düz metin kopya bulunmadı. Allauth SocialToken tablosu boş; giriş tokenlarının düz
metin tabloda gelecekte saklanmaması için `SOCIALACCOUNT_STORE_TOKENS=False` açıkça ayarlandı.

Canlıda aynı kod ve mevcut şifreleme anahtarıyla:

```sh
python manage.py audit_token_encryption
```

Komut yalnızca alan adları ve sayıları gösterir; okunamayan veya düz metin değer
varsa başarısız çıkış kodu verir. Eski EncryptedTextField kolonlarında düz metin
bulunursa mevcut anahtarı değiştirmeden:

```sh
python manage.py audit_token_encryption --encrypt-legacy
python manage.py audit_token_encryption
```

Dönüşüm tek transaction içinde yapılır, her değerin şifreleme/çözme eşitliği
kontrol edilir. Mevcut şifreli değerler yeniden şifrelenmez. Okunamayan şifreli
veri veya şifrelemeyi desteklemeyen dolu token kolonu varsa dönüşüm geri alınır.
Şifreleme anahtarını yenilemek bu komutun görevi değildir; eski anahtar olmadan
mevcut şifreli kayıtlar çözülemez. Bu komut JSON/log/backupların tamamını taramaz.

## Test notu

Entegrasyon, Octo senkronizasyonu, demo arka plan ve senkronizasyon politikası için
36 test geçti. Geniş ajans paketindeki iki eski test 13 Temmuz 2026 tarihli veri
kullandığından güncel 30 günlük rapor penceresinde başarısız; ilgili rapor tarihi
13 Temmuz'a sabitlenerek ikisi de doğrulandı. Üretim rapor tarihleri değiştirilmedi.
# Canlı yönetim panelinden uygulama ayarları

`core.0076_integrationapplication` migration'ından sonra süper yönetici,
`/admin/core/integrationapplication/` üzerinden Google Ads ve Meta uygulama
ayarlarını yönetebilir. Entegrasyonlar sayfasında bu bölüme bağlantı bulunur.
Uygulama gizli anahtarı ve Google geliştirici tokenı mevcut `EncryptedTextField`
ile şifrelenir; düzenleme formunda kayıtlı değer gösterilmez. Boş bırakmak
kayıtlı gizli değeri korur. Bu ekran yalnızca süper yöneticiye açıktır.

Platform için bir veritabanı ayarı varsa ortam değişkenlerinden önce kullanılır.
Kaydın kapatılması ortam değişkenine geri dönmez; yeni bağlantıyı durdurur.
Kayıt yoksa mevcut ortam değişkenleri kullanılmaya devam eder.
Bu ayarlar geliştirici hesabını, platform API onayını veya kullanıcı OAuth
iznini oluşturmaz; gerçek platform uygulama bilgileri gereklidir.

28 Eylül 2026 canlı panel kontrolünde Google Ads kurulumu eksik, Meta bağlantı
düğmesi kullanılabilir ve allauth sosyal uygulama listesi boştu. OAuth ile
bağlanmış reklam hesabı görünmedi. Bu bulgu Meta API erişiminin doğrulandığı
anlamına gelmez. Bu değişiklik henüz canlıya dağıtılmadı.

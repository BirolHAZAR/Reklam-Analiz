# Platform entegrasyonları

## Instagram Login: canlıya çıkış hazırlığı

Üye akışı: Hesap Ekle → Instagram'ı bağla → Instagram izni → bağlı hesaplar.
Ajans üyeleri bağlantıdan önce müşterisini seçer. Üyeden token, uygulama kimliği
veya gizli anahtar istenmez. Instagram bağlantısı organik profil ve istatistik
okuma içindir; reklam verileri Meta Ads bağlantısından alınır.

Canlı sunucuda aşağıdaki tek seferlik yönetici ayarları gerekir:

- Migration'ları uygulayın; bu çalışma grubunda `0078_local_display_names` de vardır.
- Instagram uygulama kimliği ve gizli anahtarını canlı admin panelindeki Instagram
  kaydına girin ve bağlantıyı etkinleştirin. Facebook App Secret ile karıştırmayın.
- Dönüş adresini `https://reklamanaliz.net/connect/instagram/callback/` yapın.
  Meta Instagram Business Login ayarında da aynı adresi kaydedin.
  Yerel veritabanındaki `127.0.0.1:8443` ayarı canlıya kopyalanmamalıdır.
- Ortam değişkenleri kullanılacaksa `INSTAGRAM_APP_ID`, `INSTAGRAM_APP_SECRET`,
  `INSTAGRAM_REDIRECT_URI` tanımlayın. Admin kaydı varsa ortam değişkenlerinden
  önceliklidir; kapalı bir admin kaydı ortam değişkenleriyle aşılmaz.
- Canlı ayarlarla `python manage.py check_instagram_setup` çalıştırın.
  Bu komut değişiklik yapmaz, anahtarları göstermez ve Meta'ya istek göndermez.
- Web/Celery süreçlerini güncelleyin ve mevcut platform token bakım görevinin
  çalıştığını doğrulayın. Instagram Login tokenları Instagram üzerinden yenilenir.
- Meta incelemesinde `instagram_business_basic` ve
  `instagram_business_manage_insights` izinlerini tamamlayın. Uygulama modunu
  ve dış kullanıcı erişimini Meta onayına göre açın.
- Gerçek profesyonel test hesabıyla izin → dönüş → hesap kaydı → organik veri
  okuma akışını, ardından rolü olmayan bir aboneyle bağlantıyı doğrulayın.

Otomatik testler sağlayıcı yanıtlarını taklit ederek akışı ve hata durumlarını
sınar; gerçek Meta onayının veya uçtan uca bağlantı testinin yerine geçmez.
Yerel `start_dev_https.py` ve yerel sertifikalar canlı dağıtımda kullanılmaz.

## Sekiz platform için merkezi admin ayarları

`/admin/core/integrationapplication/` ekranında Meta, Google Ads, Instagram,
YouTube, TikTok, LinkedIn, X ve GA4 sıralı kartlar olarak sunulur. Platforma özel
kimlik/gizli anahtar etiketleri, sağlayıcı paneli, resmi belge ve gerçek uygulama
desteği gösterilir. Boş veya eksik bilgiler etkin olmayan taslak olarak kaydedilebilir.
Gizli değerler şifreli saklanır; boş bırakmak mevcut değeri korur. Bu modelde
genel CSV dışa aktarma ve toplu etkinleştirme eylemleri kapalıdır.

`core.0077_expand_platform_application_settings` migration'ı yerelde uygulandı;
canlıya dağıtımda `python manage.py migrate --noinput` çalıştırılmalıdır.
Google Ads, Meta ve Instagram OAuth servislerini kullanır. Instagram ayarı
giriş ve token bakım servisinin uygulama kimliği/gizli anahtar kaynağıdır; kayıt yoksa
ortam değişkenleri kullanılır. Diğer beş platformun uygulama OAuth akışı bu
çalışmayla eklenmedi: ayarlar hazırlık olarak saklanır ve etkinleştirme engellenir.
Çalışmayan callback adresleri otomatik üretilmez. Sosyal oturum açma ayarları
(allauth) ve kullanıcıya ait hesap/token kayıtları bu ayarlardan ayrıdır.

Güncel kullanıcı akışı: `/platform-connections/` → **Hesap ekle** →
Google Ads veya Meta **Bağla** → resmi izin ekranı → hesap seçimi → bağlı hesaplar.
Kampanyalar hesap satırından açılır. Ayrı Entegrasyonlar sayfası kaldırıldı;
eski `/integrations/` adresi bağlı hesaplara yönlenir. Uygulama ayarları
süper yöneticiye hem bağlı hesaplar hem hesap ekleme ekranında sunulur.
Ajans kullanıcıları reklam hesabını bağlamadan önce müşteri seçer.

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

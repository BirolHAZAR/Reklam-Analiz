# YouTube ve GA4 Google OAuth doğrulama paketi

2 Ekim 2026. Proje: `reklam-analiz-youtube-ga4`. Google Ads'in ayrı ve incelemedeki projesi değiştirilmedi.

## Son durum: Google incelemesine alındı

2 Ekim 2026: hesap sahibi son uygunluk beyanlarını ve gönderimi açıkça onayladı. Google Verification Center **Your app's data access is under review** gösteriyor. Verification progress: **The Trust and Safety team has received your form**. Yedi kontrolün tümü in progress: ana sayfa, gizlilik, uygulama işlevleri, marka, uygun veri erişimi, asgari kapsamlar ve ek gereksinimler. Google ekranı ilk e-posta için 3–5 gün, toplam inceleme için 4–6 haftaya kadar süre belirtiyor; kesin tarih taahhüdü değildir. Bu durum gönderimin alındığını gösterir, izinlerin onaylandığı anlamına gelmez. Demo: https://youtu.be/NCXjtHhNOac. Ekran kanıtı: `youtube-ga4-google-incelemede.png`.

Aşağıdaki notlar önceki hazırlık aşamalarını da içerir; güncel durum bu bölümdür.

## Tamamlananlar

Yeni demo videosu: https://youtu.be/NCXjtHhNOac (`Google youtube analic`, 3:36, Liste dışı). Link tarayıcıda oynatılabilir; kontrol edilen Google izin sahnesi İngilizce. 834 karakterlik İngilizce kapsam gerekçesi ve video URL'si Google Data Access ekranına kaydedildi; “Data access changes saved!” doğrulandı. Ek açıklama formuna iki ayrı istemci, üretim testleri, gizlilik açıklaması ve ayrı Google Ads projesi bilgisi eklendi. Son Verification Questionnaire açıldı; kişisel kullanım / dahili kullanım / yalnız test / Gmail SMTP soruları No olarak seçildi. Uygunluk beyanları ve son gönderim hesap sahibinin açık onayını bekliyor; başvuru henüz gönderilmiş değildir.

Son ilerleme: Gizlilik politikasına YouTube/GA4 kapsamı ve Google API Sınırlı Kullanım bölümleri eklenerek 1.1 sürümü 2 Ekim 2026 tarihinde canlıda yayımlandı. Oturum açmamış kullanıcı için HTTP 200 ve iki okuma kapsamının metinde bulunması doğrulandı. Önceki içerik yedeklendi. Başlangıç metni `core/legal_defaults.py` içinde de güncellendi; canlı değişiklik veritabanında uygulanmıştır.

YouTube ve GA4 üretim sonrası kullanıcı tarafından yeniden yetkilendirildi. Mevcut PlatformAccount 81 ve 82 korundu; yeni bağlantılar sırasıyla 57 ve 58. Her iki yeni bağlantının gerçek token yenilemesi ve seçilen kanal/mülkün API üzerinden keşfi başarılı. Worker ping başarılı. GA4 worker görevi `242b1bb5-6f91-4746-8194-18d1aaf8d3d9` SUCCESS: 1 mülk, 0 günlük metrik, 0 açılış sayfası satırı. Google hâlâ son 30 tamamlanmış gün için rapor satırı dönmüyor; ölçüm veya trafik varlığı doğrulanmış değildir. Google Ads/Meta/Instagram ayarları değiştirilmedi.

- YouTube ve GA4 canlı bağlantı, gerçek API okuması ve token yenilemesi doğrulandı.
- Google Auth Platform ana sayfa, gizlilik ve kullanım koşulları adresleri kaydedildi.
- Yalnızca `youtube.readonly` ve `analytics.readonly` beyan edildi. Google ikisini hassas kapsam olarak sınıflandırdı.
- Hesap sahibinin açık onayıyla yayın durumu **In production** yapıldı.
- Otomatik marka doğrulaması başarılı. Hesap sahibinin ayrı açık onayıyla marka yayımlandı; Google “Your branding has been verified and is being shown to users” sonucunu gösterdi.
- Hassas veri inceleme formu açıldı. Gerçek form, kapsam gerekçesi ve demo videosunu zorunlu istiyor. Ortak gerekçe alanı 1000 karakter; iki kapsamı açıklayan 834 karakterlik İngilizce metin forma yerleştirildi. Demo URL'si olmadığı için Save düğmesi hâlâ devre dışı; gerekçe henüz kaydedilmiş veya incelemeye gönderilmiş değildir. Açık form sonraki adım için bırakıldı.

## İnceleme formu için İngilizce kapsam gerekçeleri

### https://www.googleapis.com/auth/youtube.readonly

Reklam Analiz lets a signed-in user connect their own YouTube channel and view the channel identity and basic channel statistics in the platform connections dashboard. We call YouTube Data API v3 channels.list with mine=true and part=snippet,statistics to discover the user's available channel and store the selected channel identifier, display name and basic statistics. Read-only authorization is needed to identify the user's own channel. An API key alone cannot discover the authenticated user's channel. We do not upload videos, edit or delete content, or request YouTube Analytics permissions. The read-only scope is the narrowest scope supported for this feature.

### https://www.googleapis.com/auth/analytics.readonly

Reklam Analiz lets a signed-in user select an accessible Google Analytics 4 property and view aggregated daily and landing-page performance reports. We use the Google Analytics Admin API to discover accessible properties and the Google Analytics Data API to retrieve reports for the last 30 completed days. Reports are synchronized in the background every four hours. The selected property and its aggregated reporting data are displayed in the Analytics dashboard. We do not modify properties, settings or tracking configuration. The analytics.readonly scope is the narrowest scope that supports both property discovery and read-only reporting.

## Önceki gizlilik eki taslağı

Google bağlantıları kullanıcı tarafından OAuth 2.0 ile yetkilendirilir. YouTube bağlantısında kullanıcının seçtiği kanalın kimliği, adı ve temel kanal istatistikleri; Google Analytics 4 bağlantısında erişilebilir mülk bilgileri ve seçilen mülke ait toplulaştırılmış günlük ve açılış sayfası raporları alınır. Bu veriler bağlantı yönetimi, senkronizasyon ve kullanıcıya görünen raporlama özellikleri için kullanılır. Bu bağlantılar salt okunurdur; YouTube içeriği veya Analytics ayarları değiştirilmez. Erişim ve yenileme belirteçleri şifreli saklanır. Google API verileri satılmaz ve genel amaçlı yapay zekâ modeli eğitimi için kullanılmaz. Veriler yalnızca ilgili özelliği sağlayan altyapı işleyenleriyle, kullanıcının açık talimatıyla veya hukuki zorunluluk kapsamında paylaşılır. İnsan erişimi açık kullanıcı izni, güvenlik, destek veya hukuki gereklilik gibi sınırlı durumlarla kısıtlanır. Kullanıcı uygulamadan veya Google Hesabı üçüncü taraf erişim ayarlarından erişimi kaldırabilir; silme taleplerini info@reklamanaliz.net adresine gönderebilir. Reklam Analiz'in Google API'lerinden aldığı bilgileri kullanması ve diğer uygulamalara aktarması, Sınırlı Kullanım koşulları dahil Google API Services User Data Policy'ye tabidir: https://developers.google.com/terms/api-services-user-data-policy.

Canlı politika 1.1 olarak güncellendi. Yayımlanan kesin metin `core/legal_defaults.py` dosyasının gizlilik politikası 8 ve 9. bölümlerindedir. Buradaki önceki taslak referans içindir.

## Yeni İngilizce demo videosu

Mevcut Google Ads videosu bu iki yeni istemciyi ve iki özelliği göstermediğinden bu başvuru için yeterli değildir. Yeni videoyu liste dışı yükleyin. Şifre, client secret, token veya doğrulama kodunu kayda dahil etmeyin.

1. İngilizce Google izin ekranı kullanılacak şekilde tarayıcı/Google dili seçilir. Reklam Analiz ana sayfası, gizlilik bağlantısı ve uygulama amacı gösterilir.
2. Platform Bağlantıları → YouTube bağlantısı başlatılır. Reklam Analiz uygulama adı, izin metni ve adres çubuğundaki YouTube OAuth client ID gösterilir. Kullanıcı kendi izin adımlarını tamamlar.
3. Kanal seçimi ve bağlı kanalın adı/temel istatistiklerinin uygulamadaki kullanımı gösterilir.
4. Platform Bağlantıları → Google Analytics 4 bağlantısı başlatılır. Aynı şekilde uygulama adı, Analytics okuma izni ve ayrı GA4 client ID gösterilir. Kullanıcı izin adımlarını tamamlar.
5. Mülk seçimi, Analytics merkezi, günlük/açılış sayfası rapor alanları ve son senkron gösterilir. Bağlı mülk son 30 gün için 0 satır döndürdüğünden verisi bulunan yetkili bir mülk varsa onu kullanın; veri yoksa bunu dürüstçe belirtin.
6. Bağlantı yönetimi ve erişimin kaldırılabileceği yer gösterilir. Sırf video için mevcut bağlantıyı silmeyin.

Anlatım: “Reklam Analiz is a reporting dashboard. Users explicitly connect their own YouTube channel or Google Analytics property. Both integrations request read-only access. YouTube is used to show channel identity and basic statistics. Google Analytics is used to show aggregated property reports. The application does not modify YouTube content or Analytics settings.”

## Sonraki adımlar

1. Marka doğrulama ve yayını tamamlandı.
2. Gizlilik metninin YouTube/GA4 kapsamı ve anonim canlı erişimi tamamlandı.
3. Verification Center → Prepare for verification formunun gerçek alanlarını kontrol et; yukarıdaki gerekçeleri kullan.
4. İki bağlantıyı gösteren yeni İngilizce liste dışı demo URL'sini ekle. Formda gereken tüm beyanları somut olarak incelemeden son gönderimi yapma.
5. Google incelemesi gönderildikten sonra sonucu Google belirler; gönderim, onay anlamına gelmez.
6. Üretimden sonra her iki hesap yeniden yetkilendirildi ve yeni tokenların yenilenmesi doğrulandı. Sürekli bağlantı, kullanıcının izni iptal etmesi veya Google'ın tokenı iptal etmesi halinde garanti edilemez.

Resmi kaynak: https://developers.google.com/identity/protocols/oauth2/production-readiness/sensitive-scope-verification

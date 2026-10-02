# YouTube ve Google Analytics 4 bağlantıları

## Son durum — 2 Ekim 2026

YouTube/GA4 hassas okuma izinleri başvurusu, https://youtu.be/NCXjtHhNOac demo videosu ve İngilizce gerekçelerle Google incelemesine alındı. Verification Center: **Your app's data access is under review**; Trust and Safety formun alındığını doğruluyor. Üretim durumu, yayımlanmış marka, 1.1 gizlilik politikası ve iki hesabın üretim sonrası token yenileme kontrolleri tamamlandı. Google'ın nihai izin onayı henüz verilmedi. Mevcut Google Ads/Meta/Instagram ayarları korundu.

## Üretim ve doğrulama ilerlemesi — 2 Ekim 2026

Gizlilik politikası YouTube/GA4 ve Google Sınırlı Kullanım bölümleriyle 1.1 olarak canlıda yayımlandı; anonim HTTP 200 kontrolü başarılı. İki hesap üretim sonrası yeniden yetkilendirildi; yeni bağlantılar YouTube 57 / GA4 58. Her ikisinin gerçek token yenilemesi ve API keşfi başarılı. GA4 worker işi `242b1bb5-6f91-4746-8194-18d1aaf8d3d9` SUCCESS (1 mülk, 0 günlük metrik, 0 açılış sayfası satırı). Mevcut hesap kimlikleri ve Google Ads/Meta/Instagram ayarları korundu. Kalan başvuru girdisi iki istemciyi ve iki özelliği gösteren yeni İngilizce demo videosudur; hassas kapsam incelemesi henüz gönderilmedi.

Yeni YouTube/GA4 projesi, hesap sahibinin açık onayıyla **In production** durumuna geçirildi. Ana sayfa, gizlilik ve kullanım koşulları bağlantıları kaydedildi; yalnızca `youtube.readonly` ve `analytics.readonly` izinleri beyan edildi. Otomatik marka doğrulaması ve açık onayla marka yayını tamamlandı. Hassas kapsam inceleme formu açıldı; İngilizce gerekçe yerleştirildi fakat zorunlu yeni demo videosu eksik olduğundan kaydedilemedi veya gönderilemedi. İngilizce gerekçeler, yeni demo adımları ve gizlilik eki taslağı `YOUTUBE_GA4_DOGRULAMA_PAKETI.md` dosyasında hazır. Testing sırasında verilen tokenların süresinin otomatik uzadığı varsayılmamalı; üretim sonrası yeniden yetkilendirme doğrulanmalı.

## Önceki canlı sonuç — 2 Ekim 2026, 15:00 (Türkiye)

- YouTube: Birol HAZAR kanalı bağlı. Gerçek API okuması ve otomatik token yenilemesi başarılı; worker yanıt veriyor. HTTP 401 / invalid_client hatası yanlış gizli anahtarın hesap sahibi tarafından düzeltilmesiyle giderildi.
- GA4: Google Analytics Admin API ve Data API etkin. Ayrı Web OAuth istemcisi `Reklam Analiz GA4 Web` oluşturuldu; gizli anahtar hesap sahibi tarafından şifreli uygulama ayarına kaydedildi. Google izin ve mülk seçim adımları tamamlandı.
- Bağlı GA4 mülkü `Akbeniz Yeni - GA4`, property ID `389050718`, PlatformAccount 82, yerel AnalyticsProperty 5. Mülk keşfi ve gerçek token yenilemesi başarılı.
- İlk aktarım gerçek worker üzerinden `SUCCESS` ile tamamlandı: 1 mülk, 0 günlük metrik satırı, 0 açılış sayfası satırı. Google son 30 tamamlanmış gün için veri döndürmedi; bu sonucun veri toplama kurulumundan mı yoksa mülkte trafik olmamasından mı kaynaklandığı henüz belirlenmedi. Analytics detay ekranında son senkron 15:00 olarak doğrulandı.
- Google Ads / Meta / Instagram uygulama ayarları değiştirilmedi. GA4 aktarımı 4 saatte bir planlıdır; aynı hesap için kilit ve kota bekleme mekanizması mevcuttur.
- Uzun süreli erişim henüz tamamlanmış değildir: yeni Google Cloud projesi External / Testing durumunda. Üretim yayını ve gerekli Google doğrulaması tamamlanmalıdır; test durumundaki bu okuma izinlerinin yenileme tokenları 7 günlük sınıra tabidir.

Aşağıdaki ilk kurulum notları, bu güncel sonuçtan önceki aşamaları da içerir.

2 Ekim 2026: Uygulama geliştirmesi `ae5317eb` canlıya alındı. Web, worker ve beat aynı `sha256:a1cc945324f81f34fbd371546d5cea03914a29fb769fa34a0643c041a04a261d` imajında doğrulandı. Veritabanı kontrolü, iki callback yolu, GA4 planı ve worker görevi başarılı. Mevcut Google Ads kampanya okuması başarılı (0 kampanya); mevcut platform ayarları korunuyor. OAuth istemci bilgileri ve kullanıcı izinleri henüz tamamlanmadığı için YouTube ve GA4 hesapları henüz bağlanmış değildir.

Google Ads'in incelemedeki projesi ve mevcut Meta/Instagram ayarları değiştirilmedi. Yeni Google Cloud projesi: `reklam-analiz-youtube-ga4` (Reklam Analiz YouTube GA4). Billing veya ücretli ürün eklenmedi.

## 1. YouTube

2 Ekim 2026 canlı tanısı: API etkinleştirildi, Web OAuth istemcisi oluşturuldu ve uygulama ayarı etkin olarak kaydedildi. Hesap bağlama denemesi HTTP 401 ile sonuçlandı. Gizli anahtar gösterilmeden yapılan kontrol, kayıtlı client_secret değerinin istemci kimliği biçiminde olduğunu belirledi; Google token uç noktası `invalid_client` döndürdü. Google Cloud istemci ayrıntıları ile uygulamanın YouTube ayar formu hesap sahibinin doğru client secret değerini doğrudan girmesi için açıldı. Gizli anahtar düzeltmesi ve gerçek kanal bağlantısı henüz tamamlanmadı. Mevcut Google Ads / Meta / Instagram ayarları değiştirilmedi.

1. Yeni projede YouTube Data API v3'ü etkinleştir. Ekran API hizmet şartlarını belirtiyor; bu adım hesap sahibi tarafından onaylanmalıdır.
2. Google Auth Platform marka/izin ekranını Reklam Analiz olarak yapılandır. Site, gizlilik ve hizmet şartları adreslerini mevcut resmi site üzerinden kullan.
3. Sadece `https://www.googleapis.com/auth/youtube.readonly` izniyle Web application OAuth istemcisi oluştur.
4. Tam dönüş adresi: `https://www.reklamanaliz.net/connect/youtube/callback/`.
5. İstemci kimliği ve gizli anahtarı uygulamanın Yönetim → Platform Ayarları → YouTube bölümünde sakla. Gizli anahtarı sohbet veya Git'e yazma.
6. Hesap Ekle → YouTube bağla → Google izin ekranı → kanal seçimini tamamla.
7. Canlı kanal kimliğini doğrula; token yenileme ve worker sağlık kontrolünü çalıştır.

Bu izin kanal bilgileri ve temel kanal istatistikleri içindir. Video yükleme ve YouTube Analytics raporları eklenmedi. YouTube reklamları mevcut Google Ads bağlantısı üzerinden okunur.

## 2. Google Analytics 4

2 Ekim 2026 GA4 bağlantısı tamamlandı: Admin API ve Data API etkin, ayrı `Reklam Analiz GA4 Web` istemcisi oluşturuldu ve hesap sahibi uygulama ayarını kaydetti. `Akbeniz Yeni - GA4` mülkü (`389050718`) admin kullanıcısı için PlatformAccount 82 olarak bağlı. Gerçek mülk keşfi başarılı; refresh token mevcut ve otomatik yenileme canlıda doğrulandı. İlk gerçek worker işi `b6956ccb-aeaa-4928-a71d-c6d48cca2eb1` SUCCESS döndü: 1 mülk, 0 günlük metrik satırı, 0 açılış sayfası satırı. Son 30 tamamlanmış gün sorgusunda Google rapor satırı dönmedi; veri varlığı veya ölçüm etiketinin çalışması bu sonuçla doğrulanmış değildir. Planlanan aktarım 4 saatte birdir. Üretim / OAuth doğrulaması halen tamamlanmalıdır.

2 Ekim 2026 YouTube bağlantısı tamamlandı: hesap sahibi gizli anahtarı düzeltti ve Google izin / kanal seçimi akışını tamamladı. `Birol HAZAR` kanalı (`UCpuF9km8_KWE_x-0o0B0TrQ`) canlıda PlatformAccount 81 olarak bağlı. Gerçek kanal okuması başarılı. Yeni bağlantı üzerinde otomatik token yenilemesi çalıştırıldı ve yenilenen token ile kanal tekrar başarıyla okundu. Önceki HTTP 401 / invalid_client engeli giderildi. Google projesi halen Testing durumunda; üretim ve doğrulama adımları tamamlanmadan uzun süreli bağlantı sonucu verilemez.

1. Yeni projede Google Analytics Admin API ve Google Analytics Data API'yi etkinleştir.
2. `https://www.googleapis.com/auth/analytics.readonly` izni için ayrı Web application OAuth istemcisi oluştur.
3. Tam dönüş adresi: `https://www.reklamanaliz.net/connect/google-analytics/callback/`.
4. İstemci bilgilerini Yönetim → Platform Ayarları → Google Analytics 4 bölümünde sakla.
5. Hesap Ekle → Google Analytics 4 bağla → Google izin ekranı → erişilebilir GA4 mülkünü seç.
6. İlk gerçek raporu worker üzerinden çalıştır ve Analytics ekranında günlük/açılış sayfası verilerini doğrula.

Raporlar son 30 tamamlanmış gün için gelir. Günlük raporda oturum, aktif/yeni kullanıcı, etkileşim, sayfa görüntülemesi, olay, önemli olay ve gelir okunur. Arka plan aktarımı 4 saatte bir planlanır; aynı hesabın eşzamanlı aktarımı kilitle engellenir.

## Süreklilik ve sınırlar

- Erişim tokenı otomatik yenilenir; refresh token şifreli saklanır. Kullanıcı izni kaldırırsa veya Google refresh tokenı iptal ederse yeniden yetkilendirme gerekir.
- Testing durumundaki harici OAuth projesinde bu izinlerin refresh tokenları 7 gün sonra sona erebilir. Uzun süreli kullanım için üretim yayın durumu ve gerekli Google doğrulaması tamamlanmalıdır.
- İstekler 30 saniye zaman aşımına sahiptir. 429 ve kota hatalarında bekleme kaydı tutulur, bağlantı silinmez. Google'ın kotalarına hiç takılmama garantisi verilemez.
- OAuth state, kullanıcı sahipliği, izin reddi, kalıcı erişim, doğru istemciyle yenileme, doğrulanmış mülk seçimi, sayfalama, rapor dönüşümü ve worker kaydı test edildi. Önceki Google Ads/Meta/Instagram testleriyle birlikte 86 test başarılı.

Resmi belgeler: [YouTube OAuth](https://developers.google.com/youtube/v3/guides/auth/server-side-web-apps), [Google refresh token koşulları](https://developers.google.com/identity/protocols/oauth2#expiration), [GA4 Admin](https://developers.google.com/analytics/devguides/config/admin/v1/rest/v1beta/accountSummaries/list), [GA4 Data API](https://developers.google.com/analytics/devguides/reporting/data/v1/api-schema).

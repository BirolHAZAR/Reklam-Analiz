# Abone platform bağlantıları ve API izin denetimi — 9 Ekim 2026

## Sonuç
Tüm platformlar için aboneler hesaplarını sorunsuz bağlayıp reklamlarını çekebilir sonucu verilemez. Canlı ayarların olması, uygulama sahibi hesabının çalışması veya bir bağlantının aktif görünmesi dış müşteriler için izin onayı değildir.

## Güncel bulgular
| Platform | Canlı yapılandırma / işlev | Sağlayıcı onayı / engel | Aboneye reklam aktarımı |
|---|---|---|---|
| Meta Ads / Facebook | Etkin OAuth; App ID 1319084260344652; callback https://reklamanaliz.net/connect/facebook/callback/ sağlayıcıyla aynı. Mevcut admin bağlantısında canlı kampanya listesi başarılı; bir kampanyanın 10 Eylül–9 Ekim günlük performans ekranı hata olmadan açıldı. Bu örnek performansın dolu olduğunu kanıtlamaz. | App Mode Development. ads_read Standard Access, No App Review requested. Marketing API Access Tier Limited access. Başvuru taslağı mevcut fakat Submit for review kapalı. İşletme In review. | Mevcut rol/yetkili hesabın okuması çalışıyor; rolü olmayan aboneye hazır değil. |
| Instagram | Etkin ayrı OAuth; Instagram App ID 1518278343095525; callback https://reklamanaliz.net/connect/instagram/callback/ eşleşiyor. Kod instagram_business_basic ve instagram_business_manage_insights istiyor. | basic Standard; taslak mevcut, gönderilmemiş. manage_insights Standard, Ready to use (0), Request advanced access kapalı. Ayrı business login settings içinde Deauthorize callback URL ve Data deletion request URL boş. | Reklamlar Meta Ads üzerinden alınır. Organik profesyonel hesap bağlantısı için dış kullanıcı onayı tamam değil. |
| Google Ads | Etkin OAuth; istemci 346819732863-tu90fkivksltrb3s7ienk4ansa950nf8.apps.googleusercontent.com; www callback sağlayıcıyla aynı. Google Ads API erişimi Explorer: 2.880 üretim işlemi/gün, 15.000 test işlemi/gün. | Marka verified; External / In production; data access under review. adwords not yet verified; 1 user / 100 user cap. Mevcut hesapta canlı kampanya isteği HTTP 403. Google Ads hesabı 911-685-6472 panelinde askıya alınma ve iptal uyarıları var. 403 yanıtının kesin alt nedeni uygulama ekranında görünmüyor; hesap durumu ile neden bağlantısı kesinleştirilmedi. | Kod gerçek reklam okumayı destekliyor; onaysız kapsam nedeniyle kesintisiz genel abone yayını için hazır denemez. |
| YouTube | Etkin ayrı OAuth; istemci 967191475167-oc5qt0pk9t2eqponsrt1ickjhe9pt224.apps.googleusercontent.com; www callback eşleşiyor. Kanal kimliği ve temel kanal istatistikleri okunuyor. | Marka verified; External / In production; data access under review. youtube.readonly not yet verified; 1 user / 100 user cap. analytics.readonly kaldırılmış. | Kanal bağlantısı organiktir; YouTube reklamları Google Ads üzerinden alınır. Ayrı YouTubeAPI.get_ads boş liste döndürüyor. |
| TikTok | Canlı admin: Ayar girilmedi. Tokenla profil doğrulaması var; abonenin OAuth/reklam aktarımı yok. TikTokAPI.get_ads boş liste döndürüyor. | Ürün içindeki uygulanmış reklam akışı bulunmadığı için bir reklam API onayı tamamlanmış kabul edilemez; harici TikTok portalı onayı ayrıca doğrulanmadı. | Hazır değil; OAuth, reklam hesabı keşfi, raporlama, token bakımı ve gerekli sağlayıcı onayı gerekir. |
| LinkedIn | Ayar girilmedi. Profil doğrulaması mevcut; LinkedInAPI.get_ads boş liste. | Uygulanmış reklam OAuth/aktarım akışı yok. Harici portal erişim onayı doğrulanmadı. | Hazır değil. |
| X | Ayar girilmedi. Profil doğrulaması mevcut; XAPI.get_ads boş liste. | Uygulanmış reklam OAuth/aktarım akışı yok. Harici portal erişim onayı doğrulanmadı. | Hazır değil. |
| GA4 | Önceki kullanıcı talebiyle kaldırıldı; canlı bağlantı seçeneklerinde yok. Google proje kapsamlarında analytics.readonly yok. | Kapsam dışı. | Reklam hesabı bağlantısı değildir. |

## Meta başvurusunun tamamlanması için kalan işler
İşletme doğrulaması ve uygun Tech Provider doğrulaması; gerçek uçtan uca ads_read / Instagram demo kayıtları; abonelik özelliklerine erişen inceleyici hesabı; OpenAI dahil gerçek veri işleyen sağlayıcılar ve ülkelerinin doğru beyanı; Instagram erişim kaldırma / veri silme adresleri; gerekli kapsamların ürün işleviyle eşleşmesi; son hukuki taahhütlerin hesap sahibi onayı ve başvuru gönderimi. Taslak doldurmak Meta'ya başvurunun gönderildiği anlamına gelmiyor.

## Abone ve yetki koşulları
Bağlama akışları giriş yapmış kullanıcının hesabına OAuth state ile bağlıdır. Hesap seçimi sağlayıcının gerçekten döndürdüğü listeden yapılır. Kod aktif deneme/abonelik planını ve tüm platformlar için ortak hesap sayısı limitini uyguluyor. Ajans bağlantısında müşteri ve manage_accounts yetkisi aranıyor. Abonelik platform sahibinin OAuth izin/onayını ve reklam hesabı üzerindeki üye yetkisini değiştirmez.

## Doğrulama kapsamı
Canlı admin, Hesap Ekle, mevcut Meta/Google kampanya okumaları ve Meta/Google sağlayıcı panelleri kontrol edildi. Yeni rolü olmayan aboneyle yeni OAuth izin verme → hesap seçme → veri çekme uçtan uca testi yapılmadı. Mevcut bağlantılar kaldırılmadı, yeni izin verilmedi, hesap ayarları değişmedi. TikTok/LinkedIn/X reklam entegrasyonu yokluğu hem canlı ayar kartlarında hem mevcut kodda doğrulandı; dış sağlayıcı konsolları ayrıca kontrol edilmedi.

Mevcut testler: core.test_ads_integrations, core.test_google_read_oauth, core.test_instagram_oauth, core.test_integration_application, core.test_platform_setup — 71 test geçti, izole SQLite ayarlarıyla. Sağlayıcı yanıtları bu testlerde taklit edilir; izin onayı veya gerçek abone testi yerine geçmez.

## Kanıtlar
- artifacts/meta-permissions-audit-20261009.png
- artifacts/meta-draft-audit-20261009.png
- artifacts/google-ads-access-audit-20261009.png
- artifacts/google-oauth-review-audit-20261009.png
- artifacts/youtube-oauth-review-audit-20261009.png
- artifacts/google-ads-live-403-20261009.png
- artifacts/meta-live-campaigns-20261009.png
- artifacts/live-platform-connect-audit-20261009.png

## Resmi kaynak
Google Ads API erişim seviyeleri OAuth istemcisinin Cloud projesine bağlıdır; OAuth veri erişimi incelemesiyle farklı bir kontroldür: https://developers.google.com/google-ads/api/docs/api-policy/developer-token

## Öncelik
1. Meta doğrulama ve review taslağının tamamlanması / gönderimi.
2. Google Ads mevcut 403 alt nedeninin güvenli sunucu tanısıyla kesinleştirilmesi ve Google OAuth incelemesinin sonucu.
3. YouTube OAuth incelemesi sonucu.
4. Onaylardan sonra rolü olmayan gerçek bir aboneyle uçtan uca bağlantı ve veri okuma kabul testi.
5. TikTok / LinkedIn / X için ayrı reklam entegrasyonlarının geliştirilmesi ve sağlayıcı başvuruları.


## 9 Ekim ek inceleme — önceki durumun düzeltmesi
Google OAuth ayrıntılı Verification progress açıldı: 4 Ekim App functionality ERROR; demo OAuth consent flow içermiyor ve işlevleri yeterince göstermiyor. Under review üst başlığı, engelsiz bekleme anlamına gelmiyor. Yeni gerçek video sonrası mevcut Trust and Safety zincirine cevap gerekiyor.
Canlı 403 yapılandırılmış alt kodu güvenli teşhis düzeltmesiyle kesinleşti: authorizationError.CUSTOMER_NOT_ENABLED (hesap etkin değil). Detay: GOOGLE_403_VE_OAUTH_SONUC_20261009.md.
YouTube ayrıntısında homepage/branding tamam; diğer 4 adım incelemede, görünür düzeltme hatası yok.
Meta OpenAI Global / Standard Retention bölgesi doğrulandı; OpenAI işlemci taslağına eklendi. Kullanıcı gerçek Meta videoları olmadığını bildirdi. İncelemeci normal kullanıcı ID36, abonelik ID45 30 Kasım 2027'ye uzatıldı; admin izinleri yok, otomatik yenileme yok. Gerçek videolar, bağımsız giriş testi ve işletme doğrulaması tamamlanmadan başvuru gönderilemedi.

## 9 Ekim — Live geçişi ve yenilenen başvuru denetimi

Meta Live anahtarı kullanıcı talimatıyla açıldı. Yeniden sayfa açılışı sonrası checked kaldı; Alerts Inbox yeni App Mode Change bildirimi uygulamanın 09 Oct 2026 tarihinde Live moda geçtiğini açıkça doğruladı. Başlıktaki Development yazısı anahtarın sol etiketidir; önceki durum ile karıştırılmamalı.

Meta izin tablosu: ads_read ve instagram_business_basic Standard Access / No App Review requested; Marketing API Access Tier Limited access / No App Review requested. public_profile Standard / Verification required. instagram_business_manage_insights Standard / Ready to use (0) / No App Review requested, Advanced düğmesi kapalı. Başvuru taslağında Verification 0 ve Allowed usage 0; diğer üç bölüm 100. İşletme Reklam Analiz In review. Submit for review kapalı. Gerçek videolar ve kullanım taahhütleri eksik. Reviewer hesabı artık Platin ile Meta + Instagram bağlantısını kullanıyor; Instagram 8 gerçek medya okuması doğrulandı. Bu, ayrı Insights API kanıtı değildir. Önceki kontrolde deauthorize/data deletion callback boştu; bu oturumda değiştirilmedi.

Google Ads ve YouTube Verification Center sayfaları yeniden yüklendi. Ads için 4 Ekim App functionality error hâlâ var: video OAuth consent flow ve uygulama işlevini yeterince göstermiyor. Yeni gerçek video sonrası Trust and Safety mevcut e-posta zincirine yanıt gerekiyor. YouTube homepage/branding complete, diğer dört adım in progress; görünür hata yok. Önceki canlı Ads 403 teşhisi CUSTOMER_NOT_ENABLED; aktif gerçek reklam hesabıyla veri testi gerekiyor.

TikTok, LinkedIn ve X canlı admin ayar ekranında Ayar girilmedi ve OAuth/reklam aktarımı henüz uygulanmadı gösteriyor. Yerel API sınıflarında get_ads boş liste döndürüyor. Bu platformların harici geliştirici portallarındaki başvuru durumu ayrıca doğrulanmadı; uygulama reklam entegrasyonu hazır değil. YouTube reklamları Google Ads bağlantısından alınır; kanal bağlantısı organiktir.

Sonuç: Meta Live tamamlandı, gerekli erişim başvuruları tamamlanmadı/gönderilmedi. Google Ads düzeltme bekliyor; YouTube incelemede. Dış müşteri için genel bağlantı/veri kabul testi hâlâ gerekli.

## 9 Ekim — kullanıcı adına başvuru hazırlığı
Kullanıcı gerekli izin başvurularını kendisi adına yapmayı açıkça yetkilendirdi. Meta reviewer talimatları canlı formda güncellendi ve Auto-saved doğrulandı: normal üye, Platin, 30 Kasım 2027 bitişi, non-www giriş, Meta ads_read hesap seçimi ve gerçek Instagram 8 medya kontrolü anlatıldı. Boş kampanya listesi ve doğrulanmamış Insights özelliği başarı gibi sunulmadı. Test erişimi alanı hâlâ boş; kullanıcıdan şifreyi doğrudan Meta formuna yazması istendi.
public_profile Advanced Access düğmesi denendi; Meta Business verification is required to get advanced access bildirdi. İşletme onayı olmadan ilerlenmedi. Çalışma klasöründe mp4/webm kayıt bulunmadı; gerçek demo dosyası/video URL'si istendi. Tarayıcı aracında video kayıt yeteneği yok. Google Ads yeniden inceleme yanıtı yeni gerçek video olmadan gönderilmedi. YouTube mevcut incelemesi korundu.
Henüz yeni final başvuru gönderimi veya Advanced Access onayı gerçekleşmedi. Meta final uyumluluk beyanları, somut metni kullanıcıya gösterip eylem anında onay almayı gerektirir; genel başvuru yetkisi yanlış veya doğrulanmamış beyanları kabul etme yetkisi değildir. Callback eksikleri için çalışmayan/uydurulmuş URL girilmedi.

## 9 Ekim — işletme doğrulamasının ayrıntılı kontrolü
Meta App Review > Verification > View details üzerinden Reklam Analiz (960733090060866) Güvenlik Merkezi açıldı. Kullanım durumu “Uygulama, Meta for Developers'daki izinlere erişim gerektiriyor”. “Birol HAZAR için doğrulama” altında “Değerlendirmede” ve bilgilerin gönderildiği, değerlendirmesinin yaklaşık 2 iş günü süreceği belirtiliyor. Ek belge, düzeltme, yeniden gönderme veya incelemeyi hızlandırma düğmesi görünmüyor; gönderim tarihi ekranda verilmedi. Bildirimler paneli Yeni Bildirim Yok gösterdi.
İşletme Desteği Ana Sayfasında doğru Reklam Analiz portfolyosu seçildi. ReklamAnaliz Test veri kaynağında son 30 gün için Veri Kaynağı Sorunu Yok. Yardım menüsünde Meta AI ve İşletme Desteği Ana Sayfası bulunuyor; doğrudan destek kaydı açma seçeneği görünmedi. Yeni destek kaydı gönderilmedi. İşletme onayı hâlâ Meta'nın değerlendirmesine bağlı; belge eksikliği varmış gibi yeni başvuru oluşturulmadı veya mevcut portfolyo bağlantısı kaldırılmadı.

## 9 Ekim — onay beklenirken incelemeci ve demo hazırlığı
Meta accesscode-web-1 alanına non-www giriş URL'si, meta_reviewer kullanıcı adı, normal üye yetkisi, Platin paketi ve 30 Kasım 2027 bitişi eklendi. Kullanıcı mevcut şifreyi doğrudan Meta formuna yazdığını bildirdi. DOM üzerinde sadece doluluk/placeholder durumu kontrol edildi: Password satırında değer var, bekleme placeholder'ı yok; Auto-saved görünür. Şifre çıktıya veya yerel notlara alınmadı. Bu kontrol yeni bağımsız parola giriş testi değildir.
instagram_business_basic ve ads_read açıklamaları güncel normal üye test akışına, non-www domaine, gerçek 8 medya sonucuna ve kampanya verisi eksikliğine göre düzenlenip Save ile taslağa kaydedildi. Uyumluluk sözleşmesi kutuları işaretlenmedi; videolar henüz yüklenmedi. Marketing API Access Tier mevcut açıklaması ve Completed test eşiği kontrol edildi, ek değişiklik gerekmedi.
Video çekim metni güncellendi; Instagram için yaklaşık 2 dakikalık görüntü/anlatım akışı eklendi. Açık meta_reviewer oturumu Hesap Ekle sayfasında kayıt başlangıcına hazırlandı. Kullanıcıdan ekran kaydını başlatması istendi; tarayıcı aracının gerçek video kaydı yeteneği yok. Meta Ads için kampanyası olan yetkili hesabın seçimi hâlâ gerekli. İşletme onayı beklenmeden hazırlık yapılabiliyor; final gönderim ve gerçek videolar tamamlanmış sayılmıyor.

# Başvuru videoları — 9 Ekim 2026

Durum: Video dosyaları henüz oluşturulmadı. Bu oturumun tarayıcı aracı kesintisiz video kaydı başlatamıyor. Gerçek ekran kaydı kullanıcı tarafından başlatılmalı; tarayıcıdaki demo adımları ajan tarafından yürütülebilir. Şifre, OTP ve tokenlar kayda girmemeli.

## 1. Meta ads_read — ayrı kayıt
Hedef dosya: meta-ads-read-demo.mp4
Normal üye meta_reviewer hesabıyla başlayın. Hesap Platin paketinde, 30 Kasım 2027'ye kadar aktif; otomatik yenileme kapalı. Meta testinde bütün adımlarda non-www reklamanaliz.net alan adını kullanın.

1. https://reklamanaliz.net/accounts/login/ ve normal üye girişi gösterilir. Parola girişi kayıt dışında kalır.
2. Hesap Ekle > Meta/Facebook bağlantısı başlatılır.
3. Gerçek Facebook Login for Business ekranında uygulama adı ve ads_read izni gösterilir. Yeni veya daha geniş veri erişimi onayı gerekiyorsa kullanıcı izin adımını tamamlar.
4. Siteye dönüş ve sağlayıcının döndürdüğü yetkili reklam hesabı seçimi gösterilir.
5. Seçilen hesabın gerçek kampanya listesi ve kampanya performansı açılır. Harcama, gösterim ve tıklama mevcutsa görünür biçimde gösterilir. Veri yok veya hata varsa kayıt başarılı veri okuma diye sunulmaz.

English narration:
“This is Reklam Analiz, a subscription reporting application. I am signed in as a normal member. I open Add Account and connect Meta. Facebook Login for Business requests read access to advertising data through ads_read. After authorization, I return to Reklam Analiz and choose an advertising account that I am permitted to access. The application displays that account's campaign list and performance reports. It does not create, edit or publish advertising campaigns.”

## 2. Instagram instagram_business_basic — ayrı kayıt
Hedef dosya: instagram-business-basic-demo.mp4

1. Aynı normal üye hesabında Hesap Ekle > Instagram başlatılır.
2. Gerçek Instagram Business Login ekranı, uygulama adı ve profesyonel hesap gösterilir. Kimlik doğrulama kayıt dışında kalır.
3. İzin sonrası uygulamaya dönüş ve bağlanan gerçek profil gösterilir.
4. Organik İçerik ekranında bu hesabın gerçek medya listesi açılır; mevcut gönderi ve etkileşim bilgileri gösterilir.
5. Kod ayrıca instagram_business_manage_insights istiyor. Bu izin için gerçek Insights işlevi ve API testi kanıtlanmadan basic videosu Insights kanıtı olarak kullanılmaz. İzin kapsamı kontrolü hâlâ tamamlanmalı.

English narration:
“I connect my own professional Instagram account to Reklam Analiz using Instagram Login. After approving the permissions, I return to the application and see the authorized profile. The organic content page displays media belonging to this account and the available engagement information. This Instagram connection is for organic content. Advertising campaign reporting uses the separate Meta advertising connection.”

## 3. Google Ads adwords — ayrı kayıt
Hedef dosya: google-ads-oauth-demo.mp4

Ön koşul: Etkin ve kullanıcı tarafından erişilebilir bir Google Ads hesabı. 9116856472 hesabı CUSTOMER_NOT_ENABLED döndürdüğü için başarılı reklam verisi okuma kaydı için kullanılamaz.

1. Normal üye girişi > Hesap Ekle > Google Ads.
2. Gerçek OAuth ekranında uygulama adı ve adwords kapsamının izin metni gösterilir. Kimlik doğrulama kayıt dışında kalır.
3. İzin verme ve siteye dönüş gösterilir.
4. Gerçek erişilebilir etkin reklam hesabı seçilir.
5. Gerçek kampanya listesi ve performans raporu açılır. Başarısız/boş veri başarı kanıtı olarak anlatılmaz.

English narration:
“I am a normal member of Reklam Analiz. I connect Google Ads from Add Account. This is the application's real Google OAuth consent flow. The requested adwords scope supports reading the advertising accounts that I am authorized to access, their campaigns and their performance reports. After consent, I return to the application, select an accessible active account and open its campaign and performance data.”

Video tamamlandıktan sonra gerçek erişilebilir video bağlantısı mevcut Google Trust and Safety yanıt taslağına eklenir. E-posta gönderimi ayrıca kullanıcı talimatı gerektirir.

## Güncel panel kontrolü
- Meta: işletme In review; Verification ve Allowed usage tamam değil; Submit for review kapalı. Gerçek videolar yok. Normal üye girişi ve oturum devralma canlıda doğrulandı. İncelemeci erişim alanına kullanıcı adı, giriş adresi, Platin paketi ve bitiş tarihi eklendi. Kullanıcı mevcut şifreyi doğrudan Meta formuna ekledi; doluluk ve Auto-saved durumu şifreyi çıktıya taşımadan doğrulandı. Yeni bağımsız parola testi yapılmadı.
- Google Ads: 4 Ekim kontrolü; ilk dört adım tamam, App functionality ERROR. İki neden: OAuth consent flow gösterilmemiş; uygulama işlevleri yeterince gösterilmemiş. Düzeltme sonrası mevcut Trust and Safety zincirine yanıt isteniyor.
- YouTube: 5 Ekim kontrolü; homepage/branding tamam; diğer dört bölüm incelemede. Görünür düzeltme hatası yok.
- Instagram deauthorization/data deletion callback altyapısı bu devam oturumunda henüz değiştirilmedi veya yayınlanmadı; boş panel alanlarına çalışmayan URL girilmedi.

## Çekime hazır Instagram akışı (yaklaşık 2 dakika)

Kayıt uygulamasını kullanıcı başlatır. Tarayıcıda açık meta_reviewer oturumu kullanılabilir. Parola/OTP girilecekse kayıt duraklatılır; erişim tokenları veya geliştirici sırları gösterilmez.

| Süre | Görüntü | İngilizce anlatım |
| --- | --- | --- |
| 0:00–0:20 | non-www sitede normal üye, Hesap Ekle sayfası | “This is ReklamAnaliz. The reviewer account is a normal subscriber with an active Platin plan. No payment is needed to test the application.” |
| 0:20–1:00 | Instagram bağlantısını başlat, gerçek Instagram izin ekranı, uygulamaya dönüş | “I select Instagram and authorize my own professional account using Instagram Login. The application uses instagram_business_basic to identify the authorized profile and read its media.” |
| 1:00–1:20 | Platform Bağlantıları'nda yetkilendirilen kullanıcı adı/hesap kimliği | “After authorization, Platform Connections shows the username and identity of the profile I connected.” |
| 1:20–2:00 | Organik İçerik > Verileri Yenile > gerçek medya listesi | “I open Organic Content and refresh the data. These are real media items belonging to the connected account, with the engagement counts available to the application.” |

Kayıt adı: instagram-business-basic-demo.mp4. Gerçek profil adı ile listede dönen içerikler birbiriyle eşleşmeli. Basic medya okuması ayrı Insights işlevinin kanıtı olarak sunulmaz. Bağlantı akışı kayıtta görünmeli; yalnızca önceden bağlanmış hesabın ekranını çekmek yeterli değildir.

Meta ads_read kaydı için mevcut Birol Hazar hesabı bağlantıyı gösterir fakat kampanya listesi boş döndü. Harcama/gösterim/tıklama raporunu göstermek için kullanıcı tarafından yetkilendirilmiş, erişilebilir kampanyası olan bir hesap gerekir. Şu anda böyle bir hesapta dolu rapor doğrulanmadı.

## Kullanıcının kayıt başlatması sonrası yürütülen demo

Kullanıcı “kayıt başladı” bildirdi. Açık meta_reviewer oturumunda Hesap Ekle > Instagram bağla tıklandı. Instagram mevcut reklamanaliznet yetkilendirmesine devam ekranı sundu; aynı mevcut izinler yenilendi. Uygulama callback'i Platform Bağlantıları'na döndü ve “@reklamanaliznet Instagram hesabı bağlandı” mesajını gösterdi. Profil kullanıcı adı ve ID 17841424769133023 görüldü. Organik İçerik > Verileri Yenile çalıştırıldı; işlem sonrası 8 medya listede kaldı. 17 Eylül 2026 gönderisinin açıklaması ve gerçek medya önizlemesi açıldı, 10 saniyelik videosunun oynatımı başlatıldı.
Bu akış kullanıcı tarafından başlatılan ekran kaydı sırasında yürütüldü; kayıt dosyasının oluştuğu, içeriği ve dosya yolu henüz doğrulanmadı. Video Meta'ya henüz yüklenmedi. Ekran mevcut izinleri yenileme akışıdır; ilk kez verilen ayrıntılı izin ekranı olarak sunulmamalıdır. Instagram Insights API doğrulaması değildir.

## Kullanıcının kendi çektiği dosya — kontrol ve yükleme denemesi
Dosya C:\Users\Birol\Videos\Ekran Kayıtları\instagram-business-basic-demo.mp4, 84.762.169 bayt. Medya süresi 169,57 saniye, H.264 1912x996 / 30 fps ve AAC ses. Kullanıcının kendi yürüttüğü son kayıt 5 saniye aralıklarla çıkarılan görüntüler üzerinden kontrol edildi: Instagram bağlantısı ve mevcut izin ekranı, callback başarı mesajı, reklamanaliznet profili, gerçek içerik listesi, yenileme başarı mesajı ve video oynatımı görünüyor. Örneklenen görüntülerde görünür şifre veya token tespit edilmedi; ses içeriği ayrıca doğrulanmadı. İnceleme görselleri artifacts/instagram-video-review-20261009 altında.
Meta instagram_business_basic formunda Dosya Seç üzerinden filechooser akışı denendi. Chrome eklentisinde Allow access to file URLs izni kapalı olduğundan setFiles başarısız oldu. Henüz video Meta'ya yüklenmedi veya yükleme kaydı Save ile tamamlanmadı. Kullanıcının açık Meta formunda dosyayı doğrudan seçmesi istendi; başvuru taslağı bu adımda açık bırakıldı.

## Kullanıcının yükleme ve Save işlemi sonrası doğrulama
Kullanıcı dosyayı seçip Save'e bastığını bildirdi. instagram_business_basic formu tekrar açıldı: “View uploaded screencast” bağlantısı ve video ID 1572706640741965 görünüyor; “Drag a new file here to replace the current screencast” metni yüklemenin kaydedildiğini doğruluyor. Kullanıcı tarafından uyumluluk kutusu da seçilmiş (1); ajan yeni sözleşme kabul etmedi. İzin açıklamasındaki eski “video yüklenmeli” cümlesi yüklenen 2:49 gerçek kaydın akışıyla güncellendi ve Save ile kaydedildi. Video mevcut iznin yenilenmesini gösteriyor; ilk kez izin seçimi veya Insights API kanıtı sayılmadı. Final App Review gönderimi yapılmadı; işletme doğrulaması ve diğer izinlerin kalan adımları ayrı.

## 9 Ekim 2026 - Gercek tanitim reklami taslagi
Kullanici test ibaresinin kaldirilmasini ve gercek reklam icin toplam 60 TL butce istedi. Birol Hazar reklam hesabi act1608518633550120 uzerinde kampanya ReklamAnaliz | Web Sitesi Tanitimi (120253345320420652), reklam seti ReklamAnaliz | Turkiye | Web Trafik (120253345320410652), reklam ReklamAnaliz | Tek Panel (120253345320430652) hazirlandi. Toplam butce 60,00 TRY, baslangic 9 Ekim 2026 13:47 GMT+3, bitis 10 Ekim 2026 13:47 GMT+3. Hedef reklamanaliz.net, optimizasyon baglanti tiklamalari, hedef kitle Turkiye 18+ varsayilan genis kitle. Meta mevcut kare 1024x1024 Reklam Analiz tanitim gorseli kullanildi; yatay logo onizlemede kesildigi icin degistirildi. Tum secili reklam alanlarinda uygunluk goruldu. Facebook Reklam Analiz ve Instagram reklamanaliznet kimligi. UTM campaign reklamanaliz_tanitim. Kampanya, reklam seti ve reklam acik olarak hazir ancak Taslak halinde, Yayinla tiklanmadi. Final yayinlama Meta kosullarinin kabulunu ve harcamayi baslatabileceginden kullaniciya devrediliyor. Taslak API'de okunan veya performans ureten kampanya olarak kanit sayilamaz. Onceki hesap bilgileri gerekiyor uyarisinin yayinlama sonrasi engel olup olmadigi henuz bilinmiyor.

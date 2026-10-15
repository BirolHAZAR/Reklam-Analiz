# Instagram insights ve Meta callback kontrolü — 15 Ekim 2026

## Canlı insights

`reklamanaliz` oturumunda Organik İçerik ekranı açıldı ve Verileri Yenile bir kez çalıştırıldı. Yenileme sonrası 8 içerik, 25 görüntüleme, 14 erişim, 5 etkileşim görünüyor. Profil ziyareti ve ayrı video izlenme alanları sağlayıcı verisi bulunmadığından “Veri yok”; sıfır gibi gösterilmiyor.

Kanıt: `artifacts/meta-20261015/instagram-insights-canli.jpg`.

## Veri silme

Meta temel ayarlarında **Data deletion instructions URL** seçili ve `https://www.reklamanaliz.net/hukuk/veri-silme-politikasi/` kayıtlı. Sayfa açık, hesap üzerinden veya e-posta ile talep, bağlantının kaldırılması, silme kapsamı ve sonuç bildirimi açıklanıyor. Resmi Meta belgesi callback veya talimat URL'si seçeneklerinden birini kabul ediyor. Bu seçim değiştirilmedi; otomatik veri silme callback'i varmış gibi gösterilmiyor.

Kaynak: https://developers.facebook.com/documentation/development/create-an-app/app-dashboard/data-deletion-callback

## Yetki kaldırma bildirimi

Facebook Login for Business ve Instagram Business Login ayarlarındaki deauthorization adresleri kaydedildi ve form yeniden açılarak doğrulandı. Canlı uçlar:

- `/connect/facebook/deauthorize/`
- `/connect/instagram/deauthorize/`

Yalnız POST ve doğru uygulama gizli anahtarıyla HMAC-SHA256 imzası kabul edilir. Platformun kullanıcı kimliği yerel site kullanıcı kimliği olarak yorumlanmaz. Uygulama kimliği ve OAuth sırasında kaydedilen platform kimliği eşleşen bağlantılar pasifleştirilir, bağlantı ve hesap tokenları temizlenir. Eski olay daha sonra oluşturulmuş yeni bir OAuth bağlantısını kapatmaz. İstek/yanıt kayıtlarında token veya app secret yazdırılmaz. Veri silme işlemi bu bildirimin parçası değildir; mevcut talimat süreci korunur.

Yeni OAuth bağlantıları Meta uygulama ve kullanıcı kimliğini saklar. Mevcut Facebook bağlantıları için `backfill_meta_callback_subjects` yönetim komutu, Meta debug_token yanıtındaki geçerlilik, app_id ve user_id doğrulamasından sonra yalnız `--apply` ile kimlik metadatasını kaydeder. Varsayılan çalışma salt okunurdur.

Mevcut Instagram Login tokenını Facebook debug_token üzerinden doğrulama denemesi HTTP 400 / OAuthException 190 döndürdü; hiçbir eşleşme tahmin edilmedi veya yazılmadı. Ardından mevcut Instagram yetkisi normal OAuth akışıyla yenilendi. Hesap 73 korundu, yeni bağlantı 79 aktif; uygulama ve kullanıcı kimlik alanlarının kaydedildiği sunucuda doğrulandı.

İlk birleşik test çalışması 113 testle başarılı. Ek kimlik testleri 36 testle, son hesap seçimi ve Instagram kimliği kontrolleri de 23 testle başarılı; Django sistem kontrolü temiz. Kullanıcının belirttiği **reklamanaliz V1.2.3** commit'i `f069c4dc34091720a012ca8e805316ed50ec1942`, main dalına gönderildi. Dokploy dağıtımı Done, süre 1 dakika 52 saniye; web ve worker konteynerlerinde commit doğrulandı. Worker ve Beat `ed100562da30` imajına otomatik geçti. Worker kontrol kanıtı: `artifacts/meta-20261015/worker-v123-dogrulandi.jpg`.

Facebook mevcut bağlantıları önce salt okunur doğrulandı, ardından yalnız sağlayıcının doğruladığı kimlik metadatası kaydedildi. Tüm kullanıcılar kapsamında 7 bağlantı doğrulandı; demo/tokensız 27 ve 35 atlandı. Token veya uygulama gizli anahtarı yazdırılmadı.

Canlı HTTPS kabulü: iki callback için GET 405; geçersiz imzalı POST 403. Gerçek bir hesabı kapatacak geçerli deauthorization bildirimi canlıya gönderilmedi; imzalı bildirimin token temizleme davranışı izole test veritabanında doğrulandı.

Kanıtlar: `artifacts/meta-20261015/facebook-callback-kaydedildi.jpg`, `instagram-callback-kaydedildi.jpg`, `instagram-yeniden-baglandi.jpg`.

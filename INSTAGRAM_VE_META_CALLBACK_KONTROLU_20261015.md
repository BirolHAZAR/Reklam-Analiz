# Instagram insights ve Meta callback kontrolü — 15 Ekim 2026

## Canlı insights

`reklamanaliz` oturumunda Organik İçerik ekranı açıldı ve Verileri Yenile bir kez çalıştırıldı. Yenileme sonrası 8 içerik, 25 görüntüleme, 14 erişim, 5 etkileşim görünüyor. Profil ziyareti ve ayrı video izlenme alanları sağlayıcı verisi bulunmadığından “Veri yok”; sıfır gibi gösterilmiyor.

Kanıt: `artifacts/meta-20261015/instagram-insights-canli.jpg`.

## Veri silme

Meta temel ayarlarında **Data deletion instructions URL** seçili ve `https://www.reklamanaliz.net/hukuk/veri-silme-politikasi/` kayıtlı. Sayfa açık, hesap üzerinden veya e-posta ile talep, bağlantının kaldırılması, silme kapsamı ve sonuç bildirimi açıklanıyor. Resmi Meta belgesi callback veya talimat URL'si seçeneklerinden birini kabul ediyor. Bu seçim değiştirilmedi; otomatik veri silme callback'i varmış gibi gösterilmiyor.

Kaynak: https://developers.facebook.com/documentation/development/create-an-app/app-dashboard/data-deletion-callback

## Yetki kaldırma bildirimi

Facebook Login for Business ayarlarındaki deauthorization alanı boş. Hazırlanan uçlar:

- `/connect/facebook/deauthorize/`
- `/connect/instagram/deauthorize/`

Yalnız POST ve doğru uygulama gizli anahtarıyla HMAC-SHA256 imzası kabul edilir. Platformun kullanıcı kimliği yerel site kullanıcı kimliği olarak yorumlanmaz. Uygulama kimliği ve OAuth sırasında kaydedilen platform kimliği eşleşen bağlantılar pasifleştirilir, bağlantı ve hesap tokenları temizlenir. Eski olay daha sonra oluşturulmuş yeni bir OAuth bağlantısını kapatmaz. İstek/yanıt kayıtlarında token veya app secret yazdırılmaz. Veri silme işlemi bu bildirimin parçası değildir; mevcut talimat süreci korunur.

Yeni OAuth bağlantıları Meta uygulama ve kullanıcı kimliğini saklar. Mevcut Facebook bağlantıları için `backfill_meta_callback_subjects` yönetim komutu, Meta debug_token yanıtındaki geçerlilik, app_id ve user_id doğrulamasından sonra yalnız `--apply` ile kimlik metadatasını kaydeder. Varsayılan çalışma salt okunurdur.

Mevcut Instagram Login tokenını Facebook debug_token üzerinden doğrulama denemesi HTTP 400 / OAuthException 190 döndürdü; hiçbir eşleşme tahmin edilmedi veya yazılmadı. Mevcut Instagram bağlantısını yeni kimlik alanlarıyla yeniden yetkilendirme gerekebilir.

İlk birleşik test çalışması 113 testle başarılı. Ek kimlik testleri 36 testle, son hesap seçimi ve Instagram kimliği kontrolleri de 23 testle başarılı; Django sistem kontrolü temiz. Kullanıcının bu değişiklik için belirttiği commit adı **reklamanaliz V1.2.3**. Canlı kabul ve Meta panelinde callback kaydı dağıtım sonrasında doğrulanmalı.

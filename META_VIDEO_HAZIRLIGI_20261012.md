# Meta ads_read video hazırlığı — 12 Ekim 2026

Güncel uygulama kullanıcısı `reklamanaliz`. Kullanıcı, eski `meta_reviewer` hesabının silindiğini bildirdi. Yeni hesabın paket ve yetkileri canlıda yeniden doğrulanmalı; eski hesabın bilgileri bu hesaba taşınmış kabul edilmez.

## Doğrulanan gerçek kampanya

Ads Manager'da hesap `1608518633550120`, kampanya `ReklamAnaliz | Web Sitesi Tanıtımı`.
12 Ekim kontrolünde Tamamlandı; son 30 gün 137 bağlantı tıklaması, 2.209 gösterim, 1.505 erişim, 59,63 TL harcama.
9 Ekim kaydındaki taslak durumu artık güncel değildir. Yayının kim tarafından başlatıldığı bu kontrolde belirlenmedi. Bu oturumda reklam oluşturulmadı, yayınlanmadı veya bütçe değiştirilmedi.

## Kayıt akışı

1. `https://reklamanaliz.net/accounts/login/` adresinde `reklamanaliz` ile giriş. Parola/OTP girişi kayıt dışında.
2. Platform Bağlantıları ekranında erişim ve hesabın abonelik yetkisini kontrol et.
3. Kayıt başlatıldıktan sonra Hesap Ekle > Meta bağlantısını aç. Gerçek Facebook Login for Business ekranında uygulama adını ve ads_read açıklamasını göster.
4. Yetkilendirme sonrası siteye dönüşü, Meta'nın döndürdüğü hesap listesini ve `1608518633550120` seçimini göster.
5. Uygulamada kampanya listesini ve yukarıdaki gerçek kampanyayı aç. Performans raporunda 9–10 Ekim'i içeren dönemi göster. Uygulamadaki tıklama tanımı Ads Manager bağlantı tıklamasından farklı olabilir; değerlerin birebir aynı olduğu varsayılmaz.
6. Veri hata verirse kaydı başarı kanıtı olarak kullanma; hatayı gider ve tekrar çek. Yeni reklam veya yeni harcama gerekli değil.

Bu aracın kesintisiz ekran kaydı başlatma yeteneği yok. Kullanıcı Windows ekran kaydını başlatabilir; tarayıcıdaki gerçek demo adımları ajan tarafından yürütülebilir. Plan veya altyazı dosyası gerçek screencast yerine geçmez.

## İngilizce anlatım

This is Reklam Analiz, an advertising reporting application. I am signed in with the application account reklamanaliz. I open Add Account and connect Meta through Facebook Login for Business. The application requests ads_read to read advertising accounts, campaigns and performance data. After authorization, I return to Reklam Analiz and select an account that I am authorized to access. I open the completed campaign ReklamAnaliz Web Sitesi Tanıtımı and display its actual reporting data. The application does not create, edit or publish advertising campaigns.

12 Ekim canlı uygulama testi tamamlandı: `reklamanaliz` oturumu doğrulandı; hesap ID 85 üzerinden gerçek kampanya listesi ve performans okundu. 9 Ekim: 1.526 gösterim, 90 tıklama, 31,84 TL. 10 Ekim: 683 gösterim, 39 tıklama, 27,79 TL. Toplam 2.209 gösterim, 129 tıklama ve 59,63 TL. Ads Manager 137 bağlantı tıklaması gösterdi; uygulamanın metrik tanımı farklı olduğundan bu fark hata olarak yorumlanmadı. Uygulamada canlı veri okuması video için hazır.

## Başvuru durumu

Meta Live açık. İşletme doğrulaması In review. Submit for review kapalı. İncelemeci talimatlarında silinen kullanıcı adı güncellendi; eski hesabın paket/yetki iddiaları çıkarıldı. Yeni parola hesap sahibi tarafından doğrudan Meta formuna girilmeli. Final başvuru gönderilmedi.

Instagram basic için önceki gerçek video kaydı mevcut. Insights kodu bu oturumda yerel olarak eklendi; canlı dağıtım ve gerçek API okuması henüz doğrulanmadı. Deauthorization/data deletion callback eksikleri henüz tamamlanmadı.

Google Ads ayrı başvurudur: 4 Ekim App functionality hatası devam ediyor. Google Ads panelinde bugün açılan hesap `326-461-4352`; hesaplar menüsünde alt hesap yönetimi mevcut, etkin/taslak filtresinde eşleşen alt hesap yok. Uygulama hesap ID 84 hâlâ `911-685-6472` hesabına bağlı. 12 Ekim gerçek API okuması tekrar HTTP 403 `authorizationError.CUSTOMER_NOT_ENABLED` döndürdü. Bu hata Meta hesabına ait değil. YouTube incelemesi sürüyor, görünür düzeltme hatası yok.

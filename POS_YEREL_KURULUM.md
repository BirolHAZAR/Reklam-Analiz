# Şirket bilgileri ve sanal POS — yerel hazırlık

25 Eylül 2026. Canlıya yayın yapılmadı. Gerçek POS anahtarı kullanılmadı, tahsilat denenmedi.

## Admin ekranları

- `/admin/core/legalsitesettings/`: şirket adı, adres, vergi dairesi/numarası, MERSİS, ticaret sicil numarası, KEP, e-postalar, telefonlar, banka adı, hesap sahibi, IBAN ve havale kontrol süresi. Süre başlangıçta **3 takvim günü**. Bilgiler footer, iletişim, sözleşme değişkenleri, yeni ödeme belgeleri ve bildirimlerde ortak kullanılır. Bilinmeyen resmi bilgiler boş bırakıldı. Önceden kabul edilmiş sözleşme kopyaları yeniden yazılmaz.
- `/admin/core/paymentgatewaysettings/`: aktif sağlayıcı **iyzico / Garanti BBVA**, kart ödemesi açık/kapalı, test/canlı ortam, dönüş adresinin HTTPS site kökü ve sağlayıcının bağlantı bilgileri. Bu ekran yalnızca süper kullanıcıya açıktır. Anahtarlar şifreli saklanır; formda tekrar gösterilmez. Boş bırakmak kayıtlı anahtarı korur. Kart ödemesini durdurmak için “Kart ödemesi açık” seçeneğini kaldırın.
- `/admin/core/hostedpaymentsession/`: işlem durumu. Süper kullanıcı, bağlantı kesintisi veya sağlayıcı incelemesi nedeniyle bekleyen işlemi “tekrar doğrula” eylemiyle sorgulayabilir. Bu eylem yeni tahsilat başlatmaz; doğrulanmış işlem bir kez etkinleştirilir. Garanti için önce imzalı banka dönüşünün alınmış olması gerekir.
- `/admin/core/legaldocument/`: şirket bilgilerini tamamladıktan sonra sözleşmeleri kontrol edip yayımlayın. Gerekli beş satış belgesi yayımlanmadan satın alma tamamlanmaz. Taslak belgeler anonim kullanıcılara açılmaz; footer yalnızca yayımlanmış politikaları listeler.

## Ödeme davranışı

Kart numarası ve CVV artık uygulamanın checkout formunda istenmez. iyzico kendi barındırdığı ödeme sayfasına yönlendirir; Garanti 3D ortak ödeme formuna geçer. Sipariş önce beklemede oluşturulur. iyzico yanıtında imza, token, sipariş, tutar, para birimi ve fraud onayı kontrol edilir. Garanti dönüş imzası/3D sonucu kontrol edilir ve tutar sunucudan bankaya sipariş sorgusu ile ayrıca doğrulanır. Sağlayıcı doğrulaması olmadan abonelik, ek hak, başarılı ödeme veya ödenmiş belge oluşturulmaz.

Eski demo kart tahsilatı ve sahte otomatik yenileme devre dışıdır. Bu sürüm tek dönemlik ödeme alır; otomatik kart yenilemesi sunmaz. Başarısız/incelemedeki yanıtlar hak tanımlamaz. Tekrarlanan başarılı bildirimler ikinci hak veya belge oluşturmaz. Aktif sağlayıcının sonradan değiştirilmesi, başlamış işlemin sağlayıcı ayarlarını değiştirmez; işlem başlangıcı ayarları şifreli saklanır.

Test ortamında kart ödeme başlatma yalnızca personel kullanıcılarına açıktır. Gerçek sağlayıcı sözleşmesi ve test hesabı olmadan uçtan uca banka testi yapılmış sayılmaz. Özellikle bankanın terminal yetkileri, Garanti sorgu yetkisi, dönüş URL erişimi ve gerçek ortam yanıtları sağlayıcı test hesabıyla doğrulanmalıdır. Ayarların girilmesi kendi başına banka onayı veya ödeme kabulü garantisi değildir.

## Yerel veritabanı ve yayın sırası

Yerel PostgreSQL bağlantısı `127.0.0.1:5432` olarak doğrulandı. Bekleyen `0073`, `0074`, `0075` migration'ları yerelde uygulandı. Ardından tüm uygulamalar için `migrate` çalıştırıldı; bekleyen migration kalmadı. Şirket kayıtları değişiklikten önce yerel geçici dizine yedeklendi. Girişte görülen `trade_registry_number does not exist` hatası, kodun yeni alanı istemesi fakat migration'ın uygulanmamış olmasıydı; giderildi ve gerçek yerel HTTP isteğinde giriş sayfası 200 döndü.

Sunucu kopyasında bekleyen değişikliklerin diff'i henüz elde edilmedi. Yayından önce kod ve migration isimleri/içerikleri iki kopya arasında karşılaştırılmalı. Aynı işlev iki kere eklenmemeli; migration isim çakışmaları üretime gitmeden giderilmeli. Üretimde önce migration'lar, sonra yeni kodla servis başlangıcı yapılmalı. Bu dosyadaki işlemler yayın izni değildir.

## Doğrulama

İzole SQLite/yerel bellek önbelleği ve sahte sağlayıcı yanıtlarıyla regresyon testleri; şirket bilgilerinin sayfalara yansıması, şifreli alanlar ve yetkiler, bekleyen ödeme, yanlış imza/tutar/sipariş, fraud beklemesi, iki kez gelen callback, muhasebe/hak tanımlama, havale, fatura PDF üretimi, SEO ve hukuk kapsamındadır.

```powershell
.\.venvs\instagram_reklam_analiz\Scripts\python.exe instagram_reklam_analiz/manage.py test core.test_payment_gateway core.test_purchase_flows core.test_seo core.test_cache_headers core.test_legal_documents --settings=config.settings_test_seo --verbosity 1
```

Playwright ile 1440 ve 390 piksel genişliklerde giriş, iletişim, fiyatlar ve teslimat sayfaları kontrol edildi. Logo bandı yüklendi, yatay taşma veya JavaScript hatası görülmedi; yıllık fiyat etiketi dönem toplamını gösterdi. Logolar kullanıcının `iyzico-logo-pack.zip` paketinden değiştirilmeden alındı.

## Teknik kaynaklar

- [iyzico logo paketi](https://docs.iyzico.com/ek-bilgiler/iyzico-logo-paketi)
- [iyzico ödeme formu](https://docs.iyzico.com/odeme-metotlari/odeme-formu/cf-entegrasyonu/cf-baslatma)
- [iyzico sonuç sorgulama](https://docs.iyzico.com/odeme-metotlari/odeme-formu/cf-entegrasyonu/cf-sorgulama)
- [iyzico imza doğrulama](https://docs.iyzico.com/ek-servisler/imza-yanitinin-dogrulanmasi)
- [Garanti ortak ödeme](https://dev.garantibbva.com.tr/sanal-pos-ortak-odeme-taksitli)
- [Garanti sipariş sorgulama](https://dev.garantibbva.com.tr/sanalpos-sorgulama-siparis-sorgulama)

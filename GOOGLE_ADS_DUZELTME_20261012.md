# Google Ads bağlantı ve izin durumu — 12 Ekim 2026

Hedef: abonelerin kendi Google Ads hesaplarını ReklamAnaliz'e OAuth ile bağlayıp reklam ve performans raporlarını okuması.

## Kullanıcının ekranlarından doğrulananlar

- Canlı OAuth projesi `project-ba6a63a8-5a5c-4618-95f`: Google Ads API etkin, Explorer erişimi mevcut (2.880 üretim işlemi/gün).
- Marka doğrulaması tamam. Veri erişimi incelemesinin 4 Ekim tarihli App functionality hatası devam ediyor: video OAuth izin akışını ve uygulama işlevini yeterince göstermiyor.
- `reklamanaliz34@gmail.com` ile gerçek Google izin ekranı açıldı. Devam sonrası hesap seçimi yerine HTTP 403 `authorizationError.CUSTOMER_NOT_ENABLED` görüldü.
- Uygulamada eski `9116856472` hesabı pasif, token yeniden bağlantı istiyor. Bu ekran yeni hesabın bağlandığını kanıtlamıyor.
- Kullanıcı etkin ve kampanyalı bir Google Ads hesabı olmadığını açıkça bildirdi.

## Kod düzeltmesi

Yapılandırılmış Google hata kodları IntegrationError üzerinde korunuyor. Hesap keşfi yalnızca tek hata kodu CUSTOMER_NOT_ENABLED olduğunda o hesabı atlıyor ve diğer hesapları keşfetmeye devam ediyor. Global erişim, token ve diğer hatalar gizlenmiyor. Kullanılabilir hesap kalmazsa açıklayıcı mesaj veriliyor.

İlk düzeltme `e61eb6e1` commit'iyle main dalına gönderildi; 45 ilgili test geçti. Canlı Dokploy dağıtımının tamamlandığı henüz doğrulanmadı.

Google test hesapları için customer.test_account ve customer_client.test_account kullanılıyor. İptal edilmiş görünen test hesapları kabul ediliyor; gerçek iptal edilmiş hesaplar filtreleniyor. Seçimde test hesabı adı açıkça etiketleniyor, test_account bilgisi saklanıyor.

Son sürüm için 46 entegrasyon/OAuth testi geçti; Django system check ve git diff check temiz. Testler sağlayıcı yanıtlarını taklit eder; gerçek Google bağlantısı veya OAuth onayı kanıtı değildir.

## Kalan zorunlu işler

1. Son kodun canlı dağıtımını ve bağlantı akışını doğrula.
2. Google'ın resmi test hesabı akışıyla test yönetici hesabı ve test müşteri hesabı hazırla. Mevcut üretim yönetici hesabına bağlı Google kullanıcısı yerine resmi belgenin uygun hesap koşulunu uygula.
3. Test kampanyasını oluşturup OAuth hesabı seçimi ve kampanya okumasını göster. Test hesapları reklam yayınlamaz ve kart gerektirmez; gerçek gösterim/tıklama/harcama metrikleri üretmez.
4. Gerçek ekran kaydı: OAuth izin ekranı, siteye dönüş, hesabı seçme, API kampanya listesi ve rapor işlevi. Test verisi açıkça belirtilmeli; boş metrikler gerçek performans gibi sunulmamalı.
5. Yeni video URL'sini mevcut Google Trust and Safety e-posta zincirine gönder. Bu oturumda video oluşturulmadı ve e-posta gönderilmedi. Test demosunun kabulü Google'a bağlı.

Tarayıcı kontrol aracı hâlâ sandbox çalışma ortamı hatası veriyor. Sayfa açma komutları kullanılabiliyor; oturumdaki form doldurma ve kayıt işlemleri otomatik yapılamıyor.

Resmi kaynaklar:
- https://developers.google.com/google-ads/api/docs/best-practices/test-accounts
- https://developers.google.com/identity/protocols/oauth2/production-readiness/sensitive-scope-verification
- https://developers.google.com/google-ads/api/docs/api-policy/developer-token

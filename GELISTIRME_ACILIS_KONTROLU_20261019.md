# Geliştirme açılış kontrolü — 19 Ekim 2026

## Düzeltmeler

- Web/worker/beat başlatıcıları `DEBUG=True` ve `DJANGO_ENV=development` değerlerini açıkça ayarlar. Dış ortamdan gelen `DEBUG=release`, Django boolean ayrıştırmasını bozuyordu.
- `ReklamAnaliz_Baslat.bat`, yeni `start_dev_stack.ps1` dosyasını kullanır. Veritabanını ve gerçek ReklamAnaliz ana sayfasını kontrol eder; çalışan proje worker/beat süreçlerini tekrar başlatmaz. Yeni servisler gizli konsollarla başlar; çıktılar `runtime/launcher/` altındadır.
- Yerel `0083_retire_competitor_features` ve `0084_remove_ad_library_id` migration'ları uygulandı. Öncesinde `runtime/local-db-backups/before-migrate-20261019.dump` yedeği alınıp `pg_restore -l` ile doğrulandı (6.883.092 bayt). Canlı veritabanına müdahale edilmedi.

## Doğrulamalar

- Geliştirme adresi: `http://localhost:8000/`; `http://127.0.0.1:8000/` de yanıt veriyor. Oturum ve OAuth adreslerinde aynı host kullanılmalıdır.
- PostgreSQL ve Redis erişimi başarılı; yerel Celery worker `pong` yanıtı verdi. Beat süreci mevcut ve schedule dosyası güncelleniyor.
- Toplu başlatıcı `-NoBrowser` ile çalıştırıldı; mevcut worker/beat tekrar açılmadı.
- `DEBUG=release` verilerek web başlatıcısı ayrı 8001 portunda sıfırdan çalıştırıldı; sistem kontrolü başarılı, HTTP 200. Geçici 8001 sunucusu kapatıldı; ana 8000 sunucusu çalışır bırakıldı.
- Yerel yönetici ile `/`, `/dashboard/`, `/hesap-ekle/`, `/platform-connections/`, `/campaign-reporting/`, `/admin/core/integrationapplication/`, `/organic-content/`, `/campaign-center/`, `/reklam-paneli/` HTTP 200 döndü.
- Kullanıcı normal giriş ekranından yerel admin oturumunu açtı. Tarayıcıda yönetici paneli ve hesap bağlama ekranı doğrulandı. Hesap ekranında konsol hatası, bozuk görsel veya yatay taşma bulunmadı.
- Kanıt: `artifacts/gelistirme-hesaplar-20261019.png`.
- Dört PowerShell başlatıcısının sözdizimi ve `git diff --check` başarılı.

## Canlıyla eşdeğerlik sınırı

Kod ve ekranlar aynı uygulamayı kullanır; yerel veritabanı ve sağlayıcı yetkilendirmeleri ayrı kayıtlardır. Yerel Google Ads kaydı devre dışı, YouTube/TikTok uygulama ayarları eksik. Bu üç entegrasyonun yerelde gerçek veri okuması doğrulanmış değildir. Canlı anahtarlar/tokenlar otomatik kopyalanmadı; yerel bağlantı kurulumunun kapsamı kullanıcıya soruldu.

LinkedIn hazırlığı yerelde görünüyor; Advertising API onayı gelene kadar kapalı. Canlı yayın veya uzak push bu kontrolün parçası olarak yapılmadı.

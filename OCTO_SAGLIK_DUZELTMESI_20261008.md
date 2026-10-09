# Octo operasyon sağlığı düzeltmesi — 8 Ekim 2026

Canlı yönetici panelinde tüm son 30 günlük metrikler sıfır, kampanya/reklam sayıları sıfır iken 31/100 gözlendi. Bağlı platform kayıtları veri var kontrolünü geçiyor; ROAS/CTR yardımcı fonksiyonu 0 metrik için 50 kreatif puanı üreterek ortak motorun verisiz kontrolünü atlatıyordu.

Düzeltme:
- ROAS ve CTR sinyali yoksa türetilen kreatif skoru sıfır.
- Yönetici panelinde sağlık yalnızca son 30 günlük harcama/gösterim/tıklama/dönüşüm/gelir sinyali varsa hesaplanır. Yoksa 0/100 ve Veri yok.
- Verisiz panelde Operasyon stabil görünüyor yerine Performans verisi bekleniyor ve senkronizasyon bağlantısı.
- Ajans firma kapsamı ve gerçek metrikleri olan hesapların puan hesabı korunur.

Doğrulama: Önce iki regresyon mevcut kodda 31 != 0 ve 24 != 0 ile başarısız oldu. Düzeltme sonrası core.test_agency_scope + core.test_control_tower_encoding, config.settings_test_seo izole SQLite ortamında 26/26 geçti. git diff --check temiz.

Durum: Yerel düzeltme tamam. Canlı dağıtım henüz yapılmadı. Bu oturumda eski SSH bağlantısı/anahtarı bulunmadı; Dokploy adresi veya mevcut sunucu bağlantı bilgisi kullanıcıdan istendi. Canlı sıfır puan henüz doğrulanmış değildir.

Paket: artifacts/octo-health-fix-20261008.patch

## Yayın hazırlığı devamı
Kullanıcı isteğiyle reklamanaliz-V1.1.16 dalı mevcut reklamanaliz-V1.16 dalından GitHub üzerinden oluşturuldu. Panel, ortak motor ve regresyon testleri 6cdc6da, bed7f94 ve 4ec63fc commitleriyle aktarıldı. Her dosyanın uzak temel sürümü yerel test edilen temel sürümle karşılaştırıldı; eşleşti. Dokploy dal hedefi değişikliği kayda gönderildi, kalıcılığı ve canlı yayın henüz doğrulanıyor.

Dokploy kaydetme sırasında NotFoundError removeChild ve client-side exception kaydı görüldü. Otomatik Türkçe çeviri ile ilişkili olabileceği değerlendirildi; dal seçimi yeniden yükleme sonrası doğrulanmadığı için yayın başlatılmadı. Kullanıcıdan Dokploy çevirisini kapatması istendi. chrome://settings/languages açılması tarayıcı URL güvenlik politikası tarafından engellendi; alternatif tarayıcı komutlarıyla aşılmadı.

Kullanıcı Chrome çeviri adımını tamamladığını bildirdi. Dokploy yeniden yüklendiğinde İngilizce arayüz ve reklamanaliz-V1.1.16 yayın hedefi doğrulandı. Deploy > Confirm ile yayın başlatıldı; en yeni manual deployment Running, kaynak klonlama ve Nixpacks build başlangıcı gözlendi. Yayın kabul testi sürüyor.


## Son yayın doğrulaması
- İlk skor düzeltmesi 4ec63fc commit ile Dokploy üzerinde Done; canlıda veri yokken 0/100 doğrulandı.
- Yayın kaynağı reklamanaliz-V1.1.16 olarak doğrulandı.
- 44aa2fa3 commit: kartta Veri yok ve son 30 gün ölçüm bekleme açıklaması; yayın Done ve canlı açıklama doğrulandı.
- 8fd012a8e526bdb1a65f963050186e8131de71e7 commit: boş veri aksiyonunun senkronizasyon düğmesi ve durum metinleri; otomatik yayın Running, son doğrulama bekleniyor.

- Son 8fd012a yayını Done. Canlıda 0/100, Veri yok açıklaması, Ölçüm bekleniyor durumu ve Senkronizasyonu Aç düğmesi doğrulandı.
- Son kodla 26 mevcut kapsam/encoding testi geçti; git diff --check temiz. Güncel dört dosyalık yama artifacts/octo-health-fix-20261008.patch dosyasına yazıldı.

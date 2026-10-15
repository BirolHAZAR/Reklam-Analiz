# Büyük Meta hesabı senkronizasyonu — 15 Ekim 2026

## Canlı tanılama

- `reklamanaliz` kullanıcısının 83 numaralı Meta hesabındaki iş 55 başarısız. Son deneme 14 Ekim 12:03:22–12:03:55 Türkiye saati. Kampanya/reklam/metrik sayıları sıfır; kampanya panelinde de bu hesap boş.
- Hata: `Meta verilerini okuma: Platforma ulaşılamadı. Lütfen tekrar deneyin.` Önceki kota bekleme bilgileri başarısız işin sonucunda kalmış.
- Aynı hesabın geniş alanlı `/ads` ilk sayfası canlı tanılamada HTTP 200: 100 kayıt, sonraki sayfa var, 2,8 saniye.
- Günlük reklam düzeyindeki 365 günlük `/insights` ilk sayfası 30,05 saniyede `ReadTimeout` verdi. Ham URL, token veya sağlayıcı hata gövdesi yazdırılmadı.
- Aynı sorgunun 30 günlük sürümü HTTP 200: 26,59 saniye, bu dönemde sıfır metrik.

## Hazırlanan düzeltme

- Günlük performans sorguları en fazla 30 günlük, kesişmeyen aralıklara bölünür. Zaman aşımı yaşayan aralık ikiye bölünerek bir güne kadar küçültülür. Bağlantı kesintisi veya kota hatası tarih aralığını bölmez.
- Her aralık mevcut sayfalama kontrol noktalarını kullanır. Büyük işlerin kota beklemeleri için kontrol noktası süresi 24 saat olur; başarılı iş sonunda temizlenir.
- Geçici taşıma/yanıt hatası ayrı sınıfla iletilir. Logda yalnız işlem adı ve istisna türü bulunur.
- Taşıma hataları, kota beklemelerinden bağımsız en fazla üç kez 60 saniye sonra tekrar edilir; bu sırada iş pending kalır. Kota bekleme üst sınırı 48 olarak korunur. Terminal hatada eski bekleme alanları temizlenir.

## Doğrulama ve yayın

97 test başarılı: Meta envanteri/sayfalama, yıllık tarih kapsamı, zaman aşımında aralık bölme, bağlantı hatasında gereksiz istek üretmeme, bağımsız taşıma tekrar sınırı, kota sınırı, hesap ayrımı, OAuth, CSRF ve Sync Center. Django sistem kontrolü temiz.

Komut: `manage.py test core.test_meta_sync_checkpoint core.test_meta_campaign_inventory core.test_meta_connection_health core.test_campaign_panel_sync core.test_sync_center core.test_sync_policy core.test_ads_integrations --settings=config.settings_test_seo --noinput`

Hazır commit: `9e587d6e`. İlk push otomatik güvenlik incelemesinde özel canlı yayın onayı için durduruldu. Kullanıcı “Evet, canlıya al” diyerek bu sürümün main dalına gönderimini ve web/worker güncellemesini açıkça onayladı. Push başarılı; Dokploy bu hash için dağıtımı başlattı. Tam aktarım henüz doğrulanmış değildir.

Dokploy yayını **Done**, süre **3m 59s**. Yeni web container `6cb5e32799d5` kaynak HEAD'i `9e587d6e`; kontrol noktası TTL'i 86400 saniye. Worker ve Beat otomatik eşitlendi (imaj `e30ef5ae10ca`). Yeni worker `3ea27dfa4edf` HEAD'i `9e587d6e`; `insights_between` ve `transport_retries` kodları doğrulandı.

`reklamanaliz` oturumunda hesap `1162849304081593` için Kampanyaları Çek bir kez çalıştırıldı. Yeni iş **56**. 15 Ekim 10:05 Türkiye saati kontrolünde reklam envanteri **908 kayıtla tamamlandı**, iş performans okumasında running. Veritabanına nihai yazım henüz gerçekleşmedi. Başlatma kanıtı: `artifacts/meta-20261015/senkron-baslatildi.jpg`.

## Canlı kabul — tamamlandı

15 Ekim yaklaşık **10:15 Türkiye saati** iş 56 **completed** oldu:

- 912 kampanya
- 908 reklam grubu
- 908 reklam
- 908 kreatif
- 365 günlük dönemde Meta'nın döndürdüğü performans metriği: 0; toplam harcama 0. Gerçek olmayan metrik üretilmedi.

Kontrol noktaları başarı sonunda temizlendi. Kampanya panelinde hesap satırı 912 kampanya / 908 reklam gösterdi; seçilen hesabın listesinde 912 kampanya kartı oluştu. İlk kartın tarihleri 2020 yılına ait; eski envanter, son 365 günde metrik varmış gibi gösterilmedi.

Sync Center'da Facebook **Senkron tamam**, Instagram reklamları **Reklam: Senkron tamam**; Google Ads **Senkron tamam**. Günlük aktarımlar 912/908/908/908 olarak göründü.

Kanıtlar: `artifacts/meta-20261015/senkron-tamam.jpg`, `artifacts/meta-20261015/kampanyalar-yuklendi.jpg`.

İlk yapılacaklar listesindeki büyük Meta hesabı aktarımı maddesi tamamlandı. Bu oturumdan sonra kullanıcı yeni commitler için sürüm numarasının her seferinde sorulmasını istedi; `AGENTS.md` ve `COMMIT_ADLANDIRMA.md` yerelde oluşturuldu, yeni commit oluşturulmadı.

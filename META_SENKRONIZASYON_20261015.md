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

Tam aktarım henüz doğrulanmadı; test ve canlı yayın sonucu bu belgeye eklenecek.

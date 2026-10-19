# Platform veri denetimi — 19 Ekim 2026

## Canlıda doğrulanan bulgular

- Facebook `1162849304081593`: veritabanı ve Meta API 912 farklı kampanya kimliği içeriyor. 799 kampanyanın adı Instagram Post; ad tekrarı kimlik tekrarı değil.
- Sağlayıcı 903 ACTIVE, 9 ARCHIVED kampanya döndürüyor. ACTIVE kayıtların 900 tanesinin bitişi geçmiş. Son kampanya bitişi 30 Aralık 2022; bitişi olmayan kayıtlar ayrıca değerlendiriliyor. Yeni aktiflik sorgusu 3 güncel kampanya ve 0 aktif reklam döndürdü.
- Meta günlük reklam/kampanya metrik geçmişi boş. 20 Ekim 2025–19 Ekim 2026 doğrudan hesap Insights sorgusu da boş. Yakın dönem veri kaybı kanıtlanmadı; ölçüm yokluğunu 0 TL göstermek hatalıydı.
- Instagram: sağlayıcı ve yerel gönderi sayısı 8. Son 30 günde 152 ölçüm satırı, aynı gönderilerin farklı günlerdeki toplam sayaçlarını içeriyor. Tüm satırları toplamak 76 beğeni, gönderi başına son ölçümü toplamak 4 beğeni veriyordu. Organik ana görünüm doğruydu; ortak rapor özeti hatalı topluyordu.
- Google Ads test hesabı `6616873903`: sağlayıcı ve veritabanı kampanya sayısı 0. Tarih segmentli metrik sorgusundan envanter türetilmesi sıfır gösterimli reklamları atlayabiliyordu.

## Hazırlanan düzeltmeler

- Facebook/Meta, Google Ads, eski Instagram reklam akışı ve LinkedIn kampanya raporlarında yalnız aktif ve yayın takvimine uygun kampanyalar okunur. Meta/Google reklamlarında kampanya, reklam grubu ve reklam aktifliği birlikte kontrol edilir.
- Instagram organik profili için reklam kaynağı bağlı Meta reklam hesabıdır. TikTok/YouTube/X için mevcut olmayan senkronizasyon desteği varmış gibi gösterilmez.
- Başarılı ve eksiksiz Meta/Google çekimi eski kayıtları silmeden aktif envanteri uzlaştırır. Başarısız veya kayıt sınırını aşan çekim eski kayıtları topluca pasife çevirmez. Google envanteri metriklerden ayrı okunur.
- Panel varsayılanı aktif kampanyalardır. Tüm geçmiş kayıtlar ayrı filtrede korunur. Aktif ve geçmiş sayıları ayrılır; bitişi geçmiş kampanya tamamlandı görünür. Ölçüm yoksa null/—, ölçülmüş sıfır ise 0 gösterilir.
- Önceki hesap isteğinin geç dönerek yeni hesap seçimini ezmesi engellenir.
- Instagram organik görevinde son 15 günde yayımlanan gönderiler sayfalama ile bulunur ve günlük güncellenir. Aynı gönderinin aynı günkü ölçümü güncellenir; eski gönderiler ve geçmiş ölçümleri korunur.
- Rapor toplamları, gönderi başına seçili dönemdeki son ölçümden hesaplanır. Bunlar toplam sayaç değerleridir; dönem içinde kazanılan yeni etkileşim sayısı olarak yorumlanmamalıdır.

## Doğrulama

- İlgili 11 test modülünde 161 test geçti; Django sistem kontrolü temiz.
- Testler aktiflik/takvim filtreleri, başarısız çekimde geçmişin korunması, bağımsız Google envanteri, eksik ölçüm ile gerçek sıfır ayrımı, gönderi sayfalaması, günlük tekrar güncelleme ve son ölçüm toplamlarını kapsıyor.
- Yeni üç Google Ads GAQL sorgusu canlı test hesabında salt okunur çalıştırıldı: üçü de başarılı, sıfır kayıt.
- Yeni Meta kampanya/reklam sorguları canlıda salt okunur doğrulandı: 3 güncel kampanya, 0 aktif reklam. Canlı kayıtlar değiştirilmedi.
- Yerel Django sunucusu proje sanal ortamıyla yeniden başlatıldı; tarayıcıda panel açılıyor.

Kaynak: [Google Ads sıfır metrik davranışı](https://developers.google.com/google-ads/api/docs/reporting/zero-metrics).

## Yayın durumu

Kullanıcı canlı yayını ve `reklamanaliz V1.2.9` numarasını onayladı. Önceki commit `reklamanaliz V1.2.8` (`4e4c5129`). Yayın sonrasındaki canlı doğrulama ayrıca operasyon kaydına işlenecek.

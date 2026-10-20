# Gerçek metrik zorunluluğu — 20 Ekim 2026

## Kesinleşen nedenler

- Canlı Reklam Hareketleri, seçili dönemde ölçüm kaydı aramadan 908 eski reklamı listeliyor ve eksik ölçümleri sıfır/0 puan gösteriyordu. Gösterilen 15.10.2026 tarihi yayın tarihi yerine yerel oluşturma tarihiydi.
- Canlı Facebook hesabı `1162849304081593`: 912 geçmiş kampanya, 3 takvime uygun kampanya, 0 aktif reklam. Aynı hesabın gerçek API sorgusunda son 30 günlük kampanya/reklam metrikleri de boş.
- Mevcut Meta izni iki reklam hesabına erişiyor. Diğer hesap `1608518633550120` / Birol Hazar, 9–10 Ekim 2026 için gerçek rapor döndürüyor. Kampanya: `120253345320420652` / ReklamAnaliz | Web Sitesi Tanıtımı. Toplam 2.209 gösterim / 129 tıklama. Kampanya kayıt durumu ACTIVE olsa da güncel yayın takvimine uygun değil; yalnız aktiflik/takvim filtresiyle rapor çekmek gerçek yakın dönem verisini kaçırıyordu.
- Google Ads `6616873903` resmi test hesabında kampanya/metrik yok. Üretim performansı varmış gibi gösterilmemeli.

## Kullanıcının son kuralı

Ölçüm dönmeyen reklam/kampanya, reklam grubu ve kreatif kayıtları saklanmayacak, listelenmeyecek ve AI/kural işlemlerine gönderilmeyecek. Sağlayıcının gerçekten döndürdüğü sıfır ölçüm ile hiç ölçüm göndermemesi ayrılır. Önce hazırlanan ölçümsüz envanter seçeneği kaldırıldı.

## Yapılan değişiklikler

- V2 yazma katmanı ölçüm alanı bulunmayan veya `metrics_available=False` payload için hiçbir performans nesnesi oluşturmaz.
- Meta/Google senkronizasyonu günlük kampanya raporunu doğrudan sağlayıcıdan alır; kampanya metriklerinin gelmesi reklam metriğine bağımlı değildir.
- Ölçümlü rapor akışı yalnız şu anda yayında olanlara kısıtlanmaz. Seçili dönemde gerçek metrik döndüren tamamlanmış/duraklatılmış kampanyalar da raporlanır. Aktiflik filtresi ayrıca kullanılabilir.
- Envanter API sonuçları bellekte ilişkilendirme için kullanılır; yalnız ölçüm içeren kampanyalar ve reklamlar yazılır. Sağlayıcı okumalarının hepsi tamamlanır; yazma ve temizlik aynı transaction içinde yapılır. Başarısız API okuması veritabanını temizlemez.
- `prune_unmeasured_ads --all --apply` veya `--account <id> --apply`, hiçbir metrik geçmişi bulunmayan nesneleri temizler. Ölçümü bulunan reklamlar, gruplar, kreatifler, kampanyalar ve geçmişleri korunur. `--apply` olmadan yalnız aday sayıları hesaplanır.
- Reklam Hareketleri ve kampanya API'leri ölçüm olmayan kayıtları kabul etmez. Eksik ölçümler null/—; skor yok; tarih gerçek yayın başlangıcından alınır.
- Yönetici manuel senkronizasyonu ile kişisel paket kontrolü arasındaki tutarsızlık yalnız manuel işlem için düzeltildi. Normal kullanıcı paket kontrolü ve otomatik görevlerin paket politikası korunur.

## Doğrulama ve yayın durumu

- Gerçek API sorguları mevcut izinlerle, sırlar yazdırılmadan çalıştırıldı.
- Veri bulunan hesap aynı yerel kullanıcı/müşteri altında PlatformAccount 81 olarak bağlandı. Gerçek senkronizasyon: 1 kampanya, 1 reklam, 2 günlük kampanya metriği ve 2 günlük reklam metriği. Yerel Reklam Hareketleri API'si 2.209 gösterim / 129 tıklama; kampanya API'si 1 ölçümlü kampanya döndürdü.
- İlgili testler ölçümsüz payload'ın nesne üretmemesini, gerçek sıfırın korunmasını, bağımsız kampanya metriklerini, dönem filtresini, müşteri kapsamını, başarısız çekimde geçmişin korunmasını, metrikli geçmişe dokunmayan temizliği ve personel dışı paket kontrollerini kapsar.
- Canlı hesap seçimi ve canlı veritabanı henüz değiştirilmedi. Yayında yeni hesabın mevcut Meta bağlantısı ve aynı müşteri kapsamıyla eklenmesi, ölçümlü senkronizasyonun tamamlanması ve eski ölçümsüz kayıtların temizlenmesi gerekir.
- Kullanıcı, önceki commit ve son onaylanan sürüm V1.2.9 hatırlatıldıktan sonra `10` numarasını seçti. Değişiklikler `reklamanaliz V1.2.10` adıyla kaydedilip yayımlanacak; canlı sonuçlar ayrıca operasyon raporuna yazılacak.
- Son kontrol: 9 ilgili modülde 141 test başarılı; Django sistem kontrolü temiz. Gerçek yerel API sorguları 1 reklam / 1 kampanya / 2.209 gösterim / 129 tıklama ile doğrulandı.

Google Ads'in tarih segmentli raporları, bütün seçili metrikleri sıfır olan satırları döndürmeyebilir; satır yokluğundan yapay sıfır ölçüm üretilmez. Kaynak: https://developers.google.com/google-ads/api/docs/reporting/zero-metrics

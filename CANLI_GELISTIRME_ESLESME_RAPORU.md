# Canlı ve geliştirme eşleşme raporu

Son kontrol: 2 Ekim 2026, yaklaşık 16:46–16:48 Türkiye saati.
Geliştirme: C:\Projeler\instagram, dal: reklamanaliz-V1.16.

## Güncel sonuç

Geliştirme kaynak kodu ile canlı web, worker ve beat kaynak kodları eşleşiyor. Üç canlı servis aynı commit ve aynı Docker imajıyla çalışıyor. Geliştirmedeki gizlilik kaydı da yedeklenerek canlıdaki 1.1 sürümüne eşitlendi.

Migration dosyaları ve uygulama şeması eşleşiyor. Canlının migration uygulama geçmişinde yerelde bulunmayan eski bir kayıt var; bu tarihsel fark korunmuştur. Ortamların kullanıcı verileri, bağlantı tokenları, sırları ve çalışma zamanı ayarlarının birebir aynı olması hedeflenmemiştir.

## Kod ve dağıtım kanıtları

- Yerel HEAD ve üç canlı servis HEAD: a143029a33d7afaf025772f55e097e5378a432f0.
- Üç canlı servis imajı: sha256:b356470d5faf4386e452ef8f658c0ce6a5f5c9678324269c1a61f4ee6315529f.
- Her serviste 746 Git izlemeli uygulama/dağıtım dosyası SHA-256 ile karşılaştırıldı. Windows/Linux satır sonları normalleştirildi.
- Sonuç: 746 aynı, 0 farklı, 0 eksik; web, worker ve beat için ayrı ayrı doğrulandı.
- Üç Swarm servisinin güncellemesi completed; her serviste bir Running task var.
- Canlı worker cevabı: celery@9bf83ad504bf → pong.
- Denetim sırasında dağıtım otomasyonu worker/beat güncellemelerini yürütüyordu. Mevcut sync_celery_release.py çalıştırıldığında devam eden güncellemeyi tespit edip ikinci bir güncelleme başlatmadı. Son kontroller güncellemeler tamamlandıktan sonra yapıldı.

## Gizlilik metni

| Ortam | Sürüm | Durum | Yürürlük tarihi | İçerik |
|---|---|---|---|---|
| Canlı veritabanı | 1.1 | published | 2026-10-02 | YouTube/GA4 ve Google Limited Use bölümleri mevcut |
| Geliştirme veritabanı | 1.1 | published | 2026-10-02 | Aynı içerik |
| Yerel ve canlı legal_defaults.py | Güncel | Kaynak varsayılanı | — | Aynı içerik |

İçeriğin ortak SHA-256 özeti:
81f7d89a551cbf1c81c4a700c2d64c2db12bbd13830d3856dcd57c4747bcefba

Son dağıtım kaynak dosyasını eşitledi; mevcut geliştirme veritabanını otomatik güncellemedi. Bu kontrolde geliştirmedeki eski içerik, sürüm ve yürürlük tarihi yedeklenip güncellendi. Geliştirme yedeği: gizlilik-gelistirme-1.0-yedek-20261002.json. Canlı veritabanına bu kontrolde yazılmadı.

legal_defaults.py ilk kayıt oluşturma için kullanılır. Gelecekte mevcut hukuki metinlere yapılacak güncellemelerin yalnızca bu dosyayı dağıtmakla uygulanmayacağı dikkate alınmalıdır; mevcut kayıtlar için ayrıca kontrollü bir veri güncellemesi gerekir.

## Şema ve migration kontrolleri

- Her iki ortamda bekleyen migration: 0.
- Yerelde core migration uygulama kaydı: 78; canlıda: 79.
- Canlıdaki tarihsel ek kayıt: 0077_live_integration_integrity. Bu ada ait migration dosyası mevcut kaynakta yok.
- İki veritabanındaki 115 core tablosu Django/PostgreSQL introspection ile karşılaştırıldı: kolon adı/türü/null/default bilgileri ile introspection tarafından döndürülen constraint ve indeks bilgileri aynı; farklı tablo: 0.
- Ek geçmiş kaydı mevcut uygulama şemasında fark oluşturmuyor. Geçmiş kayıt silinmedi; fake migration uygulanmadı.
- Bu karşılaştırma tüm PostgreSQL özelliklerinin, tetikleyicilerin, verilerin veya ortam ayarlarının birebir eşitliği iddiası değildir.

## Önceki işlemlerin yeri

1. Meta/Celery düzeltmeleri 230f5ca3, YouTube/GA4 bağlantı geliştirmeleri ae5317eb commitleri üzerinden geliştirmede yazılıp canlıya dağıtılmıştır.
2. Gizlilik eki önce canlı LegalDocument kaydına kontrollü olarak uygulanmış; aynı içerik geliştirmedeki core/legal_defaults.py dosyasına eklenmiştir. Kullanıcının son a143029a dağıtımıyla kaynak dosyası da üç canlı serviste eşitlenmiştir.
3. Google OAuth üretim durumu, marka yayını ve doğrulama başvurusu Google tarafındaki yapılandırmalardır; kaynak kod commitlerinden bağımsızdır.
4. Bağlantı yeniden yetkilendirmeleri ve tokenlar canlı veritabanındaki operasyon kayıtlarıdır.

## Bu kontrolün yaptığı değişiklikler

- Uygulama kaynak koduna yeni değişiklik yapılmadı.
- Canlı bağlantı ayarları ve tokenlara müdahale edilmedi.
- Geliştirme veritabanındaki gizlilik belgesinin içerik, sürüm ve yürürlük tarihi canlıyla eşitlendi; eski kayıt yedeklendi.
- Bu rapor güncellendi. Rapor ve yeni geliştirme yedeği yerel dosya değişiklikleridir; uygulama kodunun eşleşmesini etkilemez.
- Yeni bir uygulama dağıtımı gerektiren kod farkı bulunmadı.
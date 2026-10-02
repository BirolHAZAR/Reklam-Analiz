# Canlı ve geliştirme eşleşme raporu

Kontrol tarihi: 2 Ekim 2026. Geliştirme dizini: `C:\Projeler\instagram`. Dal: `reklamanaliz-V1.16`.

## Sonuç

Canlı ve geliştirme **tam olarak aynı değildir**. Uygulama bağlantı/worker kodları aynı sürümdedir. Kalan somut fark gizlilik politikasının kaynak dosyası ve veritabanındaki sürümüdür. Ayrıca canlı migration geçmişinde eski, artık dosyası bulunmayan tek kayıt vardır. Bu denetimde canlıya yeni kod dağıtılmadı veya veritabanı değiştirilmedi.

## Kod ve sürüm kanıtı

- Yerel HEAD, GitHub dalı ve üç canlı container içindeki `/app` Git HEAD: `ae5317eb108cc4ce56e23c86bae7701a637d269f`.
- Web, worker ve beat aynı imajda: `sha256:a1cc945324f81f34fbd371546d5cea03914a29fb769fa34a0643c041a04a261d`.
- Her canlı serviste 735 Git izlemeli uygulama dosyası SHA-256 ile karşılaştırıldı. Windows/Linux satır sonları normalleştirildi. 734 aynı; 1 farklı: `core/legal_defaults.py`. Eksik dosya yok.
- Kök dizindeki 11 dağıtım/başlatma/bağımlılık dosyası üç canlı serviste de aynı: `nixpacks.toml`, `requirements.txt`, `ops/sync_celery_release.py`, başlatma betikleri dahil. Toplam her serviste 746 dosyadan 745 aynı.
- Canlı Git çalışma ağacında uygulama kaynak kodu değişikliği yok. İmaj üretimine ait `.nixpacks/` ve depoya alınmış Windows sanal ortamındaki bir NumPy dosyası değişikliği görünüyor; bunlar uygulama kaynak değişikliği değildir. Python paketleri ve işletim sistemi ortamının birebir eşitliği bu kaynak denetiminin kapsamında değildir.

## Şimdiye kadar yapılan değişikliklerin yeri

1. YouTube/GA4 OAuth geliştirmesi `ae5317eb` commitinde: 16 dosya, 421 ekleme / 49 çıkarma. Ayrı okuma izinleri, callback ve hesap seçimi, token yenilemesi, GA4 rapor okuması ve worker planı geliştirmede yazıldı, GitHub'a gönderildi ve canlıya dağıtıldı. Bu kod üç canlı serviste yerelle aynıdır.
2. Önceki Meta/Celery düzeltmeleri `230f5ca3` commitinde ve aynı canlı sürümün geçmişindedir.
3. Son gizlilik eki canlı `LegalDocument` kaydına doğrudan uygulandı; önceki sürümün yedeği alındı. Aynı metin geliştirmedeki `core/legal_defaults.py` dosyasına da eklendi; **bu son kaynak değişikliği henüz commit/push/deploy yapılmadı**.
4. Google Cloud üretim durumu, marka, kapsam gerekçeleri ve inceleme gönderimi Google tarafındaki yapılandırma işlemleridir; Git kodu değildir. Hesap yeniden yetkilendirmeleri ve şifreli tokenlar canlı veritabanındaki kayıtlardır. Gizli anahtarlar Git'e eklenmedi.

## Gizlilik ve veritabanı farkı

| Katman | Doğrulanan durum |
|---|---|
| Canlı sayfayı besleyen kayıt | Gizlilik 1.1, yayında, YouTube/GA4 ve Limited Use bölümleri var |
| Canlı imajdaki `legal_defaults.py` | Yeni iki bölüm yok |
| Yerel `legal_defaults.py` | Yeni iki bölüm var; commit edilmemiş |
| Yerel geliştirme veritabanı | Gizlilik 1.0, yayında; yeni bölümler yok |

Yerel kaynak dosyasındaki güncel gizlilik içeriğinin SHA-256 özeti, canlı veritabanındaki yayımlanmış içeriğin özetiyle **birebir aynı**:
`81f7d89a551cbf1c81c4a700c2d64c2db12bbd13830d3856dcd57c4747bcefba`.

Bu yüzden canlıdan bütün projeyi yerelin üzerine kopyalamak doğru eşitleme değildir: uygulama kodu zaten aynı committe; güncel gizlilik metni canlı veritabanında ve yerel kaynakta vardır. Eksik olan, mevcut geliştirme veritabanını güncelleyen ve sonraki dağıtımda tekrarlanabilen bir veri migration'ı/yönetim komutudur. Sadece `legal_defaults.py` dağıtımı mevcut kayıtları güncellemez; bu dosya ilk seeding sırasında kullanılır.

Kullanıcı/hesap verileri, tokenlar, `.env` ve müşteri veritabanları ortamlar arasında topluca kopyalanmamalıdır. Ortamların kodu, migration yapısı ve gerekli ortak başlangıç verileri eşleşmeli; canlı bağlantı sırları ve gerçek operasyon verileri kendi ortamında kalmalıdır.

## Migration ve çalışma durumu

- Yerel: 78 core migration kaydı; son dosya `0078_local_display_names`; bekleyen migration 0.
- Canlı: aynı güncel migration dosyaları ve son migration; bekleyen migration 0. Geçmişte ayrıca `0077_live_integration_integrity` uygulanmış görünüyor; dosyası mevcut projede veya canlı imajda yok. Yerelde bu geçmiş kaydı yok.
- Bu tek eski kayıt, iki ortamın migration geçmişlerinin birebir eşit olmadığını gösterir. Bekleyen migration olmaması tek başına bütün PostgreSQL constraint/index yapılarının eşitliğini kanıtlamaz. Ayrı şema incelemesi olmadan bu eski kayıt silinmemeli veya rastgele fake migration uygulanmamalıdır.
- Canlı worker ping başarılı. Web/worker/beat sürüm ayrışması görülmedi.
- Yerel veritabanı salt okunur denetlendi; bağlantı hedefi yerel PostgreSQL olarak doğrulandı. Canlı tokenlar geliştirmeye taşınmadı.

## Eşitleme için gereken somut adımlar

1. Canlıda yayımlanan ve yerel kaynakta zaten bulunan gizlilik ekini esas alarak idempotent bir veri migration'ı veya yönetim komutu eklemek. Mevcut metni/şirket bilgilerini korumalı, aynı bölümleri tekrar eklememeli, yayındaki canlı 1.1 kaydını gereksiz değiştirmemeli.
2. Önce geliştirmede uygulamak; yerel gizlilik 1.1 ve içerik eşleşmesini kontrol etmek. Komut/migration'ın tekrarlı çalışmasının güvenli olduğunu test etmek.
3. Yalnız ilgili kaynakları commit/push yapmak ve normal Git/Dokploy dağıtımıyla canlıya almak. Çalışan container dosyalarını doğrudan değiştirmemek.
4. `ops/sync_celery_release.py` akışını kullanarak web, worker ve beat'i aynı yeni imaja geçirmek; migration, anonim gizlilik sayfası, worker ve mevcut bağlantıları yeniden doğrulamak.
5. Eski `0077_live_integration_integrity` kaydının getirdiği constraint/index değişikliklerini ayrı salt okunur şema karşılaştırmasıyla belirlemek; gerekirse yeni ve kayıtlı bir migration ile eşitlemek. Geçmiş kaydı silerek sorunu gizlememek.

Bu rapor denetim sonucudur; yukarıdaki yeni veri migration'ı ve dağıtım henüz yapılmış değildir. Google doğrulama başvurusu incelemede ve mevcut canlı platform bağlantıları korunmuştur.

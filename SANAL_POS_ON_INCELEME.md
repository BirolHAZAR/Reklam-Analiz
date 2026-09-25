# Sanal POS ön incelemesi — düzeltme yapılmadı

> Bu dosya ilk incelemenin kaydıdır. Sonraki kullanıcı komutuyla yerel düzeltmeler yapıldı; güncel durum ve admin ekranları [POS_YEREL_KURULUM.md](POS_YEREL_KURULUM.md) içinde açıklanır. Canlıya yayın yapılmadı.

25 Eylül 2026. Bulgular yerel kaynak koduna dayanır. Canlı site, üretim kayıtları ve sunucuda bekleyen değişiklikler doğrulanmadı. Sağlayıcının ret yazısı henüz paylaşılmadığı için aşağıdakiler kesin ret nedenleri değil, başvuru ve ödeme işletimi riskleridir.

## Öncelikli bulgular

1. **Kritik: Gerçek tahsilat doğrulanmadan ödeme tamamlanıyor.** `core/views/payment.py` kart işlemlerinde doğrudan `completed` ödeme oluşturuyor; `core/services/payment_methods.py` gerçek sağlayıcı yerine `PROVIDER_DEMO` ve `demo_tok_` üretiyor. Abonelik ve ek paket akışları bundan etkileniyor. Öneri: seçilen sağlayıcının onaylı ödeme akışını ve doğrulanmış bildirimini bağlamak; tutar/sipariş kontrolü ve tekrar gelen bildirimde tek aktivasyon sağlamak. Kullanıcı komutu olmadan değiştirilmedi.

2. **Şirket kimliği kaynakları tutarsız.** Footer'da `HZRSoft Yazılım Dijital Pazarlama Danışmanlık ve Ticaret` ve Bağcılar adresi var. `LegalSiteSettings.load()` varsayılanında `HZR Yazılım Danışmanlık Dijital Paz. LTD ŞTİ` ve yalnızca `Bakırköy` bulunuyor; vergi/telefon/MERSİS alanları boş kalabiliyor. Yönetimde düzeltilmiş olabilir; üretim kayıtları görülmedi. Öneri: başvuru evrakındaki resmi unvan/adres/vergi bilgileri ile site, sözleşme ve fatura verilerini tek kaynaktan tutarlı sunmak.

3. **Hukuk sayfalarının gerçekten yayında olduğu doğrulanmalı.** Varsayılan 20 belge taslak oluşturuluyor; taslak detayları anonim kullanıcıya 404 veriyor. Satın alma beş zorunlu belge yayımlanmadan engelleniyor. Bu koruma mevcut ve yerinde; belgelerin kaynakta bulunması başvuru incelemesinde erişilebilir oldukları anlamına gelmiyor. Öneri: gizlilik, mesafeli satış, ön bilgilendirme, iade/iptal ve ilgili hizmet koşullarının anonim erişimini kontrol etmek; gerçek şirket verileriyle içerik onayından sonra yayımlamak.

4. **Teslimat/aktivasyon şartları daha açık sunulmalı.** Kart ve havale için aktivasyon açıklamaları sözleşmelerde mevcut; ayrı ve kolay bulunabilir teslimat/hizmet ifası sayfası yok. Havalede manuel onayın azami süresi ve gecikmede izlenecek yol açık değil. Öneri: dijital hizmet olduğunu, fiziksel gönderim yapılmadığını, aktivasyon süresini ve destek kanalını görünür biçimde belirtmek. Bunun zorunlu ayrı bir URL olması gerektiği iddia edilmiyor.

5. **Yıllık paketin toplam bedeli fiyat kartında belirsiz.** Fiyat kartları yıllık seçimde de aylık eşdeğer ve `/ay` gösteriyor. Checkout'ta toplam ve KDV ayrımı mevcut. Öneri: fiyat kartında yıllık toplam tahsilatı, ödeme dönemini, yenileme yöntemini ve iptal koşullarını birlikte göstermek.

6. **Kart bilgilerinin uygulamaya gönderilmesi ayrıca değerlendirilmeli.** Checkout formu kart numarası/CVV alıyor. İncelenen kart kaydetme servisi tam kart numarası veya CVV'yi saklamıyor; demo token ve son dört haneyi saklıyor. Bu, tüm günlüklerin veya altyapının kart verisi bakımından incelendiği anlamına gelmez. Öneri: sağlayıcının barındırdığı ödeme formu/tokenizasyon seçeneğine göre veri akışını tasarlamak; sağlayıcıyla güvenlik gereksinimlerini doğrulamak.

## Mevcut olumlu kontroller

Hakkımızda/iletişim sayfaları, KDV dahil tutarlar, sözleşme ve erken hizmet başlatma onay kutuları, sunucu tarafında belge hazır olma kontrolü, sürümlü sözleşme kopyası/hash kaydı ve satın alma belgesi e-posta mekanizması kaynakta mevcut. Bunlar yokmuş gibi yeniden eklenmemeli.

## Sağlayıcı kaynakları

- [PayTR başvuru koşulları](https://www.paytr.com/destek-merkezi/basvuru): web sitesi için aktif gizlilik, mesafeli satış, teslimat/iade, hakkımızda ve iletişim sayfalarını belirtir.
- [iyzico Sanal POS](https://www.iyzico.com/isim-icin/sanal-pos): başvuru için site ve sözleşme içeriklerini belirtir.

Kesin çalışma sırası: sağlayıcı ve eksik yazısı → resmi şirket bilgilerinin doğrulanması → kullanıcı düzeltme komutu → yerel değişiklik/test → sunucu diff'iyle birleştirme → ayrıca yayın komutu.

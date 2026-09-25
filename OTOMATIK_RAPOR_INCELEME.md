# Otomatik rapor incelemesi — 25 Eylül 2026

İnceleme yerel kaynak kodu, form doğrulaması ve salt okunur veritabanı sorgularıyla yapıldı. E-posta gönderilmedi. Aşağıdaki rapor hataları henüz düzeltilmedi; kullanıcı onayı bekleniyor. Kullanıcının son talebiyle demo otomatik raporları test amacıyla açık bırakıldı.

## Doğrulanan sorunlar

| Alan / davranış | Kanıt ve etkisi | Önerilen düzeltme |
|---|---|---|
| Gönderim saati | `next_run_for` ve `ensure_next_run`, UTC `timezone.now()` üzerine saat yazıyor. Türkiye saati 09:00 seçimi 12:00 oluyor. Yerel rapor 37'nin saati 9, sonraki gönderimi 26.09.2026 12:00; son gönderimi 25.09.2026 12:05. | Önce Europe/Istanbul yerel saatinde hesapla, sonra veritabanına kaydet. Mevcut sonraki gönderimleri de düzelt. |
| Gece yarısı | `send_hour or 9` nedeniyle 0 değeri 9'a dönüşüyor. Salt okunur hesaplamada 00:00 seçimi ertesi gün 12:00 çıktı. | 0 geçerli saat olarak korunmalı. |
| Saat doğrulaması | HTML 0–23 sınırı var fakat sunucu formu 24 ve 32767 değerlerini kabul ediyor. Bu değerler tarih hesaplamasında hata oluşturur. | Model/form seviyesinde 0–23 doğrulaması. |
| Saat/periyot düzenleme | Düzenleme `ensure_next_run` çağırıyor; mevcut `next_run_at` doluysa yeniden hesaplanmıyor. | Saat/periyot değişince sonraki tarihi yeniden hesapla. |
| Gönderim dakikası | Beat görevi her saatin 05. dakikasında tarıyor. 09:00 planı en erken 09:05'te gönderilir; mevcut UTC hatasıyla 12:05 olur. | Gönderim taramasını dakika bazında yap; kuyruk gecikmesini ayrıca göster. |
| Aktif/pasif | Yeniden aktifleştirme `next_run_at = timezone.now()` yazıyor; seçilen saat beklenmiyor. | Seçilen saat ve periyoda göre gelecek ilk zamanı belirle. |
| Şimdi gönder | Manuel gönderim de `next_run_at` alanını ilerletiyor. Böylece planlı gönderim günü değişiyor. | Manuel gönderimin takvimi değiştirip değiştirmediğini açıklaştır; tercihen takvimi koru. |
| Başarısız gönderim | Dispatcher göndermeden önce sonraki tarihi ilerletiyor. E-posta görevi hata verirse `last_error` yazılıyor ama tarih geri alınmıyor ve otomatik yeniden deneme tanımlı değil. | Ayrı gönderim kaydı, güvenli tekrar deneme ve başarısız planın korunması. |
| Eksik sonraki tarih | `next_run_at` boş aktif raporlar dispatcher sorgusuna girmiyor. Admin üzerinden oluşturulan kayıtlarda tarih başlatma güvencesi yok. | Oluşturma/aktifleştirme için tek planlama yolu kullan. |
| Kural bazlı öneriler | HTML ve PDF kutucuğa uyuyor; düz metin e-postası kutucuk kapalı olsa da önerileri ekliyor. | Üç çıktıda aynı bölüm koşullarını uygula. |
| Rapor dönemi | Günlük rapor gönderildiği günü esas alıyor; sabah raporu tamamlanmamış günü içeriyor. Veri yoksa eski veri tarihine dönüyor. | Tamamlanmış dönemi raporla; eski veriye dönüşü açıkça belirt. |
| Aylık periyot | `monthly` sabit 30 gün; takvim ayı değil. Ayın aynı gününde gönderim garantisi yok. | Ürün kararı: “30 günde bir” yaz veya takvim ayı hesabı kullan. |
| Gönderim sonucu | E-posta altyapısı 0 döndürse de `last_sent_at` yazılıyor ve hata temizleniyor. | Başarı alanlarını yalnızca gönderim sonucu doğrulandıktan sonra güncelle. |

## Alan bazında kontrol

| Alan | Sonuç |
|---|---|
| Rapor adı | ModelForm zorunluluk ve uzunluk doğrulaması mevcut. Dosya adı slug ile üretiliyor. |
| Gönderim periyodu | Seçenek doğrulaması mevcut; aylık anlamı ve düzenleme sonrası takvim sorunu yukarıda. |
| Alıcı e-postaları | Yazılan adresler doğrulanıyor, tekrarlar büyük/küçük harf duyarsız ayıklanıyor; boş liste reddediliyor. Gerçek teslimat bu incelemede denenmedi. |
| Kampanya filtresi | Kullanıcı/ajans kapsamıyla sınırlandırılmış queryset kullanılıyor. Boş filtre tüm kapsamı içeriyor. |
| Ajans müşterisi | Seçilen müşteriye ait olmayan kampanyalar formda reddediliyor. Tüm ajans rolleriyle tarayıcı testi yapılmadı. |
| Gönderim saati | UTC, 00:00 ve aralık doğrulama hataları doğrulandı. |
| Kampanya özeti | HTML/PDF bölüm koşulu mevcut. |
| Reklam performansı | HTML/PDF bölüm koşulu mevcut. |
| Kural bazlı öneriler | Düz metin e-posta koşulu eksik. |
| Aktif gönderim | Yeniden açma seçilen saati atlıyor. |
| Sonraki gönderim | İlk planlama, düzenleme, manuel gönderim ve hata sonrası tutarlılık sorunları var. |
| Son gönderim / hata | Başarı/hata alanları var; yeniden deneme ve sıfır gönderim sonucu ele alınmalı. |

## Demo ile ilgili önemli durum

Yerel veritabanındaki iki aktif otomatik raporun (37 ve 38) sahibi demo kullanıcısı. Kullanıcı raporları bu hesapla test ettiği için otomatik rapor gönderimi açık bırakıldı; demo raporları hem kuyruğa alınabilir hem gönderilebilir. Kayıtları ve alıcıları değiştirilmedi. Son talep gereği yalnızca gerçek token/API görevleri demo hesaplarını atlar; rapor, Octo, bildirim ve diğer görevler için demo kısıtlaması eklenmez.

## Uygulanan demo değişiklikleri

- Demo kullanıcı/hesap/bağlantı işaretleri gerçek token kontrolü ve platform senkronundan ayrıldı.
- Gerçek API kullanan organik, rakip ve pazaryeri senkronları demo hesaplarını atlar. Rapor, Octo, bildirim, duyuru ve yaşam döngüsü e-postalarının kapsamı korunur.
- Günlük demo metrikleri admin zamanlamasından çalışır; ikinci sabit Beat zamanlaması kaldırıldı.
- Demo metrik yenilemesinin mevcut Octo tetiklemesi korunur.
- Reklam/gün bazında bağımsız, aynı tarih için tekrarlanabilir üretim korunur; satış hunisi sınırları ve paylaşılan kreatiflerin toplamları düzeltildi.
- Meta Ad Library token ayarları değiştirilmedi.

Kaynak değişikliklerini çalışan yerel Celery süreçlerinin yüklemesi için worker ve beat yeniden başlatılmalıdır. Canlıya yayın yapılmadı. Sunucuda bekleyen değişikliklerle yayın öncesi karşılaştırma gerekliliği devam ediyor.

## Doğrulama

- `core.test_demo_background`, `core.test_sync_policy`, `core.tests.ModelTests`: 22 test geçti; SQLite bellek veritabanında çalıştırıldı.
- Gerçek hesapların token kontrolü/senkron kuyruğu korunurken demo hesapların atlandığı doğrulandı.
- Aynı gün tekrar üretimde metriklerin değişmediği, reklamların farklı değerler aldığı ve kampanya/kreatif toplamlarının tutarlı olduğu doğrulandı.
- Django sistem kontrolü temiz; bekleyen migration yok.
- Yerelde demo admin zamanlaması aktif ve 24 saatte bir. Çalışan worker/beat bu oturumda yeniden başlatılmadı.

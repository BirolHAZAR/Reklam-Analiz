# Instagram ve Facebook bağlantı denetimi — 2 Ekim 2026

Güncelleme: Canlı SSH denetimi ve düzeltmeler sonradan tamamlandı. Güncel sonuçlar
[canlı denetim raporunda](CANLI_META_VE_WORKER_RAPORU.md) bulunur. Aşağıdaki metin
ilk, kaynak kod üzerinden yapılan incelemeyi anlatır.

Bu inceleme kaynak kod ve izole test veritabanı üzerinde yapıldı. Canlı sunucuya
dağıtım yapılmadı; canlı tokenların geçerliliği ve çalışan worker/beat süreçleri
bu ortamdan doğrulanmadı. Mevcut uygulama kimlikleri, secret değerleri, dönüş
adresleri, izin kapsamları ve kayıtlı kullanıcı bağlantıları değiştirilmedi.

## Bulgular ve düzeltmeler

| Bulgu | Yapılan işlem |
|---|---|
| Facebook token denetimi ortam değişkenlerindeki uygulama bilgilerini kullanıyordu; giriş akışı yönetici panelindeki bilgileri kullanabiliyor. | Denetim de girişle aynı kayıtlı uygulama kaynağını kullanıyor. |
| Meta uzun token yanıtında `expires_in` gelmezse callback varsayılan olarak 3600 saniye yazıyordu. | Gerçek süre `debug_token` üzerinden doğrulanıyor; doğrulanamayan süre için 1 saat varsayılmıyor. Bu koşulun canlıda gerçekleşip gerçekleşmediği henüz bilinmiyor. |
| Instagram yenilemesinde token/süre eksik yanıt başarı olarak işlenebiliyordu. | Eksik yanıt reddediliyor; çalışan token korunuyor. Süresi bitmiş token yenilenmeye çalışılmıyor. |
| Sağlık kontrolünün düzelttiği süre her bağlı hesap kaydına aktarılmıyordu. | Başarılı kontrolden sonra hesap tokenı ve süresi bağlantıyla eşitleniyor; şifreli alanlar korunuyor. |
| Token bitişi ile veri erişim bitişi aynı alan üzerinden değerlendiriliyordu. | Veri erişim bitişi ayrıca kaydediliyor; yaklaşan token/veri erişim bitişi için bildirim üretiliyor. |
| Aynı token bakım görevi eşzamanlı çalışabiliyordu. | Paylaşılan cache üzerinden görev kilidi eklendi. |
| Meta istemcileri kota başlıklarını ve bekleme sürelerini değerlendirmiyordu. | `Retry-After`, HTTP 429, Meta kota hata kodları ve kullanım başlıkları değerlendirilerek aynı token için ortak bekleme uygulanıyor. |
| Reklam senkronizasyonu sabit süreyle tekrar deniyordu. | Kota hatasında Meta'nın bekleme süresi dikkate alınıyor. Facebook/Instagram yayın istekleri otomatik tekrarlanmıyor. |

Kota koruması Facebook reklam okumaları, Instagram profil/organik API istemcisi,
Facebook organik yayın ve token bakım çağrılarını kapsar. Kullanım başlıklarında
%90 ve üstünde sonraki istek bekletilir. Başarılı isteğin sonucu korunur. Token
cache anahtarında SHA-256 özetiyle tutulur; açık token yazılmaz. Kota hatası
bağlantıyı otomatik olarak süresi dolmuş veya bağlantısı kesilmiş yapmaz.

Koruma token bazındadır. Meta'nın uygulama veya reklam hesabı genelindeki,
başka araçların da kullandığı kotaları için hiç limit hatası olmayacağı garanti
edilemez. Web ve worker aynı Redis cache'i kullanmalıdır.

## Sürekli bağlantı için canlı ortamda doğrulanması gerekenler

Instagram Login giriş akışı kısa tokenı uzun tokenla değiştiriyor. Mevcut bakım
görevi bitişten önceki 7 gün içinde yenileme yapıyor. Bu işlem kullanıcı izinlerini
geri çekerse veya servis tokenı iptal ederse kesintisiz erişim garantisi vermez.

Facebook OAuth akışı zaten uzun token değişimini yapıyor. Facebook kullanıcı
tokenı için Google'daki gibi kalıcı refresh token akışı yok; yeniden kullanıcı
yetkilendirmesi gerekebilir. Bu nedenle Facebook'a süresiz otomatik yenileme
vaadi veren bir işlem eklenmedi. Süre yaklaşınca bildirim eklendi.

`config/settings.py` içindeki `refresh-expired-tokens` görevi her saat 05. dakikada
`maintenance` kuyruğuna gönderilecek şekilde tanımlı. `nixpacks.toml` yalnızca
web servisini başlatıyor. Canlıda ayrı Celery Beat ve `maintenance` kuyruğunu
dinleyen worker çalışması gerekir. Bunların tanımlı olması çalıştıklarını kanıtlamaz.

Canlı uygulama ortamında salt okunur denetim:

```text
python manage.py audit_meta_connections
python manage.py audit_meta_connections --live
```

İlk komut kayıtlı süreleri, son sağlık kontrolünü ve bakım zamanlamasını verir.
İkinci komut ayrıca Meta üzerinde salt okunur token/profil kontrolü yapar.
Komutlar token/secret yazdırmaz, token yenilemez ve bağlantı kaydı değiştirmez.
Çıktıda `last_health_check` düzenli ilerlemeli; `api_valid`, `api_expires_at` ve
`api_data_access_expires_at` canlı kopuş nedenini belirlemek için incelenmelidir.
Worker loglarında bakım görevinin tamamlanması da kontrol edilmelidir.

## Doğrulama

OAuth giriş, hesap seçimi, izin reddi, state doğrulaması, Google token yenileme,
Instagram giriş, bildirim, demo izolasyonu, senkronizasyon politikası ve organik
akış regresyon testleri izole SQLite/cache ortamında çalıştırıldı.
Yeni testler süre doğrulamasını, token/hesap eşitlemesini, kota beklemesini,
geçici hatada bağlantının korunmasını ve salt okunur denetimi kapsıyor.
Son birleşik çalıştırmada 84 test geçti; Django sistem kontrolü ve diff kontrolü
başarılı oldu.

Mevcut canlı ayarlar veya izin kapsamları değiştirilmeden bu kod değişiklikleri
yayınlanabilir. Önceden yanlış kaydedilmiş Facebook bitiş süresi, başarılı bakım
kontrolünde API'nin verdiği gerçek süreyle düzeltilecektir. API'ye gerçekten
geçersiz gelen token için yeniden bağlantı gerekir.

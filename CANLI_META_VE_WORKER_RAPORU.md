# Canlı bağlantı ve worker denetimi — 2 Ekim 2026

Canlı sunucuya mevcut SSH erişimiyle girildi. Düzeltme `230f5ca3` commit'iyle
`reklamanaliz-V1.16` dalına gönderildi; Dokploy yayını tamamlandı. Web, worker
ve Beat'in aynı Docker imajını çalıştırdığı doğrulandı:
`sha256:80112d304957e84c617e8aba16c36603311a40ba7f4b213c8f908db2d254dc74`.

## Sonuçlar

| Kontrol | Sonuç |
|---|---|
| Token bakım görevi, gerçek Celery worker üzerinden | 8 bağlantı kontrol edildi; 8 aktif, 0 süresi dolmuş, 0 kontrol hatası |
| Facebook reklam hesabı | Yetkilendirildi; canlı kampanyalar ekranda listelendi |
| Instagram profesyonel hesabı | Aktif; profil ve medya okuması başarılı |
| Google OAuth tokenı | Geçerli; `adwords` izni var, uygulama kimliği eşleşiyor; otomatik token yenilemesi başarılı |
| Google kampanya verisi | HTTP 401: sağlayıcının istediği iki adımlı doğrulama eksik; aşağıdaki kullanıcı işlemi gerekli |
| Worker | `pong` yanıtı; sekiz kuyruğun tamamı dinleniyor |
| Beat | Tek replika çalışıyor; periyodik görev gönderimleri loglarda doğrulandı |
| Zamanlanmış görev kayıtları | Worker'da eksik kayıt yok |
| Redis broker ve cache | Erişim/okuma/yazma başarılı; incelenen sekiz kuyrukta birikme yok |
| Veritabanı | Bekleyen migrasyon yok |
| Django üretim/sistem kontrolleri | Hata veya uyarı yok |
| HTTPS | HTTP 200; HTTP adresi HTTPS'e yönleniyor |
| INSTAGRAM_ACCESS_TOKEN ortam bağlantısı | Geçerli; reklam okuma erişimi de hazır |
| Meta Ad Library ortam bağlantısı | Meta erişim kaydı eksik; hata `10 / 2332002` |

Bakım görevi kimliği: `c99e7bfe-395d-40af-9509-679737610e96`.
Tablodaki token geçerliliği, tüm ürün API'lerine erişim izni anlamına gelmez;
Google ve Ad Library kısıtları ayrıca canlı veri istekleriyle belirlenmiştir.

## Kopuş nedenleri ve yapılan düzeltmeler

Worker ve Beat 28 Eylül'den kalan imajı çalıştırıyordu. Web yayını bu servisleri
güncellemiyordu. Eski bakım kodu, API'de geçerli olan Instagram bağlantısını
`expired` durumuna geçiriyordu; yeni kodun salt okunur profil kontrolü aynı
bağlantıyı geçerli buldu. Servisler güncellendi ve bakım göreviyle durum düzeltildi.

Facebook'un reklam tokenı Meta'da geçerliydi. Meta token için `expires_at=0`
döndürmesine rağmen kayıtta 1 Ekim'e ait geçmiş bir yerel bitiş vardı. Bu süre
ekranda yeniden bağlantı uyarısına neden oluyordu. API açıkça token bitişi
olmadığını bildirdiğinde eski yerel süre artık temizleniyor. Veri erişim bitişi
ayrı tutuluyor. Yeni OAuth girişinde de bu yanıt için yapay 1 saatlik süre üretilmiyor.

Bu düzeltmeler mevcut uygulama kimliği, App Secret, OAuth dönüş adresi veya izin
kapsamını değiştirmedi. Facebook ve Instagram yeniden bağlanmadan düzeldi.

## Kalıcı çalışma düzeni

`reklamanaliz-celery-release.timer` sunucuya kuruldu, etkin ve otomatik açılışa
alındı. Her dakika çalışan denetim, web yayını tamamlanıp container en az 60 saniye
çalıştıktan sonra mevcut worker ve Beat'i aynı imaja geçirir. Yayın sürerken
güncelleme ertelenir. Bir imaj geri alınırsa aynı başarısız imaj sürekli yeniden
denenmez. Servislerin mevcut ortam değişkenleri korunur.

Beat tek replika olarak çalışır. Zamanlama dosyası artık sunucudaki
`/var/lib/reklamanaliz/celerybeat` dizininde kalıcıdır. Worker kapanışına görevlerin
tamamlanması için süre tanınır; güncelleme sırasında mevcut worker ile yeni
worker'ın eşzamanlı başlatılması zorlanmaz.

Token bakımı her saat İstanbul saatine göre 05. dakikada `maintenance` kuyruğuna
gönderilecek şekilde tanımlıdır. Instagram yenilemesi bitişten önceki 7 günlük
pencerede yapılır. Rate limit koruması ve bakım görev kilidi güncel worker'da da
bulunuyor. Canlı kontrollerde Meta rate limit hatası görülmedi; yüksek yükte
limitlere hiç takılmama garantisi verilmez.

Instagram'ın mevcut bitişi **30 Kasım 2026, 14:42 İstanbul saati**.
Facebook'ta mevcut token için bitiş bildirilmedi; veri erişim bitişi
**30 Aralık 2026, 15:56 İstanbul saati**. Kullanıcı izni geri çekilirse veya Meta
tokenı iptal ederse yeniden yetkilendirme yine gerekebilir.

## Kullanıcı/sağlayıcı işlemi gerektiren iki eksik

**Google Ads:** Canlı kampanya isteğinin ayrıntılı hatası
`authenticationError: TWO_STEP_VERIFICATION_NOT_ENROLLED`. Google, hesap
yöneticisinin güvenlik ayarlarını değiştirdiğini ve bağlanan Google hesabında
iki adımlı doğrulama gerektiğini bildiriyor. Tokeninfo kontrolü HTTP 200,
`adwords` izni ve doğru OAuth uygulamasını doğruladı. Sunucu veya token ayarı
değiştirilmedi. Bağlantıyı yapan Google hesabında
[iki adımlı doğrulama](https://www.google.com/landing/2step/) etkinleştirilmeli;
sonrasında kampanya okuması tekrar kontrol edilmeli.

**Meta Ad Library:** Sağlayıcı `Application does not have permission for this
action` hatasını ve `10 / 2332002` kodunu döndürüyor. Ayrıca
[Ad Library API erişim sayfasındaki](https://www.facebook.com/ads/library/api/)
adımların tamamlanmasını istiyor. Bu ayrı erişim, Facebook reklam hesabının ve
Instagram profilinin çalışmasını engellemiyor; rakip reklam kütüphanesi
işlevlerini etkiler. Sunucudan izin verilemez; Meta hesabındaki erişim kaydı ve
istenen doğrulamalar tamamlanmalı. Mevcut çalışan bağlantılar bu amaçla değiştirilmedi.

## Testler ve bakım

İzole ortamda 86 regresyon testi geçti. Sürüm eşitleme yordamı için servis kapsamı,
ortam değişkenlerinin korunması, kalıcı Beat diski, devam eden yayında erteleme ve
geri alınan imajı tekrar denememe kontrolleri de geçti. Canlıda aynı yordamın web
yayınından sonra worker ve Beat'i yeni imaja otomatik geçirdiği gözlendi.

Sunucu üzerinde işletim kontrolleri:

```text
systemctl status reklamanaliz-celery-release.timer
journalctl -u reklamanaliz-celery-release.service
docker service ps reklam-analiz-worker-j2xrq4
docker service ps reklam-analiz-beats-hcni7b
```

Nixpacks container'ında yönetim komutları giriş kabuğundan, uygulama dizininde
çalıştırılmalı: `bash -lc 'cd /app/instagram_reklam_analiz && python manage.py
audit_meta_connections --live'`. Bu kabuk Nix çalışma kütüphanelerini yükler;
doğrudan `/opt/venv/bin/python` kullanmak terminalde kütüphane hatası verebilir.

Bu rapor canlıda yapılan denetimin sonucudur; ilerideki kullanıcı güvenlik/izin
değişiklikleri için kesintisiz erişim garantisi değildir.

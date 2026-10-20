# TikTok organik ve reklam akışları — 20 Ekim 2026

## Önceki eksik

Login Kit / Display API bağlantısı yalnızca ayrı profil/video raporunu okuyordu.
Ortak Organik İçerik ekranı ve günlük yenileme yalnızca Instagram içindi.
TikTok Marketing API reklam bağlantısı uygulanmamıştı.

TikTok for Business portalında bu oturumdaki hesap için uygulama bulunmadığı
görüldü. Kullanıcının onayıyla ayrımcılık karşıtı reklam politikası kabul edildi.
Geliştirici kaydı e-posta ve telefon doğrulaması gerektiriyor. Kullanıcı SMS
kodunu girdi. Geliştirici sözleşmesi için ayrıca açık onay verdi; Next denendi,
ancak portal görünür hata göstermeden ilk adımda kaldı. Eski e-posta kodunu
yenilemek için kullanıcı onayıyla CAPTCHA tamamlandı ve yeni e-posta kodu
gönderildi. Yeni kod bekleniyor. Uygulama oluşturulmadı ve reklam erişimi henüz
doğrulanmadı; kayıt isteğinin başarılı kabul edildiği iddia edilmemeli.

## Yerel geliştirme

- TikTok public video sayfalaması ortak Organik İçerik merkezi ve günlük göreve bağlandı.
- Gerçek görüntülenme, beğeni, yorum ve paylaşım sayaçları günlük snapshot olarak tutulur.
- Eksik/bozuk sayaç veya tamamlanmayan sayfalama hiçbir içerik/metrik yazmaz.
  Gerçek ölçülmüş sıfır geçerlidir. Boş hesap için sahte içerik üretilmez.
- Tek günün tekrarlanan çekimi mükerrer snapshot oluşturmaz. Dönem toplamında
  her gönderinin son yaşam boyu sayacı kullanılır; günlük snapshot'lar toplanmaz.
- TikTok Ads için ayrı uygulama ayarları, OAuth callback, reklam hesabı seçimi,
  bağlantı doğrulaması ve kampanya/reklam günlük rapor akışı eklendi.
- Organik ve Ads bağlantıları aynı TikTok platformu altında ayrı kaynaklarla
  saklanır. Organik bağlantı reklam işine; Ads bağlantısı organik içerik işine girmez.
- Marketing API v1.3 BASIC/AUCTION raporları 30 günlük pencerelerle okunur.
  Kampanya, reklam ve grup eşleştirmeleri tüm okumalar tamamlanmadan yazılmaz.
- Kampanya raporu reklam toplamına göre önceliklidir. Grup toplamları son reklamın
  değeriyle ezilmez. Metriksiz kampanya ve reklam bilgileri kalıcı kaydedilmez.
- Hesabın gerçek para birimi ve saat dilimi API'den alınır. Kimlikler / bağlantı
  sahipliği kontrol edilir; provider hata gövdeleri ve gizli anahtarlar çıktıya yazılmaz.
- Yeni ayar seçeneği için `0085_alter_integrationapplication_provider` migration'ı var.

## Yayın ve gerçek veri doğrulaması

Kullanıcı bu geliştirmelerin commit adı için `11` numarasını verdi; hazırlanacak
commit `reklamanaliz V1.2.11`. Önceki commit `reklamanaliz V1.2.10` (`f4a47100`).
Yayın doğrulaması commit sonrasında ayrıca yapılmalıdır. TikTok geliştirici ve Marketing API uygulama onayları, salt okunur
izinler ve reklam hesabı yetkilendirmesi tamamlanmadan canlı reklam çekimi
başarılı olarak raporlanamaz.

## Kontroller

Genişletilmiş 12 modülde 144 test geçti. Ardından organik OAuth için ek hesap
kimliği ve kapsam kontrolleri eklendi; dört TikTok/uygulama ayarı modülündeki
37 test yeniden geçti. Django sistem kontrolü ve diff boşluk kontrolü temiz.
TikTok Ads kartı yerel tarayıcıda görüntülendi; henüz uygulama ayarı olmadığını
doğru gösteriyor. Örnek metrikler yalnızca test veritabanında kullanıldı.

## Resmî kaynaklar

- https://developers.tiktok.com/docs/en/tiktok-api-v2-video-list
- https://developers.tiktok.com/docs/en/tiktok-api-v2-video-object
- https://github.com/tiktok/tiktok-business-api-sdk/blob/main/python_sdk/docs/AuthenticationApi.md
- https://github.com/tiktok/tiktok-business-api-sdk/blob/main/python_sdk/docs/ReportingApi.md
- https://github.com/tiktok/tiktok-business-api-sdk/blob/main/python_sdk/docs/AccountManagementApi.md

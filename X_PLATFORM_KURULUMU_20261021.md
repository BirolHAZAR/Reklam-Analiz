# X platform durumu — 21 Ekim 2026

## Güncel sonuç — 22 Ekim 2026

### Canlı sonuç (49f518d4)

- Kullanıcı yeni commit için tekrar 13 numarasını ve canlı yayını onayladı. 49f518d4 başlığı reklamanaliz V1.2.13; origin/main'e gönderildi. Web 5609920dffad, worker ccce7a4d00eb, beat 01b5197154c9 üzerinde HEAD 49f518d doğrulandı. Canlı Django check temiz.
- Yeni OAuth akışı gerçek hesabı listeledi; Reklam Analiz müşterisi (6) altında PlatformAccount 93 bağlandı. Hesap kimliği 18ce55xw65k, source x_ads_oauth, bağlantı active; şifreli token ve secret mevcut. Organik X_API_READ_ENABLED ve X_AUTO_SYNC_ENABLED false kaldı.
- Worker görevi c9965a6a-1f25-4898-bf8e-05d41cf88447 SUCCESS: son 7 gün için campaigns_synced=0, ads_synced=0, metric_rows=0. Hesap 93 için Campaign, Ad, CampaignMetricHistory, AdMetricHistory sayıları sıfır. Son eşitleme 22 Ekim 15:36 (Türkiye).
- Canlı X kampanya ekranı hatasız açıldı: 0 kampanya, erişilebilir kampanya bulunamadı, harcama para birimi “—”. Kanıt: runtime/x-ads-bagli-esitleme-basarili-20261022.png.
- Yayın sonrası bağlantı tablosunun modelde olmayan account.currency/account.timezone alanlarını okuyup sabit TRY gösterdiği saptandı. Yerel tek satırlık düzeltme extra_data.currency/timezone kullanır, bilinmeyende “—” gösterir. Bu ek görüntü düzeltmesi henüz commit/yayın edilmedi; tekrar commit numarası sorulmalıdır. Django check ve diff kontrolü temiz.

- V1.2.13 (3b76841a) kullanıcı onayıyla yayınlandı; web, worker ve beat aynı sürümde doğrulandı. X Ads uygulama kaydı 10 etkin; Consumer Key/Secret şifreli kaydedildi. Organik X ücretli okumaları kapalı kaldı.
- Kullanıcı standart X Ads OAuth izninin reklam yönetimini de kapsadığını görerek bağlantıyı onayladı. ReklamAnaliz adaptörü yalnız GET raporlama istekleri yapar. Bağlantı kartına bu kapsamı açıklayan metin eklendi.
- Kullanıcı X Ads MSA sözleşmesini; Türkiye, Europe/Istanbul, EUR kurulumu için onayladı. @HazarBirol altında 18ce55xw65k reklam hesabı oluşturuldu. Reklam, bütçe veya ödeme oluşturulmadı. Ads Manager seçili dönemde kampanya sonucu göstermiyor. Kanıt: runtime/x-ads-hesap-olusturuldu-20261022.png.
- Gerçek OAuth dönüşü accounts yanıtında currency bulunmadığından eski doğrulamaya takıldı. Resmi X SDK Account şemasında currency yoktur; Campaign.currency alanında bulunur. Düzeltme hesap keşfinde para birimini zorunlu tutmaz; yeni hesaba uydurma para birimi yazmaz. Kampanya aktarımı ve rapor ekranı para birimini kampanya yanıtından doğrular. Eksik veya karışık para birimlerinde aktarım durur.
- Boş hesap eşitlemesi sıfır kampanya/reklam/metrik kaydı oluşturur; hesap bağlantısı ve son eşitleme durumu tutulur. Gerçek kampanya aktarımında EUR, eski TRY hesap metadatasının üzerine doğru biçimde yazılır.
- Düzeltme yerelde hazır: core.test_x_ads, core.test_platform_setup, core.test_x_oauth toplam 41/41 test geçti; Django check ve git diff --check temiz. Henüz commit veya yayın yapılmadı; proje kuralı gereği yeni sürüm numarası ve yayın onayı bekleniyor. Son commit ve son onaylanan sürüm V1.2.13 (3b76841a).
- Yayın sonrası kalan işlem: X Ads OAuth bağlantısını yeniden başlat, 18ce55xw65k hesabını Reklam Analiz müşterisi için seç, gerçek salt okunur eşitlemeyi çalıştır ve sonucu doğrula. Şu an ReklamAnaliz hesap bağlantısı tamamlanmış sayılmamalı.
- Şema kaynağı: https://github.com/xdevplatform/twitter-python-ads-sdk/blob/master/twitter_ads/account.py ve https://github.com/xdevplatform/twitter-python-ads-sdk/blob/master/twitter_ads/campaign.py.

## 22 Ekim güncellemesi

- Kullanıcı yalnızca ilgili X yanıtının okunmasına izin verdi. Açık “Your X Ads API Application” e-postasında X Ads Developer Program, App ID 33559101 için Standard Ads API erişimini onaylamış (21 Ekim 18:43, posta arayüzü saati).
- /connect/x-ads/callback/ X uygulamasının izinli dönüş adreslerine eklendi; Read uygulama izni korundu.
- Ayrı x_ads IntegrationApplication sağlayıcısı, OAuth 1.0a bağlantısı, mevcut hesap seçim ekranı, kampanya / promoted tweet günlük metrikleri ve Celery aktarımı eklendi. Bu ek kod henüz commit edilmedi veya yayınlanmadı; yeni commit numarası kullanıcıdan soruldu.
- Token secret şifreli refresh_token alanında tutulur; OAuth 1.0a tokenı için yenileme işlemi yoktur. Geçici token secret da şifreli bağlantı kaydında saklanır; oturuma sır yazılmaz.
- Gerçek para birimi ve hesap saat dilimi doğrulanır. Kampanyalar, gruplar ve promoted tweet envanteri sağlayıcı kimlikleriyle eşleştirilir. Eksik metrik veya sonraki rapor hatasında kısmi kayıt yazılmaz; boş rapordan kampanya/reklam üretilmez.
- Raporlar en fazla 31 gün; her istek en fazla 7 gün ve 20 nesne. ALL_ON_TWITTER, SPOTLIGHT ve TREND yerleşimleri ayrı okunup günlük olarak toplanır; harcama mikro birimden hesap para birimine çevrilir. Rapor başına en fazla 100 istek sınırı vardır. Daha uzun dönem veya yüksek hacimli asenkron rapor işleri bu sürüme dahil değil.
- requests-oauthlib 2.0.0 ve oauthlib 4.0.0 sabitlendi. core.0086 yalnızca sağlayıcı seçeneğini ekler.
- Son ilgili test grubu: 84/84 başarılı; Django check ve migration diff temiz. Gerçek X reklam hesabı henüz yetkilendirilmedi; canlı veri aktarımı doğrulanmadı.
- OAuth 1.0 Consumer Key/Secret henüz admin X Ads kaydına alınmadı. Konsolda mevcut Consumer Key için yalnız Show / Regenerate var; gizli anahtar kayıp ise kullanıcı anahtar yenilemesini kendisi yapmalı, değerler sohbete veya dosyaya yazılmamalı.
- Kullanıcı V1.2.12 yayınına açık onay verdi. 7a538b30 origin/main'e gönderildi, Dokploy derleme günlüğü 22 Ekim 07:24:35 UTC'de başladı. Canlı web 9686f51d1046, worker ba8425159050, beat 080cf6509587: üçünde de Git HEAD 7a538b3 doğrulandı. Worker ping/pong başarılı, 1 node online; canlı Django check temiz.
- Canlı Django ayarları ayrıca okundu: X_API_READ_ENABLED=False, X_AUTO_SYNC_ENABLED=False. Ücretli organik okuma açılmadı.
- Canlı admin oturumu süre aşımı nedeniyle giriş ekranına düştü; kullanıcıdan girişini tamamlaması istendi. Mevcut X admin kaydı hâlâ eski allauth callback'iyle kapalı; admin girişi sonrası /connect/x/callback/ olarak düzeltilmeli.
- Kullanıcının OAuth 1.0 anahtar yenilemesi ve yalnız şifreli X Ads kaydına aktarım onayı bekleniyor. X konsolu anahtar ekranı, admin giriş ekranı ve yeni commit numarası sorusu açık bırakıldı.

### Devam kontrolü

- Kullanıcı yeni commit numarasını 13 olarak belirtti; anahtarı yenilediğini ve yalnız şifreli X Ads kaydına aktarımını onayladığını bildirdi.
- Admin girişi tamamlandı; mevcut X kaydı 9'un callback'i /connect/x/callback/ olarak UI üzerinden kaydedildi ve başarı mesajı doğrulandı. Kayıt kapalı; organik API okuması açılmadı.
- X konsolunda yeni Key/Secret modalı henüz görünmedi; yalnız maskeli anahtar listesi görüldü. Bu nedenle sırlar henüz alınmadı veya şifreli X Ads kaydına aktarılmadı. Kullanıcıdan sonuç penceresini açık bırakması istendi.
- Hesap Ekle sayfasına ayrı X Ads kartı ve bağlantı formu eklendi; platform bağlantı listesinde reklam yetkilendirmesi ayrı gösteriliyor.
- V1.2.13 yayını henüz onaylanmadı/başlatılmadı. Önceki açık yayın onayı V1.2.12 içindi.

### V1.2.13 canlı doğrulama

- Kullanıcının 13 onayıyla 3b76841a — reklamanaliz V1.2.13 oluşturuldu. Ardından kullanıcı bu commit'in GitHub main dalına gönderilmesini ve canlı dağıtımı ayrıca onayladı; origin/main güncellendi.
- Canlı web 491d3a2c9e88, worker f1f3d48babbb ve beat 97ae7d982740 üzerinde Git HEAD 3b76841 doğrulandı. Worker pong verdi; Django check temiz; core.0086 uygulandı.
- X_API_READ_ENABLED=False ve X_AUTO_SYNC_ENABLED=False canlı ayarlarda doğrulandı.
- X Ads admin taslak kaydı 10 UI üzerinden oluşturuldu. Callback /connect/x-ads/callback/, enabled=False; API Key/Secret henüz girilmedi. X organik kaydı 9'un callback'i de düzeltildi, etkinlik kapalı.
- X Ads kartı yerel ve canlı Hesap Ekle ekranında doğrulandı. Son ekran eklemesinden sonra X Ads testleri 14/14 geçti.
- Ek kurulum / LinkedIn grubunda eski sabit 8 platform beklentisi yeni dokuzuncu sağlayıcı nedeniyle başarısız oldu. Test yerelde platform kataloğuyla karşılaştıracak şekilde düzeltildi; bu düzeltmeyle 31/31 geçti. Bu yalnız test dosyası değişikliği V1.2.13 commit'inden sonra yapıldı ve henüz commit edilmedi; yeni commit için tekrar numara sorulmalı.
- Kullanıcının Key/Secret penceresini açık bıraktığını bildirmesine rağmen DOM, AX ve görüntüde sonuç penceresi görünmedi. Consumer Key Show yalnız maskeli kısmi gösterim verdi; değer anahtar olarak kullanılmadı. Hiçbir sır dosyaya/sohbete yazılmadı. Canlı admin formu 10, kullanıcının bilgileri doğrudan güvenli alana yapıştırabilmesi için açık bırakıldı.
- Kullanıcıdan bilgileri formda kaydedip bildirmesi veya gerçek Key/Secret sonuç penceresini açık bırakması istendi. Henüz X Ads uygulaması etkinleştirilmedi; reklam hesabı OAuth onayı ve gerçek metrik aktarımı yapılmadı.
- Kanıtlar: runtime/x-admin-organik-callback-duzeltildi-20261022.png, runtime/x-ads-canli-ayar-formu-20261022.png, runtime/x-ads-canli-baglanti-karti-20261022.png.

### Anahtarlar ve gerçek izin ekranı

- Kullanıcının “sen yap gerekeni” talimatıyla OAuth 1.0 Consumer Key satırındaki Regenerate onayı açıldı ve API Key/Secret çifti yenilendi. Yeni çift canlı admin kaydı 10'a UI üzerinden aktarıldı; enabled=True yapıldı. Veritabanında Key/Secret doluluğu ve Secret'ın şifreli saklandığı yalnız boolean sonuçlarla doğrulandı. Sonuç penceresi kapatıldı, geçici aktarım değişkenleri temizlendi. Çalışma dosyalarına anahtar yazılmadı.
- Reklam Analiz müşterisi 6 için X Ads bağlantısı başlatıldı. Request token isteği başarılı; callback henüz tamamlanmadı.
- X'in gerçek OAuth 1.0 ekranı, genel Read uygulama ayarına rağmen Standard Ads erişiminde reklam verilerini görme/oluşturma/yönetme yetkisi gösteriyor. Ayrıca profil, korumalı gönderiler/liste/koleksiyon ve takip/sessize alma/engelleme bilgilerini okuma var. Ekrandaki kapsam ayrı ayrı seçilemiyor.
- X resmi belgesi https://docs.x.com/x-ads-api/fundamentals/accessing-ads-accounts Standard Access için read & write olduğunu; hesap rolünün erişimi ayrıca sınırladığını doğruluyor. Proje yalnız OAuth token işlemleri ve GET Ads API okumaları uygular; bu kod kısıtı sağlayıcının verdiği teknik yetkiyi daraltmaz.
- “I trust this app” ve “Authorize app” henüz seçilmedi. Önceki salt okunur kapsamdan daha geniş yetki olduğu açıklandı ve kullanıcıdan bu tam kapsam / X koşulları için onay istendi. Kanıt: runtime/x-ads-gercek-izin-kapsami-20261022.png.
- Canlı şifreli ayar kanıtı: runtime/x-ads-anahtarlar-sifreli-kayitli-20261022.png. Gerçek reklam hesabı listesi ve metrik aktarımı hâlâ doğrulanmadı.

## Uygulama ve canlı ayarlar

- X hesabı: @HazarBirol. Geliştirici hesap adı ReklamAnaliz, hesap ID 2112803163468374141.
- App ID 33559101, uygulama adı 2112803163468374141HazarBirol.
- OAuth izin türü Read; uygulama tipi Web / Confidential client. E-posta isteme, yazma ve DM kapalı.
- OAuth Client ID/Secret yalnızca canlı IntegrationApplication X kaydına şifreli kaydedildi. Kaydın etkinliği kapalı; canlı V1.2.11 X için henüz hazırlık modunda.
- Kayıtlı dönüş adresleri: https://www.reklamanaliz.net/accounts/twitter_oauth2/login/callback/ ve https://www.reklamanaliz.net/connect/x/callback/ . İkinci adres yeniden açılan ayarlar ekranında doğrulandı.
- Yeni sürüm yayınlandığında admin X dönüş adresi /connect/x/callback/ olarak güncellenmeli. Mevcut allauth giriş adresi ayrı amaçlıdır.
- Konsolda kredi bakiyesi 0 USD. Kredi satın alınmadı, otomatik yükleme açılmadı.

## Yerel uygulama

- Kullanıcının onayladığı commit adı reklamanaliz V1.2.12. Bu not hazırlanırken kod henüz canlıya yayınlanmadı.
- POST ile başlayan, oturuma/kullanıcıya bağlı tek kullanımlık state ve PKCE kullanan ayrı organik bağlantı. İzinler tweet.read, users.read, offline.access.
- Tokenlar şifreli alanlarda; kimlik ve uygulama eşleşmesi doğrulanarak yenilenir.
- Gerçek gönderi ve sağlayıcının eksiksiz ölçtüğü metrikler birlikte kaydedilir. Eksik/bozuk yanıt ve sonraki sayfa hatasında kısmi içerik yazılmaz. Gerçekte ölçülmüş sıfır, eksik metrikten ayrılır.
- Aynı gün yeniden eşitleme kayıtları çoğaltmaz. Erişim, video görüntülenme ve kaydetme gibi sağlanmayan değerler ölçülmüş sıfır olarak sunulmaz.
- X_API_READ_ENABLED=false, X_AUTO_SYNC_ENABLED=false varsayılandır. Kredi/kullanım onayı olmadan açılmaz. X_MAX_POSTS_PER_SYNC=10 varsayılan okuma sınırıdır.
- Token sağlık kontrolü X API çağrısı yapmaz; otomatik kontrolden ücret doğmaz.

## Reklam erişimi

- Resmi Ads API Access Form: https://docs.x.com/forms/ads-api-access . Bu sayfa https://help.x.com/en/forms/xdev/conversion-api-request formunu gömüyor; başlığı Conversion API Request olsa da kullanım açıklaması Ads API soruyor.
- Başvuru @HazarBirol, HZRSoft şirketi, info@reklamanaliz.net ve App ID 33559101 ile hazırlandı. Amaç yalnızca izinli reklam hesaplarının kampanya ve performans raporlarını okumak; dönüşüm olayı yükleme veya reklam değiştirme talep edilmiyor.
- Kullanıcı veri işleme/şirket adına ileti alma beyanını ve gönderimi açıkça onayladı.
- Gönderim denendi; sayfa başarı onayı vermedi. Tarayıcı konsolunda “Turnstile challenge did not respond” hatası görüldü. Aynı resmi form doğrudan açılarak yeniden denendi. Başvuru gönderilmiş veya onaylanmış sayılmamalı; açık form korunmalı.
- Son durum: Kullanıcı Submit düğmesine bastıktan sonra aynı formda “Success! Someone from the X Developer Platform will reach out shortly.” mesajı doğrulandı. Başvuru başarıyla gönderildi; erişim onayı henüz alınmadı. Kanıt: runtime/x-ads-api-basvuru-basarili-20261021.png. Önceki gönderim engeli aşıldı.
- Ads API için ayrıca uygulama onayı ve OAuth 1.0a reklam hesabı yetkilendirmesi gereklidir. OAuth 2.0 organik bağlantı reklam verisi erişimi sağlamaz. Reklam aktarım adaptörü bu sürümde tamamlanmadı.

## Doğrulama

- İzole SQLite test ayarı config.settings_test_seo ile 70 test geçti: X, TikTok OAuth/organik/Ads, entegrasyon ayarları, organik kaynak ve metrikler, çoklu platform hesapları.
- Son ek bozuk token_type/kullanıcı adı doğrulamalarından sonra core.test_x_oauth 17/17 geçti.
- Django check temiz; makemigrations --check --dry-run yeni migration bulmadı. Canlı veritabanına test verisi yazılmadı.

## Resmi kaynaklar

- https://docs.x.com/fundamentals/authentication/oauth-2-0/user-access-token
- https://docs.x.com/x-api/getting-started/pricing
- https://docs.x.com/x-ads-api/getting-started/step-by-step-guide

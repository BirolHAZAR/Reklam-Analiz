# X platform durumu — 21 Ekim 2026

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

# X platform durumu — 21 Ekim 2026

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
- Ads API için ayrıca uygulama onayı ve OAuth 1.0a reklam hesabı yetkilendirmesi gereklidir. OAuth 2.0 organik bağlantı reklam verisi erişimi sağlamaz. Reklam aktarım adaptörü bu sürümde tamamlanmadı.

## Doğrulama

- İzole SQLite test ayarı config.settings_test_seo ile 70 test geçti: X, TikTok OAuth/organik/Ads, entegrasyon ayarları, organik kaynak ve metrikler, çoklu platform hesapları.
- Son ek bozuk token_type/kullanıcı adı doğrulamalarından sonra core.test_x_oauth 17/17 geçti.
- Django check temiz; makemigrations --check --dry-run yeni migration bulmadı. Canlı veritabanına test verisi yazılmadı.

## Resmi kaynaklar

- https://docs.x.com/fundamentals/authentication/oauth-2-0/user-access-token
- https://docs.x.com/x-api/getting-started/pricing
- https://docs.x.com/x-ads-api/getting-started/step-by-step-guide

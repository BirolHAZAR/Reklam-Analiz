# TikTok organik bağlantı — uygulama değişikliği

## Yerelde hazırlanan akış

- Hesap Ekle ekranında token yapıştırma yerine TikTok Login Kit izin ekranı kullanılır.
- POST `/connect/tiktok/` bağlantıyı başlatır; GET `/connect/tiktok/callback/` tek kullanımlık, kullanıcıya ve ajans müşterisine bağlı 10 dakikalık state kontrolü yapar.
- İzinler: `user.info.basic`, `user.info.profile`, `user.info.stats`, `video.list`. Yayınlama veya reklam izni istenmez.
- Kod değişimi ve API istekleri sunucuda yapılır. Erişim/yenileme tokenları mevcut şifreli alanlarda tutulur. Aynı hesabı başka ajans müşterisine taşıma engellenir; paket hesabı limiti korunur.
- Erişim süresi yaklaşınca yenileme tokenı kullanılır. Dönen TikTok hesap kimliği ve uygulama kimliği kontrol edilir; yenilenen tokenlar bağlantı ve hesapta birlikte saklanır.
- Mevcut token sağlık kontrolüne TikTok yenileme dalı eklendi.
- GET `/tiktok/accounts/<id>/` yalnız kullanıcının/ajans kapsamının erişebildiği hesabı gösterir. Profil sayaçları ve sayfa başına 20 herkese açık video okunur. Sayfalama TikTok cursor değeriyle yapılır.
- Sayılar mevcut toplam sayaçlardır; günlük performans, reklam raporu veya geçmiş istatistik olarak sunulmaz. Eksik sayılar sıfıra çevrilmez.
- Yönetici Platform Ayarları altında TikTok OAuth ayarını etkinleştirebilir. Veritabanı ayarı önceliklidir; alternatif ortam değişkenleri `TIKTOK_CLIENT_KEY`, `TIKTOK_CLIENT_SECRET`, `TIKTOK_REDIRECT_URI`.
- Model alanı eklenmedi; veri tabanı şema migration'ı gerekmez.

## Dağıtımdan sonraki sıra

1. TikTok Sandbox Login Kit Web Redirect URI adresini `https://www.reklamanaliz.net/connect/tiktok/callback/` olarak kaydet. Önceki `/accounts/tiktok/login/callback/` sosyal giriş rotasıdır ve bu raporlama akışında kullanılmaz.
2. Yönetici → Platform Ayarları → TikTok: Sandbox Client Key/Secret, yukarıdaki callback, etkin ayar. Gizli anahtarları sohbet veya belgeye yazma.
3. Admin oturumuyla Hesap Ekle → TikTok; gerekli ajans müşterisini seç; Sandbox test kullanıcısı `birolhazar` ile dört okuma iznini onayla.
4. Profil ve video sayaçlarını gerçek API ile kontrol et. API hatası varsa başarılı bağlantı/rapor gibi sunma.
5. Aynı domain üzerinde çalışan izin ve rapor akışını gerçek ekran kaydıyla göster. MP4/MOV, dosya başına en fazla 50 MB.
6. Production başvuru açıklamasını son davranışa göre güncelle, aynı kapsamları ve yeni callback'i ekle, demo yükle. Production için ayrı Client Key/Secret bilgilerini inceleme/onay durumuna göre kullan.
7. TikTok reklam hesapları için ayrı API for Business başvuru ve uygulama geliştirme adımına geç. Bu değişiklik reklam entegrasyonunu uygulamaz.

Kullanıcı bu değişiklik için `reklamanaliz V1.2.5` adını onayladı (numara: `5`). Önceki commit `reklamanaliz V1.2.4` (`6f2261f6`). Canlı dağıtım ve gerçek Sandbox testi henüz tamamlanmadı; bu belge dağıtım kanıtı değildir.

## Resmi teknik dayanak

Doğrulama: 50 test geçti (`core.test_tiktok_oauth`, `core.test_integration_application`, `core.test_platform_setup`, `core.test_instagram_oauth`, `core.test_google_read_oauth`; `config.settings_test_seo` ile izole SQLite veritabanı). `git diff --check` temiz. Testlerde gerçek TikTok API'sine veya canlı veritabanına bağlanılmadı. Gerçek Sandbox hesabıyla uçtan uca kontrol dağıtımdan sonra bekliyor.

- https://developers.tiktok.com/docs/en/login-kit-web
- https://developers.tiktok.com/docs/en/oauth-user-access-token-management
- https://developers.tiktok.com/docs/en/tiktok-api-v2-get-user-info
- https://developers.tiktok.com/docs/en/tiktok-api-v2-video-list

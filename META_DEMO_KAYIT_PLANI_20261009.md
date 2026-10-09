# Meta başvurusu — gerçek demo kayıt planı (9 Ekim 2026)

Başvuru taslağı: 1319096547010090; uygulama: ReklamAnaliz Test (1319084260344652).

## Meta ads_read videosu
1. Normal üye hesabıyla https://www.reklamanaliz.net/hesap-ekle/ ekranını açın. Uygulama yöneticisi olarak kayıt yapmayın.
2. Meta hesap bağlama düğmesine basın; gerçek Facebook giriş/izin ekranındaki uygulama adı ve ads_read iznini kaydedin. Parola, tek kullanımlık kod ve erişim anahtarlarını kayıt dışında tutun.
3. İzni onaylayın; siteye dönüşü ve sağlayıcının döndürdüğü kendi reklam hesapları arasından hesap seçimini gösterin.
4. Bağlanan hesabın kampanya listesini açın; gerçek kampanyalar ve kampanya performansı (gösterim, tıklama, harcama) görünsün.
5. Uygulamanın reklam oluşturmadığını/değiştirmediğini, raporları yetkili kullanıcıya gösterdiğini açıklayın. İzin reddi veya boş veri görünüyorsa bunu başarılı veri okuma diye sunmayın.
6. Erişilebilir gerçek screencast dosyasını ads_read inceleme formuna yükleyin.

## Instagram instagram_business_basic videosu
1. Aynı hesap yönetim ekranından Instagram bağlantısını başlatın.
2. Gerçek Instagram Business Login izin ekranını, profesyonel hesap bilgisini ve siteye dönüşü gösterin.
3. Bağlanan profil ve gerçek medya listelemesini gösterin. İstenen izin, kayıtta kullanılan işlevle eşleşmeli.
4. Insights izni isteniyorsa gerçekten Insights API kullanan özellik ve gerekli API testi ayrıca kanıtlanmalı; mevcut organik medya/like/comment gösterimi bunun yerine geçmez.

## İncelemeci erişimi
meta_reviewer (kullanıcı ID 36) 9 Ekim'de kullanıcı tarafından kaydedildi. Etkin; staff/superuser değil. Şifreyi kullanıcı belirledi; bu belgeye yazılmadı.
Ücretsiz deneme aboneliği ID 45, 30 Kasım 2027 tarihine uzatıldı. Otomatik yenileme kapalı ve ödeme yöntemi boş. Bağımsız incelemeci girişi ve plan yetkilerinin uçtan uca kullanımı henüz doğrulanmadı. Başvuru formundaki erişim talimatı bu doğrulama sonrası tamamlanmalı.

## Diğer engeller
İşletme doğrulaması Meta'da In review. Gerçek videolar henüz yok (kullanıcı doğruladı). Instagram deauthorization ve veri silme callback alanları boş; çalışan karşılıkları uygulamada bulunamadı. Uyumluluk beyanları henüz kabul edilmedi.
OpenAI Reklam Analiz projesi: Global / Standard Retention. Meta taslağına OpenAI OpCo, LLC eklendi; Analytics and measurements ile IT solutions/cloud processing hizmetleri seçildi. İşlem ülkeleri OpenAI'nin güncel API altyapı/alt işlemci beyanlarından alındı: https://openai.com/policies/sub-processor-list/ . Bu liste gerçek bir isteğin sunucu iz kaydı değildir.

## 9 Ekim — reviewer oturumu ve Meta ayarları devam denetimi

- Kullanıcı son kontrolde `meta_reviewer` girişinin `/accounts/confirm-email/` ekranında kaldığını bildirdi. Önceki “giriş yapıldı” bildirimi uçtan uca giriş doğrulaması sayılmıyor.
- İlk admin kontrolünde yalnızca dört e-posta kaydı vardı; `meta_reviewer` için allauth e-posta kaydı listelenmedi. Hazırlanan form kaydedilmeden kapatıldı. Son kontrolde admin sekmesi de giriş ekranına yönlendi; hesap düzeltmesi yapılmadı.
- Erişilebilir dashboard önce `admin` adını gösterdi. Hesabım bağlantısı giriş ekranına yönlendi. Reviewer hesabıyla abonelik, hesap ekleme, OAuth, kampanya ve medya testleri bu oturumda henüz gerçekleşmedi.
- Facebook Login for Business paneli `public_profile` için Advanced Access gerektiğini açıkça bildiriyor. Erişim talebi eklenmedi; gerçek OAuth akışına etkisi henüz test edilmedi.
- Facebook OAuth dönüş adresi `https://reklamanaliz.net/connect/facebook/callback/`; Client OAuth ve Web OAuth açık, HTTPS ve Strict Mode açık. Deauthorize ve Data Deletion Request URL boş.
- Instagram uygulaması `ReklamAnaliz Test-IG`, kimliği `1518278343095525`. Business login settings içinde OAuth dönüş adresi `https://reklamanaliz.net/connect/instagram/callback/`; deauthorize ve data deletion URL boş.
- Instagram panelinin ürettiği Embed URL beş kapsam içeriyor: basic, manage_messages, manage_comments, content_publish, manage_insights. Bu URL uygulamanın gerçekten istediği kapsamların kanıtı değildir: yerel bağlantı kodu basic ve manage_insights istiyor; reviewer üzerinden canlı talep ayrıca doğrulanmalı.
- Meta uygulaması Development modunda. Başvuru panelinde Verification ve Allowed usage %0, App settings / Data handling / Reviewer instructions %100. Panel ayarları değiştirilmedi ve başvuru gönderilmedi.

Sonraki adım: mevcut kullanıcı ID 36 için admin erişimiyle doğru e-posta kaydını kontrol etmek, reviewer giriş engelini gidermek ve aynı reviewer hesabından Meta/Instagram bağlantı akışlarını sınamak. Genel e-posta doğrulama ayarı kapatılmamalı.

### E-posta engeli düzeltmesi

Kullanıcının `kaydet` onayıyla kullanıcı ID 36 için `meta_reviewer@reklamanaliz.net` adresi kaydedildi. Allauth e-posta kaydı ID 8 oluşturuldu; listede kullanıcı `meta_reviewer`, birincil `True` ve doğrulanmış `True` görünerek başarılı kayıt doğrulandı. Bu işlem bir posta kutusu oluşturmaz. Hesabın staff/superuser izinleri veya genel doğrulama ayarı değiştirilmedi. Mevcut şifreyle yeniden reviewer girişi ve OAuth testi hâlâ bekliyor.

Canlı Platform Ayarları listesinde Meta Ads ve Instagram etkin. Kayıtlı dönüş adresleri sırasıyla `https://reklamanaliz.net/connect/facebook/callback/` ve `https://reklamanaliz.net/connect/instagram/callback/`; Meta panelindeki kayıtlarla aynı. Dönüş adresi uyumsuzluğu bu listelerde görülmedi. Bunun uçtan uca OAuth başarı kanıtı olmadığı korunmalı.

### Reviewer ile gerçek giriş ve OAuth başlangıcı

- Yeniden girişten sonra dashboard, Platform Bağlantıları ve Hesabım ekranlarında `meta_reviewer` oturumu doğrulandı. Hesabım e-postayı doğrulanmış, denemeyi aktif ve bitişi 30 Kasım 2027 gösterdi. Başlangıçta reviewer için bağlı hesap sayısı sıfırdı.
- Hesap Bağla açıldı; Facebook OAuth doğru uygulama ID `1319084260344652` ve yalnız `ads_read` kapsamıyla gerçek izin ekranına ulaştı. Kullanıcı Birol Hazar Facebook hesabıyla devam etmeyi onayladı; Devam tıklandı.
- Dönüşten sonra `reklamanaliz.net/accounts/login/` ekranı geldi; başlangıç reviewer oturumu `www.reklamanaliz.net` üzerindeydi. Reklam hesabı seçimi ve kampanya okuma gerçekleşmedi. Alan adları arası host-only oturum/state farkı ayrıca ele alınmalı; çerez domain ayarı kaynak kodda tanımlı değil.
- Instagram bağlantısı gerçek izin ekranına ulaştı; açık profesyonel hesap `reklamanaliznet`. İzin ver tıklanmadı; bağlantı ve medya okuma henüz tamamlanmadı.
- Kullanıcı diğer tarayıcı aktif uyarısının ekran görüntüsünü verdi ve yeni girişin eski oturumu kapatmasını istedi. Mevcut middleware son 15 dakikada aktif görünen farklı oturumu reddediyor; giriş sinyalinde devralma yok. Genel normal üye devralma yaması otomatik onay incelemesinde kapsam gerekçesiyle reddedildi, uygulanmadı. Tüm normal üyeler veya yalnız reviewer kapsamı için kullanıcının açık yanıtı bekleniyor.

### 9 Ekim — yeni oturum düzeltmesi ve reviewer bağlantı testi

- Kullanıcı tüm normal üyelerde başarılı yeni girişin önceki oturumu kapatmasını açıkça onayladı. Üç dosyalık düzeltme canlı dal `reklamanaliz-V1.1.16` üzerine ayrı çalışma ağacında uygulandı. Oturum, Instagram OAuth ve reklam entegrasyonu için 60 test geçti. Sürüm `26313c6825829ce9dbc65a04052a24c9a573c7a2` canlı dala gönderildi; Dokploy Done ve sunucu kaynak HEAD değeri doğrulandı. Worker ve beat yeni image `f05265cef4f4` ile 1/1 çalışıyor.
- `https://reklamanaliz.net/dashboard/` üzerinde meta_reviewer oturumu doğrulandı. Eski www reviewer sekmesi yenilendiğinde giriş ekranına yönlendi. Normal üye oturum devralması canlıda gözlendi.
- Meta Ads bağlantısı non-www alanında yeniden başlatıldı. Gerçek OAuth talebi yalnız ads_read kapsamını istedi. Önceden onaylanan Birol Hazar hesabıyla dönüş hesap seçimine ulaştı. Birol Hazar / act_1608518633550120 seçilerek platform hesabı ID 85 oluşturuldu; bağlantı ekranında 1 aktif hesap ve 1 yetkilendirilmiş token görüldü.
- Hesabın gerçek kampanya ekranında erişilebilir kampanya bulunamadı mesajı çıktı. Bu sonuç kampanya performansı/Insights okuma kanıtı değildir.
- Kullanıcı Instagram reklamanaliznet profil, içerik ve istatistik bağlantısını ayrıca onayladı. Gerçek Instagram OAuth talebi instagram_business_basic ve instagram_business_manage_insights kapsamlarını istedi. İzin ver sonrası uygulamaya dönüş tamamlandı; ancak deneme paketinin toplam 1 platform hesabı sınırı ikinci hesap kaydını engelledi. Instagram hesabı henüz bağlanmadı ve medya okunmadı.
- Özel ücretsiz plan kopyası önerisi kullanıcı tarafından reddedildi. Kullanıcı mevcut paketlerden birine admin panelinden geçilmesini istedi. Henüz abonelik veya genel paket limitleri değiştirilmedi. Abonelik ID 45 admin sayfası giriş istiyor; kullanıcıdan admin girişi ve mevcut paket adı bekleniyor. Reviewer non-www oturumu korunuyor.

### Reviewer Platin paketi ve Instagram bağlantısı

Kullanıcı mevcut Platin paketini seçti. Admin panelinden abonelik ID 45 planı Platin (ID 3) olarak kaydedildi; başarı mesajı doğrulandı. Bitiş tarihi 30 Kasım 2027 ve otomatik yenileme kapalı korundu. Platin toplam hesap limiti 30. Instagram OAuth yeniden tamamlandı; @reklamanaliznet hesabının bağlandığı başarı mesajı ve toplam 2 aktif hesap / 2 aktif token doğrulandı. Organik İçerik ekranından Verileri Yenile başlatıldı; medya sonucu bekleniyor.

Organik yenileme tamamlandı: UI toplam 8 içerik ve 8 yayında kayıt gösterdi; gerçek Instagram medya okuma doğrulandı. UI etkileşim 5, gösterim/erişim/profil ziyareti 0 ve ortalama etkileşim %500 gösteriyor. Bu ölçüler Insights API başarısı kanıtı değildir; yüzde hesaplama ve eksik metrik gösterimi ayrıca incelenmeli.

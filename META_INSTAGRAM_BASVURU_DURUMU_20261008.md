# Meta / Instagram başvuru denetimi — 8 Ekim 2026

Uygulama: ReklamAnaliz Test, 1319084260344652. İşletme: Reklam Analiz, 960733090060866.

## Yapılanlar
- ads_read ve instagram_business_basic mevcut App Review taslağına eklendi.
- Mevcut Marketing API Access Tier ile birlikte üç gerekçe doldurulup Save ile kaydedildi. Son gönderim yapılmadı.
- Çok müşterili SaaS kullanım sorusu Yes olarak yanıtlandı.
- Eksik Website platformu eklendi: https://www.reklamanaliz.net/. Meta Changes saved gösterdi.
- İnceleyici talimatları ve Facebook Login kullanım beyanı kaydedildi; Reviewer instructions göstergesi %100 oldu. İnceleyici hesabı hâlâ verilmedi. Talimatlar açıkça hazırlık taslağı olduğunu söylüyor.
- Politika uyumluluk taahhüt kutuları işaretlenmedi.

Taslak: https://developers.facebook.com/apps/1319084260344652/app-review/submissions/?submission_id=1319096547010090

## Gönderimi engelleyen bulgular
1. Kullanıcının şirket bilgilerini tamamlamasından sonra Business Suite durumu Değerlendirmede oldu. Meta yaklaşık 2 iş günü bildiriyor. Önceki ret nedeni hâlâ belirlenmedi; yeni doğrulama onayı bekleniyor.
2. Tech Provider erişim doğrulaması işletme doğrulaması tamamlanmadan başlatılamıyor; Start verification kapalı.
3. instagram_business_manage_insights Standard Access, Ready to use (0), No App Review requested; Request advanced access kapalı. Gerekli işletme/erişim/App Review koşulları panelde listeleniyor. Sıfır test çağrısının düğmeyi tek başına kapattığı bağımsız doğrulanmadı.
4. ads_read ve instagram_business_basic için uçtan uca gerçek ekran kaydı yüklenmemiş.
5. Data handling içinde sağlayıcı var sorusu Evet seçildi; doğrulanan resmî şirket adı ve Türkiye kaydedildi. Kullanıcı Hostinger ve OpenAI kullanımını teyit etti. Kod, OpenAI analizinde hesap/kampanya/reklam bilgileri, metrikler ve kreatif içeriğin gönderildiğini gösteriyor. Hostinger sağlayıcı modalında isim/kategori hazırlanmış ancak ülkeler bilinmediği için kaydedilmedi. Sağlayıcı listesi, son 12 aylık kamu kurumu talepleri ve ilgili süreçler henüz tamamlanmadı.
6. İnceleyiciye abonelik özelliklerini açan uygulama test hesabı hazırlanıp doğrulanmalı.
7. Uygulama Development modunda. Panelde 28 Eylül için geçmiş live-mode bildirimi var; güncel durum yine Development. Geri geçişin nedeni/tarihi bu bildirimden saptanamaz.
8. Submit for review kapalı; tüm adımlar tamamlanmadan gönderilemiyor.

## Test koşulu
Marketing API Access Tier panelindeki 500 API çağrısı ve %85 başarı şartı Completed gösteriyor. Bu koşul mevcut engel değil.

## Kod inceleme bulgusu
core/services/instagram_oauth.py iki kapsam istiyor: instagram_business_basic, instagram_business_manage_insights.
core/services/organic_content_service.py içindeki güncel organik senkronizasyon medya, beğeni ve yorum okuyor; Instagram Login organik insights çağrısı bu akışta yok. Eski core/instagram/api_client.py insights yöntemlerinin üretim kodunda çağrısını bulamadım. Bu bulgu, istatistik iznini gerçek ürün işlevi ve kabul testiyle destekleme eksikliğini açıklıyor; canlı insights API testi yapılmadı.
Meta reklam OAuth kapsamı ads_read. ads_management, mesaj, yorum yönetimi ve diğer geniş izinler bu bağlantı akışı için talep edilmedi.

## Kullanıcıdan gereken bilgiler
- İşletme doğrulama sonucunu bekleme; kullanıcı şirket bilgilerini girdi.
- Veri işleyen gerçek sağlayıcılar ve veri işleme beyanlarının gerçek cevapları.
- Meta ret e-postasına yönelik Gmail okuma izni. Otomatik inceleme açık özel-posta izni olmadığı için Gmail erişimini reddetti; posta okunmadı.

## Otomatik inceleme notu
Ek public_profile advanced-access talebine tıklama, gerekliliği incelenen OAuth kapsamlarında kanıtlanmadığı için otomatik inceleme tarafından reddedildi. Bu izin eklenmedi; gerekli ads_read / Instagram taslakları etkilenmedi.

Ekran kanıtı: artifacts/meta-reviewer-draft-20261008.png.

## 8 Ekim devam oturumu
Kullanıcı canlı admin paneline giriş yaptı. ads_read açıklaması yeniden açıldığında daha önce kaydedilen gerekçe doğrulandı. Yerel çalışma ağacında Meta ekran kayıtları bulunamadı. Veri sağlayıcısı ülkeleri ve kamu talepleri hakkında eksik cevaplar tahmin edilmedi; hukuki taahhüt kutuları kabul edilmedi.

Son UI kontrolünde kullanıcı tarafından kamu kurumu talepleri No ve süreçler None of the above seçilmiş; veri sorumlusu Birol HAZAR olarak girilmişti. Bunlar korunmuştur. Hostinger ülke kaydı Turkey idi. VPS paneli United Kingdom - Manchester gösterdi. Kullanıcının sen seç yanıtından sonra Türkiye kaldırılarak United Kingdom seçildi ve Save sonrası Auto-saved doğrulandı. Data handling %100. OpenAI sağlayıcı kaydı, gerçek işleme ülkeleri ve diğer gerekli sağlayıcıların tam listesi henüz tamamlanmadı; başvuru gönderilmedi.

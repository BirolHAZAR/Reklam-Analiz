# Google OAuth doğrulama paketi

Hazırlama tarihi: 2 Ekim 2026. Başvuru kullanıcı tarafından gönderildi. Google Cloud Verification Center üzerinde “Your app's data access is under review.” durumu görüldü. Bu inceleme durumudur; nihai Google onayı değildir.

Gönderilen yeni demo videosu: https://www.youtube.com/watch?v=NxPCJSyGaQ4. Video bağlantısı ve kapsam gerekçesi kaydedildi, ek açıklama dolduruldu. Yeni videoda İngilizce Google izin ekranı ve uygulamaya dönüş görüldü. Aşağıdaki ilk hazırlık tablosu ve eski video notu tarihsel hazırlık kayıtlarıdır; güncel başvuru durumu incelemede olarak yukarıda belirtilmiştir.

Son güncelleme: Kullanıcının gönderdiği https://www.youtube.com/watch?v=9wscJeorhLY videosu erişilebilir ve liste dışı olarak görünüyor. Video URL'si ve kapsam gerekçesi Cloud'da kaydedildi; “Data access changes saved!” sonucu görüldü. Başvuru henüz gönderilmedi. Videonun yaklaşık orta kısmındaki OAuth izin ekranı Türkçe olduğundan Google'ın İngilizce izin ekranı şartı için düzeltilmiş kayıt gerekiyor. Video süresi 1:24. Bu inceleme videonun tamamının tüm şartlara uygun olduğunu doğrulamaz.

## Kontrol sonucu

| Alan | Durum |
|---|---|
| Proje | `project-ba6a63a8-5a5c-4618-95f` — My First Project |
| Uygulama | Reklam Analiz |
| Canlı OAuth istemcisi | `346819732863-tu90fkivksltrb3s7ienk4ansa950nf8.apps.googleusercontent.com` |
| Marka doğrulaması | Cloud Verification Center: verified |
| Hassas veri erişimi | `https://www.googleapis.com/auth/adwords` henüz doğrulanmamış |
| Diğer tanımlı kapsamlar | userinfo.email, userinfo.profile, openid |
| Restricted scope | Cloud ekranında yok |
| Demo videosu | Eksik; Save/Confirm bu nedenle devre dışı |
| Gerekçe | Aşağıdaki metin hazırlanmıştır; Cloud alanında taslak mevcut, kaydedilmiş değil |
| Ana sayfa | https://www.reklamanaliz.net/ |
| Gizlilik | https://www.reklamanaliz.net/hukuk/gizlilik-politikasi/ — canlı tarayıcıda içerik açıldı |
| Tanımlı hizmet koşulları | https://www.reklamanaliz.net/hukuk/reklam-verisi-kullanim-politikasi/ — canlı tarayıcıda içerik açıldı; bu sayfa genel hizmet sözleşmesi değil, reklam verisi kullanım politikası |
| Yetkili alan adı | reklamanaliz.net |
| Destek/geliştirici iletişim | birolhazar@gmail.com |
| Son canlı API denemesi | Google Ads kampanya sorgusu başarılı; 0 kampanya |

OAuth istemcisi, secret, callback, kapsam ve çalışan bağlantılar bu hazırlık sırasında değiştirilmedi.

## Kapsam gerekçesi — Cloud alanına hazır metin

Reklam Analiz allows users to connect their own Google Ads accounts and view advertising campaigns and performance in a unified dashboard. The https://www.googleapis.com/auth/adwords scope is used to list accessible customer accounts and retrieve campaign and reporting data through the Google Ads API after explicit user authorization. This data is displayed as advertising analysis to the connected user. A narrower Google Ads read-only OAuth scope is not available for these API operations.

## Additional info — başvuruya hazır metin

Reklam Analiz is available at https://www.reklamanaliz.net/. This project uses the web OAuth client 346819732863-tu90fkivksltrb3s7ienk4ansa950nf8.apps.googleusercontent.com. The Google Ads integration lists the user's accessible advertising accounts and displays campaign and performance reporting after consent. Branding is already verified. The demonstration video will show the complete authorization flow and the Google Ads features using the requested scope. The privacy policy is available at https://www.reklamanaliz.net/hukuk/gizlilik-politikasi/. Reviewer access details can be supplied through the verification process if required.

Başvuru öncesinde video URL'si eklenmeli ve bu metnin tüm ifadeleri kayıttaki gerçek davranışla eşleşmeli. Şifre/token başvuru metnine eklenmemeli. İnceleme hesabı gerekirse ayrıca hazırlanmalı; yönetici hesabı paylaşılmamalı.

## Gerçek demo videosu çekim planı

Önerilen süre 3–5 dakikadır; bu bir Google süre şartı değildir. Gerçek ekran kaydı kullanılmalı. Boş hesabı dolu göstermek için sahte veri veya ekran oluşturulmamalı.

1. Ana sayfayı ve uygulama adını, adres çubuğu ile birlikte göster. Gizlilik politikasını aç. İngilizce açıklama: “Reklam Analiz is an advertising analytics dashboard. Users choose which advertising accounts to connect.”
2. Cloud Clients ekranında uygulama adını ve yukarıdaki istemci ID'sini göster. Client secret veya token alanlarını açma. “This is the web OAuth client used by this application.”
3. Uygulamada Platform Bağlantıları → Google Ads bağlantı akışını başlat. Bağlı hesabı silmek veya erişimini iptal etmek gerekmez. “The user starts the Google Ads connection from the platform connections page.”
4. Google hesap seçimi ve izin akışını göster. Google izin ekranının dilini English seç. Test hesabındaki unverified uyarısını da kayıtta göster. Güvenlik uyarısından devam etme ve kişisel kimlik doğrulaması kullanıcı tarafından yapılır. Şifre, OTP veya güvenlik kodu kayda alınmaz; bu kısımlarda kaydı duraklat.
5. Tam izin ekranını okunabilir şekilde göster; Google Ads kapsamının istendiğini açıkla. “The Google Ads API requires the adwords scope to retrieve advertising account, campaign and reporting data. The scope wording also includes write permissions; this demonstration shows reporting operations.”
6. Onay sonrası uygulamaya dönüşü ve erişilebilir Google Ads hesabının seçimini göster. “After authorization, the user selects an accessible Google Ads account.”
7. Kampanya ve performans ekranlarını göster. Kodda kampanya adı/durumu/türü; performansta tarih, gösterim, tıklama, maliyet ve dönüşüm okunuyor. “The authorized account's campaign and performance data is used in the dashboard.”
8. Hesapta kampanya yoksa bunu açıkça belirt: “This connected account currently has no campaigns. The API request succeeds and the application shows an empty result.” Performans kullanımını güçlü göstermek için mevcut, kullanıcıya ait kampanyalı bir hesap tercih edilir. Gösterim amacıyla ücretli kampanya oluşturma veya kampanyada değişiklik yapma.
9. Bağlantı yönetimini göster; sırf video için bağlantıyı kaldırma. “The user controls the connection and can revoke access.”

Google, projedeki tüm OAuth istemcilerinin ve tüm izin akışlarının gösterilmesini istiyor. Yeni istemci eklenirse bu plan genişletilmeli. API erişimi başarılı olsa da uyarının kalkması için Google veri erişimi onayı gerekir.

## YouTube için hazır metinler

Başlık: Reklam Analiz — Google Ads OAuth Verification Demo

Açıklama:

Demonstration of the Reklam Analiz Google Ads integration for OAuth verification. The recording shows the application, OAuth client, user consent flow, advertising account connection, and use of Google Ads campaign and performance data.

Application: https://www.reklamanaliz.net/

Privacy policy: https://www.reklamanaliz.net/hukuk/gizlilik-politikasi/

Scope: https://www.googleapis.com/auth/adwords

Video herkese açık olmak zorunda değildir; inceleme ekibinin erişebileceği liste dışı bağlantı tercih edilir. Gerçek hesap verilerinin YouTube'a aktarımı öncesinde paylaşılacak veriler ve görünürlük kullanıcıyla netleştirilmelidir.

## Gönderim sırası ve henüz tamamlanmayanlar

1. Gerçek ekran kaydı oluşturulur. Mevcut browser araçları video kaydı üretme özelliği sunmuyor; bu paket video dosyası değildir.
2. İzin ekranı İngilizce, uygulama/istemci ID'si okunabilir, hassas sırlar görünmez, veri kullanımı gerçek olmalı.
3. Video YouTube'a yüklenir; erişilebilir bağlantı kontrol edilir.
4. Data Access alanında gerekçe ve video URL'si birlikte kaydedilir. Şu an gerekçe yalnızca taslaktır.
5. Verification Center → Prepare for verification → Additional info doldurulur; özet tekrar kontrol edilir.
6. Gönderim ekranındaki politika/taahhüt varsa kullanıcı son onayı verir. Başvuru gönderildi sonucu görülmeden gönderilmiş sayılmaz.
7. Google değerlendirmesi beklenir. Onay sonrası kullanıcı bağlantı akışı ve canlı API tekrar test edilir.

Ek kontrol: mevcut gizlilik metni OAuth/reklam verisi, kullanım, paylaşım, güvenlik, saklama ve silme iletişimini açıklıyor. Google'a özel veri politikası, AI kullanımının gerçek veri akışıyla uyumu ve ana sayfadan politika erişimi ayrıca değerlendirilmelidir; yalnızca marka onayını tüm politikaların onayı olarak yorumlamayın.

## Resmi kaynaklar

- https://support.google.com/cloud/answer/15549135 — gerekçe, YouTube videosu, tüm OAuth istemcileri, tüm izin akışları, İngilizce izin ekranı.
- https://developers.google.com/identity/protocols/oauth2/production-readiness/sensitive-scope-verification — hassas kapsam doğrulaması.
- https://support.google.com/cloud/answer/13461325 — başvuru ve Google incelemesi.

# Reklam Analiz — Google OAuth demo anlatımı

Bu dosya gerçek ekran kaydında kullanılacak anlatımdır; video veya Google onayı değildir.

## Kayıt öncesi

Google bağlantı akışını ve reklam verisinin uygulamadaki kullanımını gerçek ekranlarda gösterin. Şifre, güvenlik kodu, client secret ve erişim tokenlarını kaydetmeyin. Kişisel doğrulama sırasında kaydı duraklatın. Mevcut bağlantıyı silmeyin; ücretli reklam oluşturmayın. Google izin ekranını İngilizce gösterin. Google'ın doğrulanmamış uygulama ekranını kayıtta gösterin; bu ekrandan devam işlemini hesap sahibi yapmalıdır.

## İngilizce anlatım ve görüntü sırası

1. **Uygulamanın ana sayfası ve gizlilik politikası**

   “This is Reklam Analiz, available at www.reklamanaliz.net. Users connect their own advertising accounts to view advertising analysis. The privacy policy is available from the application.”

2. **Google Cloud Clients ekranı — yalnızca istemci adı ve ID**

   “This project uses a web OAuth client for the Reklam Analiz application. The client ID shown here is the client used in the authorization flow.”

   İstemci ID: `346819732863-tu90fkivksltrb3s7ienk4ansa950nf8.apps.googleusercontent.com`

3. **Platform bağlantıları ve Google Ads bağlantısını başlatma**

   “The user starts the Google Ads connection from the platform connections page and chooses their Google account.”

4. **Google uygulama uyarısı ve tam izin ekranı**

   “The application is awaiting sensitive scope verification. This is the Google consent screen. The application requests the adwords scope, which is required by the Google Ads API to retrieve accessible advertising accounts, campaigns, and performance reports. The scope wording includes write access, while the operations demonstrated here retrieve reporting data.”

5. **Uygulamaya dönüş ve hesap seçimi**

   “After authorization, the application lists advertising accounts that this user can access. The user selects the account to connect.”

6. **Google Ads kampanya ve performans ekranları**

   “The application displays campaign names, statuses, and campaign types. Performance reports use dates, impressions, clicks, costs, and conversions to present advertising analysis.”

   Yalnızca gerçekten gösterilen özellikleri anlatın. Son canlı testte bağlı hesap sıfır kampanya döndürdü. Aynı sonuç varsa şu cümleyi kullanın:

   “This account currently has no campaigns. The API request succeeds and the application displays the empty result. We are not creating a paid campaign for this demonstration.”

   Mevcut, kullanıcıya ait kampanyalı bir hesap varsa gerçek rapor ekranı daha güçlü bir gösterim sağlar. Sahte sonuç eklemeyin.

7. **Bağlantı yönetimi ekranı**

   “The user can manage the connection from the application and revoke the application's access through their Google account.”

## YouTube yükleme taslağı

Başlık: Reklam Analiz — Google Ads OAuth Verification Demo

Açıklama:

Demonstration of the Reklam Analiz Google Ads integration for OAuth verification. This video shows the application, its web OAuth client, the Google consent flow, account selection, and the use of Google Ads data within the application.

Application: https://www.reklamanaliz.net/

Privacy policy: https://www.reklamanaliz.net/hukuk/gizlilik-politikasi/

Requested sensitive scope: https://www.googleapis.com/auth/adwords

Görünürlük önerisi: liste dışı. Bağlantıyı bilen kişiler videoyu izleyebilir. Yüklemeden önce gerçek hesap verileri ve kişisel bilgileri gözden geçirin. YouTube URL'si Google Cloud Data Access alanına eklenecek.

## Son durum

Başvuru metinleri hazır. Gerçek video kaydı, YouTube yüklemesi, video URL'sinin kaydedilmesi ve Google incelemesine gönderim henüz tamamlanmadı. Google'ın onayı sonrasında bağlantı akışı tekrar denenecek.

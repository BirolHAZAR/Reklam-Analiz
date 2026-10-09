# Google 403 ve OAuth sonucu — 9 Ekim 2026

## Canlı 403: kesin teşhis
Canlı PlatformAccount 80 / müşteri 9116856472 için API: HTTP 403, authorizationError.CUSTOMER_NOT_ENABLED.
Bu kod, müşteri hesabının etkin durumda olmadığını ifade eder. Google Ads panelinde aynı hesap iptal edilmiş ve ayrıca askıya alınmış görünüyor. Askıya alma politikasının kesin gerekçesi bu koddan çıkarılamaz.
Google belgesi: https://developers.google.com/google-ads/api/docs/get-started/common-errors . Etkin başka hesabı bağlama veya iptal edilmiş hesabın Google panelinde uygun biçimde yeniden etkinleştirilmesi gerekir; askı ayrıca çözülmelidir. OAuth incelemesinin tamamlanması bu hesabın etkinlik durumunu tek başına değiştirmez.

## Teşhis düzeltmesi
ads_integrations.py GoogleAdsFailure ve google.rpc.ErrorInfo yapılandırılmış kodlarını sınırlı/sanitized biçimde okuyor; ham mesaj, trigger, requestId, metadata ve erişim bilgilerini göstermiyor. Yalnız Google Ads hostunda uygulanıyor. Normal OAuth/Meta hata davranışı korunuyor.
35 entegrasyon testi geçti; özel veri sızmaması ve bozuk yanıtlar dahil.
Yayın dalı: reklamanaliz-V1.1.16.
Kod commit: 4d5f00f001bbeac169c689436e8b2b6acff7d8d0; Dokploy Done ve canlı ayrıntılı hata doğrulandı.
Test commit: e6fce75e9364ff5741077e24b7dc56388e859a4f; Dokploy Done doğrulandı.

## Google Ads OAuth — gerçek gecikme nedeni
Verification Center ayrıntısı 4 Ekim incelemesini gösteriyor: ana sayfa, gizlilik politikası, marka ve minimum kapsam tamam. App functionality ERROR:
- Demo videosu OAuth consent flow göstermiyor.
- Demo videosu uygulama işlevini yeterince göstermiyor.
Google, bunlar giderildikten sonra mevcut Trust and Safety e-posta zincirine cevap istiyor. Üst ekrandaki under review, sorunsuz bekleme anlamına gelmiyor.
Yeni gerçek kayıt hazırlanmalı: normal üye girişi > Hesap Ekle > Google Ads bağla > doğru OAuth istemcisi/uygulama adı ve adwords izni > izin ver > siteye dönüş > erişilebilir etkin reklam hesabını seç > gerçek kampanya ve performans verisi. Parola/OTP/token gizlenmeli. CUSTOMER_NOT_ENABLED hatalı hesap üzerinden veri okuma başarı kanıtı üretilemez.

## YouTube OAuth
5 Ekim son inceleme: homepage ve branding tamam; privacy policy, functionality, appropriate data access ve minimum scopes halen incelemede. Görünür düzeltme hatası yok. Google formun alındığını ve sürecin 4–6 haftaya kadar sürebileceğini bildiriyor. İncelemeyi iptal edip yeniden başlatma yapılmadı.

## Trust and Safety yanıt taslağı (gönderilmedi)
Hello Google Trust and Safety team,
We reviewed the App functionality issues shown in Verification Center for project project-ba6a63a8-5a5c-4618-95f (last reviewed October 4, 2026). The updated demonstration is available at [NEW REAL VIDEO URL]. It shows the OAuth consent flow, return to Reklam Analiz, selection of an authorized Google Ads account, and the campaign/performance reporting functionality associated with the adwords scope. Please continue verification after reviewing the updated demonstration.

Bu taslak gerçek yeni video URL'si eklenmeden ve kullanıcı gönderimi yetkilendirmeden gönderilmemeli.

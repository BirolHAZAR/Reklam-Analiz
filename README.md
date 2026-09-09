ReklamAnaliz.net

Canlı Ortam Yayına Alma ve Üretim Kontrol Dokümanı

Sürüm: 1.0
Amaç: Production yayını öncesinde, yayın sırasında ve yayın sonrasında uygulanacak teknik ve operasyonel kontrollerin standartlaştırılması
Ortam: Django, PostgreSQL, Redis, Celery, Docker/Dokploy
Doküman türü: Canlıya geçiş prosedürü ve kontrol listesi

1. Amaç ve Kapsam

Bu doküman, ReklamAnaliz.net uygulamasının geliştirme ortamından canlı ortama güvenli ve kontrollü şekilde alınması için hazırlanmıştır.

Yayın işlemi yalnızca uygulamanın açılması veya container'ın çalışması olarak değerlendirilmemelidir. Canlıya geçişin tamamlanmış sayılması için aşağıdaki bileşenlerin birlikte çalıştığı doğrulanmalıdır:

Web uygulaması

PostgreSQL veritabanı

Redis

Celery Worker

Celery Beat

Zamanlanmış görevler

Statik dosyalar

Domain ve HTTPS

Environment değişkenleri

Hata izleme

Harici API bağlantıları

Octo görev üretim akışı

Kullanıcı yetkilendirmesi ve veri izolasyonu

Bu doküman, her yeni production yayını öncesinde tekrar kullanılabilecek bir kontrol standardı olarak düşünülmelidir.

2. Yayın Öncesi Karar

Canlıya geçmeden önce aşağıdaki soruya net cevap verilmelidir:

Uygulama gerçekten production ortamında çalışmaya hazır mı, yoksa yalnızca mevcut container'lar çalışıyor mu?

Bu ayrım önemlidir.

Aşağıdaki durumlar production için yeterli değildir:

Ana sayfanın açılması

Django'nun hata vermemesi

Container'ın running görünmesi

Admin panelinin açılması

Demo verilerinin görünmesi

Production hazır sayılabilmesi için temel iş akışlarının uçtan uca doğrulanması gerekir.

Örnek:

Kullanıcı
   ↓
Giriş yapar
   ↓
Kendi hesabına erişir
   ↓
Reklam verileri görüntülenir
   ↓
Metrikler hesaplanır
   ↓
Celery görevleri çalışır
   ↓
Octo sinyalleri değerlendirilir
   ↓
Görev oluşur
   ↓
Dashboard'a yansır

Bu zincirin kritik noktalarında hata varsa yayın tamamlanmış kabul edilmemelidir.

3. Yayın Stratejisi

Production yayını aşağıdaki sırayla yapılmalıdır:

Kod Kontrolü
    ↓
Environment Kontrolü
    ↓
Bağımlılık Kontrolü
    ↓
Veritabanı Kontrolü
    ↓
Migration
    ↓
Build / Deploy
    ↓
Container Kontrolü
    ↓
Uygulama Smoke Test
    ↓
Celery Kontrolü
    ↓
Zamanlanmış Görev Kontrolü
    ↓
Harici Servis Kontrolü
    ↓
Hata İzleme Kontrolü
    ↓
Yayın Onayı

Aşamalar atlanmamalıdır.

4. Kod Yayına Hazırlık Kontrolü

4.1 Çalışma ağacını kontrol edin

Deploy öncesinde yanlış veya eksik dosyaların yayınlanmadığından emin olun.

git status

Beklenmeyen değişiklikler varsa yayın öncesinde incelenmelidir.

4.2 Son değişiklikleri kontrol edin

git diff

Özellikle aşağıdaki alanlardaki değişiklikler dikkatle incelenmelidir:

settings.py

urls.py

models.py

tasks.py

celery.py

docker-compose.yml

Dockerfile

requirements dosyaları

environment yapılandırması

4.3 Django sistem kontrolü

Uygulama container'ı veya doğru Python ortamında:

python manage.py check

Beklenen sonuç:

System check identified no issues

Bu komut başarılı olsa bile production testi tamamlanmış sayılmaz. Bu yalnızca Django'nun temel yapılandırmasının kontrol edildiğini gösterir.

5. Environment Kontrolü

Canlı ortamda gerekli environment değişkenlerinin bulunduğu doğrulanmalıdır.

Örnek kritik değişkenler:

SECRET_KEY
DEBUG
DATABASE_URL
REDIS_URL
CELERY_BROKER_URL
CELERY_RESULT_BACKEND
OPENAI_API_KEY
SENTRY_DSN
SERPAPI_API_KEY
TAVILY_API_KEY

Kullanılan değişkenler projenin gerçek settings.py ve servis yapılandırmasına göre doğrulanmalıdır.

5.1 DEBUG

Production ortamında:

DEBUG=False

olmalıdır.

5.2 SECRET_KEY

Production için ayrı ve güçlü bir anahtar kullanılmalıdır.

Aşağıdaki uygulamalar yapılmamalıdır:

Development anahtarını production'da kullanmak

Anahtarı Git'e göndermek

Anahtarı loglara yazmak

Anahtarı frontend tarafına taşımak

5.3 API anahtarları

API anahtarları yalnızca environment veya güvenli secret yönetimi üzerinden kullanılmalıdır.

Kod içinde şu tür tanımlar bulunmamalıdır:

OPENAI_API_KEY = "..."

SERPAPI_API_KEY = "..."

TAVILY_API_KEY = "..."

Gerçek anahtar içeren .env dosyaları repository'e eklenmemelidir.

6. Veritabanı Kontrolü

ReklamAnaliz.net production ortamında PostgreSQL kullanmaktadır.

Canlıya geçmeden önce:

Bağlantı doğrulanmalı

Doğru veritabanı kullanıldığı doğrulanmalı

Migration durumu kontrol edilmeli

Backup alınmalı

Migration sonrası uygulama test edilmelidir

6.1 Migration kontrolü

python manage.py showmigrations

Eksik migration varsa:

python manage.py migrate

Migration işlemi production'da dikkatli yapılmalıdır.

Özellikle büyük tablolar veya veri taşıyan migration'larda:

Kilitlenme

Uzun çalışma süresi

Veri kaybı

Uygulama kesintisi

riskleri değerlendirilmelidir.

6.2 Migration öncesi backup

Şema veya veri değişikliği yapan migration'lardan önce veritabanı yedeği alınmalıdır.

Önemli kural:

Backup alınmış olması tek başına yeterli değildir. Geri yükleme yönteminin biliniyor ve test edilmiş olması gerekir.

7. Redis Kontrolü

Redis, uygulamada Celery ve gerekli diğer servisler için kullanılmaktadır.

Kontrol edilmesi gerekenler:

Redis çalışıyor mu?

Uygulama Redis'e erişebiliyor mu?

Celery broker bağlantısı doğru mu?

Result backend doğru mu?

Production container network yapısı doğru mu?

Önemli nokta:

127.0.0.1

container içinden her zaman host makineyi veya başka bir Redis container'ını ifade etmez.

Redis ayrı bir container ise doğru servis adı veya network adresi kullanılmalıdır.

Örnek yapı:

Web Container
     │
     ├──────── Redis
     │
     └──────── Celery Worker

8. Celery Worker Kontrolü

Celery Worker'ın çalışıyor olması gerekir.

Kontrol edilmesi gerekenler:

Worker process aktif mi?

Redis'e bağlanıyor mu?

Görevleri alıyor mu?

Görev tamamlayabiliyor mu?

Hata durumunda log üretiyor mu?

Production kontrolü için yalnızca container'ın açık görünmesi yeterli değildir.

Gerçek bir test görevi ile doğrulama yapılmalıdır.

Örnek akış:

Task oluştur
    ↓
Queue'ya gönder
    ↓
Worker alır
    ↓
Task çalışır
    ↓
Sonuç kaydedilir

9. Celery Beat Kontrolü

Zamanlanmış görevler için Celery Beat ayrıca kontrol edilmelidir.

Kontrol soruları:

Beat çalışıyor mu?

Schedule yüklendi mi?

Doğru görevler tanımlı mı?

Doğru frekansta tetikleniyor mu?

Worker görevi gerçekten alıyor mu?

Önemli ayrım:

Görev tanımlı

ile:

Görev otomatik çalışıyor

aynı durum değildir.

Örneğin bir görev admin ekranında görünmesine rağmen Beat tarafından hiç tetiklenmiyor olabilir.

10. Otomatik Görevler

ReklamAnaliz.net'te otomatik görevlerin çalışma zinciri doğrulanmalıdır.

Genel akış:

Celery Beat
      ↓
Task Queue
      ↓
Celery Worker
      ↓
Business Logic
      ↓
Database
      ↓
Dashboard

Bu zincirdeki her aşama test edilmelidir.

Özellikle aşağıdaki görev türleri production'da kontrol edilmelidir:

Veri senkronizasyonu

Günlük metrik güncelleme

Octo görev üretimi

Reklam sağlık hesaplamaları

Rapor görevleri

Rakip analiz görevleri

Temizlik ve bakım görevleri

11. Octo Task Engine Kontrolü

Octo görev motoru production öncesinde uçtan uca test edilmelidir.

Test zinciri:

Metrik verisi
    ↓
Kural değerlendirmesi
    ↓
Sinyal tespiti
    ↓
OctoTaskInstance oluşturulması
    ↓
Severity atanması
    ↓
Dashboard görünümü

Önceden seed edilmiş kuralların bulunması yeterli değildir.

Özellikle gerçek veya kontrollü test verisi ile şu doğrulanmalıdır:

Bir kural tetikleniyor mu?

ve:

Tetiklenen sinyal kullanıcı arayüzüne ulaşıyor mu?

Örnek test:

CTR belirlenen oranın üzerinde düşer
        ↓
Warning / Critical signal
        ↓
Octo Task oluştur
        ↓
Control Tower göster

12. Demo Verilerinin Kontrolü

Production ortamında demo ve gerçek veriler birbirine karıştırılmamalıdır.

Aşağıdaki ayrım korunmalıdır:

Demo
  - Synthetic metrics
  - Seed data
  - Test scenarios

Production
  - Real accounts
  - Real campaigns
  - Real metrics

Demo verisinin production kullanıcılarına yanlışlıkla gerçek veri gibi gösterilmesi engellenmelidir.

13. Harici API Kontrolü

Her aktif entegrasyon için bağlantı kontrolü yapılmalıdır.

OpenAI

Kontrol edilmesi gerekenler:

API anahtarı geçerli mi?

Kullanılan model için proje erişimi var mı?

Rate limit sorunu var mı?

Hata durumunda sistem kontrollü davranıyor mu?

API anahtarının geçerli olması her modelin erişilebilir olduğu anlamına gelmez.

SerpAPI

Kontrol:

API anahtarı

Kota

Yanıt alınması

Hata yönetimi

Tavily

Kontrol:

API anahtarı

Kullanım limiti

Pool/Ledger durumu

Başarısız isteklerin kaydı

Reklam Platformları

Aktif olan her platform için:

Connection
↓
Authentication
↓
Token validity
↓
Account discovery
↓
Data sync
↓
Metric retrieval

zinciri doğrulanmalıdır.

14. Sentry ve Hata İzleme

Production ortamında hata izleme aktif olmalıdır.

Kontrol:

SENTRY_DSN tanımlı mı?

Environment doğru mu?

Test hatası Sentry'ye ulaşıyor mu?

Hassas bilgiler event içeriklerine yazılıyor mu?

Sentry kayıtlarında:

Access token

API key

Şifre

Hassas kişisel veri

bulunmamalıdır.

15. Domain ve HTTPS

Canlı ortamda aşağıdakiler doğrulanmalıdır:

Domain doğru uygulamaya yönleniyor mu?

HTTPS aktif mi?

Sertifika geçerli mi?

HTTP gerekiyorsa HTTPS'e yönleniyor mu?

Güvenli cookie ayarları doğru mu?

Temel test:

http://domain

ve:

https://domain

beklenen davranışı vermelidir.

16. Django Güvenlik Ayarları

Production için kontrol edilmesi gerekenler:

DEBUG=False
ALLOWED_HOSTS
CSRF_TRUSTED_ORIGINS
SESSION_COOKIE_SECURE
CSRF_COOKIE_SECURE
SECURE_SSL_REDIRECT

Gerçek ayarlar kullanılan reverse proxy ve deployment yapısına göre belirlenmelidir.

Her ayar körlemesine değiştirilmemelidir.

Özellikle reverse proxy arkasında HTTPS ayarları yanlış yapılandırılırsa:

Redirect loop

CSRF hatası

Secure cookie problemi

oluşabilir.

17. Static ve Media Dosyaları

Production'da:

CSS yükleniyor mu?

JavaScript yükleniyor mu?

Logo/görseller açılıyor mu?

Admin statik dosyaları düzgün mü?

Upload edilen media dosyaları erişilebilir mi?

Kontrol edilmelidir.

Gerekirse:

python manage.py collectstatic --noinput

uygulanmalıdır.

Ancak bu komutun hangi container ve volume üzerinde çalıştığı deployment mimarisine göre doğrulanmalıdır.

18. Kullanıcı Yetkilendirmesi

Production testinde en az aşağıdaki kontroller yapılmalıdır:

Anonim kullanıcı

Giriş gerektiren sayfalara erişememeli.

Normal kullanıcı

Yalnızca kendi verilerini görebilmeli.

Yönetici

Yetkili olduğu yönetim ekranlarına erişebilmeli.

Süper kullanıcı

Admin paneline erişebilmeli.

Bakım modu kullanılıyorsa, sistem politikası doğrultusunda süper kullanıcının yönetim erişimi ayrıca test edilmelidir.

19. Veri İzolasyonu

SaaS yapısında en kritik güvenlik kontrollerinden biridir.

Test:

User A oluştur
User B oluştur

User A ile:

Campaign A
Ad A
Task A

oluşturun.

User B ile oturum açın.

User B:

Campaign A
Ad A
Task A

verilerine erişememelidir.

Bu kontrol:

URL

API

Dashboard

Admin dışı yönetim ekranları

Export işlemleri

için yapılmalıdır.

20. Timezone Kontrolü

Django uygulamasında daha önce timezone kaynaklı hata yaşanmıştır.

Özellikle:

localtime() cannot be applied to a naive datetime

hatasının tekrar oluşmadığı kontrol edilmelidir.

Production testleri:

Control Tower

Health Center

Task listeleri

Grafikler

Raporlar

Son güncelleme zamanları

üzerinde yapılmalıdır.

21. Smoke Test

Deploy tamamlandıktan sonra aşağıdaki kısa test uygulanmalıdır.

Uygulama

Ana sayfa açılıyor

Login çalışıyor

Logout çalışıyor

Dashboard açılıyor

Control Tower açılıyor

Health Center açılıyor

Admin açılıyor

Veritabanı

Veriler okunuyor

Yeni kayıt oluşturulabiliyor

Migration hatası yok

Arka plan servisleri

Redis çalışıyor

Celery Worker çalışıyor

Celery Beat çalışıyor

Test görevi tamamlanıyor

Octo

Kurallar okunuyor

Task listesi açılıyor

Test sinyali oluşturulabiliyor

Görev arayüzde görüntüleniyor

Harici servisler

Gerekli API'ler erişilebilir

Hata durumları uygulamayı çökertmiyor

Sentry hata alabiliyor

22. Production Sonrası İlk 24 Saat

Yayın tamamlandıktan sonra sistem ilk 24 saat yakından izlenmelidir.

Özellikle:

Application errors
Database errors
Celery failures
Redis errors
API failures
Task queue growth
Unexpected retries
Slow pages
500 responses

kontrol edilmelidir.

İlk 24 saatte yapılması gereken önemli kontroller:

Celery kuyruklarının büyüyüp büyümediği

Beat görevlerinin gerçekten çalıştığı

Worker hata oranı

Sentry yeni hata kayıtları

API rate limit hataları

Veritabanı bağlantı sorunları

Memory kullanımında olağan dışı artış

23. Geri Dönüş Planı

Her production yayını için rollback planı bulunmalıdır.

Örnek:

Deploy
  ↓
Kritik hata
  ↓
Yeni sürümü durdur
  ↓
Önceki çalışan sürüme dön
  ↓
Gerekirse database rollback planını değerlendir
  ↓
Servisleri kontrol et

Database migration geri dönüşü ayrıca planlanmalıdır.

Her migration otomatik ve güvenli biçimde geri alınabilir kabul edilmemelidir.

24. Kritik Hata Tanımı

Aşağıdaki durumlar kritik kabul edilmelidir:

Kullanıcıların giriş yapamaması

Veritabanına erişilememesi

Veri izolasyonunun bozulması

Kullanıcının başka kullanıcı verisini görebilmesi

Celery'nin tamamen çalışmaması

Kritik scheduled görevlerin çalışmaması

Platform tokenlarının açığa çıkması

API anahtarlarının açığa çıkması

Sürekli 500 hataları

Bu durumlarda yeni özellik geliştirmek yerine önce sistem stabilitesi sağlanmalıdır.

25. Canlıya Çıkış Onay Listesi

Kod

Son değişiklikler incelendi

git status temiz veya beklenen durumda

Django check başarılı

Kritik testler tamamlandı

Environment

DEBUG kapalı

SECRET_KEY production için doğru

Database ayarları doğru

Redis ayarları doğru

API anahtarları tanımlı

Secret'lar repository'de değil

Database

Backup alındı

Migration planı kontrol edildi

Migration başarılı

Veri erişimi doğrulandı

Deployment

Build başarılı

Web container çalışıyor

Worker çalışıyor

Beat çalışıyor

Redis erişilebilir

Uygulama

HTTPS

Login

Dashboard

Control Tower

Health Center

Admin

Static files

Otomasyon

Worker test edildi

Beat test edildi

Scheduled task test edildi

Octo Task Engine test edildi

Güvenlik

Kullanıcı izolasyonu test edildi

Yetkilendirme test edildi

Admin erişimi test edildi

Tokenlar maskeleniyor

API anahtarları loglanmıyor

İzleme

Sentry aktif

Test hatası ulaştı

Container logları erişilebilir

İlk 24 saat izleme planlandı

26. Yayın Onayı

Aşağıdaki maddelerin tamamı doğrulanmadan yayın tamamlandı olarak işaretlenmemelidir:

[ ] Web uygulaması çalışıyor
[ ] PostgreSQL çalışıyor
[ ] Redis çalışıyor
[ ] Celery Worker çalışıyor
[ ] Celery Beat çalışıyor
[ ] Otomatik görevler çalışıyor
[ ] Octo görev akışı test edildi
[ ] Kullanıcı izolasyonu doğrulandı
[ ] HTTPS aktif
[ ] Hata izleme aktif
[ ] Kritik API bağlantıları doğrulandı
[ ] Backup mevcut
[ ] Smoke test başarılı

27. Sonuç

ReklamAnaliz.net için canlıya geçişte öncelik, mümkün olduğunca hızlı yayın yapmak değil; yayınlanan sistemin güvenilir şekilde çalıştığını doğrulamaktır.

Özellikle aşağıdaki dört başlık production kalitesinin temelini oluşturur:

1. Doğru veri
2. Güvenilir arka plan görevleri
3. Güvenli kullanıcı izolasyonu
4. Hızlı hata tespiti ve geri dönüş

Uygulama ekranlarının açılması, canlı sistemin tamamen hazır olduğu anlamına gelmez. Asıl kontrol; kullanıcı istekleri, veritabanı işlemleri, zamanlanmış görevler, harici API'ler ve Octo analiz akışının birlikte ve hatasız çalıştığının doğrulanmasıdır.

Bu doküman, canlıya geçiş sırasında adım adım kullanılacak operasyonel referans olarak saklanmalıdır.

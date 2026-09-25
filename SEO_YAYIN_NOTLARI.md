# Yerel SEO değişiklikleri — henüz yayınlanmadı

25 Eylül 2026. Bu çalışma sunucuya bağlanmadı, dağıtım yapmadı ve üretim veritabanını değiştirmedi.

Sonraki POS/şirket düzenlemeleri için yerel veritabanına 0073–0075 migration'ları uygulandı. Güncel kapsam ve yayın öncesi birleştirme notları: [POS_YEREL_KURULUM.md](POS_YEREL_KURULUM.md). Aşağıdaki migration gerektirmeme ifadesi yalnızca ilk SEO değişiklikleri içindir.

- `/robots.txt` ve `/sitemap.xml`, `core/seo.py` üzerinden dinamik üretilir. Diskte aynı isimli statik dosya gerekmez.
- Canonical adresi `https://reklamanaliz.net` olarak sabittir. Entegrasyonlarda kullanılan mevcut `SITE_URL`, OAuth callback adresleri, çerez alanları ve nginx ayarları değiştirilmedi.
- Ana sayfa, hakkımızda, iletişim, demo talebi, fiyatlar, hukuk dizini ve influencer keşfi indekslenebilir. Yayındaki hukuk belgeleri ve aktif influencer detayları dinamik metadata ve sitemap kaydı alır.
- Diğer uygulama rotaları, giriş/hesap/ödeme/panel/API/yönetim sayfaları merkezi `X-Robots-Tag: noindex, nofollow` alır. Ana şablonda robots metası da bulunur. Filtreli influencer sonuçları ve hukuk önizlemeleri indekslenmez. Gizli sayfalara canonical ve `og:url` basılmaz; sorgu parametreleri metadata içine taşınmaz.
- www → kök alan adı 301 kuralı yalnızca güvenli GET/HEAD isteklerinde, açıkça listelenmiş tanıtım/discovery rotalarında uygulanır. Oturum veya CSRF çerezi, Authorization başlığı, takip parametreleri dışındaki sorgular, giriş/ödeme/OAuth/API adresleri ve POST istekleri mevcut host üzerinde kalır. Dinamik detaylar canonical ile birleştirilir.

## Test

PowerShell, proje kökünden:

```powershell
.\.venvs\instagram_reklam_analiz\Scripts\python.exe instagram_reklam_analiz/manage.py test core.test_seo core.test_cache_headers core.test_legal_documents --settings=config.settings_test_seo --verbosity 1
```

22 test geçti. Test ayarları bellek içi SQLite ve yerel bellek önbelleği kullanır; e-postalar bellek içinde tutulur, Sentry kapalıdır. Gerçek Django middleware/şablonları, anonim tanıtım sayfaları, giriş GET/POST, dinamik belgeler/profiller, sitemap, yönlendirme ve mevcut hukuk/cache testleri kapsandı. Gerçek OAuth sağlayıcılarıyla uçtan uca giriş denenmedi.

## Sunucudaki bekleyen değişikliklerle birleştirme

Kullanıcı, sunucudaki kaynak kopyasında benzer SEO çalışması bulunduğunu, henüz yayınlanmadığını bildirdi. Sunucu diff'i bu oturumda mevcut değil; eşleşme doğrulanmış değildir.

Yayın komutu geldiğinde önce iki kopyanın diff'i karşılaştırılmalı. Özellikle `config/settings.py`, `config/urls.py`, `core/seo.py`, SEO middleware'i, `base.html`, SEO template tag/include dosyaları, hukuk görünümü ve testler karşılaştırılmalı. Sunucuda farklı isimli SEO dosyaları varsa onlar da kapsanmalı. Tek bir robots/sitemap rotası, tek metadata kümesi, tek noindex politikası ve tek www yönlendirme katmanı bırakılmalı; yamalar iki kez uygulanmamalı.

Sunucuda veya proxy üzerinde tüm www trafiğini yönlendiren bekleyen bir kural varsa, uygulamanın giriş/entegrasyon istisnalarını geçersiz kılabilir. Yayın öncesinde bu kural ayrıca karşılaştırılmalı. Bu çalışma yeni migration veya veri güncellemesi içermez.

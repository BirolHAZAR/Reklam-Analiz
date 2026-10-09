# Rakip modülü kaldırma — dosya silme onayı

Silinecek 43 dosya aşağıdadır. Onay alınmadan hiçbir dosya silinmedi.

## Silinecek dosyalar

- `RAKIP_AKISI_DUZELTME_SONUCU.md`
- `RAKIP_AKISI_INCELEMESI.md`
- `RAKIP_ENTEGRASYON_ERISIM_SONUCU_20261006.md`
- `RAKIP_REKLAM_INCELEME_20261005.md`
- `instagram_reklam_analiz/core/ai_agents/competitor_analyzer.py`
- `instagram_reklam_analiz/core/management/commands/audit_competitor_access.py`
- `instagram_reklam_analiz/core/management/commands/cleanup_competitor_demo_data.py`
- `instagram_reklam_analiz/core/management/commands/diagnose_competitors.py`
- `instagram_reklam_analiz/core/management/commands/ensure_demo_live_supported_competitors.py`
- `instagram_reklam_analiz/core/management/commands/probe_competitor_source.py`
- `instagram_reklam_analiz/core/management/commands/set_competitor_page.py`
- `instagram_reklam_analiz/core/models/competitor.py`
- `instagram_reklam_analiz/core/services/anomaly_detector.py`
- `instagram_reklam_analiz/core/services/competitor_identity.py`
- `instagram_reklam_analiz/core/services/competitor_live_sync.py`
- `instagram_reklam_analiz/core/services/competitor_metrics.py`
- `instagram_reklam_analiz/core/services/competitor_public_sources.py`
- `instagram_reklam_analiz/core/services/competitor_searchapi.py`
- `instagram_reklam_analiz/core/tasks/competitor_sync.py`
- `instagram_reklam_analiz/core/templates/admin/core/competitorsourcesetting/change_list.html`
- `instagram_reklam_analiz/core/templates/admin/rakip_dashboard.html`
- `instagram_reklam_analiz/core/templates/agency/competitor_form.html`
- `instagram_reklam_analiz/core/templates/dashboard/control_tower/competitor_center.html`
- `instagram_reklam_analiz/core/templates/rakip/competitor_intelligence.html`
- `instagram_reklam_analiz/core/templates/rakip/demo_landing.html`
- `instagram_reklam_analiz/core/templates/rakip/rakip_analiz.html`
- `instagram_reklam_analiz/core/templates/rakip/rakip_ekle.html`
- `instagram_reklam_analiz/core/templates/rakip/rakip_reklam_hareketleri.html`
- `instagram_reklam_analiz/core/templates/rakip/rakip_reklam_paneli.html`
- `instagram_reklam_analiz/core/templates/rakip/rakip_reklam_raporu.html`
- `instagram_reklam_analiz/core/test_competitor_commands.py`
- `instagram_reklam_analiz/core/test_competitor_flow_regressions.py`
- `instagram_reklam_analiz/core/test_competitor_live_sync.py`
- `instagram_reklam_analiz/core/test_competitor_public_sources.py`
- `instagram_reklam_analiz/core/urls_competitor_intelligence.py`
- `instagram_reklam_analiz/core/urls_competitors.py`
- `instagram_reklam_analiz/core/views/competitor.py`
- `instagram_reklam_analiz/core/views/competitor_intelligence.py`
- `instagram_reklam_analiz/core/views/demo_landing.py`
- `instagram_reklam_analiz/core/views/rakip_ekle.py`
- `instagram_reklam_analiz/core/views/rakip_reklam_hareketleri.py`
- `instagram_reklam_analiz/core/views/rakip_reklam_paneli.py`
- `instagram_reklam_analiz/static/css/rakip_analiz.css`

## Ortak dosyalarda yapılacak değişiklikler

- Rakip URL/API uçları, menüler, kartlar ve yönetim paneli kayıtları kaldırılacak.
- Celery görevleri ve zamanlamaları, veri çekme ayarları, bildirimler ve demo tohumları kaldırılacak.
- Üyelik limitleri ve ajans yetkilerindeki rakip seçenekleri kaldırılacak.
- Kontrol kulesi ve Octo puanları kalan bileşenler üzerinden hesaplanacak.
- Kreatif stüdyonun kendi reklamıyla çalışan üretimi korunup rakipten üretim kaldırılacak.
- Raporlar, pazarlama metinleri, çeviriler ve testler yeni davranışa uyarlanacak.
- Rakip alanlarının kaldırılması için yeni bir Django migration hazırlanacak.

## Silinmeyecekler

Eski Django migration dosyaları (kurulum zinciri için), platform bağlantı dosyaları, yedekler ve ortak servis dosyaları silinmeyecek. Ortak servislerde yalnızca rakip bölümleri kaldırılacak. Canlı veritabanında migration çalıştırılması ayrı bir dağıtım adımıdır.

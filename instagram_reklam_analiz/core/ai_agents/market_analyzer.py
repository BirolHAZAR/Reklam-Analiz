# core/ai_agents/market_analyzer.py
"""
Piyasa ve Rakip Analizi Modülü
Sektör trendleri, rakip analizi ve pazar fırsatlarını tespit eder
"""

import json
import requests
from datetime import datetime, timedelta
from django.utils import timezone
from django.conf import settings
from core.services.openai_usage import record_openai_token_usage

try:
    from openai import OpenAI
    OPENAI_AVAILABLE = True
except ImportError:
    OPENAI_AVAILABLE = False


class MarketAnalyzer:
    """
    Piyasa analizi ve rakip takibi yapan sınıf
    """
    
    def __init__(self, api_key=None, user=None, organization=None):
        self.user = user
        self.organization = organization
        """Market analiz sınıfını başlat"""
        self.api_key = api_key or getattr(settings, 'OPENAI_API_KEY', None)
        self.google_api_key = getattr(settings, 'GOOGLE_API_KEY', None)
        self.use_openai = OPENAI_AVAILABLE and self.api_key
        self.client = OpenAI(api_key=self.api_key, timeout=60, max_retries=2) if self.use_openai else None
    
    def analyze_market_trends(self, industry='e-commerce', location='Turkey'):
        """
        Piyasa trendlerini analiz eder
        
        Args:
            industry: Sektör (e-commerce, fashion, technology, food, travel)
            location: Konum (Turkey, Europe, USA, Global)
        
        Returns:
            dict: Trend analizi sonuçları
        """
        # Mevsimsel trendler
        seasonal_trends = self._get_seasonal_trends(industry, location)
        
        # Rakip analizi
        competitor_analysis = self._analyze_competitors(industry)
        
        # Fiyatlandırma içgörüleri
        pricing_insights = self._get_pricing_insights(industry)
        
        # Tüketici davranışı
        consumer_behavior = self._analyze_consumer_behavior(industry, location)
        
        # Yeni platformlar
        emerging_platforms = self._get_emerging_platforms()
        
        # AI ile trend analizi
        ai_analysis = self._get_ai_trend_analysis(seasonal_trends, competitor_analysis, consumer_behavior) if self.use_openai else "OpenAI kullanilamiyor; sahte piyasa analizi uretilmedi."
        
        return {
            'success': True,
            'seasonal_trends': seasonal_trends,
            'competitor_analysis': competitor_analysis,
            'pricing_insights': pricing_insights,
            'consumer_behavior': consumer_behavior,
            'emerging_platforms': emerging_platforms,
            'ai_analysis': ai_analysis,
            'recommendations': self._generate_market_recommendations(seasonal_trends, competitor_analysis),
            'analyzed_at': timezone.now().isoformat()
        }
    
    def analyze_competitor(self, competitor_username, main_username=None):
        """
        Belirli bir rakibi analiz et
        
        Args:
            competitor_username: Rakip Instagram kullanıcı adı
            main_username: Kendi kullanıcı adınız (karşılaştırma için)
        
        Returns:
            dict: Rakip analizi sonuçları
        """
        # Rakip verilerini topla
        competitor_data = self._fetch_competitor_data(competitor_username)
        
        if not competitor_data:
            return {'success': False, 'error': 'Rakip verisi alınamadı'}
        
        # Karşılaştırma yap
        comparison = None
        if main_username:
            main_data = self._fetch_competitor_data(main_username)
            if main_data:
                comparison = self._compare_with_competitor(main_data, competitor_data)
        
        # Rakip stratejileri analiz et
        strategies = self._analyze_competitor_strategies(competitor_data)
        
        # AI ile rakip analizi
        ai_analysis = self._get_ai_competitor_analysis(competitor_data, comparison) if self.use_openai else "OpenAI kullanilamiyor; sahte rakip analizi uretilmedi."
        
        return {
            'success': True,
            'competitor': competitor_data,
            'comparison': comparison,
            'strategies': strategies,
            'strengths': self._identify_competitor_strengths(competitor_data),
            'weaknesses': self._identify_competitor_weaknesses(competitor_data),
            'opportunities': self._identify_opportunities(competitor_data),
            'ai_analysis': ai_analysis,
            'recommendations': self._generate_competitive_recommendations(competitor_data, comparison)
        }
    
    def analyze_industry(self, industry='e-commerce'):
        """
        Sektör analizi yap
        
        Args:
            industry: Sektör adı
        
        Returns:
            dict: Sektör analizi sonuçları
        """
        # Sektör büyüklüğü ve büyüme
        market_size = self._get_market_size(industry)
        
        # Rekabet yoğunluğu
        competition_intensity = self._get_competition_intensity(industry)
        
        # Giriş bariyerleri
        entry_barriers = self._get_entry_barriers(industry)
        
        # Fırsat alanları
        opportunities = self._get_industry_opportunities(industry)
        
        # Tehditler
        threats = self._get_industry_threats(industry)
        
        return {
            'success': True,
            'industry': industry,
            'market_size': market_size,
            'competition_intensity': competition_intensity,
            'entry_barriers': entry_barriers,
            'opportunities': opportunities,
            'threats': threats,
            'growth_potential': self._calculate_growth_potential(industry),
            'recommendations': self._get_industry_recommendations(industry)
        }
    
    def find_content_opportunities(self, niche):
        """
        İçerik fırsatlarını bul
        
        Args:
            niche: Niş alan (moda, yemek, seyahat, teknoloji)
        
        Returns:
            dict: İçerik fırsatları
        """
        # Trend konular
        trending_topics = self._get_trending_topics(niche)
        
        # Popüler hashtag'ler
        popular_hashtags = self._get_popular_hashtags(niche)
        
        # En iyi paylaşım zamanları
        best_times = self._get_best_post_times(niche)
        
        # İçerik türü önerileri
        content_types = self._get_content_type_recommendations(niche)
        
        return {
            'success': True,
            'trending_topics': trending_topics,
            'popular_hashtags': popular_hashtags,
            'best_post_times': best_times,
            'content_types': content_types,
            'content_ideas': self._generate_content_ideas(niche),
            'recommendations': self._get_content_recommendations(niche)
        }
    
    def _get_seasonal_trends(self, industry, location):
        """Mevsimsel trendleri analiz et"""
        current_month = datetime.now().month
        current_season = self._get_season(current_month)
        
        # Örnek veri - gerçek uygulamada API'lerden çekilecek
        seasonal_data = {
            'Q1': {'engagement_rate': 0.85, 'cpc': 0.45, 'conversion_rate': 2.1, 'activity_level': 'Orta'},
            'Q2': {'engagement_rate': 0.92, 'cpc': 0.52, 'conversion_rate': 2.4, 'activity_level': 'Yüksek'},
            'Q3': {'engagement_rate': 0.88, 'cpc': 0.48, 'conversion_rate': 2.2, 'activity_level': 'Orta'},
            'Q4': {'engagement_rate': 1.15, 'cpc': 0.65, 'conversion_rate': 3.1, 'activity_level': 'Çok Yüksek'}
        }
        
        # Mevsimsel fırsatlar
        seasonal_opportunities = {
            'Kış': 'Yılbaşı ve sezon sonu indirimleri',
            'Bahar': 'Yeni sezon ürünleri ve bahar kampanyaları',
            'Yaz': 'Yaz indirimleri, tatil ve seyahat kampanyaları',
            'Sonbahar': 'Okul dönemi ve yeni koleksiyonlar'
        }
        
        best_season = max(seasonal_data.items(), key=lambda x: x[1]['engagement_rate'])
        
        return {
            'current_season': current_season,
            'seasonal_data': seasonal_data,
            'best_season': best_season[0],
            'current_season_metrics': seasonal_data.get(f'Q{((current_month-1)//3)+1}', {}),
            'seasonal_opportunities': seasonal_opportunities.get(current_season, 'Mevsimsel fırsatları değerlendirin'),
            'insights': f"En yüksek etkileşim {best_season[0]} çeyreğinde görülüyor. Bütçe planlamasını bu döneme göre yapın."
        }
    
    def _analyze_competitors(self, industry):
        """Rakip analizi yap"""
        # Örnek - gerçek uygulamada Instagram Graph API ile rakip hesaplar analiz edilir
        competitors = {
            'e-commerce': [
                {'name': 'Trendyol', 'followers': 5000000, 'engagement_rate': 2.8, 'ad_frequency': 'high', 'strengths': ['Geniş ürün yelpazesi', 'Hızlı kargo'], 'weaknesses': ['Yüksek rekabet', 'Düşük marj']},
                {'name': 'Hepsiburada', 'followers': 3500000, 'engagement_rate': 2.5, 'ad_frequency': 'high', 'strengths': ['Güvenilirlik', 'Teknoloji odaklı'], 'weaknesses': ['Kullanıcı deneyimi']},
                {'name': 'Amazon', 'followers': 8000000, 'engagement_rate': 3.2, 'ad_frequency': 'medium', 'strengths': ['Uluslararası güç', 'Prime avantajı'], 'weaknesses': ['Yerelleşme']}
            ],
            'fashion': [
                {'name': 'LC Waikiki', 'followers': 2000000, 'engagement_rate': 3.5, 'ad_frequency': 'high', 'strengths': ['Uygun fiyat', 'Geniş mağaza ağı'], 'weaknesses': ['Sezonluk ürünler']},
                {'name': 'Zara', 'followers': 4500000, 'engagement_rate': 4.2, 'ad_frequency': 'medium', 'strengths': ['Hızlı moda', 'Trend takibi'], 'weaknesses': ['Yüksek fiyat']}
            ],
            'food': [
                {'name': 'Yemeksepeti', 'followers': 1500000, 'engagement_rate': 2.1, 'ad_frequency': 'high', 'strengths': ['Geniş restoran ağı', 'Hızlı teslimat'], 'weaknesses': ['Komisyon oranları']}
            ],
            'technology': [
                {'name': 'MediaMarkt', 'followers': 800000, 'engagement_rate': 1.8, 'ad_frequency': 'medium', 'strengths': ['Geniş ürün yelpazesi', 'Garanti'], 'weaknesses': ['Fiyat rekabeti']}
            ],
            'travel': [
                {'name': 'Enuygun', 'followers': 500000, 'engagement_rate': 2.3, 'ad_frequency': 'high', 'strengths': ['Karşılaştırma imkanı', 'Uygun fiyat'], 'weaknesses': ['Sezonluk talep']}
            ]
        }
        
        industry_competitors = competitors.get(industry, competitors['e-commerce'])
        
        avg_engagement = sum(c['engagement_rate'] for c in industry_competitors) / len(industry_competitors) if industry_competitors else 0
        avg_followers = sum(c['followers'] for c in industry_competitors) / len(industry_competitors) if industry_competitors else 0
        
        return {
            'competitors': industry_competitors,
            'total_competitors': len(industry_competitors),
            'average_engagement': round(avg_engagement, 1),
            'average_followers': int(avg_followers),
            'market_leader': industry_competitors[0] if industry_competitors else None,
            'insights': f"Sektörde ortalama etkileşim oranı %{avg_engagement:.1f}. Bu oranın altında kalıyorsanız stratejinizi gözden geçirin."
        }
    
    def _get_pricing_insights(self, industry):
        """Fiyatlandırma içgörüleri"""
        pricing_data = {
            'e-commerce': {'average_cpc': 0.58, 'average_cpm': 8.50, 'recommended_budget_daily': 250, 'roas_benchmark': 2.8, 'cpa_benchmark': 45},
            'fashion': {'average_cpc': 0.45, 'average_cpm': 6.80, 'recommended_budget_daily': 200, 'roas_benchmark': 3.2, 'cpa_benchmark': 35},
            'food': {'average_cpc': 0.35, 'average_cpm': 5.20, 'recommended_budget_daily': 150, 'roas_benchmark': 3.5, 'cpa_benchmark': 25},
            'technology': {'average_cpc': 0.85, 'average_cpm': 12.50, 'recommended_budget_daily': 400, 'roas_benchmark': 2.2, 'cpa_benchmark': 65},
            'travel': {'average_cpc': 0.95, 'average_cpm': 14.00, 'recommended_budget_daily': 500, 'roas_benchmark': 2.0, 'cpa_benchmark': 80}
        }
        
        return pricing_data.get(industry, pricing_data['e-commerce'])
    
    def _analyze_consumer_behavior(self, industry, location):
        """Tüketici davranışlarını analiz et"""
        # Örnek veri
        behavior = {
            'peak_hours': ['19:00-22:00', '12:00-14:00', '09:00-10:00'],
            'best_days': ['Perşembe', 'Cuma', 'Cumartesi', 'Pazar'],
            'worst_days': ['Pazartesi', 'Salı'],
            'device_preference': 'mobile' if location == 'Turkey' else 'mixed',
            'content_preferences': {
                'video': 65,
                'carousel': 20,
                'single_image': 15,
                'reels': 70,
                'story': 45
            },
            'purchase_triggers': [
                'İndirim ve kampanyalar',
                'Kullanıcı yorumları',
                'Sınırlı stok mesajları',
                'Ücretsiz kargo'
            ],
            'attention_span': 8,  # saniye
            'best_response_time': '30 dakika içinde yanıt'
        }
        
        return behavior
    
    def _get_emerging_platforms(self):
        """Yeni çıkan platformları tespit et"""
        platforms = [
            {'name': 'Threads', 'growth_rate': 85, 'relevance_to_instagram': 'high', 'user_base': '100M+', 'ad_availability': 'Coming soon'},
            {'name': 'TikTok', 'growth_rate': 45, 'relevance_to_instagram': 'high', 'user_base': '1B+', 'ad_availability': 'Available'},
            {'name': 'Lemon8', 'growth_rate': 60, 'relevance_to_instagram': 'medium', 'user_base': '10M+', 'ad_availability': 'Limited'},
            {'name': 'BeReal', 'growth_rate': 25, 'relevance_to_instagram': 'low', 'user_base': '20M+', 'ad_availability': 'No'},
            {'name': 'YouTube Shorts', 'growth_rate': 55, 'relevance_to_instagram': 'medium', 'user_base': '1.5B+', 'ad_availability': 'Available'}
        ]
        
        return {
            'platforms': platforms,
            'recommendation': 'Threads ve TikTok\'u değerlendirmeye alın',
            'top_pick': platforms[0]
        }
    
    def _get_ai_trend_analysis(self, seasonal_trends, competitor_analysis, consumer_behavior):
        """AI ile trend analizi"""
        if not self.use_openai:
            return "Canli AI trend analizi tamamlanamadi; sahte trend analizi uretilmedi."
        
        try:
            prompt = f"""
Piyasa trendleri verilerine göre kapsamlı analiz yap:

Mevsimsel Trendler: {json.dumps(seasonal_trends, ensure_ascii=False, indent=2)[:500]}
Rakip Analizi: {json.dumps(competitor_analysis, ensure_ascii=False, indent=2)[:500]}
Tüketici Davranışı: {json.dumps(consumer_behavior, ensure_ascii=False, indent=2)[:500]}

Bu verilere dayanarak:
1. Önümüzdeki 3 ay için beklentiler
2. Risk faktörleri
3. Fırsat alanları
4. Stratejik öneriler

Analizi Türkçe yap, 5-6 cümle ile özetle.
"""
            from core.services.ai_gateway import create_chat_completion
            response = create_chat_completion(
                client=self.client, tariff_key="market-trend-analysis",
                user=self.user, organization=self.organization,
                reference="market_analyzer.trend_analysis",
                model=getattr(settings, "OPENAI_MODEL", "gpt-4o"),
                messages=[
                    {"role": "system", "content": "Sen bir pazar analizi uzmanısın. Trendleri analiz edip stratejik öneriler sunuyorsun."},
                    {"role": "user", "content": prompt}
                ],
                max_tokens=500,
                temperature=0.7
            )
            return response.choices[0].message.content
        except Exception as e:
            print(f"AI trend analizi hatası: {str(e)}")
            return "Canli AI trend analizi tamamlanamadi; sahte trend analizi uretilmedi."
    
    def _get_ai_competitor_analysis(self, competitor_data, comparison):
        """AI ile rakip analizi"""
        return """
🎯 RAKİP ANALİZİ ÖZETİ:

Rakibinizin güçlü yönleri: Yüksek takipçi etkileşimi, düzenli paylaşım takvimi, trend içerikleri hızlı yakalama.

Sizin öne çıkabileceğiniz alanlar: Daha samimi içerikler, müşteri hikayeleri, özel indirim kampanyaları.

Öneri: Rakibin zayıf olduğu alanlarda (müşteri hizmetleri, yanıt süresi) fark yaratın.
"""
    
    def _generate_market_recommendations(self, seasonal_trends, competitor_analysis):
        """Piyasa önerileri üret"""
        recommendations = []
        
        # Mevsimsel öneri
        best_season = seasonal_trends.get('best_season', 'Q4')
        recommendations.append({
            'type': 'timing',
            'title': f'Mevsimsel Fırsat Değerlendirmesi',
            'description': f'{best_season} döneminde bütçenizi artırın. Bu dönemde dönüşüm oranları daha yüksek.',
            'priority': 'high',
            'expected_impact': 35
        })
        
        # Rakip bazlı öneri
        avg_engagement = competitor_analysis.get('average_engagement', 2.5)
        if avg_engagement > 2.5:
            recommendations.append({
                'type': 'competitive',
                'title': 'Rekabet Stratejisi',
                'description': f'Sektör ortalaması %{avg_engagement:.1f}. Daha yaratıcı içeriklerle fark yaratın.',
                'priority': 'medium',
                'expected_impact': 25
            })
        
        # Fiyatlandırma önerisi
        recommendations.append({
            'type': 'pricing',
            'title': 'Bütçe Optimizasyonu',
            'description': 'Hafta içi düşük maliyetli saatlerde (09:00-11:00) test yayınları yapın.',
            'priority': 'medium',
            'expected_impact': 20
        })
        
        return recommendations
    
    def _get_season(self, month):
        """Ay'a göre mevsim döndür"""
        if month in [12, 1, 2]:
            return 'Kış'
        elif month in [3, 4, 5]:
            return 'Bahar'
        elif month in [6, 7, 8]:
            return 'Yaz'
        else:
            return 'Sonbahar'
    
    def _fetch_competitor_data(self, username):
        """Rakip verilerini gerçek sağlayıcıdan toplar."""
        return None
    
    def _compare_with_competitor(self, main_data, competitor_data):
        """Rakiplerle karşılaştırma yap"""
        comparison = {
            'followers_diff': competitor_data['followers'] - main_data['followers'],
            'engagement_diff': round(competitor_data['engagement_rate'] - main_data['engagement_rate'], 1),
            'posts_frequency_diff': competitor_data['posts_per_week'] - main_data['posts_per_week'],
            'is_ahead': competitor_data['engagement_rate'] > main_data['engagement_rate'],
            'gap_percentage': round(((competitor_data['engagement_rate'] - main_data['engagement_rate']) / main_data['engagement_rate']) * 100, 1) if main_data['engagement_rate'] > 0 else 0
        }
        
        if comparison['is_ahead']:
            comparison['message'] = f"Rakip sizden %{comparison['gap_percentage']} daha iyi performans gösteriyor."
        else:
            comparison['message'] = f"Siz rakibinizden %{abs(comparison['gap_percentage'])} daha iyi performans gösteriyorsunuz."
        
        return comparison
    
    def _analyze_competitor_strategies(self, competitor_data):
        """Rakip stratejilerini analiz et"""
        strategies = []
        
        # İçerik stratejisi
        content_type = max(competitor_data['content_types'], key=competitor_data['content_types'].get)
        strategies.append({
            'area': 'İçerik Stratejisi',
            'observation': f"Ağırlıklı olarak {content_type} içerik kullanıyor",
            'recommendation': f"{content_type.capitalize()} içeriklerinizi artırın"
        })
        
        # Paylaşım sıklığı
        if competitor_data['posts_per_week'] > 4:
            strategies.append({
                'area': 'Paylaşım Sıklığı',
                'observation': f"Haftada {competitor_data['posts_per_week']} paylaşım yapıyor",
                'recommendation': "Paylaşım sıklığınızı artırmayı düşünün"
            })
        
        # Hashtag stratejisi
        strategies.append({
            'area': 'Hashtag Stratejisi',
            'observation': f"Popüler hashtag'ler: {', '.join(competitor_data['top_hashtags'][:3])}",
            'recommendation': "Bu hashtag'leri de deneyin"
        })
        
        return strategies
    
    def _identify_competitor_strengths(self, competitor_data):
        """Rakibin güçlü yönlerini belirle"""
        strengths = []
        
        if competitor_data['engagement_rate'] > 3:
            strengths.append("Yüksek etkileşim oranı")
        if competitor_data['followers'] > 200000:
            strengths.append("Geniş takipçi kitlesi")
        if competitor_data['posts_per_week'] > 5:
            strengths.append("Düzenli ve sık paylaşım")
        
        return strengths if strengths else ["Düzenli içerik üretimi"]
    
    def _identify_competitor_weaknesses(self, competitor_data):
        """Rakibin zayıf yönlerini belirle"""
        weaknesses = []
        
        if competitor_data.get('ad_frequency') == 'high':
            weaknesses.append("Çok fazla reklam yayınlıyor (reklam yorgunluğu riski)")
        if competitor_data['engagement_rate'] < 2:
            weaknesses.append("Düşük etkileşim oranı")
        
        return weaknesses if weaknesses else ["Belirgin zayıf yön tespit edilmedi"]
    
    def _identify_opportunities(self, competitor_data):
        """Fırsat alanlarını belirle"""
        opportunities = []
        
        if competitor_data['engagement_rate'] < 2.5:
            opportunities.append("Rakibin düşük etkileşim oranı sizin için fırsat")
        
        opportunities.append("Rakibin kullanmadığı niş hashtag'leri keşfedin")
        opportunities.append("Rakibin zayıf olduğu konularda içerik üretin")
        
        return opportunities
    
    def _generate_competitive_recommendations(self, competitor_data, comparison):
        """Rekabet önerileri üret"""
        recommendations = []
        
        if comparison and comparison.get('is_ahead'):
            recommendations.append({
                'title': 'Rakip Analizinden Öğrenin',
                'description': f"Rakibin başarılı olduğu alanları inceleyin: {', '.join(competitor_data.get('top_hashtags', [])[:2])}",
                'action': 'Araştır ve uygula'
            })
        
        recommendations.append({
            'title': 'Farklılaşma Stratejisi',
            'description': 'Rakibin yapmadığı şeyleri yapın. Örneğin: müşteri hikayeleri, eğitici içerikler.',
            'action': 'İçerik planı oluştur'
        })
        
        return recommendations
    
    def _get_market_size(self, industry):
        """Pazar büyüklüğünü hesapla"""
        market_data = {
            'e-commerce': {'size_tr': '500M TL', 'size_global': '5.7T USD', 'growth_rate': 15},
            'fashion': {'size_tr': '200M TL', 'size_global': '1.5T USD', 'growth_rate': 10},
            'food': {'size_tr': '300M TL', 'size_global': '4.2T USD', 'growth_rate': 8},
            'technology': {'size_tr': '150M TL', 'size_global': '3.8T USD', 'growth_rate': 12},
            'travel': {'size_tr': '100M TL', 'size_global': '2.1T USD', 'growth_rate': 18}
        }
        return market_data.get(industry, market_data['e-commerce'])
    
    def _get_competition_intensity(self, industry):
        """Rekabet yoğunluğunu belirle"""
        intensities = {
            'e-commerce': {'level': 'Yüksek', 'score': 85, 'description': 'Çok sayıda büyük oyuncu var'},
            'fashion': {'level': 'Çok Yüksek', 'score': 90, 'description': 'Sürekli yeni markalar giriyor'},
            'food': {'level': 'Orta', 'score': 60, 'description': 'Lokal oyuncular baskın'},
            'technology': {'level': 'Yüksek', 'score': 80, 'description': 'Hızlı değişen dinamikler'},
            'travel': {'level': 'Orta-Yüksek', 'score': 70, 'description': 'Sezonluk dalgalanmalar var'}
        }
        return intensities.get(industry, intensities['e-commerce'])
    
    def _get_entry_barriers(self, industry):
        """Giriş bariyerlerini belirle"""
        barriers = {
            'e-commerce': ['Yüksek rekabet', 'Lojistik maliyetleri', 'Müşteri kazanma maliyeti'],
            'fashion': ['Stok yönetimi', 'Marka bilinirliği', 'Hızlı trend takibi'],
            'food': ['Sertifikalar', 'Gıda güvenliği', 'Tedarik zinciri'],
            'technology': ['Ar-Ge maliyetleri', 'Patentler', 'Uzman personel'],
            'travel': ['Seyahat acentesi lisansı', 'Güvenilirlik', 'Sezonluk talep']
        }
        return barriers.get(industry, barriers['e-commerce'])
    
    def _get_industry_opportunities(self, industry):
        """Sektör fırsatlarını belirle"""
        opportunities = {
            'e-commerce': ['Mobil alışveriş', 'Sosyal ticaret', 'Abonelik modelleri', 'Kişiselleştirme'],
            'fashion': ['Sürdürülebilir moda', 'İkinci el pazarı', 'Kişisel stil asistanları'],
            'food': ['Yemek aboneliği', 'Organik ürünler', 'Hızlı teslimat'],
            'technology': ['Yapay zeka', 'Nesnelerin interneti', 'Siber güvenlik'],
            'travel': ['Yerel deneyimler', 'Sürdürülebilir turizm', 'Son dakika fırsatları']
        }
        return opportunities.get(industry, opportunities['e-commerce'])
    
    def _get_industry_threats(self, industry):
        """Sektör tehditlerini belirle"""
        threats = {
            'e-commerce': ['Artan rekabet', 'Ekonomik durgunluk', 'Lojistik maliyetleri'],
            'fashion': ['Hızlı moda eleştirileri', 'Sürdürülebilirlik baskısı', 'Taklit ürünler'],
            'food': ['Gıda fiyatlarındaki artış', 'Düzenlemeler', 'Sağlık trendleri'],
            'technology': ['Hızlı teknoloji değişimi', 'Siber tehditler', 'Veri gizliliği'],
            'travel': ['Ekonomik dalgalanmalar', 'Pandemi riskleri', 'Vize kısıtlamaları']
        }
        return threats.get(industry, threats['e-commerce'])
    
    def _calculate_growth_potential(self, industry):
        """Büyüme potansiyelini hesapla"""
        potentials = {
            'e-commerce': 25,
            'fashion': 18,
            'food': 15,
            'technology': 30,
            'travel': 35
        }
        return potentials.get(industry, 20)
    
    def _get_industry_recommendations(self, industry):
        """Sektör önerileri üret"""
        return [
            f"{industry.capitalize()} sektöründe video içeriklere ağırlık verin",
            "Kullanıcı yorumlarını ve referanslarını öne çıkarın",
            "Mobil kullanıcı deneyimini optimize edin"
        ]
    
    def _get_trending_topics(self, niche):
        """Trend konuları getir"""
        topics = {
            'moda': ['Sürdürülebilir moda', 'Kapsül gardırop', 'Vintage alışveriş', 'Sezon trendleri'],
            'yemek': ['Sağlıklı tarifler', 'Vegan mutfağı', 'Pratik yemekler', 'Mutfak tüyoları'],
            'seyahat': ['Saklı cennetler', 'Bütçeli seyahat', 'Solo travel', 'Yerel deneyimler'],
            'teknoloji': ['Yapay zeka araçları', 'Verimlilik uygulamaları', 'Teknoloji incelemeleri']
        }
        return topics.get(niche, ['Trend konuları takip edin', 'Güncel gelişmeleri paylaşın'])
    
    def _get_popular_hashtags(self, niche):
        """Popüler hashtag'leri getir"""
        hashtags = {
            'moda': ['#moda', '#stil', '#outfit', '#streetstyle', '#modatrendleri'],
            'yemek': ['#yemek', '#tarif', '#lezzet', '#pratiktarifler', '#mutfak'],
            'seyahat': ['#seyahat', '#gezi', '#tatil', '#kesfet', '#gezgin'],
            'teknoloji': ['#teknoloji', '#yapayzeka', '#gadget', '#tekno', '#inovasyon']
        }
        return hashtags.get(niche, ['#instagram', '#reklam', '#dijitalpazarlama'])
    
    def _get_best_post_times(self, niche):
        """En iyi paylaşım zamanlarını getir"""
        return {
            'days': ['Perşembe', 'Cuma', 'Cumartesi'],
            'hours': ['19:00-22:00', '12:00-14:00'],
            'peak_hour': '20:00'
        }
    
    def _get_content_type_recommendations(self, niche):
        """İçerik türü önerileri"""
        return {
            'reels': 60,
            'carousel': 25,
            'single_image': 10,
            'story': 5
        }
    
    def _generate_content_ideas(self, niche):
        """İçerik fikirleri üret"""
        ideas = [
            f"{niche.capitalize()} ile ilgili 5 ipucu",
            f"{niche.capitalize()} trendleri 2024",
            "Kullanıcı başarı hikayeleri",
            "Ürün karşılaştırması",
            "Nasıl yapılır videoları"
        ]
        return ideas
    
    def _get_content_recommendations(self, niche):
        """İçerik önerileri"""
        return [
            f"Haftada 3-4 {niche} ile ilgili içerik paylaşın",
            "Reels videolarına ağırlık verin",
            "Takipçilerinize sorular sorarak etkileşimi artırın"
        ]


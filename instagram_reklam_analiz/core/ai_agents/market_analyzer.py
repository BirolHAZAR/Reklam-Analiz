# core/ai_agents/market_analyzer.py
"""
Piyasa Analizi Modülü
Sektör trendleri ve pazar fırsatlarını tespit eder
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
    Piyasa trendlerini analiz eden sınıf
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
        
        
        # Fiyatlandırma içgörüleri
        pricing_insights = self._get_pricing_insights(industry)
        
        # Tüketici davranışı
        consumer_behavior = self._analyze_consumer_behavior(industry, location)
        
        # Yeni platformlar
        emerging_platforms = self._get_emerging_platforms()
        
        # AI ile trend analizi
        ai_analysis = self._get_ai_trend_analysis(seasonal_trends, consumer_behavior) if self.use_openai else "OpenAI kullanilamiyor; sahte piyasa analizi uretilmedi."
        
        return {
            'success': True,
            'seasonal_trends': seasonal_trends,
            'pricing_insights': pricing_insights,
            'consumer_behavior': consumer_behavior,
            'emerging_platforms': emerging_platforms,
            'ai_analysis': ai_analysis,
            'recommendations': self._generate_market_recommendations(seasonal_trends),
            'analyzed_at': timezone.now().isoformat()
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
    
    def _get_ai_trend_analysis(self, seasonal_trends, consumer_behavior):
        """AI ile trend analizi"""
        if not self.use_openai:
            return "Canli AI trend analizi tamamlanamadi; sahte trend analizi uretilmedi."
        
        try:
            prompt = f"""
Piyasa trendleri verilerine göre kapsamlı analiz yap:

Mevsimsel Trendler: {json.dumps(seasonal_trends, ensure_ascii=False, indent=2)[:500]}
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
    
    def _generate_market_recommendations(self, seasonal_trends):
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


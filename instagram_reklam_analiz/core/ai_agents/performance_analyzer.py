# core/ai_agents/performance_analyzer.py
"""
Instagram Reklam Performans Analizi Modülü
Yapay Zeka ile reklam kampanyalarının performansını analiz eder
"""

import json
import re
import numpy as np
from datetime import datetime, timedelta
from django.utils import timezone
from django.conf import settings
from core.services.openai_usage import record_openai_token_usage

# OpenAI entegrasyonu (opsiyonel)
try:
    from openai import OpenAI
    OPENAI_AVAILABLE = True
except ImportError:
    OPENAI_AVAILABLE = False


class PerformanceAnalyzer:
    """
    Instagram reklam kampanyalarının performansını analiz eden sınıf
    """
    
    def __init__(self, api_key=None, user=None, organization=None):
        self.user = user
        self.organization = organization
        """Analiz sınıfını başlat"""
        self.api_key = api_key or getattr(settings, 'OPENAI_API_KEY', None)
        self.use_openai = OPENAI_AVAILABLE and self.api_key
        self.client = OpenAI(api_key=self.api_key, timeout=60, max_retries=2) if self.use_openai else None
    
    def analyze_campaign_performance(self, campaign_data, metrics_data):
        """
        Kampanya performansını analiz et
        
        Args:
            campaign_data: Kampanya bilgileri (dict)
            metrics_data: Metrik verileri (list of dict veya QuerySet)
        
        Returns:
            dict: Analiz sonuçları
        """
        # Metrikleri hazırla
        metrics_list = self._prepare_metrics(metrics_data)
        
        if not metrics_list:
            return self._get_empty_analysis(campaign_data)
        
        # Performans skorunu hesapla
        performance_score = self._calculate_performance_score(metrics_list)
        
        # Güçlü ve zayıf yönleri belirle
        strengths, weaknesses = self._identify_strengths_weaknesses(metrics_list)
        
        # Trend analizi
        trends = self._analyze_trends(metrics_list)
        
        # AI ile derinlemesine analiz
        ai_analysis = self._get_ai_insights(campaign_data, metrics_list)
        
        # Öneriler üret
        recommendations = self._generate_recommendations(metrics_list, performance_score)
        
        return {
            'success': True,
            'performance_score': performance_score,
            'strengths': strengths,
            'weaknesses': weaknesses,
            'trends': trends,
            'ai_analysis': ai_analysis,
            'recommendations': recommendations,
            'analyzed_at': timezone.now().isoformat()
        }
    
    def analyze_instagram_account(self, account_data, media_stats):
        """
        Instagram hesabı performansını AI ile analiz et
        
        Args:
            account_data: Hesap bilgileri (dict)
            media_stats: Medya istatistikleri (dict)
        
        Returns:
            dict: Analiz sonuçları
        """
        if self.use_openai:
            return self._get_ai_account_analysis(account_data, media_stats)
        else:
            return "OpenAI kullanilamiyor; hesap analizi icin gercek AI ciktisi uretilemedi."
    
    def generate_recommendations(self, performance_data):
        """
        AI ile özel öneriler üret
        
        Args:
            performance_data: Performans verileri (dict)
        
        Returns:
            dict: Öneriler
        """
        if self.use_openai:
            return self._get_ai_recommendations(performance_data)
        else:
            return {"recommendations": [], "error": "OpenAI kullanilamiyor; sahte oneri uretilmedi."}
    
    def predict_performance(self, historical_data, future_days=30):
        """
        Gelecek performans tahmini yap
        
        Args:
            historical_data: Geçmiş veriler (list of dict)
            future_days: Tahmin edilecek gün sayısı
        
        Returns:
            dict: Tahmin sonuçları
        """
        if len(historical_data) < 7:
            return self._get_basic_prediction(historical_data, future_days)
        
        # Basit trend analizi
        recent_ctr = [d.get('ctr', 0) for d in historical_data[-7:]]
        recent_engagement = [d.get('engagement_rate', 0) for d in historical_data[-7:]]
        
        # Trend yönü
        ctr_trend = 'up' if len(recent_ctr) > 1 and recent_ctr[-1] > recent_ctr[0] else 'down'
        engagement_trend = 'up' if len(recent_engagement) > 1 and recent_engagement[-1] > recent_engagement[0] else 'down'
        
        # Ortalama değerler
        avg_ctr = np.mean(recent_ctr) if recent_ctr else 0
        avg_engagement = np.mean(recent_engagement) if recent_engagement else 0
        
        # Tahmini değerler
        predicted_ctr = avg_ctr * (1.05 if ctr_trend == 'up' else 0.95)
        predicted_engagement = avg_engagement * (1.05 if engagement_trend == 'up' else 0.95)
        
        return {
            'success': True,
            'predicted_ctr': round(predicted_ctr, 2),
            'predicted_engagement': round(predicted_engagement, 2),
            'trend': 'yükseliş' if ctr_trend == 'up' else 'düşüş',
            'confidence': 75 if len(historical_data) > 30 else 60,
            'recommended_budget_increase': 20 if ctr_trend == 'up' else 10,
            'future_days': future_days
        }
    
    def compare_campaigns(self, campaigns_data):
        """
        Birden fazla kampanyayı karşılaştır
        
        Args:
            campaigns_data: Kampanya verileri listesi
        
        Returns:
            dict: Karşılaştırma sonuçları
        """
        if not campaigns_data:
            return {'success': False, 'error': 'Kampanya verisi yok'}
        
        # En iyi kampanyayı bul
        best_campaign = max(campaigns_data, key=lambda x: x.get('performance_score', 0))
        worst_campaign = min(campaigns_data, key=lambda x: x.get('performance_score', 0))
        
        # Ortalama değerler
        avg_score = np.mean([c.get('performance_score', 0) for c in campaigns_data])
        
        return {
            'success': True,
            'total_campaigns': len(campaigns_data),
            'average_score': round(avg_score, 1),
            'best_campaign': {
                'name': best_campaign.get('name', 'Bilinmiyor'),
                'score': best_campaign.get('performance_score', 0),
                'ad_type': best_campaign.get('ad_type', 'Bilinmiyor')
            },
            'worst_campaign': {
                'name': worst_campaign.get('name', 'Bilinmiyor'),
                'score': worst_campaign.get('performance_score', 0),
                'ad_type': worst_campaign.get('ad_type', 'Bilinmiyor')
            },
            'recommendations': self._get_comparison_recommendations(best_campaign, worst_campaign)
        }
    
    def _prepare_metrics(self, metrics_data):
        """Metrik verilerini numpy array'e dönüştür"""
        metrics_list = []
        
        # QuerySet ise values'a çevir
        if hasattr(metrics_data, 'values'):
            metrics_data = metrics_data.values()
        
        for metric in metrics_data:
            # Decimal değerleri float'a çevir
            ctr = float(metric.get('ctr', 0)) if metric.get('ctr') else 0
            engagement = float(metric.get('engagement_rate', 0)) if metric.get('engagement_rate') else 0
            cpc = float(metric.get('cost_per_click', 0)) if metric.get('cost_per_click') else 0
            
            metrics_list.append({
                'impressions': int(metric.get('impressions', 0)),
                'clicks': int(metric.get('clicks', 0)),
                'ctr': ctr,
                'engagement_rate': engagement,
                'cost_per_click': cpc,
                'likes': int(metric.get('likes', 0)),
                'comments': int(metric.get('comments', 0)),
                'shares': int(metric.get('shares', 0))
            })
        
        return metrics_list
    
    def _calculate_performance_score(self, metrics_list):
        """Performans skorunu hesapla (0-100 arası)"""
        if not metrics_list:
            return 0
        
        # Son 7 gün veya tüm veriler
        recent_metrics = metrics_list[-7:] if len(metrics_list) >= 7 else metrics_list
        
        # Metrik ağırlıkları
        weights = {
            'ctr': 0.30,
            'engagement_rate': 0.30,
            'cost_per_click': 0.20,
            'likes_per_impression': 0.20
        }
        
        scores = []
        for metric in recent_metrics:
            # CTR skoru (ideal CTR: %1-3 arası)
            ctr = metric.get('ctr', 0)
            ctr_score = min(100, (ctr / 3) * 100) if ctr > 0 else 0
            
            # Etkileşim skoru (ideal: %2-5 arası)
            engagement = metric.get('engagement_rate', 0)
            engagement_score = min(100, (engagement / 5) * 100) if engagement > 0 else 0
            
            # CPC skoru (düşük CPC iyidir)
            cpc = metric.get('cost_per_click', 0)
            cpc_score = max(0, 100 - (cpc * 20)) if cpc > 0 else 50
            
            # Beğeni/Etkileşim oranı
            likes = metric.get('likes', 0)
            impressions = metric.get('impressions', 1)
            likes_ratio = (likes / impressions) * 100
            likes_score = min(100, likes_ratio * 10)
            
            # Ağırlıklı toplam
            weighted_score = (
                ctr_score * weights['ctr'] +
                engagement_score * weights['engagement_rate'] +
                cpc_score * weights['cost_per_click'] +
                likes_score * weights['likes_per_impression']
            )
            scores.append(weighted_score)
        
        return round(np.mean(scores), 1)
    
    def _identify_strengths_weaknesses(self, metrics_list):
        """Güçlü ve zayıf yönleri belirle"""
        strengths = []
        weaknesses = []
        
        if not metrics_list:
            return strengths, weaknesses
        
        # Son 7 günün ortalamaları
        recent = metrics_list[-7:] if len(metrics_list) >= 7 else metrics_list
        
        avg_ctr = np.mean([m.get('ctr', 0) for m in recent])
        avg_engagement = np.mean([m.get('engagement_rate', 0) for m in recent])
        avg_cpc = np.mean([m.get('cost_per_click', 0) for m in recent if m.get('cost_per_click', 0) > 0])
        total_likes = sum([m.get('likes', 0) for m in recent])
        total_comments = sum([m.get('comments', 0) for m in recent])
        
        # Sektör ortalamaları (örnek değerler)
        industry_avg_ctr = 0.89
        industry_avg_engagement = 1.5
        industry_avg_cpc = 0.50
        
        # CTR değerlendirmesi
        if avg_ctr > industry_avg_ctr:
            strengths.append(f"Tıklama oranı (CTR) sektör ortalamasının %{((avg_ctr/industry_avg_ctr - 1)*100):.0f} üzerinde")
        elif avg_ctr < industry_avg_ctr:
            weaknesses.append(f"Tıklama oranı (CTR) sektör ortalamasının altında (%{avg_ctr:.2f})")
        
        # Etkileşim değerlendirmesi
        if avg_engagement > industry_avg_engagement:
            strengths.append(f"Etkileşim oranı sektör ortalamasının üzerinde (%{avg_engagement:.2f})")
        elif avg_engagement < industry_avg_engagement:
            weaknesses.append(f"Etkileşim oranı düşük, içerikler yeniden değerlendirilmeli")
        
        # CPC değerlendirmesi
        if avg_cpc and avg_cpc < industry_avg_cpc:
            strengths.append(f"Tıklama başı maliyet (CPC) sektör ortalamasının altında (₺{avg_cpc:.2f})")
        elif avg_cpc and avg_cpc > industry_avg_cpc:
            weaknesses.append(f"Tıklama başı maliyet yüksek (₺{avg_cpc:.2f}), hedefleme iyileştirilmeli")
        
        # Beğeni/Yorum oranı
        if total_comments > 0 and total_likes / total_comments < 20:
            strengths.append("Takipçilerinizle güçlü bir etkileşiminiz var (yorum oranı yüksek)")
        elif total_likes > 0 and total_comments == 0:
            weaknesses.append("Yorum etkileşiminiz düşük, takipçilerinizle daha fazla iletişime geçin")
        
        # En az 3 madde olmasını sağla
        if len(strengths) < 3:
            strengths.append("Reklamlarınız düzenli olarak yayınlanıyor")
            strengths.append("Hedef kitlenizle uyumlu içerikler üretiyorsunuz")
        
        if len(weaknesses) < 3:
            weaknesses.append("Reklam metinlerinizi güçlendirebilirsiniz")
            weaknesses.append("Görsel kalitesini artırabilirsiniz")
        
        return strengths[:5], weaknesses[:5]
    
    def _analyze_trends(self, metrics_list):
        """Trend analizi yap"""
        if len(metrics_list) < 3:
            return {'direction': 'stable', 'message': 'Yeterli veri yok'}
        
        # Son 7 gün vs önceki 7 gün
        recent = metrics_list[-7:] if len(metrics_list) >= 14 else metrics_list[:len(metrics_list)//2]
        previous = metrics_list[-14:-7] if len(metrics_list) >= 14 else []
        
        if not previous:
            return {'direction': 'stable', 'message': 'Trend analizi için daha fazla veri gerekli'}
        
        recent_ctr = np.mean([m.get('ctr', 0) for m in recent])
        previous_ctr = np.mean([m.get('ctr', 0) for m in previous])
        
        if recent_ctr > previous_ctr * 1.1:
            direction = 'up'
            message = 'CTR değerinde yükseliş trendi görülüyor'
        elif recent_ctr < previous_ctr * 0.9:
            direction = 'down'
            message = 'CTR değerinde düşüş trendi var, dikkatli olun'
        else:
            direction = 'stable'
            message = 'CTR değerlerinde istikrarlı seyir'
        
        return {
            'direction': direction,
            'message': message,
            'recent_ctr': round(recent_ctr, 2),
            'previous_ctr': round(previous_ctr, 2),
            'change_percent': round(((recent_ctr - previous_ctr) / previous_ctr) * 100, 1) if previous_ctr > 0 else 0
        }
    
    def _get_ai_insights(self, campaign_data, metrics_list):
        """AI ile derinlemesine analiz yap"""
        # OpenAI API kullanımı
        if OPENAI_AVAILABLE and self.api_key:
            try:
                prompt = self._build_analysis_prompt(campaign_data, metrics_list)
                from core.services.ai_gateway import create_chat_completion
                response = create_chat_completion(
                    client=self.client, tariff_key="performance-insights",
                    user=self.user, organization=self.organization,
                    reference="performance_analyzer.insights",
                    model=getattr(settings, "OPENAI_MODEL", "gpt-4o"),
                    messages=[
                        {"role": "system", "content": "Sen bir Instagram reklam uzmanısın. Reklam performansını detaylı analiz ediyorsun."},
                        {"role": "user", "content": prompt}
                    ],
                    max_tokens=500,
                    temperature=0.7
                )
                return response.choices[0].message.content
            except Exception as e:
                pass
        
        # OpenAI kullanilamadiginda yalnizca mevcut metriklerden ozet don.
        recent_metrics = metrics_list[-7:] if len(metrics_list) >= 7 else metrics_list
        avg_ctr = np.mean([m.get('ctr', 0) for m in recent_metrics])
        avg_engagement = np.mean([m.get('engagement_rate', 0) for m in recent_metrics])
        impressions = sum([m.get('impressions', 0) for m in recent_metrics])
        clicks = sum([m.get('clicks', 0) for m in recent_metrics])
        return (
            f"- Kampanya: {campaign_data.get('campaign_name', 'Kampanya')}\n"
            f"- Ortalama CTR: %{avg_ctr:.2f}\n"
            f"- Ortalama etkileşim orani: %{avg_engagement:.2f}\n"
            f"- Toplam gosterim: {impressions:,}\n"
            f"- Toplam tiklama: {clicks:,}\n"
            "- OpenAI kapali veya kullanilamiyor; bu bolum yalnizca metrik ozeti icerir."
        )
    
    def _get_ai_account_analysis(self, account_data, media_stats):
        """AI ile hesap analizi"""
        return "Hesap analizi icin OpenAI prompt akisi bu modulde etkin degil."
    
    def _get_ai_recommendations(self, performance_data):
        """AI ile özel öneriler"""
        return {"recommendations": [], "error": "Oneri uretimi kampanya AI onerisi akisi uzerinden yapilmalidir."}
    
    def _get_basic_prediction(self, historical_data, future_days):
        """Basit tahmin (yetersiz veri durumunda)"""
        return {
            'success': True,
            'predicted_ctr': 0.85,
            'predicted_engagement': 1.2,
            'trend': 'bilinmiyor',
            'confidence': 40,
            'recommended_budget_increase': 10,
            'future_days': future_days,
            'warning': 'Yeterli geçmiş veri yok, tahmin düşük güvenilirliktedir'
        }
    
    def _get_comparison_recommendations(self, best_campaign, worst_campaign):
        """Karşılaştırma önerileri"""
        return [
            f"En iyi performans gösteren kampanya '{best_campaign.get('name')}', {best_campaign.get('ad_type')} reklam türünü kullanıyor",
            f"Başarısız kampanyanın hedefleme ayarlarını gözden geçirin",
            f"En iyi kampanyanın görsel/metin stilini diğer kampanyalara da uyarlayın"
        ]
    
    def _get_empty_analysis(self, campaign_data):
        """Boş analiz (veri yoksa)"""
        return {
            'success': False,
            'performance_score': 0,
            'strengths': ['Henüz yeterli veri yok'],
            'weaknesses': ['Veri toplanması bekleniyor'],
            'trends': {'direction': 'unknown', 'message': 'Yeterli veri yok'},
            'ai_analysis': 'Kampanya henüz yeterli veriye sahip değil. Veriler toplandıkça analiz yapılabilecektir.',
            'recommendations': [
                {'type': 'general', 'title': 'Veri Toplama', 'description': 'Kampanyanın devam etmesini bekleyin, daha fazla veri toplandığında detaylı analiz yapılabilecektir.', 'priority': 'low', 'expected_impact': 0}
            ],
            'analyzed_at': timezone.now().isoformat()
        }
    
    def _build_analysis_prompt(self, campaign_data, metrics_list):
        """AI analiz prompt'u oluştur"""
        recent_metrics = metrics_list[-14:] if len(metrics_list) >= 14 else metrics_list
        total_impressions = sum([m.get('impressions', 0) for m in recent_metrics])
        total_clicks = sum([m.get('clicks', 0) for m in recent_metrics])
        avg_ctr = np.mean([m.get('ctr', 0) for m in recent_metrics])
        avg_engagement = np.mean([m.get('engagement_rate', 0) for m in recent_metrics])
        
        prompt = f"""
Bir Instagram reklam kampanyasının performansını analiz et.

KAMPANYA BİLGİLERİ:
- Kampanya Adı: {campaign_data.get('campaign_name', 'Bilinmiyor')}
- Reklam Türü: {campaign_data.get('ad_type', 'Bilinmiyor')}
- Bütçe: {campaign_data.get('budget', 0)} TL

PERFORMANS METRİKLERİ (Son 14 gün):
- Toplam Gösterim: {total_impressions:,}
- Toplam Tıklanma: {total_clicks:,}
- Ortalama Tıklama Oranı (CTR): %{avg_ctr:.2f}
- Ortalama Etkileşim Oranı: %{avg_engagement:.2f}

Lütfen kısa ve öz bir analiz yap:
1. Performans değerlendirmesi
2. 2-3 iyileştirme önerisi
3. Genel puan (0-100 arası)

Analizi Türkçe yap.
"""
        return prompt


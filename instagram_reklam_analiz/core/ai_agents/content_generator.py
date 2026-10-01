# core/ai_agents/content_generator.py
"""
AI Destekli İçerik Üretici
Instagram için özgün içerik fikirleri, başlıklar, hashtag'ler ve post şablonları üretir
"""

import json
import random
import re
from datetime import datetime, timedelta
from django.utils import timezone
from django.conf import settings
from core.services.openai_usage import record_openai_token_usage

try:
    from openai import OpenAI
    OPENAI_AVAILABLE = True
except ImportError:
    OPENAI_AVAILABLE = False


class ContentGenerator:
    """
    AI destekli içerik üretici sınıfı
    Instagram gönderileri için yaratıcı içerik fikirleri üretir
    """
    
    def __init__(self, api_key=None, user=None, organization=None):
        self.user = user
        self.organization = organization
        """İçerik üreticiyi başlat"""
        self.api_key = api_key or getattr(settings, 'OPENAI_API_KEY', None)
        self.use_openai = OPENAI_AVAILABLE and self.api_key
        self.client = OpenAI(api_key=self.api_key, timeout=60, max_retries=2) if self.use_openai else None
    
    def generate_post_ideas(self, niche, count=5, content_type='mixed'):
        """Post fikirleri üret"""
        if self.use_openai:
            ideas = self._get_ai_post_ideas(niche, count, content_type)
        else:
            return {
                'success': False,
                'niche': niche,
                'content_type': content_type,
                'ideas': [],
                'error': 'OPENAI_API_KEY tanimli degil; sahte icerik fikri uretilmedi.',
                'generated_at': timezone.now().isoformat()
            }
        
        return {
            'success': True,
            'niche': niche,
            'content_type': content_type,
            'ideas': ideas,
            'generated_at': timezone.now().isoformat()
        }
    
    def generate_caption(self, topic, tone='friendly', length='medium', include_hashtags=True):
        """Caption üret"""
        if self.use_openai:
            caption = self._get_ai_caption(topic, tone, length, include_hashtags)
        else:
            return {
                'success': False,
                'topic': topic,
                'tone': tone,
                'caption': '',
                'hashtags': [],
                'character_count': 0,
                'error': 'OPENAI_API_KEY tanimli degil; sahte caption uretilmedi.',
            }
        
        return {
            'success': True,
            'topic': topic,
            'tone': tone,
            'caption': caption.get('text', ''),
            'hashtags': caption.get('hashtags', []),
            'character_count': len(caption.get('text', ''))
        }
    
    def generate_hashtags(self, niche, count=15):
        """Hashtag önerileri üret"""
        hashtags = self._get_hashtag_suggestions(niche, count)
        
        return {
            'success': True,
            'niche': niche,
            'popular_hashtags': hashtags['popular'],
            'niche_hashtags': hashtags['niche'],
            'brand_hashtags': hashtags['brand'],
            'all_hashtags': hashtags['popular'][:5] + hashtags['niche'][:5] + hashtags['brand'][:3]
        }
    
    def generate_post_template(self, content_type, niche):
        """Post şablonu oluştur"""
        templates = {
            'reels': self._get_reels_template(niche),
            'carousel': self._get_carousel_template(niche),
            'image': self._get_image_template(niche),
            'story': self._get_story_template(niche)
        }
        
        return {
            'success': True,
            'content_type': content_type,
            'template': templates.get(content_type, templates['image'])
        }
    
    def generate_content_calendar(self, niche, days=7):
        """Haftalık içerik takvimi oluştur"""
        calendar = []
        start_date = datetime.now()
        
        content_types = ['reels', 'carousel', 'image', 'story', 'reels', 'carousel', 'image']
        topics = self._get_daily_topics(niche, days)
        
        for i in range(days):
            date = start_date + timedelta(days=i)
            calendar.append({
                'date': date.strftime('%Y-%m-%d'),
                'day': date.strftime('%A'),
                'content_type': content_types[i % len(content_types)],
                'topic': topics[i] if i < len(topics) else f"{niche} ile ilgili ipucu",
                'best_time': self._get_best_time(date.strftime('%A')),
                'status': 'planlandı'
            })
        
        return {
            'success': True,
            'niche': niche,
            'days': days,
            'calendar': calendar,
            'recommendations': self._get_calendar_recommendations(niche)
        }
    
    def generate_engagement_questions(self, topic, count=5):
        """Etkileşim soruları üret"""
        questions = [
            f"Senin için {topic} denince akla ne geliyor?",
            f"{topic} ile ilgili en sevdiğin anı nedir?",
            f"{topic} hakkında en çok merak ettiğin şey ne?",
            f"Bu {topic} konusunda bir uzmana sorsan ne sorardın?",
            f"{topic} ile ilgili bir ipucu versen ne verirdin?"
        ]
        
        return {
            'success': True,
            'topic': topic,
            'questions': questions[:count],
            'poll_options': self._generate_poll_options(topic)
        }
    
    def _get_ai_post_ideas(self, niche, count, content_type):
        """AI ile post fikirleri üret"""
        try:
            prompt = f"""
{niche} nişi için Instagram {content_type} içerik fikirleri üret.
{count} farklı fikir üret.
Her fikir şunları içersin:
- Başlık
- İçerik açıklaması
- Hedef kitle
- Önerilen süre (reels için) veya görsel sayısı (carousel için)

Fikirler özgün, trend ve etkileşim odaklı olsun.
JSON formatında cevap ver.
"""
            from core.services.ai_gateway import create_chat_completion
            response = create_chat_completion(
                client=self.client, tariff_key="content-post-ideas",
                user=self.user, organization=self.organization,
                reference="content_generator.post_ideas",
                model=getattr(settings, "OPENAI_MODEL", "gpt-4o"),
                messages=[
                    {"role": "system", "content": "Sen kreatif bir içerik stratejistisin. Viral olabilecek içerik fikirleri üretiyorsun."},
                    {"role": "user", "content": prompt}
                ],
                max_tokens=800,
                temperature=0.8
            )
            return self._parse_ai_ideas(response.choices[0].message.content, count)
        except Exception as e:
            print(f"AI fikir üretme hatası: {str(e)}")
            return []
    
    def _get_ai_caption(self, topic, tone, length, include_hashtags):
        """AI ile caption üret"""
        try:
            length_map = {'short': 50, 'medium': 150, 'long': 300}
            max_length = length_map.get(length, 150)
            
            prompt = f"""
Konu: {topic}
Ton: {tone}
Maksimum karakter: {max_length}

Bu konu için Instagram caption'ı yaz.
Caption dikkat çekici, samimi ve harekete geçirici olsun.
{'Sonuna 5-10 ilgili hashtag ekle.' if include_hashtags else ''}
"""
            from core.services.ai_gateway import create_chat_completion
            response = create_chat_completion(
                client=self.client, tariff_key="content-caption",
                user=self.user, organization=self.organization,
                reference="content_generator.caption",
                model=getattr(settings, "OPENAI_MODEL", "gpt-4o"),
                messages=[
                    {"role": "system", "content": "Sen bir sosyal medya uzmanısın. Etkileyici caption'lar yazıyorsun."},
                    {"role": "user", "content": prompt}
                ],
                max_tokens=400,
                temperature=0.7
            )
            caption_text = response.choices[0].message.content
            hashtags = self._extract_hashtags(caption_text) if include_hashtags else []
            
            return {'text': caption_text, 'hashtags': hashtags}
        except Exception as e:
            print(f"AI caption hatası: {str(e)}")
            return {'text': '', 'hashtags': []}
    
    def _get_hashtag_suggestions(self, niche, count):
        """Hashtag önerileri"""
        hashtag_db = {
            'moda': {
                'popular': ['#moda', '#stil', '#outfit', '#streetstyle', '#kombin', '#giyim', '#modatrendleri', '#şık'],
                'niche': ['#kapsülgardırop', '#sürdürülebilirmoda', '#vintage', '#secondhand', '#slowfashion'],
                'brand': ['#markaadı', '#kampanya', '#indirim']
            },
            'yemek': {
                'popular': ['#yemek', '#tarif', '#lezzet', '#pratiktarifler', '#mutfak', '#evyemekleri', '#sağlıklıbeslenme'],
                'niche': ['#vegan', '#glutensiz', '#mealprep', '#fitrehber', '#şefönerisi'],
                'brand': ['#markaadı', '#lezzettüyoları', '#pratikçözümler']
            },
            'seyahat': {
                'popular': ['#seyahat', '#gezi', '#tatil', '#kesfet', '#gezgin', '#travelgram', '#wanderlust'],
                'niche': ['#saklıcennet', '#bütçeliseyahat', '#solotravel', '#roadtrip', '#yereldeneyimler'],
                'brand': ['#markaadı', '#gezirehberi', '#kampanyaseyahat']
            },
            'teknoloji': {
                'popular': ['#teknoloji', '#yapayzeka', '#gadget', '#tekno', '#inovasyon', '#dijitaldönüşüm'],
                'niche': ['#verimlilik', '#yazılım', '#donanım', '#sibergüvenlik', '#bulutbilişim'],
                'brand': ['#markaadı', '#teknolojihaberleri', '#ürünincelemesi']
            },
            'fitness': {
                'popular': ['#fitness', '#spor', '#sağlıklıyaşam', '#egzersiz', '#fit', '#motivasyon', '#wellness'],
                'niche': ['#evdespor', '#pilates', '#yoga', '#kardiyo', '#ağırlıkçalışması'],
                'brand': ['#markaadı', '#fitrehber', '#sağlıklıipuçları']
            }
        }
        
        data = hashtag_db.get(niche, hashtag_db['moda'])
        return {
            'popular': data['popular'][:min(7, count)],
            'niche': data['niche'][:min(5, count)],
            'brand': data['brand'][:min(3, count)]
        }
    
    def _get_reels_template(self, niche):
        """Reels şablonu"""
        return {
            'title': f'{niche.capitalize()} Reels İçerik Şablonu',
            'duration': '30-60 saniye',
            'structure': [
                {'time': '0-3 sn', 'content': 'Dikkat çekici açılış (soru veya ilginç görsel)'},
                {'time': '3-10 sn', 'content': 'Ana mesajın özeti'},
                {'time': '10-25 sn', 'content': 'Detaylı açıklama veya gösterim'},
                {'time': '25-30 sn', 'content': 'Harekete geçirici mesaj (CTA)'}
            ],
            'music_suggestion': 'Trend ve enerjik müzik',
            'caption_suggestion': 'Kısa ve merak uyandırıcı, soru ile bitir'
        }
    
    def _get_carousel_template(self, niche):
        """Carousel şablonu"""
        return {
            'title': f'{niche.capitalize()} Karousel İçerik Şablonu',
            'slide_count': 5,
            'structure': [
                {'slide': 1, 'content': 'Kapak: Dikkat çekici başlık ve görsel'},
                {'slide': 2, 'content': 'Giriş: Konunun özeti'},
                {'slide': 3, 'content': 'Ana içerik: Maddeler halinde bilgiler'},
                {'slide': 4, 'content': 'Örnekler veya görseller'},
                {'slide': 5, 'content': 'Özet ve CTA (yorum, kaydet, paylaş)'}
            ],
            'caption_suggestion': 'Uzun ve bilgilendirici, kaydetmeye teşvik eden mesaj'
        }
    
    def _get_image_template(self, niche):
        """Görsel şablonu"""
        return {
            'title': f'{niche.capitalize()} Görsel İçerik Şablonu',
            'design_tips': [
                'Yüksek kontrast kullan',
                'Metin görselin %20\'sinden az olsun',
                'Marka renklerini kullan',
                'Sade ve anlaşılır tasarım'
            ],
            'caption_suggestion': 'Bilgilendirici ve değer katan, soru sor'
        }
    
    def _get_story_template(self, niche):
        """Story şablonu"""
        return {
            'title': f'{niche.capitalize()} Story İçerik Şablonu',
            'interactive_elements': ['Anket', 'Soru kutusu', 'Kaydırma çubuğu', 'Bağlantı'],
            'duration': '5-15 saniye',
            'suggestion': 'Arka arkaya 3-5 story paylaşarak hikaye anlat'
        }
    
    def _get_daily_topics(self, niche, days):
        """Günlük konular"""
        topics = {
            'moda': ['Kombin önerileri', 'Trend renkler', 'Alışveriş ipuçları', 'Kıyafet bakımı', 'Sezon stilleri', 'Aksesuar seçimi', 'Kapsül gardırop'],
            'yemek': ['Pratik tarifler', 'Sağlıklı beslenme', 'Malzeme tüyoları', 'Sunum önerileri', 'Mevsimsel yemekler', 'Diyet tarifleri', 'Mutfak düzeni'],
            'seyahat': ['Seyahat planlaması', 'Bütçeli rotalar', 'Paketleme ipuçları', 'Yerel lezzetler', 'Konaklama önerileri', 'Aktiviteler', 'Güvenli seyahat']
        }
        return topics.get(niche, topics['moda'])[:days]
    
    def _get_best_time(self, day):
        """En iyi paylaşım zamanı"""
        times = {
            'Monday': '19:00',
            'Tuesday': '20:00',
            'Wednesday': '19:30',
            'Thursday': '20:30',
            'Friday': '21:00',
            'Saturday': '12:00',
            'Sunday': '15:00'
        }
        return times.get(day, '19:00')
    
    def _get_calendar_recommendations(self, niche):
        """Takvim önerileri"""
        return [
            f"Haftada 3-4 {niche} içeriği paylaşın",
            "Perşembe ve Cuma günleri akşam saatlerinde paylaşım yapın",
            "Reels videolarına ağırlık verin",
            "Takipçilerinize sorular sorarak etkileşimi artırın"
        ]
    
    def _generate_poll_options(self, topic):
        """Anket seçenekleri oluştur"""
        return [
            f"{topic} ile ilgili en sevdiğim şey",
            f"{topic} öğrenmek istediğim konu",
            f"{topic} hakkında bir ipucu"
        ]
    
    def _parse_ai_ideas(self, response_text, count):
        """AI yanıtını parse et"""
        try:
            json_match = re.search(r'\[.*\]', response_text, re.DOTALL)
            if json_match:
                ideas = json.loads(json_match.group())
                return ideas[:count]
        except Exception as e:
            print(f"JSON parse hatası: {str(e)}")
        return []
    
    def _extract_hashtags(self, text):
        """Metinden hashtag'leri çıkar"""
        hashtags = re.findall(r'#\w+', text)
        return hashtags[:10]


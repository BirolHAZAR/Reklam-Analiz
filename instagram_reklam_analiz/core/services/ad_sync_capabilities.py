"""Shared campaign-panel and worker capabilities; organic OAuth is not Ads OAuth."""

SUPPORTED_AD_SYNC_PLATFORMS = {"facebook", "google_ads", "linkedin"}


def ad_sync_unavailable_message(platform_code):
    return {
        "instagram": "Facebook ve Instagram yerleşimleri kampanya düzeyinde ayrılamıyor. Meta kampanyalarını Facebook bölümünde inceleyin. Organik paylaşımlarınız Organik İçerik bölümündedir.",
        "youtube": "Bu bağlantı YouTube kanal verileri içindir. YouTube reklam kampanyalarını bağlı Google Ads hesabında inceleyin.",
        "tiktok": "TikTok bağlantısında reklam kampanyası senkronizasyonu henüz desteklenmiyor. Organik içerik bağlantısı reklam hesabı erişimi sağlamaz.",
        "x": "X bağlantısında reklam kampanyası senkronizasyonu henüz desteklenmiyor.",
    }.get(platform_code, "Bu platformda reklam kampanyası senkronizasyonu henüz desteklenmiyor.")
